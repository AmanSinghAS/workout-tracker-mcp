from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anyio
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from src.db.session import engine
from src.domain.payloads import WorkoutIngestPayload
from src.service.ingest_workout import ingest_workout

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
RESOURCE_SERVER_URL = os.getenv("RESOURCE_SERVER_URL", f"http://{HOST}:{PORT}")
DEFAULT_EMAIL_ALLOWLIST = {"amansinghdallas.03@gmail.com"}
ALLOWED_EMAILS_FILE = os.getenv("ALLOWED_EMAILS_FILE", "allowed_emails.txt")
ALLOWED_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
ALLOW_ANY_GOOGLE_CLIENT_ID = os.getenv("ALLOW_ANY_GOOGLE_CLIENT_ID", "false").lower() == "true"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
if not ALLOW_ANY_GOOGLE_CLIENT_ID and not GOOGLE_CLIENT_ID:
    raise ValueError("GOOGLE_CLIENT_ID is required for Google authentication (set ALLOW_ANY_GOOGLE_CLIENT_ID=true to disable)")


def load_allowed_emails(path: str) -> set[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"Allowed emails file not found at {file_path}")

    raw = file_path.read_text(encoding="utf-8")
    entries: set[str] = set()
    for line in raw.splitlines():
        for email in line.split(","):
            cleaned = email.strip().lower()
            if cleaned:
                entries.add(cleaned)

    if not entries:
        entries = set(DEFAULT_EMAIL_ALLOWLIST)

    return entries


class GoogleTokenVerifier(TokenVerifier):
    def __init__(self, client_id: str | None, allowed_emails: set[str], allow_any_client_id: bool):
        self.client_id = client_id
        self.allowed_emails = allowed_emails
        self.allow_any_client_id = allow_any_client_id
        self._request = Request()

    def _verify(self, token: str) -> AccessToken | None:
        try:
            claims: dict[str, Any] = id_token.verify_oauth2_token(
                token, self._request, audience=None if self.allow_any_client_id else self.client_id
            )
        except Exception:
            return None

        issuer = claims.get("iss")
        if issuer not in ALLOWED_ISSUERS:
            return None

        email = claims.get("email")
        email_verified = claims.get("email_verified")
        if not email or email_verified is not True:
            return None

        normalized_email = str(email).lower()
        if normalized_email not in self.allowed_emails:
            return None

        expires_at = claims.get("exp")
        try:
            expires_at_int = int(expires_at) if expires_at is not None else None
        except (TypeError, ValueError):
            expires_at_int = None
        if expires_at_int is None:
            return None

        return AccessToken(
            token=token,
            client_id=str(claims.get("aud", "")),
            scopes=[],
            expires_at=expires_at_int,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await anyio.to_thread.run_sync(self._verify, token)


mcp = FastMCP(
    "workout-tracker-mcp",
    instructions="Persist workout entries to the Workout Tracker system of record.",
    host=HOST,
    port=PORT,
    auth=AuthSettings(
        issuer_url="https://accounts.google.com",
        resource_server_url=RESOURCE_SERVER_URL,
    ),
    token_verifier=GoogleTokenVerifier(GOOGLE_CLIENT_ID, load_allowed_emails(ALLOWED_EMAILS_FILE), ALLOW_ANY_GOOGLE_CLIENT_ID),
)


def handle_add_workout_entry(
    payload: WorkoutIngestPayload | dict, session: Session
) -> dict:
    return ingest_workout(session, payload)


@mcp.tool(name="add_workout_entry")
def add_workout_entry(payload: WorkoutIngestPayload) -> dict:
    """Validate and persist a workout entry payload."""
    try:
        with Session(engine) as session:
            return handle_add_workout_entry(payload, session)
    except ValueError as exc:
        detail = str(exc) or repr(exc)
        raise ValueError(f"Invalid workout payload: {detail}") from exc
    except SQLAlchemyError as exc:
        detail = str(exc) or repr(exc)
        raise ValueError(f"Database error while ingesting workout entry: {detail}") from exc
    except Exception as exc:
        detail = str(exc) or repr(exc)
        raise ValueError(f"Unexpected error while ingesting workout entry: {detail}") from exc
