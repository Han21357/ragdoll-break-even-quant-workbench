import pandas as pd

from app.services.data.cache import cache
from app.services.data.providers.akshare_provider import AKShareProvider


class FakeAKShare:
    @staticmethod
    def stock_zh_a_daily(**kwargs):
        assert kwargs["symbol"] == "sh600519"
        return pd.DataFrame([
            {"date": "2026-07-16", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100, "amount": 1000},
            {"date": "2026-07-17", "open": 10, "high": 12, "low": 10, "close": 11, "volume": 120, "amount": 1200},
        ])

    @staticmethod
    def stock_zh_a_hist(**kwargs):
        raise AssertionError("eastmoney daily fallback should not run when Sina succeeds")

    @staticmethod
    def stock_zh_a_spot_em():
        raise ConnectionError("eastmoney disconnected")

    @staticmethod
    def stock_zh_a_spot():
        return pd.DataFrame([
            {"代码": "sh600519", "名称": "贵州茅台", "最新价": 1500, "涨跌幅": 1.5, "成交额": 100},
            {"代码": "sz300750", "名称": "宁德时代", "最新价": 300, "涨跌幅": -2.0, "成交额": 200},
        ])

    @staticmethod
    def stock_sector_spot(indicator):
        assert indicator == "新浪行业"
        return pd.DataFrame([
            {"板块": "银行", "涨跌幅": -1.2, "公司家数": 42, "总成交额": 1000, "股票名称": "招商银行", "股票代码": "sh600036", "个股-涨跌幅": 0.5},
            {"板块": "半导体", "涨跌幅": 2.4, "公司家数": 88, "总成交额": 2000, "股票名称": "中芯国际", "股票代码": "sh688981", "个股-涨跌幅": 3.1},
        ])


def _provider(monkeypatch):
    cache._items.clear()
    provider = AKShareProvider()
    monkeypatch.setattr(provider, "_ak", lambda: FakeAKShare())
    monkeypatch.setattr(provider, "_load_disk_snapshot", lambda: None)
    monkeypatch.setattr(provider, "_save_disk_snapshot", lambda result: None)
    return provider


def test_sina_snapshot_fallback_keeps_failed_source_provenance(monkeypatch):
    result = _provider(monkeypatch).get_basic_factors()
    assert result.ok is True
    assert len(result.data) == 2
    assert result.data[0]["symbol"] == "600519"
    assert result.data[0]["source"] == "akshare:sina"
    assert [(item.source, item.status) for item in result.provenance] == [("akshare:sina", "ok")]


def test_market_snapshot_uses_sina_breadth(monkeypatch):
    result = _provider(monkeypatch).get_market_snapshot()
    assert result.ok is True
    assert result.data["total"] == 2
    assert result.data["up_count"] == 1
    assert result.data["down_count"] == 1
    assert result.data["amount"] == 300
    assert result.data["source"] == "akshare:sina"


def test_sector_snapshot_is_ranked(monkeypatch):
    result = _provider(monkeypatch).get_sector_snapshot()
    assert result.ok is True
    assert [item["name"] for item in result.data] == ["半导体", "银行"]
    assert result.data[0]["leader"] == "中芯国际"


def test_stock_daily_prefers_sina(monkeypatch):
    result = _provider(monkeypatch).get_stock_daily("600519", "2026-07-01", "2026-07-18", "none")
    assert result.ok is True
    assert result.data[-1]["close"] == 11
    assert result.data[-1]["source"] == "akshare:sina"
    assert result.provenance[0].source == "akshare:sina"
