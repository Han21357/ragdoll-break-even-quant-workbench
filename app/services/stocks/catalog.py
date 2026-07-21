"""Locally cached A-share identity catalog for code/name/pinyin lookup."""
from __future__ import annotations

import re
import threading
from datetime import datetime
from typing import Any

from app.services.data.service import data_provider


_lock = threading.Lock()
_rows: list[dict[str, Any]] = []
_meta: dict[str, Any] = {"status": "waiting", "count": 0, "updated_at": None, "source": None, "error": None}


def warm_stock_catalog(force: bool = False) -> dict[str, Any]:
    global _rows, _meta
    if _rows and not force:
        return catalog_status()
    with _lock:
        if _rows and not force:
            return catalog_status()
        _meta = {**_meta, "status": "loading", "error": None}
        result = data_provider.request("get_stock_list", required_fields=["symbol", "name"])
        if not result.ok or not result.data:
            _meta = {**_meta, "status": "unavailable", "error": result.error or "股票目录主备源均不可用"}
            return catalog_status()
        normalized = []
        for raw in result.data:
            symbol = re.sub(r"\D", "", str(raw.get("symbol") or ""))[-6:].zfill(6)
            name = str(raw.get("name") or "").strip()
            if not re.fullmatch(r"[036689]\d{5}", symbol) or not name:
                continue
            market = "SH" if symbol.startswith(("5", "6", "9")) else "SZ"
            full_pinyin, initials, pinyin_terms = _pinyin(name)
            normalized.append({
                "code": symbol, "symbol": symbol, "name": name, "market": market,
                "market_label": _market_label(symbol), "pinyin": full_pinyin,
                "initials": initials, "pinyin_terms": pinyin_terms, "source": raw.get("source") or _source(result),
            })
        _rows = normalized
        _meta = {
            "status": "ok", "count": len(_rows), "updated_at": result.updated_at or datetime.now().isoformat(timespec="seconds"),
            "data_date": result.data_date, "source": _source(result), "cache_status": result.cache_status,
            "completeness": result.completeness, "error": None,
        }
    return catalog_status()


def search_stocks(query: str, limit: int = 8) -> list[dict] | None:
    if not _rows:
        warm_stock_catalog()
    if not _rows:
        return None
    needle = _query_key(query)
    if not needle:
        return []
    ranked = []
    for item in _rows:
        code, name = item["code"], _query_key(item["name"])
        pinyin, initials, pinyin_terms = item["pinyin"], item["initials"], item["pinyin_terms"]
        if code == needle:
            rank = 0
        elif name == needle or pinyin == needle or needle in pinyin_terms:
            rank = 1
        elif code.startswith(needle):
            rank = 2
        elif name.startswith(needle) or pinyin.startswith(needle) or initials.startswith(needle):
            rank = 3
        elif needle in name or needle in pinyin or needle in initials:
            rank = 4
        else:
            continue
        ranked.append((rank, len(name), code, item))
    ranked.sort(key=lambda value: value[:3])
    return [{key: value for key, value in item.items() if key not in {"pinyin", "initials", "pinyin_terms"}} for _, _, _, item in ranked[:limit]]


def enrich_stock_rows(rows: list[dict]) -> list[dict]:
    if not _rows:
        warm_stock_catalog()
    by_code = {item["code"]: item for item in _rows}
    enriched = []
    for row in rows:
        identity = by_code.get(str(row.get("symbol") or "").zfill(6))
        if identity:
            row = {**row, "name": row.get("name") or identity["name"], "market": row.get("market") or identity["market"], "identity_source": identity["source"]}
            row["identity_status"] = "matched"
        elif row.get("symbol") and _rows:
            row = {**row, "identity_status": "unmatched", "warnings": [*(row.get("warnings") or []), "代码未在当前A股基础目录中匹配，可能已退市或代码有误，请核验"]}
        enriched.append(row)
    return enriched


def catalog_status() -> dict[str, Any]:
    return dict(_meta)


def _query_key(value: Any) -> str:
    return re.sub(r"[\s._-]+", "", str(value or "").lower().translate(str.maketrans("０１２３４５６７８９", "0123456789")))


def _pinyin(name: str) -> tuple[str, str, set[str]]:
    try:
        from pypinyin import lazy_pinyin
        parts = lazy_pinyin(name)
        terms = {"".join(parts[start:end]).lower() for start in range(len(parts)) for end in range(start + 2, len(parts) + 1)}
        return "".join(parts).lower(), "".join(part[0] for part in parts if part).lower(), terms
    except ImportError:
        return "", "", set()


def _market_label(symbol: str) -> str:
    if symbol.startswith("68"):
        return "科创板"
    if symbol.startswith("30"):
        return "创业板"
    return "上海主板" if symbol.startswith(("6", "9")) else "深圳主板"


def _source(result) -> str | None:
    return next((item.source for item in result.provenance if item.status in {"ok", "cached", "stale"}), None)
