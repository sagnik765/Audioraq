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
- `EMERGENT_LLM_KEY`

The default domains in that file are already:
- `APEX_DOMAIN=audioraq.com`
- `WWW_DOMAIN=www.audioraq.com`

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
```

Expected result:

```json
{"status":"ok"}
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
| POST | `/api/podcasts/ai-create` | Create an AI-generated episode draft |
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
