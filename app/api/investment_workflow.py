"""Persisted investment workflow APIs: positions, committee, decisions and reviews."""
from __future__ import annotations

import json
import threading
from datetime import date, datetime
from io import BytesIO, StringIO

import pandas as pd
from flask import Blueprint, jsonify, request

from app.repositories.database import (
    commit_position_import,
    create_agent_task,
    delete_strategy_draft,
    get_agent_task,
    get_decision,
    get_evidence_snapshot,
    get_position,
    get_strategy_draft,
    insert_decision,
    insert_transaction,
    list_agent_tasks,
    list_investment_reviews,
    list_positions,
    list_transactions,
    save_evidence_snapshot,
    save_investment_review,
    save_strategy_draft,
    save_strategy_version,
    update_agent_task,
    update_decision,
    upsert_position,
)
from app.services.portfolio.importer import normalize_rows
from app.services.research import ROLE_LABELS, TASK_ROLES, run_committee_task
from app.services.stocks import enrich_stock_rows


bp = Blueprint("investment_workflow", __name__, url_prefix="/api/workflow")


@bp.get("/positions")
def positions_list():
    include_closed = request.args.get("include_closed", "false").lower() == "true"
    return jsonify({"items": list_positions(request.args.get("portfolio_id"), include_closed)})


@bp.get("/transactions")
def transactions_list():
    return jsonify({"items": list_transactions(request.args.get("position_id"), request.args.get("portfolio_id"))})


@bp.post("/positions/import/preview")
def position_import_preview():
    try:
        raw_rows, mapping = _read_import_request()
        preview = normalize_rows(raw_rows, mapping, list_positions(include_closed=False))
        preview["rows"] = enrich_stock_rows(preview["rows"])
        return jsonify({"ok": True, **preview})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"无法读取导入文件：{exc}"}), 400


@bp.post("/positions/import/commit")
def position_import_commit():
    payload = request.get_json() or {}
    if payload.get("confirm") is not True:
        return jsonify({"ok": False, "error": "请先预览并明确确认导入"}), 400
    rows = payload.get("rows") or []
    invalid = [row for row in rows if row.get("errors") or row.get("valid") is False]
    if not rows or invalid:
        return jsonify({"ok": False, "error": "导入内容为空或仍有校验错误", "invalid_rows": invalid}), 400
    clean_rows = [{key: value for key, value in row.items() if key not in {"errors", "warnings", "conflict", "valid", "row_number"}} for row in rows]
    try:
        result = commit_position_import(
            clean_rows,
            payload.get("conflict_policy") or "skip",
            payload.get("portfolio_id") or "real_default",
            payload.get("portfolio_name") or "真实持仓",
        )
    except (ValueError, KeyError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, **result})


@bp.post("/positions/manual")
def position_manual_create():
    payload = request.get_json() or {}
    if payload.get("confirm") is not True:
        return jsonify({"ok": False, "error": "新增持仓会写入真实持仓与交易流水，请确认"}), 400
    preview = normalize_rows([payload], existing=list_positions())
    if not preview["rows"][0]["valid"]:
        return jsonify({"ok": False, "errors": preview["rows"][0]["errors"]}), 400
    result = commit_position_import([_clean_preview_row(preview["rows"][0])], payload.get("conflict_policy") or "skip", payload.get("portfolio_id") or "real_default")
    return jsonify({"ok": True, **result})


@bp.put("/positions/<position_id>")
def position_update(position_id):
    current = get_position(position_id)
    if not current:
        return jsonify({"ok": False, "error": "持仓不存在"}), 404
    payload = request.get_json() or {}
    if payload.get("confirm") is not True:
        return jsonify({"ok": False, "error": "修改数量或成本会影响组合指标，请确认"}), 400
    allowed = {key: payload[key] for key in ("name", "quantity", "available_quantity", "cost_price", "buy_date", "fees", "notes", "original_thesis", "review_date", "invalidation_conditions", "strategy_id") if key in payload}
    candidate = {**current, **allowed}
    preview = normalize_rows([candidate])
    if not preview["rows"][0]["valid"]:
        return jsonify({"ok": False, "errors": preview["rows"][0]["errors"]}), 400
    saved = upsert_position(candidate, position_id)
    insert_transaction({"position_id": position_id, "portfolio_id": current["portfolio_id"], "symbol": current["symbol"], "transaction_type": "manual_adjust", "quantity": allowed.get("quantity"), "price": allowed.get("cost_price"), "trade_date": date.today().isoformat(), "notes": payload.get("reason") or "用户确认修改持仓", "source": "manual"})
    return jsonify({"ok": True, "position": saved})


