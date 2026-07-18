import importlib.util
from pathlib import Path


def _load_server():
    path = Path(__file__).resolve().parents[1] / "wyckoff-server.py"
    spec = importlib.util.spec_from_file_location("wyckoff_server_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sensitive_files_not_served():
    module = _load_server()
    client = module.app.test_client()
    assert client.get("/.env").status_code == 404
    assert client.get("/wyckoff-server.py").status_code == 404
    assert client.get("/.ragdoll_data/ragdoll.sqlite3").status_code == 404


def test_cors_blocks_untrusted_origin():
    module = _load_server()
    client = module.app.test_client()
    response = client.get("/api/status", headers={"Origin": "https://evil.example"})
    assert response.headers.get("Access-Control-Allow-Origin") is None

