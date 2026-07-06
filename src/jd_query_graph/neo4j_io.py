"""Neo4j write/read helpers for the local query-term graph loop."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from jd_query_graph.recall import FakeRecallProvider

TERM_RELATIONSHIP_TYPES = {"SAME_AS", "VARIANT_OF", "RELATED_TO", "CO_OCCURS_WITH"}


class Neo4jSession(Protocol):
    def run(self, cypher: str, **parameters: object) -> object:
        ...


class Neo4jSettings(BaseSettings):
    """Local Neo4j connection settings."""

    model_config = SettingsConfigDict(env_prefix="JD_QUERY_GRAPH_NEO4J_")

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: SecretStr = Field(default=SecretStr("password"), repr=False, exclude=True)
    database: str = "neo4j"

    @property
    def password_value(self) -> str:
        """Return the raw password for deliberate credential use."""

        return self.password.get_secret_value()


def load_neo4j_settings() -> Neo4jSettings:
    """Load Neo4j settings from environment variables with local compose defaults."""

    return Neo4jSettings()


def schema_statements() -> list[str]:
    """Return idempotent Neo4j schema statements for Phase 2A labels."""

    return [
        "CREATE CONSTRAINT job_posting_id_unique IF NOT EXISTS "
        "FOR (n:JobPosting) REQUIRE n.job_posting_id IS UNIQUE",
        "CREATE CONSTRAINT query_term_id_unique IF NOT EXISTS "
        "FOR (n:QueryTerm) REQUIRE n.term_id IS UNIQUE",
        "CREATE CONSTRAINT recall_observation_id_unique IF NOT EXISTS "
        "FOR (n:RecallObservation) REQUIRE n.observation_id IS UNIQUE",
        "CREATE INDEX job_posting_canonical_source_key IF NOT EXISTS "
        "FOR (n:JobPosting) ON (n.canonical_source_key)",
        "CREATE INDEX query_term_text IF NOT EXISTS FOR (n:QueryTerm) ON (n.text)",
        "CREATE INDEX query_term_normalized_text IF NOT EXISTS "
        "FOR (n:QueryTerm) ON (n.normalized_text)",
    ]


class ArtifactGraphError(ValueError):
    """Raised when an artifact row cannot be mapped to graph records."""


@dataclass(frozen=True)
class ArtifactGraph:
    jobs: dict[str, dict[str, Any]]
    terms: dict[str, dict[str, Any]]
    mentioned_in: list[dict[str, Any]]
    term_relationships: list[dict[str, Any]]
    recall_observations: dict[str, dict[str, Any]]
    has_recall: list[dict[str, Any]]


@dataclass(frozen=True)
class Neo4jWriteSummary:
    job_count: int
    term_count: int
    mentioned_in_count: int
    relationship_count: int
    recall_observation_count: int


def write_artifact_graph(
    session: Neo4jSession,
    graph: ArtifactGraph,
    apply_schema_first: bool = True,
) -> Neo4jWriteSummary:
    """Write an artifact graph to Neo4j with idempotent MERGE statements."""

    if apply_schema_first:
        for statement in schema_statements():
            session.run(statement)

    for job in graph.jobs.values():
        session.run(
            """
            MERGE (job:JobPosting {job_posting_id: $job_posting_id})
            SET job += $properties
            """,
            job_posting_id=job["job_posting_id"],
            properties=dict(job),
        )

    for term in graph.terms.values():
        session.run(
            """
            MERGE (term:QueryTerm {term_id: $term_id})
            SET term += $properties
            """,
            term_id=term["term_id"],
            properties=dict(term),
        )

    for mention in graph.mentioned_in:
        session.run(
            """
            MATCH (term:QueryTerm {term_id: $term_id})
            MATCH (job:JobPosting {job_posting_id: $job_posting_id})
            MERGE (term)-[mentioned:MENTIONED_IN {evidence_hash: $evidence_hash}]->(job)
            SET mentioned += $properties
            """,
            term_id=mention["term_id"],
            job_posting_id=mention["job_posting_id"],
            evidence_hash=mention["evidence_hash"],
            properties=dict(mention),
        )

    for observation in graph.recall_observations.values():
        session.run(
            """
            MERGE (observation:RecallObservation {observation_id: $observation_id})
            SET observation += $properties
            """,
            observation_id=observation["observation_id"],
            properties=dict(observation),
        )

    for recall in graph.has_recall:
        session.run(
            "\n"
            "            MATCH (term:QueryTerm {term_id: $term_id})\n"
            "            MATCH (observation:RecallObservation "
            "{observation_id: $observation_id})\n"
            "            MERGE (term)-[recall:HAS_RECALL "
            "{provider: $provider, query_mode: $query_mode, "
            "probe_run_id: $probe_run_id}]->(observation)\n"
            "            SET recall += $properties\n"
            "            ",
            term_id=recall["term_id"],
            observation_id=recall["observation_id"],
            provider=recall["provider"],
            query_mode=recall["query_mode"],
            probe_run_id=recall["probe_run_id"],
            properties=dict(recall),
        )

    for relationship in graph.term_relationships:
        session.run(
            _term_relationship_write_cypher(str(relationship["relationship_type"])),
            source_term_id=relationship["source_term_id"],
            target_term_id=relationship["target_term_id"],
            relationship_hash=relationship["relationship_hash"],
            properties=dict(relationship),
        )

    return Neo4jWriteSummary(
        job_count=len(graph.jobs),
        term_count=len(graph.terms),
        mentioned_in_count=len(graph.mentioned_in),
        relationship_count=len(graph.term_relationships),
        recall_observation_count=len(graph.recall_observations),
    )


def load_artifact_graph(
    path: Path,
    probe_run_id: str = "fake-probe-run",
) -> ArtifactGraph:
    """Load a fake extraction artifact and map it to graph write records."""

    if not path.exists():
        raise FileNotFoundError(f"artifact does not exist: {path}")

    rows = _read_artifact_rows(path)
    jobs: dict[str, dict[str, Any]] = {}
    terms: dict[str, dict[str, Any]] = {}
    term_ids_by_text: dict[str, str] = {}
    term_text_context: dict[str, tuple[str, str, int]] = {}
    mentioned_in: list[dict[str, Any]] = []

    for line_number, row in rows:
        if row.get("record_type") != "term":
            continue
        canonical_source_key = _required_str(row, "canonical_source_key", line_number)
        job_id = _stable_hash("job", canonical_source_key)
        source_url = row.get("source_url")
        jobs[canonical_source_key] = {
            "job_posting_id": job_id,
            "canonical_source_key": canonical_source_key,
            "source_url": None if source_url is None else str(source_url),
        }

        term_id = _required_str(row, "term_id", line_number)
        text = _required_str(row, "text", line_number)
        if text in term_text_context:
            first_term_id, first_source_key, first_line_number = term_text_context[text]
            raise ArtifactGraphError(
                f"line {line_number}: duplicate term text {text} "
                f"(first term_id {first_term_id}, "
                f"first canonical_source_key {first_source_key}, "
                f"first line {first_line_number}, duplicate term_id {term_id}, "
                f"duplicate canonical_source_key {canonical_source_key})"
            )
        term_text_context[text] = (term_id, canonical_source_key, line_number)
        terms[term_id] = {
            "term_id": term_id,
            "text": text,
            "normalized_text": _required_str(row, "normalized_text", line_number),
            "term_category": _required_str(row, "term_category", line_number),
            "language": _required_str(row, "language", line_number),
            "source": str(row.get("source", "llm_graphrag")),
            "status": str(row.get("status", "candidate")),
            "evidence_count": _int_field(row, "evidence_count", line_number, default=1),
        }
        term_ids_by_text[text] = term_id
        mentioned_in.append(_map_mention_row(row, line_number, term_id, job_id))

    recall_observations, has_recall = _map_fake_recall(
        terms.values(),
        probe_run_id=probe_run_id,
    )
    return ArtifactGraph(
        jobs=jobs,
        terms=terms,
        mentioned_in=mentioned_in,
        term_relationships=_map_relationship_rows(rows, term_ids_by_text),
        recall_observations=recall_observations,
        has_recall=has_recall,
    )


def _read_artifact_rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise ArtifactGraphError(
                    f"line {line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(payload, dict):
                raise ArtifactGraphError(f"line {line_number}: row must be an object")
            rows.append((line_number, payload))
    return rows


def _map_mention_row(
    row: dict[str, Any],
    line_number: int,
    term_id: str,
    job_id: str,
) -> dict[str, Any]:
    source_field = _required_str(row, "source_field", line_number)
    source_index = row.get("source_index")
    evidence_text = _required_str(row, "evidence_text", line_number)
    return {
        "evidence_hash": _stable_hash(
            "mentioned",
            term_id,
            job_id,
            source_field,
            "" if source_index is None else str(source_index),
            evidence_text,
        ),
        "term_id": term_id,
        "job_posting_id": job_id,
        "canonical_source_key": _required_str(
            row,
            "canonical_source_key",
            line_number,
        ),
        "source_field": source_field,
        "source_index": source_index,
        "evidence_text": evidence_text,
        "char_start": row.get("char_start"),
        "char_end": row.get("char_end"),
        "extractor": _required_str(row, "extractor", line_number),
        "model": _required_str(row, "model", line_number),
        "confidence": _number_field(row, "confidence", line_number, default=0),
        "status": str(row.get("status", "candidate")),
    }


def _map_fake_recall(
    terms: Any,
    probe_run_id: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    term_payloads = list(terms)
    provider = FakeRecallProvider(
        dict.fromkeys([str(term["text"]) for term in term_payloads], 0),
        probe_run_id=probe_run_id,
    )
    recall_observations: dict[str, dict[str, Any]] = {}
    has_recall: list[dict[str, Any]] = []
    for term in term_payloads:
        term_text = str(term["text"])
        observation = provider.count(term_text)
        recall_observations[term_text] = observation.model_dump()
        has_recall.append(
            {
                "term_id": str(term["term_id"]),
                "observation_id": observation.observation_id,
                "provider": observation.provider,
                "query_mode": observation.query_mode,
                "probe_run_id": observation.probe_run_id,
                "created_at": observation.created_at,
            }
        )
    return recall_observations, has_recall


def _map_relationship_rows(
    rows: list[tuple[int, dict[str, Any]]],
    term_ids_by_text: dict[str, str],
) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for line_number, row in rows:
        if row.get("record_type") != "relationship":
            continue
        source_text = _required_str(row, "source_text", line_number)
        target_text = _required_str(row, "target_text", line_number)
        source_term_id = term_ids_by_text.get(source_text)
        target_term_id = term_ids_by_text.get(target_text)
        if source_term_id is None:
            raise ArtifactGraphError(
                f"line {line_number}: missing source term {source_text}"
            )
        if target_term_id is None:
            raise ArtifactGraphError(
                f"line {line_number}: missing target term {target_text}"
            )

        relationship_type = _required_str(row, "relationship_type", line_number)
        if relationship_type not in TERM_RELATIONSHIP_TYPES:
            raise ArtifactGraphError(
                f"line {line_number}: unsupported relationship type {relationship_type}"
            )
        evidence_text = _required_str(row, "evidence_text", line_number)
        relationships.append(
            {
                "relationship_hash": _stable_hash(
                    "term-relationship",
                    source_term_id,
                    target_term_id,
                    relationship_type,
                    evidence_text,
                ),
                "source_term_id": source_term_id,
                "target_term_id": target_term_id,
                "source_text": source_text,
                "target_text": target_text,
                "relationship_type": relationship_type,
                "evidence_type": str(row.get("evidence_type", "same_jd_context")),
                "evidence_text": evidence_text,
                "source_jd_ids": row.get("source_jd_ids", []),
                "candidate_source": _required_str(row, "candidate_source", line_number),
                "confidence": _number_field(row, "confidence", line_number, default=0),
                "status": str(row.get("status", "candidate")),
                "relation_rationale": row.get("relation_rationale"),
                "extractor": str(row.get("extractor", "")),
                "model": str(row.get("model", "")),
            }
        )
    return relationships


def _term_relationship_write_cypher(relationship_type: str) -> str:
    if relationship_type not in TERM_RELATIONSHIP_TYPES:
        raise ArtifactGraphError(
            f"unsupported relationship type {relationship_type}"
        )
    return (
        "\n"
        "            MATCH (source:QueryTerm {term_id: $source_term_id})\n"
        "            MATCH (target:QueryTerm {term_id: $target_term_id})\n"
        f"            MERGE (source)-[relationship:{relationship_type} "
        "{relationship_hash: $relationship_hash}]->(target)\n"
        "            SET relationship += $properties\n"
        "            "
    )


def _required_str(row: dict[str, Any], field_name: str, line_number: int) -> str:
    value = row.get(field_name)
    if value is None or str(value) == "":
        raise ArtifactGraphError(f"line {line_number}: missing {field_name}")
    return str(value)


def _int_field(
    row: dict[str, Any],
    field_name: str,
    line_number: int,
    *,
    default: int,
) -> int:
    value = row.get(field_name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactGraphError(
            f"line {line_number} field {field_name}: expected number"
        )
    return value


def _number_field(
    row: dict[str, Any],
    field_name: str,
    line_number: int,
    *,
    default: float,
) -> float:
    value = row.get(field_name, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ArtifactGraphError(
            f"line {line_number} field {field_name}: expected number"
        )
    return float(value)


def _stable_hash(prefix: str, *parts: str) -> str:
    payload = "\x1f".join([prefix, *parts]).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"
