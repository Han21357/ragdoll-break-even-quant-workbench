"""Strategy validation against factor availability."""
from __future__ import annotations

from app.schemas.strategy import ConditionGroup, StrategyDSL
from app.services.factors.registry import FACTOR_REGISTRY, validate_factors


def collect_factor_ids(group: ConditionGroup) -> list[str]:
    factors: list[str] = []
    for child in group.conditions:
        if isinstance(child, ConditionGroup):
            factors.extend(collect_factor_ids(child))
        elif child.enabled:
            factors.append(child.factor)
    return factors


def validate_strategy_payload(payload: dict, require_available: bool = True) -> dict:
    dsl = StrategyDSL.model_validate(payload)
    factors = collect_factor_ids(dsl.entry_conditions) + collect_factor_ids(dsl.exit_conditions)
    factors.extend(item.factor for item in dsl.ranking if item.enabled)
    ok, errors = validate_factors(factors, require_available=require_available)
    availability = []
    for factor_id in sorted(set(factors)):
        item = FACTOR_REGISTRY.get(factor_id)
        availability.append({
            "factor": factor_id,
            "status": item.status if item else "missing",
            "source": item.data_source if item else None,
            "message": None if item else "未注册因子",
        })
    return {
        "ok": ok,
        "errors": errors,
        "dsl": dsl.model_dump(),
        "data_availability": availability,
    }

