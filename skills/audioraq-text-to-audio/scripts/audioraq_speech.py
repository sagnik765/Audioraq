#!/usr/bin/env python3
"""Create paced MP3/WAV narration through Audioraq's public API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_ROOT = "https://www.audioraq.com/api/v1/audio"
TIMEOUT_SECONDS = 180


class NoRedirectHandler(HTTPRedirectHandler):
    """Do not forward an API key or narration to a redirect target."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


HTTP = build_opener(NoRedirectHandler())


def request_json(url: str) -> object:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Audioraq-Agensi-Skill/1.0"},
    )
    with HTTP.open(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def read_input(args: argparse.Namespace) -> str:
    if args.text is not None:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        raise ValueError("Provide --text or narration through standard input.")
    if not text.strip():
        raise ValueError("Narration text is empty.")
    return text


def has_mpeg_frame(data: bytes) -> bool:
    start = 0
    if data.startswith(b"ID3") and len(data) >= 10:
        tag_size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        footer_size = 10 if data[5] & 0x10 else 0
        start = 10 + tag_size + footer_size
    stop = min(len(data) - 1, start + 65536)
    return any(
        data[index] == 0xFF and (data[index + 1] & 0xE0) == 0xE0
        for index in range(start, stop)
    )


def validate_audio(audio: bytes, content_type: str, audio_format: str) -> None:
    if not audio:
        raise ValueError("Audioraq returned an empty audio response.")
    media_type = content_type.split(";", 1)[0].strip()
    if media_type.startswith(("application/json", "text/")):
        raise ValueError(f"Audioraq returned a non-audio response ({media_type}).")

    if audio_format == "wav":
        allowed_types = {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}
        has_wav_header = len(audio) >= 12 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
        if (media_type.startswith("audio/") and media_type not in allowed_types) or not has_wav_header:
            raise ValueError("Audioraq's response is not a valid WAV file.")
        return

    allowed_types = {"audio/mpeg", "audio/mp3", "audio/x-mp3"}
    if media_type.startswith("audio/") and media_type not in allowed_types:
        raise ValueError(f"Audioraq returned {media_type}, not MP3 audio.")
    if not has_mpeg_frame(audio):
        raise ValueError("Audioraq's response does not have a recognizable MP3 frame.")


def render(args: argparse.Namespace) -> int:
    key = os.environ.get("AUDIORAQ_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "AUDIORAQ_API_KEY is not set. Configure it in the agent's local environment; "
            "do not paste the key into chat."
        )

    text = read_input(args)
    payload = {
        "input": text,
        "voice": args.voice,
        "format": args.format,
        "quality_profile": args.quality_profile,
    }
    request = Request(
        f"{API_ROOT}/speech",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "audio/mpeg" if args.format == "mp3" else "audio/wav",
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Audioraq-Agensi-Skill/1.0",
        },
        method="POST",
    )

    with HTTP.open(request, timeout=TIMEOUT_SECONDS) as response:
        audio = response.read()
        content_type = response.headers.get("Content-Type", "").lower()
        validate_audio(audio, content_type, args.format)

        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if args.overwrite else "xb"
        with output.open(mode) as audio_file:
            audio_file.write(audio)

        print(f"Saved: {output}")
        print(f"Format: {args.format}")
        print(f"Bytes: {len(audio)}")
        print(f"Voice: {response.headers.get('X-Audioraq-Voice', args.voice)}")
        print(f"Profile: {args.quality_profile}")
        print(f"Characters: {response.headers.get('X-Audioraq-Characters', len(text))}")
        for name in (
            "X-Audioraq-Provider",
            "X-Audioraq-Model",
            "X-Request-Id",
            "X-RateLimit-Remaining",
        ):
            value = response.headers.get(name)
            if value:
                print(f"{name}: {value}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render speech with Audioraq.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("voices", help="Print Audioraq's current public voice catalog.")

    speech = commands.add_parser("speech", help="Render narration to MP3 or WAV.")
    source = speech.add_mutually_exclusive_group()
    source.add_argument("--text", help="Narration text. For longer text, prefer standard input.")
    speech.add_argument("--voice", default="aman-warm-analyst")
    speech.add_argument("--format", choices=("mp3", "wav"), default="mp3")
    speech.add_argument(
        "--quality-profile",
        choices=("podcast-education-calm", "podcast-dialogue", "podcast-storytelling"),
        default="podcast-education-calm",
    )
    speech.add_argument("--output", required=True, help="Destination audio file path.")
    speech.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file only when the user explicitly approved it.",
    )

    args = parser.parse_args()
    try:
        if args.command == "voices":
            print(json.dumps(request_json(f"{API_ROOT}/voices"), ensure_ascii=False, indent=2))
            return 0
        return render(args)
    except HTTPError as error:
        retry_after = error.headers.get("Retry-After")
        message = f"Audioraq returned HTTP {error.code}."
        if retry_after:
            message += f" Retry-After: {retry_after}."
        print(message, file=sys.stderr)
        return 2
    except (URLError, TimeoutError) as error:
        print(f"Could not reach Audioraq: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
