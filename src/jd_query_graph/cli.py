"""Command line interface for the JD query graph tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from jd_query_graph.artifacts import write_extraction_artifact
from jd_query_graph.config import graph_config_summary, load_graph_config
from jd_query_graph.corpus import DEFAULT_LOCAL_CORPUS, copy_corpus
from jd_query_graph.extraction import ExtractedTerm, FakeGraphRagExtractor
from jd_query_graph.jd_input import (
    CanonicalJdRecord,
    build_extraction_text,
    iter_jd_records,
    summarize_jds,
)
from jd_query_graph.schema import build_graphrag_schema as build_graphrag_schema_payload

app = typer.Typer(no_args_is_help=True)


@app.command()
def validate_config(
    taxonomy: Annotated[
        Path,
        typer.Option(
            "--taxonomy",
            help="Path to the node taxonomy YAML config.",
        ),
    ] = Path("configs/taxonomy.yaml"),
    relationships: Annotated[
        Path,
        typer.Option(
            "--relationships",
            help="Path to the relationship taxonomy YAML config.",
        ),
    ] = Path("configs/relationships.yaml"),
) -> None:
    """Validate graph taxonomy and relationship configs."""

    graph_config = load_graph_config(taxonomy, relationships)
    payload = {"status": "ok", **graph_config_summary(graph_config)}
    _echo_json(payload)


@app.command()
def build_graphrag_schema() -> None:
    """Print the GraphRAG schema derived from repo config."""

    graph_config = load_graph_config()
    _echo_json(
        {"status": "ok", "schema": build_graphrag_schema_payload(graph_config)}
    )


@app.command("copy-corpus")
def copy_corpus_command(
    source: Annotated[
        Path | None,
        typer.Option(
            "--source",
            help="Source JD JSONL corpus path. Defaults to env or local example path.",
        ),
    ] = None,
    target: Annotated[
        Path,
        typer.Option("--target", help="Target ignored local corpus path."),
    ] = DEFAULT_LOCAL_CORPUS,
) -> None:
    """Copy a local ByteDance corpus into this repo's ignored data dir."""

    result = copy_corpus(source_path=source, target_path=target)
    _echo_json(
        {
            "status": "ok",
            "source_path": str(result.source_path),
            "target_path": str(result.target_path),
            "line_count": result.line_count,
            "byte_size": result.byte_size,
        }
    )


@app.command()
def inspect_jds(input_jsonl: Path) -> None:
    """Validate and summarize fixed-format JD JSONL."""

    summary = summarize_jds(iter_jd_records(input_jsonl))
    payload = {"status": "ok", **summary.model_dump()}
    _echo_json(payload)


@app.command()
def write_fake_extraction_artifact(
    input_jsonl: Path,
    output: Annotated[
        Path,
        typer.Option("--output", help="Output extraction JSONL artifact path."),
    ],
    limit: Annotated[int, typer.Option("--limit", min=1)] = 20,
) -> None:
    """Write a deterministic fake extraction artifact over canonical JD input."""

    rows = []
    for index, record in enumerate(iter_jd_records(input_jsonl)):
        if index >= limit:
            break
        extraction_text = build_extraction_text(record)
        evidence_text, source_field, source_index = _first_extraction_evidence(record)
        extractor = FakeGraphRagExtractor(
            terms=[
                ExtractedTerm(
                    term_id=f"fake:{record.canonical_source_key}",
                    text=evidence_text,
                    normalized_text=evidence_text.strip().casefold(),
                    term_category="UNKNOWN",
                    language="unknown",
                    evidence_text=evidence_text,
                    source_field=source_field,
                    source_index=source_index,
                    char_start=0,
                    char_end=len(evidence_text),
                    confidence=0.5,
                )
            ]
        )
        rows.append((record, extractor.extract(record, extraction_text)))
    summary = write_extraction_artifact(output, rows)
    _echo_json({"status": "ok", **summary, "output": str(output)})


def main() -> None:
    app()


def _echo_json(payload: dict[str, object]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _first_extraction_evidence(
    record: CanonicalJdRecord,
) -> tuple[str, str, int | None]:
    if record.title:
        return f"title: {record.title}", "title", None
    if record.team:
        return f"team: {record.team}", "team", None
    if record.responsibilities:
        return (
            f"responsibilities[0]: {record.responsibilities[0]}",
            "responsibilities",
            0,
        )
    if record.qualifications:
        return (
            f"qualifications[0]: {record.qualifications[0]}",
            "qualifications",
            0,
        )
    return record.canonical_source_key, "canonical_source_key", None
