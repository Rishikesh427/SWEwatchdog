from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from swewatchdog.domain import ActionItem, Confidence, PullRequest


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class ResolvedDeadline:
    resolved_at: datetime | None
    original_text: str | None
    confidence: Confidence
    matched_calendar_event_id: str | None


@dataclass(frozen=True)
class MatchResult:
    score: int
    confidence: str
    reasons: tuple[str, ...]


RITUAL_KEYWORDS = (
    ("feature presentation", ("feature presentation", "feature demo", "demo")),
    ("standup", ("standup", "daily")),
    ("sprint review", ("sprint review", "review")),
    ("launch sync", ("launch sync", "launch")),
)


def resolve_deadline(text: str, now: datetime, events: list[CalendarEvent]) -> ResolvedDeadline:
    normalized = text.lower()

    for _, aliases in RITUAL_KEYWORDS:
        if any(alias in normalized for alias in aliases):
            event = _find_next_event(events, now, aliases)
            if event:
                return ResolvedDeadline(event.starts_at, text, Confidence.HIGH, event.id)

    if "eod" in normalized:
        return ResolvedDeadline(now.replace(hour=17, minute=0, second=0, microsecond=0), text, Confidence.MEDIUM, None)

    if "tomorrow" in normalized:
        tomorrow = now + timedelta(days=1)
        return ResolvedDeadline(tomorrow.replace(hour=10, minute=0, second=0, microsecond=0), text, Confidence.MEDIUM, None)

    return ResolvedDeadline(None, text or None, Confidence.LOW, None)


def score_pull_request_match(action_item: ActionItem, pr: PullRequest, opened_near: timedelta = timedelta(days=3)) -> MatchResult:
    score = 0
    reasons: list[str] = []
    pr_text = f"{pr.title} {pr.description}".lower()

    if action_item.jira.key and action_item.jira.key.lower() in pr_text:
        score += 45
        reasons.append("jira_key_match")

    if action_item.owner and action_item.owner.github_username == pr.author.github_username:
        score += 20
        reasons.append("owner_author_match")

    if action_item.expected_artifact.repo and action_item.expected_artifact.repo == pr.repo:
        score += 15
        reasons.append("repo_match")

    if _has_semantic_token_overlap(action_item.title, pr_text):
        score += 15
        reasons.append("semantic_title_overlap")

    if action_item.deadline.resolved_at and abs(action_item.deadline.resolved_at - pr.created_at) <= opened_near:
        score += 10
        reasons.append("temporal_proximity")

    if action_item.source.url and action_item.source.url in pr.description:
        score += 30
        reasons.append("source_link_in_pr")

    if action_item.owner and action_item.owner.github_username != pr.author.github_username:
        score -= 30
        reasons.append("conflicting_owner")

    if pr.status == "closed":
        score -= 20
        reasons.append("closed_pr_penalty")

    if score >= 70:
        confidence = "auto_match"
    elif score >= 45:
        confidence = "tentative"
    else:
        confidence = "no_match"

    return MatchResult(score, confidence, tuple(reasons))


def _find_next_event(events: list[CalendarEvent], now: datetime, aliases: tuple[str, ...]) -> CalendarEvent | None:
    matches = [
        event
        for event in events
        if event.starts_at > now and any(alias in event.title.lower() for alias in aliases)
    ]
    return sorted(matches, key=lambda event: event.starts_at)[0] if matches else None


def _has_semantic_token_overlap(title: str, pr_text: str) -> bool:
    stop_words = {"the", "a", "an", "to", "for", "and", "or", "of", "in", "on", "by", "can", "you"}
    tokens = [token for token in re.split(r"[^a-z0-9]+", title.lower()) if len(token) > 2 and token not in stop_words]
    if not tokens:
        return False
    matches = [token for token in tokens if token in pr_text]
    return len(matches) / len(tokens) >= 0.5
