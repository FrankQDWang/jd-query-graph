from jd_query_graph.neo4j_io import (
    Neo4jSettings,
    load_neo4j_settings,
    schema_statements,
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

    assert settings == Neo4jSettings(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
        database="neo4j",
    )
    assert "password" not in repr(settings)


def test_neo4j_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_URI", "bolt://example.invalid:7687")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_USER", "graph_user")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_PASSWORD", "graph_secret")
    monkeypatch.setenv("JD_QUERY_GRAPH_NEO4J_DATABASE", "graph_db")

    settings = load_neo4j_settings()

    assert settings == Neo4jSettings(
        uri="bolt://example.invalid:7687",
        user="graph_user",
        password="graph_secret",
        database="graph_db",
    )
    assert "graph_secret" not in repr(settings)
    assert "password" not in settings.model_dump()
    assert "graph_secret" not in str(settings.model_dump())


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
