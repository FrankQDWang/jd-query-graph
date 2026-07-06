from jd_query_graph.query import build_query_response
from jd_query_graph.recall import RecallObservation


def test_build_query_response_returns_exact_and_related_terms() -> None:
    response = build_query_response(
        query="term-alpha",
        terms=["term-alpha", "term-beta"],
        relationships=[
            {
                "source_text": "term-alpha",
                "target_text": "term-beta",
                "relationship_type": "RELATED_TO",
                "status": "candidate",
                "evidence_text": "负责候选需求甲。负责候选需求乙。",
                "confidence": 0.74,
            }
        ],
        observations={
            "term-alpha": RecallObservation(
                observation_id="obs-alpha",
                provider="fake-cts",
                query_text="term-alpha",
                query_mode="exact",
                total=42,
                status="ok",
                recall_bucket="10_99",
                observed_at="2026-07-03T00:00:00Z",
                probe_run_id="fake-probe-run",
                request_hash="hash-alpha",
                created_at="2026-07-03T00:00:00Z",
            ),
            "term-beta": RecallObservation(
                observation_id="obs-beta",
                provider="fake-cts",
                query_text="term-beta",
                query_mode="exact",
                total=8,
                status="ok",
                recall_bucket="1_9",
                observed_at="2026-07-03T00:00:00Z",
                probe_run_id="fake-probe-run",
                request_hash="hash-beta",
                created_at="2026-07-03T00:00:00Z",
            ),
        },
    )

    assert response["exact"]["cts_total"] == 42
    assert response["exact"]["match_type"] == "exact"
    assert response["related_terms"] == [
        {
            "text": "term-beta",
            "relationship_type": "RELATED_TO",
            "direction": "outgoing",
            "cts_total": 8,
            "status": "ok",
            "relationship_status": "candidate",
            "evidence_text": "负责候选需求甲。负责候选需求乙。",
            "confidence": 0.74,
        }
    ]


def test_build_query_response_marks_unmatched_query() -> None:
    response = build_query_response(
        query="missing",
        terms=["term-alpha"],
        relationships=[],
        observations={},
    )

    assert response["exact"]["text"] == "missing"
    assert response["exact"]["match_type"] == "unmatched"
    assert response["exact"]["cts_total"] is None
    assert response["exact"]["status"] == "unknown"


def test_build_query_response_marks_normalized_match() -> None:
    response = build_query_response(
        query="  TERM   ALPHA  ",
        terms=["term alpha"],
        relationships=[],
        observations={
            "term alpha": RecallObservation(
                observation_id="obs-alpha",
                provider="fake-cts",
                query_text="term alpha",
                query_mode="exact",
                total=42,
                status="ok",
                recall_bucket="10_99",
                observed_at="2026-07-03T00:00:00Z",
                probe_run_id="fake-probe-run",
                request_hash="hash-alpha",
                created_at="2026-07-03T00:00:00Z",
            )
        },
    )

    assert response["exact"]["text"] == "term alpha"
    assert response["exact"]["match_type"] == "normalized"
    assert response["exact"]["cts_total"] == 42
    assert response["exact"]["status"] == "ok"


def test_build_query_response_returns_incoming_related_terms() -> None:
    response = build_query_response(
        query="term-beta",
        terms=["term-alpha", "term-beta"],
        relationships=[
            {
                "source_text": "term-alpha",
                "target_text": "term-beta",
                "relationship_type": "RELATED_TO",
                "evidence_text": "负责候选需求甲。负责候选需求乙。",
                "confidence": 0.74,
            }
        ],
        observations={
            "term-alpha": RecallObservation(
                observation_id="obs-alpha",
                provider="fake-cts",
                query_text="term-alpha",
                query_mode="exact",
                total=42,
                status="ok",
                recall_bucket="10_99",
                observed_at="2026-07-03T00:00:00Z",
                probe_run_id="fake-probe-run",
                request_hash="hash-alpha",
                created_at="2026-07-03T00:00:00Z",
            )
        },
    )

    assert response["related_terms"] == [
        {
            "text": "term-alpha",
            "relationship_type": "RELATED_TO",
            "direction": "incoming",
            "cts_total": 42,
            "status": "ok",
            "relationship_status": "candidate",
            "evidence_text": "负责候选需求甲。负责候选需求乙。",
            "confidence": 0.74,
        }
    ]


def test_build_query_response_marks_related_term_without_observation_unknown() -> None:
    response = build_query_response(
        query="term-alpha",
        terms=["term-alpha", "term-beta"],
        relationships=[
            {
                "source_text": "term-alpha",
                "target_text": "term-beta",
                "relationship_type": "RELATED_TO",
                "evidence_text": "负责候选需求甲。负责候选需求乙。",
                "confidence": 0.74,
            }
        ],
        observations={},
    )

    assert response["related_terms"][0]["text"] == "term-beta"
    assert response["related_terms"][0]["cts_total"] is None
    assert response["related_terms"][0]["status"] == "unknown"
