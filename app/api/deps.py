"""FastAPI auth dependencies: resolve the current user from a JWT and gate by
role. Only reseller+ accounts may use the panel; plain users are rejected."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api import security
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = security.decode_token(creds.credentials, "access")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = await User.filter(id=int(payload["sub"])).first()
    if user is None or user.is_blocked or user.role < User.Role.reseller:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    return user


def require_role(min_role: int):
    """Dependency factory: require at least ``min_role`` (a User.Role value)."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role < min_role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _guard
