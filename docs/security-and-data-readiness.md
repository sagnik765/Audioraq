# Audioraq Security And Data Readiness

## Launch Security Baseline

Audioraq should run with production defaults that assume the public internet is hostile.

- `APP_ENV=production` must be set in production.
- `JWT_SECRET` must be unique, high entropy, and at least 32 characters.
- `ADMIN_PASSWORD` must be explicitly configured and must not use the development fallback.
- `AUTH_RETURN_BEARER_TOKENS=false` should stay disabled in production so auth tokens remain in HttpOnly cookies instead of JSON payloads.
- `SOCIAL_MANUAL_TOKEN_CONNECT_ENABLED=false` should stay disabled in production; provider accounts should connect through OAuth.
- `WRITE_TEST_CREDENTIALS=false` should stay disabled in production.
- `CORS_ORIGINS` should list explicit trusted origins, not `*`.

## Podcast Quality Guarantee

Security hardening must not lower podcast quality. The upload and AI-audio publish path still preserves the quality sequence:

- Validate media type, extension, and upload size.
- Store the uploaded media.
- Transcribe media for safety where available.
- Attach voice clarity metrics.
- Run AI Agents quality review.
- Enforce AI-created audio listenability gates.
- Enforce Audioraq Originals quality gates.
- Merge quality review into moderation.
- Block unsafe or low-quality episodes before publishing.

## Data Architecture Decision

Audioraq does not need big-data infrastructure yet. The right near-term architecture is MongoDB plus indexed event logs and daily rollups.

This is enough for launch and early traction because the product needs reliable transactional data, creator analytics, discovery filters, and retention signals before it needs Spark, Kafka, or a warehouse.

## Implemented Growth Layer

- `analytics_events` stores append-only listener/product events with TTL retention.
- `daily_episode_metrics` stores rollups for creator analytics and future recommendation learning.
- Mongo indexes now support public catalog filters, trending, highest-rated, show/season/episode hierarchy, and creator analytics.
- Event retention is controlled by `ANALYTICS_EVENT_RETENTION_DAYS`.

## When To Add Big Data Later

Move beyond MongoDB when one of these becomes true:

- Product events exceed what MongoDB can aggregate cheaply for weekly reports.
- Recommendations need offline model training on large behavioral datasets.
- Investor/customer reporting needs multi-source analytics across product, billing, marketing, and support.
- Audio/transcript processing creates a large searchable corpus that needs dedicated vector/search infrastructure.

The likely next step is not "big data" first; it is a warehouse/lakehouse export from MongoDB and object storage once real usage proves the need.
