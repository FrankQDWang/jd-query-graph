# Neo4j Write Read Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the existing fake extraction artifact into local Neo4j and query Neo4j back through a CLI response that keeps the current artifact query shape.

**Architecture:** Keep Phase 2A as a narrow graph write/read loop: one Neo4j I/O module owns local settings, schema statements, artifact-to-graph mapping, idempotent Cypher writes, and query response assembly. The CLI only loads settings, opens a Neo4j session, calls the module, and prints JSON; extraction stays fake and CTS stays fake until the graph loop is proven.

**Tech Stack:** Python 3.12, Typer, Pydantic Settings, Neo4j Python driver, pytest, Ruff, local Neo4j 5.26 from `docker-compose.yml`.

---

## Scope Check

This is Phase 2A only. It does not run real GraphRAG extraction, real CTS calls, a full 9530-row build, a serving API, auth, rate limits, audit logging, or snapshot export.

The implementation should touch one new production module plus the CLI and README:

- Create `src/jd_query_graph/neo4j_io.py`: Neo4j settings, schema statements, artifact mapping, idempotent writer, Neo4j query reader, and driver session helper.
- Modify `src/jd_query_graph/cli.py`: add `write-neo4j-artifact` and `query-neo4j`.
- Modify `README.md`: document the Phase 2A local smoke commands.
- Create `tests/test_neo4j_io.py`: unit tests for settings, schema, mapping, write calls, and query assembly.
- Modify `tests/test_cli.py`: CLI tests using monkeypatched Neo4j functions.
- Create `tests/test_neo4j_integration.py`: opt-in live Neo4j idempotency test, skipped unless explicitly enabled.

## Completion Gate

Before claiming completion, run normal verification and an extra Brooks review through a subagent:

```text
Load the brooks-review skill and review the current branch diff against:
- docs/superpowers/specs/2026-07-06-neo4j-write-read-loop-design.md
- docs/superpowers/plans/2026-07-06-neo4j-write-read-loop.md

Focus on graph identity, idempotent writes, query response contract, error clarity, and test coverage.
Return PASS only if there are no blocker findings.
```

If the Brooks subagent returns blocker findings, fix them, rerun `pytest`, `ruff`, and the Brooks gate.

## Task 1: Neo4j Settings And Schema Statements

**Files:**
- Create: `src/jd_query_graph/neo4j_io.py`
- Test: `tests/test_neo4j_io.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_neo4j_io.py` with:

```python
from jd_query_graph.neo4j_io import Neo4jSettings, load_neo4j_settings, schema_statements


def test_neo4j_settings_default_to_local_compose_credentials(monkeypatch) -> None:
    for name in [
        "JD_QUERY_GRAPH_NEO4J_URI",
        "JD_QUERY_GRAPH_NEO4J_USER",
        "JD_QUERY_GRAPH_NEO4J_PASSWORD",
        "JD_QUERY_GRAPH_NEO4J_DATABASE",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = load_neo4j_settings()

    assert settings == Neo4jSettings(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
        database="neo4j",
    )


def test_neo4j_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_URI", "bolt://example.invalid:7687")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_USER", "graph_user")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_PASSWORD", "graph_secret")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_DATABASE", "graph_db")

    settings = load_neo4j_settings()

    assert settings == Neo4jSettings(
        uri="bolt://example.invalid:7687",
        user="graph_user",
        password="graph_secret",
        database="graph_db",
    )


def test_schema_statements_define_phase2a_constraints_and_indexes() -> None:
    statements = schema_statements()

    assert statements == [
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
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'jd_query_graph.neo4j_io'`.

- [ ] **Step 3: Implement settings and schema helpers**

Create `src/jd_query_graph/neo4j_io.py` with:

```python
"""Neo4j write/read helpers for the local query-term graph loop."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jSettings(BaseSettings):
    """Local Neo4j connection settings."""

    model_config = SettingsConfigDict(env_prefix="JD_QUERY_GRAPH_NEO4J_")

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = Field(default="password", repr=False)
    database: str = "neo4j"


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
```

- [ ] **Step 4: Run the task tests**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/jd_query_graph/neo4j_io.py tests/test_neo4j_io.py
git commit -m "feat: add neo4j settings and schema statements"
```

## Task 2: Artifact To Graph Mapping

**Files:**
- Modify: `src/jd_query_graph/neo4j_io.py`
- Test: `tests/test_neo4j_io.py`

- [ ] **Step 1: Add failing mapping tests**

Append to `tests/test_neo4j_io.py`:

```python
import json
from pathlib import Path

import pytest

