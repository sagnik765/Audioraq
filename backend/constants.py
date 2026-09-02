"""Domain constants shared by the API schemas and the application module.

These live outside server.py so that models.py can reference them without
importing the application, which would be circular.
"""

SOCIAL_POST_STATUS_DRAFT = "draft"
SOCIAL_POST_STATUS_QUEUED = "queued"
SOCIAL_POST_STATUS_PUBLISHING = "publishing"
SOCIAL_POST_STATUS_PUBLISHED = "published"
SOCIAL_POST_STATUS_FAILED = "failed"

DEFAULT_AI_PODCAST_VOICE_IDS = ["aman-warm-analyst", "samantha-warm-cohost", "daniel-calm-british"]
