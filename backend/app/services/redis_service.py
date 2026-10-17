import json
import time
import logging
from typing import Any, Optional, Tuple, Dict
from app.core.config import settings

logger = logging.getLogger("payrecover.redis")


class RedisService:
    """
    Resilient Redis client abstraction with in-memory local fallback.
    Supports TTL expiration, counter incrementing, and key checks.
    Prevents any server failure if a Redis instance is offline.
    """

    def __init__(self):
        self._redis = None
        # Maps key -> (serialized_value: str, expire_at: Optional[float])
        self._in_memory_store: Dict[str, Tuple[str, Optional[float]]] = {}
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
        """Store a key-value pair with optional TTL."""
        serialized = json.dumps(value) if isinstance(value, (dict, list, bool, int, float)) else str(value)
        if self._is_connected and self._redis:
            try:
                self._redis.set(key, serialized, ex=expire_seconds)
                return True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        expire_at = (time.time() + expire_seconds) if expire_seconds else None
        self._in_memory_store[key] = (serialized, expire_at)
        return True

    def get(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize a value by key. Enforces TTL in in-memory fallback."""
        raw = None
        if self._is_connected and self._redis:
            try:
                raw = self._redis.get(key)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        if raw is None:
            entry = self._in_memory_store.get(key)
            if entry is not None:
                if isinstance(entry, tuple) and len(entry) == 2:
                    val_str, expire_at = entry
                    if expire_at is not None and time.time() > expire_at:
                        self._in_memory_store.pop(key, None)
                        return None
                    raw = val_str
                else:
                    raw = entry

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except Exception:
            return raw

    def delete(self, key: str) -> bool:
        """Remove a key from Redis and fallback store."""
        if self._is_connected and self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._in_memory_store.pop(key, None)
        return True

    def incr(self, key: str, expire_seconds: Optional[int] = None) -> int:
        """
        Increment an integer counter atomically in Redis or fallback store.
        Sets expiration TTL if newly created.
        """
        if self._is_connected and self._redis:
            try:
                val = self._redis.incr(key)
                if val == 1 and expire_seconds:
                    self._redis.expire(key, expire_seconds)
                return int(val)
            except Exception as e:
                logger.warning(f"Redis incr failed: {e}")

        # In-memory fallback
        now = time.time()
        current_val = 0
        expire_at = (now + expire_seconds) if expire_seconds else None

        entry = self._in_memory_store.get(key)
        if entry is not None:
            val_str, exp = entry if isinstance(entry, tuple) else (entry, None)
            if exp is not None and now > exp:
                current_val = 0
                expire_at = (now + expire_seconds) if expire_seconds else None
            else:
                try:
                    current_val = int(val_str)
                except (ValueError, TypeError):
                    current_val = 0
                expire_at = exp

        new_val = current_val + 1
        self._in_memory_store[key] = (str(new_val), expire_at)
        return new_val

    def ttl(self, key: str) -> int:
        """
        Return remaining TTL in seconds (-2 if key does not exist or expired, -1 if no TTL).
        """
        if self._is_connected and self._redis:
            try:
                return int(self._redis.ttl(key))
            except Exception as e:
                logger.warning(f"Redis ttl failed: {e}")

        # In-memory fallback
        entry = self._in_memory_store.get(key)
        if entry is None:
            return -2
        val_str, exp = entry if isinstance(entry, tuple) else (entry, None)
        if exp is None:
            return -1
        rem = exp - time.time()
        if rem <= 0:
            self._in_memory_store.pop(key, None)
            return -2
        return max(0, int(rem))

    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        if self._is_connected and self._redis:
            try:
                return bool(self._redis.exists(key))
            except Exception as e:
                logger.warning(f"Redis exists failed: {e}")

        return self.get(key) is not None

    def clear_in_memory(self):
        """Utility for test suites to reset in-memory fallback state."""
        self._in_memory_store.clear()

    @property
    def is_connected(self) -> bool:
        return self._is_connected


redis_service = RedisService()
