"""Evidence-first virtual investment committee with persisted role execution."""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any, Callable

from app.repositories.database import get_agent_task, update_agent_task
from app.services.data.service import data_provider
from app.services.market import build_market_panorama
from app.services.portfolio.analytics import build_portfolio_analytics


ROLE_LABELS = {
    "macro": "宏观与市场研究员",
    "fundamental": "基本面研究员",
    "valuation": "估值与价值研究员",
    "industry": "行业与产业研究员",
    "trend": "趋势与交易结构研究员",
    "risk": "组合风险经理",
    "contrarian": "反方审查员",
    "chair": "投委会主席",
}

TASK_ROLES = {
    "holding_logic": ["fundamental", "valuation", "industry", "trend", "risk", "contrarian"],
    "market_impact": ["macro", "industry", "trend", "risk", "contrarian"],
}


def run_committee_task(task_id: str, only_role: str | None = None) -> None:
    task = get_agent_task(task_id)
    if not task:
        return
    payload = task["input"]
    roles = TASK_ROLES.get(task["task_type"], TASK_ROLES["holding_logic"])
    if only_role and only_role in roles:
        roles = [only_role]
    role_runs = task.get("role_runs") or [_waiting_role(role) for role in TASK_ROLES.get(task["task_type"], roles)]
    update_agent_task(task_id, status="running", role_runs=role_runs, error=None)
    try:
        for role in roles:
            latest = get_agent_task(task_id)
            if latest and latest.get("cancel_requested"):
                update_agent_task(task_id, status="cancelled", role_runs=role_runs)
                return
            role_runs = _set_role(role_runs, role, status="fetching", error=None)
            update_agent_task(task_id, role_runs=role_runs)
            analyzer = ROLE_ANALYZERS[role]
            role_payload = {**payload, "prior_role_runs": role_runs} if role == "contrarian" else payload
            result = analyzer(role_payload)
            role_runs = _set_role(role_runs, role, status=result.get("status", "completed"), **result)
            update_agent_task(task_id, role_runs=role_runs)
        completed = [item for item in role_runs if item.get("status") in {"completed", "insufficient"}]
        chairman = synthesize_chairman(task["task_type"], payload, completed)
        final_runs = [item for item in role_runs if item["role"] != "chair"] + [{"role": "chair", "label": ROLE_LABELS["chair"], "status": "completed", **chairman["chair_run"]}]
        update_agent_task(task_id, status="completed", role_runs=final_runs, result=chairman["result"])
    except Exception as exc:
        update_agent_task(task_id, status="failed", role_runs=role_runs, error=str(exc))


def analyze_fundamental(payload: dict) -> dict:
    symbol = payload.get("symbol")
    result = data_provider.request("get_financial_factors", [symbol], required_fields=["roe", "revenue_growth", "profit_growth"])
    rows = result.data if result.ok and isinstance(result.data, list) else []
    row = rows[0] if rows else {}
    evidence = _fields(row, ["roe", "revenue_growth", "profit_growth", "gross_margin", "debt_ratio"], result.meta())
    available = [item for item in evidence if item["value"] is not None]
    conclusion = "经营数据不足，不能确认原始逻辑" if not available else "经营质量需结合增长与盈利能力继续核验"
    return _role_result(conclusion, evidence, result.meta(), ["盈利质量恶化或现金流持续弱于利润时原逻辑失效"])


def analyze_valuation(payload: dict) -> dict:
    symbol = payload.get("symbol")
    result = data_provider.request("get_basic_factors", [symbol], required_fields=["pe_ttm", "pb"])
    row = result.data[0] if result.ok and isinstance(result.data, list) and result.data else {}
    evidence = _fields(row, ["pe_ttm", "pb", "market_cap"], result.meta())
    pe = row.get("pe_ttm")
    conclusion = "估值数据不足" if pe is None else "当前估值为正，仍需历史分位与盈利预期判断安全边际" if pe > 0 else "市盈率不可直接解释，需检查盈利为负或数据口径"
    return _role_result(conclusion, evidence, result.meta(), ["估值超过用户设定上限或盈利预期下修时重新评估"])


def analyze_industry(payload: dict) -> dict:
    symbol = payload.get("symbol")
    profile = data_provider.request("get_stock_profile", symbol, required_fields=["industry"])
    sector = data_provider.request("get_sector_snapshot", required_fields=["name", "change_pct"])
    industry = profile.data.get("industry") if profile.ok and isinstance(profile.data, dict) else None
    match = next((item for item in (sector.data or []) if industry and industry in str(item.get("name"))), None) if sector.ok else None
    evidence = [{"field": "industry", "value": industry, "date": profile.data_date, "source": _source(profile)}]
    if match:
        evidence.append({"field": "sector_change_pct", "value": match.get("change_pct"), "date": sector.data_date, "source": match.get("source") or _source(sector)})
    missing = {**profile.missing_fields, **({} if match else {"sector_match": "未找到与个股行业一致的板块快照"})}
    conclusion = f"所属行业为{industry}，板块短期表现{match.get('change_pct'):+.2f}%" if industry and match and match.get("change_pct") is not None else "行业归属或景气证据不足"
    return _role_result(conclusion, evidence, {**profile.meta(), "missing_fields": missing}, ["行业景气、价格或订单趋势反转时原逻辑失效"])


