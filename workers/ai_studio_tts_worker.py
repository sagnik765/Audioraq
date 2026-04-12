#!/usr/bin/env python3
"""
Audioraq AI Studio TTS Worker.

Runs a local text-to-speech HTTP service for Create with AI. The web app calls
POST /v1/render and receives a finished audio file. Neural engines are loaded
dynamically so the worker can run with Kokoro/Chatterbox when installed, while
still offering an explicit espeak-ng fallback for development.
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("audioraq.ai_studio_tts_worker")

VOICE_ROLES = {"host", "guest", "narrator"}
DEFAULT_ENGINE_ORDER = ["kokoro", "chatterbox", "espeak"]
_kokoro_pipelines: Dict[str, Any] = {}
_chatterbox_models: Dict[str, Any] = {}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def normalize_role(role: str) -> str:
    role = (role or "host").strip().lower()
    return role if role in VOICE_ROLES else "host"


def normalize_text(text: str, keep_stage_tags: bool = True) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not keep_stage_tags:
        text = re.sub(r"\[[a-zA-Z _-]+\]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return text


def split_text(text: str, max_chars: int) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    parts = []
    buffer = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        candidate = f"{buffer} {sentence}".strip()
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        if buffer:
            parts.append(buffer)
        buffer = sentence[:max_chars].rsplit(" ", 1)[0].strip()
    if buffer:
        parts.append(buffer)
    return parts


def flatten_samples(audio: Any) -> List[float]:
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu()
        if hasattr(audio, "squeeze"):
            audio = audio.squeeze()
        if hasattr(audio, "numpy"):
            audio = audio.numpy()
    if hasattr(audio, "tolist"):
        audio = audio.tolist()
    if isinstance(audio, (int, float)):
        return [float(audio)]
    if isinstance(audio, list) and audio and isinstance(audio[0], list):
        if len(audio) == 1:
            audio = audio[0]
        else:
            audio = audio[0]
    return [float(sample) for sample in (audio or [])]


def samples_to_wav_bytes(audio: Any, sample_rate: int) -> bytes:
    samples = flatten_samples(audio)
    if not samples:
        raise RuntimeError("TTS engine returned no audio samples")

    pcm = bytearray()
    for sample in samples:
        clipped = max(-1.0, min(1.0, sample))
        pcm.extend(int(clipped * 32767).to_bytes(2, byteorder="little", signed=True))

    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm))
    return output.getvalue()


def looks_like_audio_payload(value: Any) -> bool:
    if value is None or isinstance(value, (str, bytes, bytearray)):
        return False
    if hasattr(value, "detach") or hasattr(value, "numpy"):
        return True
    if hasattr(value, "tolist"):
        return True
    if isinstance(value, (list, tuple)):
        if not value:
            return False
        first = value[0]
        return not isinstance(first, (str, bytes, bytearray, dict))
    return False


def extract_generated_audio(item: Any) -> Any:
    for attr in ("audio", "samples", "wav", "waveform"):
        value = getattr(item, attr, None)
        if looks_like_audio_payload(value):
            return value
    if isinstance(item, dict):
        for key in ("audio", "samples", "wav", "waveform"):
            value = item.get(key)
            if looks_like_audio_payload(value):
                return value
    if isinstance(item, (list, tuple)):
        for value in reversed(item):
            if looks_like_audio_payload(value):
                return value
    if looks_like_audio_payload(item):
        return item
    raise RuntimeError(f"TTS engine returned unsupported audio payload type: {type(item).__name__}")


def write_temp_wav(data: bytes, directory: Path, index: int) -> Path:
    path = directory / f"segment-{index:03d}.wav"
    path.write_bytes(data)
    return path


def stitch_wav_segments(segments: List[bytes]) -> bytes:
    if not segments:
        raise RuntimeError("No audio segments were generated")
    if len(segments) == 1:
        return segments[0]

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to stitch multi-turn audio")

    with tempfile.TemporaryDirectory(prefix="audioraq-tts-worker-stitch-") as temp_dir:
        temp_path = Path(temp_dir)
        concat_path = temp_path / "concat.txt"
        output_path = temp_path / "stitched.wav"
        concat_lines = []
        for index, segment in enumerate(segments):
            segment_path = write_temp_wav(segment, temp_path, index)
            concat_lines.append(f"file '{segment_path}'")
        concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=env_int("AUDIORAQ_TTS_FFMPEG_TIMEOUT_SECONDS", 300))
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "ffmpeg stitching failed")
        return output_path.read_bytes()


def postprocess_audio(data: bytes, target_loudness_lufs: float, output_format: str) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return data

    normalized_format = "mp3" if output_format == "mp3" else "wav"
    with tempfile.TemporaryDirectory(prefix="audioraq-tts-worker-post-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "input.wav"
        output_path = temp_path / f"output.{normalized_format}"
        input_path.write_bytes(data)
        codec_args = ["-acodec", "libmp3lame", "-b:a", "160k"] if normalized_format == "mp3" else ["-acodec", "pcm_s16le"]
        default_filter = f"highpass=f=70,lowpass=f=14000,loudnorm=I={target_loudness_lufs}:TP=-1.5:LRA=11"
        audio_filter = os.environ.get("AUDIORAQ_TTS_MASTERING_FILTER", default_filter).strip() or default_filter
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-af",
            audio_filter,
            "-ar",
            "44100",
            "-ac",
            "1",
            *codec_args,
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=env_int("AUDIORAQ_TTS_FFMPEG_TIMEOUT_SECONDS", 300))
        if result.returncode != 0:
            logger.warning("Audio post-processing failed; returning raw audio: %s", result.stderr or result.stdout)
            return data
        processed = output_path.read_bytes()
        return processed if len(processed) >= 1024 else data


class VoiceTurn(BaseModel):
    speaker: str = "Host"
    voice_role: Literal["host", "guest", "narrator"] = "host"
    text: str


class RenderRequest(BaseModel):
    script_text: str = ""
    turns: List[VoiceTurn] = Field(default_factory=list)
    target_loudness_lufs: float = -16.0
    format: Literal["wav", "mp3"] = "wav"
    quality_profile: str = "podcast-dialogue"
    engine: Optional[str] = ""


@dataclass
class RenderedAudio:
    data: bytes
    provider: str
    provider_kind: str
    model: str
    engine: str
    extension: str = "wav"
    content_type: str = "audio/wav"


def request_turns(req: RenderRequest) -> List[VoiceTurn]:
    if req.turns:
        return req.turns
    script = req.script_text.strip()
    if not script:
        raise HTTPException(status_code=400, detail="script_text or turns are required")
    return [VoiceTurn(speaker="Host", voice_role="host", text=script)]


def expand_turns(req: RenderRequest) -> List[VoiceTurn]:
    max_chars = env_int("AUDIORAQ_TTS_MAX_CHARS_PER_TURN", 900)
    expanded = []
    for turn in request_turns(req):
        for part in split_text(turn.text, max_chars):
            expanded.append(VoiceTurn(speaker=turn.speaker, voice_role=turn.voice_role, text=part))
    return expanded


def engine_order(req: RenderRequest) -> List[str]:
    requested = (req.engine or os.environ.get("AUDIORAQ_TTS_ENGINE", "auto")).strip().lower()
    aliases = {"local": "espeak", "espeak-ng": "espeak", "neural": "kokoro"}
    if requested == "auto":
        engines = DEFAULT_ENGINE_ORDER
    else:
        engines = [aliases.get(item.strip(), item.strip()) for item in requested.split(",") if item.strip()]
    if not env_bool("AUDIORAQ_TTS_ALLOW_ESPEAK_FALLBACK", True):
        engines = [engine for engine in engines if engine != "espeak"]
    return engines or ["kokoro"]


def kokoro_voice(role: str) -> str:
    defaults = {"host": "am_michael", "guest": "af_bella", "narrator": "af_sarah"}
    return os.environ.get(f"AUDIORAQ_TTS_KOKORO_VOICE_{role.upper()}", defaults[role]).strip() or defaults[role]


def get_kokoro_pipeline(lang_code: str):
    if lang_code not in _kokoro_pipelines:
        from kokoro import KPipeline

        _kokoro_pipelines[lang_code] = KPipeline(lang_code=lang_code)
    return _kokoro_pipelines[lang_code]


def render_kokoro(req: RenderRequest) -> RenderedAudio:
    lang_code = os.environ.get("AUDIORAQ_TTS_KOKORO_LANG", "a").strip() or "a"
    speed = env_float("AUDIORAQ_TTS_KOKORO_SPEED", 0.94)
    pipeline = get_kokoro_pipeline(lang_code)
    segments = []

    for turn in expand_turns(req):
        role = normalize_role(turn.voice_role)
        text = normalize_text(turn.text)
        voice = kokoro_voice(role)
        try:
            generator = pipeline(text, voice=voice, speed=speed)
        except TypeError:
            generator = pipeline(text, voice=voice)
        for item in generator:
            segments.append(samples_to_wav_bytes(extract_generated_audio(item), 24000))

    stitched = stitch_wav_segments(segments)
    output_format = req.format or "wav"
    mastered = postprocess_audio(stitched, req.target_loudness_lufs, output_format)
    return RenderedAudio(
        data=mastered,
        provider="ai-studio:kokoro",
        provider_kind="local-neural",
        model=f"kokoro:{lang_code}",
        engine="kokoro",
        extension=output_format,
        content_type="audio/mpeg" if output_format == "mp3" else "audio/wav",
    )


def chatterbox_device() -> str:
    configured = os.environ.get("AUDIORAQ_TTS_CHATTERBOX_DEVICE", "").strip()
    if configured:
        return configured
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def get_chatterbox_model():
    variant = os.environ.get("AUDIORAQ_TTS_CHATTERBOX_VARIANT", "standard").strip().lower()
    device = chatterbox_device()
    cache_key = f"{variant}:{device}"
    if cache_key in _chatterbox_models:
        return _chatterbox_models[cache_key]

    if variant == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        model = ChatterboxTurboTTS.from_pretrained(device=device)
    else:
        from chatterbox.tts import ChatterboxTTS

        model = ChatterboxTTS.from_pretrained(device=device)
    _chatterbox_models[cache_key] = model
    return model


def chatterbox_prompt_for_role(role: str) -> str:
    prompt = os.environ.get(f"AUDIORAQ_TTS_CHATTERBOX_PROMPT_{role.upper()}", "").strip()
    return prompt if prompt and Path(prompt).exists() else ""


def render_chatterbox(req: RenderRequest) -> RenderedAudio:
    model = get_chatterbox_model()
    segments = []
    exaggeration = env_float("AUDIORAQ_TTS_CHATTERBOX_EXAGGERATION", 0.55)
    cfg_weight = env_float("AUDIORAQ_TTS_CHATTERBOX_CFG_WEIGHT", 0.4)
    temperature = env_float("AUDIORAQ_TTS_CHATTERBOX_TEMPERATURE", 0.8)

    for turn in expand_turns(req):
        role = normalize_role(turn.voice_role)
        text = normalize_text(turn.text, keep_stage_tags=True)
        prompt_path = chatterbox_prompt_for_role(role)
        kwargs: Dict[str, Any] = {
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
            "temperature": temperature,
        }
        if prompt_path:
            kwargs["audio_prompt_path"] = prompt_path
        try:
            audio = model.generate(text, **kwargs)
        except TypeError:
            minimal_kwargs = {"audio_prompt_path": prompt_path} if prompt_path else {}
            audio = model.generate(text, **minimal_kwargs)
        segments.append(samples_to_wav_bytes(audio, int(getattr(model, "sr", 24000))))

    stitched = stitch_wav_segments(segments)
    output_format = req.format or "wav"
    mastered = postprocess_audio(stitched, req.target_loudness_lufs, output_format)
    return RenderedAudio(
        data=mastered,
        provider="ai-studio:chatterbox",
        provider_kind="local-neural",
        model=f"chatterbox:{os.environ.get('AUDIORAQ_TTS_CHATTERBOX_VARIANT', 'standard')}",
        engine="chatterbox",
        extension=output_format,
        content_type="audio/mpeg" if output_format == "mp3" else "audio/wav",
    )


def espeak_config(role: str) -> Dict[str, str]:
    defaults = {
        "host": {"voice": "en-us+m3", "speed": "158", "pitch": "48", "amplitude": "145"},
        "guest": {"voice": "en-us+f3", "speed": "150", "pitch": "58", "amplitude": "135"},
        "narrator": {"voice": "en-us+m1", "speed": "142", "pitch": "42", "amplitude": "140"},
    }
    role_defaults = defaults[normalize_role(role)]
    role_key = normalize_role(role).upper()
    return {
        key: os.environ.get(f"AUDIORAQ_TTS_ESPEAK_{key.upper()}_{role_key}", value).strip() or value
        for key, value in role_defaults.items()
    }


def render_espeak(req: RenderRequest) -> RenderedAudio:
    renderer = shutil.which("espeak-ng") or shutil.which("espeak")
    if not renderer:
        raise RuntimeError("espeak-ng is not installed")

    segments = []
    with tempfile.TemporaryDirectory(prefix="audioraq-tts-worker-espeak-") as temp_dir:
        temp_path = Path(temp_dir)
        for index, turn in enumerate(expand_turns(req)):
            role = normalize_role(turn.voice_role)
            config = espeak_config(role)
            script_path = temp_path / f"turn-{index:03d}.txt"
            output_path = temp_path / f"turn-{index:03d}.wav"
            script_path.write_text(normalize_text(turn.text, keep_stage_tags=False), encoding="utf-8")
            cmd = [
                renderer,
                "-v",
                config["voice"],
                "-s",
                config["speed"],
                "-p",
                config["pitch"],
                "-a",
                config["amplitude"],
                "-f",
                str(script_path),
                "-w",
                str(output_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=env_int("AUDIORAQ_TTS_ESPEAK_TIMEOUT_SECONDS", 240))
            if result.returncode != 0:
                raise RuntimeError(result.stderr or result.stdout or "espeak rendering failed")
            segments.append(output_path.read_bytes())

    stitched = stitch_wav_segments(segments)
    output_format = req.format or "wav"
    mastered = postprocess_audio(stitched, req.target_loudness_lufs, output_format)
    return RenderedAudio(
        data=mastered,
        provider="ai-studio:espeak-ng",
        provider_kind="local",
        model=Path(renderer).name,
        engine="espeak",
        extension=output_format,
        content_type="audio/mpeg" if output_format == "mp3" else "audio/wav",
    )


def render_with_engine(engine: str, req: RenderRequest) -> RenderedAudio:
    if engine == "kokoro":
        return render_kokoro(req)
    if engine == "chatterbox":
        return render_chatterbox(req)
    if engine == "espeak":
        return render_espeak(req)
    raise RuntimeError(f"unknown TTS engine '{engine}'")


def available_tools() -> Dict[str, bool]:
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "espeak": bool(shutil.which("espeak-ng") or shutil.which("espeak")),
    }


app = FastAPI(title="Audioraq AI Studio TTS Worker", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "request_id": str(uuid.uuid4()), "tools": available_tools()}


@app.get("/v1/status")
async def status():
    return {
        "status": "ok",
        "engine_order": engine_order(RenderRequest(script_text="status")),
        "allow_espeak_fallback": env_bool("AUDIORAQ_TTS_ALLOW_ESPEAK_FALLBACK", True),
        "tools": available_tools(),
        "kokoro_loaded": bool(_kokoro_pipelines),
        "chatterbox_loaded": bool(_chatterbox_models),
        "notes": [
            "Kokoro requires the kokoro Python package and espeak-ng for G2P fallback.",
            "Chatterbox requires chatterbox-tts plus torch/torchaudio-compatible hardware.",
            "Only use Chatterbox reference prompts you own or have explicit rights to use.",
        ],
    }


@app.post("/v1/render")
async def render(req: RenderRequest):
    errors = []
    min_bytes = env_int("AUDIORAQ_TTS_MIN_AUDIO_BYTES", 2048)
    for engine in engine_order(req):
        try:
            rendered = await run_in_thread(engine, req)
            if len(rendered.data) < min_bytes:
                raise RuntimeError(f"{engine} produced {len(rendered.data)} bytes, below minimum {min_bytes}")
            headers = {
                "X-Audioraq-TTS-Provider": rendered.provider,
                "X-Audioraq-TTS-Provider-Kind": rendered.provider_kind,
                "X-Audioraq-TTS-Model": rendered.model,
                "X-Audioraq-TTS-Engine": rendered.engine,
            }
            return Response(content=rendered.data, media_type=rendered.content_type, headers=headers)
        except Exception as exc:
            message = re.sub(r"\s+", " ", str(exc)).strip()[:300]
            logger.warning("TTS engine %s failed: %s", engine, message)
            errors.append({"engine": engine, "error": message})

    raise HTTPException(status_code=502, detail={"message": "All local TTS engines failed", "errors": errors[-5:]})


async def run_in_thread(engine: str, req: RenderRequest) -> RenderedAudio:
    import asyncio

    return await asyncio.to_thread(render_with_engine, engine, req)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "ai_studio_tts_worker:app",
        host=os.environ.get("AUDIORAQ_TTS_HOST", "127.0.0.1"),
        port=env_int("AUDIORAQ_TTS_PORT", 8015),
        reload=env_bool("AUDIORAQ_TTS_RELOAD", False),
    )