from jd_query_graph.neo4j_io import ArtifactGraphError, load_artifact_graph


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_load_artifact_graph_maps_terms_jobs_evidence_and_fake_recall(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    _write_jsonl(
        artifact_path,
        [
            {
                "record_type": "term",
                "canonical_source_key": "detail_id:1",
                "source_url": "https://example.invalid/job/1",
                "term_id": "term:alpha",
                "text": "term-alpha",
                "normalized_text": "term-alpha",
                "term_category": "TECH_OBJECT",
                "language": "en",
                "source": "llm_graphrag",
                "status": "candidate",
                "evidence_count": 1,
                "evidence_text": "负责候选需求甲。",
                "source_field": "responsibilities",
                "source_index": 0,
                "char_start": 0,
                "char_end": 8,
                "confidence": 0.91,
                "extractor": "fake-graphrag",
                "model": "fake-model",
            }
        ],
    )

    graph = load_artifact_graph(artifact_path)

    assert list(graph.jobs.values()) == [
        {
            "job_posting_id": graph.jobs["detail_id:1"]["job_posting_id"],
            "canonical_source_key": "detail_id:1",
            "source_url": "https://example.invalid/job/1",
        }
    ]
    assert graph.terms["term:alpha"]["text"] == "term-alpha"
    assert graph.terms["term:alpha"]["normalized_text"] == "term-alpha"
    assert graph.mentioned_in[0]["term_id"] == "term:alpha"
    assert graph.mentioned_in[0]["canonical_source_key"] == "detail_id:1"
    assert graph.mentioned_in[0]["evidence_text"] == "负责候选需求甲。"
    assert graph.recall_observations["term-alpha"]["status"] == "ok"
    assert graph.recall_observations["term-alpha"]["total"] == 0
    assert graph.has_recall[0]["term_id"] == "term:alpha"


def test_load_artifact_graph_maps_relationship_rows(tmp_path: Path) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    _write_jsonl(
        artifact_path,
        [
            {
                "record_type": "term",
                "canonical_source_key": "detail_id:1",
                "source_url": "https://example.invalid/job/1",
                "term_id": "term:alpha",
                "text": "term-alpha",
                "normalized_text": "term-alpha",
                "term_category": "TECH_OBJECT",
                "language": "en",
                "evidence_text": "甲",
                "source_field": "title",
                "confidence": 0.8,
                "extractor": "fake-graphrag",
                "model": "fake-model",
            },
            {
                "record_type": "term",
                "canonical_source_key": "detail_id:1",
                "source_url": "https://example.invalid/job/1",
                "term_id": "term:beta",
                "text": "term-beta",
                "normalized_text": "term-beta",
                "term_category": "TECH_OBJECT",
                "language": "en",
                "evidence_text": "乙",
                "source_field": "title",
                "confidence": 0.7,
                "extractor": "fake-graphrag",
                "model": "fake-model",
            },
            {
                "record_type": "relationship",
                "canonical_source_key": "detail_id:1",
                "source_text": "term-alpha",
                "target_text": "term-beta",
                "relationship_type": "RELATED_TO",
                "evidence_type": "same_jd_context",
                "evidence_text": "甲乙",
                "source_jd_ids": ["detail_id:1"],
                "candidate_source": "fake-graphrag",
                "confidence": 0.74,
                "status": "candidate",
                "relation_rationale": "Both terms appear in one JD.",
                "extractor": "fake-graphrag",
                "model": "fake-model",
            },
        ],
    )

    graph = load_artifact_graph(artifact_path)

    assert graph.term_relationships == [
        {
            "relationship_hash": graph.term_relationships[0]["relationship_hash"],
            "source_term_id": "term:alpha",
            "target_term_id": "term:beta",
            "source_text": "term-alpha",
            "target_text": "term-beta",
            "relationship_type": "RELATED_TO",
            "evidence_type": "same_jd_context",
            "evidence_text": "甲乙",
            "source_jd_ids": ["detail_id:1"],
            "candidate_source": "fake-graphrag",
            "confidence": 0.74,
            "status": "candidate",
            "relation_rationale": "Both terms appear in one JD.",
            "extractor": "fake-graphrag",
            "model": "fake-model",
        }
    ]


def test_load_artifact_graph_rejects_relationship_with_missing_term(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    _write_jsonl(
        artifact_path,
        [
            {
                "record_type": "term",
                "canonical_source_key": "detail_id:1",
                "term_id": "term:alpha",
                "text": "term-alpha",
                "normalized_text": "term-alpha",
                "term_category": "TECH_OBJECT",
                "language": "en",
                "evidence_text": "甲",
                "source_field": "title",
                "confidence": 0.8,
                "extractor": "fake-graphrag",
                "model": "fake-model",
            },
            {
                "record_type": "relationship",
                "canonical_source_key": "detail_id:1",
                "source_text": "term-alpha",
                "target_text": "missing-term",
                "relationship_type": "RELATED_TO",
                "evidence_text": "甲乙",
                "source_jd_ids": ["detail_id:1"],
                "candidate_source": "fake-graphrag",
                "confidence": 0.74,
            },
        ],
    )

    with pytest.raises(ArtifactGraphError, match="missing target term"):
        load_artifact_graph(artifact_path)
```

- [ ] **Step 2: Run mapping tests and confirm failure**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: fail because `ArtifactGraphError` and `load_artifact_graph` are not defined.

- [ ] **Step 3: Implement artifact mapping**

Add these imports at the top of `src/jd_query_graph/neo4j_io.py`:

```python
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jd_query_graph.recall import FakeRecallProvider
```

Add these definitions below `schema_statements()`:

```python


TERM_RELATIONSHIP_TYPES = {"SAME_AS", "VARIANT_OF", "RELATED_TO", "CO_OCCURS_WITH"}


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
    mentioned_in: list[dict[str, Any]] = []

    for line_number, row in rows:
        record_type = row.get("record_type")
        if record_type != "term":
            continue
        canonical_source_key = _required_str(row, "canonical_source_key", line_number)
        source_url = row.get("source_url")
        job_id = _stable_hash("job", canonical_source_key)
        jobs[canonical_source_key] = {
            "job_posting_id": job_id,
            "canonical_source_key": canonical_source_key,
            "source_url": source_url if source_url is None else str(source_url),
        }
        term_id = _required_str(row, "term_id", line_number)
        text = _required_str(row, "text", line_number)
        terms[term_id] = {
            "term_id": term_id,
            "text": text,
            "normalized_text": _required_str(row, "normalized_text", line_number),
            "term_category": _required_str(row, "term_category", line_number),
            "language": _required_str(row, "language", line_number),
            "source": str(row.get("source", "llm_graphrag")),
            "status": str(row.get("status", "candidate")),
            "evidence_count": int(row.get("evidence_count", 1)),
        }
        term_ids_by_text[text] = term_id
        mentioned_in.append(
            {
                "evidence_hash": _stable_hash(
                    "mentioned",
                    term_id,
                    job_id,
                    str(row.get("source_field")),
                    str(row.get("source_index")),
                    str(row.get("evidence_text")),
                ),
                "term_id": term_id,
                "job_posting_id": job_id,
                "canonical_source_key": canonical_source_key,
                "source_field": _required_str(row, "source_field", line_number),
                "source_index": row.get("source_index"),
                "evidence_text": _required_str(row, "evidence_text", line_number),
                "char_start": row.get("char_start"),
                "char_end": row.get("char_end"),
                "extractor": _required_str(row, "extractor", line_number),
                "model": _required_str(row, "model", line_number),
                "confidence": float(row.get("confidence", 0)),
                "status": str(row.get("status", "candidate")),
            }
        )

    provider = FakeRecallProvider(
        dict.fromkeys([term["text"] for term in terms.values()], 0),
        probe_run_id=probe_run_id,
    )
    recall_observations: dict[str, dict[str, Any]] = {}
    has_recall: list[dict[str, Any]] = []
    for term in terms.values():
        observation = provider.count(str(term["text"]))
        observation_payload = observation.model_dump()
        recall_observations[str(term["text"])] = observation_payload
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
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ArtifactGraphError(f"line {line_number}: row must be an object")
            rows.append((line_number, payload))
    return rows


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
            raise ArtifactGraphError(f"line {line_number}: missing source term {source_text}")
        if target_term_id is None:
            raise ArtifactGraphError(f"line {line_number}: missing target term {target_text}")
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
                "confidence": float(row.get("confidence", 0)),
                "status": str(row.get("status", "candidate")),
                "relation_rationale": row.get("relation_rationale"),
                "extractor": str(row.get("extractor", "")),
                "model": str(row.get("model", "")),
            }
        )
    return relationships


