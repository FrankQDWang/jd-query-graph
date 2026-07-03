from pathlib import Path

from jd_query_graph.corpus import (
    CORPUS_SOURCE_ENV,
    DEFAULT_LOCAL_CORPUS,
    KNOWN_BYTEDANCE_MAINLAND_SOURCE,
    CorpusCopyResult,
    copy_corpus,
    resolve_corpus_source,
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


def test_default_local_corpus_path_is_stable() -> None:
    assert Path(
        "data/corpora/bytedance/factual_jobs_mainland.jsonl"
    ) == DEFAULT_LOCAL_CORPUS


def test_source_path_can_come_from_environment(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"

    assert resolve_corpus_source({CORPUS_SOURCE_ENV: str(source)}) == source


def test_explicit_empty_environment_uses_known_local_source() -> None:
    assert resolve_corpus_source(env={}) == KNOWN_BYTEDANCE_MAINLAND_SOURCE


def test_explicit_source_path_wins_over_environment(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    configured = tmp_path / "configured.jsonl"

    assert (
        resolve_corpus_source(
            env={CORPUS_SOURCE_ENV: str(configured)},
            source_path=source,
        )
        == source
    )
