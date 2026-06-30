from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.text_to_audio_api import (
    API_KEY_PREFIX,
    TextToAudioRequest,
    build_text_to_audio_router,
    extract_api_key,
    generate_api_key,
    hash_api_key,
    public_key_document,
)


class FakeResult:
    def __init__(self, modified_count=0):
        self.modified_count = modified_count


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_args):
        return self

    async def to_list(self, _limit):
        return list(self.documents)


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(dict(document))

    async def count_documents(self, query):
        return len([document for document in self.documents if matches(document, query)])

    async def find_one(self, query):
        return next((document for document in self.documents if matches(document, query)), None)

    def find(self, query):
        return FakeCursor([document for document in self.documents if matches(document, query)])

    async def update_one(self, query, update):
        document = await self.find_one(query)
        if not document:
            return FakeResult()
        for key, value in update.get("$set", {}).items():
            document[key] = value
        for key, value in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + value
        return FakeResult(modified_count=1)

    async def find_one_and_update(self, query, update, upsert=False, **_kwargs):
        document = await self.find_one(query)
        if not document and upsert:
            document = {"_id": query["_id"], **update.get("$setOnInsert", {})}
            self.documents.append(document)
        for key, value in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + value
        return document

    def aggregate(self, _pipeline):
        if not self.documents:
            return FakeCursor([])
        return FakeCursor(
            [
                {
                    "requests": len(self.documents),
                    "characters": sum(item["character_count"] for item in self.documents),
                    "output_bytes": sum(item["output_bytes"] for item in self.documents),
                    "average_latency_ms": sum(item["latency_ms"] for item in self.documents) / len(self.documents),
                }
            ]
        )


class FakeDatabase:
    def __init__(self):
        self.developer_api_keys = FakeCollection()
        self.text_to_audio_usage = FakeCollection()
        self.text_to_audio_rate_limits = FakeCollection()


def matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


def make_request(headers=None):
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": encoded_headers})


def test_generated_api_keys_are_unique_and_hash_deterministically():
    first = generate_api_key()
    second = generate_api_key()

    assert first.startswith(API_KEY_PREFIX)
    assert second.startswith(API_KEY_PREFIX)
    assert first != second
    assert hash_api_key(first) == hash_api_key(first)
    assert hash_api_key(first) != hash_api_key(second)
    assert first not in hash_api_key(first)


def test_api_key_can_be_read_from_bearer_or_explicit_header():
    bearer_key = generate_api_key()
    explicit_key = generate_api_key()

    assert extract_api_key(make_request({"Authorization": f"Bearer {bearer_key}"})) == bearer_key
    assert extract_api_key(make_request({"X-Audioraq-Key": explicit_key})) == explicit_key
    assert extract_api_key(make_request({"Authorization": "Bearer a-user-jwt"})) == ""


def test_speech_request_normalizes_whitespace_and_defaults_to_mp3():
    request = TextToAudioRequest(input="  A clear   sentence.  ")

    assert request.input == "A clear sentence."
    assert request.format == "mp3"
    assert request.voice == "aman-warm-analyst"


def test_public_key_document_never_exposes_the_hash():
    public = public_key_document(
        {
            "id": "key-1",
            "name": "Production",
            "display_prefix": "arq_live_abcd...wxyz",
            "key_hash": "secret-digest",
            "scopes": ["audio:speech"],
            "requests_count": 3,
            "characters_count": 120,
        }
    )

    assert public["prefix"] == "arq_live_abcd...wxyz"
    assert public["requests_count"] == 3
    assert "key_hash" not in public


def test_key_creation_speech_delivery_usage_and_revocation_work_end_to_end():
    database = FakeDatabase()
    app = FastAPI()

    async def current_user(_request):
        return {"_id": "user-1", "role": "podcaster"}

    def render_audio(_text, turns, output_format, quality_profile):
        assert turns[0]["voice_id"] == "voice-one"
        assert output_format == "mp3"
        assert quality_profile == "podcast-education-calm"
        return {
            "data": b"ID3" + (b"a" * 4096),
            "content_type": "audio/mpeg",
            "extension": "mp3",
            "provider": "test:local-neural",
            "provider_kind": "local-neural",
            "model": "test-model",
        }

    app.include_router(
        build_text_to_audio_router(
            db=database,
            get_current_user=current_user,
            render_audio=render_audio,
            voices=[
                {
                    "id": "voice-one",
                    "name": "Voice One",
                    "gender": "male",
                    "style": "calm",
                    "accent": "Neutral English",
                    "description": "A test voice.",
                    "suggested_roles": ["narrator"],
                }
            ],
            public_voice=lambda voice: dict(voice),
        ),
        prefix="/api",
    )
    client = TestClient(app)

    created = client.post("/api/developer/api-keys", json={"name": "Test key"})
    assert created.status_code == 200
    raw_key = created.json()["key"]
    assert raw_key.startswith(API_KEY_PREFIX)
    assert raw_key not in str(database.developer_api_keys.documents)

    speech = client.post(
        "/api/v1/audio/speech",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"input": "A sentence worth hearing.", "voice": "voice-one", "format": "mp3"},
    )
    assert speech.status_code == 200
    assert speech.headers["content-type"].startswith("audio/mpeg")
    assert speech.headers["x-audioraq-provider"] == "test:local-neural"
    assert speech.content.startswith(b"ID3")
    assert database.text_to_audio_usage.documents[0]["character_count"] == 25
    assert "input" not in database.text_to_audio_usage.documents[0]

    usage = client.get("/api/developer/usage")
    assert usage.status_code == 200
    assert usage.json()["requests"] == 1
    assert usage.json()["text_retained"] is False

    key_id = created.json()["api_key"]["id"]
    revoked = client.delete(f"/api/developer/api-keys/{key_id}")
    assert revoked.status_code == 200
    rejected = client.post(
        "/api/v1/audio/speech",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"input": "This should fail.", "voice": "voice-one"},
    )
    assert rejected.status_code == 401
