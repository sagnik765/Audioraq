"""Text-to-speech rendering and audio post-production.

Turns script turns into audio bytes across the local, Apple `say`, ElevenLabs,
OpenAI and local-HTTP providers, then handles silence padding, stitching,
transcoding and peak headroom. Speaks only in bytes and files -- it holds no
database or request state.
"""
import base64
import io
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from array import array
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import HTTPException

from backend.config import parse_bool_env, parse_float_env, parse_int_env
from backend.voices import (
    AI_AUDIO_VOICE_ROLES,
    AI_PODCAST_VOICE_BY_ID,
    PROOF_STUDIO_APPLE_GAP_SECONDS,
    PROOF_STUDIO_APPLE_NARRATIVE_RATES,
    PROOF_STUDIO_APPLE_RATES,
    PROOF_STUDIO_APPLE_TARGET_PEAK_DBFS,
    PROOF_STUDIO_APPLE_VOICES,
    PROOF_STUDIO_LOCAL_FILTER,
)

logger = logging.getLogger(__name__)


def ai_audio_sentence_gap_seconds() -> float:
    return max(0.0, parse_float_env("AI_AUDIO_TTS_SENTENCE_GAP_SECONDS", 1.0))


def ai_audio_edge_padding_seconds() -> float:
    return max(0.0, parse_float_env("AI_AUDIO_TTS_EDGE_PADDING_SECONDS", 1.0))


def tts_sentence_parts(text: str) -> List[str]:
    normalized = normalize_local_tts_text(text)
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def cap_audio_script_turns(turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
    max_words = parse_int_env("AI_AUDIO_MAX_WORDS", 1200)
    max_chars = parse_int_env("AI_AUDIO_TTS_MAX_CHARS", 4500)
    min_final_turn_words = parse_int_env("AI_AUDIO_MIN_FINAL_TURN_WORDS", 18)
    reserved_end_turns = max(0, parse_int_env("AI_AUDIO_RESERVED_END_TURNS", 2))

    def trim_text_to_budget(text: str, remaining_words: int, remaining_chars: int) -> str:
        text = (text or "").strip()
        if not text or remaining_words <= 0 or remaining_chars <= 0:
            return ""

        truncated = False
        words = text.split()
        if len(words) > remaining_words:
            if remaining_words < min_final_turn_words:
                return ""
            text = " ".join(words[:remaining_words])
            truncated = True

        if len(text) > remaining_chars:
            if remaining_chars < 140:
                return ""
            text = text[:remaining_chars].rsplit(" ", 1)[0].strip()
            sentence_boundary = max(text.rfind("."), text.rfind("?"), text.rfind("!"))
            if sentence_boundary >= 120:
                text = text[: sentence_boundary + 1].strip()
            elif text and text[-1] not in ".!?":
                text = f"{text.rstrip(' ,;:')}."
            truncated = True

        if truncated and len(text.split()) < min_final_turn_words:
            return ""
        return text.strip()

    normalized_turns = []
    for turn in turns:
        text = (turn.get("text") or "").strip()
        if text:
            normalized_turns.append({**turn, "text": text})

    if not normalized_turns:
        return []

    reserved_turns = []
    main_turns = normalized_turns
    if reserved_end_turns and len(normalized_turns) > reserved_end_turns + 2:
        reserved_turns = normalized_turns[-reserved_end_turns:]
        main_turns = normalized_turns[:-reserved_end_turns]

    reserved_words = sum(len(turn["text"].split()) for turn in reserved_turns)
    reserved_chars = sum(len(turn["text"]) for turn in reserved_turns)
    main_word_budget = max(max_words - reserved_words, 0) if reserved_turns else max_words
    main_char_budget = max(max_chars - reserved_chars, 0) if reserved_turns else max_chars
    capped = []
    word_count = 0
    char_count = 0

    for turn in main_turns:
        remaining_words = main_word_budget - word_count
        remaining_chars = main_char_budget - char_count
        text = trim_text_to_budget(turn["text"], remaining_words, remaining_chars)
        if not text:
            break
        capped.append({**turn, "text": text})
        word_count += len(text.split())
        char_count += len(text)

    for turn in reserved_turns:
        remaining_words = max_words - word_count
        remaining_chars = max_chars - char_count
        text = trim_text_to_budget(turn["text"], remaining_words, remaining_chars)
        if not text:
            continue
        capped.append({**turn, "text": text})
        word_count += len(text.split())
        char_count += len(text)
    return capped


def split_audio_turns_for_tts(turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
    max_chars = parse_int_env("AI_AUDIO_TTS_MAX_CHARS_PER_TURN", 1400)
    max_sentences = parse_int_env("AI_AUDIO_TTS_MAX_SENTENCES_PER_TURN", 1, minimum=1, maximum=4)
    split_turns = []
    for turn in turns:
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        sentences = tts_sentence_parts(text)
        if not sentences:
            continue
        if len(text) <= max_chars and len(sentences) <= max_sentences:
            split_turns.append({**turn, "text": normalize_local_tts_text(text)})
            continue
        buffer = ""
        sentence_count = 0
        for sentence in sentences:
            candidate = f"{buffer} {sentence}".strip()
            if len(candidate) <= max_chars and sentence_count < max_sentences:
                buffer = candidate
                sentence_count += 1
                continue
            if buffer:
                split_turns.append({**turn, "text": buffer})
            if len(sentence) > max_chars:
                buffer = sentence[:max_chars].rsplit(" ", 1)[0].strip()
            else:
                buffer = sentence
            sentence_count = 1
        if buffer:
            split_turns.append({**turn, "text": buffer})
    return split_turns


def get_ai_audio_provider_order() -> List[str]:
    requested = os.environ.get("AI_AUDIO_TTS_PROVIDER", "auto").strip().lower() or "auto"
    if requested == "auto":
        order = []
        if os.environ.get("AI_AUDIO_LOCAL_TTS_URL"):
            order.append("local_http")
        if os.environ.get("ELEVENLABS_API_KEY"):
            order.append("elevenlabs")
        if os.environ.get("OPENAI_API_KEY"):
            order.append("openai")
        if (
            apple_say_tts_available()
            and parse_bool_env("AI_AUDIO_TTS_APPLE_SAY_ENABLED", True)
            and not parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False)
        ):
            order.append("apple_say")
        if not parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False):
            order.append("local")
        return order or (["local_http"] if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False) else ["local"])

    aliases = {
        "apple": "apple_say",
        "apple-say": "apple_say",
        "macos": "apple_say",
        "macos_say": "apple_say",
        "macos-say": "apple_say",
        "say": "apple_say",
        "espeak": "local",
        "espeak-ng": "local",
        "local-neural": "local_http",
        "http": "local_http",
    }
    order = [aliases.get(provider.strip(), provider.strip()) for provider in requested.split(",") if provider.strip()]
    if parse_bool_env("AI_AUDIO_TTS_LOCAL_FALLBACK", True) and "local" not in order and not parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False):
        order.append("local")
    if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False):
        order = [provider for provider in order if provider not in {"local", "apple_say"}]
    return order or (["local_http"] if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False) else ["local"])


