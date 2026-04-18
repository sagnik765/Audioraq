# Audioraq

Audioraq is a podcast-first listening and creator platform built for long-form audio and video. It helps listeners discover shows intentionally and gives podcasters a show-based workflow for publishing, audience growth, and AI-assisted episode planning.

## Product Shape

### For listeners
- Personalized home feed based on interests, listening history, saves, and follows
- Public browse and search with podcast-specific filters
- Episode detail pages, recommendation reasons, trust signals, and trending
- Continue listening, queue, history, ratings, likes, and saves

### For creators
- Show-first creator studio with shows and episodes
- Direct upload, RSS import, and AI-assisted episode planning
- Post-publish editing, analytics, moderation review, and audience controls
- Audio and video publishing with show thumbnails and episode artwork

### Platform
- React frontend served by a FastAPI backend from one Docker image
- MongoDB for app data
- Emergent Object Storage for media files
- JWT cookie auth with separate listener and creator flows

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Tailwind CSS, Shadcn UI |
| Backend | FastAPI, Motor, PyMongo |
| Database | MongoDB |
| Storage | Emergent Object Storage |
| AI | Emergent Integrations + LLM-backed generation/recommendation helpers |
| Deployment | Docker, Oracle Cloud Infrastructure, MongoDB |

## Local Development

### Prerequisites
- Node.js 20+
- Python 3.11+
- MongoDB running locally

### Environment variables

Backend in [backend/.env.example](/Users/sagnikroy/Documents/New project/Podlyzer-Centralized-Podcast-Hub/backend/.env.example):

```dotenv
MONGO_URL=mongodb://localhost:27017
DB_NAME=audioraq
JWT_SECRET=replace-with-a-long-random-secret
ADMIN_EMAIL=admin@audioraq.com
ADMIN_PASSWORD=admin123
EMERGENT_LLM_KEY=
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

Frontend in [frontend/.env.example](/Users/sagnikroy/Documents/New project/Podlyzer-Centralized-Podcast-Hub/frontend/.env.example):

```dotenv
REACT_APP_BACKEND_URL=http://localhost:8001
```

### Run locally

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# frontend
cd frontend
npm install
npm start
```

The development app runs at `http://localhost:3000`.

## Production Container

The root [Dockerfile](/Users/sagnikroy/Documents/New project/Podlyzer-Centralized-Podcast-Hub/Dockerfile) builds the React frontend and serves it from FastAPI so auth and API traffic stay on the same origin.

```bash
docker build -t audioraq .
docker run --rm -p 8001:8001 \
  -e MONGO_URL="<your-mongodb-uri>" \
  -e DB_NAME="audioraq" \
  -e JWT_SECRET="<your-secret>" \
  -e ADMIN_EMAIL="admin@audioraq.com" \
  -e ADMIN_PASSWORD="<your-admin-password>" \
  -e EMERGENT_LLM_KEY="<your-emergent-key>" \
  -e COOKIE_SECURE="true" \
  -e COOKIE_SAMESITE="lax" \
  audioraq
```

Then open `http://localhost:8001`.

## Recommended Deployment: Oracle Cloud Always Free

This repo is now prepared to deploy cleanly on an Oracle Cloud Infrastructure Always Free compute instance using Docker Compose. The Oracle path keeps the app and MongoDB on the same VM so you do not need a separate paid database service.

### Recommended Oracle shape

Use an Always Free `VM.Standard.A1.Flex` instance in your tenancy home region. A practical starting size for Audioraq is `2 OCPUs / 12 GB RAM`.

Important: Oracle documents that idle Always Free compute instances can be reclaimed. For a public app, keep an eye on instance activity and monitoring instead of assuming the VM is permanently reserved.

### 1. Create the Oracle VM

Create a public Linux instance and keep the public IPv4 address stable by assigning a reserved public IP.

Open inbound traffic for:
- `22` for SSH
- `80` for HTTP
- `443` for HTTPS

### 2. Bootstrap the instance

SSH to the instance, clone this repository, and run:

```bash
bash deploy/oracle/provision-ubuntu.sh
```

Reconnect your shell after the script finishes so Docker group membership applies.

### 3. Configure secrets and domains

Copy the Oracle env template:

```bash
cp deploy/oracle/oracle.env.example deploy/oracle/oracle.env
```

Fill in:
- `MONGO_INITDB_ROOT_PASSWORD`
- `JWT_SECRET`
- `ADMIN_PASSWORD`
- Optional legacy remote keys: `EMERGENT_LLM_KEY`, `ELEVENLABS_API_KEY`, or `OPENAI_API_KEY`

