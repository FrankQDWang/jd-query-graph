import json
from pathlib import Path

import pytest

from jd_query_graph.neo4j_io import (
    ArtifactGraphError,
    Neo4jSettings,
    load_artifact_graph,
    load_neo4j_settings,
    schema_statements,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


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
