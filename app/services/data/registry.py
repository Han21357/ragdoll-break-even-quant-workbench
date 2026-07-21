"""Provider registry with primary, fallback and visible degradation state."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Callable

from .base import MarketDataProvider
from .models import DataResult, SourceStatus
from .providers.akshare_provider import AKShareProvider
from .providers.aktools_provider import AKToolsProvider
from .providers.baostock_provider import BaostockProvider
from .providers.efinance_provider import EfinanceProvider
from .providers.mootdx_provider import MootdxProvider
from .providers.astock_provider import AStockDataProvider
from .providers.tushare_provider import TushareProvider
from .providers.tencent_provider import TencentProvider


class ProviderRegistry:
    def __init__(self, providers: list[MarketDataProvider] | None = None):
        self.providers = providers or [AKShareProvider(), AKToolsProvider(), EfinanceProvider(), TencentProvider(), MootdxProvider(), BaostockProvider(), AStockDataProvider(), TushareProvider()]

    def call(self, method: str, *args, **kwargs) -> DataResult:
        statuses: list[SourceStatus] = []
        errors = []
        providers = self._ordered_providers(method)
        for provider in providers:
            fn: Callable = getattr(provider, method)
            result = None
            for attempt in range(2):
                started = time.time()
                try:
                    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"provider-{provider.name}")
                    future = executor.submit(fn, *args, **kwargs)
                    try:
                        result = future.result(timeout=10)
                    except FutureTimeout:
                        future.cancel()
                        result = DataResult(False, [] if method != "get_market_snapshot" else {}, [SourceStatus(provider.name, "timeout", message="数据源10秒内未响应", latency_ms=10000)], "数据源10秒内未响应")
                    finally:
                        executor.shutdown(wait=False, cancel_futures=True)
                except Exception as exc:
                    result = DataResult(False, [] if method != "get_market_snapshot" else {}, [SourceStatus(provider.name, "unavailable", message=str(exc), latency_ms=int((time.time()-started)*1000))], str(exc))
                if result.ok or attempt == 1 or result.error in {"unsupported", "security master not provided"} or any(item.status == "disabled" for item in result.provenance):
                    break
                time.sleep(.25 * (attempt + 1))
            statuses.extend(result.provenance)
            if result.ok:
                result.provenance = statuses
                return result
            errors.append(f"{provider.name}: {result.error}")
        return DataResult(False, [] if method != "get_market_snapshot" else {}, statuses, "; ".join(errors))

    def _ordered_providers(self, method: str) -> list[MarketDataProvider]:
        if method == "get_index_daily":
            order = {"akshare": 0, "aktools": 1, "tencent": 2, "baostock": 3, "efinance": 4, "mootdx": 5, "a-stock-data": 6, "tushare": 7}
            return sorted(self.providers, key=lambda provider: order.get(provider.name, 99))
        if method == "get_stock_daily":
            order = {"akshare": 0, "aktools": 1, "tencent": 2, "efinance": 3, "baostock": 4, "mootdx": 5, "a-stock-data": 6, "tushare": 7}
            return sorted(self.providers, key=lambda provider: order.get(provider.name, 99))
        return self.providers

    def status(self) -> dict:
        checks = {}
        for provider in self.providers:
            try:
                if provider.name == "akshare":
                    __import__("akshare")
                elif provider.name == "aktools":
                    import os
                    if not os.getenv("AKTOOLS_URL"):
                        checks[provider.name] = {"ok": True, "status": "optional_unconfigured", "error": "AKTOOLS_URL 未配置"}
                        continue
                elif provider.name == "tushare":
                    __import__("tushare")
                    import os
                    if not os.getenv("TUSHARE_TOKEN"):
                        checks[provider.name] = {"ok": True, "status": "optional_unconfigured", "error": "TUSHARE_TOKEN 未配置"}
                        continue
                elif provider.name in {"baostock", "efinance", "mootdx", "tushare"}:
                    __import__(provider.name)
                checks[provider.name] = {"ok": True, "status": "installed", "error": None}
            except Exception as exc:
                optional = provider.name in {"efinance", "mootdx", "tushare"}
                checks[provider.name] = {"ok": optional, "status": "optional_missing" if optional else "missing", "error": str(exc)}
        return {
            "status": "ok" if all(item["ok"] for item in checks.values()) else "degraded",
            "checks": checks,
        }


registry = ProviderRegistry()
