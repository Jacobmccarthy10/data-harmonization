"""Lightweight in-memory session store. No database in v1."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, Optional


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, Any]] = {}

    def put(self, payload: Dict[str, Any]) -> str:
        key = str(uuid.uuid4())
        with self._lock:
            self._data[key] = payload
        return key

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._data.get(key)


analyses = MemoryStore()
discover_uploads = MemoryStore()
coverage_runs = MemoryStore()
