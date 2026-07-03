# Neo4j GraphRAG Query Term Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first verifiable backend slice for importing real ByteDance JD JSONL, aligning schema configs to the approved graph design, extracting candidate query terms through a GraphRAG adapter boundary, writing graph records, and querying terms with fake recall observations.

**Architecture:** Keep Neo4j GraphRAG behind a narrow adapter so the repo can test schema, parsing, graph records, and query behavior without live LLM or Neo4j side effects. Phase 1 uses canonical JD input contracts, typed config models, local artifact output, and a fake provider for recall structure; live Neo4j/LLM/CTS execution becomes a later gated slice after this contract is green.

**Tech Stack:** Python 3.12, Pydantic, Typer, PyYAML, pytest, Ruff, Neo4j Python driver, Neo4j GraphRAG dependency boundary, local ignored corpus under `data/`.

---

## Scope Check

This merged plan keeps the completed initial scaffold context and the current Phase 1 execution steps in one document. Phase 1 implements the first testable slice of the approved spec, not the full production system. It deliberately excludes real CTS calls, full 9530-JD extraction, community detection, and production release readiness. Those need separate plans after this slice proves the schema and extraction contracts.

## Phase 0: Initial Scaffold Context

The initial scaffold established the Python backend repository shape before the approved Neo4j GraphRAG query-term graph spec was written.

**Original goal:** Create the initial internal Python backend repository for a Neo4j-backed JD query-term graph tool.

**Original architecture:** Start with tested contracts around declarative graph configs and fixed-format JD JSONL ingestion. Keep Neo4j GraphRAG behind a later extraction adapter so the repo is usable before live Neo4j, LLM, or CTS credentials exist.

**Initial scaffold files:**

- `configs/taxonomy.yaml`: declarative node type taxonomy.
- `configs/relationships.yaml`: declarative relationship type taxonomy.
- `src/jd_query_graph/config.py`: config models and validation.
- `src/jd_query_graph/jd_input.py`: fixed JD JSONL parsing and summary.
- `src/jd_query_graph/cli.py`: CLI entrypoint for config validation and JD inspection.
- `tests/test_config_models.py`: config contract tests.
- `tests/test_jd_records.py`: JD input contract tests.
- `tests/test_cli.py`: CLI smoke tests.

**Initial scaffold tasks:**

- Config contracts: test valid config loading and unknown relationship endpoint rejection; implement Pydantic models and loader.
- JD JSONL contracts: test valid JD parsing and malformed record rejection; implement JD record parser and summary.
- CLI contracts: test `validate-config` and `inspect-jds`; implement Typer CLI.
- Repository verification: run `uv run pytest` and `uv run ruff check .`.

Phase 1 below supersedes the scaffold schema where the spec says the scaffold was temporary, especially the fine-grained `Skill`, `Tool`, `Framework`, and `ProgrammingLanguage` node types.

## File Structure

- Create `AGENTS.md`: repo-local workflow contract for Superpowers direct workflow and no hardcoded term pairs.
- Modify `README.md`: replace the temporary JD schema with the canonical ByteDance JD contract and Phase 1 commands.
- Modify `configs/taxonomy.yaml`: replace fine-grained scaffold node types with `JobPosting`, `QueryTerm`, `RecallObservation`, and `term_categories`.
- Modify `configs/relationships.yaml`: replace scaffold relationships with the approved relationship schema and required relationship properties.
- Create `src/jd_query_graph/corpus.py`: corpus copy/locate helpers for the local ignored ByteDance JSONL.
- Modify `src/jd_query_graph/jd_input.py`: parse canonical JD rows and generate extraction text.
- Modify `src/jd_query_graph/config.py`: support node labels, term category enum, and relationship definitions.
- Create `src/jd_query_graph/schema.py`: convert repo config into a GraphRAG-compatible schema dictionary.
- Create `src/jd_query_graph/extraction.py`: adapter interface plus deterministic fake adapter for tests.
- Create `src/jd_query_graph/artifacts.py`: JSONL artifact writer for extracted terms and relationships.
- Create `src/jd_query_graph/recall.py`: fake recall provider and recall observation model.
- Create `src/jd_query_graph/query.py`: in-memory query result assembler for exact term and related terms.
- Modify `src/jd_query_graph/cli.py`: add `copy-corpus`, `build-graphrag-schema`, `extract-sample`, and `query-artifact`.
- Add tests under `tests/` for every new contract.

## Task 1: Repository Workflow Contract

**Files:**
- Create: `AGENTS.md`
- Test: manual review plus `rg` checks in this task

- [ ] **Step 1: Create repo workflow contract**

Create `AGENTS.md` with this content:

```markdown
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
```

- [ ] **Step 2: Verify hard-rule text is present**

Run:

```bash
rg -n "Do not hardcode concrete query terms|RecallObservation|Local corpus" AGENTS.md
```

Expected: three matching lines.

- [ ] **Step 3: Commit**

Run:

```bash
git add AGENTS.md
git commit -m "docs: add repo workflow contract"
```

## Task 2: Canonical Corpus Location And Copy Command

**Files:**
- Create: `src/jd_query_graph/corpus.py`
- Modify: `src/jd_query_graph/cli.py`
- Test: `tests/test_corpus.py`, `tests/test_cli.py`

- [ ] **Step 1: Write failing corpus tests**

Create `tests/test_corpus.py`:

