"""GraphRAG schema export from repository graph config."""

from __future__ import annotations

from typing import Any

from jd_query_graph.config import GraphConfig


def build_graphrag_schema(graph_config: GraphConfig) -> dict[str, Any]:
    """Build a GraphRAG-compatible schema dictionary from repo config."""

    return {
        "node_types": [
            {"label": node_label.name, "description": node_label.description}
            for node_label in graph_config.taxonomy.node_labels
        ],
        "relationship_types": [
            {
                "label": relationship_type.name,
                "description": relationship_type.description,
            }
            for relationship_type in graph_config.relationships.relationship_types
        ],
        "patterns": [
            (
                relationship_type.source,
                relationship_type.name,
                relationship_type.target,
            )
            for relationship_type in graph_config.relationships.relationship_types
        ],
    }
