"""Deterministic strategy diagnostics."""
from __future__ import annotations


def diagnose_backtest(result: dict) -> dict:
    metrics = result.get("metrics", {})
    trades = result.get("trades", [])
    checks = []

    def add(name, score, severity, message):
        checks.append({"name": name, "score": score, "severity": severity, "message": message})

    trade_count = len(trades)
    add("样本量", 100 if trade_count >= 30 else 45, "major" if trade_count < 30 else "info", f"成交记录 {trade_count} 笔。")
    costs = metrics.get("total_cost", 0)
    final_equity = result.get("final_equity") or 1
    cost_ratio = costs / final_equity
    add("成本鲁棒性", 40 if cost_ratio > 0.03 else 82, "major" if cost_ratio > 0.03 else "info", f"交易成本占期末权益 {cost_ratio:.2%}。")
    max_dd = abs(metrics.get("max_drawdown", 0))
    add("回撤风险", 45 if max_dd > 25 else 80, "major" if max_dd > 25 else "info", f"最大回撤 {metrics.get('max_drawdown', 0)}%。")
    symbols = {}
    for trade in trades:
        symbols[trade["symbol"]] = symbols.get(trade["symbol"], 0) + trade.get("pnl", 0)
    if symbols:
        total_abs = sum(abs(v) for v in symbols.values()) or 1
        concentration = max(abs(v) for v in symbols.values()) / total_abs
    else:
        concentration = 0
    add("收益分散度", 38 if concentration > 0.6 else 78, "major" if concentration > 0.6 else "info", f"最大单一股票收益贡献占比 {concentration:.1%}。")
    add("未来函数审查", 75, "info", "当前执行仅使用调仓日及以前数据，但尚未审计未来财务数据。")
    add("交易限制覆盖", 62, "minor", "已处理整手、T+1、手续费、印花税、过户费、滑点；停牌、涨跌停、退市和分红送转仍显示为限制。")

    score = round(sum(item["score"] for item in checks) / len(checks)) if checks else 0
    return {
        "credibility_score": score,
        "dimensions": {
            "data_credibility": 70,
            "backtest_credibility": 68,
            "parameter_stability": 55,
            "cost_robustness": next(item["score"] for item in checks if item["name"] == "成本鲁棒性"),
            "market_adaptability": 55,
            "return_dispersion": next(item["score"] for item in checks if item["name"] == "收益分散度"),
        },
        "checks": checks,
        "main_risks": [item["message"] for item in checks if item["severity"] in {"major", "critical"}],
    }

