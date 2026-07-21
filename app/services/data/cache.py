"""Small in-process TTL cache for data provider calls."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from config import CACHE_DIR


class TTLCache:
    def __init__(self):
        self._items: dict[str, tuple[float, int, Any]] = {}
        self._lock = Lock()

    def get(self, key: str):
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            ts, ttl, value = item
            if time.time() - ts > ttl:
                self._items.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int):
        with self._lock:
            self._items[key] = (time.time(), ttl_seconds, value)


cache = TTLCache()


class PersistentCache:
    """Atomic JSON cache with explicit fresh/stale state."""

    def __init__(self, root: Path | None = None):
        self.root = root or CACHE_DIR / "provider"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def key(self, method: str, args: tuple, kwargs: dict) -> str:
        raw = json.dumps(["schema-v2", method, args, kwargs], ensure_ascii=False, sort_keys=True, default=str)
        return f"{method}-{hashlib.sha256(raw.encode()).hexdigest()[:24]}"

    def get(self, key: str, ttl_seconds: int, allow_stale: bool = False):
        path = self.root / f"{key}.json"
        try:
            payload = json.loads(path.read_text())
            age = max(0, time.time() - float(payload["saved_at"]))
            if age > ttl_seconds and not allow_stale:
                return None
            return payload.get("value"), ("stale" if age > ttl_seconds else "fresh"), payload.get("saved_at")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: Any):
        path = self.root / f"{key}.json"
        temp = path.with_suffix(".tmp")
        serialized = asdict(value) if is_dataclass(value) else value
        payload = {"saved_at": time.time(), "value": serialized}
        with self._lock:
            temp.write_text(json.dumps(payload, ensure_ascii=False, default=str))
            temp.replace(path)


persistent_cache = PersistentCache()
