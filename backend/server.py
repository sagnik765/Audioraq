from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, Request, HTTPException, UploadFile, File, Form, Response, Query, Header
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import bcrypt
import jwt
import secrets
import requests
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT config
JWT_ALGORITHM = "HS256"

def get_jwt_secret():
    return os.environ["JWT_SECRET"]

# Object Storage
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "podcasthub"
storage_key = None

def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key

def put_object(path, data, content_type):
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=300
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path):
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=120
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# Password helpers
def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# JWT helpers
def create_access_token(user_id, email):
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=60), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id):
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

# Auth helper
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

# AI keyword extraction
async def extract_keywords(text):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"keywords-{uuid.uuid4()}",
            system_message="You are a keyword extraction expert. Extract 5-10 relevant keywords/topics from the given text. Return ONLY a JSON array of lowercase strings, no other text. Example: [\"technology\", \"science\", \"ai\"]"
        ).with_model("openai", "gpt-5.2")
        msg = UserMessage(text=f"Extract keywords from this text: {text}")
        response = await chat.send_message(msg)
        import json
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        keywords = json.loads(cleaned.strip())
        if isinstance(keywords, list):
            return [k.lower().strip() for k in keywords if isinstance(k, str)]
        return []
    except Exception as e:
        logger.error(f"Keyword extraction error: {e}")
        words = text.lower().split()
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "shall", "can", "need", "dare", "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during", "before", "after", "above", "below", "between", "out", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "because", "but", "and", "or", "if", "while", "about", "up", "it", "its", "i", "my", "we", "our", "you", "your", "he", "she", "they", "them", "this", "that", "these", "those", "what", "which", "who", "whom"}
        keywords = list(set([w.strip(".,!?;:\"'()[]{}") for w in words if len(w) > 3 and w not in stop_words]))
        return keywords[:10]

# AI recommendations
async def get_ai_recommendations(user_interests, viewed_keywords, all_podcasts):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json
        podcast_summaries = []
        for p in all_podcasts[:50]:
            podcast_summaries.append({
                "id": p["id"],
                "title": p["title"],
                "keywords": p.get("keywords", []),
                "category": p.get("category", "")
            })
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"recommend-{uuid.uuid4()}",
            system_message="You are a podcast recommendation engine. Given user interests and available podcasts, rank and return the most relevant podcast IDs. Return ONLY a JSON array of podcast ID strings, ordered by relevance. Max 20 IDs."
        ).with_model("openai", "gpt-5.2")
        prompt = f"""User interests: {json.dumps(user_interests)}
Previously viewed podcast keywords: {json.dumps(viewed_keywords)}
Available podcasts: {json.dumps(podcast_summaries)}

Return the most relevant podcast IDs as a JSON array."""
        msg = UserMessage(text=prompt)
        response = await chat.send_message(msg)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        ids = json.loads(cleaned.strip())
        if isinstance(ids, list):
            return [str(i) for i in ids]
        return []
    except Exception as e:
        logger.error(f"AI recommendation error: {e}")
        return []

# Pydantic models
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str  # "user" or "podcaster"
    phone: Optional[str] = ""
    interests: Optional[List[str]] = []
    podcast_description: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class UpdateInterestsRequest(BaseModel):
    interests: List[str]

class UpdatePodcastDescriptionRequest(BaseModel):
    podcast_description: str

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Startup
@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.podcasts.create_index("keywords")
    await db.podcasts.create_index("podcaster_id")
    await db.view_history.create_index([("user_id", 1), ("podcast_id", 1)])

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@podlyzer.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email, "password_hash": hashed,
            "name": "Admin", "role": "admin",
            "interests": [], "phone": "",
            "podcast_description": "",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info("Admin user seeded")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})

    # Init storage
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

    # Write test credentials
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write(f"# Test Credentials\n\n")
        f.write(f"## Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n")
        f.write(f"## Test User\n- Email: testuser@test.com\n- Password: test123\n- Role: user\n\n")
        f.write(f"## Test Podcaster\n- Email: podcaster@test.com\n- Password: test123\n- Role: podcaster\n\n")
        f.write(f"## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n- POST /api/auth/refresh\n")

# ===================== AUTH ENDPOINTS =====================

