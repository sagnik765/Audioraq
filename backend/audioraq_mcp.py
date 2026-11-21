"""Hosted Audioraq MCP tools for the production FastAPI application."""

from __future__ import annotations

import base64
from contextvars import ContextVar
import json
import os
from typing import Any, Literal

import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import AudioContent, CallToolResult, TextContent

from backend.text_to_audio_api import API_KEY_PREFIX, API_SCOPE_SPEECH, hash_api_key


TIMEOUT = httpx.Timeout(180.0, connect=15.0)
QUALITY_PROFILES = (
    "podcast-education-calm",
    "podcast-dialogue",
    "podcast-storytelling",
)


class AudioraqApiKeyVerifier(TokenVerifier):
    """Validate opaque Audioraq developer keys against the existing key store."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token.startswith(API_KEY_PREFIX):
            return None
        document = await self.db.developer_api_keys.find_one(
            {"key_hash": hash_api_key(token), "revoked_at": None}
        )
        if not document or API_SCOPE_SPEECH not in document.get("scopes", []):
            return None
        return AccessToken(
            token=token,
            client_id=document["id"],
            subject=document.get("user_id"),
            scopes=document.get("scopes", []),
        )



_current_access_token: ContextVar[AccessToken | None] = ContextVar(
    "audioraq_mcp_access_token",
    default=None,
)


class AudioraqBearerAuthMiddleware:
    """Authenticate Audioraq API keys without advertising an OAuth flow."""

    def __init__(self, app: Any, verifier: AudioraqApiKeyVerifier) -> None:
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        authorization = dict(scope.get("headers", [])).get(b"authorization", b"")
        try:
            scheme, credential = authorization.decode("latin-1").split(" ", 1)
        except ValueError:
            scheme, credential = "", ""
        access_token = None
        if scheme.lower() == "bearer" and credential.strip():
            access_token = await self.verifier.verify_token(credential.strip())

        if access_token is None:
            body = json.dumps(
                {"error": "invalid_api_key", "message": "A valid Audioraq API key is required."}
            ).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"cache-control", b"no-store"),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        context_token = _current_access_token.set(access_token)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_access_token.reset(context_token)


def build_audioraq_mcp_server(db: Any) -> tuple[MCPServer, Any]:
    """Build the bearer-protected tools and deployed Streamable HTTP app."""
    api_root = os.environ.get(
        "AUDIORAQ_MCP_API_ROOT",
        f"http://127.0.0.1:{os.environ.get('PORT', '8001')}/api/v1/audio",
    ).rstrip("/")
    verifier = AudioraqApiKeyVerifier(db)
    server = MCPServer(
        "Audioraq",
        instructions=(
            "Use list_voices to browse Audioraq's public voice catalog. Use create_speech "
            "to render user-approved narration as MP3 or WAV. Speech requests use the "
            "authenticated user's Audioraq developer key and count toward its API usage."
        ),
    )

    @server.tool()
    async def list_voices() -> dict[str, Any]:
        """List Audioraq's public voice catalog and delivery profiles."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
                response = await client.get(f"{api_root}/voices")
        except httpx.TimeoutException as exc:
            raise RuntimeError("Audioraq voice lookup timed out.") from exc
        except httpx.RequestError as exc:
            raise RuntimeError("Could not reach the Audioraq API.") from exc
        if response.status_code >= 300:
            raise RuntimeError(f"Audioraq voice lookup returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("Audioraq returned an invalid voice catalog response.") from exc

    @server.tool()
    async def create_speech(
        text: str,
        voice: str = "aman-warm-analyst",
        output_format: Literal["mp3", "wav"] = "mp3",
        quality_profile: Literal[
            "podcast-education-calm",
            "podcast-dialogue",
            "podcast-storytelling",
        ] = "podcast-education-calm",
    ) -> CallToolResult:
        """Render approved text and return Audioraq audio plus request metadata."""
        approved_text = text.strip()
        if not approved_text:
            raise ValueError("Narration text cannot be empty.")
        if quality_profile not in QUALITY_PROFILES:
            raise ValueError("Unsupported Audioraq quality profile.")

        access_token = _current_access_token.get()
        if access_token is None:
            raise RuntimeError("An Audioraq API key is required for speech generation.")

        payload = {
            "input": approved_text,
            "voice": voice,
            "format": output_format,
            "quality_profile": quality_profile,
        }
        headers = {
            "Accept": "audio/mpeg" if output_format == "mp3" else "audio/wav",
            "Authorization": f"Bearer {access_token.token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
                response = await client.post(f"{api_root}/speech", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Audioraq rendering timed out. It may have completed; check API usage before retrying."
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError("Could not reach the Audioraq API; no automatic retry was attempted.") from exc

        if response.status_code == 401:
            raise RuntimeError("Audioraq rejected this key. Check whether it was revoked.")
        if response.status_code == 413:
            raise RuntimeError("Audioraq's configured character limit was exceeded.")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            message = "Audioraq rate limit reached."
            if retry_after:
                message += f" Retry after {retry_after} seconds."
            raise RuntimeError(message)
        if response.status_code >= 300:
            raise RuntimeError(f"Audioraq speech rendering returned HTTP {response.status_code}.")

        media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        allowed_media_types = {
            "mp3": {"audio/mpeg", "audio/mp3", "audio/x-mp3"},
            "wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
        }
        if media_type not in allowed_media_types[output_format]:
            raise RuntimeError("Audioraq did not return the requested audio format.")

        audio = response.content
        if not audio:
            raise RuntimeError("Audioraq returned an empty audio response.")
        if output_format == "wav" and not (
            len(audio) >= 12 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
        ):
            raise RuntimeError("Audioraq's response does not have a valid WAV signature.")
        if output_format == "mp3":
            has_id3_header = audio.startswith(b"ID3")
            has_mpeg_frame = len(audio) >= 2 and audio[0] == 0xFF and audio[1] & 0xE0 == 0xE0
            if not (has_id3_header or has_mpeg_frame):
                raise RuntimeError("Audioraq's response does not have a valid MP3 signature.")

        metadata = {
            "request_id": response.headers.get("X-Request-Id"),
            "voice": response.headers.get("X-Audioraq-Voice", voice),
            "format": output_format,
            "quality_profile": quality_profile,
            "characters": response.headers.get("X-Audioraq-Characters", str(len(approved_text))),
            "provider": response.headers.get("X-Audioraq-Provider"),
            "model": response.headers.get("X-Audioraq-Model"),
            "output_bytes": len(audio),
        }
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text="Audioraq audio render completed. Metadata: "
                    + json.dumps(metadata, ensure_ascii=False),
                ),
                AudioContent(
                    type="audio",
                    data=base64.b64encode(audio).decode("ascii"),
                    mime_type=media_type,
                ),
            ]
        )

    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "www.audioraq.com",
            "www.audioraq.com:*",
            "audioraq.com",
            "audioraq.com:*",
            "localhost:*",
            "127.0.0.1:*",
            "testserver",
        ],
        allowed_origins=[
            "https://www.audioraq.com",
            "https://audioraq.com",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
    )
    http_app = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        max_request_body_size=64 * 1024,
        host="www.audioraq.com",
        transport_security=transport_security,
    )
    return server, AudioraqBearerAuthMiddleware(http_app, verifier)
