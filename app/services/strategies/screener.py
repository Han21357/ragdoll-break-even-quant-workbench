"""Strategy screening funnel with per-stock explanations."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from app.schemas.strategy import Condition, ConditionGroup, StrategyDSL
from app.services.data.registry import registry
from app.services.factors.calculator import latest_factor_snapshot
from app.services.strategies.validator import validate_strategy_payload


def run_screening(strategy_payload: dict, symbols: list[str] | None = None) -> dict:
    validation = validate_strategy_payload(strategy_payload, require_available=True)
    if not validation["ok"]:
        return {"ok": False, "error": "策略未通过校验", "details": validation["errors"]}
    dsl = StrategyDSL.model_validate(strategy_payload)
    if not symbols:
        stock_list = registry.call("get_stock_list")
        if not stock_list.ok:
            return {"ok": False, "error": "股票池不可用", "provenance": [p.__dict__ for p in stock_list.provenance]}
        symbols = [row["symbol"] for row in stock_list.data[:200]]

    end = datetime.now().date()
    start = end - timedelta(days=140)
    snapshots: list[dict] = []
    provenance = []
    failures = []
    for symbol in symbols:
        daily = registry.call("get_stock_daily", symbol, start.isoformat(), end.isoformat(), dsl.price_adjustment)
        provenance.extend(daily.provenance)
        if not daily.ok:
            failures.append({"symbol": symbol, "reason": daily.error, "provenance": [p.__dict__ for p in daily.provenance]})
            continue
        snapshot = latest_factor_snapshot(symbol, daily.data)
        snapshot["_source"] = daily.data[-1].get("source")
        snapshot["_as_of"] = daily.data[-1].get("as_of")
        snapshots.append(snapshot)
    if not snapshots:
        return {"ok": False, "error": "没有任何股票取得可计算日线数据", "failures": failures, "provenance": [p.__dict__ for p in provenance]}

    remaining = snapshots
    funnel = [{"label": f"A股初始股票池：{len(snapshots)}只", "count": len(snapshots)}]
    explanations = {row["symbol"]: {"passed": [], "failed": [], "factor_values": {}} for row in snapshots}
    for condition in _flatten_conditions(dsl.entry_conditions):
        if not condition.enabled:
            continue
        passed = []
        for row in remaining:
            ok, actual = _evaluate(row, condition, snapshots)
            explanations[row["symbol"]]["factor_values"][condition.factor] = _json_value(actual)
            target = {
                "factor": condition.factor,
                "operator": condition.operator,
                "threshold": condition.value,
                "actual": _json_value(actual),
                "data_date": row.get("_as_of"),
                "source": row.get("_source"),
            }
            if ok:
                explanations[row["symbol"]]["passed"].append(target)
                passed.append(row)
            else:
                explanations[row["symbol"]]["failed"].append(target)
        remaining = passed
        funnel.append({"label": f"{condition.factor} {condition.operator} {condition.value}", "count": len(remaining)})

    ranked = remaining[: int(dsl.portfolio.get("max_positions", 20))]
    results = []
    for rank, row in enumerate(ranked, start=1):
        results.append({
            "symbol": row["symbol"],
            "name": row.get("name"),
            "rank": rank,
            "close": _json_value(row.get("close")),
            "as_of": row.get("_as_of"),
            "source": row.get("_source"),
            "explanation": explanations[row["symbol"]],
        })
    funnel.append({"label": f"最终排序后保留：{len(results)}只", "count": len(results)})
    return {
        "ok": True,
        "funnel": funnel,
        "results": results,
        "excluded_count": len(snapshots) - len(results),
        "failures": failures[:20],
        "provenance": [p.__dict__ for p in provenance[-10:]],
    }


def _flatten_conditions(group: ConditionGroup) -> list[Condition]:
    items: list[Condition] = []
    for child in group.conditions:
        if isinstance(child, ConditionGroup):
            items.extend(_flatten_conditions(child))
        else:
            items.append(child)
    return items


def _evaluate(row: dict, condition: Condition, universe: list[dict]) -> tuple[bool, Any]:
    value = row.get(condition.factor)
    if pd.isna(value):
        return False, None
    op = condition.operator
    target = condition.value
    if op == ">":
        return value > target, value
    if op == ">=":
        return value >= target, value
    if op == "<":
        return value < target, value
    if op == "<=":
        return value <= target, value
    if op == "==":
        return value == target, value
    if op == "between":
        low, high = target
        return low <= value <= high, value
    if op in {"top_percentile", "bottom_percentile"}:
        series = [item.get(condition.factor) for item in universe if item.get(condition.factor) is not None and not pd.isna(item.get(condition.factor))]
        if not series:
            return False, value
        pct = pd.Series(series).rank(pct=True).iloc[series.index(value)] * 100 if value in series else 0
        return (pct >= 100 - float(target)) if op == "top_percentile" else (pct <= float(target)), value
    return False, value


def _json_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6)
    return value

