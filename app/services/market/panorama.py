"""Build the real market panorama used by the workbench home page."""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from statistics import median
from typing import Any

from app.services.data.models import DataResult, SourceStatus
from app.services.data.registry import registry as default_registry
from config import CACHE_DIR

PANORAMA_CACHE_FILE = CACHE_DIR / "market_panorama.json"
PANORAMA_DISK_TTL = 12 * 3600

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
        if result.ok:
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
        sectors = sector_result.data[:8]
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
        "status": status,
        "as_of": max(as_of_values) if as_of_values else (breadth or {}).get("as_of"),
        "refreshing": False,
        "indices": indices,
        "breadth": breadth or empty_breadth("unavailable"),
        "regime": regime,
        "sectors": sectors,
        "provenance": provenance,
        "limitations": limitations,
    }
    if registry is default_registry and result["ok"]:
        _save_cached_panorama(result)
    return result


def _load_cached_panorama() -> dict[str, Any] | None:
    try:
        if time.time() - PANORAMA_CACHE_FILE.stat().st_mtime > PANORAMA_DISK_TTL:
            return None
        payload = json.loads(PANORAMA_CACHE_FILE.read_text())
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not data.get("ok"):
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
        "total": 0,
        "up_count": 0,
        "down_count": 0,
        "flat_count": 0,
        "up_ratio": None,
        "median_change": None,
        "amount": None,
        "buckets": [{"label": label, "count": 0} for label, _ in BUCKETS],
        "as_of": None,
    }


def build_index_item(spec: dict[str, str], rows: list[dict[str, Any]], window: int) -> dict[str, Any]:
    series = normalize_index_series(rows, window)
    if not series:
        return {**spec, "status": "empty", "source": None, "as_of": None, "series": []}
    latest = series[-1]
    return {
        **spec,
        "status": "ok",
        "value": latest["close"],
        "change_pct": latest.get("pct_change"),
        "amount": latest.get("amount"),
        "as_of": latest["date"],
        "source": latest.get("source"),
        "series": series,
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
