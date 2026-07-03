"""Local corpus copy and path helpers."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CORPUS_SOURCE_ENV = "JD_QUERY_GRAPH_CORPUS_SOURCE"
KNOWN_BYTEDANCE_MAINLAND_SOURCE = Path(
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
    source_path: Path | None = None,
    target_path: Path = DEFAULT_LOCAL_CORPUS,
) -> CorpusCopyResult:
    """Copy a local corpus JSONL into this repo's ignored data directory."""

    source_path = resolve_corpus_source(source_path=source_path)
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


def resolve_corpus_source(
    env: Mapping[str, str] | None = None,
    source_path: Path | None = None,
) -> Path:
    """Resolve source path without hardcoding personal paths in tests."""

    if source_path is not None:
        return source_path
    environment = os.environ if env is None else env
    if configured := environment.get(CORPUS_SOURCE_ENV):
        return Path(configured)
    return KNOWN_BYTEDANCE_MAINLAND_SOURCE
