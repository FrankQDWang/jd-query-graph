"""Extraction adapter contracts for GraphRAG-backed query term extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Protocol, Self

from pydantic import BaseModel, Field, model_validator

from jd_query_graph.jd_input import CanonicalJdRecord


class ExtractedTerm(BaseModel):
    term_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    term_category: str = Field(min_length=1)
    language: str = Field(min_length=1)
    source: str = "llm_graphrag"
    status: str = "candidate"
    evidence_count: int = Field(default=1, ge=1)
    evidence_text: str = Field(min_length=1)
    source_field: str = Field(min_length=1)
    source_index: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_span_order(self) -> Self:
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class ExtractedRelationship(BaseModel):
    source_text: str = Field(min_length=1)
    target_text: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    source_jd_ids: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    candidate_source: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    status: str = "candidate"
    relation_rationale: str | None = None


class ExtractionResult(BaseModel):
    terms: list[ExtractedTerm]
    relationships: list[ExtractedRelationship]
    metadata: dict[str, str]


class GraphRagExtractor(Protocol):
    def extract(
        self,
        record: CanonicalJdRecord,
        extraction_text: str,
    ) -> ExtractionResult:
        """Extract query terms and candidate relationships from one JD."""


@dataclass(frozen=True)
class FakeGraphRagExtractor:
    terms: list[ExtractedTerm] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
    extractor: str = "fake-graphrag"
    model: str = "fake-model"
    prompt_version: str = "fake-prompt-v1"

    def extract(
        self,
        record: CanonicalJdRecord,
        extraction_text: str,
    ) -> ExtractionResult:
        return ExtractionResult(
            terms=self.terms,
            relationships=self.relationships,
            metadata={
                "extractor": self.extractor,
                "model": self.model,
                "prompt_version": self.prompt_version,
            },
        )
