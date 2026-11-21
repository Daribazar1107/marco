"""Google login (OAuth 2.0, web flow) and per-user tokens.

1. Browser asks /api/google/connect -> gets Google's consent page URL
2. User agrees on Google's page -> Google sends them to /api/google/callback
3. We swap the code for a token and keep it in the google_tokens table
4. Tools call get_service(...) -> works with that user's Google account
"""

import json
import os
import secrets
import time
import uuid
from contextvars import ContextVar

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import BACKEND_DIR, settings
from app.db import engine
from app.models import GoogleToken

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",  # read and create events
    "https://www.googleapis.com/auth/gmail.compose",  # drafts and sending
    "https://www.googleapis.com/auth/contacts.readonly",  # search contacts (read only)
]
CLIENT_FILE = BACKEND_DIR / settings.google_client_file
REDIRECT_URI = f"{settings.public_url}/api/google/callback"

# Google allows plain http only for localhost; oauthlib needs to be told
if settings.public_url.startswith("http://localhost"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
# Google may give back scopes the user granted earlier; don't treat that as an error
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

# Which user the agent is working for right now (set before tools run)
current_user_id: ContextVar[uuid.UUID] = ContextVar("current_user_id")

# state -> (user_id, code_verifier, expires). Lives in memory: fine for one server.
_pending: dict[str, tuple[uuid.UUID, str, float]] = {}
STATE_SECONDS = 600


class GoogleNotConnected(Exception):
    pass


def _make_flow(**kwargs) -> Flow:
    if not CLIENT_FILE.exists():
        raise FileNotFoundError(
            f"{CLIENT_FILE.name} алга. Google Cloud-оос OAuth client (Web application) JSON татаж backend хавтсанд хадгална уу."
        )
    return Flow.from_client_secrets_file(
        str(CLIENT_FILE), scopes=SCOPES, redirect_uri=REDIRECT_URI, **kwargs
    )


def build_auth_url(user_id: uuid.UUID) -> str:
    state = secrets.token_urlsafe(24)
    flow = _make_flow(state=state, autogenerate_code_verifier=True)
    url, _ = flow.authorization_url(
        access_type="offline",  # gives a refresh_token, so no login again later
        prompt="consent",
        include_granted_scopes="true",
    )
    _pending[state] = (user_id, flow.code_verifier, time.time() + STATE_SECONDS)
    return url


def handle_callback(state: str, code: str) -> uuid.UUID:
    entry = _pending.pop(state, None)
    if not entry or entry[2] < time.time():
        raise ValueError("Хүчингүй эсвэл хугацаа нь дууссан state (CSRF хамгаалалт)")
    user_id, verifier, _ = entry
    flow = _make_flow(state=state, code_verifier=verifier)
    flow.fetch_token(code=code)
    save_creds(user_id, flow.credentials)
    return user_id


def save_creds(user_id: uuid.UUID, creds: Credentials) -> None:
    token = json.loads(creds.to_json())
    with engine.begin() as connection:
        connection.execute(
            insert(GoogleToken)
            .values(user_id=user_id, token=token)
            .on_conflict_do_update(index_elements=["user_id"], set_={"token": token})
        )


def load_creds(user_id: uuid.UUID) -> Credentials:
    with engine.connect() as connection:
        token = connection.execute(
            select(GoogleToken.token).where(GoogleToken.user_id == user_id)
        ).scalar_one_or_none()
    if token is None:
        raise GoogleNotConnected("Google бүртгэл холбогдоогүй байна")
    creds = Credentials.from_authorized_user_info(token, SCOPES)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # The user removed Marco's access in their Google account: ask to connect again
            disconnect(user_id)
            raise GoogleNotConnected("Google холболт хүчингүй болсон. Дахин холбоно уу.")
        save_creds(user_id, creds)  # keep the fresh token
    return creds


def is_connected(user_id: uuid.UUID) -> bool:
    with engine.connect() as connection:
        return (
            connection.execute(
                select(GoogleToken.user_id).where(GoogleToken.user_id == user_id)
            ).first()
            is not None
        )


def disconnect(user_id: uuid.UUID) -> None:
    with engine.begin() as connection:
        connection.execute(GoogleToken.__table__.delete().where(GoogleToken.user_id == user_id))


def get_service(name: str, version: str):
    """Tools call this. The user comes from current_user_id."""
    creds = load_creds(current_user_id.get())
    return build(name, version, credentials=creds, cache_discovery=False)
