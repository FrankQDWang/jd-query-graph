import pytest
from pydantic import ValidationError

from jd_query_graph.extraction import (
    ExtractedRelationship,
    ExtractedTerm,
    FakeGraphRagExtractor,
)
from jd_query_graph.jd_input import CanonicalJdRecord, build_extraction_text


def record() -> CanonicalJdRecord:
    return CanonicalJdRecord.model_validate(
        {
            "canonical_source_key": "detail_id:1",
            "source_url": "https://example.invalid/job/1",
            "title": "示例岗位甲",
            "team": "示例团队",
            "cities": ["示例城市"],
            "responsibilities": ["负责候选需求甲。", "负责候选需求乙。"],
            "qualifications": ["具备示例能力。"],
            "raw_snapshot_path": "raw_pages/details/1.md",
            "raw_snapshot_sha256": "abc123",
        }
    )


def test_fake_extractor_returns_terms_and_candidate_relationships() -> None:
    extractor = FakeGraphRagExtractor(
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
            ),
            ExtractedTerm(
                term_id="term:beta",
                text="term-beta",
                normalized_text="term-beta",
                term_category="CAPABILITY",
                language="en",
                evidence_text="负责候选需求乙。",
                source_field="responsibilities",
                source_index=1,
                char_start=0,
                char_end=8,
                confidence=0.88,
            ),
        ],
        relationships=[
            ExtractedRelationship(
                source_text="term-alpha",
                target_text="term-beta",
                relationship_type="RELATED_TO",
                evidence_type="same_jd_context",
                evidence_text="负责候选需求甲。负责候选需求乙。",
                source_jd_ids=["detail_id:1"],
                candidate_source="fake-graphrag",
                confidence=0.74,
                relation_rationale=(
                    "Both terms describe engineering automation work in the same JD."
                ),
            )
        ],
    )

    result = extractor.extract(record(), build_extraction_text(record()))

    assert [term.text for term in result.terms] == ["term-alpha", "term-beta"]
    assert result.relationships[0].relationship_type == "RELATED_TO"
    assert result.metadata == {
        "extractor": "fake-graphrag",
        "model": "fake-model",
        "prompt_version": "fake-prompt-v1",
    }


def test_extracted_term_rejects_negative_source_index() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ExtractedTerm(
            term_id="term:alpha",
            text="term-alpha",
            normalized_text="term-alpha",
            term_category="TECH_OBJECT",
            language="en",
            evidence_text="负责候选需求甲。",
            source_field="responsibilities",
            source_index=-1,
            confidence=0.91,
        )


def test_extracted_term_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError, match="char_end must"):
        ExtractedTerm(
            term_id="term:alpha",
            text="term-alpha",
            normalized_text="term-alpha",
            term_category="TECH_OBJECT",
            language="en",
            evidence_text="负责候选需求甲。",
            source_field="responsibilities",
            char_start=8,
            char_end=7,
            confidence=0.91,
        )


def test_extracted_relationship_rejects_empty_source_jd_ids() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        ExtractedRelationship(
            source_text="term-alpha",
            target_text="term-beta",
            relationship_type="RELATED_TO",
            evidence_type="same_jd_context",
            evidence_text="负责候选需求甲。负责候选需求乙。",
            source_jd_ids=[],
            candidate_source="fake-graphrag",
            confidence=0.74,
        )


def test_extracted_relationship_rejects_empty_source_jd_id() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        ExtractedRelationship(
            source_text="term-alpha",
            target_text="term-beta",
            relationship_type="RELATED_TO",
            evidence_type="same_jd_context",
            evidence_text="负责候选需求甲。负责候选需求乙。",
            source_jd_ids=["detail_id:1", ""],
            candidate_source="fake-graphrag",
            confidence=0.74,
        )
