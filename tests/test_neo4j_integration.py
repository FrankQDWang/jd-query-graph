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
            "source_url": f"https://example.invalid/job/{run_id}",
            "term_id": f"term:{run_id}:alpha",
            "text": f"term-alpha-{run_id}",
            "normalized_text": f"term-alpha-{run_id}",
            "term_category": "TECH_OBJECT",
            "language": "en",
            "source": "llm_graphrag",
            "status": "candidate",
            "evidence_count": 1,
            "evidence_text": f"alpha evidence {run_id}",
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
            count_rows = list(
                session.run(
                    """
                    MATCH (job:JobPosting {canonical_source_key: $source_key})
                    WITH count(job) AS job_count
                    MATCH (term:QueryTerm {term_id: $term_id})
                    WITH job_count, count(term) AS term_count
                    MATCH (observation:RecallObservation {
                      probe_run_id: $probe_run_id
                    })
                    WITH job_count, term_count,
                      count(observation) AS recall_observation_count
                    MATCH (term:QueryTerm {term_id: $term_id})
                      -[mentioned:MENTIONED_IN]->
                      (job:JobPosting {canonical_source_key: $source_key})
                    WITH job_count, term_count, recall_observation_count,
                      count(mentioned) AS mentioned_in_count
                    MATCH (term:QueryTerm {term_id: $term_id})
                      -[recall:HAS_RECALL]->
                      (observation:RecallObservation {
                        probe_run_id: $probe_run_id
                      })
                    RETURN job_count, term_count, mentioned_in_count,
                      recall_observation_count, count(recall) AS has_recall_count
                    """,
                    source_key=f"test:{run_id}:1",
                    term_id=f"term:{run_id}:alpha",
                    probe_run_id=f"test:{run_id}",
                )
            )
            response = query_neo4j_response(session, f"term-alpha-{run_id}")

            assert first == second
            assert first.job_count == 1
            assert first.term_count == 1
            assert first.mentioned_in_count == 1
            assert first.relationship_count == 0
            assert first.recall_observation_count == 1
            assert len(count_rows) == 1
            assert count_rows[0].data() == {
                "job_count": 1,
                "term_count": 1,
                "mentioned_in_count": 1,
                "recall_observation_count": 1,
                "has_recall_count": 1,
            }
            assert response["exact"]["status"] == "ok"
        finally:
            session.run(
                """
                MATCH (n)
                WHERE n.term_id STARTS WITH $term_prefix
                  OR n.canonical_source_key STARTS WITH $source_prefix
                  OR n.probe_run_id = $probe_run_id
                DETACH DELETE n
                """,
                term_prefix=f"term:{run_id}:",
                source_prefix=f"test:{run_id}:",
                probe_run_id=f"test:{run_id}",
            )
