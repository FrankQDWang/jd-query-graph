# AGENTS.md

## Workflow

Use Superpowers direct workflow in this repository:

- Use `superpowers:brainstorming` for product or architecture changes.
- Use `superpowers:writing-plans` before implementation.
- Use `superpowers:test-driven-development` for behavior changes.
- Use `superpowers:verification-before-completion` before completion claims.

Do not use the old SeekTalent gstack/fw wrapper workflow in this repository.

## Product Boundary

This repository is an internal backend tool for building and querying a Neo4j-backed JD query-term graph.

It is not a lightweight user-side package, not a SQLite bundled snapshot package, and not a UI project.

## Hard Rules

- Do not hardcode concrete query terms, concrete synonym pairs, concrete aliases, or fixed technology allowlists.
- Allowed static config is limited to node labels, term category enums, relationship type enums, status enums, evidence type enums, thresholds, prompt versions, and execution settings.
- All extracted query terms and term-term relationships must carry evidence and run metadata.
- LLM or Neo4j GraphRAG output is candidate evidence, not final truth.
- `RecallObservation` data must come from provider probe code, never from LLM output.
- Local corpus files under `data/` are ignored and must not be committed.
