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
