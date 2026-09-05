import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import User
from app.schemas.contracts import LoginRequest, TokenResponse, UserResponse
from app.core.auth import verify_password, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_SECONDS
from app.services.event_service import event_service

logger = logging.getLogger("payrecover.api.auth")
router = APIRouter(tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user via email and password, returning signed JWT bearer token and profile.
    """
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: '{email_clean}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        logger.warning(f"Login attempt for deactivated user: '{email_clean}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your user account is deactivated. Please contact an administrator."
        )

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
def logout(current_user: User = Depends(get_current_user)):
    """
    Acknowledge user logout.
    """
    logger.info(f"User '{current_user.email}' logged out.")
    return {"message": "Logged out successfully", "user_id": current_user.id}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Return currently authenticated user profile without exposing password hashes.
    """
    return UserResponse.model_validate(current_user)
