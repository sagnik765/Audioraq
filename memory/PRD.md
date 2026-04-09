# Audioraq - Product Requirements Document

## Product Vision
Audioraq is a podcast-first product built to help listeners discover long-form audio and video without competing against short-form noise, and to help creators run a podcast business workflow rather than just upload individual media files.

The next version of Audioraq should feel like:
- a personalized listening app for listeners
- a show-management and publishing tool for creators
- a discovery engine organized around shows, episodes, trust, and intent

## Problem Statement
Podcasts today are often buried inside general-purpose media platforms where discovery is driven by short-form engagement patterns rather than long-form listening intent. Listeners struggle to find relevant shows, and creators struggle to build sustainable audience workflows.

## Revised Product Direction
The product is evolving from:
- "upload podcast files and browse them"

Into:
- "create a show, publish episodes, build followers, and help listeners return to relevant content over time"

## Target User Personas
1. Listener
Discovers podcasts based on interests, search intent, saved items, listening history, and followed shows.

2. Podcaster
Creates and manages a show, publishes episodes, edits metadata after publish, tracks performance, and grows a repeat audience.

3. Admin
Oversees platform quality, creator trust, and product operations.

## Product Model
### Current Model
- one uploaded media file maps directly to one "podcast" record

### Target Model
- **Show**: the top-level creator identity and podcast brand
- **Episode**: an individual piece of audio/video content belonging to a show
- **Creator**: the account that owns one or more shows
- **Listener Graph**: interests, listening history, saved items, follows, and feedback signals

This model unlocks:
- show pages
- subscriptions / follows
- episode detail pages
- seasons and publishing structure
- better recommendation quality
- clearer analytics for creators

## Experience Principles
- Optimize for time to first value in the first session
- Make Dashboard personalized and Browse exploratory
- Use stronger listening signals than simple clicks
- Help creators manage an ongoing publishing workflow, not just file uploads
- Give users confidence through transparent recommendation reasons and trust signals
- Reduce friction for existing podcasters migrating into Audioraq

## Current Architecture
- **Backend**: FastAPI + MongoDB + Emergent Object Storage + OpenAI GPT-5.2
- **Frontend**: React + Tailwind CSS + Shadcn UI + Phosphor Icons
- **Auth**: JWT httpOnly cookies, bcrypt password hashing, brute force protection
- **AI**: keyword extraction and recommendation ranking

## Current Implemented Scope
- role-based accounts for listeners and podcasters
- 3-step registration
- episode upload with cloud object storage
- recommendations based on interests and listening/view history
- browse/search with category filtering
- sticky player with audio/video playback
- podcaster dashboard with basic stats and deletion
- trending and personalized dashboard sections

## Product Gaps To Close
### Information Architecture
- podcasts are treated as standalone uploads instead of episodes within shows
- dashboard and browse overlap too much
- there is no episode detail destination

### Onboarding And Settings
- onboarding does not clearly show progress or default paths to value
- listeners cannot easily refine interests later in the UI
- podcasters cannot clearly manage show-level identity after signup

### Discovery And Recommendations
- recommendations rely too heavily on light signals
- browse is not available to logged-out users
- recommendation reasons are not explained
- search is too shallow for high-intent discovery

### Listening Retention
- no continue listening flow
- no listening history view
- no queue / play-next behavior
- no save-for-later system
- no follows or new episode workflows

### Creator Workflow
- upload is a single-step form instead of a publish workflow
- no drafts
- no post-publish editing flow
- analytics are too basic
- no guided first-show / first-episode setup
- no RSS import for existing podcasters

## Requested Product Roadmap
### Phase 1 - Foundation
1. Separate **show** from **episode**
2. Turn Dashboard into a personalized home feed
3. Turn Browse into an exploration surface
4. Add episode detail pages
5. Add visible settings pages for listeners and podcasters
6. Improve onboarding with progress states and better defaults

### Phase 2 - Discovery And Trust
1. Open Browse to logged-out users
2. Improve recommendation signals
3. Add explicit feedback actions:
- save
- follow creator / follow show
- not interested
4. Explain why something is recommended
5. Expand search into a decision tool with:
- duration
- media type
- newest / trending
- followed creators
6. Add better empty states with action paths
7. Add trust and quality signals:
- duration
- publish cadence
- episode count
- profile quality
- verified ownership

### Phase 3 - Listening Retention
1. Add continue listening
2. Add listening history
3. Add queueing and play-next
4. Add save for later and lightweight collections
5. Add follows and new episode workflows

### Phase 4 - Creator Platform
1. Replace single-step upload with a publish flow
2. Add upload progress and draft vs publish
3. Add post-publish editing
4. Add first-upload concierge:
- create show
- choose artwork
- write show description
- publish first episode
5. Add creator analytics:
- plays over time
- drop-off
- discovery source
- interest-match insights
6. Add RSS import for creators with existing shows

## Build Order
1. Create show vs episode structure
2. Split Dashboard and Browse responsibilities
3. Add editable user/preferences settings
4. Improve recommendation signals and feedback actions
5. Add creator analytics and richer publish flow
6. Add public browse and trust signals
7. Add retention systems like continue listening, queueing, and saves
8. Add creator growth workflows such as RSS import and follower notifications

## Dependencies
### Data Model Dependencies
- show and episode separation must land before follows, subscriptions, show pages, seasons, and RSS import feel correct

### Discovery Dependencies
- stronger recommendation signals require new event tracking beyond simple click-to-play
- explanation labels should be generated from the actual ranking inputs

### Retention Dependencies
- continue listening and queue require durable player state and playback progress capture

### Creator Dependencies
- meaningful analytics require better event instrumentation first
- first-upload concierge should sit on top of the show model, not the current flat upload model

## Metrics To Track
### Listener Metrics
- signup completion rate
- time to first play
- first-session plays per user
- 7-day listener retention
- save rate
- follow rate
- continue-listening completion rate

### Discovery Metrics
- search-to-play conversion
- recommendation click-through rate
- recommendation satisfaction rate
- browse-to-signup conversion for logged-out users

### Creator Metrics
- time to first published episode
- first-week creator activation
- number of episodes published per creator
- creator return rate
- follower growth per show

## Current Priorities
### P0
- redesign the data model around shows and episodes
- redesign dashboard vs browse responsibilities

### P1
- episode detail pages
- settings and onboarding improvements
- stronger recommendation signals and feedback actions
- public browse

### P2
- continue listening
- listening history
- queue and play-next
- save for later
- follow workflows
- recommendation explanations

### P3
- advanced creator analytics
- richer publish flow
- RSS import
- trust and verification systems

## Explicit Non-Goal For Now
- generic YouTube extraction / ripping for arbitrary URLs is not part of the product roadmap

## Status
This PRD reflects the target product direction as of April 1, 2026 and supersedes the earlier "episode upload plus browse" scope.
