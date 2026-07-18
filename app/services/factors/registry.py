"""Factor registry for the strategy DSL."""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class FactorDefinition:
    id: str
    name: str
    category: str
    description: str
    formula: str
    data_source: str
    frequency: str
    latest_update: str | None
    coverage: str
    status: str
    version: str = "1.0"


def _factor(fid, name, category, formula, status="available", source="AKShare/Baostock", coverage="A股日频"):
    return FactorDefinition(fid, name, category, name, formula, source, "daily", None, coverage, status)


FACTOR_REGISTRY: dict[str, FactorDefinition] = {
    f.id: f
    for f in [
        _factor("close", "收盘价", "行情", "close"),
        _factor("open", "开盘价", "行情", "open"),
        _factor("high", "最高价", "行情", "high"),
        _factor("low", "最低价", "行情", "low"),
        _factor("volume", "成交量", "行情", "volume"),
        _factor("amount", "成交额", "行情", "amount"),
        _factor("turnover_rate", "换手率", "行情", "turnover_rate"),
        _factor("return_1d", "1日收益", "行情", "pct_change"),
        _factor("return_5d", "5日收益", "行情", "close / close.shift(5) - 1"),
        _factor("return_10d", "10日收益", "行情", "close / close.shift(10) - 1"),
        _factor("return_20d", "20日收益", "行情", "close / close.shift(20) - 1"),
        _factor("return_60d", "60日收益", "行情", "close / close.shift(60) - 1", "partial"),
        _factor("max_drawdown_20d", "20日最大回撤", "行情", "rolling max drawdown 20"),
        _factor("max_drawdown_60d", "60日最大回撤", "行情", "rolling max drawdown 60", "partial"),
        _factor("volatility_20d", "20日波动率", "行情", "std(return_1d, 20)"),
        _factor("volatility_60d", "60日波动率", "行情", "std(return_1d, 60)", "partial"),
        _factor("MA5", "MA5", "趋势", "mean(close, 5)"),
        _factor("MA10", "MA10", "趋势", "mean(close, 10)"),
        _factor("MA20", "MA20", "趋势", "mean(close, 20)"),
        _factor("MA60", "MA60", "趋势", "mean(close, 60)"),
        _factor("MA20_slope", "MA20斜率", "趋势", "MA20 - MA20.shift(5)"),
        _factor("ma_alignment", "均线排列", "趋势", "MA5 >= MA10 >= MA20"),
        _factor("distance_MA20", "距离MA20", "趋势", "close / MA20 - 1"),
        _factor("distance_MA60", "距离MA60", "趋势", "close / MA60 - 1"),
        _factor("recent_high", "近期新高", "趋势", "close >= rolling_max(high, lookback)"),
        _factor("recent_low", "近期新低", "趋势", "close <= rolling_min(low, lookback)"),
        _factor("RSI14", "RSI14", "动量量价", "RSI(close, 14)"),
        _factor("MACD", "MACD", "动量量价", "EMA12 - EMA26"),
        _factor("MACD_signal", "MACD signal", "动量量价", "EMA(MACD, 9)"),
        _factor("MACD_histogram", "MACD histogram", "动量量价", "MACD - signal"),
        _factor("volume_ratio", "量比", "动量量价", "volume / mean(volume, 20)"),
        _factor("volume_change", "成交量变化", "动量量价", "volume / volume.shift(5) - 1"),
        _factor("OBV", "OBV", "动量量价", "on balance volume"),
        _factor("ATR", "ATR", "动量量价", "ATR(14)"),
        _factor("relative_index_strength", "相对指数强弱", "动量量价", "stock return - benchmark return", "partial"),
        _factor("relative_industry_strength", "相对行业强弱", "动量量价", "stock return - industry return", "partial"),
        _factor("market_cap", "市值", "基本面", "total market cap", "partial", "AKShare"),
        _factor("pe_ttm", "PE TTM", "基本面", "pe_ttm", "partial", "AKShare"),
        _factor("pb", "PB", "基本面", "pb", "partial", "AKShare"),
        _factor("ps_ttm", "PS TTM", "基本面", "ps_ttm", "unavailable", "AKShare"),
        _factor("roe", "ROE", "基本面", "roe", "partial", "AKShare/Baostock"),
        _factor("gross_margin", "毛利率", "基本面", "gross_margin", "partial", "Baostock"),
        _factor("net_margin", "净利率", "基本面", "net_margin", "partial", "Baostock"),
        _factor("revenue_growth", "营收增速", "基本面", "revenue_growth", "partial", "Baostock"),
        _factor("profit_growth", "利润增速", "基本面", "profit_growth", "partial", "Baostock"),
        _factor("debt_ratio", "资产负债率", "基本面", "debt_ratio", "partial", "Baostock"),
        _factor("operating_cashflow", "经营现金流", "基本面", "operating_cashflow", "unavailable"),
        _factor("industry", "行业", "分类过滤", "industry"),
        _factor("board", "板块", "分类过滤", "board"),
        _factor("is_st", "ST", "分类过滤", "is_st"),
        _factor("listed_days", "上市天数", "分类过滤", "today - ipo_date", "partial"),
        _factor("suspended", "停牌", "分类过滤", "tradestatus == 0", "partial"),
        _factor("limit_up", "涨停", "分类过滤", "close == limit_up_price", "unavailable"),
        _factor("limit_down", "跌停", "分类过滤", "close == limit_down_price", "unavailable"),
        _factor("tradable", "可交易", "分类过滤", "tradestatus == 1", "partial"),
        _factor("industry_momentum_20d", "行业20日动量", "行业", "industry return 20d", "partial"),
        _factor("analyst_coverage_60d_change", "60日机构覆盖变化", "事件", "coverage_count - coverage_count.shift(60)", "unavailable"),
    ]
}


def list_factors() -> list[dict]:
    return [asdict(item) for item in FACTOR_REGISTRY.values()]


def get_factor(factor_id: str) -> dict | None:
    item = FACTOR_REGISTRY.get(factor_id)
    return asdict(item) if item else None


def validate_factors(factor_ids: list[str], require_available: bool = True) -> tuple[bool, list[str]]:
    errors = []
    for factor_id in factor_ids:
        item = FACTOR_REGISTRY.get(factor_id)
        if not item:
            errors.append(f"未知因子: {factor_id}")
        elif require_available and item.status == "unavailable":
            errors.append(f"因子不可用，不能进入正式策略: {factor_id}")
    return not errors, errors

