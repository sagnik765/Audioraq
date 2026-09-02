"""Authentication, authorization, and request-safety primitives.

Password hashing, JWT issue and verification, auth cookies, the current-user
dependency, rate limiting, and the SSRF guards applied to outbound fetches.
"""
import hashlib
import ipaddress
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

import bcrypt
import jwt
import requests
from bson import ObjectId
from fastapi import HTTPException, Request, Response

from backend.config import (
    DEFAULT_MEMORY_DIR,
    ensure_aware_utc,
    is_production_env,
    parse_bool,
)
from backend.db import db

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"


def get_jwt_secret():
    return os.environ["JWT_SECRET"]


def should_return_auth_tokens() -> bool:
    configured = os.environ.get("AUTH_RETURN_BEARER_TOKENS")
    if configured is not None:
        return parse_bool(configured, default=False)
    return not is_production_env()


def attach_auth_token_payload(payload: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    if should_return_auth_tokens():
        payload["access_token"] = access_token
    return payload


def validate_runtime_security() -> None:
    production = is_production_env()
    jwt_secret = (os.environ.get("JWT_SECRET") or "").strip()
    weak_jwt_values = {"", "secret", "changeme", "replace-with-a-long-random-secret", "dev-secret"}
    if jwt_secret.lower() in weak_jwt_values or len(jwt_secret) < 32:
        message = "JWT_SECRET must be a unique high-entropy value of at least 32 characters."
        if production:
            raise RuntimeError(message)
        logger.warning(message)

    admin_password = (os.environ.get("ADMIN_PASSWORD") or "").strip()
    weak_admin_values = {"", "admin", "admin123", "password", "test123", "replace-with-a-strong-admin-password"}
    if admin_password.lower() in weak_admin_values or len(admin_password) < 12:
        message = "ADMIN_PASSWORD must be explicitly configured with a strong password before production launch."
        if production:
            raise RuntimeError(message)
        logger.warning(message)


def get_admin_password_for_seed() -> str:
    admin_password = (os.environ.get("ADMIN_PASSWORD") or "").strip()
    if admin_password:
        return admin_password
    if is_production_env():
        raise RuntimeError("ADMIN_PASSWORD is required in production")
    return "admin123"


def write_test_credentials_if_enabled(admin_email: str, admin_password: str) -> None:
    if not parse_bool(os.environ.get("WRITE_TEST_CREDENTIALS"), default=not is_production_env()):
        return
    memory_dir = Path(os.environ.get("MEMORY_DIR", str(DEFAULT_MEMORY_DIR)))
    memory_dir.mkdir(parents=True, exist_ok=True)
    include_admin_password = parse_bool(os.environ.get("INCLUDE_ADMIN_TEST_PASSWORD"), default=False)
    admin_password_display = admin_password if include_admin_password and not is_production_env() else "<configured in environment>"
    with open(memory_dir / "test_credentials.md", "w", encoding="utf-8") as f:
        f.write("# Test Credentials\n\n")
        f.write(f"## Admin\n- Email: {admin_email}\n- Password: {admin_password_display}\n- Role: admin\n\n")
        f.write("## Test User\n- Email: testuser@test.com\n- Password: test123\n- Role: user\n\n")
        f.write("## Test Podcaster\n- Email: podcaster@test.com\n- Password: test123\n- Role: podcaster\n\n")
        f.write("## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n- POST /api/auth/refresh\n")


def get_client_fingerprint(request: Request) -> str:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    client_ip = forwarded_for or (request.client.host if request.client else "unknown")
    digest = hashlib.sha256(f"{client_ip}:{os.environ.get('JWT_SECRET', '')[:16]}".encode("utf-8")).hexdigest()
    return digest[:32]


def validate_runtime_url(url: str, *, allow_local: bool = False) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must be an absolute http(s) URL")
    hostname = parsed.hostname.strip().lower()
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="URL host could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if allow_local:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise HTTPException(status_code=400, detail="URL points to a private or unsafe network")
    return candidate


def safe_external_get(url: str, *, timeout: int = 30, max_bytes: int = 5_242_880, max_redirects: int = 3) -> requests.Response:
    current_url = validate_runtime_url(url)
    for _ in range(max_redirects + 1):
        response = requests.get(current_url, timeout=timeout, stream=True, allow_redirects=False)
        if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            response.close()
            if not location:
                raise HTTPException(status_code=400, detail="External URL redirect was missing a destination")
            current_url = validate_runtime_url(urljoin(current_url, location))
            continue
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            response.close()
            raise HTTPException(status_code=400, detail="External URL response is too large")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            data.extend(chunk)
            if len(data) > max_bytes:
                response.close()
                raise HTTPException(status_code=400, detail="External URL response is too large")
        response._content = bytes(data)
        response.close()
        return response
    raise HTTPException(status_code=400, detail="External URL redirected too many times")


def validate_external_redirect_url(url: str) -> str:
    return validate_runtime_url(url)


def get_cookie_settings(request: Optional[Request] = None):
    forwarded_proto = request.headers.get("x-forwarded-proto") if request else None
    request_scheme = request.url.scheme if request else None
    secure_default = (forwarded_proto or request_scheme or "").lower() == "https"
    secure = parse_bool(os.environ.get("COOKIE_SECURE"), default=secure_default)
    same_site = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"

    settings = {
        "httponly": True,
        "secure": secure,
        "samesite": same_site,
        "path": "/",
    }

    cookie_domain = os.environ.get("COOKIE_DOMAIN")
    if cookie_domain:
        settings["domain"] = cookie_domain

    return settings


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, request: Optional[Request] = None):
    cookie_settings = get_cookie_settings(request)
    response.set_cookie(key="access_token", value=access_token, max_age=3600, **cookie_settings)
    response.set_cookie(key="refresh_token", value=refresh_token, max_age=604800, **cookie_settings)


def clear_auth_cookies(response: Response):
    cookie_settings = {"path": "/"}
    cookie_domain = os.environ.get("COOKIE_DOMAIN")
    if cookie_domain:
        cookie_settings["domain"] = cookie_domain
    response.delete_cookie("access_token", **cookie_settings)
    response.delete_cookie("refresh_token", **cookie_settings)


def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password, hashed_password):
    if not hashed_password:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id, email):
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id):
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def try_get_current_user(request: Optional[Request]):
    if request is None:
        return None
    try:
        return await get_current_user(request)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise


async def enforce_rate_limit(request: Request, action: str, max_attempts: int, window_seconds: int) -> None:
    now = datetime.now(timezone.utc)
    key = hashlib.sha256(f"{action}:{get_client_fingerprint(request)}".encode("utf-8")).hexdigest()
    window_start = now - timedelta(seconds=window_seconds)
    existing = await db.rate_limits.find_one({"_id": key})
    if existing:
        created_at = ensure_aware_utc(existing.get("created_at"))
        if created_at and created_at > window_start:
            attempts = int(existing.get("attempts", 0)) + 1
            await db.rate_limits.update_one(
                {"_id": key},
                {"$set": {"last_attempt_at": now, "expires_at": now + timedelta(seconds=window_seconds)}, "$inc": {"attempts": 1}},
            )
            if attempts > max_attempts:
                raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
            return

    await db.rate_limits.update_one(
        {"_id": key},
        {
            "$set": {
                "action": action,
                "created_at": now,
                "last_attempt_at": now,
                "expires_at": now + timedelta(seconds=window_seconds),
                "attempts": 1,
            }
        },
        upsert=True,
    )
