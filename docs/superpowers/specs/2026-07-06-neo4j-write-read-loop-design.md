# Neo4j Write/Read Loop Design

## Goal

Build the next verifiable backend slice: write the existing fake extraction
artifact into local Neo4j, then query Neo4j back through a CLI response that
matches the current artifact query shape.

This is Phase 2A. It proves the graph write/read path before real GraphRAG
output is introduced.

## Scope

Phase 2A includes:

- Neo4j constraints and indexes for the Phase 1 graph labels.
- An artifact-to-Neo4j writer for `JobPosting`, `QueryTerm`, `MENTIONED_IN`,
  candidate term-term relationships, `RecallObservation`, and `HAS_RECALL`.
- Idempotent writes: running the same 20-row artifact twice must not duplicate
  nodes or relationships.
- A Neo4j-backed query CLI that returns exact term, neighbors, relationship
  type, evidence, status, and fake recall status.
- Tests and CLI smoke checks against a small local sample.

Phase 2A does not include:

- Real GraphRAG or LLM extraction.
- Real CTS calls.
- Full 9530-row graph build.
- Quality scoring of extracted terms.
- Serving API, auth, rate limits, audit logging, or snapshot export.

## Why This Slice

The next risky boundary is not the LLM. It is whether graph records can be
written and read back without losing identity, evidence, or relationship
direction.

Keeping extraction fake for this slice makes failures diagnosable:

- If counts duplicate, the writer or uniqueness model is wrong.
- If evidence is missing, artifact-to-graph mapping is wrong.
- If query output is wrong, the Neo4j read path is wrong.

Only after this loop is stable should real GraphRAG output be connected.

## Inputs

The primary input is the existing fake extraction JSONL artifact produced by:

```bash
uv run --extra dev jd-query-graph write-fake-extraction-artifact \
  data/corpora/bytedance/factual_jobs_mainland.jsonl \
  --output artifacts/extraction/sample.jsonl \
  --limit 20
```

The writer treats this artifact as a structure contract, not as extraction
quality evidence.

## Graph Mapping

`JobPosting` is derived from artifact row provenance:

- `job_posting_id`: stable hash or stable key derived from
  `canonical_source_key`.
- `canonical_source_key`
- `source_url`
- `run_id` or import run metadata for this local build.

`QueryTerm` is derived from term rows:

- `term_id`
- `text`
- `normalized_text`
- `term_category`
- `language`
- `source`
- `status`
- `evidence_count`

`MENTIONED_IN` connects each term to its source `JobPosting` and carries:

- `source_field`
- `source_index`
- `evidence_text`
- `char_start`
- `char_end`
- `extractor`
- `model`
- `confidence`
- `status`

Term-term candidate relationships are written from relationship rows when
present. The fake artifact may contain zero term-term relationships; this is
valid for the writer smoke path. Tests should still cover one synthetic
relationship row so query behavior is verified.

`RecallObservation` and `HAS_RECALL` remain fake for Phase 2A. They exist only
to preserve the response shape used by the current query code.

## Idempotency Rules

The same artifact can be written repeatedly with the same run identifiers.
After the second run:

- `JobPosting` count is unchanged.
- `QueryTerm` count is unchanged.
- `MENTIONED_IN` count is unchanged.
- Candidate relationship count is unchanged.
- `RecallObservation` count is unchanged for the same fake recall request hash.

The writer must use stable keys, not insertion order.

## CLI Shape

Add a write command:

```bash
uv run --extra dev jd-query-graph write-neo4j-artifact artifacts/extraction/sample.jsonl
```

The command returns JSON:

```json
{
  "status": "ok",
  "job_count": 20,
  "term_count": 20,
  "mentioned_in_count": 20,
  "relationship_count": 0,
  "recall_observation_count": 20
}
```

Add a query command:

```bash
uv run --extra dev jd-query-graph query-neo4j "title: 示例岗位"
```

The query response should stay close to the current artifact query response:

- `response_version`
- `snapshot_id` or local graph run id
- `generated_at`
- `query`
- `normalized_query`
- `exact`
- `related_terms`

If no term matches, return `match_type: "unmatched"` and `status: "unknown"`.

## Configuration

Neo4j connection settings should come from environment variables or a small
settings model. Do not hardcode credentials.

Required settings:

- URI
- username
- password
- database name, optional with Neo4j default if omitted

Local defaults may match `docker-compose.yml` only when safe for development.

## Error Handling

The writer should fail clearly when:

- Neo4j is unavailable.
- The artifact path is missing.
- A row is invalid or missing required fields.
- A relationship references a term that was not written.

Failures should include enough row or key context to diagnose the bad input,
without dumping credentials.

## Tests

Use focused tests for:

- Constraint/index statement generation or application boundary.
- Artifact row parsing for term, relationship, and provenance rows.
- Idempotent write behavior against a test Neo4j database or an adapter fake.
- Query response for exact match, normalized match, unmatched query, and a
  relationship neighbor.
- CLI smoke for write then query on a 20-row sample when Neo4j is available.

If integration tests need a live Neo4j service, they should be clearly marked
or skipped when Neo4j is unavailable. Unit tests must still pass without a
running database.

## Acceptance

Phase 2A is complete when:

- Local Neo4j can start from `docker-compose.yml`.
- A 20-row fake extraction artifact writes successfully.
- Running the writer twice produces stable graph counts.
- A CLI query reads from Neo4j and returns exact term, neighbor data when
  present, evidence text, relationship status, and fake recall status.
- `uv run --extra dev pytest -q` passes.
- `uv run --extra dev ruff check .` passes.

## Next Step After Phase 2A

After this write/read loop is stable, Phase 2B should replace the fake artifact
source with a real GraphRAG adapter spike over a small JD sample. That later
slice should measure term and relationship quality; Phase 2A deliberately does
not.
