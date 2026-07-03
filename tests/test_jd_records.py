import json
from pathlib import Path

import pytest

from jd_query_graph.jd_input import JdRecordError, iter_jd_records, summarize_jds


def test_reads_fixed_format_jd_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "jds.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "jd_id": "job-001",
                        "title": "Backend Engineer",
                        "company": "Example",
                        "description": "Build Go services on Kubernetes.",
                        "language": "en",
                        "source": "fixture",
                        "url": "https://example.invalid/jobs/001",
                    }
                ),
                json.dumps(
                    {
                        "jd_id": "job-002",
                        "title": "数据平台工程师",
                        "description": "负责 Spark 和 Flink 平台开发。",
                        "language": "zh",
                        "source": "fixture",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = list(iter_jd_records(input_path))
    summary = summarize_jds(records)

    assert [record.jd_id for record in records] == ["job-001", "job-002"]
    assert summary.total_records == 2
    assert summary.language_counts == {"en": 1, "zh": 1}
    assert summary.source_counts == {"fixture": 2}


def test_rejects_jd_record_without_description(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "jd_id": "job-001",
                "title": "Backend Engineer",
                "source": "fixture",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(JdRecordError, match="line 1"):
        list(iter_jd_records(input_path))