def safe_tts_error(exc: Exception) -> str:
    return re.sub(r"\s+", " ", str(exc)).strip()[:220]


def content_type_for_tts_output(output_format: str) -> str:
    if output_format.startswith("mp3"):
        return "audio/mpeg"
    if output_format.startswith("wav"):
        return "audio/wav"
    if output_format.startswith("pcm"):
        return "audio/L16"
    return "audio/mpeg"


def extension_for_content_type(content_type: str) -> str:
    if content_type == "audio/wav":
        return "wav"
    if content_type == "audio/L16":
        return "pcm"
    return "mp3"


def wav_silence_bytes(duration_seconds: float, reference_segment: bytes) -> bytes:
    sample_rate = 44100
    channels = 1
    sample_width = 2
    try:
        with wave.open(io.BytesIO(reference_segment), "rb") as wav_file:
            sample_rate = wav_file.getframerate() or sample_rate
            channels = wav_file.getnchannels() or channels
            sample_width = wav_file.getsampwidth() or sample_width
    except Exception:
        pass
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        frame_count = max(1, int(sample_rate * max(0.0, duration_seconds)))
        wav_file.writeframes(b"\x00" * frame_count * channels * sample_width)
    return output.getvalue()


def compressed_silence_bytes(duration_seconds: float, extension: str) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return b""
    with tempfile.TemporaryDirectory(prefix="audioraq-tts-silence-") as temp_dir:
        temp_path = Path(temp_dir)
        output_path = temp_path / f"silence.{extension}"
        codec_args = ["-acodec", "libmp3lame", "-b:a", "128k"] if extension == "mp3" else ["-acodec", "pcm_s16le"]
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            f"{max(0.01, duration_seconds):.3f}",
            *codec_args,
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.warning(f"Could not generate {extension} silence: {result.stderr or result.stdout}")
            return b""
        return output_path.read_bytes()


def audio_silence_segment(duration_seconds: float, extension: str, reference_segment: bytes) -> bytes:
    if duration_seconds <= 0:
        return b""
    if extension == "wav":
        return wav_silence_bytes(duration_seconds, reference_segment)
    return compressed_silence_bytes(duration_seconds, extension)


def apply_audio_segment_padding(
    segments: List[bytes],
    extension: str,
    gap_seconds: float,
    edge_padding_seconds: float,
) -> List[bytes]:
    if not segments:
        return segments
    silence_gap = audio_silence_segment(gap_seconds, extension, segments[0]) if gap_seconds > 0 else b""
    silence_edge = audio_silence_segment(edge_padding_seconds, extension, segments[0]) if edge_padding_seconds > 0 else b""
    padded = []
    if silence_edge:
        padded.append(silence_edge)
    for index, segment in enumerate(segments):
        if index and silence_gap:
            padded.append(silence_gap)
        padded.append(segment)
    if silence_edge:
        padded.append(silence_edge)
    return padded


def stitch_audio_segments(
    segments: List[bytes],
    extension: str = "mp3",
    gap_seconds: Optional[float] = None,
    edge_padding_seconds: Optional[float] = None,
) -> bytes:
    gap = ai_audio_sentence_gap_seconds() if gap_seconds is None else max(0.0, gap_seconds)
    edge = ai_audio_edge_padding_seconds() if edge_padding_seconds is None else max(0.0, edge_padding_seconds)
    segments = apply_audio_segment_padding(segments, extension, gap, edge)
    if len(segments) == 1:
        return segments[0]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to stitch multi-voice TTS audio segments")

    with tempfile.TemporaryDirectory(prefix="audioraq-tts-stitch-") as temp_dir:
        temp_path = Path(temp_dir)
        concat_path = temp_path / "concat.txt"
        output_path = temp_path / f"episode.{extension}"
        concat_lines = []
        for index, segment in enumerate(segments):
            segment_path = temp_path / f"segment-{index:03d}.{extension}"
            segment_path.write_bytes(segment)
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
            "libmp3lame" if extension == "mp3" else "pcm_s16le",
            "-b:a",
            "128k",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            if extension == "mp3":
                logger.warning(f"ffmpeg MP3 stitching failed; using safe byte concatenation fallback: {result.stderr or result.stdout}")
                data = b"".join(segments)
                if len(data) < 1024:
                    raise RuntimeError("byte-concatenated audio was empty after ffmpeg stitching failed")
                return data
            raise RuntimeError(result.stderr or result.stdout or "ffmpeg stitching failed")
        data = output_path.read_bytes()
        if len(data) < 1024:
            raise RuntimeError("ffmpeg stitched an empty audio file")
        return data


