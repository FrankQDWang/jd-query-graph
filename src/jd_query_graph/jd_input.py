"""Fixed-format JD JSONL parsing."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class JdRecordError(ValueError):
    """Raised when a JD JSONL record cannot be parsed."""


class JdRecord(BaseModel):
    """Normalized JD input record."""

    model_config = ConfigDict(extra="allow", frozen=True)

    jd_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1)
    company: str | None = None
    language: str = "unknown"
    url: str | None = None


class JdSummary(BaseModel):
    """Aggregate information about a JD input file."""

    total_records: int
    language_counts: dict[str, int]
    source_counts: dict[str, int]


def iter_jd_records(path: Path | str) -> Iterator[JdRecord]:
    """Yield validated JD records from a JSONL file."""

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
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise JdRecordError(
                    f"line {line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(payload, dict):
                raise JdRecordError(f"line {line_number}: record must be an object")
            try:
                yield JdRecord.model_validate(payload)
            except ValidationError as exc:
                raise JdRecordError(
                    f"line {line_number}: invalid JD record: {exc}"
                ) from exc


def summarize_jds(records: Iterable[JdRecord]) -> JdSummary:
    """Summarize a sequence of JD records."""

    total_records = 0
    language_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for record in records:
        total_records += 1
        language_counts[record.language] += 1
        source_counts[record.source] += 1

    return JdSummary(
        total_records=total_records,
        language_counts=dict(sorted(language_counts.items())),
        source_counts=dict(sorted(source_counts.items())),
    )
