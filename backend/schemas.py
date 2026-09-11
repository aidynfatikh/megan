from datetime import date as Date
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, json_schema_serialization_defaults_required=True
    )


class Segment(Model):
    id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    speaker_id: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.end < self.start:
            raise ValueError("Segment end precedes its start")
        return self


class Speaker(Model):
    id: str
    name: str
    name_source: Literal["anonymous", "explicit_introduction", "user_edit"] = "anonymous"


class Evidence(Model):
    segment_id: str
    quote: str


class Source(Evidence):
    start: float | None = None
    end: float | None = None


class Checks(Model):
    references_valid: bool = False
    quotes_match: bool = False


class Review(Model):
    state: Literal["unreviewed", "needs_review", "edited", "reviewed"] = "unreviewed"
    reasons: list[str] = Field(default_factory=list)


class Due(Model):
    raw: str | None = None
    date: Date | None = None
    resolution: Literal[
        "not_stated",
        "explicit",
        "relative",
        "ambiguous",
        "needs_meeting_date",
        "unsupported",
        "user_edit",
    ] = "not_stated"


Priority = Literal["low", "normal", "high", "unspecified"]


class DraftClaim(Model):
    evidence: list[Evidence]
    text: str = Field(min_length=1, max_length=2000)


class DraftTopic(Model):
    title: str
    theses: list[DraftClaim]


class DraftDecision(Model):
    evidence: list[Evidence]
    status: Literal["confirmed", "tentative", "reported_fact", "rejected", "superseded"] = (
        "confirmed"
    )
    text: str = Field(min_length=1, max_length=2000)


class DraftActionEvidence(Model):
    task: list[Evidence]
    assignee: list[Evidence]
    due: list[Evidence]
    priority: list[Evidence]
    conditions: list[Evidence] = Field(default_factory=list)


class DraftAction(Model):
    evidence: DraftActionEvidence
    status: Literal[
        "outstanding", "completed", "proposal", "hypothetical", "rejected", "superseded"
    ] = "outstanding"
    task: str = Field(min_length=1, max_length=2000)
    assignee: str | None
    speaker_id: str | None
    due_raw: str | None
    priority: Priority
    conditions: list[str]


class DraftReport(Model):
    # Resolve actionable state before writing narrative sections in constrained generation.
    action_items: list[DraftAction]
    decisions: list[DraftDecision]
    title: str = Field(min_length=1, max_length=200)
    summary: list[DraftClaim] = Field(max_length=5)
    topics: list[DraftTopic]
    open_questions: list[DraftClaim]
    risks: list[DraftClaim]


class Claim(Model):
    id: str
    text: str
    evidence: list[Source]
    checks: Checks
    review: Review


class Topic(Model):
    id: str
    title: str
    theses: list[Claim]


class Action(Model):
    id: str
    task: str
    assignee: str | None
    speaker_id: str | None
    due: Due
    priority: Priority
    conditions: list[str]
    evidence: dict[str, list[Source]]
    checks: Checks
    review: Review
    edited_fields: list[str] = Field(default_factory=list)


class Report(Model):
    title: str
    summary: list[Claim] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    decisions: list[Claim] = Field(default_factory=list)
    open_questions: list[Claim] = Field(default_factory=list)
    risks: list[Claim] = Field(default_factory=list)
    action_items: list[Action] = Field(default_factory=list)
    content_status: Literal["ready", "no_usable_speech"] = "ready"


class JobError(Model):
    code: str
    message: str
    stage: str
    retryable: bool = True


class Provenance(Model):
    asr_backend: str
    asr_model: str
    llm: str
    llm_digest: str | None = None
    diarization_backend: str = "none"
    diarization_model: str | None = None
    diarization_model_sha256: str | None = None
    diarization_runtime: str | None = None
    sample: bool = False


class Job(Model):
    schema_version: int = 1
    id: UUID
    filename: str
    status: Literal["queued", "running", "done", "failed", "interrupted"] = "queued"
    stage: str = "queued"
    created_at: datetime
    updated_at: datetime
    meeting_date: Date | None = None
    report_language: Literal["ru", "kk", "en"] = "ru"
    duration_sec: float | None = None
    elapsed_sec: float = 0
    timings: dict[str, float] = Field(default_factory=dict)
    segments: list[Segment] = Field(default_factory=list)
    speakers: list[Speaker] = Field(default_factory=list)
    diarization_status: Literal["disabled", "pending", "running", "done", "failed"] = "disabled"
    report: Report | None = None
    report_revision: int = 0
    attempt: int = 1
    warnings: list[str] = Field(default_factory=list)
    error: JobError | None = None
    provenance: Provenance


class ActionPatch(Model):
    revision: int = Field(ge=1)
    task: str = Field(min_length=1, max_length=2000)
    assignee: str | None = Field(max_length=200)
    due_date: Date | None
    priority: Priority


class SpeakerPatch(Model):
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=100)


class ChatRequest(Model):
    question: str = Field(min_length=1, max_length=1000)


class ChatDraft(Model):
    answer: str
    evidence: list[Evidence]


class ChatAnswer(Model):
    answer: str
    citations: list[Source]
    supported: bool