def _required_str(row: dict[str, Any], field_name: str, line_number: int) -> str:
    value = row.get(field_name)
    if value is None or str(value) == "":
        raise ArtifactGraphError(f"line {line_number}: missing {field_name}")
    return str(value)


def _stable_hash(prefix: str, *parts: str) -> str:
    payload = "\u241f".join([prefix, *parts]).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"
```

- [ ] **Step 4: Run mapping tests**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: all tests in `tests/test_neo4j_io.py` pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/jd_query_graph/neo4j_io.py tests/test_neo4j_io.py
git commit -m "feat: map extraction artifacts to graph records"
```

## Task 3: Idempotent Neo4j Writer

**Files:**
- Modify: `src/jd_query_graph/neo4j_io.py`
- Test: `tests/test_neo4j_io.py`

- [ ] **Step 1: Add failing writer tests**

Append to `tests/test_neo4j_io.py`:

```python
from jd_query_graph.neo4j_io import ArtifactGraph, Neo4jWriteSummary, write_artifact_graph


class FakeResult:
    def single(self):
        return None


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(self, cypher: str, **parameters: object) -> FakeResult:
        self.calls.append((cypher, parameters))
        return FakeResult()


def test_write_artifact_graph_runs_schema_and_merge_statements() -> None:
    session = FakeSession()
    graph = ArtifactGraph(
        jobs={
            "detail_id:1": {
                "job_posting_id": "job:1",
                "canonical_source_key": "detail_id:1",
                "source_url": "https://example.invalid/job/1",
            }
        },
        terms={
            "term:alpha": {
                "term_id": "term:alpha",
                "text": "term-alpha",
                "normalized_text": "term-alpha",
                "term_category": "TECH_OBJECT",
                "language": "en",
                "source": "llm_graphrag",
                "status": "candidate",
                "evidence_count": 1,
            },
            "term:beta": {
                "term_id": "term:beta",
                "text": "term-beta",
                "normalized_text": "term-beta",
                "term_category": "TECH_OBJECT",
                "language": "en",
                "source": "llm_graphrag",
                "status": "candidate",
                "evidence_count": 1,
            }
        },
        mentioned_in=[
            {
                "evidence_hash": "mentioned:1",
                "term_id": "term:alpha",
                "job_posting_id": "job:1",
                "canonical_source_key": "detail_id:1",
                "source_field": "title",
                "source_index": None,
                "evidence_text": "title: 示例岗位",
                "char_start": 0,
                "char_end": 11,
                "extractor": "fake-graphrag",
                "model": "fake-model",
                "confidence": 0.5,
                "status": "candidate",
            }
        ],
        term_relationships=[
            {
                "relationship_hash": "rel:1",
                "source_term_id": "term:alpha",
                "target_term_id": "term:beta",
                "source_text": "term-alpha",
                "target_text": "term-beta",
                "relationship_type": "RELATED_TO",
                "evidence_type": "same_jd_context",
                "evidence_text": "alpha beta",
                "source_jd_ids": ["detail_id:1"],
                "candidate_source": "fake-graphrag",
                "confidence": 0.74,
                "status": "candidate",
                "relation_rationale": "Both terms appear in one JD.",
                "extractor": "fake-graphrag",
                "model": "fake-model",
            }
        ],
        recall_observations={
            "term-alpha": {
                "observation_id": "obs:1",
                "provider": "fake-cts",
                "query_text": "term-alpha",
                "query_mode": "exact",
                "total": 0,
                "status": "ok",
                "recall_bucket": "0",
                "observed_at": "2026-07-03T00:00:00Z",
                "probe_run_id": "fake-probe-run",
                "request_hash": "hash",
                "error_code": None,
                "created_at": "2026-07-03T00:00:00Z",
            }
        },
        has_recall=[
            {
                "term_id": "term:alpha",
                "observation_id": "obs:1",
                "provider": "fake-cts",
                "query_mode": "exact",
                "probe_run_id": "fake-probe-run",
                "created_at": "2026-07-03T00:00:00Z",
            }
        ],
    )

    summary = write_artifact_graph(session, graph)

    assert summary == Neo4jWriteSummary(
        job_count=1,
        term_count=2,
        mentioned_in_count=1,
        relationship_count=1,
        recall_observation_count=1,
    )
    cypher_text = "\n".join(cypher for cypher, _ in session.calls)
    assert "CREATE CONSTRAINT job_posting_id_unique IF NOT EXISTS" in cypher_text
    assert "MERGE (job:JobPosting {job_posting_id: $job_posting_id})" in cypher_text
    assert "MERGE (term:QueryTerm {term_id: $term_id})" in cypher_text
    assert "MERGE (term)-[rel:MENTIONED_IN {evidence_hash: $evidence_hash}]->(job)" in cypher_text
    assert "MERGE (obs:RecallObservation {observation_id: $observation_id})" in cypher_text
    assert "MERGE (term)-[rel:HAS_RECALL" in cypher_text
    assert "MERGE (source)-[rel:RELATED_TO {relationship_hash: $relationship_hash}]->(target)" in cypher_text
```

