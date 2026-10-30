import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response
from pwdlib import PasswordHash

from app.config import settings
from app.models import Credential, User

password_hash = PasswordHash.recommended()
COOKIE = "checkx_session"
_attempts: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """Per-process limiter; put a shared limiter at the proxy for multi-worker deployments."""
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    for ip in list(_attempts):
        if not _attempts[ip] or _attempts[ip][-1] < now - 60:
            del _attempts[ip]
    hits = _attempts[key]
    while hits and hits[0] < now - 60:
        hits.popleft()
    if len(hits) >= 20:
        raise HTTPException(429, "请求过于频繁，请稍后再试")
    hits.append(now)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_credential(user: User, kind: str, name: str, days: int):
    token = "cx_" + secrets.token_urlsafe(48)
    credential = await Credential.create(
        user=user,
        token_hash=digest(token),
        kind=kind,
        name=name,
        expires_at=datetime.now(UTC) + timedelta(days=days),
    )
    return credential, token


async def current_user(request: Request) -> User:
    authorization = request.headers.get("authorization", "")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "无效的访问令牌")
        kind = "api"
    else:
        token = request.cookies.get(COOKIE, "")
        kind = "session"
    if not token or len(token) > 256:
        raise HTTPException(401, "请先登录")
    credential = await Credential.get_or_none(
        token_hash=digest(token),
        kind=kind,
        expires_at__gt=datetime.now(UTC),
    ).select_related("user")
    if credential is None:
        raise HTTPException(401, "登录已过期或令牌无效")
    request.state.credential = credential
    return credential.user


def set_session(response: Response, token: str):
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_days * 86400,
        path="/",
    )
