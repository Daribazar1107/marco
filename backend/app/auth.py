"""Who is calling? Every /api request carries the Supabase login token:
    Authorization: Bearer <access_token>
We ask Supabase if the token is real, then make sure the user has a profile row."""

import time
import uuid
from dataclasses import dataclass

import httpx
from fastapi import Header, HTTPException
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import engine
from app.models import Profile

# token -> (user, valid until). Saves one Supabase call per request.
_cache: dict[str, tuple["CurrentUser", float]] = {}
CACHE_SECONDS = 60


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str


async def _ask_supabase(token: str) -> CurrentUser:
    if not settings.supabase_anon_key:
        raise HTTPException(500, "SUPABASE_ANON_KEY .env файлд алга байна")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
        )
    if response.status_code != 200:
        raise HTTPException(401, "Нэвтрэлт хүчингүй байна. Дахин нэвтэрнэ үү.")
    data = response.json()
    return CurrentUser(id=uuid.UUID(data["id"]), email=data.get("email") or "")


def _ensure_profile(user: CurrentUser) -> None:
    """Conversations and Google tokens point to profiles, so the row must exist."""
    with engine.begin() as connection:
        connection.execute(
            insert(Profile)
            .values(id=user.id, email=user.email)
            .on_conflict_do_nothing(index_elements=["id"])
        )


async def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Нэвтрээгүй байна")
    token = authorization.removeprefix("Bearer ").strip()

    cached = _cache.get(token)
    if cached and cached[1] > time.time():
        return cached[0]

    user = await _ask_supabase(token)
    _ensure_profile(user)
    _cache[token] = (user, time.time() + CACHE_SECONDS)
    return user
