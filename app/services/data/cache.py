"""Small in-process TTL cache for data provider calls."""
from __future__ import annotations

import time
from threading import Lock
from typing import Any


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

