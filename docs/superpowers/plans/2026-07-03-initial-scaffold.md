# Initial Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the initial internal Python backend repository for a Neo4j-backed JD query-term graph tool.

**Architecture:** Start with tested contracts around declarative graph configs and fixed-format JD JSONL ingestion. Keep Neo4j GraphRAG behind a later extraction adapter so the repo is usable before live Neo4j, LLM, or CTS credentials exist.

**Tech Stack:** Python 3.12, Pydantic, Typer, PyYAML, Neo4j Python driver, Neo4j GraphRAG, pytest, Ruff, Docker Compose Neo4j.

---

## File Structure

- `configs/taxonomy.yaml`: declarative node type taxonomy.
- `configs/relationships.yaml`: declarative relationship type taxonomy.
- `src/jd_query_graph/config.py`: config models and validation.
- `src/jd_query_graph/jd_input.py`: fixed JD JSONL parsing and summary.
- `src/jd_query_graph/cli.py`: CLI entrypoint for config validation and JD inspection.
- `tests/test_config_models.py`: config contract tests.
- `tests/test_jd_records.py`: JD input contract tests.
- `tests/test_cli.py`: CLI smoke tests.

## Tasks

### Task 1: Config Contracts

- [ ] Write tests for loading valid config and rejecting unknown relationship endpoints.
- [ ] Run config tests and confirm they fail because implementation is missing.
- [ ] Implement Pydantic models and loader.
- [ ] Run config tests and confirm they pass.

### Task 2: JD JSONL Contracts

- [ ] Write tests for valid JD parsing and malformed record rejection.
- [ ] Run JD tests and confirm they fail because implementation is missing.
- [ ] Implement JD record parser and summary.
- [ ] Run JD tests and confirm they pass.

### Task 3: CLI Contracts

- [ ] Write tests for `validate-config` and `inspect-jds`.
- [ ] Run CLI tests and confirm they fail because implementation is missing.
- [ ] Implement Typer CLI.
- [ ] Run CLI tests and confirm they pass.

### Task 4: Repository Verification

- [ ] Run `uv run pytest`.
- [ ] Run `uv run ruff check .`.
- [ ] Initialize git repository after verification.

