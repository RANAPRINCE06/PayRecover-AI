import logging
from typing import List, Union
from fastapi import Depends, HTTPException, status

from app.models.entities import User, UserRole
from app.core.auth import get_current_user

logger = logging.getLogger("payrecover.rbac")


def require_roles(allowed_roles: List[Union[UserRole, str]]):
    """
    FastAPI dependency factory to enforce RBAC permissions.
    Rejects any request where the authenticated user's role is not in allowed_roles.
    """
    role_values = {r.value if hasattr(r, "value") else str(r) for r in allowed_roles}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in role_values:
            logger.warning(
                f"RBAC Violation: User '{current_user.email}' (role: {current_user.role}) "
                f"attempted to access an endpoint requiring one of: {role_values}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Role '{current_user.role}' is not authorized. Required: {list(role_values)}."
            )
        return current_user

    return role_checker


# Convenience dependencies
require_admin = require_roles([UserRole.ADMIN])
require_operator = require_roles([UserRole.ADMIN, UserRole.OPERATOR])
require_analyst = require_roles([UserRole.ADMIN, UserRole.ANALYST])
require_viewer = require_roles([UserRole.ADMIN, UserRole.OPERATOR, UserRole.ANALYST, UserRole.VIEWER])