- [ ] **Step 2: Run writer tests and confirm failure**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: fail because `Neo4jWriteSummary` and `write_artifact_graph` are not defined.

- [ ] **Step 3: Implement writer**

Add this import at the top of `src/jd_query_graph/neo4j_io.py`:

```python
from collections.abc import Protocol
```

Add these definitions below the artifact mapping helpers:

```python


class Neo4jSession(Protocol):
    def run(self, cypher: str, **parameters: object) -> object:
        """Run a Cypher statement."""


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
    """Write mapped artifact graph records with stable MERGE keys."""

    if apply_schema_first:
        for statement in schema_statements():
            session.run(statement)
    for job in graph.jobs.values():
        session.run(
            "MERGE (job:JobPosting {job_posting_id: $job_posting_id}) "
            "SET job += $props",
            job_posting_id=job["job_posting_id"],
            props=job,
        )
    for term in graph.terms.values():
        session.run(
            "MERGE (term:QueryTerm {term_id: $term_id}) SET term += $props",
            term_id=term["term_id"],
            props=term,
        )
    for mention in graph.mentioned_in:
        session.run(
            "MATCH (term:QueryTerm {term_id: $term_id}) "
            "MATCH (job:JobPosting {job_posting_id: $job_posting_id}) "
            "MERGE (term)-[rel:MENTIONED_IN {evidence_hash: $evidence_hash}]->(job) "
            "SET rel += $props",
            term_id=mention["term_id"],
            job_posting_id=mention["job_posting_id"],
            evidence_hash=mention["evidence_hash"],
            props=mention,
        )
    for observation in graph.recall_observations.values():
        session.run(
            "MERGE (obs:RecallObservation {observation_id: $observation_id}) "
            "SET obs += $props",
            observation_id=observation["observation_id"],
            props=observation,
        )
    for recall_link in graph.has_recall:
        session.run(
            "MATCH (term:QueryTerm {term_id: $term_id}) "
            "MATCH (obs:RecallObservation {observation_id: $observation_id}) "
            "MERGE (term)-[rel:HAS_RECALL {provider: $provider, "
            "query_mode: $query_mode, probe_run_id: $probe_run_id}]->(obs) "
            "SET rel += $props",
            term_id=recall_link["term_id"],
            observation_id=recall_link["observation_id"],
            provider=recall_link["provider"],
            query_mode=recall_link["query_mode"],
            probe_run_id=recall_link["probe_run_id"],
            props=recall_link,
        )
    for relationship in graph.term_relationships:
        session.run(
            _term_relationship_merge_cypher(str(relationship["relationship_type"])),
            relationship_hash=relationship["relationship_hash"],
            source_term_id=relationship["source_term_id"],
            target_term_id=relationship["target_term_id"],
            props=relationship,
        )
    return Neo4jWriteSummary(
        job_count=len(graph.jobs),
        term_count=len(graph.terms),
        mentioned_in_count=len(graph.mentioned_in),
        relationship_count=len(graph.term_relationships),
        recall_observation_count=len(graph.recall_observations),
    )


def _term_relationship_merge_cypher(relationship_type: str) -> str:
    if relationship_type not in TERM_RELATIONSHIP_TYPES:
        raise ArtifactGraphError(f"unsupported relationship type {relationship_type}")
    return (
        "MATCH (source:QueryTerm {term_id: $source_term_id}) "
        "MATCH (target:QueryTerm {term_id: $target_term_id}) "
        f"MERGE (source)-[rel:{relationship_type} "
        "{relationship_hash: $relationship_hash}]->(target) "
        "SET rel += $props"
    )
```

