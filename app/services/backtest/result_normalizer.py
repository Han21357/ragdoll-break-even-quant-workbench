"""Normalize backtest metrics and series."""
from __future__ import annotations

import math

import pandas as pd


def max_drawdown(equity: list[dict]) -> tuple[float, dict | None]:
    if not equity:
        return 0.0, None
    df = pd.DataFrame(equity)
    values = df["equity"].astype(float)
    peaks = values.cummax()
    dd = values / peaks - 1
    idx = dd.idxmin()
    peak_idx = values.loc[:idx].idxmax()
    return round(float(dd.loc[idx]) * 100, 2), {
        "peak_date": df.loc[peak_idx, "date"],
        "trough_date": df.loc[idx, "date"],
        "drawdown_pct": round(float(dd.loc[idx]) * 100, 2),
    }


def annualized_return(equity: list[dict]) -> float:
    if len(equity) < 2:
        return 0.0
    start = pd.to_datetime(equity[0]["date"])
    end = pd.to_datetime(equity[-1]["date"])
    years = max((end - start).days / 365.25, 1 / 365.25)
    total = equity[-1]["equity"] / equity[0]["equity"] - 1
    return round(((1 + total) ** (1 / years) - 1) * 100, 2)


def periodic_stats(equity: list[dict]) -> dict:
    if len(equity) < 2:
        return {"volatility": 0, "sharpe": 0, "sortino": 0, "positive_period_rate": 0}
    df = pd.DataFrame(equity)
    returns = df["equity"].pct_change().dropna()
    vol = returns.std() * math.sqrt(252)
    excess = returns.mean() * 252 - 0.03
    downside = returns[returns < 0].std() * math.sqrt(252)
    return {
        "volatility": round(vol * 100, 2) if pd.notna(vol) else 0,
        "sharpe": round(excess / vol, 2) if vol and pd.notna(vol) else 0,
        "sortino": round(excess / downside, 2) if downside and pd.notna(downside) else 0,
        "positive_period_rate": round((returns > 0).mean() * 100, 1) if len(returns) else 0,
    }


def monthly_returns(equity: list[dict]) -> dict:
    if not equity:
        return {}
    df = pd.DataFrame(equity)
    df["date"] = pd.to_datetime(df["date"])
    month_end = df.set_index("date")["equity"].resample("ME").last()
    returns = month_end.pct_change().dropna()
    return {idx.strftime("%Y-%m"): round(value * 100, 2) for idx, value in returns.items()}

