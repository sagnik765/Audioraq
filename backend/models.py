"""Request and response schemas for the Audioraq API.

Moved verbatim out of server.py; these are pure data shapes with no behaviour,
so they carry no imports from the rest of the application.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.constants import DEFAULT_AI_PODCAST_VOICE_IDS, SOCIAL_POST_STATUS_DRAFT


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str
    phone: Optional[str] = ""
    age: Optional[int] = None
    interests: Optional[List[str]] = []
    podcast_description: Optional[str] = ""
    show_title: Optional[str] = ""
    promo_code: Optional[str] = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class CompleteSocialSignupRequest(BaseModel):
    name: Optional[str] = ""
    role: str
    phone: Optional[str] = ""
    age: Optional[int] = None
    interests: Optional[List[str]] = []
    podcast_description: Optional[str] = ""
    show_title: Optional[str] = ""
    promo_code: Optional[str] = ""


class RedeemPromoRequest(BaseModel):
    code: str


class UpdateInterestsRequest(BaseModel):
    interests: List[str]


class UpdatePodcastDescriptionRequest(BaseModel):
    podcast_description: str


class UpdatePlaybackProgressRequest(BaseModel):
    progress_seconds: float = 0
    duration_seconds: float = 0
    event_type: Optional[str] = "progress"


class UpdatePodcastRatingRequest(BaseModel):
    rating: int


class EpisodeAssistantRequest(BaseModel):
    question: str


class ManualSocialConnectRequest(BaseModel):
    provider: Literal["linkedin", "instagram"]
    access_token: str
    refresh_token: Optional[str] = ""
    organization_id: Optional[str] = ""
    organization_name: Optional[str] = ""
    page_id: Optional[str] = ""
    instagram_account_id: Optional[str] = ""
    account_name: Optional[str] = ""


class SocialPostCreateRequest(BaseModel):
    provider: Literal["linkedin", "instagram"]
    social_account_id: str
    headline: str
    caption: Optional[str] = ""
    cta: Optional[str] = ""
    link_url: Optional[str] = ""
    hashtags: Optional[List[str]] = []
    scheduled_at: Optional[str] = ""
    asset_url: Optional[str] = ""
    use_generated_card: bool = True
    source: Optional[str] = "manual"
    status: Optional[str] = SOCIAL_POST_STATUS_DRAFT
    publish_now: bool = False


class FeedbackSubmissionRequest(BaseModel):
    persona: Optional[Literal["listener", "podcaster", "visitor", "investor", "other"]] = "visitor"
    category: Optional[Literal["bug", "confusing", "missing_feature", "delight", "pricing", "launch", "other"]] = "other"
    rating: Optional[int] = None
    page_url: Optional[str] = ""
    message: str
    desired_outcome: Optional[str] = ""
    friction_area: Optional[str] = ""
    email: Optional[str] = ""
    contact_ok: bool = False


class RssImportRequest(BaseModel):
    feed_url: str
    show_id: Optional[str] = ""
    import_limit: Optional[int] = 10


class PodcastIdentityInput(BaseModel):
    podcastName: str
    niche: str
    targetAudience: str


class EpisodeIntentInput(BaseModel):
    episodeGoal: Literal["educate", "entertain", "storytelling", "interview"]
    desiredOutcome: str


class ContentInput(BaseModel):
    topic: str
    keyPoints: List[str]
    references: Optional[List[str]] = []


class ToneStyleInput(BaseModel):
    tone: Literal["casual", "professional", "energetic", "storytelling"]
    format: Literal["solo", "interview", "narrative"]
    lengthPreference: Literal["short", "medium", "long"]


class GrowthOptimizationInput(BaseModel):
    optimizeFor: Literal["retention", "virality", "clarity"]
    includeHook: bool = True
    knownIssues: Optional[str] = ""


class VoiceCastingInput(BaseModel):
    selectedVoiceIds: List[str] = Field(default_factory=lambda: DEFAULT_AI_PODCAST_VOICE_IDS[:3])


class AIPodcastIntake(BaseModel):
    identity: PodcastIdentityInput
    episodeIntent: EpisodeIntentInput
    contentInput: ContentInput
    toneStyle: ToneStyleInput
    growthOptimization: GrowthOptimizationInput
    voiceCasting: VoiceCastingInput = Field(default_factory=VoiceCastingInput)


class GenerateAIPodcastDraftRequest(BaseModel):
    show_id: str
    intake: AIPodcastIntake


class CreateAIStudioProjectRequest(BaseModel):
    show_id: str
    intake: Optional[AIPodcastIntake] = None
    title: Optional[str] = ""


class UpdateAIStudioProjectRequest(BaseModel):
    title: Optional[str] = None
    intake: Optional[AIPodcastIntake] = None
    active_stage: Optional[Literal[
        "brief",
        "research",
        "outline",
        "script",
        "cast",
        "table_read",
        "final_render",
        "quality_review",
        "publish",
    ]] = None
    show_bible: Optional[Dict[str, Any]] = None
    cast: Optional[List[Dict[str, Any]]] = None


class UpdateAIStudioProjectStageRequest(BaseModel):
    stage: Literal[
        "brief",
        "research",
        "outline",
        "script",
        "cast",
        "table_read",
        "final_render",
        "quality_review",
        "publish",
    ]
    status: str = "in_progress"
    notes: Optional[str] = ""
    artifact: Optional[Dict[str, Any]] = None


class CreateAIStudioRenderJobRequest(BaseModel):
    project_id: str
    draft_id: Optional[str] = ""
    render_type: Literal["preview", "final"] = "preview"
