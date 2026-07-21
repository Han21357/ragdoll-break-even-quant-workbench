from app.services.data.models import DataResult, SourceStatus
from app.services.data.service import DataProvider


class FakeRegistry:
    providers = []

    def call(self, method, *args, **kwargs):
        return DataResult(True, [{"trade_date": "2026-07-20", "close": 10, "industry": None}], [SourceStatus("fake-primary", "ok", as_of="2026-07-20")])

    def status(self):
        return {"status": "ok", "checks": {}}


class FailingRegistry:
    providers = []

    def call(self, method, *args, **kwargs):
        return DataResult(False, [], [SourceStatus("failed-primary", "unavailable", message="upstream offline")], "upstream offline")


def test_data_provider_reports_completeness_and_missing_reason(monkeypatch):
    provider = DataProvider(FakeRegistry())
    monkeypatch.setattr("app.services.data.service.persistent_cache.get", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.data.service.persistent_cache.set", lambda *args, **kwargs: None)
    result = provider.request("get_stock_daily", "600519", required_fields=["trade_date", "close", "industry"])
    assert result.ok
    assert result.data_date == "2026-07-20"
    assert result.completeness == 0.6667
    assert result.missing_fields == {"industry": "所有数据源均未返回该字段"}


def test_data_provider_returns_stale_cache_when_all_sources_fail(monkeypatch):
    payload = {
        "ok": True,
        "data": [{"trade_date": "2026-07-18", "close": 10.5}],
        "provenance": [{"source": "cached-source", "status": "ok", "as_of": "2026-07-18", "fetched_at": "2026-07-18T16:00:00", "message": None, "latency_ms": 42}],
        "completeness": 1.0,
        "missing_fields": {},
        "data_date": "2026-07-18",
        "updated_at": "2026-07-18T16:00:00",
        "cache_status": "miss",
    }
    calls = iter([None, (payload, "stale", 1)])
    monkeypatch.setattr("app.services.data.service.persistent_cache.get", lambda *args, **kwargs: next(calls))
    result = DataProvider(FailingRegistry()).request("get_stock_daily", "600519", "2026-07-01", "2026-07-20", "qfq", required_fields=["trade_date", "close"])
    assert result.ok
    assert result.cache_status == "stale"
    assert result.error == "upstream offline"
    assert result.provenance[-1].source == "local-cache"
    assert result.provenance[-1].status == "stale"
