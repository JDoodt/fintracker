from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Get the current user from the session. Raises 401 if not authenticated."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
        )
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
        )
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get the current user from the session. Returns None if not authenticated."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require that the current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
