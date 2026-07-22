"""SQLite initialization and legacy JSON migration."""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DATA_DIR, DB_PATH, PROJECT_DIR, PUBLIC_DEMO


SCHEMA = """
CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  dsl_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategy_versions (
  id TEXT PRIMARY KEY,
  strategy_id TEXT NOT NULL,
  version TEXT NOT NULL,
  dsl_json TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backtest_tasks (
  id TEXT PRIMARY KEY,
  strategy_id TEXT,
  status TEXT NOT NULL,
  config_json TEXT NOT NULL,
  result_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolios (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS holding_lineage (
  id TEXT PRIMARY KEY,
  portfolio_id TEXT,
  symbol TEXT NOT NULL,
  strategy_id TEXT,
  strategy_version TEXT,
  selected_at TEXT,
  selected_rank INTEGER,
  selected_factors_json TEXT,
  current_conditions_json TEXT,
  user_followed_signal INTEGER DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_research_records (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist (
  id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  name TEXT,
  source_context TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_snapshots (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_records (
  id TEXT PRIMARY KEY,
  portfolio_id TEXT,
  symbol TEXT,
  action TEXT NOT NULL,
  thesis TEXT NOT NULL,
  evidence_snapshot_id TEXT NOT NULL,
  due_at TEXT,
  result_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
  id TEXT PRIMARY KEY,
  portfolio_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  name TEXT,
  market TEXT,
  quantity REAL NOT NULL,
  available_quantity REAL,
  cost_price REAL,
  buy_date TEXT,
  fees REAL DEFAULT 0,
  notes TEXT,
  original_thesis TEXT,
  review_date TEXT,
  invalidation_conditions TEXT,
  strategy_id TEXT,
  decision_id TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_portfolio_symbol_open
ON positions(portfolio_id, symbol) WHERE status='open';
CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY,
  position_id TEXT,
  portfolio_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  transaction_type TEXT NOT NULL,
  quantity REAL,
  price REAL,
  fees REAL DEFAULT 0,
  trade_date TEXT NOT NULL,
  notes TEXT,
  source TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_tasks (
  id TEXT PRIMARY KEY,
  task_type TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id TEXT,
  status TEXT NOT NULL,
  input_json TEXT NOT NULL,
  result_json TEXT,
  role_runs_json TEXT,
  error TEXT,
  cancel_requested INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS investment_reviews (
  id TEXT PRIMARY KEY,
  decision_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategy_drafts (
  id TEXT PRIMARY KEY,
  idea TEXT NOT NULL,
  compiled_json TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS migrations (
  id TEXT PRIMARY KEY,
  source_file TEXT NOT NULL,
  backup_file TEXT,
  status TEXT NOT NULL,
  message TEXT,
  created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _ensure_columns(conn, "decision_records", {
            "source": "TEXT",
            "risk_json": "TEXT",
            "invalidation_json": "TEXT",
            "agent_opinions_json": "TEXT",
            "user_confirmed": "INTEGER DEFAULT 0",
            "user_modified": "INTEGER DEFAULT 0",
            "modification_json": "TEXT",
            "actual_action": "TEXT",
            "review_id": "TEXT",
            "updated_at": "TEXT",
        })
    migrate_legacy_json()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def migrate_legacy_json() -> None:
    if PUBLIC_DEMO:
        return
    legacy_files = [
        (PROJECT_DIR / ".quant_strategies.json", "strategies"),
        (PROJECT_DIR / ".wyckoff_holdings.json", "portfolios"),
        (PROJECT_DIR / ".ai_effect_tracker.json", "reviews"),
    ]
    for path, kind in legacy_files:
        if not path.exists():
            continue
        migration_id = f"{path.name}:{int(path.stat().st_mtime)}"
        with connect() as conn:
            seen = conn.execute("SELECT 1 FROM migrations WHERE id=?", (migration_id,)).fetchone()
            if seen:
                continue
        backup = DATA_DIR / f"{path.name}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
        try:
            shutil.copy2(path, backup)
            payload = json.loads(path.read_text())
            if kind == "strategies" and isinstance(payload, list):
                for item in payload:
                    upsert_strategy(item.get("id") or f"legacy_{len(json.dumps(item))}", item.get("name") or item.get("label") or "旧策略", item)
            elif kind == "portfolios" and isinstance(payload, list):
                upsert_portfolio("legacy_holdings", "旧持仓迁移", "real", {"holdings": payload})
            elif kind == "reviews":
                predictions = payload.get("predictions") if isinstance(payload, dict) else None
                if predictions:
                    insert_review({"legacy_effect_tracker": payload})
            _record_migration(migration_id, path, backup, "ok", "migrated")
        except Exception as exc:
            _record_migration(migration_id, path, backup if backup.exists() else None, "error", str(exc))


def _record_migration(migration_id: str, path: Path, backup: Path | None, status: str, message: str):
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO migrations VALUES (?, ?, ?, ?, ?, ?)",
            (migration_id, str(path), str(backup) if backup else None, status, message, datetime.now().isoformat(timespec="seconds")),
        )


def upsert_strategy(strategy_id: str, name: str, dsl: dict) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO strategies VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM strategies WHERE id=?), ?), ?)",
            (strategy_id, name, dsl.get("description", ""), json.dumps(dsl, ensure_ascii=False), strategy_id, now, now),
        )
    return get_strategy(strategy_id)


def list_strategies() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM strategies ORDER BY updated_at DESC").fetchall()
    return [_row_strategy(row) for row in rows]


def get_strategy(strategy_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM strategies WHERE id=?", (strategy_id,)).fetchone()
    return _row_strategy(row) if row else None


def save_strategy_version(strategy_id: str, version: str, dsl: dict, note: str = "") -> dict:
    vid = f"{strategy_id}:{version}"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO strategy_versions VALUES (?, ?, ?, ?, ?, ?)", (vid, strategy_id, version, json.dumps(dsl, ensure_ascii=False), note, now))
    return {"id": vid, "strategy_id": strategy_id, "version": version, "created_at": now}


def upsert_backtest(task_id: str, status: str, config: dict, result: dict | None = None, error: str | None = None, strategy_id: str | None = None):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO backtest_tasks VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM backtest_tasks WHERE id=?), ?), ?)",
            (task_id, strategy_id, status, json.dumps(config, ensure_ascii=False), json.dumps(result, ensure_ascii=False) if result else None, error, task_id, now, now),
        )


def get_backtest(task_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM backtest_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return None
    return {**dict(row), "config": json.loads(row["config_json"]), "result": json.loads(row["result_json"]) if row["result_json"] else None}


def upsert_portfolio(portfolio_id: str, name: str, kind: str, payload: dict) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO portfolios VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM portfolios WHERE id=?), ?), ?)",
            (portfolio_id, name, kind, json.dumps(payload, ensure_ascii=False), portfolio_id, now, now),
        )
    return {"id": portfolio_id, "name": name, "kind": kind, "payload": payload}


def list_portfolios() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM portfolios ORDER BY updated_at DESC").fetchall()
    return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]


def insert_review(payload: dict) -> dict:
    review_id = payload.get("id") or f"review_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO reviews VALUES (?, ?, ?)", (review_id, json.dumps(payload, ensure_ascii=False), now))
    return {"id": review_id, "created_at": now, "payload": payload}


def list_reviews() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
    items = [{"id": row["id"], "created_at": row["created_at"], **json.loads(row["payload_json"])} for row in rows]
    return [item for item in items if _review_has_evidence(item)]


def _review_has_evidence(item: dict) -> bool:
    legacy = item.get("legacy_effect_tracker")
    if isinstance(legacy, dict):
        return bool(legacy.get("predictions"))
    return bool(item.get("stock_code") and item.get("decision_date") and item.get("action"))


def upsert_watchlist(symbol: str, name: str | None, source_context: str, evidence: dict) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    item_id = f"watch:{symbol}"
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO watchlist VALUES (?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM watchlist WHERE id=?), ?), ?)", (item_id, symbol, name, source_context, json.dumps(evidence, ensure_ascii=False), item_id, now, now))
    return {"id": item_id, "symbol": symbol, "name": name, "source_context": source_context, "evidence": evidence, "created_at": now}


def list_watchlist() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY updated_at DESC").fetchall()
    return [{**dict(row), "evidence": json.loads(row["evidence_json"])} for row in rows]


def save_evidence_snapshot(entity_type: str, entity_id: str, payload: dict) -> dict:
    snapshot_id = f"ev_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("INSERT INTO evidence_snapshots VALUES (?, ?, ?, ?, ?)", (snapshot_id, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), now))
    return {"id": snapshot_id, "created_at": now, "payload": payload}


def get_evidence_snapshot(snapshot_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM evidence_snapshots WHERE id=?", (snapshot_id,)).fetchone()
    return {**dict(row), "payload": json.loads(row["payload_json"])} if row else None


def insert_decision(payload: dict, evidence_snapshot_id: str) -> dict:
    decision_id = payload.get("id") or f"decision_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO decision_records
            (id, portfolio_id, symbol, action, thesis, evidence_snapshot_id, due_at, result_json, created_at,
             source, risk_json, invalidation_json, agent_opinions_json, user_confirmed, user_modified,
             modification_json, actual_action, review_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (decision_id, payload.get("portfolio_id"), payload.get("symbol"), payload.get("action") or "观察",
             payload.get("thesis") or "", evidence_snapshot_id, payload.get("due_at"), None, now,
             payload.get("source") or "manual", _json(payload.get("risk")), _json(payload.get("invalidation_conditions")),
             _json(payload.get("agent_opinions")), int(bool(payload.get("user_confirmed"))),
             int(bool(payload.get("user_modified"))), _json(payload.get("modification")), payload.get("actual_action"),
             payload.get("review_id"), now),
        )
    return {"id": decision_id, "created_at": now, "updated_at": now, "evidence_snapshot_id": evidence_snapshot_id, **payload}


def list_decisions() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM decision_records ORDER BY created_at DESC").fetchall()
    return [_decision_row(row) for row in rows]


def update_decision_result(decision_id: str, result: dict) -> None:
    with connect() as conn:
        conn.execute("UPDATE decision_records SET result_json=?, updated_at=? WHERE id=?", (json.dumps(result, ensure_ascii=False), datetime.now().isoformat(timespec="seconds"), decision_id))


def get_decision(decision_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM decision_records WHERE id=?", (decision_id,)).fetchone()
    return _decision_row(row) if row else None


def update_decision(decision_id: str, payload: dict) -> dict | None:
    allowed = {
        "action": ("action", lambda value: value), "thesis": ("thesis", lambda value: value),
        "due_at": ("due_at", lambda value: value), "actual_action": ("actual_action", lambda value: value),
        "user_confirmed": ("user_confirmed", lambda value: int(bool(value))),
        "user_modified": ("user_modified", lambda value: int(bool(value))),
        "risk": ("risk_json", _json), "invalidation_conditions": ("invalidation_json", _json),
        "agent_opinions": ("agent_opinions_json", _json), "modification": ("modification_json", _json),
        "review_id": ("review_id", lambda value: value),
    }
    changes = [(column, transform(payload[key])) for key, (column, transform) in allowed.items() if key in payload]
    if not changes:
        return get_decision(decision_id)
    changes.append(("updated_at", datetime.now().isoformat(timespec="seconds")))
    with connect() as conn:
        conn.execute(f"UPDATE decision_records SET {', '.join(f'{column}=?' for column, _ in changes)} WHERE id=?", [value for _, value in changes] + [decision_id])
    return get_decision(decision_id)


def list_positions(portfolio_id: str | None = None, include_closed: bool = False) -> list[dict]:
    clauses, params = [], []
    if portfolio_id:
        clauses.append("portfolio_id=?")
        params.append(portfolio_id)
    if not include_closed:
        clauses.append("status='open'")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM positions{where} ORDER BY updated_at DESC", params).fetchall()
    return [dict(row) for row in rows]


def get_position(position_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    return dict(row) if row else None


def find_open_position(portfolio_id: str, symbol: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM positions WHERE portfolio_id=? AND symbol=? AND status='open'", (portfolio_id, symbol)).fetchone()
    return dict(row) if row else None


def upsert_position(payload: dict, position_id: str | None = None) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    position_id = position_id or payload.get("id") or f"pos_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    current = get_position(position_id)
    merged = {**(current or {}), **payload}
    with connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO positions
            (id, portfolio_id, symbol, name, market, quantity, available_quantity, cost_price, buy_date, fees,
             notes, original_thesis, review_date, invalidation_conditions, strategy_id, decision_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (position_id, merged.get("portfolio_id") or "real_default", merged.get("symbol"), merged.get("name"), merged.get("market"),
             float(merged.get("quantity") or 0), _float_or_none(merged.get("available_quantity")), _float_or_none(merged.get("cost_price")),
             merged.get("buy_date"), float(merged.get("fees") or 0), merged.get("notes"), merged.get("original_thesis"),
             merged.get("review_date"), merged.get("invalidation_conditions"), merged.get("strategy_id"), merged.get("decision_id"),
             merged.get("status") or "open", merged.get("created_at") or now, now),
        )
    return get_position(position_id)


def insert_transaction(payload: dict) -> dict:
    transaction_id = payload.get("id") or f"txn_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO transactions
            (id, position_id, portfolio_id, symbol, transaction_type, quantity, price, fees, trade_date, notes, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (transaction_id, payload.get("position_id"), payload.get("portfolio_id") or "real_default", payload.get("symbol"),
             payload.get("transaction_type"), _float_or_none(payload.get("quantity")), _float_or_none(payload.get("price")),
             float(payload.get("fees") or 0), payload.get("trade_date") or datetime.now().date().isoformat(), payload.get("notes"),
             payload.get("source") or "manual", now),
        )
    return {"id": transaction_id, "created_at": now, **payload}


def list_transactions(position_id: str | None = None, portfolio_id: str | None = None) -> list[dict]:
    clauses, params = [], []
    if position_id:
        clauses.append("position_id=?")
        params.append(position_id)
    if portfolio_id:
        clauses.append("portfolio_id=?")
        params.append(portfolio_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM transactions{where} ORDER BY trade_date DESC, created_at DESC", params).fetchall()
    return [dict(row) for row in rows]


def commit_position_import(rows: list[dict], conflict_policy: str, portfolio_id: str = "real_default",
                           portfolio_name: str = "真实持仓") -> dict:
    """Commit a validated preview and its audit ledger in one transaction."""
    if conflict_policy not in {"merge", "overwrite", "skip", "new_portfolio"}:
        raise ValueError("冲突处理必须是 merge、overwrite、skip 或 new_portfolio")
    now = datetime.now().isoformat(timespec="seconds")
    target_id = f"real_{uuid_token()}" if conflict_policy == "new_portfolio" else portfolio_id
    imported, skipped, transactions = [], [], []
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO portfolios VALUES (?, ?, 'real', ?, ?, ?)",
            (target_id, portfolio_name, _json({"source": "position_import"}), now, now),
        )
        for index, source_row in enumerate(rows):
            row = {**source_row, "portfolio_id": target_id}
            existing = conn.execute(
                "SELECT * FROM positions WHERE portfolio_id=? AND symbol=? AND status='open'",
                (target_id, row["symbol"]),
            ).fetchone()
            if existing and conflict_policy == "skip":
                skipped.append({"symbol": row["symbol"], "reason": "已有未清仓持仓"})
                continue
            position_id = existing["id"] if existing else f"pos_{uuid_token()}_{index}"
            transaction_type = "buy"
            if existing and conflict_policy == "merge":
                old_qty = float(existing["quantity"] or 0)
                add_qty = float(row["quantity"])
                total_qty = old_qty + add_qty
                old_cost = float(existing["cost_price"] or 0)
                row["cost_price"] = ((old_qty * old_cost) + (add_qty * float(row["cost_price"]))) / total_qty
                row["quantity"] = total_qty
                row["available_quantity"] = (float(existing["available_quantity"] or old_qty) + float(row.get("available_quantity") or add_qty))
                transaction_type = "add"
            elif existing:
                transaction_type = "import_correction"
            conn.execute(
                """INSERT OR REPLACE INTO positions
                (id, portfolio_id, symbol, name, market, quantity, available_quantity, cost_price, buy_date, fees,
                 notes, original_thesis, review_date, invalidation_conditions, strategy_id, decision_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
                (position_id, target_id, row["symbol"], row.get("name"), row.get("market"), row["quantity"],
                 row.get("available_quantity"), row.get("cost_price"), row.get("buy_date"), row.get("fees") or 0,
                 row.get("notes"), row.get("original_thesis"), row.get("review_date"), row.get("invalidation_conditions"),
                 row.get("strategy_id"), row.get("decision_id"), existing["created_at"] if existing else now, now),
            )
            transaction_id = f"txn_{uuid_token()}_{index}"
            ledger_qty = source_row["quantity"]
            conn.execute(
                """INSERT INTO transactions
                (id, position_id, portfolio_id, symbol, transaction_type, quantity, price, fees, trade_date, notes, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'position_import', ?)""",
                (transaction_id, position_id, target_id, row["symbol"], transaction_type, ledger_qty,
                 source_row.get("cost_price"), source_row.get("fees") or 0, source_row.get("buy_date") or now[:10],
                 source_row.get("notes"), now),
            )
            imported.append(position_id)
            transactions.append(transaction_id)
        conn.execute("UPDATE portfolios SET updated_at=? WHERE id=?", (now, target_id))
    return {"portfolio_id": target_id, "imported": imported, "skipped": skipped, "transactions": transactions}