```python
from pathlib import Path

from jd_query_graph.corpus import (
    BYTE_DANCE_MAINLAND_SOURCE,
    DEFAULT_LOCAL_CORPUS,
    CorpusCopyResult,
    copy_corpus,
)


def test_copy_corpus_copies_source_to_default_location(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    target = tmp_path / "data" / "corpora" / "bytedance" / "factual_jobs_mainland.jsonl"
    source.write_text('{"canonical_source_key":"job-1"}\n', encoding="utf-8")

    result = copy_corpus(source_path=source, target_path=target)

    assert result == CorpusCopyResult(
        source_path=source,
        target_path=target,
        line_count=1,
        byte_size=source.stat().st_size,
    )
    assert target.read_text(encoding="utf-8") == '{"canonical_source_key":"job-1"}\n'


def test_default_paths_are_stable() -> None:
    assert BYTE_DANCE_MAINLAND_SOURCE == Path(
        "/Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/"
        "source=jobs_bytedance/factual_jobs_mainland.jsonl"
    )
    assert DEFAULT_LOCAL_CORPUS == Path(
        "data/corpora/bytedance/factual_jobs_mainland.jsonl"
    )
```

Extend `tests/test_cli.py` with:

```python
def test_copy_corpus_command_outputs_summary(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    target = tmp_path / "copied.jsonl"
    source.write_text('{"canonical_source_key":"job-1"}\n', encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["copy-corpus", "--source", str(source), "--target", str(target)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "byte_size": source.stat().st_size,
        "line_count": 1,
        "source_path": str(source),
        "status": "ok",
        "target_path": str(target),
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_corpus.py tests/test_cli.py -q
```

Expected: fail because `jd_query_graph.corpus` and `copy-corpus` do not exist.

- [ ] **Step 3: Implement corpus helper**

Create `src/jd_query_graph/corpus.py`:

```python
"""Local corpus copy and path helpers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


BYTE_DANCE_MAINLAND_SOURCE = Path(
    "/Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/"
    "source=jobs_bytedance/factual_jobs_mainland.jsonl"
)
DEFAULT_LOCAL_CORPUS = Path("data/corpora/bytedance/factual_jobs_mainland.jsonl")


@dataclass(frozen=True)
class CorpusCopyResult:
    source_path: Path
    target_path: Path
    line_count: int
    byte_size: int


def copy_corpus(
    source_path: Path = BYTE_DANCE_MAINLAND_SOURCE,
    target_path: Path = DEFAULT_LOCAL_CORPUS,
) -> CorpusCopyResult:
    """Copy a local corpus JSONL into this repo's ignored data directory."""

    if not source_path.exists():
        raise FileNotFoundError(f"corpus source does not exist: {source_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)
    return CorpusCopyResult(
        source_path=source_path,
        target_path=target_path,
        line_count=_count_lines(target_path),
        byte_size=target_path.stat().st_size,
    )


def _count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)
```

- [ ] **Step 4: Add CLI command**

Modify `src/jd_query_graph/cli.py` imports:

```python
from jd_query_graph.corpus import (
    BYTE_DANCE_MAINLAND_SOURCE,
    DEFAULT_LOCAL_CORPUS,
    copy_corpus,
)
```

Add command before `inspect_jds`:

```python
@app.command()
def copy_corpus_command(
    source: Annotated[
        Path,
        typer.Option("--source", help="Source JD JSONL corpus path."),
    ] = BYTE_DANCE_MAINLAND_SOURCE,
    target: Annotated[
        Path,
        typer.Option("--target", help="Target ignored local corpus path."),
    ] = DEFAULT_LOCAL_CORPUS,
) -> None:
    """Copy the known local ByteDance corpus into this repo's ignored data dir."""

    result = copy_corpus(source_path=source, target_path=target)
    _echo_json(
        {
            "status": "ok",
            "source_path": str(result.source_path),
            "target_path": str(result.target_path),
            "line_count": result.line_count,
            "byte_size": result.byte_size,
        }
    )
```

Set the Typer command name explicitly if Typer converts underscores unexpectedly:

```python
@app.command("copy-corpus")
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_corpus.py tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/jd_query_graph/corpus.py src/jd_query_graph/cli.py tests/test_corpus.py tests/test_cli.py
git commit -m "feat: add local corpus copy command"
```

## Task 3: Canonical JD Contract Parser

**Files:**
- Modify: `src/jd_query_graph/jd_input.py`
- Modify: `src/jd_query_graph/cli.py`
- Test: `tests/test_jd_records.py`, `tests/test_cli.py`

- [ ] **Step 1: Replace JD parser tests with canonical contract cases**

Update `tests/test_jd_records.py` to cover canonical rows:

```python
import json
from pathlib import Path

import pytest

from jd_query_graph.jd_input import (
    CanonicalJdRecord,
    JdRecordError,
    build_extraction_text,
    iter_jd_records,
    summarize_jds,
)


def canonical_row() -> dict[str, object]:
    return {
        "canonical_source_key": "detail_id:1",
        "source_url": "https://example.invalid/job/1",
        "job_id": "A1",
        "title": "示例岗位甲",
        "team": "示例团队",
        "location": "示例城市",
        "cities": ["示例城市"],
        "job_type": "示例类型",
        "responsibilities": ["负责候选需求甲。", "负责候选需求乙。"],
        "qualifications": ["具备示例能力。"],
        "raw_snapshot_path": "raw_pages/details/1.md",
        "raw_snapshot_sha256": "abc123",
        "collected_at": "2026-05-12T07:25:04.030Z",
        "parse_confidence": 0.8,
    }


def test_reads_canonical_jd_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "jds.jsonl"
    input_path.write_text(
        json.dumps(canonical_row(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    records = list(iter_jd_records(input_path))
    summary = summarize_jds(records)

    assert records == [CanonicalJdRecord.model_validate(canonical_row())]
    assert summary.total_records == 1
    assert summary.city_counts == {"示例城市": 1}
    assert summary.team_counts == {"示例团队": 1}


def test_builds_extraction_text_from_approved_fields() -> None:
    record = CanonicalJdRecord.model_validate(canonical_row())

    text = build_extraction_text(record)

    assert "title: 示例岗位甲" in text
    assert "team: 示例团队" in text
    assert "responsibilities[0]: 负责候选需求甲。" in text
    assert "qualifications[0]: 具备示例能力。" in text
    assert "location:" not in text


def test_rejects_missing_required_canonical_field(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.jsonl"
    row = canonical_row()
    del row["responsibilities"]
    input_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(JdRecordError, match="line 1"):
        list(iter_jd_records(input_path))
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_jd_records.py -q
```