@api_router.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    email = req.email.lower().strip()
    if req.role not in ["user", "podcaster"]:
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'podcaster'")
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    keywords = []
    if req.role == "podcaster" and req.podcast_description:
        keywords = await extract_keywords(req.podcast_description)

    user_doc = {
        "email": email,
        "password_hash": hash_password(req.password),
        "name": req.name,
        "role": req.role,
        "phone": req.phone or "",
        "interests": [i.lower().strip() for i in (req.interests or [])],
        "podcast_description": req.podcast_description or "",
        "podcast_keywords": keywords,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

    return {
        "id": user_id, "email": email, "name": req.name,
        "role": req.role, "phone": req.phone or "",
        "interests": user_doc["interests"],
        "podcast_description": user_doc["podcast_description"],
        "podcast_keywords": keywords,
        "access_token": access_token
    }

@api_router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response):
    email = req.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"

    # Brute force check
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("attempts", 0) >= 5:
        last = attempt.get("last_attempt")
        if last:
            if isinstance(last, str):
                last = datetime.fromisoformat(last)
            if datetime.now(timezone.utc) - last < timedelta(minutes=15):
                raise HTTPException(status_code=429, detail="Too many attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(req.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"attempts": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Clear attempts on success
    await db.login_attempts.delete_many({"identifier": identifier})

    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

    return {
        "id": user_id, "email": user["email"], "name": user["name"],
        "role": user["role"], "phone": user.get("phone", ""),
        "interests": user.get("interests", []),
        "podcast_description": user.get("podcast_description", ""),
        "podcast_keywords": user.get("podcast_keywords", []),
        "access_token": access_token
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return user

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user_id = str(user["_id"])
        access_token = create_access_token(user_id, user["email"])
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
        return {"message": "Token refreshed", "access_token": access_token}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# ===================== USER ENDPOINTS =====================

@api_router.put("/user/interests")
async def update_interests(req: UpdateInterestsRequest, request: Request):
    user = await get_current_user(request)
    interests = [i.lower().strip() for i in req.interests]
    await db.users.update_one({"_id": ObjectId(user["_id"])}, {"$set": {"interests": interests}})
    return {"message": "Interests updated", "interests": interests}

@api_router.put("/user/podcast-description")
async def update_podcast_description(req: UpdatePodcastDescriptionRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can update podcast description")
    keywords = await extract_keywords(req.podcast_description)
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"podcast_description": req.podcast_description, "podcast_keywords": keywords}}
    )
    return {"message": "Description updated", "keywords": keywords}

# ===================== PODCAST ENDPOINTS =====================

@api_router.post("/podcasts/upload")
async def upload_podcast(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form("general"),
    thumbnail: Optional[UploadFile] = File(None)
):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can upload podcasts")

    # Validate file type
    allowed_audio = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/aac", "audio/flac", "audio/x-m4a", "audio/mp4"]
    allowed_video = ["video/mp4", "video/webm", "video/ogg", "video/quicktime", "video/x-msvideo"]
    allowed_types = allowed_audio + allowed_video
    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}. Allowed: audio and video files.")

    # Upload media file
    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    media_path = f"{APP_NAME}/podcasts/{user['_id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    put_object(media_path, data, content_type)

    # Upload thumbnail if provided
    thumbnail_path = ""
    if thumbnail:
        t_ext = thumbnail.filename.split(".")[-1] if "." in thumbnail.filename else "jpg"
        thumbnail_path = f"{APP_NAME}/thumbnails/{user['_id']}/{uuid.uuid4()}.{t_ext}"
        t_data = await thumbnail.read()
        put_object(thumbnail_path, t_data, thumbnail.content_type or "image/jpeg")

    # Extract keywords from description
    keywords = await extract_keywords(f"{title} {description} {category}")

    media_type = "video" if content_type in allowed_video else "audio"
    podcast_doc = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "category": category.lower(),
        "keywords": keywords,
        "media_path": media_path,
        "media_type": media_type,
        "content_type": content_type,
        "original_filename": file.filename,
        "thumbnail_path": thumbnail_path,
        "podcaster_id": user["_id"],
        "podcaster_name": user["name"],
        "play_count": 0,
        "file_size": len(data),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_deleted": False
    }
    await db.podcasts.insert_one(podcast_doc)
    podcast_doc.pop("_id", None)
    return podcast_doc

@api_router.get("/podcasts")
async def get_podcasts(
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    query = {"is_deleted": False}
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"keywords": {"$in": [search.lower()]}},
            {"podcaster_name": {"$regex": search, "$options": "i"}}
        ]
    if category:
        query["category"] = category.lower()

    skip = (page - 1) * limit
    total = await db.podcasts.count_documents(query)
    podcasts = await db.podcasts.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"podcasts": podcasts, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@api_router.get("/podcasts/my")
async def get_my_podcasts(request: Request):
    user = await get_current_user(request)
    podcasts = await db.podcasts.find(
        {"podcaster_id": user["_id"], "is_deleted": False}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"podcasts": podcasts}

