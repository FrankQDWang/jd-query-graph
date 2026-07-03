"""Recall provider contracts and fake CTS provider."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field


class RecallObservation(BaseModel):
    observation_id: str = Field(min_length=1)
    provider: str = "fake-cts"
    query_text: str = Field(min_length=1)
    query_mode: str = "exact"
    total: int | None = Field(default=None, ge=0)
    status: str
    recall_bucket: str | None = None
    observed_at: str = Field(min_length=1)
    probe_run_id: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    error_code: str | None = None
    created_at: str = Field(min_length=1)


class FakeRecallProvider:
    def __init__(
        self,
        totals: dict[str, int] | None = None,
        probe_run_id: str = "fake-probe-run",
        observed_at: str = "2026-07-03T00:00:00Z",
    ) -> None:
        self._totals = totals or {}
        self._probe_run_id = probe_run_id
        self._observed_at = observed_at

    def count(self, query_text: str, query_mode: str = "exact") -> RecallObservation:
        request_hash = _request_hash(query_text=query_text, query_mode=query_mode)
        base = {
            "observation_id": f"{self._probe_run_id}:{request_hash}",
            "query_text": query_text,
            "query_mode": query_mode,
            "observed_at": self._observed_at,
            "probe_run_id": self._probe_run_id,
            "request_hash": request_hash,
            "created_at": self._observed_at,
        }
        if query_text in self._totals:
            return RecallObservation(
                **base,
                total=self._totals[query_text],
                status="ok",
                recall_bucket=_bucket(self._totals[query_text]),
            )
        return RecallObservation(
            **base,
            total=None,
            status="unknown",
        )


def _request_hash(query_text: str, query_mode: str) -> str:
    payload = f"fake-cts:{query_mode}:{query_text}".encode()
    return hashlib.sha256(payload).hexdigest()


def _bucket(total: int) -> str:
    if total == 0:
        return "0"
    if total < 10:
        return "1_9"
    if total < 100:
        return "10_99"
    return "100_plus"
