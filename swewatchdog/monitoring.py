from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from swewatchdog.domain import (
    ActionItem,
    FollowUpChannel,
    FollowUpDecision,
    FollowUpReason,
    Person,
    PullRequest,
    PullRequestStatus,
    ReviewStatus,
)


@dataclass(frozen=True)
class MonitoringPolicy:
    missing_pr_grace: timedelta = timedelta(minutes=15)
    reviewer_grace: timedelta = timedelta(hours=24)
    changes_requested_grace: timedelta = timedelta(hours=24)
    approved_merge_grace: timedelta = timedelta(hours=12)


def evaluate_action_item(
    action_item: ActionItem,
    now: datetime,
    prs: list[PullRequest],
    policy: MonitoringPolicy = MonitoringPolicy(),
) -> list[FollowUpDecision]:
    matched_prs = [pr for pr in prs if pr.id in action_item.matched_pr_ids]
    if not matched_prs:
        return _evaluate_missing_pr(action_item, now, policy)

    decisions: list[FollowUpDecision] = []
    for pr in matched_prs:
        decisions.extend(_evaluate_pr(action_item, pr, now, policy))
    return decisions


def choose_channel(person: Person | None) -> FollowUpChannel:
    if person is None:
        return FollowUpChannel.NEEDS_IDENTITY_MAPPING
    if person.slack_user_id:
        return FollowUpChannel.SLACK_DM
    if person.github_account_email or person.work_email:
        return FollowUpChannel.EMAIL
    return FollowUpChannel.NEEDS_IDENTITY_MAPPING


def _evaluate_missing_pr(action_item: ActionItem, now: datetime, policy: MonitoringPolicy) -> list[FollowUpDecision]:
    if not action_item.deadline.resolved_at:
        return []
    if now < action_item.deadline.resolved_at + policy.missing_pr_grace:
        return []
    return [
        FollowUpDecision(
            action_item_id=action_item.id,
            pull_request_id=None,
            recipient=action_item.owner,
            channel=choose_channel(action_item.owner),
            reason=FollowUpReason.MISSING_PR,
            urgency="urgent",
            message=(
                f'Expected a GitHub PR for "{action_item.title}" by '
                f"{action_item.deadline.resolved_at.isoformat()}, but no matching PR is linked yet."
            ),
        )
    ]


def _evaluate_pr(action_item: ActionItem, pr: PullRequest, now: datetime, policy: MonitoringPolicy) -> list[FollowUpDecision]:
    if pr.status == PullRequestStatus.CLOSED:
        return [
            FollowUpDecision(
                action_item_id=action_item.id,
                pull_request_id=pr.id,
                recipient=action_item.owner,
                channel=choose_channel(action_item.owner),
                reason=FollowUpReason.CLOSED_WITHOUT_MERGE,
                urgency="normal",
                message=(
                    f'PR #{pr.github_pr_number} for "{action_item.title}" was closed without merge. '
                    "Confirm whether this work is cancelled or has a replacement PR."
                ),
            )
        ]

    if pr.review_status == ReviewStatus.REVIEW_REQUESTED and now >= pr.updated_at + policy.reviewer_grace:
        return [
            FollowUpDecision(
                action_item_id=action_item.id,
                pull_request_id=pr.id,
                recipient=reviewer.person,
                channel=choose_channel(reviewer.person),
                reason=FollowUpReason.OVERDUE_REVIEW,
                urgency="normal",
                message=(
                    f'PR #{pr.github_pr_number} for "{action_item.title}" is waiting on your review. '
                    "Please approve, request changes, or reject it."
                ),
            )
            for reviewer in pr.reviewers
            if reviewer.status == "pending"
        ]

    if pr.review_status == ReviewStatus.CHANGES_REQUESTED and now >= pr.updated_at + policy.changes_requested_grace:
        return [
            FollowUpDecision(
                action_item_id=action_item.id,
                pull_request_id=pr.id,
                recipient=pr.author,
                channel=choose_channel(pr.author),
                reason=FollowUpReason.CHANGES_REQUESTED,
                urgency="normal",
                message=f'Changes were requested on PR #{pr.github_pr_number} for "{action_item.title}", and there has not been recent activity.',
            )
        ]

    if pr.review_status == ReviewStatus.APPROVED and now >= pr.updated_at + policy.approved_merge_grace:
        return [
            FollowUpDecision(
                action_item_id=action_item.id,
                pull_request_id=pr.id,
                recipient=pr.author,
                channel=choose_channel(pr.author),
                reason=FollowUpReason.AWAITING_MERGE,
                urgency="normal",
                message=f'PR #{pr.github_pr_number} for "{action_item.title}" is approved but has not merged yet.',
            )
        ]

    return []
