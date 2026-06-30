# Audioraq Text-to-Audio API

The Audioraq API converts text into finished MP3 or WAV audio. It reuses the same voice profiles, sentence-aware pacing, one-second pauses, edge padding, and mastering pipeline used by the Creator Studio.

## Base URL

```text
https://www.audioraq.com/api
```

The current stable version is `v1`.

## Authentication

Create an API key at [www.audioraq.com/developers](https://www.audioraq.com/developers). Send it as a bearer token:

```http
Authorization: Bearer arq_live_...
```

`X-Audioraq-Key` and `X-API-Key` are also accepted. Keep keys on a trusted server and never expose them in browser or mobile application source code. Raw keys are displayed once; Audioraq stores only a SHA-256 digest.

## Create Speech

`POST /v1/audio/speech`

```json
{
  "input": "Welcome to a calmer way to turn ideas into audio.",
  "voice": "aman-warm-analyst",
  "format": "mp3",
  "quality_profile": "podcast-education-calm"
}
```

| Field | Required | Values |
| --- | --- | --- |
| `input` | Yes | Non-empty text, up to the configured request limit; 5,000 characters by default |
| `voice` | No | An ID returned by `GET /v1/audio/voices`; defaults to `aman-warm-analyst` |
| `format` | No | `mp3` or `wav`; defaults to `mp3` |
| `quality_profile` | No | `podcast-education-calm`, `podcast-dialogue`, or `podcast-storytelling` |

The response body is binary audio. Useful response headers include:

- `X-Request-Id`: support and tracing identifier.
- `X-Audioraq-Voice`: stable requested voice profile.
- `X-Audioraq-Provider`: renderer selected by the configured provider chain.
- `X-Audioraq-Model`: model or local engine used.
- `X-Audioraq-Characters`: billable/request character count.
- `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`: current key limit.

### cURL

```bash
curl https://www.audioraq.com/api/v1/audio/speech \
  -H "Authorization: Bearer $AUDIORAQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Welcome to a calmer way to turn ideas into audio.",
    "voice": "aman-warm-analyst",
    "format": "mp3",
    "quality_profile": "podcast-education-calm"
  }' \
  --output audioraq-speech.mp3
```

### Python

```python
import os
import requests

response = requests.post(
    "https://www.audioraq.com/api/v1/audio/speech",
    headers={"Authorization": f"Bearer {os.environ['AUDIORAQ_API_KEY']}"},
    json={
        "input": "Your text becomes finished, paced audio.",
        "voice": "samantha-warm-cohost",
        "format": "mp3",
        "quality_profile": "podcast-education-calm",
    },
    timeout=180,
)
response.raise_for_status()
with open("speech.mp3", "wb") as audio_file:
    audio_file.write(response.content)
```

## List Voices

`GET /v1/audio/voices` is public and returns the stable voice IDs, names, styles, accents, suggested roles, supported quality profiles, and the default voice.

## Key Management

Authenticated Audioraq accounts can manage keys through the website or these same-origin session endpoints:

- `GET /developer/api-keys`
- `POST /developer/api-keys` with `{ "name": "Production" }`
- `DELETE /developer/api-keys/{key_id}`
- `GET /developer/usage`

Key-management endpoints use the Audioraq session cookie, not a developer API key.

## Errors

| Status | Meaning |
| --- | --- |
| `400` | Unknown voice or invalid request option |
| `401` | Missing, invalid, or revoked API key |
| `413` | Input exceeds the character limit |
| `429` | Per-key minute limit exceeded; inspect `Retry-After` |
| `502` | No configured audio renderer completed the request |

## Privacy and Reliability

- Usage records do not retain input text.
- Raw API keys are never stored.
- Rendering runs off the async web event loop so other requests remain responsive.
- Provider routing can use the local neural worker and configured fallbacks without changing the public API contract.
- The first release is synchronous. Long-form jobs and webhooks are a planned versioned extension rather than an unstable behavior in `v1`.
