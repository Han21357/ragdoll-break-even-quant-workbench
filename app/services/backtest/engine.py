"""A-share backtest runner with execution costs and explicit limitations."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from app.schemas.backtest import BacktestConfig
from app.services.backtest.akquant_adapter import akquant_status
from app.services.backtest.diagnostics import diagnose_backtest
from app.services.backtest.result_normalizer import annualized_return, max_drawdown, monthly_returns, periodic_stats
from app.services.data.registry import registry


def run_backtest(config_payload: dict) -> dict:
    config = BacktestConfig.model_validate(config_payload)
    if not config.stocks:
        return {"ok": False, "error": "回测需要明确股票池；系统不会生成默认候选股票。"}

    data_by_symbol = {}
    provenance = []
    for symbol in config.stocks[: config.max_positions]:
        result = registry.call("get_stock_daily", symbol, config.start_date, config.end_date, config.price_adjustment)
        provenance.extend(result.provenance)
        if not result.ok:
            return {"ok": False, "error": f"{symbol} 历史行情不可用: {result.error}", "provenance": [p.__dict__ for p in result.provenance]}
        df = pd.DataFrame(result.data).sort_values("trade_date")
        if df.empty:
            return {"ok": False, "error": f"{symbol} 历史行情为空，不作为0收益处理。"}
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        data_by_symbol[symbol] = df.dropna(subset=["close"])

    calendar = sorted(set().union(*[set(df["trade_date"]) for df in data_by_symbol.values()]))
    if len(calendar) < 2:
        return {"ok": False, "error": "样本区间不足，无法形成权益曲线。"}

    cash = config.initial_capital
    positions: dict[str, dict] = {}
    trades = []
    equity_curve = []
    total_cost = 0.0
    rebalance_days = _rebalance_days(calendar, config)

    for date in calendar:
        date_key = pd.Timestamp(date)
        if date_key in rebalance_days:
            target_symbols = _tradable_symbols(data_by_symbol, date_key)[: config.max_positions]
            target_value = (cash + _positions_value(positions, data_by_symbol, date_key)) * min(config.single_position_limit, 1 / max(len(target_symbols), 1))
            for symbol in list(positions):
                if symbol not in target_symbols and (date_key - positions[symbol]["entry_date"]).days >= config.sellable_after_days:
                    proceeds, cost, trade = _sell(symbol, positions.pop(symbol), data_by_symbol[symbol], date_key, config)
                    cash += proceeds
                    total_cost += cost
                    trades.append(trade)
            for symbol in target_symbols:
                if symbol in positions:
                    continue
                price = _price_on(data_by_symbol[symbol], date_key, config.trade_price)
                if price is None:
                    continue
                exec_price = price * (1 + config.slippage)
                shares = int(target_value / exec_price / config.lot_size) * config.lot_size
                if shares <= 0:
                    continue
                gross = shares * exec_price
                cost = max(gross * config.commission_rate, config.min_commission) + gross * config.transfer_fee_rate
                if gross + cost > cash:
                    continue
                cash -= gross + cost
                total_cost += cost
                positions[symbol] = {"shares": shares, "entry_price": exec_price, "entry_date": date_key, "entry_cost": cost}

        equity = cash + _positions_value(positions, data_by_symbol, date_key)
        equity_curve.append({"date": date_key.date().isoformat(), "equity": round(float(equity), 2)})

    final_date = pd.Timestamp(calendar[-1])
    for symbol in list(positions):
        if (final_date - positions[symbol]["entry_date"]).days >= config.sellable_after_days:
            proceeds, cost, trade = _sell(symbol, positions.pop(symbol), data_by_symbol[symbol], final_date, config, reason="period_end")
            cash += proceeds
            total_cost += cost
            trades.append(trade)
    final_equity = cash + _positions_value(positions, data_by_symbol, final_date)
    if equity_curve:
        equity_curve[-1]["equity"] = round(float(final_equity), 2)

    max_dd, dd_period = max_drawdown(equity_curve)
    stats = periodic_stats(equity_curve)
    trade_wins = [t for t in trades if t.get("pnl", 0) > 0]
    trade_losses = [t for t in trades if t.get("pnl", 0) < 0]
    total_return = (final_equity / config.initial_capital - 1) * 100
    result = {
        "ok": True,
        "engine": {"adapter": "akquant", **akquant_status(), "compatibility_runner_used": True},
        "config": config.model_dump(),
        "initial_capital": config.initial_capital,
        "final_equity": round(float(final_equity), 2),
        "metrics": {
            "total_return": round(float(total_return), 2),
            "annual_return": annualized_return(equity_curve),
            "benchmark_return": None,
            "excess_return": None,
            "volatility": stats["volatility"],
            "sharpe": stats["sharpe"],
            "sortino": stats["sortino"],
            "calmar": round(annualized_return(equity_curve) / abs(max_dd), 2) if max_dd else 0,
            "max_drawdown": max_dd,
            "max_drawdown_period": dd_period,
            "turnover_rate": None,
            "total_cost": round(total_cost, 2),
            "holding_count": len(config.stocks),
            "trade_count": len(trades),
            "trade_win_rate": round(len(trade_wins) / len(trades) * 100, 1) if trades else 0,
            "positive_period_rate": stats["positive_period_rate"],
            "profit_loss_ratio": _profit_loss_ratio(trade_wins, trade_losses),
        },
        "equity_curve": equity_curve,
        "drawdown_curve": _drawdown_curve(equity_curve),
        "monthly_returns": monthly_returns(equity_curve),
        "trades": trades,
        "holdings_history": [],
        "provenance": [p.__dict__ for p in provenance[-20:]],
        "limitations": [
            "当前适配器已处理手续费、最低佣金、卖出印花税、过户费、滑点、整手约束和T+1。",
            "当前未处理分红送转。",
            "当前仅根据日线tradable字段近似处理停牌，未完整模拟停牌期间订单排队。",
            "当前未处理涨跌停无法成交。",
            "当前未处理退市和ST全历史变更。",
            "如果股票池来自当前股票列表，可能存在幸存者偏差。",
        ],
    }
    result["diagnostics"] = diagnose_backtest(result)
    return result


def _rebalance_days(calendar: list, config: BacktestConfig) -> set[pd.Timestamp]:
    if config.hold_days:
        return {pd.Timestamp(day) for i, day in enumerate(calendar) if i % config.hold_days == 0}
    if config.rebalance_frequency == "weekly":
        return {pd.Timestamp(day) for i, day in enumerate(calendar) if i % 5 == 0}
    if config.rebalance_frequency == "daily":
        return {pd.Timestamp(day) for day in calendar}
    seen = set()
    days = set()
    for day in calendar:
        key = (day.year, day.month)
        if key not in seen:
            seen.add(key)
            days.add(pd.Timestamp(day))
    return days


def _tradable_symbols(data_by_symbol, date):
    return [symbol for symbol, df in data_by_symbol.items() if _price_on(df, date, "close") is not None]


def _price_on(df, date, price_field):
    rows = df[df["trade_date"] <= date]
    if rows.empty:
        return None
    value = rows.iloc[-1].get(price_field) or rows.iloc[-1].get("close")
    return float(value) if pd.notna(value) else None


def _positions_value(positions, data_by_symbol, date):
    total = 0.0
    for symbol, pos in positions.items():
        price = _price_on(data_by_symbol[symbol], date, "close")
        if price is not None:
            total += pos["shares"] * price
    return total


def _sell(symbol, pos, df, date, config, reason="rebalance"):
    price = _price_on(df, date, config.trade_price)
    exec_price = price * (1 - config.slippage)
    gross = pos["shares"] * exec_price
    cost = max(gross * config.commission_rate, config.min_commission) + gross * config.transfer_fee_rate + gross * config.stamp_tax_rate
    pnl = gross - cost - pos["shares"] * pos["entry_price"] - pos.get("entry_cost", 0)
    return gross - cost, cost, {
        "symbol": symbol,
        "entry_date": pos["entry_date"].date().isoformat(),
        "exit_date": date.date().isoformat(),
        "shares": pos["shares"],
        "entry_price": round(pos["entry_price"], 4),
        "exit_price": round(exec_price, 4),
        "pnl": round(pnl, 2),
        "return_pct": round(pnl / (pos["shares"] * pos["entry_price"]) * 100, 2),
        "cost": round(cost + pos.get("entry_cost", 0), 2),
        "hold_days": (date - pos["entry_date"]).days,
        "reason": reason,
    }


def _profit_loss_ratio(wins, losses):
    if not wins or not losses:
        return None
    return round((sum(t["pnl"] for t in wins) / len(wins)) / abs(sum(t["pnl"] for t in losses) / len(losses)), 2)


def _drawdown_curve(equity):
    if not equity:
        return []
    values = pd.Series([item["equity"] for item in equity])
    peaks = values.cummax()
    dd = values / peaks - 1
    return [{"date": equity[i]["date"], "drawdown": round(float(dd.iloc[i]) * 100, 2)} for i in range(len(equity))]
