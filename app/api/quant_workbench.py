"""API routes for the AI quantitative workbench."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.repositories.database import (
    get_backtest,
    get_strategy,
    init_db,
    insert_review,
    list_portfolios,
    list_strategies,
    save_strategy_version,
    upsert_backtest,
    upsert_portfolio,
    upsert_strategy,
)
from app.schemas.strategy import StrategyDSL
from app.services.backtest.engine import run_backtest
from app.services.data.registry import registry
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


def _clean_tasks():
    now = time.time()
    for task_id, task in list(_memory_tasks.items()):
        if now - task.get("created_ts", now) > _TASK_TTL_SECONDS:
            _memory_tasks.pop(task_id, None)


@bp.get("/data/status")
def data_status():
    status = registry.status()
    return jsonify({**status, "generated_at": datetime.now().isoformat(timespec="seconds")})


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


@bp.post("/portfolios")
def portfolio_create():
    payload = request.get_json() or {}
    portfolio_id = payload.get("id") or f"portfolio_{uuid.uuid4().hex[:8]}"
    saved = upsert_portfolio(portfolio_id, payload.get("name", "模拟组合"), payload.get("kind", "paper"), payload)
    return jsonify({"ok": True, "portfolio": saved})


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
    return jsonify({"reviews": [], "message": "旧复盘数据已迁移到SQLite，详细记录仍通过 /api/effect/* 兼容接口查看。"})


@bp.post("/reviews")
def review_create():
    payload = request.get_json() or {}
    review = insert_review(payload)
    return jsonify({"ok": True, "review": review})
