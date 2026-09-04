import json
import logging
from typing import Any, Optional
from app.core.config import settings

logger = logging.getLogger("payrecover.redis")


class RedisService:
    """
    Resilient Redis client abstraction with in-memory local dict fallback.
    Prevents any server failure if a Redis instance is offline.
    """

    def __init__(self):
        self._redis = None
        self._in_memory_store = {}
        self._is_connected = False
        self._init_connection()

    def _init_connection(self):
        try:
            import redis
            client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.5
            )
            client.ping()
            self._redis = client
            self._is_connected = True
            logger.info("Connected to Redis instance successfully.")
        except Exception as e:
            self._is_connected = False
            logger.warning(f"Redis unavailable ({e}). Using resilient In-Memory state store.")

    def set(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        serialized = json.dumps(value) if isinstance(value, (dict, list, bool, int, float)) else str(value)
        if self._is_connected and self._redis:
            try:
                self._redis.set(key, serialized, ex=expire_seconds)
                return True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        self._in_memory_store[key] = serialized
        return True

    def get(self, key: str) -> Optional[Any]:
        raw = None
        if self._is_connected and self._redis:
            try:
                raw = self._redis.get(key)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        if raw is None:
            raw = self._in_memory_store.get(key)

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except Exception:
            return raw

    def delete(self, key: str) -> bool:
        if self._is_connected and self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._in_memory_store.pop(key, None)
        return True

    @property
    def is_connected(self) -> bool:
        return self._is_connected


redis_service = RedisService()
