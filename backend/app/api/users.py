import uuid
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import User, UserRole
from app.schemas.contracts import UserResponse, UserCreate, UserUpdate
from app.core.auth import hash_password
from app.core.rbac import require_admin

logger = logging.getLogger("payrecover.api.users")
router = APIRouter(tags=["User Management"])


@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: List all system users."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: Create a new system user with assigned role and hashed password."""
    email_clean = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{email_clean}' already exists."
        )

    # Validate role
    role_upper = payload.role.upper()
    valid_roles = [r.value for r in UserRole]
    if role_upper not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: {valid_roles}."
        )

    new_user = User(
        id=f"usr_{uuid.uuid4().hex[:10]}",
        email=email_clean,
        name=payload.name.strip(),
        hashed_password=hash_password(payload.password),
        role=role_upper,
        is_active=True,
        merchant_id=payload.merchant_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Admin '{admin.email}' created user '{new_user.email}' with role '{new_user.role}'")
    return UserResponse.model_validate(new_user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: Fetch user details by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: Update user name, role, active status, or password."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if payload.name is not None:
        user.name = payload.name.strip()

    if payload.role is not None:
        role_upper = payload.role.upper()
        valid_roles = [r.value for r in UserRole]
        if role_upper not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{payload.role}'. Must be one of: {valid_roles}."
            )
        user.role = role_upper

    if payload.is_active is not None:
        # Prevent deactivating the active admin making the call if they are the only admin
        if not payload.is_active and user.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own administrative account."
            )
        user.is_active = payload.is_active

    if payload.password is not None and payload.password.strip():
        user.hashed_password = hash_password(payload.password.strip())

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    logger.info(f"Admin '{admin.email}' updated user '{user.email}' (role: {user.role}, active: {user.is_active})")
    return UserResponse.model_validate(user)


@router.post("/{user_id}/toggle-active", response_model=UserResponse)
def toggle_user_active(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: Toggle user active status between active and deactivated."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.id == admin.id and user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own administrative account."
        )

    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    logger.info(f"Admin '{admin.email}' toggled user '{user.email}' active status to: {user.is_active}")
    return UserResponse.model_validate(user)