- [ ] **Step 4: Run writer tests**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: all tests in `tests/test_neo4j_io.py` pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/jd_query_graph/neo4j_io.py tests/test_neo4j_io.py
git commit -m "feat: write artifact graph to neo4j"
```

## Task 4: Neo4j Query Reader

**Files:**
- Modify: `src/jd_query_graph/neo4j_io.py`
- Test: `tests/test_neo4j_io.py`

- [ ] **Step 1: Add failing query reader tests**

Append to `tests/test_neo4j_io.py`:

```python
from jd_query_graph.neo4j_io import query_neo4j_response


class FakeRecord(dict):
    def data(self) -> dict[str, object]:
        return dict(self)


class FakeQuerySession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(self, cypher: str, **parameters: object) -> list[FakeRecord]:
        self.calls.append((cypher, parameters))
        if "RETURN properties(term) AS term" in cypher:
            return [
                FakeRecord(
                    {
                        "term": {
                            "term_id": "term:alpha",
                            "text": "term-alpha",
                            "normalized_text": "term-alpha",
                        },
                        "observation": {
                            "observation_id": "obs:alpha",
                            "provider": "fake-cts",
                            "query_text": "term-alpha",
                            "query_mode": "exact",
                            "total": 0,
                            "status": "ok",
                            "recall_bucket": "0",
                            "observed_at": "2026-07-03T00:00:00Z",
                            "probe_run_id": "fake-probe-run",
                            "request_hash": "hash-alpha",
                            "error_code": None,
                            "created_at": "2026-07-03T00:00:00Z",
                        },
                    }
                )
            ]
        return [
            FakeRecord(
                {
                    "relationship": {
                        "source_text": "term-alpha",
                        "target_text": "term-beta",
                        "relationship_type": "RELATED_TO",
                        "evidence_text": "alpha beta",
                        "confidence": 0.74,
                    },
                    "neighbor_observation": {
                        "observation_id": "obs:beta",
                        "provider": "fake-cts",
                        "query_text": "term-beta",
                        "query_mode": "exact",
                        "total": 0,
                        "status": "ok",
                        "recall_bucket": "0",
                        "observed_at": "2026-07-03T00:00:00Z",
                        "probe_run_id": "fake-probe-run",
                        "request_hash": "hash-beta",
                        "error_code": None,
                        "created_at": "2026-07-03T00:00:00Z",
                    },
                }
            )
        ]


class FakeEmptyQuerySession:
    def run(self, cypher: str, **parameters: object) -> list[FakeRecord]:
        return []


def test_query_neo4j_response_returns_current_response_shape() -> None:
    response = query_neo4j_response(FakeQuerySession(), "term-alpha")

    assert response["response_version"] == "query-response-v1"
    assert response["snapshot_id"] == "neo4j-local"
    assert response["query"] == "term-alpha"
    assert response["exact"]["text"] == "term-alpha"
    assert response["exact"]["match_type"] == "exact"
    assert response["exact"]["status"] == "ok"
    assert response["related_terms"] == [
        {
            "text": "term-beta",
            "relationship_type": "RELATED_TO",
            "direction": "outgoing",
            "cts_total": 0,
            "status": "ok",
            "evidence_text": "alpha beta",
            "confidence": 0.74,
        }
    ]


def test_query_neo4j_response_returns_unknown_when_unmatched() -> None:
    response = query_neo4j_response(FakeEmptyQuerySession(), "missing")

    assert response["exact"] == {
        "text": "missing",
        "match_type": "unmatched",
        "cts_total": None,
        "status": "unknown",
    }
    assert response["related_terms"] == []
