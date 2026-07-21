"""Build the real market panorama used by the workbench home page."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import median, pstdev
from typing import Any

from app.services.data.models import DataResult, SourceStatus
from app.services.data.service import data_provider as default_registry
from config import CACHE_DIR

PANORAMA_CACHE_FILE = CACHE_DIR / "market_panorama.json"
PANORAMA_DISK_TTL = 12 * 3600
PANORAMA_SCHEMA_VERSION = 3
SECTOR_HISTORY_FILE = CACHE_DIR / "sector_history.json"

INDEX_SPECS = [
    {"id": "sh", "symbol": "sh000001", "name": "上证指数"},
    {"id": "sz", "symbol": "sz399001", "name": "深证成指"},
    {"id": "cy", "symbol": "sz399006", "name": "创业板指"},
    {"id": "hs300", "symbol": "sh000300", "name": "沪深300"},
]

BUCKETS = [
    ("≥+5%", lambda value: value >= 5),
    ("+2%～+5%", lambda value: 2 <= value < 5),
    ("0%～+2%", lambda value: 0 < value < 2),
    ("平盘", lambda value: value == 0),
    ("-2%～0%", lambda value: -2 < value < 0),
    ("-5%～-2%", lambda value: -5 < value <= -2),
    ("≤-5%", lambda value: value <= -5),
]


def build_market_panorama(registry=default_registry, window: int = 40) -> dict[str, Any]:
    """Return a partial-friendly market panorama without generating invented values."""
    if registry is default_registry:
        cached = _load_cached_panorama()
        if cached is not None:
            return cached
    provenance: list[dict[str, Any]] = []
    limitations: list[str] = []
    today = date.today()
    start = (today - timedelta(days=120)).isoformat()
    end = today.isoformat()

    breadth = None
    snapshot = registry.call("get_basic_factors")
    provenance.extend(_as_dicts(snapshot.provenance))
    if snapshot.ok and isinstance(snapshot.data, list):
        breadth = build_breadth(snapshot.data)
    else:
        limitations.append("全市场实时涨跌结构不可用，未使用估算数据填充。")
        fallback = registry.call("get_market_snapshot")
        provenance.extend(_as_dicts(fallback.provenance))
        if fallback.ok and isinstance(fallback.data, dict):
            breadth = partial_breadth(fallback.data)

    indices = []
    for spec in INDEX_SPECS:
        result = registry.call("get_index_daily", spec["symbol"], start, end, "none")
        provenance.extend(_as_dicts(result.provenance))
        if result.ok and _valid_index_rows(result.data):
            indices.append(build_index_item(spec, result.data, window))
        else:
            indices.append({
                **spec,
                "status": "unavailable",
                "error": result.error,
                "source": None,
                "as_of": None,
                "series": [],
            })

    sectors = []
    sector_result = registry.call("get_sector_snapshot")
    provenance.extend(_as_dicts(sector_result.provenance))
    if sector_result.ok and isinstance(sector_result.data, list):
        sectors = enrich_sector_persistence(sector_result.data)[:8]
    else:
        limitations.append("行业板块快照不可用。")

    ok_indices = [item for item in indices if item.get("status") == "ok"]
    as_of_values = [item.get("as_of") for item in ok_indices if item.get("as_of")]
    status = "ok" if ok_indices and breadth and breadth.get("status") == "ok" else ("partial" if ok_indices or breadth else "error")
    if not ok_indices:
        limitations.append("四大指数历史序列不可用，走势图为空。")

    regime = build_regime(breadth)
    result = {
        "ok": status != "error",
        "schema_version": PANORAMA_SCHEMA_VERSION,
        "status": status,
        "as_of": max(as_of_values) if as_of_values else (breadth or {}).get("as_of"),
        "refreshing": False,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "indices": indices,
        "breadth": breadth or empty_breadth("unavailable"),
        "regime": regime,
        "sectors": sectors,
        "provenance": provenance,
        "limitations": limitations,
        "missing_fields": _market_missing_fields(breadth, indices, sectors),
        "completeness": _market_completeness(breadth, indices, sectors),
    }
    if registry is default_registry and result["ok"]:
        _save_cached_panorama(result)
    return result


def _valid_index_rows(rows: Any) -> bool:
    """Reject a stock series accidentally returned for an ambiguous index code."""
    if not isinstance(rows, list) or not rows:
        return False
    closes = [row.get("close") for row in rows if isinstance(row, dict) and row.get("close") is not None]
    return bool(closes) and float(closes[-1]) >= 100


def _load_cached_panorama() -> dict[str, Any] | None:
    try:
        if time.time() - PANORAMA_CACHE_FILE.stat().st_mtime > PANORAMA_DISK_TTL:
            return None
        payload = json.loads(PANORAMA_CACHE_FILE.read_text())
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not data.get("ok") or data.get("schema_version") != PANORAMA_SCHEMA_VERSION:
            return None
        data = dict(data)
        data["cache"] = {"status": "local", "saved_at": payload.get("saved_at")}
        return data
    except (OSError, AttributeError, TypeError, json.JSONDecodeError):
        return None


def _save_cached_panorama(data: dict[str, Any]) -> None:
    try:
        PANORAMA_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_path = PANORAMA_CACHE_FILE.with_suffix(".tmp")
        temp_path.write_text(json.dumps({"saved_at": time.time(), "data": data}, ensure_ascii=False))
        temp_path.replace(PANORAMA_CACHE_FILE)
    except OSError:
        pass


def build_breadth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = []
    amount = 0.0
    as_of_values = []
    for row in rows:
        pct = _number(row.get("pct_change"))
        if pct is None:
            continue
        values.append(round(pct, 4))
        amount += _number(row.get("amount")) or 0
        if row.get("as_of"):
            as_of_values.append(str(row["as_of"]))
    if not values:
        return empty_breadth("empty")

    up = sum(1 for value in values if value > 0)
    down = sum(1 for value in values if value < 0)
    flat = sum(1 for value in values if value == 0)
    total = len(values)
    buckets = [{"label": label, "count": sum(1 for value in values if predicate(value))} for label, predicate in BUCKETS]
    return {
        "status": "ok",
        "total": total,
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "up_ratio": round(up / total, 4),
        "median_change": round(median(values), 4),
        "amount": round(amount, 2),
        "buckets": buckets,
        "as_of": max(as_of_values) if as_of_values else date.today().isoformat(),
    }


def partial_breadth(data: dict[str, Any]) -> dict[str, Any]:
    total = _number(data.get("total"))
    up = _number(data.get("up_count"))
    down = _number(data.get("down_count"))
    flat = max(total - (up or 0) - (down or 0), 0) if total is not None and up is not None and down is not None else None
    return {
        "status": "partial",
        "total": total,
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "up_ratio": round(up / total, 4) if total and up is not None else None,
        "median_change": None,
        "amount": _number(data.get("amount")),
        "buckets": [{"label": label, "count": None} for label, _ in BUCKETS],
        "as_of": data.get("as_of"),
    }


def empty_breadth(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "total": None,
        "up_count": None,
        "down_count": None,
        "flat_count": None,
        "up_ratio": None,
        "median_change": None,
        "amount": None,
        "buckets": [{"label": label, "count": None} for label, _ in BUCKETS],
        "as_of": None,
    }


def build_index_item(spec: dict[str, str], rows: list[dict[str, Any]], window: int) -> dict[str, Any]:
    history = normalize_index_series(rows, max(window, 80))
    if not history:
        return {**spec, "status": "empty", "source": None, "as_of": None, "series": []}
    latest = history[-1]
    returns = [item.get("pct_change") for item in history if item.get("pct_change") is not None]
    series = history[-window:]
    return {
        **spec,
        "status": "ok",
        "value": latest["close"],
        "change_pct": latest.get("pct_change"),
        "amount": latest.get("amount"),
        "as_of": latest["date"],
        "source": latest.get("source"),
        "series": series,
        "volatility_20d": _annualized_volatility(returns[-20:]),
        "volatility_60d": _annualized_volatility(returns[-60:]),
    }


def normalize_index_series(rows: list[dict[str, Any]], window: int = 40) -> list[dict[str, Any]]:
    cleaned = []
    for row in rows:
        close = _number(row.get("close"))
        if close is None or close <= 0 or not row.get("trade_date"):
            continue
        cleaned.append({
            "date": str(row["trade_date"]),
            "close": round(close, 4),
            "pct_change": _number(row.get("pct_change")),
            "amount": _number(row.get("amount")),
            "source": row.get("source"),
        })
    cleaned.sort(key=lambda item: item["date"])
    cleaned = cleaned[-window:]
    if not cleaned:
        return []
    for index, item in enumerate(cleaned):
        if item.get("pct_change") is None and index > 0 and cleaned[index - 1]["close"]:
            item["pct_change"] = round((item["close"] / cleaned[index - 1]["close"] - 1) * 100, 4)
    first = cleaned[0]["close"]
    for item in cleaned:
        item["normalized"] = round(item["close"] / first * 100, 4)
    return cleaned


def build_regime(breadth: dict[str, Any] | None) -> dict[str, Any]:
    if not breadth or breadth.get("up_ratio") is None:
        return {
            "label": "待确认",
            "trend": "待确认",
            "breadth": "待确认",
            "risk_appetite": "待确认",
            "money_flow_score": None,
            "rotation": {},
            "method": "市场宽度不可用时不生成环境判断。",
        }
    ratio = breadth["up_ratio"]
    trend = "强" if ratio >= 0.58 else ("弱" if ratio <= 0.42 else "震荡")
    width = "宽" if ratio >= 0.58 else ("窄" if ratio <= 0.42 else "中")
    risk = "偏强" if ratio >= 0.55 else ("偏弱" if ratio <= 0.45 else "中性")
    return {
        "label": f"风险偏好{risk}" if risk != "中性" else "中性",
        "trend": trend,
        "breadth": width,
        "risk_appetite": risk,
        "money_flow_score": None,
        "rotation": {},
        "method": "由全市场上涨比例确定性派生；不是LLM判断。",
    }


def _as_dicts(items: list[SourceStatus]) -> list[dict[str, Any]]:
    return [item.__dict__ for item in items]


def _number(value: Any) -> float | None:
    try:
        if value in ("", "-", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _annualized_volatility(values: list[float]) -> float | None:
    if len(values) < 10:
        return None
    return round(pstdev([value / 100 for value in values]) * sqrt(252) * 100, 4)


def enrich_sector_persistence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist one snapshot per date and calculate consecutive direction days."""
    today = max((str(row.get("as_of")) for row in rows if row.get("as_of")), default=date.today().isoformat())
    history = {}
    try:
        history = json.loads(SECTOR_HISTORY_FILE.read_text())
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    history[today] = {row.get("name"): _number(row.get("change_pct")) for row in rows if row.get("name")}
    history = dict(sorted(history.items())[-60:])
    try:
        SECTOR_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = SECTOR_HISTORY_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(history, ensure_ascii=False))
        temp.replace(SECTOR_HISTORY_FILE)
    except OSError:
        pass
    dates = sorted(history, reverse=True)
    enriched = []
    for raw in rows:
        item = dict(raw)
        current = _number(item.get("change_pct"))
        streak = 0
        if current is not None and current != 0:
            direction = 1 if current > 0 else -1
            for day in dates:
                value = _number(history[day].get(item.get("name")))
                if value is None or value == 0 or (1 if value > 0 else -1) != direction:
                    break
                streak += 1
        item["rotation_persistence_days"] = streak or None
        item["rotation_history_days"] = len(dates)
        enriched.append(item)
    return enriched


def _market_missing_fields(breadth, indices, sectors):
    missing = {}
    if not breadth or breadth.get("up_count") is None:
        missing["breadth"] = "AKShare 与 efinance 全市场快照均未返回有效涨跌数据"
    if not breadth or breadth.get("median_change") is None:
        missing["median_change"] = "主备快照未提供可计算的全A涨跌幅序列"
    if not breadth or breadth.get("amount") is None:
        missing["amount"] = "主备快照未提供可汇总成交额"
    if not any(item.get("volatility_20d") is not None for item in indices):
        missing["volatility_20d"] = "指数有效收益率样本不足10个交易日"
    if not any(item.get("volatility_60d") is not None for item in indices):
        missing["volatility_60d"] = "当前指数窗口不足60个交易日"
    if not sectors:
        missing["sectors"] = "AKShare 与东财行业板块接口均不可用"
    elif max((item.get("rotation_history_days") or 0 for item in sectors), default=0) < 2:
        missing["rotation_persistence"] = "本地板块日快照不足2日；将随每日增量更新自动形成"
    return missing


def _market_completeness(breadth, indices, sectors):
    expected = 8
    missing = _market_missing_fields(breadth, indices, sectors)
    return round((expected - len(missing)) / expected, 4)
