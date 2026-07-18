from datetime import date, timedelta

from app.services.backtest.engine import run_backtest
from app.services.data.models import DataResult, SourceStatus


def _daily(symbol, start="2025-01-01", days=45):
    base = date.fromisoformat(start)
    rows = []
    for i in range(days):
        trade_date = base + timedelta(days=i)
        close = 10 + i * 0.1
        rows.append({
            "symbol": symbol,
            "trade_date": trade_date.isoformat(),
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": 100000,
            "amount": 1000000,
            "turnover_rate": 1.0,
            "pct_change": 1.0,
            "adjustment": "qfq",
            "source": "test",
            "as_of": trade_date.isoformat(),
            "status": "ok",
        })
    return rows


def test_backtest_requires_real_stock_pool():
    result = run_backtest({"stocks": [], "start_date": "2025-01-01", "end_date": "2025-02-01"})
    assert result["ok"] is False
    assert "股票池" in result["error"]


def test_backtest_costs_lot_size_t1_and_hold_days(monkeypatch):
    from app.services.backtest import engine

    def fake_call(method, symbol, start, end, adjustment):
        return DataResult(True, _daily(symbol), [SourceStatus("test", "ok", as_of=end)])

    monkeypatch.setattr(engine.registry, "call", fake_call)
    result = run_backtest({
        "stocks": ["600519"],
        "start_date": "2025-01-01",
        "end_date": "2025-02-14",
        "initial_capital": 100000,
        "max_positions": 1,
        "hold_days": 10,
        "lot_size": 100,
        "sellable_after_days": 1,
        "commission_rate": 0.001,
        "min_commission": 5,
        "stamp_tax_rate": 0.001,
        "transfer_fee_rate": 0.00001,
        "slippage": 0.001,
    })
    assert result["ok"] is True
    assert result["metrics"]["total_cost"] > 0
    assert result["trades"]
    assert all(trade["shares"] % 100 == 0 for trade in result["trades"])
    assert all(trade["hold_days"] >= 1 for trade in result["trades"])
    assert result["metrics"]["max_drawdown"] <= 0
    assert result["diagnostics"]["credibility_score"] == result["diagnostics"]["credibility_score"]

