"""Data provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import DataResult


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def get_stock_list(self) -> DataResult:
        raise NotImplementedError

    @abstractmethod
    def get_stock_daily(self, symbol: str, start_date: str, end_date: str, adjustment: str = "qfq") -> DataResult:
        raise NotImplementedError

    def get_index_daily(self, symbol: str, start_date: str, end_date: str, adjustment: str = "none") -> DataResult:
        return self.get_stock_daily(symbol, start_date, end_date, adjustment)

    def get_industry_members(self, industry: str) -> DataResult:
        return DataResult(False, [], [], f"{self.name} does not expose industry members here")

    def get_industry_daily(self, industry: str, start_date: str, end_date: str) -> DataResult:
        return DataResult(False, [], [], f"{self.name} does not expose industry daily data here")

    def get_basic_factors(self, symbols: list[str] | None = None) -> DataResult:
        return DataResult(False, [], [], f"{self.name} basic factors unavailable")

    def get_financial_factors(self, symbols: list[str] | None = None) -> DataResult:
        return DataResult(False, [], [], f"{self.name} financial factors unavailable")

    def get_market_snapshot(self) -> DataResult:
        return DataResult(False, {}, [], f"{self.name} market snapshot unavailable")

    def get_sector_snapshot(self) -> DataResult:
        return DataResult(False, [], [], f"{self.name} sector snapshot unavailable")

    def get_fund_flow(self, symbol: str, days: int = 120) -> DataResult:
        return DataResult(False, [], [], f"{self.name} fund flow unavailable")

    def get_stock_profile(self, symbol: str) -> DataResult:
        return DataResult(False, {}, [], f"{self.name} stock profile unavailable")

    def get_research_reports(self, symbol: str, limit: int = 20) -> DataResult:
        return DataResult(False, [], [], f"{self.name} research reports unavailable")

    def get_stock_news(self, symbol: str, limit: int = 20) -> DataResult:
        return DataResult(False, [], [], f"{self.name} stock news unavailable")

    def get_announcements(self, symbol: str, limit: int = 20) -> DataResult:
        return DataResult(False, [], [], f"{self.name} announcements unavailable")
