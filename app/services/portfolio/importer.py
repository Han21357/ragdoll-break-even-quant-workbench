"""Position import normalization, validation and conflict planning."""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any


FIELDS = [
    "symbol", "name", "market", "quantity", "available_quantity", "cost_price", "buy_date",
    "fees", "portfolio_id", "notes", "original_thesis", "review_date",
]

ALIASES = {
    "symbol": ["股票代码", "证券代码", "代码", "symbol", "ticker", "stock_code"],
    "name": ["股票名称", "证券名称", "名称", "name", "stock_name"],
    "market": ["市场", "交易所", "market", "exchange"],
    "quantity": ["持仓数量", "股票余额", "证券数量", "数量", "持仓", "quantity", "shares"],
    "available_quantity": ["可用数量", "可卖数量", "可用余额", "available", "available_quantity"],
    "cost_price": ["成本价", "摊薄成本价", "成本", "cost", "cost_price"],
    "buy_date": ["买入日期", "建仓日期", "buy_date", "trade_date"],
    "fees": ["手续费", "费用", "佣金", "fees", "commission"],
    "portfolio_id": ["所属组合", "组合", "portfolio", "portfolio_id"],
    "notes": ["备注", "notes", "note"],
    "original_thesis": ["原始买入理由", "买入理由", "投资逻辑", "original_thesis", "thesis"],
    "review_date": ["计划复盘日期", "复盘日期", "review_date", "due_date"],
}


def infer_mapping(columns: list[str]) -> dict[str, str]:
    normalized = {_column_key(column): str(column) for column in columns}
    mapping = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            if _column_key(alias) in normalized:
                mapping[field] = normalized[_column_key(alias)]
                break
    return mapping


def normalize_rows(raw_rows: list[dict[str, Any]], mapping: dict[str, str] | None = None,
                   existing: list[dict[str, Any]] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    columns = list(dict.fromkeys(str(key) for row in raw_rows for key in row.keys()))
    mapping = {**infer_mapping(columns), **(mapping or {})}
    existing_keys = {(str(item.get("portfolio_id") or "real_default"), _symbol(item.get("symbol"))) for item in (existing or []) if item.get("status", "open") == "open"}
    seen = set()
    rows = []
    for index, raw in enumerate(raw_rows, start=1):
        item = {field: _clean(raw.get(source)) for field, source in mapping.items() if source in raw}
        item["symbol"] = _symbol(item.get("symbol"))
        item["market"] = _market(item.get("market"), item["symbol"])
        item["portfolio_id"] = str(item.get("portfolio_id") or "real_default")
        item["quantity"] = _number(item.get("quantity"))
        item["available_quantity"] = _number(item.get("available_quantity"))
        item["cost_price"] = _number(item.get("cost_price"))
        item["fees"] = _number(item.get("fees")) or 0
        item["buy_date"] = _date_value(item.get("buy_date"))
        item["review_date"] = _date_value(item.get("review_date"))
        errors, warnings = validate_row(item, today)
        key = (item["portfolio_id"], item["symbol"])
        if key in seen:
            errors.append("本次导入中存在重复股票")
        seen.add(key)
        conflict = "existing_position" if key in existing_keys else None
        if conflict:
            warnings.append("与已有未清仓持仓冲突，确认时需选择合并、覆盖、跳过或新建组合")
        rows.append({"row_number": index, **item, "errors": errors, "warnings": warnings, "conflict": conflict, "valid": not errors})
    required = {"symbol", "quantity", "cost_price"}
    unmapped = sorted(required - set(mapping))
    return {
        "columns": columns,
        "mapping": mapping,
        "supported_fields": FIELDS,
        "unmapped_required_fields": unmapped,
        "rows": rows,
        "summary": {
            "total": len(rows), "valid": sum(item["valid"] for item in rows),
            "invalid": sum(not item["valid"] for item in rows),
            "conflicts": sum(bool(item["conflict"]) for item in rows),
        },
    }


def validate_row(item: dict[str, Any], today: date) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    symbol = item.get("symbol") or ""
    if not re.fullmatch(r"[036689]\d{5}", symbol):
        errors.append("股票代码必须是当前支持的6位A股代码")
    if item.get("quantity") is None:
        errors.append("持仓数量缺失")
    elif item["quantity"] <= 0:
        errors.append("持仓数量必须大于0")
    if item.get("cost_price") is None:
        errors.append("成本价缺失")
    elif item["cost_price"] <= 0:
        errors.append("成本价必须大于0")
    if item.get("available_quantity") is not None and item["available_quantity"] < 0:
        errors.append("可用数量不能为负数")
    if item.get("quantity") is not None and item.get("available_quantity") is not None and item["available_quantity"] > item["quantity"]:
        errors.append("可用数量不能大于持仓数量")
    buy_date = item.get("buy_date")
    if buy_date and date.fromisoformat(buy_date) > today:
        errors.append("买入日期不能晚于当前日期")
    review_date = item.get("review_date")
    if review_date and date.fromisoformat(review_date) <= today:
        warnings.append("计划复盘日期已到期，导入后会进入待复盘队列")
    if item.get("fees", 0) < 0:
        errors.append("手续费不能为负数")
    if item.get("buy_date") is None:
        warnings.append("缺少买入日期，持有天数和真实交易期收益将不完整")
    warnings.append("拆股、分红与复权影响需结合后续交易流水和公司行动数据核验")
    return errors, warnings


def _column_key(value: Any) -> str:
    return re.sub(r"[\s_\-（）()]+", "", str(value or "")).lower()


def _clean(value: Any):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    value = str(value).strip() if not isinstance(value, (int, float)) else value
    return None if value == "" else value


def _symbol(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-6:].zfill(6) if digits else ""


def _market(value: Any, symbol: str) -> str:
    text = str(value or "").lower()
    if "上" in text or text in {"sh", "sse"}:
        return "SH"
    if "深" in text or text in {"sz", "szse"}:
        return "SZ"
    return "SH" if symbol.startswith(("5", "6", "9")) else "SZ" if symbol else ""


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return float(str(value).replace(",", "").replace("¥", "").replace("¥", ""))
    except (TypeError, ValueError):
        return None


def _date_value(value: Any) -> str | None:
    if value in (None, "", "-"):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None
