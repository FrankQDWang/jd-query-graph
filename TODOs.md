# TODOs

## Cloud Service Architecture Spec

- [ ] Add a Cloud Service Architecture spec that separates build-plane graph construction from serving-plane query access.
- [ ] Define build-plane responsibilities: JSONL import, source/run/hash tracking, LLM/GraphRAG extraction, normalization, Neo4j writes, relation validation, CTS probe queue, and snapshot publish.
- [ ] Define serving-plane responsibilities: read-optimized adjacency snapshots, normalized lookup, exact and neighbor recall responses, API versioning, pagination, ranking, caching, and rollback.
- [ ] Specify why Neo4j is the authoring and analysis graph, while high-QPS agent queries should read a materialized serving snapshot.

## Phase 2: Real Build Loop

- [ ] Add Neo4j constraints and indexes for `JobPosting`, `QueryTerm`, `RecallObservation`, and relationship uniqueness.
- [ ] Implement idempotent graph writer for `JobPosting`, `QueryTerm`, `MENTIONED_IN`, term-term relationships, `RecallObservation`, and `HAS_RECALL`.
- [ ] Add a real GraphRAG adapter spike behind the existing extraction boundary.
- [ ] Add a real CTS provider interface with mock HTTP contract tests before live credentials are used.
- [ ] Persist append-only run metadata for import, extraction, graph write, relationship validation, and CTS probe runs.
- [ ] Generate a quality report covering term precision, relation correctness, `SAME_AS`/`VARIANT_OF` error rates, and recall observation coverage.
- [ ] Add an explicit full-corpus dry-run gate for the 9530-row ByteDance corpus.

## Phase 3: Service Query Layer

- [ ] Add a FastAPI or gRPC service skeleton for read-only query serving.
- [ ] Build a serving snapshot exporter from Neo4j or graph artifacts.
- [ ] Define Query Response Schema v1 with exact match, normalized match, neighbors, recall status, evidence, confidence, and metadata.
- [ ] Implement normalized lookup and relationship-type filters.
- [ ] Add ranking, pagination, cache policy, and stale recall handling.
- [ ] Add auth, rate limit, audit logging, secret handling, and low-frequency count suppression.
- [ ] Run a load test for expected agent QPS and latency targets.
