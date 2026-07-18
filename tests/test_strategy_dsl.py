import pytest

from app.schemas.strategy import Condition, ConditionGroup, StrategyDSL
from app.services.strategies.compiler import compile_strategy_from_text
from app.services.strategies.validator import validate_strategy_payload


def _valid_payload():
    return StrategyDSL(
        id="s1",
        name="test",
        entry_conditions=ConditionGroup(logic="AND", conditions=[Condition(factor="close", operator="<", value=100)]),
    ).model_dump()


def test_valid_condition_passes():
    result = validate_strategy_payload(_valid_payload())
    assert result["ok"] is True


def test_illegal_factor_rejected():
    payload = _valid_payload()
    payload["entry_conditions"]["conditions"][0]["factor"] = "unknown_factor"
    result = validate_strategy_payload(payload)
    assert result["ok"] is False


def test_illegal_operator_rejected():
    with pytest.raises(ValueError):
        Condition(factor="close", operator="exec", value="x")


def test_arbitrary_python_factor_rejected():
    with pytest.raises(ValueError):
        Condition(factor="__import__('os').system('ls')", operator=">", value=0)


def test_compiler_marks_unavailable_institutional_attention_disabled():
    result = compile_strategy_from_text("机构关注增加的股票")
    conditions = result["dsl"]["entry_conditions"]["conditions"]
    assert conditions[0]["factor"] == "analyst_coverage_60d_change"
    assert conditions[0]["enabled"] is False
    assert result["ambiguities"][0]["data_status"] == "unavailable"

