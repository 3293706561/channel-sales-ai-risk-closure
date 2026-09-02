from __future__ import annotations

import secrets

from fastapi import Header, HTTPException
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .models import User

password_hash = PasswordHash.recommended()
sessions: dict[str, str] = {}


def issue_token(user_id: str) -> str:
    token = secrets.token_urlsafe(24)
    sessions[token] = user_id
    return token


def current_user(authorization: str | None = Header(default=None), db: Session | None = None) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录。")
    token = authorization.removeprefix("Bearer ")
    user_id = sessions.get(token)
    if not user_id or db is None:
        raise HTTPException(401, "登录已失效，请重新登录。")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "账号不可用。")
    return user
