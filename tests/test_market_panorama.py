from app.services.data.models import DataResult, SourceStatus
from app.services.market.panorama import build_breadth, build_market_panorama, normalize_index_series


def test_breadth_buckets_ratio_and_flat_count():
    rows = [
        {"pct_change": 6, "amount": 10, "as_of": "2026-07-18"},
        {"pct_change": 3, "amount": 20, "as_of": "2026-07-18"},
        {"pct_change": 1, "amount": 30, "as_of": "2026-07-18"},
        {"pct_change": 0, "amount": 40, "as_of": "2026-07-18"},
        {"pct_change": -1, "amount": 50, "as_of": "2026-07-18"},
        {"pct_change": -3, "amount": 60, "as_of": "2026-07-18"},
        {"pct_change": -6, "amount": 70, "as_of": "2026-07-18"},
    ]
    breadth = build_breadth(rows)
    assert breadth["up_count"] == 3
    assert breadth["down_count"] == 3
    assert breadth["flat_count"] == 1
    assert breadth["up_ratio"] == round(3 / 7, 4)
    assert breadth["median_change"] == 0
    assert [item["count"] for item in breadth["buckets"]] == [1, 1, 1, 1, 1, 1, 1]


def test_index_normalization_uses_first_close_without_fake_curve():
    rows = [
        {"trade_date": "2026-07-01", "close": 10, "source": "akshare"},
        {"trade_date": "2026-07-02", "close": 11, "source": "akshare"},
        {"trade_date": "2026-07-03", "close": 9, "source": "akshare"},
    ]
    series = normalize_index_series(rows)
    assert [item["normalized"] for item in series] == [100, 110, 90]
    assert series[1]["pct_change"] == 10
    assert round(series[2]["pct_change"], 4) == -18.1818
    assert all("random" not in item for item in series)


def test_empty_breadth_does_not_invent_counts():
    breadth = build_breadth([{"pct_change": None}, {"pct_change": "-"}])
    assert breadth["status"] == "empty"
    assert breadth["total"] == 0
    assert all(item["count"] == 0 for item in breadth["buckets"])


class PanoramaRegistry:
    def __init__(self, fail_snapshot=False):
        self.fail_snapshot = fail_snapshot

    def call(self, method, *args, **kwargs):
        if method == "get_basic_factors":
            if self.fail_snapshot:
                return DataResult(False, [], [SourceStatus("akshare", "unavailable", message="boom")], "boom")
            return DataResult(True, [
                {"pct_change": 2, "amount": 100, "as_of": "2026-07-18"},
                {"pct_change": -1, "amount": 200, "as_of": "2026-07-18"},
                {"pct_change": 0, "amount": 300, "as_of": "2026-07-18"},
            ], [SourceStatus("akshare", "ok", as_of="2026-07-18")])
        if method == "get_market_snapshot":
            return DataResult(True, {
                "total": 3,
                "up_count": 1,
                "down_count": 1,
                "amount": 600,
                "as_of": "2026-07-18",
            }, [SourceStatus("baostock", "partial", as_of="2026-07-18")])
        if method == "get_index_daily":
            return DataResult(True, [
                {"trade_date": "2026-07-01", "close": 100, "source": "baostock"},
                {"trade_date": "2026-07-02", "close": 101, "source": "baostock"},
            ], [SourceStatus("baostock", "ok", as_of="2026-07-02")])
        if method == "get_sector_snapshot":
            return DataResult(True, [
                {"name": "半导体", "change_pct": 3.2, "source": "akshare:sina-sector"},
            ], [SourceStatus("akshare:sina-sector", "ok", as_of="2026-07-18")])
        raise AssertionError(method)


def test_panorama_keeps_provenance_and_partial_fallback():
    data = build_market_panorama(PanoramaRegistry(fail_snapshot=True))
    assert data["status"] == "partial"
    assert data["breadth"]["status"] == "partial"
    assert data["breadth"]["up_ratio"] == round(1 / 3, 4)
    assert {"akshare", "baostock", "akshare:sina-sector"} <= {item["source"] for item in data["provenance"]}
    assert data["limitations"]


def test_panorama_full_data_shape():
    data = build_market_panorama(PanoramaRegistry())
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert len(data["indices"]) == 4
    assert data["indices"][0]["series"][0]["normalized"] == 100
    assert data["breadth"]["flat_count"] == 1
    assert data["sectors"][0]["name"] == "半导体"