Expected: fail because `CanonicalJdRecord`, `build_extraction_text`, `city_counts`, and `team_counts` do not exist.

- [ ] **Step 3: Implement canonical parser**

Replace `src/jd_query_graph/jd_input.py` with a canonical JD model while preserving `iter_jd_records` and `summarize_jds` names:

```python
"""Canonical JD JSONL parsing and extraction text construction."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class JdRecordError(ValueError):
    """Raised when a JD JSONL record cannot be parsed."""


class CanonicalJdRecord(BaseModel):
    """Canonical JD input record from the ByteDance corpus."""

    model_config = ConfigDict(extra="allow", frozen=True)

    canonical_source_key: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    cities: list[str]
    responsibilities: list[str]
    qualifications: list[str]
    raw_snapshot_path: str = Field(min_length=1)
    raw_snapshot_sha256: str = Field(min_length=1)
    job_id: str | None = None
    external_job_id: str | None = None
    title: str | None = None
    team: str | None = None
    location: str | None = None
    job_type: str | None = None
    collected_at: str | None = None
    parse_confidence: float | None = None

    @field_validator("cities", "responsibilities", "qualifications")
    @classmethod
    def validate_string_list(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) for item in value):
            raise ValueError("array fields must contain only strings")
        return value

    @field_validator("parse_confidence")
    @classmethod
    def validate_parse_confidence(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("parse_confidence must be finite")
        return value


class JdSummary(BaseModel):
    """Aggregate information about a canonical JD input file."""

    total_records: int
    city_counts: dict[str, int]
    team_counts: dict[str, int]


def iter_jd_records(path: Path | str) -> Iterator[CanonicalJdRecord]:
    """Yield validated canonical JD records from a JSONL file."""

    input_path = Path(path)
    try:
        handle = input_path.open(encoding="utf-8")
    except OSError as exc:
        raise JdRecordError(f"cannot read JD JSONL {input_path}: {exc}") from exc

    with handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped, parse_constant=_reject_json_constant)
            except json.JSONDecodeError as exc:
                raise JdRecordError(
                    f"line {line_number}: invalid JSON: {exc.msg}"
                ) from exc
            except ValueError as exc:
                raise JdRecordError(f"line {line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise JdRecordError(f"line {line_number}: record must be an object")
            try:
                yield CanonicalJdRecord.model_validate(payload)
            except ValidationError as exc:
                raise JdRecordError(
                    f"line {line_number}: invalid canonical JD record: {exc}"
                ) from exc


def summarize_jds(records: Iterable[CanonicalJdRecord]) -> JdSummary:
    """Summarize a sequence of canonical JD records."""

    total_records = 0
    city_counts: Counter[str] = Counter()
    team_counts: Counter[str] = Counter()

    for record in records:
        total_records += 1
        for city in record.cities:
            city_counts[city] += 1
        if record.team:
            team_counts[record.team] += 1

    return JdSummary(
        total_records=total_records,
        city_counts=dict(sorted(city_counts.items())),
        team_counts=dict(sorted(team_counts.items())),
    )


def build_extraction_text(record: CanonicalJdRecord) -> str:
    """Build the approved extraction text from canonical JD fields."""

    lines: list[str] = []
    if record.title:
        lines.append(f"title: {record.title}")
    if record.team:
        lines.append(f"team: {record.team}")
    for index, value in enumerate(record.responsibilities):
        lines.append(f"responsibilities[{index}]: {value}")
    for index, value in enumerate(record.qualifications):
        lines.append(f"qualifications[{index}]: {value}")
    return "\n".join(lines)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
```

- [ ] **Step 4: Update CLI test expectations**

Update `test_inspect_jds_command_outputs_summary` in `tests/test_cli.py` to use canonical rows and expect `city_counts` / `team_counts`:

```python
def test_inspect_jds_command_outputs_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "jds.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "canonical_source_key": "detail_id:1",
                "source_url": "https://example.invalid/job/1",
                "title": "示例岗位甲",
                "team": "示例团队",
                "location": "示例城市",
                "cities": ["示例城市"],
                "responsibilities": ["负责候选需求甲。"],
                "qualifications": [],
                "raw_snapshot_path": "raw_pages/details/1.md",
                "raw_snapshot_sha256": "abc123",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["inspect-jds", str(input_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "city_counts": {"示例城市": 1},
        "status": "ok",
        "team_counts": {"示例团队": 1},
        "total_records": 1,
    }
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_jd_records.py tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/jd_query_graph/jd_input.py tests/test_jd_records.py tests/test_cli.py
git commit -m "feat: parse canonical jd records"
```

## Task 4: Approved Graph Schema Config

**Files:**
- Modify: `configs/taxonomy.yaml`
- Modify: `configs/relationships.yaml`
- Modify: `src/jd_query_graph/config.py`
- Test: `tests/test_config_models.py`

- [ ] **Step 1: Write failing config tests**

Replace `tests/test_config_models.py` with:

