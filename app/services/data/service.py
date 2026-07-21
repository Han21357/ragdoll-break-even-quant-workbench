"""Unified application-facing DataProvider facade."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .cache import persistent_cache
from .models import DataResult, SourceStatus
from .registry import registry


class DataProvider:
    TTL = {"get_basic_factors": 180, "get_market_snapshot": 180, "get_sector_snapshot": 300, "get_stock_daily": 3600, "get_index_daily": 3600, "get_stock_profile": 21600, "get_fund_flow": 1800, "get_research_reports": 21600, "get_stock_news": 900, "get_announcements": 3600, "get_stock_list": 86400}

    def __init__(self, provider_registry=registry):
        self.registry = provider_registry

    def request(self, method: str, *args, required_fields: list[str] | None = None, **kwargs) -> DataResult:
        key = persistent_cache.key(method, args, kwargs)
        cached = persistent_cache.get(key, self.TTL.get(method, 900))
        if cached:
            return self._restore(cached[0], cached[1])
        result = self.registry.call(method, *args, **kwargs)
        self._annotate(result, required_fields or [])
        if result.ok:
            old = persistent_cache.get(key, self.TTL.get(method, 900), allow_stale=True)
            if old and method in {"get_stock_daily", "get_index_daily", "get_fund_flow"}:
                self._merge_incremental(result, old[0])
            persistent_cache.set(key, result)
            return result
        stale = persistent_cache.get(key, self.TTL.get(method, 900), allow_stale=True)
        if stale:
            restored = self._restore(stale[0], "stale")
            restored.provenance = result.provenance + restored.provenance + [SourceStatus("local-cache", "stale", message="主备数据源均失败，返回最近一次可核验快照")]
            restored.error = result.error
            return restored
        return result

    call = request

    def _annotate(self, result: DataResult, fields: list[str]):
        result.data_date = result.data_date or self._data_date(result.data)
        result.updated_at = datetime.now().isoformat(timespec="seconds")
        if not fields:
            result.completeness = 1.0 if result.ok else 0.0
            return
        rows = result.data if isinstance(result.data, list) else [result.data] if isinstance(result.data, dict) else []
        rows = [row for row in rows if isinstance(row, dict)]
        if not rows:
            result.missing_fields = {field: "所有数据源均未返回该字段" for field in fields}
            result.completeness = 0.0
            return
        present = 0
        result.missing_fields = {}
        for field in fields:
            available = sum(row.get(field) is not None for row in rows)
            present += available
            if available == 0:
                result.missing_fields[field] = "所有数据源均未返回该字段"
            elif available < len(rows):
                result.missing_fields[field] = f"{len(rows) - available}/{len(rows)} 条记录缺失该字段"
        result.completeness = round(present / (len(rows) * len(fields)), 4)

    def _restore(self, payload: dict[str, Any], cache_status: str) -> DataResult:
        result = DataResult(payload.get("ok", False), payload.get("data"), [SourceStatus(**item) for item in payload.get("provenance", [])], payload.get("error"), payload.get("completeness"), payload.get("missing_fields") or {}, payload.get("data_date"), payload.get("updated_at") or datetime.now().isoformat(timespec="seconds"), cache_status)
        return result

    @staticmethod
    def _merge_incremental(result: DataResult, payload: dict[str, Any]):
        previous = payload.get("data") or []
        if not isinstance(previous, list) or not isinstance(result.data, list):
            return
        def row_key(row):
            return (row.get("symbol"), row.get("trade_date") or row.get("date") or row.get("as_of"))
        merged = {row_key(row): row for row in previous if isinstance(row, dict)}
        merged.update({row_key(row): row for row in result.data if isinstance(row, dict)})
        result.data = sorted(merged.values(), key=lambda row: str(row.get("trade_date") or row.get("date") or row.get("as_of") or ""))
        result.cache_status = "incremental"

    @staticmethod
    def _data_date(data):
        if isinstance(data, list):
            dates = [str(row.get("trade_date") or row.get("as_of") or row.get("date")) for row in data if isinstance(row, dict) and (row.get("trade_date") or row.get("as_of") or row.get("date"))]
            return max(dates) if dates else None
        if isinstance(data, dict):
            return data.get("as_of") or data.get("trade_date") or data.get("date")
        return None

    def __getattr__(self, method):
        if not method.startswith("get_"):
            raise AttributeError(method)
        return lambda *args, **kwargs: self.request(method, *args, **kwargs)

    def status(self):
        return self.registry.status()


data_provider = DataProvider()
