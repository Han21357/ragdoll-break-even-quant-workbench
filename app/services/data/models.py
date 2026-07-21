"""Normalized market-data records and source metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SourceStatus:
    source: str
    status: str
    as_of: str | None = None
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    message: str | None = None
    latency_ms: int | None = None


@dataclass
class DataResult:
    ok: bool
    data: Any
    provenance: list[SourceStatus]
    error: str | None = None
    completeness: float | None = None
    missing_fields: dict[str, str] = field(default_factory=dict)
    data_date: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    cache_status: str = "miss"

    def meta(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data_date": self.data_date,
            "updated_at": self.updated_at,
            "completeness": self.completeness,
            "missing_fields": self.missing_fields,
            "cache_status": self.cache_status,
            "error": self.error,
            "sources": [item.__dict__ for item in self.provenance],
        }


NORMALIZED_DAILY_FIELDS = [
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover_rate",
    "pct_change",
    "adjustment",
    "source",
    "as_of",
    "status",
]