```python
from pathlib import Path

import pytest

from jd_query_graph.config import ConfigError, load_graph_config


def test_loads_approved_graph_schema() -> None:
    graph_config = load_graph_config(
        taxonomy_path=Path("configs/taxonomy.yaml"),
        relationships_path=Path("configs/relationships.yaml"),
    )

    assert graph_config.node_label_names == {
        "JobPosting",
        "QueryTerm",
        "RecallObservation",
    }
    assert graph_config.term_category_names == {
        "CAPABILITY",
        "TECH_OBJECT",
        "DOMAIN_CONTEXT",
        "ROLE_CONTEXT",
        "QUALIFIER",
        "UNKNOWN",
    }
    assert graph_config.relationship_type_names == {
        "MENTIONED_IN",
        "SAME_AS",
        "VARIANT_OF",
        "RELATED_TO",
        "CO_OCCURS_WITH",
        "HAS_RECALL",
    }


def test_rejects_relationship_with_unknown_endpoint(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: QueryTerm
    description: Search term.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v2
relationship_types:
  - name: BAD_EDGE
    description: Invalid edge.
    source: QueryTerm
    target: MissingNode
    required_properties: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unknown target node label"):
        load_graph_config(taxonomy_path, relationships_path)


def test_rejects_fine_grained_node_labels(tmp_path: Path) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    relationships_path = tmp_path / "relationships.yaml"
    taxonomy_path.write_text(
        """
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: Skill
    description: Too specific.
term_categories:
  - name: UNKNOWN
    description: Unknown.
""".strip(),
        encoding="utf-8",
    )
    relationships_path.write_text(
        """
schema_version: jd-query-relationships-v2
relationship_types: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="forbidden node label"):
        load_graph_config(taxonomy_path, relationships_path)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_config_models.py -q
```

Expected: fail because config files and model properties still use scaffold schema.

- [ ] **Step 3: Replace taxonomy config**

Replace `configs/taxonomy.yaml`:

```yaml
schema_version: jd-query-taxonomy-v2
node_labels:
  - name: JobPosting
    description: A canonical source JD.
  - name: QueryTerm
    description: Candidate resume search query term extracted from JD evidence.
  - name: RecallObservation
    description: Provider recall count observation for one query term.
term_categories:
  - name: CAPABILITY
    description: Capability, requirement, responsibility, experience, or transferable ability.
  - name: TECH_OBJECT
    description: Technical object, tool, platform, system, product, or engineering object.
  - name: DOMAIN_CONTEXT
    description: Business domain, business scenario, or industry context.
  - name: ROLE_CONTEXT
    description: Job family, function, or role context.
  - name: QUALIFIER
    description: Search modifier or narrowing condition.
  - name: UNKNOWN
    description: Term category is unclear and requires post-processing or review.
```

- [ ] **Step 4: Replace relationship config**

Replace `configs/relationships.yaml`:

```yaml
schema_version: jd-query-relationships-v2
relationship_types:
  - name: MENTIONED_IN
    description: Query term is extracted from a source JD field.
    source: QueryTerm
    target: JobPosting
    required_properties:
      - source_field
      - evidence_text
      - extractor
      - confidence
      - status
  - name: SAME_AS
    description: Query terms are effectively interchangeable for resume search.
    source: QueryTerm
    target: QueryTerm
    required_properties:
      - evidence_type
      - evidence_text
      - candidate_source
      - confidence
      - extractor
      - status
  - name: VARIANT_OF
    description: Query term is a spelling, language, abbreviation, symbol, or version variant of another term.
    source: QueryTerm
    target: QueryTerm
    required_properties:
      - evidence_type
      - evidence_text
      - candidate_source
      - confidence
      - extractor
      - status
  - name: RELATED_TO
    description: Query terms are related for recruiting search but are not interchangeable.
    source: QueryTerm
    target: QueryTerm
    required_properties:
      - evidence_type
      - evidence_text
      - candidate_source
      - confidence
      - extractor
      - status
  - name: CO_OCCURS_WITH
    description: Query terms co-occur in a JD, field, sentence, paragraph, or fixed window.
    source: QueryTerm
    target: QueryTerm
    required_properties:
      - cooccurrence_count
      - window_type
      - support
      - score
      - status
  - name: HAS_RECALL
    description: Query term has a provider recall count observation.
    source: QueryTerm
    target: RecallObservation
    required_properties:
      - provider
      - query_mode
      - probe_run_id
      - created_at
```

- [ ] **Step 5: Update config models**

Modify `src/jd_query_graph/config.py` to use `NodeLabel`, `TermCategory`, and `RelationshipType.required_properties`. Preserve `ConfigError`, `GraphConfig`, `load_graph_config`, and `graph_config_summary`.

Key model signatures must be:

```python
class NodeLabel(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class TermCategory(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class RelationshipType(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    required_properties: list[str] = Field(default_factory=list)
```

Add forbidden labels:

```python
FORBIDDEN_NODE_LABELS = {
    "Skill",
    "Tool",
    "Framework",
    "ProgrammingLanguage",
    "Role",
    "Domain",
}
```

Required `GraphConfig` properties:

```python
@property
def node_label_names(self) -> set[str]:
    return {node_label.name for node_label in self.taxonomy.node_labels}

@property
def term_category_names(self) -> set[str]:
    return {category.name for category in self.taxonomy.term_categories}

@property
def relationship_type_names(self) -> set[str]:
    return {rel.name for rel in self.relationships.relationship_types}
```

For backward compatibility with existing CLI tests, either update tests or make `graph_config_summary()` return:

```python
{
    "node_label_count": len(graph_config.taxonomy.node_labels),
    "term_category_count": len(graph_config.taxonomy.term_categories),
    "relationship_type_count": len(graph_config.relationships.relationship_types),
    "node_labels": sorted(graph_config.node_label_names),
    "term_categories": sorted(graph_config.term_category_names),
    "relationship_types": sorted(graph_config.relationship_type_names),
}
```

- [ ] **Step 6: Update CLI config test**

In `tests/test_cli.py`, change `test_validate_config_command_outputs_summary` expectations:

