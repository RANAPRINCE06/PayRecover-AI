import logging
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import User
from app.schemas.contracts import LoginRequest, TokenResponse, UserResponse
from app.core.auth import (
    verify_password,
    verify_dummy_password,
    create_access_token,
    decode_access_token,
    revoke_token,
    get_current_user,
    security_bearer,
    ACCESS_TOKEN_EXPIRE_SECONDS
)
from app.core.rate_limiter import login_rate_limiter

logger = logging.getLogger("payrecover.api.auth")
router = APIRouter(tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user via email and password with 2D rate-limiting and timing-safe checks.
    Returns signed JWT bearer token containing a unique JTI.
    """
    email_clean = payload.email.strip().lower()

    # 1. Evaluate rate limits across IP and Account dimensions
    login_rate_limiter.check_rate_limit(request, email_clean)

    # 2. Database lookup
    user = db.query(User).filter(User.email == email_clean).first()

    # 3. Timing-safe credential verification to eliminate user enumeration
    if user:
        is_valid = verify_password(payload.password, user.hashed_password)
    else:
        # Run dummy bcrypt check so timing is indistinguishable from existing user
        verify_dummy_password(payload.password)
        is_valid = False

    # 4. Handle authentication failure
    if not is_valid:
        login_rate_limiter.record_failed_attempt(request, email_clean)
        logger.warning(f"Failed login attempt for email: '{email_clean}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 5. Check account activation
    if not user.is_active:
        logger.warning(f"Login attempt for deactivated user: '{email_clean}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your user account is deactivated. Please contact an administrator."
        )

    # 6. Authentication succeeded — record successful attempt
    login_rate_limiter.record_successful_attempt(request, email_clean)

    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role, "name": user.name},
        expires_delta=timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    )

    logger.info(f"Successful login for user '{user.email}' (role: {user.role})")
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
):
    """
    Server-side token revocation via Redis.
    Idempotent: revoking an already revoked token is safe and returns 200.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required. Please provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    raw_token = credentials.credentials
    # Validate token signature and expiration
    payload = decode_access_token(raw_token)

    # Server-side blacklist token in Redis
    revoke_token(raw_token)

    user_id = payload.get("sub", "unknown")
    logger.info(f"User '{user_id}' logged out; token JTI '{payload.get('jti')}' revoked.")
    return {"message": "Logged out successfully", "user_id": user_id}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Return currently authenticated user profile without exposing password hashes.
    Enforces token revocation blacklist.
    """
    return UserResponse.model_validate(current_user)
