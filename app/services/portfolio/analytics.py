"""Portfolio metrics calculated only from verified holdings and adjusted prices."""
from __future__ import annotations

from datetime import date, timedelta
from math import sqrt
from statistics import pstdev

from app.services.data.service import data_provider


def build_portfolio_analytics(holdings: list[dict], window_days: int = 180) -> dict:
    if not holdings:
        return {"ok": False, "metrics": {}, "curve": [], "exposures": [], "missing_fields": {"holdings": "当前没有持仓，无法计算组合指标"}, "evidence": []}
    end = date.today()
    start = end - timedelta(days=window_days * 2)
    histories = {}
    evidence = []
    missing = {}
    profiles = {}
    for holding in holdings:
        symbol = str(holding.get("code") or holding.get("symbol") or "")
        daily = data_provider.request("get_stock_daily", symbol, start.isoformat(), end.isoformat(), "qfq", required_fields=["trade_date", "close"])
        evidence.append({"field": f"price:{symbol}", **daily.meta()})
        if daily.ok and daily.data:
            histories[symbol] = {row["trade_date"]: row["close"] for row in daily.data if row.get("close") is not None}
        else:
            missing[f"price:{symbol}"] = daily.error or "复权历史行情不可用"
        profile = data_provider.request("get_stock_profile", symbol, required_fields=["industry"])
        evidence.append({"field": f"industry:{symbol}", **profile.meta()})
        if profile.ok:
            profiles[symbol] = profile.data
        else:
            recorded_sector = holding.get("sector")
            if recorded_sector and recorded_sector not in {"其他", "未知", ""}:
                profiles[symbol] = {"industry": recorded_sector, "source": "user-holding-record"}
                evidence.append({"field": f"industry:{symbol}", "ok": True, "data_date": holding.get("created_at"), "updated_at": holding.get("created_at"), "completeness": 1.0, "missing_fields": {}, "cache_status": "user_record", "error": None, "sources": [{"source": "user-holding-record", "status": "ok", "as_of": holding.get("created_at"), "message": "第三方行业资料失败，使用用户持仓中保存的行业标签"}]})
            else:
                missing[f"industry:{symbol}"] = profile.error or "行业信息不可用"
    dates = sorted(set.intersection(*(set(rows) for rows in histories.values()))) if len(histories) == len(holdings) and histories else []
    quantities = {str(h.get("code") or h.get("symbol")): float(h.get("shares") or 0) for h in holdings}
    curve = []
    for day in dates[-window_days:]:
        value = sum(histories[symbol][day] * quantities[symbol] for symbol in histories)
        curve.append({"date": day, "value": round(value, 2)})
    returns = [(curve[i]["value"] / curve[i-1]["value"] - 1) for i in range(1, len(curve)) if curve[i-1]["value"]]
    max_drawdown = None
    if curve:
        peak = curve[0]["value"]
        drawdowns = []
        for point in curve:
            peak = max(peak, point["value"])
            drawdowns.append(point["value"] / peak - 1 if peak else 0)
        max_drawdown = min(drawdowns) * 100
    latest_value = curve[-1]["value"] if curve else None
    costs = sum(float(h.get("cost") or 0) * float(h.get("shares") or 0) for h in holdings)
    industry_values = {}
    stock_exposure = []
    if latest_value:
        for holding in holdings:
            symbol = str(holding.get("code") or holding.get("symbol"))
            value = histories.get(symbol, {}).get(curve[-1]["date"], 0) * quantities.get(symbol, 0)
            industry = (profiles.get(symbol) or {}).get("industry")
            stock_exposure.append({"symbol": symbol, "name": holding.get("name"), "weight": round(value / latest_value, 4), "industry": industry})
            if industry:
                industry_values[industry] = industry_values.get(industry, 0) + value
    industry_exposure = [{"industry": key, "weight": round(value / latest_value, 4)} for key, value in sorted(industry_values.items(), key=lambda item: item[1], reverse=True)] if latest_value else []
    industry_hhi = sum(item["weight"] ** 2 for item in industry_exposure) if industry_exposure else None
    top3_industry = sum(item["weight"] for item in industry_exposure[:3]) if industry_exposure else None
    metrics = {
        "market_value": latest_value,
        "cumulative_return_pct": round((latest_value / costs - 1) * 100, 4) if latest_value is not None and costs > 0 else None,
        "today_return_pct": round(returns[-1] * 100, 4) if returns else None,
        "max_drawdown_pct": round(max_drawdown, 4) if max_drawdown is not None else None,
        "annualized_volatility_pct": round(pstdev(returns) * sqrt(252) * 100, 4) if len(returns) >= 10 else None,
        "position_pct": None,
        "industry_concentration_pct": round(max((item["weight"] for item in industry_exposure), default=0) * 100, 4) if len(profiles) == len(holdings) and industry_exposure else None,
        "industry_hhi": round(industry_hhi, 4) if len(profiles) == len(holdings) and industry_hhi is not None else None,
        "top3_industry_exposure_pct": round(top3_industry * 100, 4) if len(profiles) == len(holdings) and top3_industry is not None else None,
        "max_single_exposure_pct": round(max((item["weight"] for item in stock_exposure), default=0) * 100, 4) if stock_exposure else None,
        "beta": None,
        "style_exposure": None,
    }
    if len(curve) < 10:
        missing["annualized_volatility_pct"] = "共同有效复权价格不足10个交易日"
    if not industry_exposure:
        missing["industry_concentration_pct"] = "持仓行业信息主备源均不可用"
    elif len(profiles) != len(holdings):
        missing["industry_concentration_pct"] = "部分持仓缺少行业信息，不能把已知部分当作完整集中度"
    missing["position_pct"] = "持仓记录没有现金余额或账户总资产，不能可靠计算仓位"
    missing["beta"] = "尚未取得与组合日期完全对齐的沪深300复权收益序列"
    missing["style_exposure"] = "当前数据源未返回可复现的风格因子暴露"
    completeness = round(sum(value is not None for value in metrics.values()) / len(metrics) * 100, 1)
    return {"ok": bool(curve), "metrics": metrics, "curve": curve, "stock_exposure": stock_exposure, "industry_exposure": industry_exposure, "missing_fields": missing, "evidence": evidence, "as_of": curve[-1]["date"] if curve else None, "updated_at": date.today().isoformat(), "data_completeness_pct": completeness, "methodology": "以当前持股数量对历史前复权收盘价做静态持仓回溯；若期间发生过交易，需要接入成交记录后重建真实净值。"}
