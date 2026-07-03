import json
from pathlib import Path

from jd_query_graph.artifacts import write_extraction_artifact
from jd_query_graph.extraction import (
    ExtractedRelationship,
    ExtractedTerm,
    ExtractionResult,
)
from jd_query_graph.jd_input import CanonicalJdRecord


def test_write_extraction_artifact_records_evidence(tmp_path: Path) -> None:
    record = CanonicalJdRecord.model_validate(
        {
            "canonical_source_key": "detail_id:1",
            "source_url": "https://example.invalid/job/1",
            "cities": ["示例城市"],
            "responsibilities": ["负责候选需求甲。"],
            "qualifications": [],
            "raw_snapshot_path": "raw_pages/details/1.md",
            "raw_snapshot_sha256": "abc123",
        }
    )
    result = ExtractionResult(
        terms=[
            ExtractedTerm(
                term_id="term:alpha",
                text="term-alpha",
                normalized_text="term-alpha",
                term_category="TECH_OBJECT",
                language="en",
                evidence_text="负责候选需求甲。",
                source_field="responsibilities",
                source_index=0,
                char_start=0,
                char_end=8,
                confidence=0.91,
            )
        ],
        relationships=[
            ExtractedRelationship(
                source_text="term-alpha",
                target_text="term-beta",
                relationship_type="RELATED_TO",
                evidence_type="same_jd_context",
                evidence_text="负责候选需求甲。",
                source_jd_ids=["detail_id:1"],
                candidate_source="fake-graphrag",
                confidence=0.74,
                relation_rationale="Both terms appear in related JD context.",
            )
        ],
        metadata={
            "extractor": "fake-graphrag",
            "model": "fake-model",
            "prompt_version": "fake-prompt-v1",
        },
    )
    output_path = tmp_path / "extraction.jsonl"

    summary = write_extraction_artifact(output_path, [(record, result)])

    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert summary == {"job_count": 1, "term_count": 1, "relationship_count": 1}
    assert rows[0]["record_type"] == "term"
    assert rows[0]["canonical_source_key"] == "detail_id:1"
    assert rows[0]["evidence_text"] == "负责候选需求甲。"
    assert rows[0]["extractor"] == "fake-graphrag"
    assert rows[0]["model"] == "fake-model"
    assert rows[0]["prompt_version"] == "fake-prompt-v1"
    assert rows[1]["record_type"] == "relationship"
    assert rows[1]["status"] == "candidate"
    assert rows[1]["extractor"] == "fake-graphrag"
    assert rows[1]["model"] == "fake-model"
    assert rows[1]["prompt_version"] == "fake-prompt-v1"
