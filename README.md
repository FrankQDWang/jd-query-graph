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

Phase 1 validates configs and data contracts, copies the local ByteDance corpus,
and emits fake extraction artifacts for structure checks only. It does not run
live GraphRAG extraction, write to Neo4j, or call CTS.

## Local Stack

```bash
uv sync --extra dev
docker compose up -d neo4j
uv run jd-query-graph validate-config
uv run jd-query-graph inspect-jds path/to/jds.jsonl
```

## ByteDance JD JSONL Contract

Each line must be a JSON object:

```json
{
  "canonical_source_key": "bytedance:job-001",
  "source_url": "https://jobs.bytedance.com/en/position/001/detail",
  "job_id": "001",
  "title": "Backend Engineer",
  "team": "Engineering",
  "location": "Shanghai",
  "cities": ["Shanghai"],
  "job_type": "Full-time",
  "responsibilities": ["Build graph-backed backend services."],
  "qualifications": ["Experience with Python and graph databases."],
  "raw_snapshot_path": "raw/bytedance/job-001.html",
  "raw_snapshot_sha256": "0123456789abcdef...",
  "collected_at": "2026-07-03T00:00:00Z",
  "parse_confidence": 0.98
}
```

The canonical ByteDance corpus records source identity, posting metadata,
structured text fields, raw snapshot provenance, collection time, and parse
confidence for each job.

Required parser fields are `canonical_source_key`, `source_url`, `cities`,
`responsibilities`, `qualifications`, `raw_snapshot_path`, and
`raw_snapshot_sha256`. The other listed fields are optional or contextual
metadata when present in the source corpus.

## Phase 1 Commands

```bash
uv run --extra dev jd-query-graph validate-config
uv run --extra dev jd-query-graph build-graphrag-schema
uv run --extra dev jd-query-graph copy-corpus
uv run --extra dev jd-query-graph inspect-jds data/corpora/bytedance/factual_jobs_mainland.jsonl
uv run --extra dev jd-query-graph write-fake-extraction-artifact data/corpora/bytedance/factual_jobs_mainland.jsonl --output artifacts/extraction/sample.jsonl --limit 20
```

`data/` and `artifacts/` are local working directories and are ignored by git.

## Phase 2A Neo4j Write/Read Loop

Start local Neo4j and build a small fake extraction artifact:

```bash
docker compose up -d neo4j
uv run --extra dev jd-query-graph copy-corpus
uv run --extra dev jd-query-graph write-fake-extraction-artifact \
  data/corpora/bytedance/factual_jobs_mainland.jsonl \
  --output artifacts/extraction/sample.jsonl \
  --limit 20
```

Write the artifact into Neo4j. Running this command twice should report the
same counts and must not create duplicate graph records:

```bash
uv run --extra dev jd-query-graph write-neo4j-artifact artifacts/extraction/sample.jsonl
uv run --extra dev jd-query-graph write-neo4j-artifact artifacts/extraction/sample.jsonl
```

Query a term from the artifact:

```bash
uv run --extra dev jd-query-graph query-neo4j "title: 示例岗位"
```

The response keeps the Phase 1 query shape: `exact`, `related_terms`, evidence,
relationship status, and fake recall status.
