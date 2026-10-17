import uuid
import logging
from datetime import datetime, timezone, timedelta
import time
from typing import Optional, Dict, Any, Tuple
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.entities import User, UserRole
from app.services.redis_service import redis_service

logger = logging.getLogger("payrecover.auth")

SECRET_KEY = getattr(settings, "SECRET_KEY", "payrecover-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 86400  # 24 hours

security_bearer = HTTPBearer(auto_error=False)

# Precomputed dummy bcrypt hash to guarantee constant-time check when user does not exist
DUMMY_BCRYPT_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj40bhe8Gz2K"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False


def verify_dummy_password(plain_password: str) -> bool:
    """Perform dummy bcrypt check to equalize timing for nonexistent users."""
    return verify_password(plain_password, DUMMY_BCRYPT_HASH)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token with a unique JTI."""
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    expire = now_utc + (expires_delta or timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS))
    if "jti" not in to_encode:
        to_encode["jti"] = f"jwt_{uuid.uuid4().hex}"
    to_encode.update({"exp": expire, "iat": now_utc})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature.",
            headers={"WWW-Authenticate": "Bearer"}
        )


def revoke_token(token: str) -> bool:
    """
    Revoke a token by storing its JTI in Redis with a TTL equal to remaining lifetime.
    Idempotent.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        jti = payload.get("jti")
        if not jti:
            logger.warning("Token revocation requested for token missing JTI.")
            return False

        exp = payload.get("exp")
        now_ts = time.time()
        if exp:
            remaining_ttl = int(exp - now_ts)
        else:
            remaining_ttl = ACCESS_TOKEN_EXPIRE_SECONDS

        if remaining_ttl <= 0:
            remaining_ttl = 1  # Expired naturally; set 1s in revocation store

        redis_key = f"auth:revoked:{jti}"
        redis_service.set(
            redis_key,
            {"revoked_at": datetime.now(timezone.utc).isoformat(), "sub": payload.get("sub")},
            expire_seconds=remaining_ttl
        )
        logger.info(f"Token revoked successfully (JTI: {jti}, TTL: {remaining_ttl}s)")
        return True
    except Exception as e:
        logger.warning(f"Error during token revocation: {e}")
        return False


def is_token_revoked(jti: str) -> bool:
    """
    Check Redis revocation state for a token JTI.
    Rejects revoked tokens. Handles Redis availability failure safely.
    """
    if not getattr(settings, "AUTH_REVOCATION_ENABLED", True):
        return False

    redis_key = f"auth:revoked:{jti}"
    try:
        revoked_val = redis_service.get(redis_key)
        if revoked_val is not None:
            return True

        # Check if Redis connection is offline and fail-closed policy is requested
        if not redis_service.is_connected and getattr(settings, "AUTH_FAIL_CLOSED_ON_REDIS_ERROR", False):
            logger.error(f"Redis unavailable and fail-closed enabled during revocation check for JTI: {jti}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable. Please retry later."
            )

        return False
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Redis revocation lookup failed for JTI '{jti}': {e}")
        if getattr(settings, "AUTH_FAIL_CLOSED_ON_REDIS_ERROR", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable. Please retry later."
            )
        return False


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency requiring a valid Bearer token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required. Please provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(credentials.credentials)

    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        logger.warning(f"Rejected request using revoked token (JTI: {jti})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user subject identifier.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact an administrator."
        )

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """FastAPI dependency returning the user if credentials present, or None."""
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        jti = payload.get("jti")
        if jti and is_token_revoked(jti):
            return None
        user_id = payload.get("sub")
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.is_active:
                return user
    except Exception:
        pass
    return None
