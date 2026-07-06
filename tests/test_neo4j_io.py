import json
from pathlib import Path

import pytest

from jd_query_graph.neo4j_io import (
    ArtifactGraph,
    ArtifactGraphError,
    Neo4jSettings,
    Neo4jWriteSummary,
    load_artifact_graph,
    load_neo4j_settings,
    query_neo4j_response,
    schema_statements,
    write_artifact_graph,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _term_row(
    term_id: str,
    text: str,
    *,
    canonical_source_key: str = "detail_id:1",
    confidence: object = 0.8,
    evidence_count: object = 1,
) -> dict[str, object]:
    return {
        "record_type": "term",
        "canonical_source_key": canonical_source_key,
        "term_id": term_id,
        "text": text,
        "normalized_text": text,
        "term_category": "TECH_OBJECT",
        "language": "en",
        "source": "llm_graphrag",
        "status": "candidate",
        "evidence_count": evidence_count,
        "evidence_text": f"evidence for {text}",
        "source_field": "title",
        "confidence": confidence,
        "extractor": "fake-graphrag",
        "model": "fake-model",
    }


def _relationship_row() -> dict[str, object]:
    return {
        "record_type": "relationship",
        "canonical_source_key": "detail_id:1",
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


class FakeNeo4jSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(self, cypher: str, **parameters: object) -> object:
        self.calls.append((cypher, parameters))
        return object()


class FakeRecord(dict):
    def data(self) -> dict[str, object]:
        return dict(self)


class FakeQuerySession:
    def __init__(
        self,
        term_rows: list[FakeRecord],
        relationship_rows: list[FakeRecord] | None = None,
    ) -> None:
        self.term_rows = term_rows
        self.relationship_rows = relationship_rows or []
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(self, cypher: str, **parameters: object) -> list[FakeRecord]:
        self.calls.append((cypher, parameters))
        if "RETURN properties(term) AS term" in cypher:
            return self.term_rows
        return self.relationship_rows


def _recall_observation(term_text: str, total: int = 0) -> dict[str, object]:
    return {
        "observation_id": f"obs:{term_text}",
        "provider": "fake-cts",
        "query_text": term_text,
        "query_mode": "exact",
        "total": total,
        "status": "ok",
        "recall_bucket": "0" if total == 0 else "1_9",
        "observed_at": "2026-07-03T00:00:00Z",
        "probe_run_id": "fake-probe-run",
        "request_hash": f"hash:{term_text}",
        "error_code": None,
        "created_at": "2026-07-03T00:00:00Z",
    }


def _term_record(
    text: str,
    *,
    term_id: str = "term:alpha",
    normalized_text: str | None = None,
    observation: dict[str, object] | None = None,
) -> FakeRecord:
    return FakeRecord(
        {
            "term": {
                "term_id": term_id,
                "text": text,
                "normalized_text": normalized_text or text,
            },
            "observation": observation,
        }
    )


def _relationship_record(
    source_text: str,
    target_text: str,
    *,
    observation_text: str,
) -> FakeRecord:
    return FakeRecord(
        {
            "relationship": {
                "source_text": source_text,
                "target_text": target_text,
                "relationship_type": "RELATED_TO",
                "evidence_text": "alpha beta",
                "confidence": 0.74,
            },
            "neighbor_observation": _recall_observation(observation_text),
        }
    )


def _single_line_cypher(cypher: str) -> str:
    return " ".join(cypher.split())


def test_neo4j_settings_default_to_local_compose_credentials(monkeypatch) -> None:
    for name in [
        "JD_QUERY_GRAPH_NEO4J_URI",
        "JD_QUERY_GRAPH_NEO4J_USER",
        "JD_QUERY_GRAPH_NEO4J_PASSWORD",
        "JD_QUERY_GRAPH_NEO4J_DATABASE",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = load_neo4j_settings()

    assert settings.uri == "bolt://localhost:7687"
    assert settings.user == "neo4j"
    assert settings.password_value == "password"
    assert settings.database == "neo4j"
    assert settings == Neo4jSettings()
    assert "password" not in repr(settings)


def test_neo4j_settings_read_environment_without_serializing_secret(
    monkeypatch,
) -> None:
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_URI", "bolt://example.invalid:7687")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_USER", "graph_user")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_PASSWORD", "graph_secret")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_DATABASE", "graph_db")

    settings = load_neo4j_settings()

    assert settings.uri == "bolt://example.invalid:7687"
    assert settings.user == "graph_user"
    assert settings.password_value == "graph_secret"
    assert settings.database == "graph_db"
    assert "graph_secret" not in repr(settings)
    assert "graph_secret" not in str(settings)
    assert "password" not in settings.model_dump()
    assert "graph_secret" not in str(settings.model_dump())
    assert "graph_secret" not in settings.model_dump_json()
    assert "graph_secret" not in str(dict(settings))
    assert not isinstance(dict(settings)["password"], str)


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
                "evidence_text": "candidate requirement alpha",
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
    assert graph.mentioned_in[0]["evidence_text"] == "candidate requirement alpha"
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
                "evidence_text": "alpha",
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
                "evidence_text": "beta",
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
                "evidence_text": "alpha beta",
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
            "evidence_text": "alpha beta",
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
                "evidence_text": "alpha",
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
                "evidence_text": "alpha beta",
                "source_jd_ids": ["detail_id:1"],
                "candidate_source": "fake-graphrag",
                "confidence": 0.74,
            },
        ],
    )

    with pytest.raises(ArtifactGraphError, match="missing target term"):
        load_artifact_graph(artifact_path)


