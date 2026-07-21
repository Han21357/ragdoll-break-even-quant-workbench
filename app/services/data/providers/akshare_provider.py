"""AKShare provider wrapped behind the normalized data interface."""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime
from threading import Lock
from typing import Any

import pandas as pd

from config import CACHE_DIR

from ..base import MarketDataProvider
from ..cache import cache
from ..models import DataResult, SourceStatus


class AKShareProvider(MarketDataProvider):
    name = "akshare"
    _snapshot_lock = Lock()
    _snapshot_file = CACHE_DIR / "akshare_a_share_snapshot.json"

    def _ak(self):
        import akshare as ak

        return ak

    def _status(
        self,
        status: str,
        message: str | None = None,
        as_of: str | None = None,
        source: str | None = None,
    ) -> SourceStatus:
        return SourceStatus(source=source or self.name, status=status, as_of=as_of, message=message)

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
        ak = self._ak()
        adjust_map = {"qfq": "qfq", "hfq": "hfq", "none": ""}
        plain_symbol = _plain_symbol(symbol)
        sina_symbol = ("sh" if plain_symbol.startswith(("5", "6", "9")) else "sz") + plain_symbol
        attempts = [
            ("akshare:sina", lambda: ak.stock_zh_a_daily(
                symbol=sina_symbol,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=adjust_map.get(adjustment, "qfq"),
            )),
            ("akshare:eastmoney", lambda: ak.stock_zh_a_hist(
                symbol=plain_symbol,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=adjust_map.get(adjustment, "qfq"),
            )),
        ]
        provenance = []
        errors = []
        for source, loader in attempts:
            try:
                rows = _normalize_akshare_daily(loader(), symbol, adjustment, source)
                if not rows:
                    raise ValueError("daily endpoint returned no rows")
                provenance.append(self._status("ok", as_of=rows[-1]["trade_date"], source=source))
                result = DataResult(True, rows, provenance)
                cache.set(key, result, 3600)
                return result
            except Exception as exc:
                errors.append(f"{source}: {exc}")
                provenance.append(self._status("unavailable", str(exc), source=source))
        return DataResult(False, [], provenance, "; ".join(errors))

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
        cache_key = "akshare:basic_factors:all"
        result = cache.get(cache_key)
        if result is None:
            result = self._load_disk_snapshot()
            if result is not None:
                cache.set(cache_key, result, 180)
        if result is None:
            with self._snapshot_lock:
                result = cache.get(cache_key)
                if result is None:
                    result = self._fetch_basic_factors()
                    if result.ok:
                        cache.set(cache_key, result, 180)
                        self._save_disk_snapshot(result)
        if not symbols or not result.ok:
            return result
        wanted = {_plain_symbol(value) for value in symbols}
        return DataResult(
            True,
            [row for row in result.data if row.get("symbol") in wanted],
            list(result.provenance),
        )

    def _fetch_basic_factors(self) -> DataResult:
        ak = self._ak()
        attempts = [
            ("akshare:sina", ak.stock_zh_a_spot),
            ("akshare:eastmoney", ak.stock_zh_a_spot_em),
        ]
        provenance = []
        errors = []
        as_of = datetime.now().date().isoformat()
        for source, loader in attempts:
            try:
                rows = _normalize_spot_rows(loader(), source, as_of)
                if not rows:
                    raise ValueError("snapshot returned no usable A-share rows")
                provenance.append(self._status("ok", as_of=as_of, source=source))
                return DataResult(True, rows, provenance)
            except Exception as exc:
                errors.append(f"{source}: {exc}")
                provenance.append(self._status("unavailable", str(exc), source=source))
        return DataResult(False, [], provenance, "; ".join(errors))

    def _load_disk_snapshot(self) -> DataResult | None:
        try:
            payload = json.loads(self._snapshot_file.read_text())
            if time.time() - float(payload["saved_at"]) > 12 * 3600:
                return None
            rows = payload.get("data") or []
            if not rows:
                return None
            provenance = [SourceStatus(**item) for item in payload.get("provenance") or []]
            provenance.append(self._status("cached", "loaded from local snapshot", source="local-cache:akshare"))
            return DataResult(True, rows, provenance)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def _save_disk_snapshot(self, result: DataResult) -> None:
        try:
            self._snapshot_file.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._snapshot_file.with_suffix(".tmp")
            temp_path.write_text(json.dumps({
                "saved_at": time.time(),
                "data": result.data,
                "provenance": [asdict(item) for item in result.provenance],
            }, ensure_ascii=False))
            temp_path.replace(self._snapshot_file)
        except OSError:
            pass

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
            "source": rows[0].get("source", self.name) if rows else self.name,
        }, basic.provenance)

    def get_sector_snapshot(self) -> DataResult:
        cached = cache.get("akshare:sector_snapshot")
        if cached is not None:
            return cached
        source = "akshare:sina-sector"
        try:
            df = self._ak().stock_sector_spot(indicator="新浪行业")
            rows = []
            for _, row in df.iterrows():
                name = str(row.get("板块") or "").strip()
                change = _num(row.get("涨跌幅"))
                if not name or change is None:
                    continue
                rows.append({
                    "name": name,
                    "change_pct": round(change, 4),
                    "stocks": int(_num(row.get("公司家数")) or 0),
                    "amount": _num(row.get("总成交额")),
                    "leader": row.get("股票名称"),
                    "leader_symbol": row.get("股票代码"),
                    "leader_change_pct": _num(row.get("个股-涨跌幅")),
                    "source": source,
                    "as_of": datetime.now().date().isoformat(),
                    "status": "ok",
                })
            rows.sort(key=lambda item: item["change_pct"], reverse=True)
            if not rows:
                raise ValueError("sector snapshot returned no usable rows")
            result = DataResult(True, rows, [self._status("ok", as_of=datetime.now().date().isoformat(), source=source)])
            cache.set("akshare:sector_snapshot", result, 300)
            return result
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc), source=source)], str(exc))

    def get_industry_members(self, industry: str) -> DataResult:
        source = "akshare:eastmoney-industry-members"
        try:
            df = self._ak().stock_board_industry_cons_em(symbol=industry)
            today = datetime.now().date().isoformat()
            rows = []
            for _, row in df.iterrows():
                symbol = _plain_symbol(row.get("代码"))
                if symbol.isdigit() and len(symbol) == 6:
                    rows.append({"symbol": symbol, "name": row.get("名称"), "industry": industry, "source": source, "as_of": today, "status": "ok"})
            if not rows:
                raise ValueError("industry member endpoint returned no stocks")
            return DataResult(True, rows, [self._status("ok", as_of=today, source=source)], data_date=today)
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc), source=source)], str(exc))


def _num(value: Any):
    try:
        if value in ("", "-", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _plain_symbol(value: Any) -> str:
    raw = str(value or "").lower().replace("sh.", "").replace("sz.", "")
    for prefix in ("sh", "sz", "bj"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    return raw.zfill(6)


def _normalize_spot_rows(df, source: str, as_of: str, wanted: set[str] | None = None) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        symbol = _plain_symbol(row.get("代码"))
        if not symbol.isdigit() or len(symbol) != 6 or (wanted is not None and symbol not in wanted):
            continue
        rows.append({
            "symbol": symbol,
            "name": row.get("名称"),
            "close": _num(row.get("最新价")),
            "pct_change": _num(row.get("涨跌幅")),
            "turnover_rate": _num(row.get("换手率")),
            "amount": _num(row.get("成交额")),
            "market_cap": _num(row.get("总市值")),
            "pe_ttm": _num(row.get("市盈率-动态")),
            "pb": _num(row.get("市净率")),
            "source": source,
            "as_of": as_of,
            "status": "ok",
        })
    return rows


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
