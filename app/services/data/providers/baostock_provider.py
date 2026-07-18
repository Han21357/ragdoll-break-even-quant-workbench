"""Baostock provider used as fallback source."""
from __future__ import annotations

import contextlib
import io
from datetime import datetime

from ..base import MarketDataProvider
from ..cache import cache
from ..models import DataResult, SourceStatus


class BaostockProvider(MarketDataProvider):
    name = "baostock"

    def _status(self, status: str, message: str | None = None, as_of: str | None = None) -> SourceStatus:
        return SourceStatus(source=self.name, status=status, as_of=as_of, message=message)

    def _login(self):
        import baostock as bs

        with contextlib.redirect_stdout(io.StringIO()):
            bs.login()
        return bs

    def get_stock_list(self) -> DataResult:
        cached = cache.get("baostock:stock_list")
        if cached is not None:
            return cached
        try:
            bs = self._login()
            rows = []
            rs = bs.query_stock_basic()
            while rs.error_code == "0" and rs.next():
                raw_code, name, ipo, out_date, stock_type, status = rs.get_row_data()
                if stock_type == "1" and status == "1":
                    rows.append({
                        "symbol": raw_code.split(".")[-1],
                        "raw_symbol": raw_code,
                        "name": name,
                        "ipo_date": ipo,
                        "source": self.name,
                        "as_of": datetime.now().date().isoformat(),
                        "status": "ok",
                    })
            with contextlib.redirect_stdout(io.StringIO()):
                bs.logout()
            result = DataResult(True, rows, [self._status("ok", as_of=datetime.now().date().isoformat())])
            cache.set("baostock:stock_list", result, 86400)
            return result
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjustment: str = "qfq") -> DataResult:
        key = f"baostock:daily:{symbol}:{start_date}:{end_date}:{adjustment}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            bs = self._login()
            bs_code = _to_baostock_symbol(symbol)
            adjust_map = {"qfq": "2", "hfq": "1", "none": "3"}
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount,turn,pctChg,tradestatus,isST",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=adjust_map.get(adjustment, "2"),
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                raw = rs.get_row_data()
                if len(raw) < 11 or not raw[4]:
                    continue
                rows.append({
                    "symbol": symbol.replace("sh.", "").replace("sz.", ""),
                    "trade_date": raw[0],
                    "open": _num(raw[1]),
                    "high": _num(raw[2]),
                    "low": _num(raw[3]),
                    "close": _num(raw[4]),
                    "volume": _num(raw[5]),
                    "amount": _num(raw[6]),
                    "turnover_rate": _num(raw[7]),
                    "pct_change": _num(raw[8]),
                    "tradable": raw[9] == "1",
                    "is_st": raw[10] == "1",
                    "adjustment": adjustment,
                    "source": self.name,
                    "as_of": raw[0],
                    "status": "ok",
                })
            with contextlib.redirect_stdout(io.StringIO()):
                bs.logout()
            if not rows:
                return DataResult(False, [], [self._status("empty", "Baostock returned no rows")], "empty data")
            result = DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])])
            cache.set(key, result, 3600)
            return result
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_market_snapshot(self) -> DataResult:
        return DataResult(True, {
            "total": None,
            "up_count": None,
            "down_count": None,
            "amount": None,
            "as_of": datetime.now().date().isoformat(),
            "source": self.name,
            "status": "partial",
            "message": "Baostock fallback is installed; real-time breadth requires AKShare snapshot.",
        }, [self._status("partial", "market breadth unavailable in fallback", datetime.now().date().isoformat())])


def _num(value):
    try:
        if value in ("", "-", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_baostock_symbol(symbol: str) -> str:
    value = str(symbol).lower().replace("sh.", "").replace("sz.", "")
    if value.startswith(("5", "6", "9")):
        return f"sh.{value}"
    return f"sz.{value}"
