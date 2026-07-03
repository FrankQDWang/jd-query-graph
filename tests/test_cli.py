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
                "jd_id": "job-001",
                "title": "Backend Engineer",
                "description": "Build Go services on Kubernetes.",
                "language": "en",
                "source": "fixture",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["inspect-jds", str(input_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "status": "ok",
        "total_records": 1,
        "language_counts": {"en": 1},
        "source_counts": {"fixture": 1},
    }