@bp.post("/positions/<position_id>/close")
def position_close(position_id):
    current = get_position(position_id)
    payload = request.get_json() or {}
    if not current:
        return jsonify({"ok": False, "error": "持仓不存在"}), 404
    if payload.get("confirm") is not True:
        return jsonify({"ok": False, "error": "清仓会改变持仓状态并写入卖出流水，请确认"}), 400
    quantity = float(payload.get("quantity") or current["quantity"])
    if quantity <= 0 or quantity > float(current["quantity"]):
        return jsonify({"ok": False, "error": "卖出数量必须大于0且不能超过当前持仓"}), 400
    remaining = float(current["quantity"]) - quantity
    saved = upsert_position({**current, "quantity": remaining, "available_quantity": min(float(current.get("available_quantity") or 0), remaining), "status": "closed" if remaining == 0 else "open"}, position_id)
    transaction = insert_transaction({"position_id": position_id, "portfolio_id": current["portfolio_id"], "symbol": current["symbol"], "transaction_type": "sell", "quantity": quantity, "price": payload.get("price"), "fees": payload.get("fees"), "trade_date": payload.get("trade_date") or date.today().isoformat(), "notes": payload.get("notes"), "source": "manual"})
    return jsonify({"ok": True, "position": saved, "transaction": transaction})


@bp.post("/positions/<position_id>/remove")
def position_remove(position_id):
    current = get_position(position_id)
    payload = request.get_json() or {}
    if not current:
        return jsonify({"ok": False, "error": "持仓不存在"}), 404
    if payload.get("confirm") is not True:
        return jsonify({"ok": False, "error": "删除不会伪装成卖出，但会停止组合计算，请确认"}), 400
    saved = upsert_position({**current, "status": "deleted"}, position_id)
    transaction = insert_transaction({"position_id": position_id, "portfolio_id": current["portfolio_id"], "symbol": current["symbol"], "transaction_type": "remove", "trade_date": date.today().isoformat(), "notes": payload.get("reason") or "用户删除错误持仓记录", "source": "manual"})
    return jsonify({"ok": True, "position": saved, "transaction": transaction})


@bp.post("/positions/from-paper/preview")
def position_from_paper_preview():
    payload = request.get_json() or {}
    holdings = payload.get("holdings") or []
    rows = [{"symbol": item.get("symbol") or item.get("code"), "name": item.get("name"), "quantity": item.get("quantity"), "cost_price": item.get("cost_price") or item.get("price"), "buy_date": item.get("buy_date"), "strategy_id": payload.get("strategy_id")} for item in holdings]
    preview = normalize_rows(rows, existing=list_positions())
    preview["rows"] = enrich_stock_rows(preview["rows"])
    return jsonify({"ok": True, **preview})


@bp.get("/strategy-draft")
def strategy_draft_get():
    return jsonify({"draft": get_strategy_draft(request.args.get("id") or "current")})


@bp.put("/strategy-draft")
def strategy_draft_save():
    payload = request.get_json() or {}
    return jsonify({"ok": True, "draft": save_strategy_draft(payload.get("id") or "current", payload.get("idea") or "", payload.get("compiled"))})


@bp.delete("/strategy-draft")
def strategy_draft_delete():
    delete_strategy_draft(request.args.get("id") or "current")
    return jsonify({"ok": True})


@bp.get("/committee/tasks")
def committee_tasks_list():
    return jsonify({"items": list_agent_tasks()})


@bp.post("/committee/tasks")
def committee_task_create():
    payload = request.get_json() or {}
    task_type = payload.get("task_type")
    if task_type not in TASK_ROLES:
        return jsonify({"ok": False, "error": "任务类型必须是 holding_logic 或 market_impact"}), 400
    position = get_position(payload.get("position_id")) if payload.get("position_id") else None
    if task_type == "holding_logic" and not position:
        return jsonify({"ok": False, "error": "持仓逻辑审查需要选择一个真实持仓"}), 400
    holdings = [_analytics_holding(item) for item in list_positions()]
    task_input = {"symbol": position["symbol"] if position else None, "position": _analytics_holding(position) if position else None, "holdings": holdings, "question": payload.get("question"), "created_by": "user"}
    task = create_agent_task({"task_type": task_type, "subject_type": "position" if position else "portfolio", "subject_id": position["id"] if position else payload.get("portfolio_id") or "real_default", "input": task_input, "status": "waiting", "role_runs": [{"role": role, "label": ROLE_LABELS[role], "status": "waiting"} for role in TASK_ROLES[task_type]]})
    threading.Thread(target=run_committee_task, args=(task["id"],), daemon=True).start()
    return jsonify({"ok": True, "task": task}), 202


@bp.get("/committee/tasks/<task_id>")
def committee_task_get(task_id):
    task = get_agent_task(task_id)
    return (jsonify({"task": task}) if task else (jsonify({"error": "任务不存在"}), 404))


@bp.post("/committee/tasks/<task_id>/cancel")
def committee_task_cancel(task_id):
    if not get_agent_task(task_id):
        return jsonify({"error": "任务不存在"}), 404
    return jsonify({"ok": True, "task": update_agent_task(task_id, cancel_requested=True)})


@bp.post("/committee/tasks/<task_id>/retry")
def committee_task_retry(task_id):
    task = get_agent_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    role = (request.get_json() or {}).get("role")
    if role and role not in TASK_ROLES.get(task["task_type"], []):
        return jsonify({"error": "该角色不属于此任务"}), 400
    update_agent_task(task_id, status="waiting", cancel_requested=False, error=None)
    threading.Thread(target=run_committee_task, args=(task_id, role), daemon=True).start()
    return jsonify({"ok": True, "task": get_agent_task(task_id)}), 202


