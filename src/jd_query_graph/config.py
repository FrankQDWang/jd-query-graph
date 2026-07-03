"""Declarative graph taxonomy and relationship config loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ConfigError(ValueError):
    """Raised when graph configuration is invalid."""


TAXONOMY_SCHEMA_VERSION = "jd-query-taxonomy-v2"
RELATIONSHIPS_SCHEMA_VERSION = "jd-query-relationships-v2"

FORBIDDEN_NODE_LABELS = {
    "Skill",
    "Tool",
    "Framework",
    "ProgrammingLanguage",
    "Role",
    "Domain",
}


class NodeLabel(BaseModel):
    """Configured graph node label."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("name must be alphanumeric or underscore")
        return value


class TermCategory(BaseModel):
    """Configured query term category."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value.upper() != value or not value.replace("_", "").isalnum():
            raise ValueError(
                "term category name must be uppercase alphanumeric or underscore"
            )
        return value


class RelationshipType(BaseModel):
    """Configured graph relationship type."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    required_properties: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value.upper() != value or not value.replace("_", "").isalnum():
            raise ValueError(
                "relationship name must be uppercase alphanumeric or underscore"
            )
        return value

    @field_validator("required_properties")
    @classmethod
    def validate_required_properties(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if not value:
                raise ValueError("empty required property")
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate required property: {duplicate_list}")
        return values


class TaxonomyConfig(BaseModel):
    """Node taxonomy config file."""

    schema_version: str
    node_labels: list[NodeLabel]
    term_categories: list[TermCategory]

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != TAXONOMY_SCHEMA_VERSION:
            raise ValueError(f"unsupported taxonomy schema version: {value}")
        return value


class RelationshipsConfig(BaseModel):
    """Relationship taxonomy config file."""

    schema_version: str
    relationship_types: list[RelationshipType]

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != RELATIONSHIPS_SCHEMA_VERSION:
            raise ValueError(f"unsupported relationships schema version: {value}")
        return value


class GraphConfig(BaseModel):
    """Validated combined graph config."""

    taxonomy: TaxonomyConfig
    relationships: RelationshipsConfig

    @property
    def node_label_names(self) -> set[str]:
        return {node_label.name for node_label in self.taxonomy.node_labels}

    @property
    def term_category_names(self) -> set[str]:
        return {category.name for category in self.taxonomy.term_categories}

    @property
    def relationship_type_names(self) -> set[str]:
        return {
            relationship_type.name
            for relationship_type in self.relationships.relationship_types
        }

    @property
    def relationship_types(self) -> list[RelationshipType]:
        return self.relationships.relationship_types


def load_graph_config(
    taxonomy_path: Path | str = Path("configs/taxonomy.yaml"),
    relationships_path: Path | str = Path("configs/relationships.yaml"),
) -> GraphConfig:
    """Load and validate node and relationship config files."""

    taxonomy = _load_model(Path(taxonomy_path), TaxonomyConfig)
    relationships = _load_model(Path(relationships_path), RelationshipsConfig)
    _validate_unique_node_labels(taxonomy)
    _validate_unique_term_categories(taxonomy)
    _validate_allowed_node_labels(taxonomy)
    _validate_unique_relationship_types(relationships)
    graph_config = GraphConfig(taxonomy=taxonomy, relationships=relationships)
    _validate_relationship_endpoints(graph_config)
    return graph_config


def _load_model(
    path: Path,
    model_type: type[TaxonomyConfig] | type[RelationshipsConfig],
):
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"config {path} must be a mapping")
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise ConfigError(f"invalid config {path}: {exc}") from exc


def _validate_unique_node_labels(taxonomy: TaxonomyConfig) -> None:
    _validate_unique_names(
        [node_label.name for node_label in taxonomy.node_labels],
        "node label",
    )


def _validate_unique_term_categories(taxonomy: TaxonomyConfig) -> None:
    _validate_unique_names(
        [category.name for category in taxonomy.term_categories],
        "term category",
    )


def _validate_allowed_node_labels(taxonomy: TaxonomyConfig) -> None:
    forbidden = sorted(
        node_label.name
        for node_label in taxonomy.node_labels
        if node_label.name in FORBIDDEN_NODE_LABELS
    )
    if forbidden:
        raise ConfigError(f"forbidden node label: {', '.join(forbidden)}")


def _validate_unique_relationship_types(relationships: RelationshipsConfig) -> None:
    _validate_unique_names(
        [
            relationship_type.name
            for relationship_type in relationships.relationship_types
        ],
        "relationship type",
    )


def _validate_unique_names(names: list[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ConfigError(f"duplicate {label}: {duplicate_list}")


def _validate_relationship_endpoints(graph_config: GraphConfig) -> None:
    node_labels = graph_config.node_label_names
    for relationship_type in graph_config.relationships.relationship_types:
        if relationship_type.source not in node_labels:
            raise ConfigError(
                f"relationship {relationship_type.name} has unknown source node label "
                f"{relationship_type.source}"
            )
        if relationship_type.target not in node_labels:
            raise ConfigError(
                f"relationship {relationship_type.name} has unknown target node label "
                f"{relationship_type.target}"
            )


def graph_config_summary(graph_config: GraphConfig) -> dict[str, Any]:
    """Return a stable JSON-serializable config summary."""

    return {
        "node_label_count": len(graph_config.taxonomy.node_labels),
        "term_category_count": len(graph_config.taxonomy.term_categories),
        "relationship_type_count": len(graph_config.relationships.relationship_types),
        "node_labels": sorted(graph_config.node_label_names),
        "term_categories": sorted(graph_config.term_category_names),
        "relationship_types": sorted(graph_config.relationship_type_names),
    }
