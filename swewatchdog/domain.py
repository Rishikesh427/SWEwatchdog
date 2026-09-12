from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionItemStatus(StrEnum):
    CANDIDATE_COMMITMENT = "candidate_commitment"
    NEEDS_CLARIFICATION = "needs_clarification"
    AWAITING_PR = "awaiting_pr"
    PR_DETECTED = "pr_detected"
    AWAITING_REVIEW = "awaiting_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    AWAITING_MERGE = "awaiting_merge"
    DONE = "done"
    CANCELLED = "cancelled"
    NOT_PR_WORK = "not_pr_work"
    CLOSED_WITHOUT_MERGE = "closed_without_merge"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    AMBIGUOUS_OWNER = "ambiguous_owner"
    AMBIGUOUS_DEADLINE = "ambiguous_deadline"
    AMBIGUOUS_REPO = "ambiguous_repo"
    MISSING_PR_OVERDUE = "missing_pr_overdue"
    REVIEW_OVERDUE = "review_overdue"
    STALE_PR = "stale_pr"


class PullRequestStatus(StrEnum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class ReviewStatus(StrEnum):
    NO_REVIEW_REQUESTED = "no_review_requested"
    REVIEW_REQUESTED = "review_requested"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    STALE = "stale"


class FollowUpReason(StrEnum):
    MISSING_PR = "missing_pr"
    OVERDUE_REVIEW = "overdue_review"
    CHANGES_REQUESTED = "changes_requested"
    AWAITING_MERGE = "awaiting_merge"
    AMBIGUITY = "ambiguity"
    STALE_PR = "stale_pr"
    CLOSED_WITHOUT_MERGE = "closed_without_merge"


class FollowUpChannel(StrEnum):
    SLACK_DM = "slack_dm"
    SLACK_CHANNEL = "slack_channel"
    EMAIL = "email"
    GITHUB_COMMENT = "github_comment"
    NEEDS_IDENTITY_MAPPING = "needs_identity_mapping"


class IntegrationProvider(StrEnum):
    SLACK = "slack"
    GITHUB = "github"
    CALENDAR = "calendar"
    JIRA = "jira"
    GRANOLA = "granola"
    EMAIL = "email"


class IntegrationStatus(StrEnum):
    CONNECTED = "connected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNHEALTHY = "unhealthy"


class IntegrationEventKind(StrEnum):
    SLACK_MESSAGE = "slack_message"
    GRANOLA_NOTE = "granola_note"
    GITHUB_PR = "github_pr"


@dataclass(frozen=True)
class Person:
    id: str
    display_name: str
    slack_user_id: str | None = None
    github_username: str | None = None
    github_account_email: str | None = None
    work_email: str | None = None
    calendar_user_id: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    display_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))


@dataclass(frozen=True)
class IntegrationConnection:
    id: str
    account_id: str
    provider: IntegrationProvider
    status: IntegrationStatus
    scopes: tuple[str, ...] = ()
    workspace_id: str | None = None
    connected_identity: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))


@dataclass(frozen=True)
class IntegrationEvent:
    id: str
    provider: IntegrationProvider
    kind: IntegrationEventKind
    source_url: str
    source_created_at: datetime
    payload_hash: str
    payload_json: str
    processed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))


@dataclass(frozen=True)
class Deadline:
    resolved_at: datetime | None
    original_text: str | None
    confidence: Confidence


@dataclass(frozen=True)
class SourceRef:
    system: str
    url: str | None = None
    channel_id: str | None = None
    message_ts: str | None = None
    meeting_id: str | None = None


@dataclass(frozen=True)
class JiraRef:
    key: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class ExpectedArtifact:
    type: str = "github_pr"
    repo: str | None = None


@dataclass(frozen=True)
class Commitment:
    id: str
    source_system: str
    source_url: str
    raw_text: str
    candidate_owner_handle: str | None
    candidate_deadline_text: str | None
    candidate_jira_key: str | None
    candidate_repo: str | None
    confidence: Confidence
    created_at: datetime


@dataclass(frozen=True)
class ActionItem:
    id: str
    title: str
    description: str
    status: ActionItemStatus
    owner: Person | None
    source: SourceRef
    jira: JiraRef
    deadline: Deadline
    expected_artifact: ExpectedArtifact
    matched_pr_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    last_checked_at: datetime | None = None
    next_follow_up_at: datetime | None = None


@dataclass(frozen=True)
class ReviewerState:
    person: Person
    status: str


@dataclass(frozen=True)
class PullRequest:
    id: str
    github_pr_number: int
    repo: str
    url: str
    title: str
    description: str
    author: Person
    status: PullRequestStatus
    review_status: ReviewStatus
    reviewers: tuple[ReviewerState, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    linked_action_item_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FollowUpDecision:
    action_item_id: str
    pull_request_id: str | None
    recipient: Person | None
    channel: FollowUpChannel
    reason: FollowUpReason
    urgency: str
    message: str
