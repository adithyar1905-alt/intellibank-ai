from collections.abc import Callable
from fastapi import HTTPException, status

from app.core.authentication import CurrentUser
from app.models.user import User


def require_roles(*required_roles: str) -> Callable[[User], User]:
    if not required_roles:
        raise ValueError("At least one role is required.")

    def check_roles(user: CurrentUser) -> User:
        assigned_roles = {role.name for role in user.roles}
        if "Super Admin" not in assigned_roles and not assigned_roles.intersection(
            required_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role.",
            )
        return user

    return check_roles


def require_permissions(*required_permissions: str) -> Callable[[User], User]:
    if not required_permissions:
        raise ValueError("At least one permission is required.")

    def check_permissions(user: CurrentUser) -> User:
        if any(role.name == "Super Admin" for role in user.roles):
            return user
        granted = {
            f"{permission.resource}:{permission.action}"
            for role in user.roles
            for permission in role.permissions
        }
        if not set(required_permissions).issubset(granted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return user

    return check_permissions