@bp.post("/committee/tasks/<task_id>/decision")
def committee_decision_create(task_id):
    task = get_agent_task(task_id)
    payload = request.get_json() or {}
    if not task or task.get("status") != "completed":
        return jsonify({"ok": False, "error": "投委会任务尚未完成"}), 409
    if payload.get("confirm") is not True:
        return jsonify({"ok": False, "error": "AI意见仅供研究，保存前需要用户明确确认"}), 400
    result = task.get("result") or {}
    snapshot = save_evidence_snapshot("committee_decision", task_id, {"task_input": task["input"], "role_runs": task["role_runs"], "chairman": result})
    decision_payload = {
        "portfolio_id": payload.get("portfolio_id") or "real_default", "symbol": task["input"].get("symbol"),
        "action": payload.get("action") or result.get("action") or "HOLD", "thesis": payload.get("thesis") or result.get("conclusion") or "",
        "due_at": payload.get("due_at") or result.get("review_date"), "source": "investment_committee",
        "risk": {"opposing_reasons": result.get("opposing_reasons"), "missing_data": result.get("missing_data")},
        "invalidation_conditions": payload.get("invalidation_conditions") or result.get("invalidation_conditions"),
        "agent_opinions": task["role_runs"], "user_confirmed": True, "user_modified": bool(payload.get("action") or payload.get("thesis")),
        "modification": payload.get("modification"),
    }
    decision = insert_decision(decision_payload, snapshot["id"])
    return jsonify({"ok": True, "decision": decision, "evidence_snapshot": snapshot})


@bp.put("/decisions/<decision_id>")
def decision_update(decision_id):
    if not get_decision(decision_id):
        return jsonify({"error": "决策不存在"}), 404
    payload = request.get_json() or {}
    if payload.get("confirm") is not True:
        return jsonify({"error": "修改决策需明确确认"}), 400
    return jsonify({"ok": True, "decision": update_decision(decision_id, payload)})


@bp.post("/decisions/<decision_id>/review")
def investment_review_create(decision_id):
    decision = get_decision(decision_id)
    payload = request.get_json() or {}
    if not decision:
        return jsonify({"error": "决策不存在"}), 404
    if payload.get("confirm") is not True:
        return jsonify({"error": "复盘将作为正式记录保存，请确认"}), 400
    required = ("actual_action", "decision_correct", "execution_correct", "bias_type", "next_adjustment")
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        return jsonify({"error": "复盘字段不完整", "missing_fields": missing}), 400
    review = save_investment_review(decision_id, {**payload, "decision_snapshot": decision, "reviewed_at": datetime.now().isoformat(timespec="seconds")})
    version = None
    strategy = payload.get("create_strategy_version")
    if strategy and strategy.get("strategy_id") and strategy.get("dsl"):
        version = save_strategy_version(strategy["strategy_id"], strategy.get("version") or f"review-{date.today().isoformat()}", strategy["dsl"], strategy.get("note") or f"由复盘 {review['id']} 创建")
    return jsonify({"ok": True, "review": review, "strategy_version": version})


@bp.get("/investment-reviews")
def investment_reviews_list():
    return jsonify({"items": list_investment_reviews()})


@bp.get("/evidence/<snapshot_id>")
def evidence_get(snapshot_id):
    snapshot = get_evidence_snapshot(snapshot_id)
    return (jsonify({"snapshot": snapshot}) if snapshot else (jsonify({"error": "证据快照不存在"}), 404))


def _read_import_request() -> tuple[list[dict], dict]:
    if request.files:
        upload = request.files.get("file")
        if not upload or not upload.filename:
            raise ValueError("未选择文件")
        mapping = json.loads(request.form.get("mapping") or "{}")
        raw = upload.read()
        if upload.filename.lower().endswith((".xlsx", ".xls")):
            frame = pd.read_excel(BytesIO(raw), dtype=object)
        elif upload.filename.lower().endswith(".csv"):
            frame = pd.read_csv(BytesIO(raw), sep=None, engine="python", dtype=object)
        else:
            raise ValueError("仅支持 CSV、XLSX 或 XLS 文件")
        return frame.where(frame.notna(), None).to_dict(orient="records"), mapping
    payload = request.get_json() or {}
    mapping = payload.get("mapping") or {}
    if payload.get("text"):
        frame = pd.read_csv(StringIO(payload["text"]), sep=None, engine="python", dtype=object)
        return frame.where(frame.notna(), None).to_dict(orient="records"), mapping
    if not isinstance(payload.get("rows"), list):
        raise ValueError("请提供 rows、粘贴表格文本或上传文件")
    return payload["rows"], mapping


def _clean_preview_row(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in {"errors", "warnings", "conflict", "valid", "row_number"}}


def _analytics_holding(position: dict | None) -> dict | None:
    if not position:
        return None
    return {**position, "code": position["symbol"], "shares": position["quantity"], "cost": position.get("cost_price")}
