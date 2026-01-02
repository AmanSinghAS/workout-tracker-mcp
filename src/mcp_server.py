from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any

from pydantic import AnyHttpUrl

import anyio
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.handlers.metadata import ProtectedResourceMetadataHandler
from mcp.server.auth.routes import build_resource_metadata_url
from mcp.shared.auth import ProtectedResourceMetadata
from mcp.server.fastmcp import FastMCP

from src.db.session import engine
from src.domain.payloads import WorkoutIngestPayload
from src.service.ingest_workout import ingest_workout

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
RESOURCE_SERVER_URL = os.getenv("RESOURCE_SERVER_URL", f"http://{HOST}:{PORT}/mcp")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
ALLOWED_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


class GoogleTokenVerifier(TokenVerifier):
    def __init__(self, client_id: str | None):
        self.client_id = client_id
        self._request = GoogleAuthRequest()

    def _verify(self, token: str) -> AccessToken | None:
        try:
            claims: dict[str, Any] = id_token.verify_oauth2_token(
                token, self._request, audience=self.client_id
            )
        except Exception:
            return None

        issuer = claims.get("iss")
        if issuer not in ALLOWED_ISSUERS:
            return None

        if self.client_id and claims.get("aud") != self.client_id:
            return None

        email = claims.get("email")
        email_verified = claims.get("email_verified")
        if not email or email_verified is not True:
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
    token_verifier=GoogleTokenVerifier(GOOGLE_CLIENT_ID),
)


resource_url = AnyHttpUrl(RESOURCE_SERVER_URL)
metadata = ProtectedResourceMetadata(
    resource=resource_url,
    authorization_servers=[AnyHttpUrl("https://accounts.google.com")],
    resource_name="Workout Tracker MCP",
)
metadata_handler = ProtectedResourceMetadataHandler(metadata)
metadata_url = build_resource_metadata_url(resource_url)
metadata_path = urlparse(str(metadata_url)).path


@mcp.custom_route(metadata_path, methods=["GET", "OPTIONS"])
async def oauth_protected_resource(request: StarletteRequest) -> Response:
    return await metadata_handler.handle(request)


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