```

- [ ] **Step 2: Run query tests and confirm failure**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: fail because `query_neo4j_response` is not defined.

- [ ] **Step 3: Implement Neo4j-backed response assembly**

Add these imports at the top of `src/jd_query_graph/neo4j_io.py`:

```python
from jd_query_graph.query import build_query_response
from jd_query_graph.recall import RecallObservation
```

Add this reader below the writer functions:

```python


def query_neo4j_response(
    session: Neo4jSession,
    query: str,
    snapshot_id: str = "neo4j-local",
    generated_at: str = "2026-07-06T00:00:00Z",
) -> dict[str, Any]:
    """Read Neo4j and return the current query response shape."""

    normalized_query = " ".join(query.strip().casefold().split())
    term_rows = [
        record.data()
        for record in session.run(
            "MATCH (term:QueryTerm) "
            "WHERE term.text = $query OR term.normalized_text = $normalized_query "
            "OPTIONAL MATCH (term)-[:HAS_RECALL]->(obs:RecallObservation) "
            "RETURN properties(term) AS term, properties(obs) AS observation "
            "ORDER BY CASE WHEN term.text = $query THEN 0 ELSE 1 END "
            "LIMIT 1",
            query=query,
            normalized_query=normalized_query,
        )
    ]
    if not term_rows:
        return build_query_response(
            query=query,
            terms=[],
            relationships=[],
            observations={},
            snapshot_id=snapshot_id,
            generated_at=generated_at,
        )

    matched_term = term_rows[0]["term"]
    if not isinstance(matched_term, dict):
        raise ArtifactGraphError("Neo4j query returned term payload in unexpected shape")
    matched_text = str(matched_term["text"])
    matched_term_id = str(matched_term["term_id"])
    observations = _observation_mapping(matched_text, term_rows[0].get("observation"))

    relationship_rows = [
        record.data()
        for record in session.run(
            "MATCH (source:QueryTerm)-[rel]->(target:QueryTerm) "
            "WHERE type(rel) IN $relationship_types "
            "AND (source.term_id = $term_id OR target.term_id = $term_id) "
            "OPTIONAL MATCH (neighbor:QueryTerm)-[:HAS_RECALL]->(obs:RecallObservation) "
            "WHERE neighbor.term_id = CASE "
            "WHEN source.term_id = $term_id THEN target.term_id ELSE source.term_id END "
            "RETURN {source_text: source.text, target_text: target.text, "
            "relationship_type: type(rel), evidence_text: rel.evidence_text, "
            "confidence: rel.confidence} AS relationship, "
            "properties(obs) AS neighbor_observation",
            term_id=matched_term_id,
            relationship_types=sorted(TERM_RELATIONSHIP_TYPES),
        )
    ]

    relationships: list[dict[str, Any]] = []
    related_terms = [matched_text]
    for row in relationship_rows:
        relationship = row.get("relationship")
        if not isinstance(relationship, dict):
            raise ArtifactGraphError("Neo4j query returned relationship payload in unexpected shape")
        relationships.append(relationship)
        source_text = str(relationship["source_text"])
        target_text = str(relationship["target_text"])
        neighbor_text = target_text if source_text == matched_text else source_text
        related_terms.append(neighbor_text)
        observations.update(_observation_mapping(neighbor_text, row.get("neighbor_observation")))

    return build_query_response(
        query=query,
        terms=related_terms,
        relationships=relationships,
        observations=observations,
        snapshot_id=snapshot_id,
        generated_at=generated_at,
    )


def _observation_mapping(
    term_text: str,
    payload: object,
) -> dict[str, RecallObservation]:
    if not isinstance(payload, dict):
        return {}
    return {term_text: RecallObservation.model_validate(payload)}
```

- [ ] **Step 4: Run query reader tests**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_io.py -q
```

Expected: all tests in `tests/test_neo4j_io.py` pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/jd_query_graph/neo4j_io.py tests/test_neo4j_io.py
git commit -m "feat: query neo4j graph responses"
```

## Task 5: CLI Commands

**Files:**
- Modify: `src/jd_query_graph/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `tests/test_cli.py`:

