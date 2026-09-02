"""Media object storage.

Covers the local persistent volume, the read-only legacy remote fallback, and
range-aware streaming for the audio player. This layer knows nothing about
MongoDB or the request models; it deals only in bytes, paths, and HTTP responses.
"""
import logging
import mimetypes
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests
from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from backend.config import EMERGENT_KEY, LEGACY_STORAGE_URL, PROJECT_DIR

logger = logging.getLogger(__name__)

STREAM_CHUNK_SIZE = 1024 * 1024


def init_storage():
    if get_storage_backend() == "local":
        return "local"
    return init_legacy_storage()


def init_legacy_storage():
    global storage_key
    if storage_key:
        return storage_key
    if not LEGACY_STORAGE_URL:
        raise RuntimeError("LEGACY_STORAGE_URL is required when STORAGE_BACKEND=legacy.")
    if not EMERGENT_KEY:
        raise RuntimeError("EMERGENT_LLM_KEY is required for legacy object storage. Set STORAGE_BACKEND=local to use local disk storage.")
    resp = requests.post(f"{LEGACY_STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def get_storage_backend() -> str:
    backend = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
    if backend == "emergent":
        return "legacy"
    return backend if backend in {"legacy", "local"} else "local"


def local_storage_root() -> Path:
    configured = Path(os.environ.get("LOCAL_STORAGE_DIR", str(PROJECT_DIR / "data" / "media"))).expanduser()
    return (configured if configured.is_absolute() else PROJECT_DIR / configured).resolve()


def local_storage_path(path: str) -> Path:
    normalized = (path or "").strip().lstrip("/")
    if not normalized:
        raise ValueError("Storage path is required")
    destination = (local_storage_root() / normalized).resolve()
    if local_storage_root() not in destination.parents and destination != local_storage_root():
        raise ValueError("Invalid storage path")
    return destination


def local_storage_content_type_path(path: str) -> Path:
    return local_storage_path(path).with_name(f"{local_storage_path(path).name}.content-type")


def object_cache_key(path: str) -> str:
    normalized = (path or "").strip().lstrip("/")
    if not normalized:
        raise ValueError("Storage path is required")
    return f"__object_cache/{normalized}"


def cache_object_locally(path: str, data: bytes, content_type: str) -> None:
    cache_path = object_cache_key(path)
    destination = local_storage_path(cache_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temp_destination.write_bytes(data)
    temp_destination.replace(destination)
    local_storage_content_type_path(cache_path).write_text(content_type or "application/octet-stream", encoding="utf-8")


def cached_object_exists(path: str) -> bool:
    try:
        source = local_storage_path(object_cache_key(path))
        return source.exists() and source.stat().st_size > 0
    except Exception:
        return False


def cached_object_content_type(path: str, fallback: str) -> str:
    try:
        content_type_path = local_storage_content_type_path(object_cache_key(path))
        if content_type_path.exists():
            return content_type_path.read_text(encoding="utf-8").strip() or fallback
    except Exception:
        pass
    return fallback


def delete_cached_object(path: str) -> None:
    try:
        cache_path = object_cache_key(path)
        source = local_storage_path(cache_path)
        content_type_path = local_storage_content_type_path(cache_path)
        if source.exists():
            source.unlink()
        if content_type_path.exists():
            content_type_path.unlink()
    except Exception as exc:
        logger.warning(f"Could not remove cached media object for {path}: {exc}")


def write_local_object(path: str, data: bytes, content_type: str) -> None:
    destination = local_storage_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temp_destination.write_bytes(data)
    temp_destination.replace(destination)
    local_storage_content_type_path(path).write_text(content_type or "application/octet-stream", encoding="utf-8")


def put_object(path, data, content_type):
    if get_storage_backend() == "local":
        write_local_object(path, data, content_type)
        return {"path": path, "storage_backend": "local"}

    key = init_storage()
    for attempt in range(4):
        try:
            resp = requests.put(
                f"{LEGACY_STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key, "Content-Type": content_type},
                data=data,
                timeout=300,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code and status_code < 500:
                raise
            if attempt == 3:
                raise
            delay = 2 ** attempt
            logger.warning(f"Storage upload retry {attempt + 1}/4 for {path} after {status_code or exc.__class__.__name__}; waiting {delay}s")
            time.sleep(delay)
    try:
        cache_object_locally(path, data, content_type)
    except Exception as exc:
        logger.warning(f"Could not cache uploaded media object {path}: {exc}")
    return resp.json()


def get_legacy_object(path: str) -> Tuple[bytes, str]:
    key = init_legacy_storage()
    resp = requests.get(
        f"{LEGACY_STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def get_object(path):
    if get_storage_backend() == "local":
        source = local_storage_path(path)
        if source.exists():
            content_type_path = local_storage_content_type_path(path)
            guessed_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            content_type = content_type_path.read_text(encoding="utf-8").strip() if content_type_path.exists() else guessed_type
            return source.read_bytes(), content_type
        try:
            data, content_type = get_legacy_object(path)
            try:
                write_local_object(path, data, content_type)
            except Exception as cache_exc:
                logger.warning(f"Could not migrate legacy media object {path} into local storage: {cache_exc}")
            return data, content_type
        except Exception as exc:
            logger.warning(f"Legacy media fallback miss for {path}: {exc}")
            raise FileNotFoundError(path) from exc

    return get_legacy_object(path)


def safe_inline_filename(filename: str) -> str:
    safe_name = re.sub(r'[\r\n"\\]+', "", (filename or "podcast").strip()) or "podcast"
    return safe_name[:180]


def media_stream_headers(
    filename: str,
    *,
    content_length: Optional[int] = None,
    content_range: Optional[str] = None,
) -> Dict[str, str]:
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{safe_inline_filename(filename)}"',
        "Cache-Control": "private, max-age=3600, no-transform",
    }
    if content_length is not None:
        headers["Content-Length"] = str(max(0, content_length))
    if content_range:
        headers["Content-Range"] = content_range
    return headers


def parse_range_header(range_header: Optional[str], size: int) -> Optional[Tuple[int, int]]:
    if not range_header:
        return None

    header = range_header.strip().lower()
    if not header.startswith("bytes=") or "," in header:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    start_text, separator, end_text = header[6:].partition("-")
    if separator != "-":
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    try:
        if start_text == "":
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError("suffix range must be positive")
            start = max(size - suffix_length, 0)
            end = size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
            end = min(end, size - 1)
    except ValueError:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    if size <= 0 or start < 0 or start >= size or end < start:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    return start, end


def iter_file_range(source: Path, start: int, end: int) -> Iterator[bytes]:
    with source.open("rb") as file_handle:
        file_handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = file_handle.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def should_count_stream_play(range_header: Optional[str]) -> bool:
    if not range_header:
        return True
    match = re.match(r"^\s*bytes=(\d*)-", range_header, flags=re.IGNORECASE)
    return bool(match and match.group(1) in {"", "0"})


def stream_local_object(path: str, content_type: str, request: Request, filename: str):
    source = local_storage_path(path)
    if not source.exists():
        raise FileNotFoundError(path)

    size = source.stat().st_size
    range_tuple = parse_range_header(request.headers.get("range"), size)
    if not range_tuple:
        return FileResponse(
            source,
            media_type=content_type,
            headers=media_stream_headers(filename, content_length=size),
        )

    start, end = range_tuple
    content_length = end - start + 1
    return StreamingResponse(
        iter_file_range(source, start, end),
        status_code=206,
        media_type=content_type,
        headers=media_stream_headers(
            filename,
            content_length=content_length,
            content_range=f"bytes {start}-{end}/{size}",
        ),
    )


def stream_bytes_object(data: bytes, content_type: str, request: Request, filename: str):
    size = len(data)
    range_tuple = parse_range_header(request.headers.get("range"), size)
    if not range_tuple:
        return Response(content=data, media_type=content_type, headers=media_stream_headers(filename, content_length=size))

    start, end = range_tuple
    partial_data = data[start : end + 1]
    return Response(
        content=partial_data,
        status_code=206,
        media_type=content_type,
        headers=media_stream_headers(
            filename,
            content_length=len(partial_data),
            content_range=f"bytes {start}-{end}/{size}",
        ),
    )


def stream_cached_or_remote_object(path: str, content_type: str, request: Request, filename: str):
    if cached_object_exists(path):
        return stream_local_object(object_cache_key(path), cached_object_content_type(path, content_type), request, filename)

    data, storage_content_type = get_object(path)
    resolved_content_type = content_type or storage_content_type
    try:
        cache_object_locally(path, data, resolved_content_type)
        return stream_local_object(object_cache_key(path), resolved_content_type, request, filename)
    except Exception as exc:
        logger.warning(f"Could not cache streamed media object {path}; serving from memory: {exc}")
        return stream_bytes_object(data, resolved_content_type, request, filename)


def stream_stored_object(path: str, content_type: str, request: Request, filename: str):
    if get_storage_backend() == "local":
        try:
            return stream_local_object(path, content_type, request, filename)
        except FileNotFoundError:
            return stream_cached_or_remote_object(path, content_type, request, filename)
    return stream_cached_or_remote_object(path, content_type, request, filename)


def delete_object(path, missing_ok: bool = True) -> str:
    normalized_path = (path or "").strip()
    if not normalized_path:
        return "skipped"

    if get_storage_backend() == "local":
        source = local_storage_path(normalized_path)
        content_type_path = local_storage_content_type_path(normalized_path)
        existed = source.exists()
        if source.exists():
            source.unlink()
        if content_type_path.exists():
            content_type_path.unlink()
        if existed:
            return "deleted"
        if missing_ok:
            return "missing"
        raise FileNotFoundError(normalized_path)

    delete_cached_object(normalized_path)
    key = init_storage()
    resp = requests.delete(
        f"{LEGACY_STORAGE_URL}/objects/{normalized_path}",
        headers={"X-Storage-Key": key},
        timeout=120,
    )
    if missing_ok and resp.status_code == 404:
        return "missing"
    if resp.status_code == 405:
        logger.warning(f"Storage API does not support hard delete for {normalized_path}; scrubbing object contents instead")
        scrub_resp = requests.put(
            f"{LEGACY_STORAGE_URL}/objects/{normalized_path}",
            headers={"X-Storage-Key": key, "Content-Type": "application/octet-stream"},
            data=b"",
            timeout=120,
        )
        scrub_resp.raise_for_status()
        return "scrubbed"
    resp.raise_for_status()
    return "deleted"


def cleanup_storage_paths(paths: List[str], strict: bool = False) -> Dict[str, Any]:
    deleted = []
    scrubbed = []
    missing = []
    failures = []

    seen = set()
    normalized_paths = []
    for raw_path in paths:
        path = (raw_path or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        normalized_paths.append(path)

    for path in normalized_paths:
        try:
            cleanup_result = delete_object(path, missing_ok=True)
            if cleanup_result == "deleted":
                deleted.append(path)
            elif cleanup_result == "scrubbed":
                scrubbed.append(path)
            elif cleanup_result == "missing":
                missing.append(path)
        except Exception as exc:
            logger.error(f"Storage cleanup failed for {path}: {exc}")
            failures.append({"path": path, "error": str(exc)})

    if strict and failures:
        raise HTTPException(status_code=502, detail="Could not remove media from storage. Please retry.")

    return {"deleted": deleted, "scrubbed": scrubbed, "missing": missing, "failures": failures}
