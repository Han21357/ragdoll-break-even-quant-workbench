"""AKShare provider wrapped behind the normalized data interface."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ..base import MarketDataProvider
from ..cache import cache
from ..models import DataResult, SourceStatus


class AKShareProvider(MarketDataProvider):
    name = "akshare"

    def _ak(self):
        import akshare as ak

        return ak

    def _status(self, status: str, message: str | None = None, as_of: str | None = None) -> SourceStatus:
        return SourceStatus(source=self.name, status=status, as_of=as_of, message=message)

    def get_stock_list(self) -> DataResult:
        cached = cache.get("akshare:stock_list")
        if cached is not None:
            return cached
        try:
            ak = self._ak()
            df = ak.stock_info_a_code_name()
            rows = [
                {
                    "symbol": str(row["code"]).zfill(6),
                    "name": row["name"],
                    "source": self.name,
                    "as_of": datetime.now().date().isoformat(),
                    "status": "ok",
                }
                for _, row in df.iterrows()
            ]
            result = DataResult(True, rows, [self._status("ok", as_of=datetime.now().date().isoformat())])
            cache.set("akshare:stock_list", result, 86400)
            return result
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjustment: str = "qfq") -> DataResult:
        key = f"akshare:daily:{symbol}:{start_date}:{end_date}:{adjustment}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            ak = self._ak()
            adjust_map = {"qfq": "qfq", "hfq": "hfq", "none": ""}
            df = ak.stock_zh_a_hist(
                symbol=symbol.replace("sh.", "").replace("sz.", ""),
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=adjust_map.get(adjustment, "qfq"),
            )
            rows = _normalize_akshare_daily(df, symbol, adjustment, self.name)
            if not rows:
                return DataResult(False, [], [self._status("empty", "AKShare returned no rows")], "empty data")
            result = DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])])
            cache.set(key, result, 3600)
            return result
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_index_daily(self, symbol: str, start_date: str, end_date: str, adjustment: str = "none") -> DataResult:
        key = f"akshare:index:{symbol}:{start_date}:{end_date}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            ak = self._ak()
            df = ak.stock_zh_index_daily(symbol=symbol.replace(".", ""))
            if "date" in df.columns:
                df = df[(pd.to_datetime(df["date"]) >= pd.to_datetime(start_date)) & (pd.to_datetime(df["date"]) <= pd.to_datetime(end_date))]
            rows = _normalize_akshare_daily(df, symbol, "none", self.name)
            if not rows:
                return DataResult(False, [], [self._status("empty", "AKShare returned no index rows")], "empty data")
            result = DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])])
            cache.set(key, result, 3600)
            return result
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_basic_factors(self, symbols: list[str] | None = None) -> DataResult:
        try:
            ak = self._ak()
            df = ak.stock_zh_a_spot_em()
            if symbols:
                wanted = {s.replace("sh.", "").replace("sz.", "") for s in symbols}
                df = df[df["代码"].astype(str).isin(wanted)]
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "symbol": str(row.get("代码", "")).zfill(6),
                    "name": row.get("名称"),
                    "close": _num(row.get("最新价")),
                    "pct_change": _num(row.get("涨跌幅")),
                    "turnover_rate": _num(row.get("换手率")),
                    "amount": _num(row.get("成交额")),
                    "market_cap": _num(row.get("总市值")),
                    "pe_ttm": _num(row.get("市盈率-动态")),
                    "pb": _num(row.get("市净率")),
                    "source": self.name,
                    "as_of": datetime.now().date().isoformat(),
                    "status": "ok",
                })
            return DataResult(True, rows, [self._status("ok", as_of=datetime.now().date().isoformat())])
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_market_snapshot(self) -> DataResult:
        basic = self.get_basic_factors()
        if not basic.ok:
            return basic
        rows = basic.data
        up = sum(1 for row in rows if (row.get("pct_change") or 0) > 0)
        down = sum(1 for row in rows if (row.get("pct_change") or 0) < 0)
        amount = sum(row.get("amount") or 0 for row in rows)
        return DataResult(True, {
            "total": len(rows),
            "up_count": up,
            "down_count": down,
            "amount": amount,
            "as_of": datetime.now().date().isoformat(),
            "source": self.name,
        }, basic.provenance)


def _num(value: Any):
    try:
        if value in ("", "-", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_akshare_daily(df, symbol: str, adjustment: str, source: str) -> list[dict]:
    if df is None or len(df) == 0:
        return []
    field_map = {
        "日期": "trade_date",
        "date": "trade_date",
        "开盘": "open",
        "open": "open",
        "最高": "high",
        "high": "high",
        "最低": "low",
        "low": "low",
        "收盘": "close",
        "close": "close",
        "成交量": "volume",
        "volume": "volume",
        "成交额": "amount",
        "amount": "amount",
        "换手率": "turnover_rate",
        "涨跌幅": "pct_change",
    }
    rows = []
    for _, raw in df.iterrows():
        item = {"symbol": symbol.replace("sh.", "").replace("sz.", ""), "adjustment": adjustment, "source": source, "status": "ok"}
        for original, target in field_map.items():
            if original in raw:
                item[target] = raw[original] if target == "trade_date" else _num(raw[original])
        if "trade_date" not in item or item.get("close") is None:
            continue
        item["trade_date"] = str(pd.to_datetime(item["trade_date"]).date())
        item["as_of"] = item["trade_date"]
        item.setdefault("turnover_rate", None)
        item.setdefault("pct_change", None)
        rows.append(item)
    rows.sort(key=lambda row: row["trade_date"])
    return rows

