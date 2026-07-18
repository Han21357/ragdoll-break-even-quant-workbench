"""Provider registry with primary, fallback and visible degradation state."""
from __future__ import annotations

from typing import Callable

from .base import MarketDataProvider
from .models import DataResult, SourceStatus
from .providers.akshare_provider import AKShareProvider
from .providers.baostock_provider import BaostockProvider


class ProviderRegistry:
    def __init__(self, providers: list[MarketDataProvider] | None = None):
        self.providers = providers or [AKShareProvider(), BaostockProvider()]

    def call(self, method: str, *args, **kwargs) -> DataResult:
        statuses: list[SourceStatus] = []
        errors = []
        for provider in self.providers:
            fn: Callable = getattr(provider, method)
            result = fn(*args, **kwargs)
            statuses.extend(result.provenance)
            if result.ok:
                result.provenance = statuses
                return result
            errors.append(f"{provider.name}: {result.error}")
        return DataResult(False, [] if method != "get_market_snapshot" else {}, statuses, "; ".join(errors))

    def status(self) -> dict:
        checks = {}
        for provider in self.providers:
            try:
                if provider.name == "akshare":
                    __import__("akshare")
                elif provider.name == "baostock":
                    __import__("baostock")
                checks[provider.name] = {"ok": True, "status": "installed", "error": None}
            except Exception as exc:
                checks[provider.name] = {"ok": False, "status": "missing", "error": str(exc)}
        return {
            "status": "ok" if all(item["ok"] for item in checks.values()) else "degraded",
            "checks": checks,
        }


registry = ProviderRegistry()
