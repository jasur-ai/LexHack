"""Small in-process TTL + LRU cache for final answers (identical questions are answered instantly)."""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from typing import Any

from lex_agent.language.transliterator import normalize_uzbek_apostrophes


def normalize_question(text: str) -> str:
    norm = normalize_uzbek_apostrophes(text or "").lower()
    norm = re.sub(r"[\s\u00a0]+", " ", norm)
    norm = re.sub(r"[?!.,;:]+$", "", norm.strip())
    return norm


class AnswerCache:
    def __init__(self, *, max_items: int = 512, ttl_sec: int = 6 * 3600) -> None:
        self.max_items = max(0, max_items)
        self.ttl_sec = max(0, ttl_sec)
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @property
    def enabled(self) -> bool:
        return self.max_items > 0 and self.ttl_sec > 0

    def get(self, key: str | None) -> Any | None:
        if not key or not self.enabled:
            return None
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            stored_at, value = item
            if time.monotonic() - stored_at > self.ttl_sec:
                self._data.pop(key, None)
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: str | None, value: Any) -> None:
        if not key or not self.enabled:
            return
        with self._lock:
            self._data[key] = (time.monotonic(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict[str, int]:
        return {"items": len(self._data), "hits": self.hits, "misses": self.misses}