```python
def test_validate_config_command_outputs_summary() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-config"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["node_label_count"] == 3
    assert "QueryTerm" in payload["node_labels"]
    assert "CAPABILITY" in payload["term_categories"]
    assert "SAME_AS" in payload["relationship_types"]
```

- [ ] **Step 7: Run tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_config_models.py tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add configs/taxonomy.yaml configs/relationships.yaml src/jd_query_graph/config.py tests/test_config_models.py tests/test_cli.py
git commit -m "feat: define approved graph schema config"
```

## Task 5: GraphRAG Schema Export

**Files:**
- Create: `src/jd_query_graph/schema.py`
- Modify: `src/jd_query_graph/cli.py`
- Test: `tests/test_schema_export.py`, `tests/test_cli.py`

- [ ] **Step 1: Write failing schema export tests**

Create `tests/test_schema_export.py`:

```python
from pathlib import Path

from jd_query_graph.config import load_graph_config
from jd_query_graph.schema import build_graphrag_schema


def test_builds_graphrag_schema_from_config() -> None:
    graph_config = load_graph_config(
        Path("configs/taxonomy.yaml"),
        Path("configs/relationships.yaml"),
    )

    schema = build_graphrag_schema(graph_config)

    assert schema["node_types"] == [
        {"label": "JobPosting", "description": "A canonical source JD."},
        {
            "label": "QueryTerm",
            "description": "Candidate resume search query term extracted from JD evidence.",
        },
        {
            "label": "RecallObservation",
            "description": "Provider recall count observation for one query term.",
        },
    ]
    assert ("QueryTerm", "MENTIONED_IN", "JobPosting") in schema["patterns"]
    assert ("QueryTerm", "SAME_AS", "QueryTerm") in schema["patterns"]
    assert ("QueryTerm", "HAS_RECALL", "RecallObservation") in schema["patterns"]
