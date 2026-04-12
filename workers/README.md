# Audioraq AI Studio TTS Worker

The AI Studio TTS Worker is the local audio-rendering service behind `Create with AI`.
It exposes the contract the web app calls:

```text
POST /v1/render
GET /health
GET /v1/status
```

The worker is intentionally separate from the website. Run the website on OCI, then run this worker on whichever machine has the best local AI compute: your Mac, a GPU workstation, or an optional Docker Compose profile.

## Local Run

Create a Python 3.11 environment and install the base worker:

```bash
python3.11 -m venv .venv-ai-studio
source .venv-ai-studio/bin/activate
pip install -r workers/requirements.tts-worker.txt
```

Install at least one local neural engine:

```bash
pip install -r workers/requirements.tts-worker-kokoro.txt
```

Optional expressive engine:

```bash
pip install -r workers/requirements.tts-worker-chatterbox.txt
```

Start the worker:

```bash
AUDIORAQ_TTS_ENGINE=kokoro,chatterbox,espeak \
AUDIORAQ_TTS_ALLOW_ESPEAK_FALLBACK=true \
AUDIORAQ_TTS_HOST=127.0.0.1 \
AUDIORAQ_TTS_PORT=8015 \
python workers/ai_studio_tts_worker.py
```

Point the web app at it:

```dotenv
AI_AUDIO_TTS_PROVIDER=local_http,local
AI_AUDIO_LOCAL_TTS_URL=http://127.0.0.1:8015
AI_AUDIO_REQUIRE_NEURAL_WORKER=false
```

When you are ready to prevent low-quality fallback publishes, change:

```dotenv
AI_AUDIO_REQUIRE_NEURAL_WORKER=true
AUDIORAQ_TTS_ALLOW_ESPEAK_FALLBACK=false
```

## Worker Contract

Request:

```json
{
  "script_text": "",
  "turns": [
    {"speaker": "Host", "voice_role": "host", "text": "Welcome to the show."},
    {"speaker": "Guest", "voice_role": "guest", "text": "Thanks for having me."}
  ],
  "target_loudness_lufs": -16,
  "format": "wav",
  "quality_profile": "podcast-dialogue"
}
```

Successful response:

```text
Content-Type: audio/wav
X-Audioraq-TTS-Provider: ai-studio:kokoro
X-Audioraq-TTS-Provider-Kind: local-neural
X-Audioraq-TTS-Model: kokoro:a
```

If the worker uses the development fallback, it returns:

```text
X-Audioraq-TTS-Provider: ai-studio:espeak-ng
X-Audioraq-TTS-Provider-Kind: local
```

The web app can reject that fallback when `AI_AUDIO_REQUIRE_NEURAL_WORKER=true`.

## Legal And Quality Rules

Only use Chatterbox reference prompt audio that you own or have explicit permission to use. Do not use Joe Rogan, Raj Shamani, celebrities, or any real person's voice sample as a prompt without rights.

For proof-of-work publishing, use neural-only mode:

```dotenv
AUDIORAQ_TTS_ENGINE=kokoro,chatterbox
AUDIORAQ_TTS_ALLOW_ESPEAK_FALLBACK=false
AI_AUDIO_REQUIRE_NEURAL_WORKER=true
```

This makes failed neural rendering block the publish instead of quietly creating robotic audio.
