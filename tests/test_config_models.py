from pathlib import Path

import pytest

from jd_query_graph.config import ConfigError, load_graph_config


def test_loads_default_taxonomy_and_relationships() -> None:
    graph_config = load_graph_config(
        taxonomy_path=Path("configs/taxonomy.yaml"),
        relationships_path=Path("configs/relationships.yaml"),
    )

    assert graph_config.taxonomy.schema_version == "jd-query-taxonomy-v1"
    assert "QuerySurface" in graph_config.node_type_names
    assert "RecallObservation" in graph_config.node_type_names
    assert "ALIAS_OF" in graph_config.relationship_type_names
    assert graph_config.serving_node_type_names == {
        "QuerySurface",
        "Skill",
        "Tool",
        "Framework",
        "ProgrammingLanguage",
        "Role",
        "Domain",
    }


def test_rejects_relationship_with_unknown_endpoint(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v1
node_types:
  - name: QuerySurface
    description: Searchable term.
    serving: true
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v1
relationship_types:
  - name: BAD_EDGE
    description: Invalid edge.
    source: QuerySurface
    target: MissingNode
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unknown target node type"):
        load_graph_config(taxonomy_path, relationships_path)