```

Extend `tests/test_cli.py`:

```python
def test_build_graphrag_schema_command_outputs_schema() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["build-graphrag-schema"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert ["QueryTerm", "SAME_AS", "QueryTerm"] in payload["schema"]["patterns"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_schema_export.py tests/test_cli.py -q
```

Expected: fail because `jd_query_graph.schema` and CLI command do not exist.

- [ ] **Step 3: Implement schema export**

Create `src/jd_query_graph/schema.py`:

```python
"""GraphRAG schema export from repository graph config."""

from __future__ import annotations

from typing import Any

from jd_query_graph.config import GraphConfig


def build_graphrag_schema(graph_config: GraphConfig) -> dict[str, Any]:
    """Build a GraphRAG-compatible schema dictionary from repo config."""

    return {
        "node_types": [
            {"label": node_label.name, "description": node_label.description}
            for node_label in graph_config.taxonomy.node_labels
        ],
        "relationship_types": [
            {
                "label": relationship_type.name,
                "description": relationship_type.description,
            }
            for relationship_type in graph_config.relationships.relationship_types
        ],
        "patterns": [
            (
                relationship_type.source,
                relationship_type.name,
                relationship_type.target,
            )
            for relationship_type in graph_config.relationships.relationship_types
        ],
    }
```

- [ ] **Step 4: Add CLI command**

Modify `src/jd_query_graph/cli.py` imports:

```python
from jd_query_graph.schema import build_graphrag_schema
```

Add:

```python
@app.command()
def build_graphrag_schema() -> None:
    """Print the GraphRAG schema derived from repo config."""

    graph_config = load_graph_config()
    _echo_json({"status": "ok", "schema": build_graphrag_schema(graph_config)})
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_schema_export.py tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/jd_query_graph/schema.py src/jd_query_graph/cli.py tests/test_schema_export.py tests/test_cli.py
git commit -m "feat: export graphrag schema"
```

## Task 6: Extraction Models And Fake GraphRAG Adapter

**Files:**
- Create: `src/jd_query_graph/extraction.py`
- Test: `tests/test_extraction.py`

- [ ] **Step 1: Write failing extraction tests**

Create `tests/test_extraction.py`:

```python
from jd_query_graph.extraction import (
    ExtractedRelationship,
    ExtractedTerm,
    FakeGraphRagExtractor,
)
from jd_query_graph.jd_input import CanonicalJdRecord, build_extraction_text


def record() -> CanonicalJdRecord:
    return CanonicalJdRecord.model_validate(
        {
            "canonical_source_key": "detail_id:1",
            "source_url": "https://example.invalid/job/1",
            "title": "示例岗位甲",
            "team": "示例团队",
            "cities": ["示例城市"],
            "responsibilities": ["负责候选需求甲。", "负责候选需求乙。"],
            "qualifications": ["具备示例能力。"],
            "raw_snapshot_path": "raw_pages/details/1.md",
            "raw_snapshot_sha256": "abc123",
        }
    )


def test_fake_extractor_returns_terms_and_candidate_relationships() -> None:
    extractor = FakeGraphRagExtractor(
        terms=[
            ExtractedTerm(
                text="term-alpha",
                term_category="TECH_OBJECT",
                evidence_text="负责候选需求甲。",
                source_field="responsibilities",
                confidence=0.91,
            ),
            ExtractedTerm(
                text="term-beta",
                term_category="CAPABILITY",
                evidence_text="负责候选需求乙。",
                source_field="responsibilities",
                confidence=0.88,
            ),
        ],
        relationships=[
            ExtractedRelationship(
                source_text="term-alpha",
                target_text="term-beta",
                relationship_type="RELATED_TO",
                evidence_text="负责候选需求甲。负责候选需求乙。",
                confidence=0.74,
                relation_rationale="Both terms describe engineering automation work in the same JD.",
            )
        ],
    )

    result = extractor.extract(record(), build_extraction_text(record()))

    assert [term.text for term in result.terms] == ["term-alpha", "term-beta"]
    assert result.relationships[0].relationship_type == "RELATED_TO"
    assert result.metadata == {
        "extractor": "fake-graphrag",
        "model": "fake-model",
        "prompt_version": "fake-prompt-v1",
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_extraction.py -q
```

Expected: fail because extraction module does not exist.

- [ ] **Step 3: Implement extraction models**

Create `src/jd_query_graph/extraction.py`:

```python
"""Extraction adapter contracts for GraphRAG-backed query term extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, Field

from jd_query_graph.jd_input import CanonicalJdRecord


class ExtractedTerm(BaseModel):
    text: str = Field(min_length=1)
    term_category: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    source_field: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedRelationship(BaseModel):
    source_text: str = Field(min_length=1)
    target_text: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    relation_rationale: str | None = None


class ExtractionResult(BaseModel):
    terms: list[ExtractedTerm]
    relationships: list[ExtractedRelationship]
    metadata: dict[str, str]


class GraphRagExtractor(Protocol):
    def extract(
        self,
        record: CanonicalJdRecord,
        extraction_text: str,
    ) -> ExtractionResult:
        """Extract query terms and candidate relationships from one JD."""


@dataclass(frozen=True)
class FakeGraphRagExtractor:
    terms: list[ExtractedTerm] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
    extractor: str = "fake-graphrag"
    model: str = "fake-model"
    prompt_version: str = "fake-prompt-v1"

    def extract(
        self,
        record: CanonicalJdRecord,
        extraction_text: str,
    ) -> ExtractionResult:
        return ExtractionResult(
            terms=self.terms,
            relationships=self.relationships,
            metadata={
                "extractor": self.extractor,
                "model": self.model,
                "prompt_version": self.prompt_version,
            },
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_extraction.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/jd_query_graph/extraction.py tests/test_extraction.py
git commit -m "feat: add graphrag extraction adapter contract"
```

## Task 7: Extraction Artifact Writer

**Files:**
- Create: `src/jd_query_graph/artifacts.py`
- Modify: `src/jd_query_graph/cli.py`
- Test: `tests/test_artifacts.py`, `tests/test_cli.py`

- [ ] **Step 1: Write failing artifact tests**

Create `tests/test_artifacts.py`:

```python
import json
from pathlib import Path

from jd_query_graph.artifacts import write_extraction_artifact
from jd_query_graph.extraction import (
    ExtractedRelationship,
    ExtractedTerm,
    ExtractionResult,
)
from jd_query_graph.jd_input import CanonicalJdRecord


def test_write_extraction_artifact_records_evidence(tmp_path: Path) -> None:
    record = CanonicalJdRecord.model_validate(
        {
            "canonical_source_key": "detail_id:1",
            "source_url": "https://example.invalid/job/1",
            "cities": ["示例城市"],
            "responsibilities": ["负责候选需求甲。"],
            "qualifications": [],
            "raw_snapshot_path": "raw_pages/details/1.md",
            "raw_snapshot_sha256": "abc123",
        }
    )
    result = ExtractionResult(
        terms=[
            ExtractedTerm(
                text="term-alpha",
                term_category="TECH_OBJECT",
                evidence_text="负责候选需求甲。",
                source_field="responsibilities",
                confidence=0.91,
            )
        ],
        relationships=[
            ExtractedRelationship(
                source_text="term-alpha",
                target_text="term-beta",
                relationship_type="RELATED_TO",
                evidence_text="负责候选需求甲。",
                confidence=0.74,
            )
        ],
        metadata={
            "extractor": "fake-graphrag",
            "model": "fake-model",
            "prompt_version": "fake-prompt-v1",
        },
    )
    output_path = tmp_path / "extraction.jsonl"

    summary = write_extraction_artifact(output_path, [(record, result)])

    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert summary == {"job_count": 1, "term_count": 1, "relationship_count": 1}
    assert rows[0]["record_type"] == "term"
    assert rows[0]["canonical_source_key"] == "detail_id:1"
    assert rows[0]["evidence_text"] == "负责候选需求甲。"
    assert rows[1]["record_type"] == "relationship"
    assert rows[1]["status"] == "candidate"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_artifacts.py -q
```

Expected: fail because artifact writer does not exist.

- [ ] **Step 3: Implement artifact writer**

Create `src/jd_query_graph/artifacts.py`:

```python
"""Artifact writers for extraction runs."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from jd_query_graph.extraction import ExtractionResult
from jd_query_graph.jd_input import CanonicalJdRecord


def write_extraction_artifact(
    output_path: Path,
    records: Iterable[tuple[CanonicalJdRecord, ExtractionResult]],
) -> dict[str, int]:
    """Write extracted terms and candidate relationships as JSONL."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    job_count = 0
    term_count = 0
    relationship_count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for record, result in records:
            job_count += 1
            for term in result.terms:
                term_count += 1
                _write_row(
                    handle,
                    {
                        "record_type": "term",
                        "canonical_source_key": record.canonical_source_key,
                        "source_url": record.source_url,
                        **term.model_dump(),
                        **result.metadata,
                        "status": "candidate",
                    },
                )
            for relationship in result.relationships:
                relationship_count += 1
                _write_row(
                    handle,
                    {
                        "record_type": "relationship",
                        "canonical_source_key": record.canonical_source_key,
                        "source_url": record.source_url,
                        **relationship.model_dump(),
                        **result.metadata,
                        "status": "candidate",
                    },
                )
    return {
        "job_count": job_count,
        "term_count": term_count,
        "relationship_count": relationship_count,
    }


def _write_row(handle, payload: dict[str, object]) -> None:
    handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
```

- [ ] **Step 4: Add `extract-sample` CLI using fake extractor**

In `src/jd_query_graph/cli.py`, import:

```python
from jd_query_graph.artifacts import write_extraction_artifact
from jd_query_graph.extraction import ExtractedTerm, FakeGraphRagExtractor
from jd_query_graph.jd_input import build_extraction_text
```

Add command:

```python
@app.command()
def extract_sample(
    input_jsonl: Path,
    output: Annotated[
        Path,
        typer.Option("--output", help="Output extraction JSONL artifact path."),
    ],
    limit: Annotated[int, typer.Option("--limit", min=1)] = 20,
) -> None:
    """Run a deterministic fake extraction sample over canonical JD input."""

    rows = []
    for index, record in enumerate(iter_jd_records(input_jsonl)):
        if index >= limit:
            break
        extraction_text = build_extraction_text(record)
        first_line = extraction_text.splitlines()[0] if extraction_text else record.canonical_source_key
        extractor = FakeGraphRagExtractor(
            terms=[
                ExtractedTerm(
                    text=first_line,
                    term_category="UNKNOWN",
                    evidence_text=first_line,
                    source_field="title",
                    confidence=0.5,
                )
            ]
        )
        rows.append((record, extractor.extract(record, extraction_text)))
    summary = write_extraction_artifact(output, rows)
    _echo_json({"status": "ok", **summary, "output": str(output)})
```

This fake command is contract scaffolding only. The real GraphRAG adapter is a later task or plan.

- [ ] **Step 5: Add CLI test for extract sample**

Add to `tests/test_cli.py`:

```python
def test_extract_sample_command_writes_artifact(tmp_path: Path) -> None:
    input_path = tmp_path / "jds.jsonl"
    output_path = tmp_path / "extraction.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "canonical_source_key": "detail_id:1",
                "source_url": "https://example.invalid/job/1",
                "title": "示例岗位甲",
                "cities": ["示例城市"],
                "responsibilities": ["负责候选需求甲。"],
                "qualifications": [],
                "raw_snapshot_path": "raw_pages/details/1.md",
                "raw_snapshot_sha256": "abc123",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["extract-sample", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["job_count"] == 1
    assert output_path.exists()
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_artifacts.py tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/jd_query_graph/artifacts.py src/jd_query_graph/cli.py tests/test_artifacts.py tests/test_cli.py
git commit -m "feat: write extraction artifacts"
```

## Task 8: Fake Recall And Query Artifact

**Files:**
- Create: `src/jd_query_graph/recall.py`
- Create: `src/jd_query_graph/query.py`
- Modify: `src/jd_query_graph/cli.py`
- Test: `tests/test_recall.py`, `tests/test_query.py`, `tests/test_cli.py`

- [ ] **Step 1: Write failing recall and query tests**

Create `tests/test_recall.py`:

```python
from jd_query_graph.recall import FakeRecallProvider


def test_fake_recall_provider_returns_stable_observation() -> None:
    provider = FakeRecallProvider({"term-alpha": 42})

    observation = provider.count("term-alpha")

    assert observation.provider == "fake-cts"
    assert observation.query_text == "term-alpha"
    assert observation.total == 42
    assert observation.status == "ok"
```

Create `tests/test_query.py`:

```python
from jd_query_graph.query import build_query_response
from jd_query_graph.recall import RecallObservation


def test_build_query_response_returns_exact_and_related_terms() -> None:
    response = build_query_response(
        query="term-alpha",
        terms=["term-alpha", "term-beta"],
        relationships=[
            {
                "source_text": "term-alpha",
                "target_text": "term-beta",
                "relationship_type": "RELATED_TO",
                "evidence_text": "负责候选需求甲。负责候选需求乙。",
                "confidence": 0.74,
            }
        ],
        observations={
            "term-alpha": RecallObservation(
                provider="fake-cts",
                query_text="term-alpha",
                total=42,
                status="ok",
            ),
            "term-beta": RecallObservation(
                provider="fake-cts",
                query_text="term-beta",
                total=8,
                status="ok",
            ),
        },
    )

    assert response["exact"]["cts_total"] == 42
    assert response["related_terms"] == [
        {
            "text": "term-beta",
            "relationship_type": "RELATED_TO",
            "cts_total": 8,
            "status": "ok",
            "evidence_text": "负责候选需求甲。负责候选需求乙。",
            "confidence": 0.74,
        }
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_recall.py tests/test_query.py -q
```

Expected: fail because modules do not exist.

- [ ] **Step 3: Implement fake recall provider**

Create `src/jd_query_graph/recall.py`:

```python
"""Recall provider contracts and fake CTS provider."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecallObservation(BaseModel):
    provider: str = "fake-cts"
    query_text: str = Field(min_length=1)
    total: int | None = Field(default=None, ge=0)
    status: str


class FakeRecallProvider:
    def __init__(self, totals: dict[str, int] | None = None) -> None:
        self._totals = totals or {}

    def count(self, query_text: str) -> RecallObservation:
        if query_text in self._totals:
            return RecallObservation(
                query_text=query_text,
                total=self._totals[query_text],
                status="ok",
            )
        return RecallObservation(
            query_text=query_text,
            total=None,
            status="unknown",
        )
```

- [ ] **Step 4: Implement query assembler**

Create `src/jd_query_graph/query.py`:

```python
"""Artifact-backed query response assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from jd_query_graph.recall import RecallObservation


def build_query_response(
    query: str,
    terms: Sequence[str],
    relationships: Sequence[Mapping[str, Any]],
    observations: Mapping[str, RecallObservation],
) -> dict[str, Any]:
    exact_observation = observations.get(query)
    return {
        "query": query,
        "exact": _term_payload(query, exact_observation),
        "related_terms": [
            {
                "text": str(relationship["target_text"]),
                "relationship_type": str(relationship["relationship_type"]),
                **_observation_payload(
                    observations.get(str(relationship["target_text"]))
                ),
                "evidence_text": str(relationship["evidence_text"]),
                "confidence": float(relationship["confidence"]),
            }
            for relationship in relationships
            if relationship.get("source_text") == query
        ],
    }


def _term_payload(
    text: str,
    observation: RecallObservation | None,
) -> dict[str, Any]:
    return {"text": text, **_observation_payload(observation)}


def _observation_payload(
    observation: RecallObservation | None,
) -> dict[str, Any]:
    if observation is None:
        return {"cts_total": None, "status": "unknown"}
    return {"cts_total": observation.total, "status": observation.status}
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_recall.py tests/test_query.py -q
```

Expected: pass.

- [ ] **Step 6: Add query artifact CLI test**

Add to `tests/test_cli.py`:

```python
def test_query_artifact_command_returns_related_terms(tmp_path: Path) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    artifact_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "record_type": "term",
                        "text": "term-alpha",
                        "evidence_text": "负责候选需求甲。",
                        "canonical_source_key": "detail_id:1",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "record_type": "term",
                        "text": "term-beta",
                        "evidence_text": "负责候选需求乙。",
                        "canonical_source_key": "detail_id:1",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "record_type": "relationship",
                        "source_text": "term-alpha",
                        "target_text": "term-beta",
                        "relationship_type": "RELATED_TO",
                        "evidence_text": "负责候选需求甲。负责候选需求乙。",
                        "confidence": 0.74,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["query-artifact", str(artifact_path), "term-alpha"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["response"]["query"] == "term-alpha"
    assert payload["response"]["related_terms"][0]["text"] == "term-beta"
```

- [ ] **Step 7: Implement query artifact CLI command**

Modify `src/jd_query_graph/cli.py` imports:

```python
import json

from jd_query_graph.query import build_query_response
from jd_query_graph.recall import FakeRecallProvider
```

If `json` is already imported, keep one import only.

Add command:

```python
@app.command()
def query_artifact(artifact_jsonl: Path, query: str) -> None:
    """Query an extraction artifact with fake recall observations."""

    terms: list[str] = []
    relationships: list[dict[str, object]] = []
    with artifact_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("record_type") == "term":
                terms.append(str(row["text"]))
            elif row.get("record_type") == "relationship":
                relationships.append(row)
    provider = FakeRecallProvider({term: 0 for term in terms})
    observations = {term: provider.count(term) for term in terms}
    response = build_query_response(
        query=query,
        terms=terms,
        relationships=relationships,
        observations=observations,
    )
    _echo_json({"status": "ok", "response": response})
```

- [ ] **Step 8: Run CLI query tests to verify pass**

Run:

```bash
uv run --extra dev pytest tests/test_recall.py tests/test_query.py tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/jd_query_graph/recall.py src/jd_query_graph/query.py src/jd_query_graph/cli.py tests/test_recall.py tests/test_query.py tests/test_cli.py
git commit -m "feat: add fake recall query response"
```

## Task 9: End-To-End Phase 1 Verification

**Files:**
- Modify: `README.md`
- Test: all tests

- [ ] **Step 1: Update README with Phase 1 commands**

Replace the temporary fixed JD JSONL section with the canonical contract and add:

````markdown
## Phase 1 Commands

```bash
uv run --extra dev jd-query-graph validate-config
uv run --extra dev jd-query-graph build-graphrag-schema
uv run --extra dev jd-query-graph copy-corpus
uv run --extra dev jd-query-graph inspect-jds data/corpora/bytedance/factual_jobs_mainland.jsonl
uv run --extra dev jd-query-graph extract-sample data/corpora/bytedance/factual_jobs_mainland.jsonl --output artifacts/extraction/sample.jsonl --limit 20
```

`data/` and `artifacts/` are local working directories and are ignored by git.
````

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
uv build --wheel
```

Expected:

- pytest passes.
- Ruff reports `All checks passed!`.
- Wheel build succeeds.

- [ ] **Step 3: Run live local corpus copy if source exists**

Run:

```bash
uv run --extra dev jd-query-graph copy-corpus
wc -l data/corpora/bytedance/factual_jobs_mainland.jsonl
```

Expected:

```text
9530 data/corpora/bytedance/factual_jobs_mainland.jsonl
```

If the source path is unavailable, stop and report the missing local corpus. Do not substitute synthetic data.

- [ ] **Step 4: Run sample extraction artifact**

Run:

```bash
uv run --extra dev jd-query-graph extract-sample data/corpora/bytedance/factual_jobs_mainland.jsonl --output artifacts/extraction/sample.jsonl --limit 20
wc -l artifacts/extraction/sample.jsonl
```

Expected: command succeeds and artifact has at least 20 lines.

- [ ] **Step 5: Check for forbidden hardcoded term pairs**

Run:

```bash
rg -n "hardcoded_terms|STATIC_TERM|TERM_WHITELIST|alias_pairs|synonym_pairs" src tests configs
```

Expected: no matches. If matches appear in implementation, config, or tests, remove them before claiming Phase 1 is ready.

- [ ] **Step 6: Commit**

Run:

```bash
git add README.md
git commit -m "docs: document phase1 workflow"
```

## Self-Review Checklist

- Spec coverage: Tasks cover repo workflow, corpus copy, canonical JD parsing, approved schema config, GraphRAG schema export, extraction adapter contract, extraction artifacts, fake recall/query response, and Phase 1 verification.
- Explicit exclusions: Real CTS, real LLM execution, Neo4j persistence, community detection, and full 9530 extraction are excluded from Phase 1 and require later gated plans.
- No unfinished markers: Every task has concrete files, tests, commands, and expected outcomes.
- Type consistency: `CanonicalJdRecord`, `build_extraction_text`, `GraphConfig`, `build_graphrag_schema`, `ExtractedTerm`, `ExtractedRelationship`, `ExtractionResult`, `FakeGraphRagExtractor`, `RecallObservation`, and `build_query_response` names are consistent across tasks.
