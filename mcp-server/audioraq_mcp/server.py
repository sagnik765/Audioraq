"""Local stdio MCP server that exposes Audioraq's developer audio API."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import AudioContent, CallToolResult, TextContent


API_ROOT = "https://www.audioraq.com/api/v1/audio"
TIMEOUT = httpx.Timeout(180.0, connect=15.0)
QUALITY_PROFILES = (
    "podcast-education-calm",
    "podcast-dialogue",
    "podcast-storytelling",
)

mcp = MCPServer(
    "Audioraq",
    instructions=(
        "Use list_voices to inspect Audioraq's current public voice catalog. "
        "Use create_speech to render user-approved text as MP3 or WAV. "
        "create_speech sends narration to www.audioraq.com and requires the "
        "user's AUDIORAQ_API_KEY environment variable."
    ),
)


def _api_key() -> str:
    key = os.environ.get("AUDIORAQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "AUDIORAQ_API_KEY is not configured for the MCP server. "
            "Create a developer key at https://www.audioraq.com/developers "
            "and pass it through your MCP client's local environment."
        )
    return key


def _raise_for_audioraq_error(response: httpx.Response) -> None:
    status = response.status_code
    if status < 300:
        return
    if status == 401:
        message = "Audioraq rejected the API key. Check it or create a replacement key."
    elif status == 413:
        message = "Audioraq's configured character limit was exceeded. Shorten the text or render separate sections."
    elif status == 429:
        retry_after = response.headers.get("Retry-After")
        message = "Audioraq rate limit reached."
        if retry_after:
            message += f" Retry after {retry_after} seconds."
    else:
        message = f"Audioraq returned HTTP {status}; the response body was omitted."
    raise RuntimeError(message)


async def _get_json(url: str, *, headers: dict[str, str] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise RuntimeError("The Audioraq request timed out; no automatic retry was attempted.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach Audioraq over HTTPS.") from exc
    _raise_for_audioraq_error(response)
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Audioraq returned an invalid JSON response.") from exc


@mcp.tool()
async def list_voices() -> dict[str, Any]:
    """List Audioraq's public voices, defaults, and supported delivery profiles."""
    return await _get_json(f"{API_ROOT}/voices")


@mcp.tool()
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
    """Render narration with Audioraq and return metadata plus an audio block."""
    approved_text = text.strip()
    if not approved_text:
        raise ValueError("Narration text cannot be empty.")
    if quality_profile not in QUALITY_PROFILES:
        raise ValueError("Unsupported Audioraq quality profile.")

    payload = {
        "input": approved_text,
        "voice": voice,
        "format": output_format,
        "quality_profile": quality_profile,
    }
    headers = {
        "Accept": "audio/mpeg" if output_format == "mp3" else "audio/wav",
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            response = await client.post(f"{API_ROOT}/speech", json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "The Audioraq render timed out. It may have completed; check usage before retrying."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach Audioraq over HTTPS; no automatic retry was attempted.") from exc

    _raise_for_audioraq_error(response)
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
    if output_format == "wav" and not (len(audio) >= 12 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"):
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


def main() -> None:
    """Start the local MCP server over stdio for the connected agent."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
