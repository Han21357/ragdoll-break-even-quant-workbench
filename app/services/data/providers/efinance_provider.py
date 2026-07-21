"""Optional efinance provider for quotes, daily bars and fund flow."""
from __future__ import annotations

from datetime import datetime

from ..base import MarketDataProvider
from ..models import DataResult, SourceStatus
from .akshare_provider import _normalize_akshare_daily, _num, _plain_symbol


class EfinanceProvider(MarketDataProvider):
    name = "efinance"

    def _ef(self):
        import efinance as ef
        return ef

    def _status(self, status, message=None, as_of=None):
        return SourceStatus(self.name, status, as_of=as_of, message=message)

    def get_stock_list(self) -> DataResult:
        return self.get_basic_factors()

    def get_basic_factors(self, symbols=None) -> DataResult:
        try:
            df = self._ef().stock.get_realtime_quotes()
            wanted = {_plain_symbol(item) for item in symbols or []}
            today = datetime.now().date().isoformat()
            rows = []
            for _, row in df.iterrows():
                symbol = _plain_symbol(row.get("股票代码"))
                if wanted and symbol not in wanted:
                    continue
                rows.append({
                    "symbol": symbol, "name": row.get("股票名称"), "close": _num(row.get("最新价")),
                    "pct_change": _num(row.get("涨跌幅")), "amount": _num(row.get("成交额")),
                    "turnover_rate": _num(row.get("换手率")), "pe_ttm": _num(row.get("市盈率-动态")),
                    "pb": _num(row.get("市净率")), "market_cap": _num(row.get("总市值")),
                    "source": self.name, "as_of": today, "status": "ok",
                })
            if not rows:
                raise ValueError("efinance returned no quote rows")
            return DataResult(True, rows, [self._status("ok", as_of=today)], data_date=today)
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_market_snapshot(self) -> DataResult:
        result = self.get_basic_factors()
        if not result.ok:
            return result
        values = [row for row in result.data if row.get("pct_change") is not None]
        return DataResult(True, {
            "total": len(values), "up_count": sum(row["pct_change"] > 0 for row in values),
            "down_count": sum(row["pct_change"] < 0 for row in values),
            "amount": sum(row.get("amount") or 0 for row in values), "as_of": result.data_date,
            "source": self.name,
        }, result.provenance, data_date=result.data_date)

    def get_stock_daily(self, symbol, start_date, end_date, adjustment="qfq") -> DataResult:
        try:
            df = self._ef().stock.get_quote_history(_plain_symbol(symbol), beg=start_date.replace("-", ""), end=end_date.replace("-", ""), klt=101, fqt={"none": 0, "qfq": 1, "hfq": 2}.get(adjustment, 1))
            rows = _normalize_akshare_daily(df, symbol, adjustment, self.name)
            if not rows:
                raise ValueError("efinance returned no daily rows")
            return DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_index_daily(self, symbol, start_date, end_date, adjustment="none") -> DataResult:
        names = {"sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指", "sh000300": "沪深300"}
        lookup = names.get(str(symbol).lower(), symbol)
        try:
            df = self._ef().stock.get_quote_history(lookup, beg=start_date.replace("-", ""), end=end_date.replace("-", ""), klt=101, fqt=0)
            rows = _normalize_akshare_daily(df, symbol, "none", self.name)
            if not rows or rows[-1].get("close") is None or rows[-1]["close"] < 100:
                raise ValueError("efinance returned an invalid or ambiguous index series")
            return DataResult(True, rows, [self._status("ok", as_of=rows[-1]["trade_date"])], data_date=rows[-1]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))

    def get_fund_flow(self, symbol: str, days: int = 120) -> DataResult:
        try:
            df = self._ef().stock.get_history_bill(_plain_symbol(symbol))
            rows = []
            for _, row in df.head(days).iterrows():
                rows.append({
                    "symbol": _plain_symbol(symbol), "trade_date": str(row.get("日期"))[:10],
                    "main_net_inflow": _num(row.get("主力净流入")), "small_net_inflow": _num(row.get("小单净流入")),
                    "source": self.name,
                })
            if not rows:
                raise ValueError("efinance returned no fund-flow rows")
            return DataResult(True, rows, [self._status("ok", as_of=rows[0]["trade_date"])], data_date=rows[0]["trade_date"])
        except Exception as exc:
            return DataResult(False, [], [self._status("unavailable", str(exc))], str(exc))
