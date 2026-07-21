"""Optional mootdx historical market data provider."""
from __future__ import annotations

from datetime import datetime

from ..base import MarketDataProvider
from ..models import DataResult, SourceStatus
from .akshare_provider import _num, _plain_symbol


class MootdxProvider(MarketDataProvider):
    name = "mootdx"

    def _status(self, status, message=None, as_of=None):
        return SourceStatus(self.name, status, as_of=as_of, message=message)

    def get_stock_list(self) -> DataResult:
        return DataResult(False, [], [self._status("unsupported", "mootdx is not used for the security master")], "unsupported")

    def get_stock_daily(self, symbol, start_date, end_date, adjustment="qfq") -> DataResult:
        try:
            from mootdx.quotes import Quotes
            plain = _plain_symbol(symbol)
            market = 1 if plain.startswith(("5", "6", "9")) else 0
            client = Quotes.factory(market="std", multithread=True, heartbeat=True)
            df = client.bars(symbol=plain, frequency=9, offset=0, start=0, market=market)
            rows = []
            for index, row in df.iterrows():
                trade_date = str(index)[:10]
                if not start_date <= trade_date <= end_date:
                    continue
                rows.append({
                    "symbol": plain, "trade_date": trade_date, "open": _num(row.get("open")),
                    "high": _num(row.get("high")), "low": _num(row.get("low")), "close": _num(row.get("close")),
                    "volume": _num(row.get("volume")), "amount": _num(row.get("amount")),
                    "turnover_rate": None, "pct_change": None, "adjustment": adjustment,
                    "source": self.name, "as_of": trade_date, "status": "ok",
                })
            rows.sort(key=lambda item: item["trade_date"])
            if not rows:
                raise ValueError("mootdx returned no daily rows in requested range")
            return DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_index_daily(self, symbol, start_date, end_date, adjustment="none") -> DataResult:
        try:
            from mootdx.quotes import Quotes
            value = str(symbol).lower()
            plain = _plain_symbol(value)
            market = 1 if value.startswith("sh") else 0
            client = Quotes.factory(market="std", multithread=True, heartbeat=True)
            df = client.bars(symbol=plain, frequency=9, offset=0, start=0, market=market)
            rows = []
            for index, row in df.iterrows():
                trade_date = str(index)[:10]
                if start_date <= trade_date <= end_date:
                    rows.append({
                        "symbol": value, "trade_date": trade_date, "open": _num(row.get("open")),
                        "high": _num(row.get("high")), "low": _num(row.get("low")), "close": _num(row.get("close")),
                        "volume": _num(row.get("volume")), "amount": _num(row.get("amount")),
                        "turnover_rate": None, "pct_change": None, "adjustment": "none",
                        "source": self.name, "as_of": trade_date, "status": "ok",
                    })
            rows.sort(key=lambda item: item["trade_date"])
            if not rows or rows[-1].get("close") is None or rows[-1]["close"] < 100:
                raise ValueError("mootdx returned no valid index rows in requested range")
            return DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))
