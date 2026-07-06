"""Neo4j write/read helpers for the local query-term graph loop."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jSettings(BaseSettings):
    """Local Neo4j connection settings."""

    model_config = SettingsConfigDict(env_prefix="JD_QUERY_GRAPH_NEO4J_")

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: SecretStr = Field(default=SecretStr("password"), repr=False, exclude=True)
    database: str = "neo4j"

    @property
    def password_value(self) -> str:
        """Return the raw password for deliberate credential use."""

        return self.password.get_secret_value()


def load_neo4j_settings() -> Neo4jSettings:
    """Load Neo4j settings from environment variables with local compose defaults."""

    return Neo4jSettings()


def schema_statements() -> list[str]:
    """Return idempotent Neo4j schema statements for Phase 2A labels."""

    return [
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