def local_tts_voice_profile() -> str:
    raw_profile = os.environ.get("AI_AUDIO_TTS_LOCAL_VOICE_PROFILE", "proof_studio").strip().lower()
    normalized = raw_profile.replace("-", "_")
    if normalized in {"proof_studio", "proof", "audioraq_proof"}:
        return "proof_studio"
    if normalized in {"dialogue", "multi_voice", "multivoice"}:
        return "dialogue"
    return "proof_studio"


def local_tts_role_config(voice_role: str) -> Dict[str, str]:
    role = voice_role if voice_role in AI_AUDIO_VOICE_ROLES else "host"
    role_key = role.upper()
    if local_tts_voice_profile() == "proof_studio":
        voice_defaults = {"host": "en-us+m3", "guest": "en-us+m3", "narrator": "en-us+m3"}
        speed_defaults = {"host": "158", "guest": "158", "narrator": "158"}
        pitch_defaults = {"host": "48", "guest": "48", "narrator": "48"}
        amplitude_defaults = {"host": "145", "guest": "145", "narrator": "145"}
    else:
        voice_defaults = {"host": "en-us+m3", "guest": "en-us+f3", "narrator": "en-us+m1"}
        speed_defaults = {"host": "158", "guest": "150", "narrator": "142"}
        pitch_defaults = {"host": "48", "guest": "58", "narrator": "42"}
        amplitude_defaults = {"host": "145", "guest": "135", "narrator": "140"}
    return {
        "voice": os.environ.get(f"AI_AUDIO_TTS_LOCAL_VOICE_{role_key}", voice_defaults[role]).strip() or voice_defaults[role],
        "speed": os.environ.get(f"AI_AUDIO_TTS_LOCAL_SPEED_{role_key}", speed_defaults[role]).strip() or speed_defaults[role],
        "pitch": os.environ.get(f"AI_AUDIO_TTS_LOCAL_PITCH_{role_key}", pitch_defaults[role]).strip() or pitch_defaults[role],
        "amplitude": os.environ.get(f"AI_AUDIO_TTS_LOCAL_AMPLITUDE_{role_key}", amplitude_defaults[role]).strip() or amplitude_defaults[role],
    }


