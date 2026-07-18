"""SQLite initialization and legacy JSON migration."""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DATA_DIR, DB_PATH, PROJECT_DIR


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
    migrate_legacy_json()


def migrate_legacy_json() -> None:
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

