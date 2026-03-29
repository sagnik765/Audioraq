# PodcastHub

**A dedicated podcast discovery and streaming platform — built so podcasters don't have to compete with every other type of content on the internet.**

---

## The Problem

Podcasts today live on YouTube, Spotify, and other general-purpose platforms where they're buried under short-form videos, music, and trending clips. Podcasters compete not just with each other, but with every content creator on the platform. Listeners searching for specific podcast topics have to sift through unrelated media to find what they want.

## The Solution

PodcastHub is a platform built exclusively for podcasts. Creators upload directly to an audience that's here specifically for long-form audio and video content. An AI-powered recommendation engine connects listeners with the right shows based on their stated interests and listening history — no algorithm games, no noise.

---

## Features

### For Listeners
- **Interest-Based Onboarding** — Select your topics during sign-up (technology, true crime, comedy, philosophy, etc.) and get immediate, relevant recommendations
- **AI-Powered Recommendations** — OpenAI GPT-5.2 analyzes your interests and viewing history to surface podcasts you'll actually want to hear
- **Search & Browse** — Full-text search across titles, descriptions, creators, and keywords with category filtering
- **Inline Player** — Sticky audio/video player bar with play/pause, seek, skip ±15s, and volume controls. Video podcasts open in a dedicated modal
- **Trending Section** — See what the community is listening to right now

### For Podcasters
- **Creator Studio Dashboard** — Upload episodes, track play counts, and manage your catalog from one place
- **Audio & Video Support** — Upload MP3, WAV, MP4, WebM, and other standard formats directly to cloud storage
- **Automatic Keyword Extraction** — Describe your podcast and AI extracts relevant keywords that match listener interests
- **Thumbnail Support** — Attach cover art to each episode for a polished presentation
- **Category Tagging** — Organize episodes under topics so listeners can filter and find your content

### Platform
- **Role-Based Accounts** — Separate flows for listeners and podcasters with dedicated dashboards for each
- **JWT Authentication** — Secure httpOnly cookie-based sessions with refresh tokens, brute force protection, and admin seeding
- **Cloud Object Storage** — Podcast media files stored via Emergent Object Storage with streaming playback

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React, Tailwind CSS, Shadcn/UI, Phosphor Icons |
| **Backend** | FastAPI (Python), Motor (async MongoDB driver) |
| **Database** | MongoDB |
| **Storage** | Emergent Object Storage (audio/video files) |
| **AI** | OpenAI GPT-5.2 via Emergent Integrations (keyword extraction + recommendations) |
| **Auth** | JWT (PyJWT), bcrypt password hashing, httpOnly cookies |

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│   React UI  │────▶│  FastAPI /api │────▶│  MongoDB  │
│  (port 3000)│     │  (port 8001) │     │           │
└─────────────┘     └──────┬───────┘     └───────────┘
                           │
                    ┌──────┴───────┐
                    │              │
              ┌─────▼─────┐ ┌─────▼──────┐
              │  Emergent  │ │  OpenAI    │
              │  Storage   │ │  GPT-5.2   │
              └────────────┘ └────────────┘
```

---

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- MongoDB running locally on port 27017

### Environment Variables

**Backend** (`/backend/.env`):
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
JWT_SECRET="<your-64-char-hex-secret>"
ADMIN_EMAIL="admin@podcasthub.com"
ADMIN_PASSWORD="admin123"
EMERGENT_LLM_KEY="<your-emergent-key>"
```

**Frontend** (`/frontend/.env`):
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

### Run Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd frontend
yarn install
yarn start
```

The app will be available at `http://localhost:3000`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register (user or podcaster) |
| POST | `/api/auth/login` | Login with email/password |
| POST | `/api/auth/logout` | Clear session cookies |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/interests/options` | List available interest topics |
| PUT | `/api/user/interests` | Update user interests |
| POST | `/api/podcasts/upload` | Upload a podcast (multipart) |
| GET | `/api/podcasts` | List/search podcasts |
| GET | `/api/podcasts/my` | List podcaster's own episodes |
| GET | `/api/podcasts/{id}` | Get single podcast |
| DELETE | `/api/podcasts/{id}` | Delete a podcast |
| GET | `/api/podcasts/{id}/stream` | Stream podcast media |
| GET | `/api/podcasts/{id}/thumbnail` | Get episode thumbnail |
| POST | `/api/podcasts/{id}/view` | Record a view |
| GET | `/api/recommendations` | AI-powered recommendations |
| GET | `/api/trending` | Top podcasts by play count |
| GET | `/api/categories` | List active categories |

---

## How the Recommendation Engine Works

1. **On registration**, listeners select interests (e.g., technology, comedy, history)
2. **On upload**, the AI extracts keywords from the podcaster's episode description
3. **When a listener opens their dashboard**, the engine:
   - Gathers their stated interests
   - Collects keywords from previously viewed podcasts
   - Sends both to GPT-5.2 alongside the full podcast catalog
   - Returns a ranked list of the most relevant episodes
4. **Fallback**: If the AI call fails, it falls back to keyword matching, then to popularity-based ranking

---

## License

MIT