The default domains in that file are already:
- `APEX_DOMAIN=audioraq.com`
- `WWW_DOMAIN=www.audioraq.com`

### 3a. Run Create with AI locally first

Audioraq now defaults to the proof-studio voice path used for the April 11 QA episodes:

```dotenv
STORAGE_BACKEND=local
LOCAL_STORAGE_DIR=/app/data/media
AI_TEXT_PROVIDER=ollama,deterministic
AI_TEXT_ALLOW_REMOTE=false
AI_TEXT_LOCAL_ENABLED=true
AI_TEXT_LOCAL_BASE_URL=http://host.docker.internal:11434
AI_TEXT_LOCAL_MODEL=llama3.2:3b
AI_AUDIO_TTS_PROVIDER=apple_say,local
AI_AUDIO_LOCAL_TTS_URL=
AI_AUDIO_LOCAL_TTS_PROFILE=podcast-dialogue
AI_AUDIO_LOCAL_TTS_FORMAT=wav
AI_AUDIO_TARGET_LUFS=-16
AI_AUDIO_REQUIRE_NEURAL_WORKER=false
AI_AUDIO_ENFORCE_LISTENABILITY_GATE=true
AI_AUDIO_MIN_LISTENABILITY_SCORE=68
AI_AUDIO_TTS_LOCAL_FALLBACK=true
AI_AUDIO_TTS_APPLE_SAY_ENABLED=true
AI_AUDIO_TTS_LOCAL_VOICE_PROFILE=proof_studio
AI_AUDIO_TTS_LOCAL_FILTER=highpass=f=80,lowpass=f=12000,loudnorm=I=-16:TP=-1.5:LRA=11
```

`AI_TEXT_PROVIDER=ollama,deterministic` routes draft writing, Agent 2 revision, safety review, keyword extraction, and AI recommendations to a local Ollama-compatible endpoint first, then falls back to deterministic logic instead of a paid LLM API. The current code does not bundle an Ollama model; install/run the local model outside the web container and point `AI_TEXT_LOCAL_BASE_URL` at it.

`AI_AUDIO_TTS_PROVIDER=apple_say,local` uses the restored proof-studio path. On macOS it can reproduce the April 11 QA recipe with the generic system voices `Aman` for the host and `Samantha` for the co-host/guest, plus the same 0.22s dialogue gaps. OCI/Linux cannot run Apple system voices, so the live site uses `AI_AUDIO_TTS_PROVIDER=local` with the matching proof-studio local voice profile instead of forcing Kokoro.

`AI_AUDIO_TTS_PROVIDER=local_http,local` is still available when you want to route audio rendering to a local neural TTS worker first. The worker contract is `POST /v1/render` with JSON `{script_text, turns, target_loudness_lufs, format, quality_profile}` and either an audio response or JSON containing `audio_base64`, `content_type`, `extension`, `provider`, and `model`. This seam remains optional so the Create with AI USP is not dependent on a paid or quota-bound TTS server.

The worker implementation lives in [workers/ai_studio_tts_worker.py](/Users/sagnikroy/Documents/New%20project/Podlyzer-Centralized-Podcast-Hub/workers/ai_studio_tts_worker.py). It supports a local engine order such as `kokoro,chatterbox,espeak`, exposes `/health` and `/v1/status`, masters audio toward `AI_AUDIO_TARGET_LUFS`, and includes listenability profiles such as `podcast-education-calm`, `podcast-dialogue`, and `podcast-storytelling`. Only set `AI_AUDIO_REQUIRE_NEURAL_WORKER=true` after that worker is already installed and you intentionally want neural-only publishing.

`STORAGE_BACKEND=local` removes the hidden dependency on `EMERGENT_LLM_KEY` for media storage. Do not switch an existing live catalog from `emergent` to `local` until existing media has been migrated, otherwise old episode media paths will stop resolving.

The OCI worker Dockerfile preinstalls CPU-only PyTorch before optional neural engines so Kokoro/Chatterbox do not resolve large CUDA wheels on the small free-tier server. Override `AI_STUDIO_PYTORCH_CPU_VERSION` only after confirming the matching CPU wheel exists.

You can inspect the live provider state from a podcaster account with:

```text
GET /api/ai-studio/status
```

The Oracle Compose file also includes an optional `ai-studio-worker` profile. It is off by default so the website stays lightweight:

```bash
docker compose --env-file deploy/oracle/oracle.env -f deploy/oracle/docker-compose.oracle.yml --profile ai-studio up -d --build ai-studio-worker
```

If `AI_AUDIO_REQUIRE_NEURAL_WORKER=true`, `deploy/oracle/deploy.sh` automatically includes the `ai-studio` profile so future deploys keep the Kokoro worker running.

