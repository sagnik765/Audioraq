# Podlyzer - Product Requirements Document

## Original Problem Statement
Build a software that shows podcast content, separating podcasts from other content forms. Podcasters upload content, users discover and play podcasts. User accounts ask for interests; a recommendation engine suggests podcasts based on interests and viewing history. Podcaster accounts describe their podcast; keywords are extracted and matched with user interests.

## Architecture
- **Backend**: FastAPI + MongoDB + Emergent Object Storage + OpenAI GPT-5.2 (via Emergent LLM Key)
- **Frontend**: React + Tailwind CSS + Shadcn UI + Phosphor Icons
- **Auth**: JWT httpOnly cookies, bcrypt password hashing, brute force protection
- **AI**: Keyword extraction from podcast descriptions, AI-powered recommendation engine

## User Personas
1. **Listener (User)**: Discovers podcasts based on interests, plays audio/video content
2. **Podcaster**: Uploads and manages podcast episodes, tracks play counts
3. **Admin**: Platform management

## Core Requirements
- Two account types: user and podcaster
- 3-step registration: role selection → details → interests/description
- Podcast upload (audio + video) with object storage
- AI keyword extraction from descriptions
- AI-powered recommendation engine (interests + view history)
- Browse/search with category filtering
- Sticky audio/video player bar

## What's Been Implemented (March 29, 2026)
- Full JWT auth system with registration, login, logout, refresh
- Admin seeding on startup
- 3-step registration flow (role → details → interests/description)
- Podcaster dashboard with Creator Studio (stats, upload form, podcast management)
- User dashboard with AI recommendations, trending, search
- Browse page with search and category filters
- Sticky player bar with play/pause, seek, skip, volume controls
- Video modal for video podcasts
- AI keyword extraction (OpenAI GPT-5.2)
- AI recommendation engine (interests + view history matching)
- Object storage integration for podcast files
- Dark theme UI with amber/gold accents (Outfit + DM Sans fonts)
- Deployment readiness: PASSED

## Test Results
- Backend: 94.4% (17/18 tests passed)
- Frontend: 95%+ (all major flows working)
- Only issue: Object storage external service intermittent 500 errors on upload

## Prioritized Backlog
### P0 (Critical)
- Debug object storage upload intermittent failures

### P1 (High)
- Podcast episode ordering/playlists
- User profile editing page
- Password reset flow

### P2 (Medium)
- Podcast analytics for podcasters
- Comments/ratings system
- Podcast series/channels
- Share functionality

### P3 (Low)
- Social features (follow podcasters)
- Notification system
- Podcast transcription
- Monetization features
