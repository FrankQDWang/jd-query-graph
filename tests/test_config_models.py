from pathlib import Path

import pytest

from jd_query_graph.config import ConfigError, load_graph_config


def test_loads_approved_graph_schema() -> None:
    graph_config = load_graph_config(
        taxonomy_path=Path("configs/taxonomy.yaml"),
        relationships_path=Path("configs/relationships.yaml"),
    )

    assert graph_config.node_label_names == {
        "JobPosting",
        "QueryTerm",
        "RecallObservation",
    }
    assert graph_config.term_category_names == {
        "CAPABILITY",
        "TECH_OBJECT",
        "DOMAIN_CONTEXT",
        "ROLE_CONTEXT",
        "QUALIFIER",
        "UNKNOWN",
    }
    assert graph_config.relationship_type_names == {
        "MENTIONED_IN",
        "SAME_AS",
        "VARIANT_OF",
        "RELATED_TO",
        "CO_OCCURS_WITH",
        "HAS_RECALL",
    }
    relationship_properties = {
        relationship.name: set(relationship.required_properties)
        for relationship in graph_config.relationship_types
    }
    assert {
        "source_index",
        "char_start",
        "char_end",
        "model",
    } <= relationship_properties["MENTIONED_IN"]
    assert {"source_jd_ids", "model"} <= relationship_properties["SAME_AS"]
    assert {"sample_evidence"} <= relationship_properties["CO_OCCURS_WITH"]


def test_rejects_relationship_with_unknown_endpoint(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: QueryTerm
    description: Search term.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v2
relationship_types:
  - name: BAD_EDGE
    description: Invalid edge.
    source: QueryTerm
    target: MissingNode
    required_properties: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unknown target node label"):
        load_graph_config(taxonomy_path, relationships_path)


def test_rejects_fine_grained_node_labels(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: Skill
    description: Too specific.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v2
relationship_types: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="forbidden node label"):
        load_graph_config(taxonomy_path, relationships_path)


def test_rejects_wrong_taxonomy_schema_version(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v1
node_labels:
  - name: QueryTerm
    description: Search term.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v2
relationship_types: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unsupported taxonomy schema version"):
        load_graph_config(taxonomy_path, relationships_path)


def test_rejects_wrong_relationships_schema_version(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: QueryTerm
    description: Search term.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v1
relationship_types: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unsupported relationships schema version"):
        load_graph_config(taxonomy_path, relationships_path)


def test_rejects_empty_required_relationship_property(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: QueryTerm
    description: Search term.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v2
relationship_types:
  - name: BAD_EDGE
    description: Invalid edge.
    source: QueryTerm
    target: QueryTerm
    required_properties:
      - ""
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="empty required property"):
        load_graph_config(taxonomy_path, relationships_path)


def test_rejects_duplicate_required_relationship_property(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: QueryTerm
    description: Search term.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v2
relationship_types:
  - name: BAD_EDGE
    description: Invalid edge.
    source: QueryTerm
    target: QueryTerm
    required_properties:
      - evidence_text
      - evidence_text
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="duplicate required property"):
        load_graph_config(taxonomy_path, relationships_path)
