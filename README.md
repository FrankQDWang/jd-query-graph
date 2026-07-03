# JD Query Graph

Internal backend tool for turning normalized JD JSONL into a Neo4j query-term
knowledge graph.

First target:

- validate declarative node and relationship taxonomy configs;
- import fixed-format JD JSONL;
- use Neo4j GraphRAG as an extraction adapter;
- write query surfaces and relationships to Neo4j;
- probe CTS count-only recall for serving query surfaces;
- expose a backend lookup API for exact, alias, equivalent, related, and
  co-occurring query terms with recall counts.

The first version is an internal tool. It may depend on Neo4j, builder-only LLM
credentials, and CTS credentials. It is not a lightweight user-side package.

## Local Stack

```bash
uv sync --extra dev
docker compose up -d neo4j
uv run jd-query-graph validate-config
uv run jd-query-graph inspect-jds path/to/jds.jsonl
```

## Fixed JD JSONL Shape

Each line must be a JSON object:

```json
{
  "jd_id": "job-001",
  "title": "Backend Engineer",
  "company": "Example",
  "description": "Responsible for Go, Kubernetes, and graph services.",
  "language": "en",
  "source": "local-corpus",
  "url": "https://example.invalid/jobs/001"
}
```

Only `jd_id`, `title`, `description`, and `source` are required.

