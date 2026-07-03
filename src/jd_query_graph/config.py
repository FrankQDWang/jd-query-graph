"""Declarative graph taxonomy and relationship config loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ConfigError(ValueError):
    """Raised when graph configuration is invalid."""


class NodeType(BaseModel):
    """Configured graph node type."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    serving: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("name must be alphanumeric or underscore")
        return value


class RelationshipType(BaseModel):
    """Configured graph relationship type."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value.upper() != value or not value.replace("_", "").isalnum():
            raise ValueError(
                "relationship name must be uppercase alphanumeric or underscore"
            )
        return value


class TaxonomyConfig(BaseModel):
    """Node taxonomy config file."""

    schema_version: str
    node_types: list[NodeType]


class RelationshipsConfig(BaseModel):
    """Relationship taxonomy config file."""

    schema_version: str
    relationship_types: list[RelationshipType]


class GraphConfig(BaseModel):
    """Validated combined graph config."""

    taxonomy: TaxonomyConfig
    relationships: RelationshipsConfig

    @property
    def node_type_names(self) -> set[str]:
        return {node_type.name for node_type in self.taxonomy.node_types}

    @property
    def serving_node_type_names(self) -> set[str]:
        return {
            node_type.name
            for node_type in self.taxonomy.node_types
            if node_type.serving
        }

    @property
    def relationship_type_names(self) -> set[str]:
        return {
            relationship_type.name
            for relationship_type in self.relationships.relationship_types
        }


def load_graph_config(
    taxonomy_path: Path | str = Path("configs/taxonomy.yaml"),
    relationships_path: Path | str = Path("configs/relationships.yaml"),
) -> GraphConfig:
    """Load and validate node and relationship config files."""

    taxonomy = _load_model(Path(taxonomy_path), TaxonomyConfig)
    relationships = _load_model(Path(relationships_path), RelationshipsConfig)
    _validate_unique_node_types(taxonomy)
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


def _validate_unique_node_types(taxonomy: TaxonomyConfig) -> None:
    _validate_unique_names(
        [node_type.name for node_type in taxonomy.node_types],
        "node type",
    )


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
    node_types = graph_config.node_type_names
    for relationship_type in graph_config.relationships.relationship_types:
        if relationship_type.source not in node_types:
            raise ConfigError(
                f"relationship {relationship_type.name} has unknown source node type "
                f"{relationship_type.source}"
            )
        if relationship_type.target not in node_types:
            raise ConfigError(
                f"relationship {relationship_type.name} has unknown target node type "
                f"{relationship_type.target}"
            )


def graph_config_summary(graph_config: GraphConfig) -> dict[str, Any]:
    """Return a stable JSON-serializable config summary."""

    return {
        "node_type_count": len(graph_config.taxonomy.node_types),
        "relationship_type_count": len(graph_config.relationships.relationship_types),
        "node_types": sorted(graph_config.node_type_names),
        "serving_node_types": sorted(graph_config.serving_node_type_names),
        "relationship_types": sorted(graph_config.relationship_type_names),
    }
