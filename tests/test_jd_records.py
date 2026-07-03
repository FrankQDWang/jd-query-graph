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
