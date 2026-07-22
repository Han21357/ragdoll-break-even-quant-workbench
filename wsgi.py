"""WSGI entry point for hosted deployments."""
from __future__ import annotations

import importlib.util
from pathlib import Path


server_path = Path(__file__).with_name("wyckoff-server.py")
spec = importlib.util.spec_from_file_location("ragdoll_server", server_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load server module from {server_path}")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
app = server.app
