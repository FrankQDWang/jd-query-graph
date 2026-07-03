import json
from pathlib import Path

from typer.testing import CliRunner

from jd_query_graph.cli import app


def test_validate_config_command_outputs_summary() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-config"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["node_type_count"] >= 2
    assert "ALIAS_OF" in payload["relationship_types"]


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
