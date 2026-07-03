from pathlib import Path

from jd_query_graph.config import load_graph_config
from jd_query_graph.schema import build_graphrag_schema


def test_builds_graphrag_schema_from_config() -> None:
    graph_config = load_graph_config(
        Path("configs/taxonomy.yaml"),
        Path("configs/relationships.yaml"),
    )

    schema = build_graphrag_schema(graph_config)

    assert schema["node_types"] == [
        {"label": "JobPosting", "description": "A canonical source JD."},
        {
            "label": "QueryTerm",
            "description": (
                "Candidate resume search query term extracted from JD evidence."
            ),
        },
        {
            "label": "RecallObservation",
            "description": "Provider recall count observation for one query term.",
        },
    ]
    assert ("QueryTerm", "MENTIONED_IN", "JobPosting") in schema["patterns"]
    assert ("QueryTerm", "SAME_AS", "QueryTerm") in schema["patterns"]
    assert ("QueryTerm", "HAS_RECALL", "RecallObservation") in schema["patterns"]
