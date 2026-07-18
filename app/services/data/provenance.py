"""Helpers for data source visibility."""
from __future__ import annotations

from .models import SourceStatus


def summarize_status(provenance: list[SourceStatus]) -> dict:
    if not provenance:
        return {"status": "unavailable", "sources": []}
    if any(item.status == "ok" for item in provenance) and any(item.status != "ok" for item in provenance):
        status = "degraded"
    elif all(item.status == "ok" for item in provenance):
        status = "ok"
    elif any(item.status == "stale" for item in provenance):
        status = "stale"
    else:
        status = "unavailable"
    return {"status": status, "sources": [item.__dict__ for item in provenance]}

