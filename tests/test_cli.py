import json
from pathlib import Path

from typer.testing import CliRunner

import jd_query_graph.cli as cli
from jd_query_graph.cli import app


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


def test_build_graphrag_schema_command_outputs_schema() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["build-graphrag-schema"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert ["QueryTerm", "SAME_AS", "QueryTerm"] in payload["schema"]["patterns"]


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


def test_write_fake_extraction_artifact_command_writes_artifact(
    tmp_path: Path,
) -> None:
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
        [
            "write-fake-extraction-artifact",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["job_count"] == 1
    assert output_path.exists()
    artifact_row = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact_row["extractor"] == "fake-graphrag"
    assert artifact_row["model"] == "fake-model"
    assert artifact_row["prompt_version"] == "fake-prompt-v1"


def test_write_fake_extraction_artifact_uses_truthful_source_field(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "jds.jsonl"
    output_path = tmp_path / "extraction.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "canonical_source_key": "detail_id:1",
                "source_url": "https://example.invalid/job/1",
                "team": "示例团队",
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
        [
            "write-fake-extraction-artifact",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    artifact_row = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact_row["evidence_text"] == "team: 示例团队"
    assert artifact_row["source_field"] == "team"
    assert artifact_row["source_index"] is None


def test_write_fake_extraction_artifact_honors_limit(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "jds.jsonl"
    output_path = tmp_path / "extraction.jsonl"
    rows = [
        {
            "canonical_source_key": "detail_id:1",
            "source_url": "https://example.invalid/job/1",
            "title": "示例岗位甲",
            "cities": ["示例城市"],
            "responsibilities": [],
            "qualifications": [],
            "raw_snapshot_path": "raw_pages/details/1.md",
            "raw_snapshot_sha256": "abc123",
        },
        {
            "canonical_source_key": "detail_id:2",
            "source_url": "https://example.invalid/job/2",
            "title": "示例岗位乙",
            "cities": ["示例城市"],
            "responsibilities": [],
            "qualifications": [],
            "raw_snapshot_path": "raw_pages/details/2.md",
            "raw_snapshot_sha256": "def456",
        },
    ]
    input_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "write-fake-extraction-artifact",
            str(input_path),
            "--output",
            str(output_path),
            "--limit",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["job_count"] == 1
    artifact_rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(artifact_rows) == 1
    assert artifact_rows[0]["canonical_source_key"] == "detail_id:1"


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


def test_write_neo4j_artifact_command_outputs_summary_and_uses_session(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "extraction.jsonl"
    settings = object()
    graph = object()
    session = object()
    events: list[tuple[str, object]] = []

    class FakeSummary:
        def __init__(self) -> None:
            self.job_count = 1
            self.term_count = 2
            self.mentioned_in_count = 3
            self.relationship_count = 4
            self.recall_observation_count = 5

    class FakeSessionContext:
        def __init__(self, received_settings: object) -> None:
            events.append(("session_settings", received_settings))

        def __enter__(self) -> object:
            events.append(("enter", session))
            return session

        def __exit__(self, *exc_info: object) -> None:
            events.append(("exit", session))

    def fake_load_artifact_graph(path: Path) -> object:
        events.append(("artifact_path", path))
        return graph

    def fake_write_artifact_graph(received_session: object, received_graph: object):
        events.append(("write_session", received_session))
        events.append(("write_graph", received_graph))
        return FakeSummary()

    monkeypatch.setattr(cli, "load_neo4j_settings", lambda: settings)
    monkeypatch.setattr(cli, "load_artifact_graph", fake_load_artifact_graph)
    monkeypatch.setattr(cli, "neo4j_session", FakeSessionContext)
    monkeypatch.setattr(cli, "write_artifact_graph", fake_write_artifact_graph)
    runner = CliRunner()

    result = runner.invoke(app, ["write-neo4j-artifact", str(artifact_path)])

    assert result.exit_code == 0
    assert events == [
        ("artifact_path", artifact_path),
        ("session_settings", settings),
        ("enter", session),
        ("write_session", session),
        ("write_graph", graph),
        ("exit", session),
    ]
    assert json.loads(result.output) == {
        "job_count": 1,
        "mentioned_in_count": 3,
        "recall_observation_count": 5,
        "relationship_count": 4,
        "status": "ok",
        "term_count": 2,
    }


def test_query_neo4j_command_outputs_response_and_uses_session(monkeypatch) -> None:
    settings = object()
    session = object()
    response = {"query": "term-alpha", "related_terms": []}
    events: list[tuple[str, object]] = []

    class FakeSessionContext:
        def __init__(self, received_settings: object) -> None:
            events.append(("session_settings", received_settings))

        def __enter__(self) -> object:
            events.append(("enter", session))
            return session

        def __exit__(self, *exc_info: object) -> None:
            events.append(("exit", session))

    def fake_query_neo4j_response(received_session: object, query: str):
        events.append(("query_session", received_session))
        events.append(("query", query))
        return response

    monkeypatch.setattr(cli, "load_neo4j_settings", lambda: settings)
    monkeypatch.setattr(cli, "neo4j_session", FakeSessionContext)
    monkeypatch.setattr(cli, "query_neo4j_response", fake_query_neo4j_response)
    runner = CliRunner()

    result = runner.invoke(app, ["query-neo4j", "term-alpha"])

    assert result.exit_code == 0
    assert events == [
        ("session_settings", settings),
        ("enter", session),
        ("query_session", session),
        ("query", "term-alpha"),
        ("exit", session),
    ]
    assert json.loads(result.output) == {
        "response": response,
        "status": "ok",
    }
