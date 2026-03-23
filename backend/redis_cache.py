"""
Redis-backed cache and lock helpers with an in-process fallback.
"""

from __future__ import annotations

import fnmatch
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

try:
    import redis

    REDIS_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - exercised when redis isn't installed
    redis = None
    REDIS_IMPORT_ERROR = exc


@dataclass
class _MemoryValue:
    value: str
    expires_at: Optional[float]


class _MemoryBackend:
    """Best-effort fallback when Redis is unavailable."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, _MemoryValue] = {}

    def _purge_if_expired(self, key: str) -> None:
        item = self._values.get(key)
        if not item:
            return
        if item.expires_at is not None and item.expires_at <= time.time():
            self._values.pop(key, None)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._purge_if_expired(key)
            item = self._values.get(key)
            return item.value if item else None

    def set(
        self, key: str, value: str, ex: Optional[int] = None, nx: bool = False
    ) -> bool:
        expires_at = time.time() + ex if ex else None
        with self._lock:
            self._purge_if_expired(key)
            if nx and key in self._values:
                return False
            self._values[key] = _MemoryValue(value=value, expires_at=expires_at)
            return True

    def delete(self, *keys: str) -> int:
        deleted = 0
        with self._lock:
            for key in keys:
                if key in self._values:
                    self._values.pop(key, None)
                    deleted += 1
        return deleted

    def keys(self, pattern: str) -> list[str]:
        with self._lock:
            for key in list(self._values):
                self._purge_if_expired(key)
            return [key for key in self._values if fnmatch.fnmatch(key, pattern)]


class RedisCache:
    """Small JSON cache used for API payloads, locks, and sync status."""

    def __init__(self, url: Optional[str] = None, prefix: str = "photo_face") -> None:
        self.prefix = prefix.rstrip(":")
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._memory_backend = _MemoryBackend()
        self._client = None
        self._backend_name = "memory"
        self._connect()

    def _connect(self) -> None:
        if redis is None:
            logger.warning(
                "redis package is unavailable, using in-memory cache fallback: {}",
                REDIS_IMPORT_ERROR,
            )
            return

        try:
            client = redis.Redis.from_url(
                self.url,
                decode_responses=True,
                health_check_interval=30,
                socket_timeout=2,
            )
            client.ping()
        except Exception as exc:  # pragma: no cover - depends on local Redis availability
            logger.warning(
                "Redis is unavailable at {}. Falling back to in-memory cache: {}",
                self.url,
                exc,
            )
            return

        self._client = client
        self._backend_name = "redis"
        logger.info("Connected to Redis cache at {}", self.url)

    def is_redis(self) -> bool:
        return self._client is not None

    def backend_name(self) -> str:
        return self._backend_name

    def namespaced(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    def get_json(self, key: str, default: Any = None) -> Any:
        raw = self._get(self.namespaced(key))
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return self._set(self.namespaced(key), json.dumps(value), ex=ttl)

    def delete(self, *keys: str) -> int:
        namespaced_keys = [self.namespaced(key) for key in keys]
        return self._delete(*namespaced_keys)

    def delete_prefix(self, prefix: str) -> int:
        pattern = self.namespaced(f"{prefix}*")
        keys = self._keys(pattern)
        if not keys:
            return 0
        return self._delete(*keys)

    def acquire_lock(self, key: str, ttl: int = 900) -> Optional[str]:
        token = uuid.uuid4().hex
        namespaced_key = self.namespaced(key)
        acquired = self._set(namespaced_key, token, ex=ttl, nx=True)
        return token if acquired else None

    def release_lock(self, key: str, token: str) -> bool:
        namespaced_key = self.namespaced(key)
        current = self._get(namespaced_key)
        if current != token:
            return False
        self._delete(namespaced_key)
        return True

    def _get(self, key: str) -> Optional[str]:
        if self._client is not None:
            return self._client.get(key)
        return self._memory_backend.get(key)

    def _set(
        self, key: str, value: str, ex: Optional[int] = None, nx: bool = False
    ) -> bool:
        if self._client is not None:
            result = self._client.set(key, value, ex=ex, nx=nx)
            return bool(result)
        return self._memory_backend.set(key, value, ex=ex, nx=nx)

    def _delete(self, *keys: str) -> int:
        if not keys:
            return 0
        if self._client is not None:
            return int(self._client.delete(*keys))
        return self._memory_backend.delete(*keys)

    def _keys(self, pattern: str) -> list[str]:
        if self._client is not None:
            return list(self._client.scan_iter(match=pattern))
        return self._memory_backend.keys(pattern)
