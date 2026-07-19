"""Production WSGI entry point for cloud deployment."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SERVER_PATH = Path(__file__).resolve().parent / "wyckoff-server.py"
SPEC = importlib.util.spec_from_file_location("ragdoll_wyckoff_server", SERVER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load Flask application from {SERVER_PATH}")

module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
app = module.app
