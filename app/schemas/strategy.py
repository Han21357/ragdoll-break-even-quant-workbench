"""Strategy DSL schema and validation."""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_OPERATORS = {
    ">",
    ">=",
    "<",
    "<=",
    "==",
    "between",
    "cross_above",
    "cross_below",
    "top_percentile",
    "bottom_percentile",
}


class Condition(BaseModel):
    factor: str
    operator: str
    value: Any = None
    lookback: Optional[int] = Field(default=None, ge=1, le=500)
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator("operator")
    @classmethod
    def operator_is_safe(cls, value: str) -> str:
        if value not in ALLOWED_OPERATORS:
            raise ValueError(f"unsupported operator: {value}")
        return value

    @field_validator("factor")
    @classmethod
    def factor_is_identifier(cls, value: str) -> str:
        if "__" in value or "(" in value or ")" in value or ";" in value:
            raise ValueError("factor must be a registered factor id, not executable code")
        return value


class ConditionGroup(BaseModel):
    logic: Literal["AND", "OR", "NOT"] = "AND"
    conditions: list[Union[Condition, "ConditionGroup"]] = Field(default_factory=list)
    enabled: bool = True

    @model_validator(mode="after")
    def not_has_one_child(self):
        if self.logic == "NOT" and len(self.conditions) != 1:
            raise ValueError("NOT groups must contain exactly one child")
        return self


class StrategyDSL(BaseModel):
    id: str
    name: str
    description: str = ""
    universe: dict[str, Any] = Field(default_factory=lambda: {"market": "A股", "exclude_st": True, "min_listed_days": 120})
    frequency: str = "daily"
    price_adjustment: str = "qfq"
    entry_conditions: ConditionGroup
    exit_conditions: ConditionGroup = Field(default_factory=lambda: ConditionGroup(logic="OR", conditions=[]))
    ranking: list[Condition] = Field(default_factory=list)
    portfolio: dict[str, Any] = Field(default_factory=lambda: {"max_positions": 20, "single_position_limit": 0.2})
    execution: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    benchmark: str = "sh.000300"
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


ConditionGroup.model_rebuild()