```python
from jd_query_graph.neo4j_io import Neo4jWriteSummary


def test_write_neo4j_artifact_command_outputs_summary(monkeypatch, tmp_path: Path) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    artifact_path.write_text("", encoding="utf-8")

    class FakeSessionContext:
        def __enter__(self):
            return "session"

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

    monkeypatch.setattr("jd_query_graph.cli.load_neo4j_settings", lambda: "settings")
    monkeypatch.setattr("jd_query_graph.cli.neo4j_session", lambda settings: FakeSessionContext())
    monkeypatch.setattr("jd_query_graph.cli.load_artifact_graph", lambda path: "graph")
    monkeypatch.setattr(
        "jd_query_graph.cli.write_artifact_graph",
        lambda session, graph: Neo4jWriteSummary(
            job_count=1,
            term_count=1,
            mentioned_in_count=1,
            relationship_count=0,
            recall_observation_count=1,
        ),
    )
    runner = CliRunner()

    result = runner.invoke(app, ["write-neo4j-artifact", str(artifact_path)])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "job_count": 1,
        "mentioned_in_count": 1,
        "recall_observation_count": 1,
        "relationship_count": 0,
        "status": "ok",
        "term_count": 1,
    }


def test_query_neo4j_command_outputs_response(monkeypatch) -> None:
    class FakeSessionContext:
        def __enter__(self):
            return "session"

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

    monkeypatch.setattr("jd_query_graph.cli.load_neo4j_settings", lambda: "settings")
    monkeypatch.setattr("jd_query_graph.cli.neo4j_session", lambda settings: FakeSessionContext())
    monkeypatch.setattr(
        "jd_query_graph.cli.query_neo4j_response",
        lambda session, query: {
            "response_version": "query-response-v1",
            "snapshot_id": "neo4j-local",
            "generated_at": "2026-07-06T00:00:00Z",
            "query": query,
            "normalized_query": query,
            "exact": {
                "text": query,
                "match_type": "exact",
                "cts_total": 0,
                "status": "ok",
            },
            "related_terms": [],
        },
    )
    runner = CliRunner()

    result = runner.invoke(app, ["query-neo4j", "term-alpha"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["response"]["query"] == "term-alpha"
```

- [ ] **Step 2: Run CLI tests and confirm failure**

Run:

```bash
uv run --extra dev pytest tests/test_cli.py -q
```

Expected: fail because `write-neo4j-artifact`, `query-neo4j`, and imported CLI helpers do not exist.

- [ ] **Step 3: Add Neo4j session helper**

Add these imports at the top of `src/jd_query_graph/neo4j_io.py`:

```python
from collections.abc import Iterator, Protocol
from contextlib import contextmanager

from neo4j import GraphDatabase
```

Add this session helper below `load_neo4j_settings()`:

```python


@contextmanager
def neo4j_session(settings: Neo4jSettings) -> Iterator[Neo4jSession]:
    """Open a Neo4j session and close its driver after use."""

    driver = GraphDatabase.driver(settings.uri, auth=(settings.user, settings.password))
    try:
        with driver.session(database=settings.database) as session:
            yield session
    finally:
        driver.close()
```

- [ ] **Step 4: Add CLI imports and commands**

Modify `src/jd_query_graph/cli.py` imports:

```python
from jd_query_graph.neo4j_io import (
    load_artifact_graph,
    load_neo4j_settings,
    neo4j_session,
    query_neo4j_response,
    write_artifact_graph,
)
```

Add commands after `query_artifact`:

```python
@app.command("write-neo4j-artifact")
def write_neo4j_artifact(artifact_jsonl: Path) -> None:
    """Write a fake extraction artifact into Neo4j."""

    settings = load_neo4j_settings()
    graph = load_artifact_graph(artifact_jsonl)
    with neo4j_session(settings) as session:
        summary = write_artifact_graph(session, graph)
    _echo_json({"status": "ok", **summary.__dict__})


@app.command("query-neo4j")
def query_neo4j(query: str) -> None:
    """Query the Neo4j-backed graph response."""

    settings = load_neo4j_settings()
    with neo4j_session(settings) as session:
        response = query_neo4j_response(session, query)
    _echo_json({"status": "ok", "response": response})
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
uv run --extra dev pytest tests/test_cli.py -q
```

Expected: all CLI tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/jd_query_graph/cli.py src/jd_query_graph/neo4j_io.py tests/test_cli.py
git commit -m "feat: add neo4j write and query cli commands"
```

## Task 6: Opt-In Live Neo4j Idempotency Test

**Files:**
- Create: `tests/test_neo4j_integration.py`
- Test: `tests/test_neo4j_integration.py`

- [ ] **Step 1: Add skipped-by-default integration test**

Create `tests/test_neo4j_integration.py`:

```python
import json
import os
import uuid
from pathlib import Path

import pytest

from jd_query_graph.neo4j_io import (
    load_artifact_graph,
    load_neo4j_settings,
    neo4j_session,
    query_neo4j_response,
    write_artifact_graph,
)


pytestmark = pytest.mark.skipif(
    os.getenv("JD_QUERY_GRAPH_RUN_NEO4J_TESTS") != "1",
    reason="set JD_QUERY_GRAPH_RUN_NEO4J_TESTS=1 to run live Neo4j tests",
)


