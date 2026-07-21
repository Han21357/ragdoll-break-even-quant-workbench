"""Natural-language strategy compiler with explicit assumptions."""
from __future__ import annotations

import re
import time

from app.schemas.strategy import Condition, ConditionGroup, StrategyDSL


def compile_strategy_from_text(text: str) -> dict:
    original = (text or "").strip()
    if not original:
        raise ValueError("投资想法不能为空")
    semantic = []
    conditions = []
    ambiguities = []
    max_positions = _extract_int(original, r"(?:最多(?:持有)?|最大持仓|持有不超过)\s*(\d+)\s*只", 10)
    holding_days = _extract_int(original, r"(?:持有|持仓周期)\s*(\d+)\s*(?:天|日)", 20)
    stop_loss = _extract_percent(original, r"(?:止损|回撤)\s*-?\s*(\d+(?:\.\d+)?)\s*%", 0.08)
    take_profit = _extract_percent(original, r"(?:止盈|盈利)\s*\+?\s*(\d+(?:\.\d+)?)\s*%", 0.20)
    rebalance = "monthly" if "月度调仓" in original or "每月" in original else "daily" if "每日调仓" in original else "weekly"

    if "低于100" in original or "低于 100" in original or "100元" in original:
        semantic.append({"text": "价格低于100元", "definition": "close < 100"})
        conditions.append(Condition(factor="close", operator="<", value=100))
    if "下行通道" in original:
        semantic.append({"text": "没有进入下行通道", "definition": "close >= MA20 AND slope(MA20, 5) >= 0"})
        conditions.append(Condition(factor="distance_MA20", operator=">=", value=0))
        conditions.append(Condition(factor="MA20_slope", operator=">=", value=0, lookback=5))
    if "5日" in original and ("大涨" in original or "涨幅" in original):
        semantic.append({"text": "近5日没有大涨", "definition": "return_5d <= 12%"})
        conditions.append(Condition(factor="return_5d", operator="<=", value=0.12, lookback=5))
    if "行业" in original and ("景气" in original or "动量" in original or "较强" in original):
        semantic.append({"text": "行业景气较强", "definition": "industry_momentum_20d top_percentile 30"})
        conditions.append(Condition(factor="industry_momentum_20d", operator="top_percentile", value=30, lookback=20))
        ambiguities.append({
            "term": "行业景气较强",
            "options": ["行业20日涨跌幅前30%", "行业成交额20日变化前30%", "行业相对沪深300超额收益前30%"],
            "selected": "行业20日涨跌幅前30%",
            "data_status": "partial",
        })
    if "机构关注" in original or "分析师" in original:
        semantic.append({"text": "机构关注增加", "definition": "analyst_coverage_60d_change > 0"})
        conditions.append(Condition(factor="analyst_coverage_60d_change", operator=">", value=0, lookback=60, enabled=False))
        ambiguities.append({
            "term": "机构关注增加",
            "options": ["近60日覆盖机构数增加", "近60日分析师人数增加", "首次出现买入评级"],
            "selected": "近60日覆盖机构数增加",
            "data_status": "unavailable",
            "message": "当前正式数据层尚未接入可验证研报覆盖数据，因此默认禁用该条件。",
        })

    if not conditions:
        semantic.append({"text": "投资想法", "definition": "需要用户选择因子、阈值和股票池"})
        ambiguities.append({"term": original[:30], "message": "尚未匹配到可执行因子，请在规则编辑器中补充。"})

    dsl = StrategyDSL(
        id=f"strategy_{int(time.time())}",
        name="自然语言策略草案",
        description=original,
        entry_conditions=ConditionGroup(logic="AND", conditions=conditions),
        portfolio={"max_positions": max_positions, "single_position_limit": min(0.2, 1 / max(max_positions, 1))},
        execution={"rebalance_frequency": rebalance, "holding_days": holding_days},
        risk={"stop_loss": stop_loss, "take_profit": take_profit},
        metadata={
            "original_text": original,
            "compiler": "rule_based_pydantic_v1",
            "requires_user_confirmation": True,
        },
    )
    return {
        "original_text": original,
        "semantic_breakdown": semantic,
        "dsl": dsl.model_dump(),
        "ambiguities": ambiguities,
        "assumptions": [
            "未让 LLM 生成任意 Python；所有条件必须通过因子注册表和 Pydantic 校验。",
            "未明确说明时，默认每周调仓、持有20日、止损8%、止盈20%、最多10只；确认页允许逐项修改。",
        ],
    }


def _extract_int(text: str, pattern: str, default: int) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else default


def _extract_percent(text: str, pattern: str, default: float) -> float:
    match = re.search(pattern, text)
    return float(match.group(1)) / 100 if match else default
