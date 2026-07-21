"""Optional AKTools HTTP gateway for environments that run an AKTools service."""
from __future__ import annotations

import os
from datetime import datetime

import requests

from ..base import MarketDataProvider
from ..models import DataResult, SourceStatus
from .akshare_provider import _normalize_akshare_daily, _normalize_spot_rows, _plain_symbol


class AKToolsProvider(MarketDataProvider):
    name = "aktools"

    def __init__(self):
        self.base_url = os.getenv("AKTOOLS_URL", "").rstrip("/")

    def _disabled(self, shape="list"):
        reason = "AKTOOLS_URL 未配置，可选HTTP主源未启用"
        return DataResult(False, {} if shape == "dict" else [], [SourceStatus(self.name, "disabled", message=reason)], reason)

    def _request(self, endpoint: str, params: dict):
        if not self.base_url:
            return None
        response = requests.get(f"{self.base_url}/api/public/{endpoint}", params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_stock_list(self) -> DataResult:
        result = self.get_basic_factors()
        if not result.ok:
            return result
        return DataResult(True, [{key: row.get(key) for key in ("symbol", "name", "source", "as_of", "status")} for row in result.data], result.provenance, data_date=result.data_date)

    def get_basic_factors(self, symbols=None) -> DataResult:
        if not self.base_url:
            return self._disabled()
        try:
            payload = self._request("stock_zh_a_spot_em", {})
            import pandas as pd
            rows = _normalize_spot_rows(pd.DataFrame(payload), self.name, datetime.now().date().isoformat(), {_plain_symbol(value) for value in symbols} if symbols else None)
            if not rows:
                raise ValueError("AKTools returned no normalized quote rows")
            as_of = datetime.now().date().isoformat()
            return DataResult(True, rows, [SourceStatus(self.name, "ok", as_of=as_of)], data_date=as_of)
        except Exception as exc:
            return DataResult(False, [], [SourceStatus(self.name, "unavailable", message=str(exc))], str(exc))

    def get_stock_daily(self, symbol, start_date, end_date, adjustment="qfq") -> DataResult:
        if not self.base_url:
            return self._disabled()
        try:
            payload = self._request("stock_zh_a_hist", {"symbol": _plain_symbol(symbol), "period": "daily", "start_date": start_date.replace("-", ""), "end_date": end_date.replace("-", ""), "adjust": "" if adjustment == "none" else adjustment})
            import pandas as pd
            rows = _normalize_akshare_daily(pd.DataFrame(payload), symbol, adjustment, self.name)
            if not rows:
                raise ValueError("AKTools returned no normalized daily rows")
            return DataResult(True, rows, [SourceStatus(self.name, "ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [SourceStatus(self.name, "unavailable", message=str(exc))], str(exc))

    def get_index_daily(self, symbol, start_date, end_date, adjustment="none") -> DataResult:
        if not self.base_url:
            return self._disabled()
        try:
            payload = self._request("stock_zh_index_daily", {"symbol": str(symbol).lower()})
            import pandas as pd
            rows = _normalize_akshare_daily(pd.DataFrame(payload), symbol, "none", self.name)
            rows = [row for row in rows if start_date <= row["trade_date"] <= end_date]
            if not rows or rows[-1].get("close") is None or rows[-1]["close"] < 100:
                raise ValueError("AKTools returned no valid index rows")
            return DataResult(True, rows, [SourceStatus(self.name, "ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [SourceStatus(self.name, "unavailable", message=str(exc))], str(exc))