def create_agent_task(payload: dict) -> dict:
    task_id = payload.get("id") or f"committee_{uuid_token()}"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("""INSERT INTO agent_tasks
            (id, task_type, subject_type, subject_id, status, input_json, result_json, role_runs_json, error, cancel_requested, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (task_id, payload.get("task_type"), payload.get("subject_type"), payload.get("subject_id"), payload.get("status") or "waiting",
             _json(payload.get("input") or {}), _json(payload.get("result")), _json(payload.get("role_runs") or []), payload.get("error"), now, now))
    return get_agent_task(task_id)


def update_agent_task(task_id: str, **changes) -> dict | None:
    mapping = {"status": "status", "result": "result_json", "role_runs": "role_runs_json", "error": "error", "cancel_requested": "cancel_requested"}
    values = []
    sets = []
    for key, value in changes.items():
        if key not in mapping:
            continue
        sets.append(f"{mapping[key]}=?")
        values.append(_json(value) if key in {"result", "role_runs"} else int(bool(value)) if key == "cancel_requested" else value)
    if not sets:
        return get_agent_task(task_id)
    sets.append("updated_at=?")
    values.extend([datetime.now().isoformat(timespec="seconds"), task_id])
    with connect() as conn:
        conn.execute(f"UPDATE agent_tasks SET {', '.join(sets)} WHERE id=?", values)
    return get_agent_task(task_id)


def get_agent_task(task_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM agent_tasks WHERE id=?", (task_id,)).fetchone()
    return _agent_task_row(row) if row else None


def list_agent_tasks(limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM agent_tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_agent_task_row(row) for row in rows]


def save_investment_review(decision_id: str, payload: dict) -> dict:
    review_id = payload.get("id") or f"ireview_{uuid_token()}"
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO investment_reviews VALUES (?, ?, ?, COALESCE((SELECT created_at FROM investment_reviews WHERE id=?), ?), ?)",
                     (review_id, decision_id, _json(payload), review_id, now, now))
    update_decision(decision_id, {"review_id": review_id})
    return {"id": review_id, "decision_id": decision_id, "payload": payload, "created_at": now, "updated_at": now}


def list_investment_reviews() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM investment_reviews ORDER BY updated_at DESC").fetchall()
    return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]


def save_strategy_draft(draft_id: str, idea: str, compiled: dict | None) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO strategy_drafts VALUES (?, ?, ?, ?)", (draft_id, idea, _json(compiled), now))
    return {"id": draft_id, "idea": idea, "compiled": compiled, "updated_at": now}


def get_strategy_draft(draft_id: str = "current") -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM strategy_drafts WHERE id=?", (draft_id,)).fetchone()
    return {**dict(row), "compiled": json.loads(row["compiled_json"]) if row["compiled_json"] else None} if row else None


def delete_strategy_draft(draft_id: str = "current") -> None:
    with connect() as conn:
        conn.execute("DELETE FROM strategy_drafts WHERE id=?", (draft_id,))


def _decision_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    for source, target in (("result_json", "result"), ("risk_json", "risk"), ("invalidation_json", "invalidation_conditions"),
                           ("agent_opinions_json", "agent_opinions"), ("modification_json", "modification")):
        data[target] = json.loads(data[source]) if data.get(source) else None
    data["user_confirmed"] = bool(data.get("user_confirmed"))
    data["user_modified"] = bool(data.get("user_modified"))
    return data


def _agent_task_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["input"] = json.loads(data["input_json"])
    data["result"] = json.loads(data["result_json"]) if data.get("result_json") else None
    data["role_runs"] = json.loads(data["role_runs_json"]) if data.get("role_runs_json") else []
    data["cancel_requested"] = bool(data.get("cancel_requested"))
    return data


def _json(value) -> str | None:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _float_or_none(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def uuid_token() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def _row_strategy(row: Any) -> dict:
    data = dict(row)
    return {
        "id": data["id"],
        "name": data["name"],
        "description": data["description"],
        "dsl": json.loads(data["dsl_json"]),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
    }
