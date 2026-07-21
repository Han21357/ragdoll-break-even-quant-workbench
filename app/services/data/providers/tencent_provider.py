"""Token-free Tencent Finance historical quote fallback."""
from __future__ import annotations

from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..base import MarketDataProvider
from ..models import DataResult, SourceStatus
from .akshare_provider import _plain_symbol


class TencentProvider(MarketDataProvider):
    name = "tencent"
    endpoint = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def __init__(self):
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=.3, status_forcelist=[429, 500, 502, 503, 504])))

    def get_stock_list(self) -> DataResult:
        return DataResult(False, [], [self._status("unsupported", "Tencent fallback is not used for the security master")], "unsupported")

    def get_stock_daily(self, symbol, start_date, end_date, adjustment="qfq") -> DataResult:
        value = str(symbol).lower()
        if not value.startswith(("sh", "sz")):
            plain = _plain_symbol(value)
            value = ("sh" if plain.startswith(("5", "6", "9")) else "sz") + plain
        adjust = "" if adjustment == "none" else adjustment
        try:
            params = {"param": f"{value},day,{start_date},{end_date},500,{adjust}"}
            response = self.session.get(self.endpoint, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            node = (payload.get("data") or {}).get(value) or {}
            raw_rows = node.get("day") or node.get("qfqday") or []
            rows = []
            for raw in raw_rows:
                if len(raw) < 6 or not start_date <= str(raw[0]) <= end_date:
                    continue
                rows.append({
                    "symbol": _plain_symbol(value), "trade_date": str(raw[0]),
                    "open": _number(raw[1]), "close": _number(raw[2]), "high": _number(raw[3]), "low": _number(raw[4]),
                    "volume": _number(raw[5]), "amount": _number(raw[6]) if len(raw) > 6 else None,
                    "turnover_rate": None, "pct_change": None, "adjustment": adjustment,
                    "source": self.name, "as_of": str(raw[0]), "status": "ok",
                })
            if not rows:
                raise ValueError("Tencent returned no normalized daily rows")
            return DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_index_daily(self, symbol, start_date, end_date, adjustment="none") -> DataResult:
        result = self.get_stock_daily(symbol, start_date, end_date, "none")
        if result.ok and (result.data[-1].get("close") is None or result.data[-1]["close"] < 100):
            return DataResult(False, [], [self._status("unavailable", "Tencent returned an invalid index series")], "invalid index series")
        return result

    def _status(self, status, message=None, as_of=None):
        return SourceStatus(self.name, status, as_of=as_of, message=message, fetched_at=datetime.now().isoformat(timespec="seconds"))


def _number(value):
    try:
        return None if value in (None, "", "-") else float(value)
    except (TypeError, ValueError):
        return None
