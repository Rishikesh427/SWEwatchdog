import type { ActionItem, FollowUpDecision, Person, PullRequest } from "../domain/entities.js";

const HOUR = 1000 * 60 * 60;

export interface MonitoringPolicy {
  missingPrGraceMs: number;
  reviewerGraceMs: number;
  changesRequestedGraceMs: number;
  approvedMergeGraceMs: number;
}

export const defaultMonitoringPolicy: MonitoringPolicy = {
  missingPrGraceMs: 15 * 60 * 1000,
  reviewerGraceMs: 24 * HOUR,
  changesRequestedGraceMs: 24 * HOUR,
  approvedMergeGraceMs: 12 * HOUR
};

export function evaluateActionItem(
  actionItem: ActionItem,
  now: Date,
  prs: PullRequest[],
  policy: MonitoringPolicy = defaultMonitoringPolicy
): FollowUpDecision[] {
  const matchedPrs = prs.filter((pr) => actionItem.matchedPrIds.includes(pr.id));
  if (matchedPrs.length === 0) {
    return evaluateMissingPr(actionItem, now, policy);
  }

  return matchedPrs.flatMap((pr) => evaluatePullRequest(actionItem, pr, now, policy));
}

function evaluateMissingPr(actionItem: ActionItem, now: Date, policy: MonitoringPolicy): FollowUpDecision[] {
  if (!actionItem.deadline.resolvedAt || now.getTime() < actionItem.deadline.resolvedAt.getTime() + policy.missingPrGraceMs) {
    return [];
  }

  return [
    {
      actionItemId: actionItem.id,
      pullRequestId: null,
      recipient: actionItem.owner,
      channel: chooseChannel(actionItem.owner),
      reason: "missing_pr",
      urgency: "urgent",
      message: `Expected a GitHub PR for "${actionItem.title}" by ${actionItem.deadline.resolvedAt.toISOString()}, but no matching PR is linked yet.`
    }
  ];
}

function evaluatePullRequest(
  actionItem: ActionItem,
  pr: PullRequest,
  now: Date,
  policy: MonitoringPolicy
): FollowUpDecision[] {
  if (pr.status === "closed") {
    return [
      {
        actionItemId: actionItem.id,
        pullRequestId: pr.id,
        recipient: actionItem.owner,
        channel: chooseChannel(actionItem.owner),
        reason: "closed_without_merge",
        urgency: "normal",
        message: `PR #${pr.githubPrNumber} for "${actionItem.title}" was closed without merge. Confirm whether this work is cancelled or has a replacement PR.`
      }
    ];
  }

  if (pr.reviewStatus === "review_requested") {
    return pr.reviewers
      .filter((reviewer) => reviewer.status === "pending")
      .filter(() => now.getTime() >= pr.updatedAt.getTime() + policy.reviewerGraceMs)
      .map((reviewer) => ({
        actionItemId: actionItem.id,
        pullRequestId: pr.id,
        recipient: reviewer.person,
        channel: chooseChannel(reviewer.person),
        reason: "overdue_review" as const,
        urgency: "normal" as const,
        message: `PR #${pr.githubPrNumber} for "${actionItem.title}" is waiting on your review. Please approve, request changes, or reject it.`
      }));
  }

  if (pr.reviewStatus === "changes_requested" && now.getTime() >= pr.updatedAt.getTime() + policy.changesRequestedGraceMs) {
    return [
      {
        actionItemId: actionItem.id,
        pullRequestId: pr.id,
        recipient: pr.author,
        channel: chooseChannel(pr.author),
        reason: "changes_requested",
        urgency: "normal",
        message: `Changes were requested on PR #${pr.githubPrNumber} for "${actionItem.title}", and there has not been recent activity.`
      }
    ];
  }

  if (pr.reviewStatus === "approved" && now.getTime() >= pr.updatedAt.getTime() + policy.approvedMergeGraceMs) {
    return [
      {
        actionItemId: actionItem.id,
        pullRequestId: pr.id,
        recipient: pr.author,
        channel: chooseChannel(pr.author),
        reason: "awaiting_merge",
        urgency: "normal",
        message: `PR #${pr.githubPrNumber} for "${actionItem.title}" is approved but has not merged yet.`
      }
    ];
  }

  return [];
}

export function chooseChannel(person: Person | null): FollowUpDecision["channel"] {
  if (!person) return "needs_identity_mapping";
  if (person.slackUserId) return "slack_dm";
  if (person.githubAccountEmail || person.workEmail) return "email";
  return "needs_identity_mapping";
}