def analyze_trend(payload: dict) -> dict:
    symbol = payload.get("symbol")
    end = date.today()
    start = end - timedelta(days=160)
    result = data_provider.request("get_stock_daily", symbol, start.isoformat(), end.isoformat(), "qfq", required_fields=["trade_date", "close"])
    rows = [row for row in (result.data or []) if row.get("close") is not None]
    closes = [float(row["close"]) for row in rows]
    ma20 = mean(closes[-20:]) if len(closes) >= 20 else None
    ma60 = mean(closes[-60:]) if len(closes) >= 60 else None
    latest = closes[-1] if closes else None
    peak = max(closes) if closes else None
    drawdown = (latest / peak - 1) * 100 if latest is not None and peak else None
    evidence = [
        {"field": "close", "value": latest, "date": rows[-1]["trade_date"] if rows else None, "source": rows[-1].get("source") if rows else _source(result)},
        {"field": "ma20", "value": round(ma20, 4) if ma20 else None, "date": result.data_date, "source": _source(result)},
        {"field": "ma60", "value": round(ma60, 4) if ma60 else None, "date": result.data_date, "source": _source(result)},
        {"field": "drawdown_from_window_peak_pct", "value": round(drawdown, 4) if drawdown is not None else None, "date": result.data_date, "source": _source(result)},
    ]
    if latest is None:
        conclusion = "趋势行情不足"
    elif ma20 and ma60:
        conclusion = "趋势偏强" if latest > ma20 > ma60 else "趋势偏弱" if latest < ma20 < ma60 else "趋势分歧"
    else:
        conclusion = "历史不足，无法确认中期趋势"
    return _role_result(conclusion, evidence, result.meta(), ["跌破用户失效价位或中期结构持续转弱时退出原判断"])


def analyze_risk(payload: dict) -> dict:
    holdings = payload.get("holdings") or ([payload.get("position")] if payload.get("position") else [])
    holdings = [item for item in holdings if item]
    result = build_portfolio_analytics(holdings)
    metrics = result.get("metrics") or {}
    evidence = [{"field": key, "value": metrics.get(key), "date": result.get("as_of"), "source": "portfolio-analytics"} for key in ("max_single_exposure_pct", "industry_concentration_pct", "max_drawdown_pct", "annualized_volatility_pct")]
    concentration = metrics.get("max_single_exposure_pct")
    conclusion = "组合历史不足，风险无法完整量化" if not result.get("ok") else "单股暴露偏高" if concentration is not None and concentration >= 35 else "当前单股暴露未超过35%观察线"
    return _role_result(conclusion, evidence, {"missing_fields": result.get("missing_fields") or {}, "completeness": _completeness(evidence), "data_date": result.get("as_of"), "sources": []}, ["单股暴露超过风险预算或组合回撤突破阈值时需减仓"])


def analyze_macro(payload: dict) -> dict:
    data = build_market_panorama()
    breadth = data.get("breadth") or {}
    indices = data.get("indices") or []
    evidence = [
        {"field": "up_ratio", "value": breadth.get("up_ratio"), "date": data.get("as_of"), "source": breadth.get("source") or _source_dict(data)},
        {"field": "median_change", "value": breadth.get("median_change"), "date": data.get("as_of"), "source": breadth.get("source") or _source_dict(data)},
        {"field": "index_direction", "value": {item.get("name"): item.get("change_pct") for item in indices}, "date": data.get("as_of"), "source": "normalized-index-history"},
    ]
    ratio = breadth.get("up_ratio")
    conclusion = "市场宽度数据不足" if ratio is None else "市场风险偏好偏强" if ratio >= .58 else "市场风险偏好偏弱" if ratio <= .42 else "市场分歧"
    return _role_result(conclusion, evidence, {"missing_fields": data.get("missing_fields") or {}, "completeness": data.get("completeness"), "data_date": data.get("as_of"), "sources": data.get("provenance") or []}, ["市场宽度与指数趋势同步转弱时降低组合风险预算"])


def analyze_contrarian(payload: dict) -> dict:
    prior = payload.get("prior_role_runs") or []
    missing = []
    dates = set()
    for run in prior:
        missing.extend(run.get("missing_data") or [])
        dates.update(str(item.get("date")) for item in run.get("evidence") or [] if item.get("date"))
    evidence = [{"field": "missing_count", "value": len(set(missing)), "date": date.today().isoformat(), "source": "committee-audit"},
                {"field": "evidence_date_count", "value": len(dates), "date": date.today().isoformat(), "source": "committee-audit"}]
    conclusion = f"发现{len(set(missing))}项缺失证据与{max(len(dates)-1, 0)}组日期差异" if missing or len(dates) > 1 else "未发现明显证据缺口，但结论仍需用户确认"
    return _role_result(conclusion, evidence, {"missing_fields": {str(i): value for i, value in enumerate(set(missing))}, "completeness": 1 if not missing else 0.5, "data_date": date.today().isoformat(), "sources": []}, ["任何核心证据无法复现或日期错配时，主席结论失效"])


