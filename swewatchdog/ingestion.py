from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from swewatchdog.domain import (
    ActionItem,
    ActionItemStatus,
    Commitment,
    Confidence,
    Deadline,
    ExpectedArtifact,
    IntegrationEvent,
    IntegrationEventKind,
    IntegrationProvider,
    JiraRef,
    Person,
    PullRequest,
    PullRequestStatus,
    ReviewerState,
    ReviewStatus,
    SourceRef,
)
from swewatchdog.intelligence import CalendarEvent, resolve_deadline

JIRA_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
REPO_HINT = re.compile(r"\brepo[:\s]+([a-zA-Z0-9_.-]+/?[a-zA-Z0-9_.-]*)", re.I)
DEADLINE_HINT = re.compile(r"\b(before|by|ahead of)\s+([^?.,;\n]+)", re.I)
ENGINEERING_VERB = re.compile(r"\b(add|fix|update|ship|implement|open|merge|review|wire|refactor|build|remove)\b", re.I)


def load_json_fixture(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def integration_event_from_fixture(payload: dict[str, Any]) -> IntegrationEvent:
    kind = IntegrationEventKind(payload["kind"])
    provider = {
        IntegrationEventKind.SLACK_MESSAGE: IntegrationProvider.SLACK,
        IntegrationEventKind.GRANOLA_NOTE: IntegrationProvider.GRANOLA,
        IntegrationEventKind.GITHUB_PR: IntegrationProvider.GITHUB,
    }[kind]
    source_url = payload.get("url") or payload.get("html_url") or payload.get("id")
    source_created_at = _parse_dt(payload.get("created_at") or payload.get("updated_at"))
    payload_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    return IntegrationEvent(
        id=f"event_{provider.value}_{kind.value}_{_stable_hash(source_url)}",
        provider=provider,
        kind=kind,
        source_url=source_url,
        source_created_at=source_created_at,
        payload_hash=payload_hash,
        payload_json=payload_json,
    )


def extract_commitment(source: dict[str, Any]) -> Commitment | None:
    text = source["text"]
    owner = _extract_owner(text)
    jira_key = _first_match(JIRA_KEY, text)
    deadline = _clean_deadline(_first_match(DEADLINE_HINT, text))
    repo = _first_group(REPO_HINT, text)
    likely_task = bool(owner or jira_key or deadline) and bool(ENGINEERING_VERB.search(text))

    if not likely_task:
        return None

    created_at = _parse_dt(source["created_at"])
    source_system = source["system"]
    return Commitment(
        id=f"commitment_{source_system}_{_stable_hash(source_system + source['url'] + text)}",
        source_system=source_system,
        source_url=source["url"],
        raw_text=text,
        candidate_owner_handle=owner,
        candidate_deadline_text=deadline,
        candidate_jira_key=jira_key,
        candidate_repo=repo,
        confidence=Confidence.HIGH if owner and (deadline or jira_key) else Confidence.MEDIUM,
        created_at=created_at,
    )


def commitment_to_action_item(
    commitment: Commitment,
    people: list[Person],
    events: list[CalendarEvent],
    now: datetime,
    default_repo: str | None,
) -> ActionItem:
    owner = _find_person(people, commitment.candidate_owner_handle)
    deadline = resolve_deadline(commitment.candidate_deadline_text or "", now, events)
    repo = commitment.candidate_repo or default_repo

    action_item = ActionItem(
        id=f"action_{commitment.id}",
        title=_summarize_title(commitment.raw_text),
        description=commitment.raw_text,
        status=ActionItemStatus.CANDIDATE_COMMITMENT,
        owner=owner,
        source=SourceRef(system=commitment.source_system, url=commitment.source_url),
        jira=JiraRef(
            key=commitment.candidate_jira_key,
            url=f"https://jira.example.com/browse/{commitment.candidate_jira_key}" if commitment.candidate_jira_key else None,
        ),
        deadline=Deadline(deadline.resolved_at, deadline.original_text, deadline.confidence),
        expected_artifact=ExpectedArtifact(repo=repo),
        created_at=commitment.created_at,
        updated_at=commitment.created_at,
    )
    return _normalize_candidate_status(action_item)


def pull_request_from_fixture(payload: dict[str, Any], people: list[Person]) -> PullRequest:
    author = _find_person(people, payload["author"]) or Person(
        id=f"person_github_{payload['author']}",
        display_name=payload["author"],
        github_username=payload["author"],
    )
    reviewers = tuple(
        ReviewerState(
            person=_find_person(people, reviewer["github_username"])
            or Person(
                id=f"person_github_{reviewer['github_username']}",
                display_name=reviewer["github_username"],
                github_username=reviewer["github_username"],
            ),
            status=reviewer["status"],
        )
        for reviewer in payload.get("reviewers", [])
    )

    return PullRequest(
        id=payload["id"],
        github_pr_number=int(payload["github_pr_number"]),
        repo=payload["repo"],
        url=payload["url"],
        title=payload["title"],
        description=payload.get("description", ""),
        author=author,
        status=PullRequestStatus(payload["status"]),
        review_status=ReviewStatus(payload["review_status"]),
        reviewers=reviewers,
        created_at=_parse_dt(payload["created_at"]),
        updated_at=_parse_dt(payload["updated_at"]),
        merged_at=_parse_optional_dt(payload.get("merged_at")),
        closed_at=_parse_optional_dt(payload.get("closed_at")),
    )


def people_from_fixture(payload: dict[str, Any]) -> list[Person]:
    return [
        Person(
            id=person["id"],
            display_name=person["display_name"],
            slack_user_id=person.get("slack_user_id"),
            github_username=person.get("github_username"),
            github_account_email=person.get("github_account_email"),
            work_email=person.get("work_email"),
            calendar_user_id=person.get("calendar_user_id"),
            aliases=tuple(person.get("aliases", [])),
        )
        for person in payload.get("people", [])
    ]


def events_from_fixture(payload: dict[str, Any]) -> list[CalendarEvent]:
    return [
        CalendarEvent(
            id=event["id"],
            title=event["title"],
            starts_at=_parse_dt(event["starts_at"]),
            ends_at=_parse_dt(event["ends_at"]),
        )
        for event in payload.get("calendar_events", [])
    ]


def _find_person(people: list[Person], handle: str | None) -> Person | None:
    if not handle:
        return None
    normalized = handle.removeprefix("@").lower()
    for person in people:
        candidates = {
            person.display_name.lower(),
            *(alias.lower() for alias in person.aliases),
        }
        if person.github_username:
            candidates.add(person.github_username.lower())
        if person.slack_user_id:
            candidates.add(person.slack_user_id.lower())
        if normalized in candidates:
            return person
    return None


def _extract_owner(text: str) -> str | None:
    slack_mention = re.search(r"<@([A-Z0-9]+)>", text)
    if slack_mention:
        return slack_mention.group(1)
    mention = re.search(r"@([a-zA-Z0-9_.-]+)", text)
    if mention:
        return mention.group(1)
    assignment = re.search(r"\b([A-Z][a-z]+)\s+(?:to|will|should|can)\b", text)
    return assignment.group(1) if assignment else None


def _summarize_title(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", text)
    cleaned = re.sub(r"@[a-zA-Z0-9_.-]+", "", cleaned)
    cleaned = JIRA_KEY.sub("", cleaned)
    cleaned = REPO_HINT.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    title = re.split(r"\b(?:before|by|ahead of)\b", cleaned, flags=re.I)[0].strip()
    title = re.sub(r"^(can you|please|to)\s+", "", title, flags=re.I).strip()
    title = re.sub(r"^[A-Z][a-z]+\s+to\s+", "", title).strip()
    return title or "Untitled engineering action item"


def _normalize_candidate_status(action_item: ActionItem) -> ActionItem:
    from dataclasses import replace

    if action_item.owner is None:
        return replace(action_item, status=ActionItemStatus.AMBIGUOUS_OWNER)
    if action_item.deadline.resolved_at is None or action_item.deadline.confidence == Confidence.LOW:
        return replace(action_item, status=ActionItemStatus.AMBIGUOUS_DEADLINE)
    if action_item.expected_artifact.repo is None:
        return replace(action_item, status=ActionItemStatus.AMBIGUOUS_REPO)
    return replace(action_item, status=ActionItemStatus.AWAITING_PR)


def _clean_deadline(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = JIRA_KEY.sub("", text)
    cleaned = REPO_HINT.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip() or None


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def _first_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def _stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _parse_optional_dt(value: str | None) -> datetime | None:
    return _parse_dt(value) if value else None
