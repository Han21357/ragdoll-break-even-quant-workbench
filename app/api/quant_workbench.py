"""API routes for the AI quantitative workbench."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from app.repositories.database import (
    get_backtest,
    get_evidence_snapshot,
    get_strategy,
    init_db,
    insert_review,
    insert_decision,
    list_decisions,
    list_portfolios,
    list_reviews,
    list_strategies,
    list_watchlist,
    save_evidence_snapshot,
    save_strategy_version,
    upsert_backtest,
    upsert_portfolio,
    upsert_strategy,
    upsert_watchlist,
    update_decision_result,
)
from app.schemas.strategy import StrategyDSL
from app.services.backtest.engine import run_backtest
from app.services.data.service import data_provider
from app.services.factors.registry import get_factor, list_factors
from app.services.market import build_market_panorama
from app.services.strategies.compiler import compile_strategy_from_text
from app.services.strategies.screener import run_screening
from app.services.strategies.validator import validate_strategy_payload

bp = Blueprint("quant_workbench", __name__, url_prefix="/api")
_memory_tasks: dict[str, dict] = {}
_TASK_TTL_SECONDS = 3600


def register_quant_workbench(app):
    init_db()
    app.register_blueprint(bp)
    from app.api.investment_workflow import bp as investment_workflow_bp
    app.register_blueprint(investment_workflow_bp)


def _clean_tasks():
    now = time.time()
    for task_id, task in list(_memory_tasks.items()):
        if now - task.get("created_ts", now) > _TASK_TTL_SECONDS:
            _memory_tasks.pop(task_id, None)


@bp.get("/data/status")
def data_status():
    status = data_provider.status()
    return jsonify({**status, "generated_at": datetime.now().isoformat(timespec="seconds")})


@bp.get("/data/coverage")
def data_coverage():
    return jsonify({
        "policy": "缺失值使用 null，并返回 missing_fields 中的具体原因；不使用0冒充数据。",
        "provider_order": [provider.name for provider in data_provider.registry.providers],
        "cache": {"memory": "进程内TTL", "persistent": "本地原子JSON", "stale_fallback": True, "incremental_snapshots": ["板块轮动"]},
        "fields": {
            "market": ["breadth", "median_change", "amount", "index_history", "volatility_20d", "volatility_60d", "sectors", "rotation_persistence"],
            "portfolio": ["adjusted_price", "today_return", "cumulative_return", "max_drawdown", "volatility", "position", "industry_concentration", "single_exposure", "equity_curve"],
            "strategy": ["universe", "daily", "valuation", "financials", "fund_flow", "sector", "research_reports"],
            "research": ["evidence_value", "data_date", "source", "missing_reason", "news", "announcements"],
            "review": ["decision", "evidence_snapshot", "due_price", "holding_result"],
        },
    })


@bp.get("/market/overview")
def market_overview():
    panorama = build_market_panorama()
    breadth = dict(panorama.get("breadth") or {})
    source = next((item.get("source") for item in panorama.get("provenance", []) if item.get("status") == "ok"), None)
    breadth["source"] = source
    return jsonify({
        "ok": panorama["ok"],
        "overview": breadth,
        "source_status": {"status": panorama["status"], "sources": panorama.get("provenance", [])},
    }), 200 if panorama["ok"] else 503


@bp.get("/market/regime")
def market_regime():
    panorama = build_market_panorama()
    regime = dict(panorama.get("regime") or {})
    regime.setdefault("volatility", "中")
    regime.setdefault("style", "均衡")
    regime.setdefault("as_of", panorama.get("as_of"))
    return jsonify({
        "ok": panorama["ok"],
        "regime": regime,
        "source_status": {"status": panorama["status"], "sources": panorama.get("provenance", [])},
    }), 200 if panorama["ok"] else 503


@bp.get("/market/panorama")
def market_panorama():
    data = build_market_panorama()
    status = 200 if data.get("ok") else 503
    return jsonify(data), status


@bp.get("/factors")
def factors():
    return jsonify({"factors": list_factors()})


@bp.get("/factors/<factor_id>")
def factor_detail(factor_id):
    factor = get_factor(factor_id)
    if not factor:
        return jsonify({"error": "factor not found"}), 404
    return jsonify(factor)


@bp.post("/factors/analyze")
def factor_analyze():
    payload = request.get_json() or {}
    factor_id = payload.get("factor_id", "close")
    factor = get_factor(factor_id)
    if not factor:
        return jsonify({"ok": False, "error": "未知因子"}), 400
    return jsonify({
        "ok": factor["status"] != "unavailable",
        "factor": factor,
        "analysis": {
            "coverage": factor["coverage"],
            "data_quality": factor["status"],
            "notes": "P1 因子分层收益、IC、Rank IC 和换手接口已预留；正式分析需要截面因子矩阵。",
        },
    })


@bp.post("/strategies/compile")
@bp.post("/ai/strategy-compile")
def strategy_compile():
    payload = request.get_json() or {}
    try:
        return jsonify({"ok": True, **compile_strategy_from_text(payload.get("text") or payload.get("idea") or "")})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.post("/strategies/validate")
def strategy_validate():
    payload = request.get_json() or {}
    try:
        return jsonify(validate_strategy_payload(payload.get("dsl") or payload))
    except Exception as exc:
        return jsonify({"ok": False, "errors": [str(exc)]}), 400


@bp.get("/strategies")
def strategies_list():
    return jsonify({"strategies": list_strategies()})


@bp.post("/strategies")
def strategy_create():
    payload = request.get_json() or {}
    dsl_payload = payload.get("dsl") or payload
    validation = validate_strategy_payload(dsl_payload, require_available=False)
    if not validation["ok"]:
        return jsonify(validation), 400
    dsl = StrategyDSL.model_validate(validation["dsl"])
    saved = upsert_strategy(dsl.id, dsl.name, dsl.model_dump())
    version = save_strategy_version(dsl.id, payload.get("version", "v1.0"), dsl.model_dump(), payload.get("note", "initial version"))
    return jsonify({"ok": True, "strategy": saved, "version": version})


@bp.get("/strategies/<strategy_id>")
def strategy_get(strategy_id):
    strategy = get_strategy(strategy_id)
    if not strategy:
        return jsonify({"error": "strategy not found"}), 404
    return jsonify(strategy)


@bp.post("/strategies/<strategy_id>/version")
def strategy_version(strategy_id):
    strategy = get_strategy(strategy_id)
    if not strategy:
        return jsonify({"error": "strategy not found"}), 404
    payload = request.get_json() or {}
    dsl_payload = payload.get("dsl") or strategy["dsl"]
    validation = validate_strategy_payload(dsl_payload, require_available=False)
    if not validation["ok"]:
        return jsonify(validation), 400
    saved = save_strategy_version(strategy_id, payload.get("version", f"v{int(time.time())}"), validation["dsl"], payload.get("note", ""))
    upsert_strategy(strategy_id, validation["dsl"].get("name", strategy["name"]), validation["dsl"])
    return jsonify({"ok": True, "version": saved})


@bp.post("/strategies/<strategy_id>/screen")
def strategy_screen(strategy_id):
    strategy = get_strategy(strategy_id)
    if not strategy:
        return jsonify({"error": "strategy not found"}), 404
    payload = request.get_json() or {}
    result = run_screening(payload.get("dsl") or strategy["dsl"], payload.get("symbols"))
    status = 200 if result.get("ok") else 422
    return jsonify(result), status


@bp.post("/backtests")
def backtest_create():
    payload = request.get_json() or {}
    task_id = f"bt_{uuid.uuid4().hex[:10]}"
    _clean_tasks()
    _memory_tasks[task_id] = {"status": "running", "created_ts": time.time(), "stage": "loading_data"}
    upsert_backtest(task_id, "running", payload, strategy_id=payload.get("strategy_id"))

    def _runner():
        try:
            result = run_backtest(payload)
            if not result.get("ok"):
                _memory_tasks[task_id] = {"status": "error", "created_ts": time.time(), "error": result.get("error"), "result": result}
                upsert_backtest(task_id, "error", payload, result=result, error=result.get("error"), strategy_id=payload.get("strategy_id"))
                return
            _memory_tasks[task_id] = {"status": "done", "created_ts": time.time(), "result": result}
            upsert_backtest(task_id, "done", payload, result=result, strategy_id=payload.get("strategy_id"))
        except Exception as exc:
            _memory_tasks[task_id] = {"status": "error", "created_ts": time.time(), "error": str(exc)}
            upsert_backtest(task_id, "error", payload, error=str(exc), strategy_id=payload.get("strategy_id"))

    threading.Thread(target=_runner, daemon=True).start()
    return jsonify({"task_id": task_id, "status": "running"})


@bp.get("/backtests/<task_id>")
def backtest_task(task_id):
    task = _memory_tasks.get(task_id)
    if task:
        return jsonify(task)
    stored = get_backtest(task_id)
    if not stored:
        return jsonify({"error": "task not found"}), 404
    return jsonify(stored)


@bp.get("/backtests/<task_id>/result")
def backtest_result(task_id):
    stored = get_backtest(task_id)
    if not stored:
        task = _memory_tasks.get(task_id)
        if task and task.get("result"):
            return jsonify(task["result"])
        return jsonify({"error": "result not found"}), 404
    return jsonify(stored.get("result") or {"status": stored["status"], "error": stored.get("error")})


@bp.get("/backtests/<task_id>/diagnostics")
def backtest_diagnostics(task_id):
    stored = get_backtest(task_id)
    result = stored.get("result") if stored else (_memory_tasks.get(task_id) or {}).get("result")
    if not result:
        return jsonify({"error": "diagnostics not found"}), 404
    return jsonify(result.get("diagnostics", {}))


@bp.post("/backtests/<task_id>/sensitivity")
def backtest_sensitivity(task_id):
    stored = get_backtest(task_id)
    if not stored:
        return jsonify({"error": "backtest not found"}), 404
    return jsonify({"ok": True, "task_id": task_id, "status": "planned", "message": "P1 参数敏感性接口已预留，当前不生成伪结果。"})


@bp.post("/backtests/<task_id>/walk-forward")
def backtest_walk_forward(task_id):
    stored = get_backtest(task_id)
    if not stored:
        return jsonify({"error": "backtest not found"}), 404
    return jsonify({"ok": True, "task_id": task_id, "status": "planned", "message": "P1 Walk-forward 接口已预留，当前不生成伪结果。"})


@bp.get("/strategy-health")
def strategy_health_list():
    rows = []
    for strategy in list_strategies():
        rows.append({
            "strategy_id": strategy["id"],
            "name": strategy["name"],
            "status": "观察",
            "reason": "需要累计最近20/60/120日模拟表现后确定状态。",
            "dimensions": {"signal_count": None, "drawdown_change": None, "data_health": "待检查"},
        })
    return jsonify({"items": rows})


@bp.get("/strategy-health/<strategy_id>")
def strategy_health_detail(strategy_id):
    strategy = get_strategy(strategy_id)
    if not strategy:
        return jsonify({"error": "strategy not found"}), 404
    return jsonify({"strategy_id": strategy_id, "status": "观察", "message": "健康中心已接入策略血缘，等待每日信号任务积累样本。"})


@bp.get("/portfolios")
def portfolios_list():
    return jsonify({"portfolios": list_portfolios()})


@bp.get("/watchlist")
def watchlist_list():
    return jsonify({"items": list_watchlist()})


@bp.post("/watchlist")
def watchlist_create():
    payload = request.get_json() or {}
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        return jsonify({"ok": False, "error": "加入观察池需要明确股票代码；板块本身不能伪装成股票。"}), 400
    evidence = payload.get("evidence") or {}
    saved = upsert_watchlist(symbol, payload.get("name"), payload.get("source_context") or "manual", evidence)
    return jsonify({"ok": True, "item": saved})


@bp.post("/watchlist/to-strategy")
def watchlist_to_strategy():
    payload = request.get_json() or {}
    items = list_watchlist()
    symbols = payload.get("symbols") or [item["symbol"] for item in items if str(item["symbol"]).isdigit()]
    for item in items:
        if not str(item["symbol"]).startswith("sector:"):
            continue
        industry = item.get("name") or str(item["symbol"]).split(":", 1)[-1]
        members = data_provider.request("get_industry_members", industry)
        if members.ok:
            symbols.extend(row["symbol"] for row in members.data)
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        return jsonify({"ok": False, "error": "观察池为空，无法生成带真实股票池的策略。"}), 400
    text = payload.get("idea") or f"在股票池 {','.join(symbols)} 中，每周调仓，最多持有5只"
    compiled = compile_strategy_from_text(text)
    compiled["dsl"]["universe"] = {**(compiled["dsl"].get("universe") or {}), "type": "symbols", "symbols": symbols}
    return jsonify({"ok": True, **compiled, "evidence": {"watchlist_symbols": symbols, "generated_at": datetime.now().isoformat(timespec="seconds")}})


@bp.get("/research/<symbol>")
def stock_research(symbol):
    requests_spec = [
        ("profile", "get_stock_profile", {"required_fields": ["industry", "market_cap", "pe_ttm", "pb"]}),
        ("fund_flow", "get_fund_flow", {}),
        ("reports", "get_research_reports", {}),
        ("news", "get_stock_news", {}),
        ("announcements", "get_announcements", {}),
    ]
    sections = {}
    missing = {}
    evidence = []
    for key, method, options in requests_spec:
        result = data_provider.request(method, symbol, **options)
        sections[key] = result.data if result.ok else ([] if key != "profile" else {})
        evidence.append({"field": key, **result.meta()})
        if not result.ok:
            missing[key] = result.error or "主备数据源均未返回数据"
        missing.update({f"{key}.{field}": reason for field, reason in result.missing_fields.items()})
    return jsonify({"ok": any(bool(value) for value in sections.values()), "symbol": symbol, "sections": sections, "evidence": evidence, "missing_fields": missing, "generated_at": datetime.now().isoformat(timespec="seconds")})


@bp.post("/portfolios")
def portfolio_create():
    payload = request.get_json() or {}
    portfolio_id = payload.get("id") or f"portfolio_{uuid.uuid4().hex[:8]}"
    saved = upsert_portfolio(portfolio_id, payload.get("name", "模拟组合"), payload.get("kind", "paper"), payload)
    return jsonify({"ok": True, "portfolio": saved})


@bp.post("/portfolios/from-screen")
def portfolio_from_screen():
    payload = request.get_json() or {}
    selected = payload.get("selected") or []
    if not selected:
        return jsonify({"ok": False, "error": "筛选结果为空，不能创建模拟组合。"}), 400
    portfolio_id = payload.get("id") or f"paper_{uuid.uuid4().hex[:8]}"
    evidence = {"strategy_id": payload.get("strategy_id"), "strategy_version": payload.get("strategy_version"), "screened_at": payload.get("screened_at") or datetime.now().isoformat(timespec="seconds"), "selected": selected, "source_status": payload.get("source_status") or {}}
    snapshot = save_evidence_snapshot("screening", portfolio_id, evidence)
    saved = upsert_portfolio(portfolio_id, payload.get("name", "筛选模拟组合"), "paper", {"holdings": selected, "evidence_snapshot_id": snapshot["id"]})
    return jsonify({"ok": True, "portfolio": saved, "evidence_snapshot": snapshot})


@bp.post("/portfolios/<portfolio_id>/optimize")
def portfolio_optimize(portfolio_id):
    payload = request.get_json() or {}
    holdings = payload.get("holdings") or []
    if not holdings:
        return jsonify({"ok": False, "error": "组合优化需要传入当前持仓权重，系统不会生成默认建议。"}), 400
    n = len(holdings)
    target = round(1 / n, 4)
    return jsonify({
        "ok": True,
        "portfolio_id": portfolio_id,
        "objective": payload.get("objective", "equal_weight"),
        "method": "等权优化；PyPortfolioOpt P1 适配器已预留。",
        "constraints": payload.get("constraints", {"max_single_weight": 0.2, "min_cash": 0.05}),
        "suggested_weights": [{"symbol": h.get("symbol"), "target_weight": target} for h in holdings],
        "disclaimer": "数学权重不是确定性投资建议。",
    })


@bp.get("/portfolios/<portfolio_id>/exposure")
def portfolio_exposure(portfolio_id):
    return jsonify({"portfolio_id": portfolio_id, "industry_exposure": [], "style_exposure": [], "message": "等待持仓行业数据后计算。"})


@bp.get("/portfolios/<portfolio_id>/lineage")
def portfolio_lineage(portfolio_id):
    return jsonify({
        "portfolio_id": portfolio_id,
        "items": [],
        "schema": ["来源策略", "策略版本", "入选日期", "入选排名", "入选时因子值", "当前成立条件", "最近信号", "用户是否遵循信号"],
    })


@bp.post("/ai/backtest-diagnose")
def ai_backtest_diagnose():
    payload = request.get_json() or {}
    return jsonify({
        "ok": True,
        "diagnosis": payload.get("diagnostics") or {},
        "message": "当前返回确定性体检结果摘要；LLM只可解释这些检查，不能改写指标。",
    })


@bp.post("/ai/portfolio-explain")
def ai_portfolio_explain():
    payload = request.get_json() or {}
    return jsonify({"ok": True, "explanation": "组合风险解释需要基于已传入行业、权重、策略血缘和信号数据。", "input_keys": sorted(payload.keys())})


@bp.get("/reviews")
def reviews_list():
    decisions = _resolve_due_decisions(list_decisions())
    return jsonify({"reviews": list_reviews(), "decisions": decisions, "message": "仅返回SQLite中的真实决策与复盘记录；无记录时不生成总结。"})


@bp.post("/reviews")
def review_create():
    payload = request.get_json() or {}
    review = insert_review(payload)
    return jsonify({"ok": True, "review": review})


@bp.post("/decisions")
def decision_create():
    payload = request.get_json() or {}
    if not payload.get("thesis") or not payload.get("action"):
        return jsonify({"ok": False, "error": "记录决策需要明确行动和当时的判断理由。"}), 400
    evidence = dict(payload.get("evidence") or {})
    symbol = payload.get("symbol")
    if symbol:
        start = (date.today() - timedelta(days=45)).isoformat()
        quote = data_provider.request("get_stock_daily", symbol, start, date.today().isoformat(), "qfq", required_fields=["trade_date", "close"])
        if quote.ok and quote.data:
            latest = quote.data[-1]
            evidence["decision_quote"] = {"symbol": symbol, "close": latest.get("close"), "date": latest.get("trade_date"), "source": latest.get("source"), "adjustment": latest.get("adjustment")}
        else:
            evidence["decision_quote_missing"] = quote.error or "主备行情源均未返回决策日价格"
    snapshot = save_evidence_snapshot("decision", payload.get("symbol") or payload.get("portfolio_id") or "market", evidence)
    decision = insert_decision(payload, snapshot["id"])
    return jsonify({"ok": True, "decision": decision, "evidence_snapshot": snapshot})


def _resolve_due_decisions(decisions: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    for decision in decisions:
        if decision.get("result") or not decision.get("due_at") or decision["due_at"] > today:
            continue
        if not decision.get("symbol"):
            decision["result_missing_reason"] = "决策没有明确股票代码，无法计算标的到期收益"
            continue
        snapshot = get_evidence_snapshot(decision["evidence_snapshot_id"])
        baseline = (snapshot or {}).get("payload", {}).get("decision_quote") or {}
        if baseline.get("close") is None or not baseline.get("date"):
            decision["result_missing_reason"] = (snapshot or {}).get("payload", {}).get("decision_quote_missing") or "证据快照缺少决策日复权价格"
            continue
        result = data_provider.request("get_stock_daily", decision["symbol"], baseline["date"], today, "qfq", required_fields=["trade_date", "close"])
        if not result.ok or not result.data:
            decision["result_missing_reason"] = result.error or "主备行情源均未返回到期价格"
            continue
        latest = result.data[-1]
        realized = {
            "status": "checked", "baseline_date": baseline["date"], "baseline_close": baseline["close"],
            "result_date": latest.get("trade_date"), "result_close": latest.get("close"),
            "return_pct": round((float(latest["close"]) / float(baseline["close"]) - 1) * 100, 4),
            "source": latest.get("source"), "adjustment": latest.get("adjustment"),
        }
        update_decision_result(decision["id"], realized)
        decision["result"] = realized
    return decisions