@api_router.get("/podcasts/{podcast_id}")
async def get_podcast(podcast_id: str):
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False}, {"_id": 0})
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return podcast

@api_router.delete("/podcasts/{podcast_id}")
async def delete_podcast(podcast_id: str, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id})
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")
    if podcast["podcaster_id"] != user["_id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.podcasts.update_one({"id": podcast_id}, {"$set": {"is_deleted": True}})
    return {"message": "Podcast deleted"}

@api_router.get("/podcasts/{podcast_id}/stream")
async def stream_podcast(podcast_id: str):
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")

    # Increment play count
    await db.podcasts.update_one({"id": podcast_id}, {"$inc": {"play_count": 1}})

    try:
        data, ct = get_object(podcast["media_path"])
        return Response(
            content=data,
            media_type=podcast.get("content_type", ct),
            headers={"Accept-Ranges": "bytes", "Content-Disposition": f"inline; filename=\"{podcast.get('original_filename', 'podcast')}\""}
        )
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail="Failed to stream podcast")

@api_router.get("/podcasts/{podcast_id}/thumbnail")
async def get_thumbnail(podcast_id: str):
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast or not podcast.get("thumbnail_path"):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    try:
        data, ct = get_object(podcast["thumbnail_path"])
        return Response(content=data, media_type=ct)
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get thumbnail")

# ===================== VIEW HISTORY & RECOMMENDATIONS =====================

@api_router.post("/podcasts/{podcast_id}/view")
async def record_view(podcast_id: str, request: Request):
    user = await get_current_user(request)
    await db.view_history.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {"$set": {"viewed_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"message": "View recorded"}

@api_router.get("/recommendations")
async def get_recommendations(request: Request):
    user = await get_current_user(request)
    user_interests = user.get("interests", [])

    # Get viewed podcast keywords
    history = await db.view_history.find({"user_id": user["_id"]}).to_list(50)
    viewed_ids = [h["podcast_id"] for h in history]
    viewed_keywords = []
    if viewed_ids:
        viewed_podcasts = await db.podcasts.find({"id": {"$in": viewed_ids}}, {"keywords": 1, "_id": 0}).to_list(50)
        for vp in viewed_podcasts:
            viewed_keywords.extend(vp.get("keywords", []))
        viewed_keywords = list(set(viewed_keywords))

    # Get all podcasts
    all_podcasts = await db.podcasts.find({"is_deleted": False}, {"_id": 0}).to_list(100)
    if not all_podcasts:
        return {"podcasts": [], "method": "empty"}

    # Try AI recommendations
    ai_ids = await get_ai_recommendations(user_interests, viewed_keywords, all_podcasts)
    if ai_ids:
        # Order podcasts by AI ranking
        podcast_map = {p["id"]: p for p in all_podcasts}
        ordered = [podcast_map[pid] for pid in ai_ids if pid in podcast_map]
        if ordered:
            return {"podcasts": ordered[:20], "method": "ai"}

    # Fallback: keyword matching
    all_terms = list(set(user_interests + viewed_keywords))
    if all_terms:
        matched = await db.podcasts.find(
            {"is_deleted": False, "keywords": {"$in": all_terms}}, {"_id": 0}
        ).sort("play_count", -1).limit(20).to_list(20)
        if matched:
            return {"podcasts": matched, "method": "keyword"}

    # Fallback: popular
    popular = await db.podcasts.find({"is_deleted": False}, {"_id": 0}).sort("play_count", -1).limit(20).to_list(20)
    return {"podcasts": popular, "method": "popular"}

@api_router.get("/categories")
async def get_categories():
    cats = await db.podcasts.distinct("category", {"is_deleted": False})
    return {"categories": [c for c in cats if c]}

@api_router.get("/trending")
async def get_trending():
    podcasts = await db.podcasts.find({"is_deleted": False}, {"_id": 0}).sort("play_count", -1).limit(10).to_list(10)
    return {"podcasts": podcasts}

# ===================== INTEREST OPTIONS =====================

INTEREST_OPTIONS = [
    "technology", "science", "business", "health", "education",
    "entertainment", "sports", "politics", "music", "comedy",
    "true crime", "history", "philosophy", "art", "gaming",
    "finance", "travel", "food", "lifestyle", "spirituality",
    "self improvement", "news", "culture", "environment", "psychology"
]

@api_router.get("/interests/options")
async def get_interest_options():
    return {"interests": INTEREST_OPTIONS}

# Include router and CORS
app.include_router(api_router)

cors_origins = os.environ.get('CORS_ORIGINS', '*').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins != ['*'] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
