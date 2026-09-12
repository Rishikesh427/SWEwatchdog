from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from swewatchdog.domain import ActionItem, ActionItemStatus, PullRequest, PullRequestStatus, ReviewStatus
from swewatchdog.intelligence import score_pull_request_match
from swewatchdog.monitoring import evaluate_action_item


def run_watchdog_evaluation(
    action_items: list[ActionItem],
    pull_requests: list[PullRequest],
    now: datetime,
) -> tuple[list[ActionItem], list]:
    updated = [_match_and_transition(item, pull_requests, now) for item in action_items]
    follow_ups = [decision for item in updated for decision in evaluate_action_item(item, now, pull_requests)]
    return updated, follow_ups


def transition_for_pr(pr: PullRequest) -> ActionItemStatus:
    if pr.status == PullRequestStatus.MERGED:
        return ActionItemStatus.DONE
    if pr.status == PullRequestStatus.CLOSED:
        return ActionItemStatus.CLOSED_WITHOUT_MERGE
    if pr.review_status in {ReviewStatus.CHANGES_REQUESTED, ReviewStatus.REJECTED}:
        return ActionItemStatus.CHANGES_REQUESTED
    if pr.review_status == ReviewStatus.APPROVED:
        return ActionItemStatus.AWAITING_MERGE
    if pr.review_status == ReviewStatus.REVIEW_REQUESTED:
        return ActionItemStatus.AWAITING_REVIEW
    return ActionItemStatus.PR_DETECTED


def _match_and_transition(action_item: ActionItem, prs: list[PullRequest], now: datetime) -> ActionItem:
    candidates = sorted(
        ((pr, score_pull_request_match(action_item, pr)) for pr in prs),
        key=lambda item: item[1].score,
        reverse=True,
    )
    auto_match = next((candidate for candidate in candidates if candidate[1].confidence == "auto_match"), None)
    if not auto_match:
        return action_item

    pr = auto_match[0]
    matched_ids = action_item.matched_pr_ids
    if pr.id not in matched_ids:
        matched_ids = (*matched_ids, pr.id)

    return replace(action_item, status=transition_for_pr(pr), matched_pr_ids=matched_ids, updated_at=now)