ROLE_ANALYZERS: dict[str, Callable[[dict], dict]] = {
    "macro": analyze_macro, "fundamental": analyze_fundamental, "valuation": analyze_valuation,
    "industry": analyze_industry, "trend": analyze_trend, "risk": analyze_risk,
    "contrarian": analyze_contrarian,
}


def synthesize_chairman(task_type: str, payload: dict, role_runs: list[dict]) -> dict:
    missing = sorted({item for run in role_runs for item in (run.get("missing_data") or [])})
    complete_values = [run.get("completeness") for run in role_runs if run.get("completeness") is not None]
    completeness = round(mean(complete_values) * 100, 1) if complete_values else 0
    negative = [run for run in role_runs if any(word in run.get("conclusion", "") for word in ("偏弱", "偏高", "不足", "失效"))]
    positive = [run for run in role_runs if any(word in run.get("conclusion", "") for word in ("偏强", "未超过"))]
    if negative:
        conclusion, action = "持有观察，先补证据并执行风险约束", "HOLD"
    elif positive:
        conclusion, action = "原逻辑暂未被现有证据否定，继续跟踪", "HOLD"
    else:
        conclusion, action = "证据分歧，暂不改变持仓", "WAIT"
    support = [run["conclusion"] for run in positive] or [run["conclusion"] for run in role_runs if run["role"] != "contrarian"][:2]
    oppose = [run["conclusion"] for run in negative] or ["反方未发现足以推翻结论的完整证据，但样本仍有限"]
    invalidation = sorted({condition for run in role_runs for condition in (run.get("invalidation_conditions") or [])})
    result = {
        "conclusion": conclusion, "action": action, "supporting_reasons": support,
        "opposing_reasons": oppose, "disagreements": _disagreements(role_runs),
        "missing_data": missing, "evidence_completeness_pct": completeness,
        "invalidation_conditions": invalidation, "next_step": "由用户核验原始理由与失效条件后保存为待确认决策",
        "review_date": (date.today() + timedelta(days=20)).isoformat(),
        "disclaimer": "这是基于有限公开数据和用户记录的研究意见，不构成收益承诺，不会自动执行交易。",
    }
    return {"result": result, "chair_run": {"conclusion": conclusion, "evidence": [], "missing_data": missing, "uncertainty": "主席不平均评分，按反方风险、数据缺口和可证伪条件作出结论", "invalidation_conditions": invalidation, "completeness": completeness / 100}}


def _role_result(conclusion: str, evidence: list[dict], meta: dict, invalidation: list[str]) -> dict:
    missing = list((meta.get("missing_fields") or {}).values())
    completeness = meta.get("completeness")
    if completeness is None:
        completeness = _completeness(evidence)
    return {"status": "insufficient" if not any(item.get("value") is not None for item in evidence) else "completed", "conclusion": conclusion,
            "evidence": evidence, "missing_data": missing, "uncertainty": "仅使用已列出的证据，未返回字段不参与判断",
            "invalidation_conditions": invalidation, "completeness": completeness}


def _waiting_role(role: str) -> dict:
    return {"role": role, "label": ROLE_LABELS[role], "status": "waiting", "conclusion": None, "evidence": [], "missing_data": [], "uncertainty": None, "invalidation_conditions": [], "completeness": None}


def _set_role(role_runs: list[dict], role: str, **changes) -> list[dict]:
    found = False
    updated = []
    for item in role_runs:
        if item["role"] == role:
            updated.append({**item, **changes, "role": role, "label": ROLE_LABELS[role]})
            found = True
        else:
            updated.append(item)
    if not found:
        updated.append({**_waiting_role(role), **changes})
    return updated


def _fields(row: dict, fields: list[str], meta: dict) -> list[dict]:
    return [{"field": field, "value": row.get(field), "date": meta.get("data_date"), "source": row.get("source") or _source_meta(meta)} for field in fields]


def _source(result) -> str | None:
    return next((item.source for item in result.provenance if item.status == "ok"), None)


def _source_meta(meta: dict) -> str | None:
    return next((item.get("source") for item in meta.get("sources") or [] if item.get("status") == "ok"), None)


def _source_dict(payload: dict) -> str | None:
    return next((item.get("source") for item in payload.get("provenance") or [] if item.get("status") == "ok"), None)


def _completeness(evidence: list[dict]) -> float:
    return round(sum(item.get("value") is not None for item in evidence) / len(evidence), 4) if evidence else 0


def _disagreements(role_runs: list[dict]) -> list[str]:
    conclusions = [f"{run['label']}：{run.get('conclusion')}" for run in role_runs if run.get("conclusion")]
    return conclusions if len(conclusions) > 1 else []
