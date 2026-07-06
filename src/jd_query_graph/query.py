"""Artifact-backed query response assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from jd_query_graph.recall import RecallObservation


def build_query_response(
    query: str,
    terms: Sequence[str],
    relationships: Sequence[Mapping[str, Any]],
    observations: Mapping[str, RecallObservation],
    snapshot_id: str = "artifact",
    generated_at: str = "2026-07-03T00:00:00Z",
) -> dict[str, Any]:
    normalized_query = _normalize_query(query)
    matched_term, match_type = _match_term(
        query=query,
        normalized_query=normalized_query,
        terms=terms,
    )
    exact_observation = observations.get(matched_term)
    return {
        "response_version": "query-response-v1",
        "snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "query": query,
        "normalized_query": normalized_query,
        "exact": _term_payload(
            matched_term,
            exact_observation,
            match_type=match_type,
        ),
        "related_terms": _related_terms(
            matched_term=matched_term,
            relationships=relationships,
            observations=observations,
        ),
    }


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().casefold().split())


def _match_term(
    query: str,
    normalized_query: str,
    terms: Sequence[str],
) -> tuple[str, str]:
    if query in terms:
        return query, "exact"
    for term in terms:
        if _normalize_query(term) == normalized_query:
            return term, "normalized"
    return query, "unmatched"


def _related_terms(
    matched_term: str,
    relationships: Sequence[Mapping[str, Any]],
    observations: Mapping[str, RecallObservation],
) -> list[dict[str, Any]]:
    related = []
    for relationship in relationships:
        source_text = str(relationship["source_text"])
        target_text = str(relationship["target_text"])
        if source_text == matched_term:
            neighbor_text = target_text
            direction = "outgoing"
        elif target_text == matched_term:
            neighbor_text = source_text
            direction = "incoming"
        else:
            continue
        related.append(
            {
                "text": neighbor_text,
                "relationship_type": str(relationship["relationship_type"]),
                "direction": direction,
                **_observation_payload(observations.get(neighbor_text)),
                "relationship_status": str(relationship.get("status", "candidate")),
                "evidence_text": str(relationship["evidence_text"]),
                "confidence": float(relationship["confidence"]),
            }
        )
    return related


def _term_payload(
    text: str,
    observation: RecallObservation | None,
    match_type: str,
) -> dict[str, Any]:
    return {"text": text, "match_type": match_type, **_observation_payload(observation)}


def _observation_payload(
    observation: RecallObservation | None,
) -> dict[str, Any]:
    if observation is None:
        return {"cts_total": None, "status": "unknown"}
    return {"cts_total": observation.total, "status": observation.status}