def test_load_artifact_graph_rejects_duplicate_term_text_with_line_context(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    _write_jsonl(
        artifact_path,
        [
            _term_row("term:alpha", "shared-term", canonical_source_key="detail_id:1"),
            _term_row("term:beta", "shared-term", canonical_source_key="detail_id:2"),
        ],
    )

    with pytest.raises(
        ArtifactGraphError,
        match=(
            r"line 2: duplicate term text shared-term .*"
            r"first term_id term:alpha.*"
            r"first canonical_source_key detail_id:1.*"
            r"duplicate term_id term:beta.*"
            r"duplicate canonical_source_key detail_id:2"
        ),
    ):
        load_artifact_graph(artifact_path)


def test_load_artifact_graph_rejects_malformed_json_with_line_context(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    artifact_path.write_text('{"record_type": "term"\n', encoding="utf-8")

    with pytest.raises(ArtifactGraphError, match="line 1: invalid JSON"):
        load_artifact_graph(artifact_path)


@pytest.mark.parametrize(
    ("field_name", "expected_message"),
    [
        ("confidence", "line 1 field confidence: expected number"),
        ("evidence_count", "line 1 field evidence_count: expected number"),
    ],
)
def test_load_artifact_graph_rejects_invalid_numeric_fields_with_context(
    tmp_path: Path,
    field_name: str,
    expected_message: str,
) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    row = _term_row("term:alpha", "term-alpha")
    row[field_name] = "not-a-number"
    _write_jsonl(artifact_path, [row])

    with pytest.raises(ArtifactGraphError, match=expected_message):
        load_artifact_graph(artifact_path)


def test_load_artifact_graph_relationship_hash_is_stable_when_terms_reordered(
    tmp_path: Path,
) -> None:
    first_artifact_path = tmp_path / "first.jsonl"
    second_artifact_path = tmp_path / "second.jsonl"
    alpha = _term_row("term:alpha", "term-alpha")
    beta = _term_row("term:beta", "term-beta")
    relationship = _relationship_row()
    _write_jsonl(first_artifact_path, [alpha, beta, relationship])
    _write_jsonl(second_artifact_path, [beta, alpha, relationship])

    first_graph = load_artifact_graph(first_artifact_path)
    second_graph = load_artifact_graph(second_artifact_path)

    assert (
        first_graph.term_relationships[0]["relationship_hash"]
        == second_graph.term_relationships[0]["relationship_hash"]
    )


def test_write_artifact_graph_runs_schema_and_idempotent_merge_calls(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    _write_jsonl(
        artifact_path,
        [
            _term_row("term:alpha", "term-alpha"),
            _term_row("term:beta", "term-beta"),
            _relationship_row(),
        ],
    )
    graph = load_artifact_graph(artifact_path)
    session = FakeNeo4jSession()

    summary = write_artifact_graph(session, graph)

    assert summary == Neo4jWriteSummary(
        job_count=1,
        term_count=2,
        mentioned_in_count=2,
        relationship_count=1,
        recall_observation_count=2,
    )
    schema = schema_statements()
    assert [cypher for cypher, _ in session.calls[: len(schema)]] == schema
    combined_cypher = _single_line_cypher(
        "\n".join(cypher for cypher, _ in session.calls)
    )
    assert "MERGE (job:JobPosting {job_posting_id: $job_posting_id})" in combined_cypher
    assert "MERGE (term:QueryTerm {term_id: $term_id})" in combined_cypher
    assert (
        "MERGE (term)-[mentioned:MENTIONED_IN "
        "{evidence_hash: $evidence_hash}]->(job)"
        in combined_cypher
    )
    assert (
        "MERGE (observation:RecallObservation "
        "{observation_id: $observation_id})"
        in combined_cypher
    )
    assert (
        "MERGE (term)-[recall:HAS_RECALL "
        "{provider: $provider, query_mode: $query_mode, "
        "probe_run_id: $probe_run_id}]->(observation)"
        in combined_cypher
    )
    assert (
        "MERGE (source)-[relationship:RELATED_TO "
        "{relationship_hash: $relationship_hash}]->(target)"
        in combined_cypher
    )
    assert any(
        parameters.get("term_id") == "term:alpha"
        for _cypher, parameters in session.calls
    )
    assert any(
        parameters.get("term_id") == "term:beta"
        for _cypher, parameters in session.calls
    )


def test_write_artifact_graph_rejects_unsupported_term_relationship_type() -> None:
    graph = ArtifactGraph(
        jobs={},
        terms={},
        mentioned_in=[],
        term_relationships=[
            {
                "relationship_hash": "relationship:unsupported",
                "source_term_id": "term:alpha",
                "target_term_id": "term:beta",
                "relationship_type": "UNSUPPORTED",
            }
        ],
        recall_observations={},
        has_recall=[],
    )

    with pytest.raises(ArtifactGraphError, match="unsupported relationship type"):
        write_artifact_graph(FakeNeo4jSession(), graph, apply_schema_first=False)


def test_query_neo4j_response_returns_exact_match_with_outgoing_relationship() -> None:
    session = FakeQuerySession(
        term_rows=[
            _term_record(
                "term-alpha",
                observation=_recall_observation("term-alpha", total=3),
            )
        ],
        relationship_rows=[
            _relationship_record(
                "term-alpha",
                "term-beta",
                observation_text="term-beta",
            )
        ],
    )

    response = query_neo4j_response(session, "term-alpha")

    assert response == {
        "response_version": "query-response-v1",
        "snapshot_id": "neo4j-local",
        "generated_at": "2026-07-06T00:00:00Z",
        "query": "term-alpha",
        "normalized_query": "term-alpha",
        "exact": {
            "text": "term-alpha",
            "match_type": "exact",
            "cts_total": 3,
            "status": "ok",
        },
        "related_terms": [
            {
                "text": "term-beta",
                "relationship_type": "RELATED_TO",
                "direction": "outgoing",
                "cts_total": 0,
                "status": "ok",
                "evidence_text": "alpha beta",
                "confidence": 0.74,
            }
        ],
    }
    assert session.calls[0][1]["query"] == "term-alpha"
    assert session.calls[0][1]["normalized_query"] == "term-alpha"
    assert session.calls[1][1]["term_id"] == "term:alpha"
    assert sorted(session.calls[1][1]["relationship_types"]) == [
        "CO_OCCURS_WITH",
        "RELATED_TO",
        "SAME_AS",
        "VARIANT_OF",
    ]


def test_query_neo4j_response_returns_unmatched_unknown_response() -> None:
    response = query_neo4j_response(FakeQuerySession(term_rows=[]), "missing")

    assert response["exact"] == {
        "text": "missing",
        "match_type": "unmatched",
        "cts_total": None,
        "status": "unknown",
    }
    assert response["related_terms"] == []


def test_query_neo4j_response_returns_normalized_match() -> None:
    session = FakeQuerySession(
        term_rows=[
            _term_record(
                "term alpha",
                normalized_text="term alpha",
                observation=_recall_observation("term alpha", total=2),
            )
        ]
    )

    response = query_neo4j_response(session, "  TERM   ALPHA  ")

    assert response["normalized_query"] == "term alpha"
    assert response["exact"] == {
        "text": "term alpha",
        "match_type": "normalized",
        "cts_total": 2,
        "status": "ok",
    }
    assert (
        "ORDER BY CASE WHEN term.text = $query THEN 0 ELSE 1 END, "
        "term.term_id, term.text"
        in _single_line_cypher(session.calls[0][0])
    )


def test_query_neo4j_response_returns_incoming_relationship_direction() -> None:
    session = FakeQuerySession(
        term_rows=[
            _term_record(
                "term-beta",
                term_id="term:beta",
                observation=_recall_observation("term-beta", total=1),
            )
        ],
        relationship_rows=[
            _relationship_record(
                "term-alpha",
                "term-beta",
                observation_text="term-alpha",
            )
        ],
    )

    response = query_neo4j_response(session, "term-beta")

    assert response["related_terms"] == [
        {
            "text": "term-alpha",
            "relationship_type": "RELATED_TO",
            "direction": "incoming",
            "cts_total": 0,
            "status": "ok",
            "evidence_text": "alpha beta",
            "confidence": 0.74,
        }
    ]


def test_query_neo4j_response_rejects_unexpected_term_record_shape() -> None:
    session = FakeQuerySession(term_rows=[FakeRecord({"term": "not-a-map"})])

    with pytest.raises(ArtifactGraphError, match="term payload"):
        query_neo4j_response(session, "term-alpha")


def test_query_neo4j_response_rejects_unexpected_relationship_record_shape() -> None:
    session = FakeQuerySession(
        term_rows=[_term_record("term-alpha")],
        relationship_rows=[FakeRecord({"relationship": "not-a-map"})],
    )

    with pytest.raises(ArtifactGraphError, match="relationship payload"):
        query_neo4j_response(session, "term-alpha")


def test_query_neo4j_response_rejects_string_observation_total() -> None:
    observation = _recall_observation("term-alpha")
    observation["total"] = "3"
    session = FakeQuerySession(
        term_rows=[
            _term_record(
                "term-alpha",
                observation=observation,
            )
        ]
    )

    with pytest.raises(
        ArtifactGraphError,
        match="observation payload for term-alpha field total: expected int or null",
    ):
        query_neo4j_response(session, "term-alpha")


def test_query_neo4j_response_rejects_unexpected_observation_key() -> None:
    observation = _recall_observation("term-alpha")
    observation["unexpected"] = "value"
    session = FakeQuerySession(
        term_rows=[
            _term_record(
                "term-alpha",
                observation=observation,
            )
        ]
    )

    with pytest.raises(
        ArtifactGraphError,
        match="observation payload for term-alpha has unexpected keys: unexpected",
    ):
        query_neo4j_response(session, "term-alpha")


def test_query_neo4j_response_wraps_missing_observation_status() -> None:
    observation = _recall_observation("term-alpha")
    del observation["status"]
    session = FakeQuerySession(
        term_rows=[
            _term_record(
                "term-alpha",
                observation=observation,
            )
        ]
    )

    with pytest.raises(
        ArtifactGraphError,
        match="invalid recall observation for term-alpha",
    ):
        query_neo4j_response(session, "term-alpha")


def test_query_neo4j_response_wraps_negative_observation_total() -> None:
    observation = _recall_observation("term-alpha")
    observation["total"] = -1
    session = FakeQuerySession(
        term_rows=[
            _term_record(
                "term-alpha",
                observation=observation,
            )
        ]
    )

    with pytest.raises(
        ArtifactGraphError,
        match="invalid recall observation for term-alpha",
    ):
        query_neo4j_response(session, "term-alpha")