def shape_tts_pronunciation(text: str) -> str:
    """Make synthetic speech easier to articulate without changing meaning."""
    text = text.replace("&", " and ")
    text = re.sub(r"\bQ\s*&\s*A\b", "Q and A", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvs\.?\b", "versus", text, flags=re.IGNORECASE)
    text = re.sub(r"\be\.g\.", "for example", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\.e\.", "that is", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\w)/(?=\w)", " and ", text)
    text = re.sub(r"(?<=\d)%", " percent", text)

    def spell_acronym(match: re.Match) -> str:
        acronym = match.group(0)
        if "." in acronym:
            return acronym
        return ".".join(acronym) + "."

    return re.sub(r"\b[A-Z]{2,6}\b", spell_acronym, text)


def normalize_local_tts_text(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = text.replace(" - ", ", ")
    text = shape_tts_pronunciation(text)
    text = re.sub(r"\s+", " ", text).strip()
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return text


def postprocess_local_wav_audio(data: bytes) -> bytes:
    if not parse_bool_env("AI_AUDIO_TTS_LOCAL_POSTPROCESS", True):
        return data
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return data
    audio_filter = os.environ.get(
        "AI_AUDIO_TTS_LOCAL_FILTER",
        PROOF_STUDIO_LOCAL_FILTER,
    ).strip()
    with tempfile.TemporaryDirectory(prefix="audioraq-local-tts-post-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "input.wav"
        output_path = temp_path / "output.wav"
        input_path.write_bytes(data)
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
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            logger.warning(f"Local TTS post-processing failed; using raw local output: {result.stderr or result.stdout}")
            return data
        processed = output_path.read_bytes()
        return processed if len(processed) >= 1024 else data


def transcode_local_tts_output(data: bytes) -> Tuple[bytes, str, str]:
    output_format = os.environ.get("AI_AUDIO_TTS_LOCAL_OUTPUT_FORMAT", "wav").strip().lower() or "wav"
    if output_format in {"wav", "wave"}:
        return data, "audio/wav", "wav"
    if output_format not in {"mp3", "mpeg"}:
        logger.warning(f"Unsupported AI_AUDIO_TTS_LOCAL_OUTPUT_FORMAT={output_format}; using WAV output")
        return data, "audio/wav", "wav"

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg is not installed; using WAV local TTS output")
        return data, "audio/wav", "wav"

    bitrate = os.environ.get("AI_AUDIO_TTS_LOCAL_MP3_BITRATE", "160k").strip() or "160k"
    with tempfile.TemporaryDirectory(prefix="audioraq-local-tts-transcode-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "input.wav"
        output_path = temp_path / "output.mp3"
        input_path.write_bytes(data)
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            bitrate,
            "-ar",
            "44100",
            "-ac",
            "1",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            logger.warning(f"Local TTS MP3 transcode failed; using WAV output: {result.stderr or result.stdout}")
            return data, "audio/wav", "wav"
        transcoded = output_path.read_bytes()
        if len(transcoded) < 1024:
            logger.warning("Local TTS MP3 transcode produced an empty file; using WAV output")
            return data, "audio/wav", "wav"
        return transcoded, "audio/mpeg", "mp3"


def apple_say_tts_available() -> bool:
    return bool(shutil.which("say") and shutil.which("afconvert"))


def proof_studio_apple_role(voice_role: str, speaker: str = "") -> str:
    normalized_speaker = (speaker or "").strip().lower()
    if normalized_speaker in {"co-host", "cohost", "guest"}:
        return "guest"
    if normalized_speaker == "narrator":
        return "narrator"
    return voice_role if voice_role in AI_AUDIO_VOICE_ROLES else "host"


def synthesize_apple_say_turn(text: str, output_wav: Path, voices: List[str], rate_wpm: int) -> Tuple[str, float]:
    say = shutil.which("say")
    afconvert = shutil.which("afconvert")
    if not say or not afconvert:
        raise RuntimeError("Apple proof-studio voices require macOS say and afconvert")

    text_path = output_wav.with_suffix(".txt")
    text_path.write_text(normalize_local_tts_text(text), encoding="utf-8")
    last_error: Optional[Exception] = None
    for attempt, selected_voice in enumerate(dict.fromkeys(voices), start=1):
        tmp_aiff = output_wav.with_suffix(f".{attempt}.aiff")
        try:
            say_result = subprocess.run(
                [say, "-v", selected_voice, "-r", str(rate_wpm), "-o", str(tmp_aiff), "-f", str(text_path)],
                capture_output=True,
                text=True,
                timeout=240,
            )
            if say_result.returncode != 0:
                raise RuntimeError(say_result.stderr or say_result.stdout or "Apple say rendering failed")
            convert_result = subprocess.run([afconvert, "-f", "WAVE", "-d", "LEI16", str(tmp_aiff), str(output_wav)], capture_output=True, text=True, timeout=240)
            if convert_result.returncode != 0:
                raise RuntimeError(convert_result.stderr or convert_result.stdout or "Apple say WAV conversion failed")
            with wave.open(str(output_wav), "rb") as wav_file:
                duration_seconds = wav_file.getnframes() / max(1, wav_file.getframerate())
            min_duration = 0.16 if len((text or "").split()) <= 3 else 0.35
            if duration_seconds >= min_duration:
                return selected_voice, duration_seconds
            last_error = RuntimeError(f"Apple say voice {selected_voice} produced a short turn: {duration_seconds:.2f}s")
        except Exception as exc:
            last_error = exc
        finally:
            tmp_aiff.unlink(missing_ok=True)
    raise RuntimeError(f"Could not synthesize Apple proof-studio dialogue turn: {last_error}")


def concat_wav_files_with_silence(
    segment_paths: List[Path],
    output_wav: Path,
    gap_seconds: float = PROOF_STUDIO_APPLE_GAP_SECONDS,
    edge_padding_seconds: float = 1.0,
) -> None:
    if not segment_paths:
        raise RuntimeError("No Apple proof-studio audio segments were generated")
    with wave.open(str(segment_paths[0]), "rb") as first:
        params = first.getparams()
        framerate = first.getframerate()
        sample_width = first.getsampwidth()
        channels = first.getnchannels()
    silence_frames = int(framerate * max(0.0, gap_seconds))
    silence = b"\x00" * silence_frames * sample_width * channels
    edge_frames = int(framerate * max(0.0, edge_padding_seconds))
    edge_silence = b"\x00" * edge_frames * sample_width * channels
    with wave.open(str(output_wav), "wb") as out:
        out.setparams(params)
        if edge_silence:
            out.writeframes(edge_silence)
        for index, segment_path in enumerate(segment_paths):
            with wave.open(str(segment_path), "rb") as segment:
                if segment.getframerate() != framerate or segment.getsampwidth() != sample_width or segment.getnchannels() != channels:
                    raise RuntimeError(f"Apple proof-studio segment format mismatch: {segment_path}")
                out.writeframes(segment.readframes(segment.getnframes()))
                if index < len(segment_paths) - 1 and silence:
                    out.writeframes(silence)
        if edge_silence:
            out.writeframes(edge_silence)


def master_wav_peak_headroom(path: Path, target_peak_dbfs: float = PROOF_STUDIO_APPLE_TARGET_PEAK_DBFS) -> Dict[str, Any]:
    with wave.open(str(path), "rb") as wav_in:
        params = wav_in.getparams()
        frames = wav_in.readframes(wav_in.getnframes())
    if params.sampwidth != 2 or not frames:
        return {"target_peak_dbfs": target_peak_dbfs, "gain": 1.0, "peak_before": None, "peak_after": None}

    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()

    max_abs = max((abs(sample) for sample in samples), default=0)
    if max_abs <= 0:
        return {"target_peak_dbfs": target_peak_dbfs, "gain": 1.0, "peak_before": None, "peak_after": None}

    full_scale = float((1 << (params.sampwidth * 8 - 1)) - 1)
    target_abs = max(1, int(full_scale * (10 ** (target_peak_dbfs / 20.0))))
    gain = target_abs / max_abs
    mastered = array("h", (max(-32768, min(32767, int(round(sample * gain)))) for sample in samples))
    peak_after = max((abs(sample) for sample in mastered), default=0)
    if sys.byteorder != "little":
        mastered.byteswap()

    with wave.open(str(path), "wb") as wav_out:
        wav_out.setparams(params)
        wav_out.writeframes(mastered.tobytes())

    return {
        "target_peak_dbfs": target_peak_dbfs,
        "gain": round(gain, 4),
        "peak_before": round(20 * math.log10(max(max_abs / full_scale, 0.0000001)), 2),
        "peak_after": round(20 * math.log10(max(max(1, peak_after) / full_scale, 0.0000001)), 2),
    }


def render_apple_say_proof_audio(script_text: str, turns: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    if not apple_say_tts_available():
        raise RuntimeError("Apple proof-studio TTS is only available on macOS with say and afconvert")

    rendered_turns = split_audio_turns_for_tts(turns or [{"speaker": "Host", "voice_role": "host", "text": script_text}])
    if not rendered_turns:
        raise RuntimeError("no voice turns were available for Apple proof-studio TTS")
    rendered_roles = [
        proof_studio_apple_role(str(turn.get("voice_role") or "host"), str(turn.get("speaker") or ""))
        for turn in rendered_turns
    ]
    narrative_mode = "narrator" in rendered_roles
    active_rates = PROOF_STUDIO_APPLE_NARRATIVE_RATES if narrative_mode else PROOF_STUDIO_APPLE_RATES
    turn_gap_seconds = ai_audio_sentence_gap_seconds()
    edge_padding_seconds = ai_audio_edge_padding_seconds()

    with tempfile.TemporaryDirectory(prefix="audioraq-apple-proof-") as temp_dir:
        temp_path = Path(temp_dir)
        segments = []
        voices = {}
        timings = []
        cursor = edge_padding_seconds
        for index, turn in enumerate(rendered_turns, start=1):
            role = rendered_roles[index - 1]
            voice_profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
            voice_candidates = (
                list(voice_profile.get("apple_voices") or []) + PROOF_STUDIO_APPLE_VOICES.get(role, PROOF_STUDIO_APPLE_VOICES["host"])
                if voice_profile
                else PROOF_STUDIO_APPLE_VOICES.get(role, PROOF_STUDIO_APPLE_VOICES["host"])
            )
            rate_wpm = int(voice_profile.get("rate_wpm") or active_rates.get(role, active_rates["host"])) if voice_profile else active_rates.get(role, active_rates["host"])
            segment_path = temp_path / f"segment-{index:03d}-{role}.wav"
            selected_voice, duration_seconds = synthesize_apple_say_turn(
                turn.get("text") or "",
                segment_path,
                voice_candidates,
                rate_wpm,
            )
            speaker_key = turn.get("speaker") or role
            voices[speaker_key] = {
                "voice_id": voice_profile.get("id") if voice_profile else "",
                "display_name": voice_profile.get("name") if voice_profile else selected_voice,
                "gender": voice_profile.get("gender") if voice_profile else "",
                "style": voice_profile.get("style") if voice_profile else "",
                "engine_voice": selected_voice,
            }
            timings.append(
                {
                    "speaker": turn.get("speaker") or role.title(),
                    "voice_role": role,
                    "voice_id": voice_profile.get("id") if voice_profile else "",
                    "voice_name": voice_profile.get("name") if voice_profile else selected_voice,
                    "voice": selected_voice,
                    "start": round(cursor, 3),
                    "end": round(cursor + duration_seconds, 3),
                    "duration": round(duration_seconds, 3),
                }
            )
            cursor += duration_seconds + (turn_gap_seconds if index < len(rendered_turns) else edge_padding_seconds)
            segments.append(segment_path)

        output_path = temp_path / "episode.wav"
        concat_wav_files_with_silence(segments, output_path, gap_seconds=turn_gap_seconds, edge_padding_seconds=edge_padding_seconds)
        mastering = master_wav_peak_headroom(output_path)
        data = output_path.read_bytes()
        if len(data) < 1024:
            raise RuntimeError("Apple proof-studio TTS produced an empty audio file")
        return {
            "data": data,
            "content_type": "audio/wav",
            "provider": "apple-say:proof-studio",
            "provider_kind": "local-proof",
            "model": "macOS say",
            "voices": voices,
            "turn_count": len(rendered_turns),
            "chunk_count": len(segments),
            "timings": timings,
            "rates_wpm": active_rates,
            "turn_gap_seconds": turn_gap_seconds,
            "edge_padding_seconds": edge_padding_seconds,
            "mastering": mastering,
            "enhancement_profile": f"audioraq-qa-proof-dialogue+20-voice-library+calm-podcast-rate+{turn_gap_seconds}s-sentence-gaps+{edge_padding_seconds}s-edge-padding",
            "benchmark_note": "Replicates the April 11 QA proof-studio recipe using generic macOS system voices; does not clone a real person's voice.",
            "voice_profile": "apple_proof_studio",
            "extension": "wav",
            "filename": "ai-generated-episode.wav",
        }


def render_local_ai_audio(script_text: str, turns: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    renderer = shutil.which("espeak-ng") or shutil.which("espeak")
    if not renderer:
        raise RuntimeError("local AI audio renderer is not installed")

    use_multivoice = parse_bool_env("AI_AUDIO_TTS_LOCAL_MULTIVOICE", True)
    if use_multivoice and turns:
        rendered_turns = split_audio_turns_for_tts(turns)
    else:
        host_config = local_tts_role_config("host")
        rendered_turns = [{"speaker": "Host", "voice_role": "host", "text": script_text, **host_config}]

    with tempfile.TemporaryDirectory(prefix="audioraq-ai-audio-") as temp_dir:
        temp_path = Path(temp_dir)
        segments = []
        voices = {}
        for index, turn in enumerate(rendered_turns):
            role = turn.get("voice_role") if turn.get("voice_role") in AI_AUDIO_VOICE_ROLES else "host"
            voice_profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
            host_config = local_tts_role_config("host")
            if voice_profile and voice_profile.get("espeak"):
                profile_config = voice_profile["espeak"]
                config = {
                    "voice": str(profile_config.get("voice") or host_config["voice"]),
                    "speed": str(profile_config.get("speed") or host_config["speed"]),
                    "pitch": str(profile_config.get("pitch") or host_config["pitch"]),
                    "amplitude": str(profile_config.get("amplitude") or host_config["amplitude"]),
                }
            else:
                config = (
                    local_tts_role_config(role)
                    if use_multivoice and turns
                    else {
                        "voice": turn.get("voice") or host_config["voice"],
                        "speed": turn.get("speed") or host_config["speed"],
                        "pitch": turn.get("pitch") or host_config["pitch"],
                        "amplitude": turn.get("amplitude") or host_config["amplitude"],
                    }
                )
            speaker_key = turn.get("speaker") or role
            voices[speaker_key] = {
                "voice_id": voice_profile.get("id") if voice_profile else "",
                "display_name": voice_profile.get("name") if voice_profile else config["voice"],
                "gender": voice_profile.get("gender") if voice_profile else "",
                "style": voice_profile.get("style") if voice_profile else "",
                "engine_voice": config["voice"],
            }
            script_path = temp_path / f"script-{index:03d}.txt"
            output_path = temp_path / f"segment-{index:03d}.wav"
            script_path.write_text(normalize_local_tts_text(turn.get("text") or ""), encoding="utf-8")
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            if result.returncode != 0:
                logger.error(f"AI audio renderer failed: {result.stderr or result.stdout}")
                raise RuntimeError("local AI audio rendering failed")
            segment = output_path.read_bytes()
            if len(segment) >= 1024:
                segments.append(segment)
        if not segments:
            raise RuntimeError("local AI audio renderer produced no usable segments")
        data = stitch_audio_segments(segments, extension="wav")
        data = postprocess_local_wav_audio(data)
        data, content_type, extension = transcode_local_tts_output(data)
        if len(data) < 1024:
            raise RuntimeError("local AI audio renderer produced an empty file")
        return {
            "data": data,
            "content_type": content_type,
            "provider": f"{Path(renderer).name}:{local_tts_voice_profile()}-enhanced-local",
            "provider_kind": "local",
            "model": Path(renderer).name,
            "voices": voices or {"host": os.environ.get("AI_AUDIO_TTS_VOICE", "en-us").strip() or "en-us"},
            "turn_count": len(rendered_turns),
            "chunk_count": len(segments),
            "enhancement_profile": f"role-voice-variants+pacing+ffmpeg-normalization+{extension}-delivery",
            "benchmark_note": "Local espeak-ng fallback optimized for clarity; not equivalent to neural ElevenLabs production TTS.",
            "voice_profile": local_tts_voice_profile(),
            "extension": extension,
            "filename": f"ai-generated-episode.{extension}",
        }


def render_elevenlabs_ai_audio(turns: List[Dict[str, str]]) -> Dict[str, Any]:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")

    host_voice = os.environ.get("ELEVENLABS_VOICE_ID_HOST", "JBFqnCBsd6RMkjVDRZzb").strip() or "JBFqnCBsd6RMkjVDRZzb"
    voice_ids = {
        "host": host_voice,
        "guest": os.environ.get("ELEVENLABS_VOICE_ID_GUEST", "").strip() or host_voice,
        "narrator": os.environ.get("ELEVENLABS_VOICE_ID_NARRATOR", "").strip() or host_voice,
    }

    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_v3").strip() or "eleven_v3"
    output_format = os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128").strip() or "mp3_44100_128"
    content_type = content_type_for_tts_output(output_format)
    extension = extension_for_content_type(content_type)
    rendered_turns = split_audio_turns_for_tts(turns)
    if not rendered_turns:
        raise RuntimeError("no voice turns were available for ElevenLabs TTS")

    def build_inputs(active_voice_ids: Dict[str, str]) -> List[Dict[str, str]]:
        tts_inputs = []
        for turn in rendered_turns:
            voice_role = turn.get("voice_role") if turn.get("voice_role") in AI_AUDIO_VOICE_ROLES else "host"
            profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
            env_key = f"ELEVENLABS_VOICE_ID_{re.sub(r'[^A-Z0-9]+', '_', (profile or {}).get('id', '').upper()).strip('_')}" if profile else ""
            selected_voice_id = os.environ.get(env_key, "").strip() if env_key else ""
            tts_inputs.append({"text": turn["text"], "voice_id": selected_voice_id or active_voice_ids[voice_role]})
        return tts_inputs

    body_template = {"model_id": model_id}
    language_code = os.environ.get("ELEVENLABS_LANGUAGE_CODE", "").strip()
    if language_code:
        body_template["language_code"] = language_code

    request_timeout = parse_int_env("AI_AUDIO_TTS_TIMEOUT_SECONDS", 240)
    max_request_chars = max(1000, parse_int_env("ELEVENLABS_MAX_REQUEST_CHARS", 4500))

    def post_dialogue(tts_inputs: List[Dict[str, str]]):
        return requests.post(
            "https://api.elevenlabs.io/v1/text-to-dialogue",
            params={"output_format": output_format},
            headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": content_type},
            json={**body_template, "inputs": tts_inputs},
            timeout=request_timeout,
        )

    inputs = build_inputs(voice_ids)
    input_chars = sum(len(item.get("text") or "") for item in inputs)
    if input_chars > max_request_chars:
        raise RuntimeError(f"ElevenLabs TTS input has {input_chars} characters, above the configured {max_request_chars}-character cap")

    response = post_dialogue(inputs)
    if response.status_code == 404 and "voice_not_found" in response.text and len(set(voice_ids.values())) > 1:
        logger.warning("ElevenLabs secondary voice was not available; retrying dialogue render with host voice only")
        voice_ids = {role: voice_ids["host"] for role in voice_ids}
        inputs = build_inputs(voice_ids)
        response = post_dialogue(inputs)
    if response.status_code >= 400:
        raise RuntimeError(f"ElevenLabs TTS failed with {response.status_code}: {response.text[:300]}")

    data = response.content
    if len(data) < 1024:
        raise RuntimeError("ElevenLabs TTS produced an empty file")
    return {
        "data": data,
        "content_type": content_type,
        "provider": f"elevenlabs:{model_id}",
        "provider_kind": "elevenlabs",
        "model": model_id,
        "voices": {role: voice for role, voice in voice_ids.items() if voice},
        "turn_count": len(rendered_turns),
        "chunk_count": 1,
        "extension": extension,
        "filename": f"ai-generated-episode.{extension}",
    }


def render_openai_ai_audio(turns: List[Dict[str, str]]) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts"
    response_format = os.environ.get("OPENAI_TTS_RESPONSE_FORMAT", "mp3").strip() or "mp3"
    content_type = "audio/mpeg" if response_format == "mp3" else f"audio/{response_format}"
    gpt4o_voice_defaults = {"host": "marin", "guest": "cedar", "narrator": "coral"}
    legacy_voice_defaults = {"host": "alloy", "guest": "nova", "narrator": "onyx"}
    defaults = gpt4o_voice_defaults if model.startswith("gpt-4o") else legacy_voice_defaults
    voices = {
        "host": os.environ.get("OPENAI_TTS_VOICE_HOST", defaults["host"]).strip() or defaults["host"],
        "guest": os.environ.get("OPENAI_TTS_VOICE_GUEST", defaults["guest"]).strip() or defaults["guest"],
        "narrator": os.environ.get("OPENAI_TTS_VOICE_NARRATOR", defaults["narrator"]).strip() or defaults["narrator"],
    }
    base_instructions = os.environ.get(
        "OPENAI_TTS_INSTRUCTIONS",
        "Natural podcast delivery: warm, clear, conversational, and expressive without imitating any real person.",
    ).strip()

    segments = []
    actual_voices: Dict[str, Any] = {}
    rendered_turns = split_audio_turns_for_tts(turns)
    if not rendered_turns:
        raise RuntimeError("no voice turns were available for OpenAI TTS")
    for turn in rendered_turns:
        voice_role = turn.get("voice_role") if turn.get("voice_role") in AI_AUDIO_VOICE_ROLES else "host"
        voice_profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
        selected_voice = (voice_profile.get("openai_voice") if voice_profile else "") or voices[voice_role]
        speaker_key = turn.get("speaker") or voice_role
        actual_voices[speaker_key] = {
            "voice_id": voice_profile.get("id") if voice_profile else "",
            "display_name": voice_profile.get("name") if voice_profile else selected_voice,
            "gender": voice_profile.get("gender") if voice_profile else "",
            "style": voice_profile.get("style") if voice_profile else "",
            "engine_voice": selected_voice,
        }
        payload = {
            "model": model,
            "voice": selected_voice,
            "input": turn["text"],
            "response_format": response_format,
        }
        if model.startswith("gpt-4o") and base_instructions:
            payload["instructions"] = f"{base_instructions} Speaker role: {turn.get('speaker') or voice_role}."
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=parse_int_env("AI_AUDIO_TTS_TIMEOUT_SECONDS", 240),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI TTS failed with {response.status_code}: {response.text[:300]}")
        if len(response.content) < 1024:
            raise RuntimeError("OpenAI TTS produced an empty segment")
        segments.append(response.content)

    extension = "mp3" if response_format == "mp3" else response_format
    data = stitch_audio_segments(segments, extension=extension)
    return {
        "data": data,
        "content_type": content_type,
        "provider": f"openai:{model}",
        "provider_kind": "openai",
        "model": model,
        "voices": actual_voices or voices,
        "turn_count": len(rendered_turns),
        "extension": extension,
        "filename": f"ai-generated-episode.{extension}",
    }


def render_local_http_ai_audio(
    script_text: str,
    turns: List[Dict[str, str]],
    output_format: str = "",
    quality_profile: str = "",
) -> Dict[str, Any]:
    base_url = os.environ.get("AI_AUDIO_LOCAL_TTS_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("AI_AUDIO_LOCAL_TTS_URL is not configured")

    payload = {
        "script_text": script_text,
        "turns": split_audio_turns_for_tts(turns),
        "target_loudness_lufs": parse_float_env("AI_AUDIO_TARGET_LUFS", -16.0),
        "format": output_format or os.environ.get("AI_AUDIO_LOCAL_TTS_FORMAT", "wav").strip().lower() or "wav",
        "quality_profile": quality_profile or os.environ.get("AI_AUDIO_LOCAL_TTS_PROFILE", "podcast-dialogue").strip() or "podcast-dialogue",
        "pacing": {
            "sentence_gap_seconds": ai_audio_sentence_gap_seconds(),
            "edge_padding_seconds": ai_audio_edge_padding_seconds(),
        },
    }
    response = requests.post(
        f"{base_url}/v1/render",
        json=payload,
        timeout=parse_int_env("AI_AUDIO_LOCAL_TTS_TIMEOUT_SECONDS", 900),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Local TTS worker failed with {response.status_code}: {response.text[:300]}")

    if (response.headers.get("Content-Type") or "").startswith("audio/"):
        data = response.content
        content_type = response.headers.get("Content-Type", "audio/wav").split(";")[0]
        extension = extension_for_content_type(content_type)
        provider = response.headers.get("X-Audioraq-TTS-Provider", "local-http:audio")
        provider_kind = response.headers.get("X-Audioraq-TTS-Provider-Kind", "local-neural")
        model = response.headers.get("X-Audioraq-TTS-Model", "")
    else:
        body = response.json()
        encoded_audio = body.get("audio_base64") or body.get("data_base64") or ""
        if not encoded_audio:
            raise RuntimeError("Local TTS worker did not return audio_base64")
        data = base64.b64decode(encoded_audio)
        content_type = body.get("content_type") or "audio/wav"
        extension = body.get("extension") or extension_for_content_type(content_type)
        provider = body.get("provider") or "local-http:audio"
        provider_kind = body.get("provider_kind") or "local-neural"
        model = body.get("model") or ""

    if len(data) < 1024:
        raise RuntimeError("Local TTS worker produced an empty audio file")
    if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False) and provider_kind != "local-neural":
        raise RuntimeError(f"Local TTS worker returned {provider_kind} audio, but AI_AUDIO_REQUIRE_NEURAL_WORKER=true")

    return {
        "data": data,
        "content_type": content_type,
        "provider": provider,
        "provider_kind": provider_kind,
        "model": model,
        "voices": {"source": "local-http-worker"},
        "turn_count": len(payload["turns"]),
        "extension": extension,
        "filename": f"ai-generated-episode.{extension}",
        "quality_profile": payload["quality_profile"],
    }


def render_ai_audio_bytes(script_text: str, turns: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    voice_turns = cap_audio_script_turns(turns or [{"speaker": "Host", "voice_role": "host", "text": script_text}])
    provider_errors = []
    for provider in get_ai_audio_provider_order():
        try:
            if provider == "local_http":
                return render_local_http_ai_audio(script_text, voice_turns)
            if provider == "apple_say":
                return render_apple_say_proof_audio(script_text, voice_turns)
            if provider == "elevenlabs":
                return render_elevenlabs_ai_audio(voice_turns)
            if provider == "openai":
                return render_openai_ai_audio(voice_turns)
            if provider == "local":
                return render_local_ai_audio(script_text, voice_turns)
            raise RuntimeError(f"unknown provider '{provider}'")
        except Exception as exc:
            error = safe_tts_error(exc)
            provider_errors.append(f"{provider}: {error}")
            logger.warning(f"AI audio provider {provider} failed; trying fallback if available: {error}")

    raise HTTPException(
        status_code=502,
        detail=f"AI audio rendering failed across configured providers. Last errors: {'; '.join(provider_errors[-3:])}",
    )


def transcode_ai_audio_result(rendered: Dict[str, Any], output_format: str) -> Dict[str, Any]:
    requested = "mp3" if output_format == "mp3" else "wav"
    current = str(rendered.get("extension") or extension_for_content_type(str(rendered.get("content_type") or ""))).lower()
    if current == requested:
        return rendered

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(f"ffmpeg is required to deliver {requested} output")
    data = rendered.get("data") or b""
    if len(data) < 1024:
        raise RuntimeError("audio renderer returned an incomplete file")

    with tempfile.TemporaryDirectory(prefix="audioraq-text-to-audio-") as temp_dir:
        temp_path = Path(temp_dir)
        input_extension = current if current in {"mp3", "wav"} else "audio"
        input_path = temp_path / f"input.{input_extension}"
        output_path = temp_path / f"output.{requested}"
        input_path.write_bytes(data)
        codec_args = ["-codec:a", "libmp3lame", "-b:a", "160k"] if requested == "mp3" else ["-codec:a", "pcm_s16le"]
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(input_path),
                "-ar",
                "44100",
                "-ac",
                "1",
                *codec_args,
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=parse_int_env("AI_AUDIO_TTS_TIMEOUT_SECONDS", 240),
        )
        if result.returncode != 0 or not output_path.exists():
            raise RuntimeError(result.stderr or result.stdout or "audio format conversion failed")
        output = output_path.read_bytes()

    return {
        **rendered,
        "data": output,
        "content_type": "audio/mpeg" if requested == "mp3" else "audio/wav",
        "extension": requested,
        "filename": f"audioraq-speech.{requested}",
    }


def render_text_to_audio_bytes(
    script_text: str,
    turns: Optional[List[Dict[str, str]]],
    output_format: str,
    quality_profile: str,
) -> Dict[str, Any]:
    voice_turns = cap_audio_script_turns(turns or [{"speaker": "Narrator", "voice_role": "narrator", "text": script_text}])
    provider_errors = []
    for provider in get_ai_audio_provider_order():
        try:
            if provider == "local_http":
                rendered = render_local_http_ai_audio(
                    script_text,
                    voice_turns,
                    output_format=output_format,
                    quality_profile=quality_profile,
                )
            elif provider == "apple_say":
                rendered = render_apple_say_proof_audio(script_text, voice_turns)
            elif provider == "elevenlabs":
                rendered = render_elevenlabs_ai_audio(voice_turns)
            elif provider == "openai":
                rendered = render_openai_ai_audio(voice_turns)
            elif provider == "local":
                rendered = render_local_ai_audio(script_text, voice_turns)
            else:
                raise RuntimeError(f"unknown provider '{provider}'")
            return transcode_ai_audio_result(rendered, output_format)
        except Exception as exc:
            error = safe_tts_error(exc)
            provider_errors.append(f"{provider}: {error}")
            logger.warning(f"Text-to-audio provider {provider} failed; trying fallback if available: {error}")

    raise HTTPException(
        status_code=502,
        detail=f"Text-to-audio rendering failed across configured providers. Last errors: {'; '.join(provider_errors[-3:])}",
    )
