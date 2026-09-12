import type { ActionItem, ActionItemStatus, PullRequest } from "./entities.js";

export function nextStatusForPullRequest(actionItem: ActionItem, pr: PullRequest): ActionItemStatus {
  if (pr.status === "merged") return "done";
  if (pr.status === "closed") return "closed_without_merge";
  if (pr.reviewStatus === "changes_requested" || pr.reviewStatus === "rejected") return "changes_requested";
  if (pr.reviewStatus === "approved") return "awaiting_merge";
  if (pr.reviewStatus === "review_requested") return "awaiting_review";
  if (!actionItem.matchedPrIds.includes(pr.id)) return "pr_detected";
  return actionItem.status;
}

export function normalizeCandidateStatus(actionItem: ActionItem): ActionItemStatus {
  if (!actionItem.owner) return "ambiguous_owner";
  if (!actionItem.deadline.resolvedAt || actionItem.deadline.confidence === "low") return "ambiguous_deadline";
  if (!actionItem.expectedArtifact.repo) return "ambiguous_repo";
  return "awaiting_pr";
}

export function isTerminalStatus(status: ActionItemStatus): boolean {
  return ["done", "cancelled", "not_pr_work", "closed_without_merge", "expired"].includes(status);
}
