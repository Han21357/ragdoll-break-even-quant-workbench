"""Deterministic factor calculations from normalized daily bars."""
from __future__ import annotations

import math

import pandas as pd


def enrich_daily_factors(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("trade_date").copy()
    for col in ["open", "high", "low", "close", "volume", "amount", "turnover_rate", "pct_change"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    close = df["close"]
    df["return_1d"] = close.pct_change()
    for window in [5, 10, 20, 60]:
        df[f"return_{window}d"] = close.pct_change(window)
        df[f"MA{window}"] = close.rolling(window).mean()
    df["MA20_slope"] = df["MA20"] - df["MA20"].shift(5)
    df["distance_MA20"] = close / df["MA20"] - 1
    df["distance_MA60"] = close / df["MA60"] - 1
    df["volatility_20d"] = df["return_1d"].rolling(20).std() * math.sqrt(252)
    df["volatility_60d"] = df["return_1d"].rolling(60).std() * math.sqrt(252)
    df["max_drawdown_20d"] = close / close.rolling(20).max() - 1
    df["max_drawdown_60d"] = close / close.rolling(60).max() - 1
    df["ma_alignment"] = (df["MA5"] >= df["MA10"]) & (df["MA10"] >= df["MA20"])
    df["recent_high"] = close >= df["high"].rolling(20).max()
    df["recent_low"] = close <= df["low"].rolling(20).min()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    df["RSI14"] = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_histogram"] = df["MACD"] - df["MACD_signal"]
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    df["volume_change"] = df["volume"].pct_change(5)
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df["OBV"] = (direction * df["volume"].fillna(0)).cumsum()
    true_range = pd.concat([
        df["high"] - df["low"],
        (df["high"] - close.shift()).abs(),
        (df["low"] - close.shift()).abs(),
    ], axis=1).max(axis=1)
    df["ATR"] = true_range.rolling(14).mean()
    return df


def latest_factor_snapshot(symbol: str, rows: list[dict]) -> dict:
    df = enrich_daily_factors(rows)
    if df.empty:
        return {"symbol": symbol, "status": "unavailable", "reason": "no daily rows"}
    latest = df.iloc[-1].to_dict()
    latest["symbol"] = symbol
    latest["status"] = "ok"
    return latest