### 3b. Enable production AI voices

`Create with AI` renders playable audio with a provider chain. By default, `AI_AUDIO_TTS_PROVIDER=auto` tries:

```text
local_http worker when AI_AUDIO_LOCAL_TTS_URL is set
ElevenLabs when ELEVENLABS_API_KEY is set
OpenAI TTS when OPENAI_API_KEY is set
Apple proof-studio voices on macOS when available
local proof-studio fallback
```

For the most natural podcast-style voices, set ElevenLabs:

```dotenv
AI_AUDIO_TTS_PROVIDER=auto
ELEVENLABS_API_KEY=<your-elevenlabs-key>
ELEVENLABS_MODEL_ID=eleven_v3
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_MAX_REQUEST_CHARS=4500
ELEVENLABS_VOICE_ID_HOST=<host-voice-id>
ELEVENLABS_VOICE_ID_GUEST=<optional-guest-voice-id>
ELEVENLABS_VOICE_ID_NARRATOR=<optional-narrator-voice-id>
```

For the simplest production setup, set OpenAI TTS:

```dotenv
AI_AUDIO_TTS_PROVIDER=auto
OPENAI_API_KEY=<your-openai-key>
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE_HOST=marin
OPENAI_TTS_VOICE_GUEST=cedar
OPENAI_TTS_VOICE_NARRATOR=coral
```

Keep `AI_AUDIO_TTS_LOCAL_FALLBACK=true` so Audioraq still publishes an audio episode if the paid provider is temporarily unavailable. New AI drafts include `audio_script_turns` so interview-style episodes can render with distinct host/guest/narrator voices. If guest/narrator ElevenLabs voice IDs are blank, Audioraq safely reuses the host voice until valid additional voices are configured. Do not configure cloned voices or voices imitating real people without permission.

`AI_AUDIO_MAX_WORDS`, `AI_AUDIO_TTS_MAX_CHARS`, `AI_AUDIO_MIN_FINAL_TURN_WORDS`, and `AI_AUDIO_RESERVED_END_TURNS` control how much of a generated script becomes audio while preserving a clean ending. The default total audio cap stays under one ElevenLabs dialogue request for reliability; `ELEVENLABS_MAX_REQUEST_CHARS` protects direct provider requests from exceeding the account limit.

The built-in local fallback can be improved, but it is still not a neural production TTS provider. Set `AI_AUDIO_TTS_LOCAL_MULTIVOICE=true` and `AI_AUDIO_TTS_LOCAL_POSTPROCESS=true` to render host/guest/narrator turns with different `espeak-ng` voice variants, pacing, pitch, and ffmpeg normalization. This is useful for low-cost seeding or outages, but it should be labeled as local fallback quality rather than ElevenLabs-equivalent audio.

### 3c. Enable Google and Apple sign-in

The live app already contains the full OAuth flow. The last step is adding real provider credentials to [deploy/oracle/oracle.env.example](/Users/sagnikroy/Documents/New%20project/Podlyzer-Centralized-Podcast-Hub/deploy/oracle/oracle.env.example) and your deployed `deploy/oracle/oracle.env`.

Use these exact production callback URLs:
- Google callback: `https://www.audioraq.com/api/auth/oauth/google/callback`
- Apple callback: `https://www.audioraq.com/api/auth/oauth/apple/callback`

Set these production env vars:

```dotenv
GOOGLE_CLIENT_ID=<google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<google-oauth-client-secret>
GOOGLE_REDIRECT_URI=https://www.audioraq.com/api/auth/oauth/google/callback

APPLE_CLIENT_ID=<apple-services-id>
APPLE_TEAM_ID=<apple-team-id>
APPLE_KEY_ID=<apple-key-id>
APPLE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
APPLE_REDIRECT_URI=https://www.audioraq.com/api/auth/oauth/apple/callback
```

#### Google Cloud

1. Open Google Cloud Console and create or select the Audioraq project.
2. Configure the OAuth consent screen with app name `Audioraq`, your support email, and the authorized domain `audioraq.com`.
3. Create an OAuth client of type `Web application`.
4. Add this redirect URI:
   - `https://www.audioraq.com/api/auth/oauth/google/callback`
5. Copy the Google client ID and secret into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

#### Apple Developer

1. In Apple Developer, create or use an App ID with `Sign in with Apple` enabled.
2. Create a `Services ID`. This Services ID becomes `APPLE_CLIENT_ID`.
3. Under the Services ID configuration, enable `Sign in with Apple` for the web.
4. Set:
   - Primary App ID: your Apple app identifier with Sign in with Apple enabled
   - Domains and subdomains: `www.audioraq.com`, `audioraq.com`
   - Return URL: `https://www.audioraq.com/api/auth/oauth/apple/callback`
