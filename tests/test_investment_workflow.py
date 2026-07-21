from datetime import date, timedelta

from flask import Flask

from app.api.investment_workflow import bp
from app.repositories import database
from app.services.portfolio.importer import normalize_rows


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "workflow.sqlite3")
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "migrate_legacy_json", lambda: None)
    monkeypatch.setattr("app.api.investment_workflow.enrich_stock_rows", lambda rows: rows)
    database.init_db()
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app.test_client()


def test_future_review_date_is_valid():
    future = (date.today() + timedelta(days=20)).isoformat()
    preview = normalize_rows([{"symbol": "600519", "quantity": 100, "cost_price": 1500, "review_date": future}])
    assert preview["summary"]["valid"] == 1
    assert preview["rows"][0]["review_date"] == future


def test_csv_preview_commit_and_transaction_ledger(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    text = "股票代码,股票名称,持仓数量,可用数量,成本价,买入日期\n600519,贵州茅台,100,100,1500,2026-06-01\n300750,宁德时代,200,200,220,2026-06-02\n601318,中国平安,300,300,48,2026-06-03"
    preview = client.post("/api/workflow/positions/import/preview", json={"text": text})
    assert preview.status_code == 200
    body = preview.get_json()
    assert body["summary"] == {"total": 3, "valid": 3, "invalid": 0, "conflicts": 0}

    committed = client.post("/api/workflow/positions/import/commit", json={"confirm": True, "rows": body["rows"], "conflict_policy": "merge"})
    assert committed.status_code == 200
    assert len(committed.get_json()["imported"]) == 3
    assert len(client.get("/api/workflow/positions").get_json()["items"]) == 3
    assert len(client.get("/api/workflow/transactions").get_json()["items"]) == 3


def test_conflict_merge_updates_weighted_cost(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    first = client.post("/api/workflow/positions/import/preview", json={"rows": [{"symbol": "600519", "quantity": 100, "cost_price": 100}] }).get_json()
    client.post("/api/workflow/positions/import/commit", json={"confirm": True, "rows": first["rows"], "conflict_policy": "merge"})
    second = client.post("/api/workflow/positions/import/preview", json={"rows": [{"symbol": "600519", "quantity": 100, "cost_price": 200}] }).get_json()
    assert second["summary"]["conflicts"] == 1
    client.post("/api/workflow/positions/import/commit", json={"confirm": True, "rows": second["rows"], "conflict_policy": "merge"})
    position = client.get("/api/workflow/positions").get_json()["items"][0]
    assert position["quantity"] == 200
    assert position["cost_price"] == 150


def test_close_requires_confirmation(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    preview = client.post("/api/workflow/positions/import/preview", json={"rows": [{"symbol": "600519", "quantity": 100, "cost_price": 100}] }).get_json()
    result = client.post("/api/workflow/positions/import/commit", json={"confirm": True, "rows": preview["rows"], "conflict_policy": "merge"}).get_json()
    position_id = result["imported"][0]
    assert client.post(f"/api/workflow/positions/{position_id}/close", json={}).status_code == 400
    closed = client.post(f"/api/workflow/positions/{position_id}/close", json={"confirm": True, "price": 110})
    assert closed.status_code == 200
    assert closed.get_json()["position"]["status"] == "closed"


def test_committee_task_persists_role_statuses(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    monkeypatch.setattr("app.api.investment_workflow.run_committee_task", lambda task_id: None)
    preview = client.post("/api/workflow/positions/import/preview", json={"rows": [{"symbol": "600519", "quantity": 100, "cost_price": 100}] }).get_json()
    position_id = client.post("/api/workflow/positions/import/commit", json={"confirm": True, "rows": preview["rows"], "conflict_policy": "merge"}).get_json()["imported"][0]
    created = client.post("/api/workflow/committee/tasks", json={"task_type": "holding_logic", "position_id": position_id})
    assert created.status_code == 202
    task = created.get_json()["task"]
    assert task["status"] == "waiting"
    assert [item["role"] for item in task["role_runs"]] == ["fundamental", "valuation", "industry", "trend", "risk", "contrarian"]
    assert client.get(f"/api/workflow/committee/tasks/{task['id']}").status_code == 200


def test_structured_review_is_persisted(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    snapshot = database.save_evidence_snapshot("decision", "600519", {"close": 100, "source": "test"})
    decision = database.insert_decision({"symbol": "600519", "action": "HOLD", "thesis": "盈利与趋势仍需跟踪", "user_confirmed": True}, snapshot["id"])
    response = client.post(f"/api/workflow/decisions/{decision['id']}/review", json={
        "confirm": True,
        "actual_action": "HOLD",
        "decision_correct": True,
        "execution_correct": True,
        "bias_type": "市场变化",
        "next_adjustment": "增加明确失效条件",
    })
    assert response.status_code == 200
    assert response.get_json()["review"]["decision_id"] == decision["id"]
    assert database.get_decision(decision["id"])["review_id"]
