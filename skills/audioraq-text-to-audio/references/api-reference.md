# Audioraq Text-to-Audio API

This file summarizes Audioraq's public v1 API. Follow the current [online API reference](https://github.com/sagnik765/Audioraq/blob/main/docs/text-to-audio-api.md) if details change.

## Base URL and authentication

Base URL: https://www.audioraq.com/api

Create a key at https://www.audioraq.com/developers. The speech endpoint accepts it as a bearer token:

~~~http
Authorization: Bearer arq_live_...
~~~

The helper reads only AUDIORAQ_API_KEY from the agent process. It sends the key only to www.audioraq.com and refuses redirects.

## List voices

GET /v1/audio/voices is public. It returns stable voice IDs, names, styles, accents, suggested roles, supported quality profiles, and the default voice.

## Render speech

POST /v1/audio/speech returns binary audio.

~~~json
{
  "input": "Welcome to a calmer way to turn ideas into audio.",
  "voice": "aman-warm-analyst",
  "format": "mp3",
  "quality_profile": "podcast-education-calm"
}
~~~

Fields:

- input: Required. Non-empty narration text. The documented default limit is 5,000 characters.
- voice: Optional. Current ID from GET /v1/audio/voices. Documented default: aman-warm-analyst.
- format: Optional. mp3 or wav. Default: mp3.
- quality_profile: Optional. podcast-education-calm, podcast-dialogue, or podcast-storytelling.

The dialogue profile controls delivery style. The v1 request schema does not document separate speaker tracks.

## Useful response headers

- X-Request-Id: support and tracing reference.
- X-Audioraq-Voice: requested voice profile.
- X-Audioraq-Provider and X-Audioraq-Model: renderer and model or local engine used.
- X-Audioraq-Characters: request character count.
- X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset: current key limit.

## Errors

- 400: invalid voice or request option.
- 401: missing, invalid, or revoked key.
- 413: text is over the configured character limit.
- 429: per-key minute limit; respect Retry-After.
- 502: no configured renderer completed the request.

## Data and reliability

The current API documentation says usage records retain character counts and operational metadata, not submitted text. Rendering is synchronous. Long-form jobs and webhooks are planned extensions, not v1 features. The API documentation does not describe captions, audio stitching, or voice cloning for this endpoint.
