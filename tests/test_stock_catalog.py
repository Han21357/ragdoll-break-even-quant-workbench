from app.services.data.models import DataResult, SourceStatus
from app.services.stocks import catalog


def _result():
    return DataResult(
        True,
        [
            {"symbol": "600519", "name": "贵州茅台", "source": "test-catalog"},
            {"symbol": "300750", "name": "宁德时代", "source": "test-catalog"},
            {"symbol": "601318", "name": "中国平安", "source": "test-catalog"},
            {"symbol": "605208", "name": "永茂泰", "source": "test-catalog"},
        ],
        [SourceStatus("test-catalog", "ok", as_of="2026-07-21")],
        data_date="2026-07-21",
    )


def test_catalog_supports_code_name_pinyin_and_initials(monkeypatch):
    monkeypatch.setattr(catalog, "_rows", [])
    monkeypatch.setattr(catalog.data_provider, "request", lambda *args, **kwargs: _result())
    catalog.warm_stock_catalog(force=True)
    assert catalog.search_stocks("6005")[0]["name"] == "贵州茅台"
    assert catalog.search_stocks("茅台")[0]["code"] == "600519"
    assert "600519" in {item["code"] for item in catalog.search_stocks("maotai")}
    assert catalog.search_stocks("gzmt")[0]["code"] == "600519"


def test_catalog_enriches_code_only_import(monkeypatch):
    monkeypatch.setattr(catalog, "_rows", [])
    monkeypatch.setattr(catalog.data_provider, "request", lambda *args, **kwargs: _result())
    rows = catalog.enrich_stock_rows([{"symbol": "300750", "quantity": 100, "cost_price": 200}])
    assert rows[0]["name"] == "宁德时代"
    assert rows[0]["market"] == "SZ"
    assert rows[0]["identity_status"] == "matched"
