"""Command line interface for the JD query graph tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from jd_query_graph.config import graph_config_summary, load_graph_config
from jd_query_graph.jd_input import iter_jd_records, summarize_jds

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
def inspect_jds(input_jsonl: Path) -> None:
    """Validate and summarize fixed-format JD JSONL."""

    summary = summarize_jds(iter_jd_records(input_jsonl))
    payload = {"status": "ok", **summary.model_dump()}
    _echo_json(payload)


def main() -> None:
    app()


def _echo_json(payload: dict[str, object]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))

