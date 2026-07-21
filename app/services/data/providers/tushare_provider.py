"""Optional Tushare enhancement; disabled unless TUSHARE_TOKEN is configured."""
from __future__ import annotations

import os

from ..base import MarketDataProvider
from ..models import DataResult, SourceStatus


class TushareProvider(MarketDataProvider):
    name = "tushare"

    def _unavailable(self):
        reason = "TUSHARE_TOKEN 未配置，可选增强未启用" if not os.getenv("TUSHARE_TOKEN") else "当前能力未由 Tushare 增强"
        return DataResult(False, [], [SourceStatus(self.name, "disabled", message=reason)], reason)

    get_stock_list = lambda self: self._unavailable()
    get_stock_daily = lambda self, *args, **kwargs: self._unavailable()
