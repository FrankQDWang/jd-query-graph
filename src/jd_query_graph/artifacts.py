"""Artifact writers for extraction runs."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

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
                    },
                )
    return {
        "job_count": job_count,
        "term_count": term_count,
        "relationship_count": relationship_count,
    }


def _write_row(handle: TextIO, payload: dict[str, object]) -> None:
    handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
