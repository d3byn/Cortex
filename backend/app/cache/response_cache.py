import hashlib
import json
import threading
import time
from typing import Any, Optional

class ResponseCache:
    """An in-memory cache for full /query responses.

    Two things make an entry go stale:
      - TIME: entries older than `ttl_seconds` are treated as missing.
      - DATA CHANGES: `version` is bumped whenever a document is added or
        deleted, and the version is baked into every cache key. A change
        doesn't need to hunt down and delete old entries — they simply
        can never be matched again, and old versions expire naturally.
    """

    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}
        self._version = 0

    def bump_version(self) -> None:
        with self._lock:
            self._version += 1

    def make_key(self, **parts: Any) -> str:
        with self._lock:
            version = self._version
        raw = json.dumps({"v": version, **parts}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time() + self.ttl_seconds, value)

query_cache = ResponseCache()