def test_live_neo4j_write_is_idempotent_and_queryable(tmp_path: Path) -> None:
    run_id = uuid.uuid4().hex
    artifact_path = tmp_path / "extraction.jsonl"
    rows = [
        {
            "record_type": "term",
            "canonical_source_key": f"test:{run_id}:1",
            "source_url": "https://example.invalid/job/1",
            "term_id": f"term:{run_id}:alpha",
            "text": f"term-alpha-{run_id}",
            "normalized_text": f"term-alpha-{run_id}",
            "term_category": "TECH_OBJECT",
            "language": "en",
            "source": "llm_graphrag",
            "status": "candidate",
            "evidence_count": 1,
            "evidence_text": "alpha",
            "source_field": "title",
            "source_index": None,
            "char_start": 0,
            "char_end": 5,
            "confidence": 0.9,
            "extractor": "fake-graphrag",
            "model": "fake-model",
        }
    ]
    artifact_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    graph = load_artifact_graph(artifact_path, probe_run_id=f"test:{run_id}")
    settings = load_neo4j_settings()

    with neo4j_session(settings) as session:
        try:
            first = write_artifact_graph(session, graph)
            second = write_artifact_graph(session, graph)
            response = query_neo4j_response(session, f"term-alpha-{run_id}")

            assert first == second
            assert first.job_count == 1
            assert first.term_count == 1
            assert first.mentioned_in_count == 1
            assert first.recall_observation_count == 1
            assert response["exact"]["status"] == "ok"
        finally:
            session.run(
                "MATCH (n) WHERE n.term_id STARTS WITH $term_prefix "
                "OR n.canonical_source_key STARTS WITH $source_prefix "
                "OR n.probe_run_id = $probe_run_id DETACH DELETE n",
                term_prefix=f"term:{run_id}:",
                source_prefix=f"test:{run_id}:",
                probe_run_id=f"test:{run_id}",
            )
```

- [ ] **Step 2: Run normal tests and confirm the integration test is skipped**

Run:

```bash
uv run --extra dev pytest tests/test_neo4j_integration.py -q
```

Expected: `1 skipped`.

- [ ] **Step 3: Run live test against local Neo4j**

Run:

```bash
docker compose up -d neo4j
JD_QUERY_GRAPH_RUN_NEO4J_TESTS=1 uv run --extra dev pytest tests/test_neo4j_integration.py -q
```

Expected: `1 passed`.

- [ ] **Step 4: Commit**

Run:

```bash
git add tests/test_neo4j_integration.py
git commit -m "test: add live neo4j write read smoke"
```

## Task 7: README Smoke Path And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document Phase 2A commands**

Append to `README.md`:

````markdown
## Phase 2A Neo4j Write/Read Loop

Start local Neo4j and build a small fake extraction artifact:

```bash
docker compose up -d neo4j
uv run --extra dev jd-query-graph copy-corpus
uv run --extra dev jd-query-graph write-fake-extraction-artifact \
  data/corpora/bytedance/factual_jobs_mainland.jsonl \
  --output artifacts/extraction/sample.jsonl \
  --limit 20
```

Write the artifact into Neo4j. Running this command twice should report the
same counts and must not create duplicate graph records:

```bash
uv run --extra dev jd-query-graph write-neo4j-artifact artifacts/extraction/sample.jsonl
uv run --extra dev jd-query-graph write-neo4j-artifact artifacts/extraction/sample.jsonl
```

Query a term from the artifact:

```bash
uv run --extra dev jd-query-graph query-neo4j "title: 示例岗位"
```

The response keeps the Phase 1 query shape: `exact`, `related_terms`, evidence,
relationship status, and fake recall status.
````

- [ ] **Step 2: Run unit verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
```

Expected: all tests pass and Ruff reports no issues.

- [ ] **Step 3: Run local CLI smoke**

Run:

```bash
docker compose up -d neo4j
uv run --extra dev jd-query-graph copy-corpus
uv run --extra dev jd-query-graph write-fake-extraction-artifact \
  data/corpora/bytedance/factual_jobs_mainland.jsonl \
  --output artifacts/extraction/sample.jsonl \
  --limit 20
uv run --extra dev jd-query-graph write-neo4j-artifact artifacts/extraction/sample.jsonl
uv run --extra dev jd-query-graph write-neo4j-artifact artifacts/extraction/sample.jsonl
uv run --extra dev jd-query-graph query-neo4j "$(python - <<'PY'
import json
from pathlib import Path
for line in Path('artifacts/extraction/sample.jsonl').read_text(encoding='utf-8').splitlines():
    row = json.loads(line)
    if row.get('record_type') == 'term':
        print(row['text'])
        break
PY
)"
```

Expected:

- the fake artifact command prints `"job_count": 20`;
- both Neo4j write commands print `"job_count": 20`, `"term_count": 20`, and `"mentioned_in_count": 20`;
- the query command prints `"status": "ok"` and a response with `response_version` set to `query-response-v1`.

- [ ] **Step 4: Run Brooks subagent gate**

Dispatch a subagent with this prompt:

```text
Load the brooks-review skill and review the current branch diff against:
- docs/superpowers/specs/2026-07-06-neo4j-write-read-loop-design.md
- docs/superpowers/plans/2026-07-06-neo4j-write-read-loop.md

Focus on graph identity, idempotent writes, query response contract, error clarity, and test coverage.
Return PASS only if there are no blocker findings.
```

Expected: Brooks subagent returns `PASS` or only non-blocking findings. If it returns blockers, fix them and rerun `uv run --extra dev pytest -q`, `uv run --extra dev ruff check .`, and the Brooks gate.

- [ ] **Step 5: Commit README after verification**

Run:

```bash
git add README.md
git commit -m "docs: add neo4j write read smoke path"
```

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short --branch
```

Expected: working tree is clean except the branch may be ahead of `origin/main`.
