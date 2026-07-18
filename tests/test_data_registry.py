from app.services.data.base import MarketDataProvider
from app.services.data.models import DataResult, SourceStatus
from app.services.data.registry import ProviderRegistry


class FailingProvider(MarketDataProvider):
    name = "akshare"

    def get_stock_list(self):
        return DataResult(False, [], [SourceStatus("akshare", "unavailable", message="boom")], "boom")

    def get_stock_daily(self, symbol, start_date, end_date, adjustment="qfq"):
        return DataResult(False, [], [SourceStatus("akshare", "unavailable", message="boom")], "boom")


class WorkingProvider(MarketDataProvider):
    name = "baostock"

    def get_stock_list(self):
        return DataResult(True, [{"symbol": "600519", "source": "baostock"}], [SourceStatus("baostock", "ok")])

    def get_stock_daily(self, symbol, start_date, end_date, adjustment="qfq"):
        return DataResult(True, [{"symbol": symbol, "trade_date": start_date, "close": 10, "source": "baostock", "as_of": start_date, "status": "ok"}], [SourceStatus("baostock", "ok")])


def test_registry_falls_back_and_keeps_provenance():
    registry = ProviderRegistry([FailingProvider(), WorkingProvider()])
    result = registry.call("get_stock_list")
    assert result.ok is True
    assert result.data[0]["source"] == "baostock"
    assert [p.source for p in result.provenance] == ["akshare", "baostock"]


def test_registry_does_not_treat_failure_as_empty():
    registry = ProviderRegistry([FailingProvider()])
    result = registry.call("get_stock_list")
    assert result.ok is False
    assert result.error
    assert result.data == []

