"""Backtest request and result schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    strategy_id: Optional[str] = None
    stocks: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    rebalance_frequency: str = "monthly"
    max_positions: int = Field(default=10, ge=1, le=100)
    initial_capital: float = Field(default=100000.0, gt=0)
    single_position_limit: float = Field(default=0.2, gt=0, le=1)
    trade_price: str = "close"
    commission_rate: float = Field(default=0.0003, ge=0)
    min_commission: float = Field(default=5.0, ge=0)
    stamp_tax_rate: float = Field(default=0.001, ge=0)
    transfer_fee_rate: float = Field(default=0.00001, ge=0)
    slippage: float = Field(default=0.0005, ge=0)
    sellable_after_days: int = Field(default=1, ge=0)
    lot_size: int = Field(default=100, ge=1)
    benchmark: str = "sh.000300"
    exclude_st: bool = True
    price_adjustment: str = "qfq"
    hold_days: Optional[int] = Field(default=None, ge=1)
