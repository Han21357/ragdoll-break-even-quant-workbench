"""Runtime configuration for 老布偶猫回本之路."""
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

DATA_DIR = Path(os.getenv("RAGDOLL_DATA_DIR", PROJECT_DIR / ".ragdoll_data")).resolve()
CACHE_DIR = Path(os.getenv("RAGDOLL_CACHE_DIR", DATA_DIR / "cache")).resolve()
DB_PATH = Path(os.getenv("RAGDOLL_DB_PATH", DATA_DIR / "ragdoll.sqlite3")).resolve()
PORT = int(os.getenv("PORT", "8766"))

PYTHON_BIN = os.getenv("PYTHON_BIN") or sys.executable
WYCKOFF_BIN = os.getenv("WYCKOFF_BIN") or shutil.which("wyckoff") or ""

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "RAGDOLL_ALLOWED_ORIGINS",
        "http://localhost:8766,http://127.0.0.1:8766",
    ).split(",")
    if origin.strip()
]

A_SHARE_BACKTEST_DEFAULTS = {
    "timezone": "Asia/Shanghai",
    "lot_size": 100,
    "sellable_after_days": 1,
    "commission_rate": 0.0003,
    "min_commission": 5.0,
    "stamp_tax_rate": 0.001,
    "transfer_fee_rate": 0.00001,
    "slippage": 0.0005,
    "price_adjustment": "qfq",
    "allow_short": False,
    "initial_capital": 100000.0,
    "single_position_limit": 0.2,
    "benchmark": "sh.000300",
}

for path in (DATA_DIR, CACHE_DIR):
    path.mkdir(parents=True, exist_ok=True)