5. Create a `Sign in with Apple` key, download the `.p8` file once, and copy:
   - `APPLE_TEAM_ID`
   - `APPLE_KEY_ID`
   - the `.p8` contents into `APPLE_PRIVATE_KEY`

Important:
- Store `APPLE_PRIVATE_KEY` as one line with literal `\n` escapes in the env file.
- If you want extra safety, you can also add the apex callback URL in each provider console:
  - `https://audioraq.com/api/auth/oauth/google/callback`
  - `https://audioraq.com/api/auth/oauth/apple/callback`

### 4. Launch Audioraq

```bash
bash deploy/oracle/deploy.sh
```

This starts:
- MongoDB
- the Audioraq app
- Caddy for HTTPS and reverse proxy

### 5. Point GoDaddy to Oracle

In GoDaddy DNS, point the domain directly to the Oracle VM:
- `A` record for `@` -> your Oracle reserved public IP
- `A` record for `www` -> the same Oracle reserved public IP

You do not need GoDaddy forwarding with this setup. Caddy handles:
- `audioraq.com` -> redirect to `https://www.audioraq.com`
- `https://www.audioraq.com` -> Audioraq app

### 6. Verify

After DNS propagates, test:

```bash
curl https://www.audioraq.com/api/health
curl https://www.audioraq.com/api/auth/social/providers
```

Expected result:

```json
{"status":"ok"}
```

And after the provider secrets are added:

```json
{"google":true,"apple":true}
```

### Why this fixes the URL branding

On Oracle, the public URL becomes your own domain, so the user-facing URL is `www.audioraq.com` instead of a provider-generated hostname containing `podlyzer`.

## Fastest Hosted Path: Render + MongoDB Atlas

If your priority is the fastest GitHub-to-live workflow, Render is the easiest hosted option for this repo.

Use:
- a Render web service built from the root Dockerfile
- a MongoDB Atlas database for `MONGO_URL`
- `www.audioraq.com` as the custom domain in Render

The repo includes [render.yaml](/Users/sagnikroy/Documents/New%20project/Podlyzer-Centralized-Podcast-Hub/render.yaml) so Render can import the app directly from GitHub.

Important: Render's official docs say free web services have important limitations and should not be used for production applications. They can spin down after inactivity and are better for hobby/testing use. If you want a more stable live app on Render, switch the service from `free` to a paid plan after the first deploy.

## Railway To Atlas Migration

If you want to move the existing Railway data into Atlas before switching traffic, use [scripts/migrate_mongo.py](/Users/sagnikroy/Documents/New project/Podlyzer-Centralized-Podcast-Hub/scripts/migrate_mongo.py).

Example:

```bash
python3 scripts/migrate_mongo.py \
  --source-uri "<railway-mongo-uri>" \
  --source-db "podlyzer" \
  --target-uri "<atlas-uri>" \
  --target-db "audioraq"
```

Add `--drop-target` if you want the target database cleared before import.

## API Overview

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Register listener or creator |
| POST | `/api/auth/login` | Email/password sign-in |
| GET | `/api/auth/me` | Current authenticated user |
| GET | `/api/shows` | Browse and search shows |
| GET | `/api/podcasts` | Browse and search episodes |
| POST | `/api/podcasts/upload` | Upload a new episode |
| POST | `/api/podcasts/ai-create` | Publish an AI-generated audio episode from a draft |
| GET | `/api/ai-studio/status` | Inspect local/remote AI provider configuration |
| GET | `/api/recommendations` | Personalized recommendations |
| GET | `/api/trending` | Trending content |
| GET | `/api/health` | Deployment health check |

## Alternative Hosted Option

If you later decide you want less infrastructure management, the repo can still be deployed on Koyeb or another Docker host. Oracle Cloud is now the recommended path for the lowest-cost long-running deployment.

## Notes

- The current Railway files remain in the repo for backwards compatibility.
- The GitHub repo name is still unchanged. This update rebrands the product and deployment path around `Audioraq`, but renaming the repository itself is a separate GitHub action.

## Official References

- [Oracle Cloud Infrastructure Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
- [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Create an OCI compute instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm)
- [Create security lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/creating-securitylist.htm)
- [Assign a reserved public IP](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/reserved-public-ip-assign.htm)
- [Render free services](https://render.com/docs/free)
- [Render Docker deployments](https://render.com/docs/docker)
- [Render custom domains](https://render.com/docs/custom-domains)
- [Render Blueprint reference](https://render.com/docs/blueprint-spec)

## License

MIT
