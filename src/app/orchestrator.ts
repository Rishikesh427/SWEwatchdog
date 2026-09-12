import { nextStatusForPullRequest } from "../domain/stateMachine.js";
import type { ActionItem, FollowUpDecision, PullRequest } from "../domain/entities.js";
import { scorePullRequestMatch } from "../intelligence/matching.js";
import { evaluateActionItem } from "../monitoring/rules.js";

export interface WatchdogRunResult {
  updatedActionItems: ActionItem[];
  followUps: FollowUpDecision[];
}

export function runWatchdogEvaluation(actionItems: ActionItem[], pullRequests: PullRequest[], now: Date): WatchdogRunResult {
  const updatedActionItems = actionItems.map((actionItem) => matchAndTransition(actionItem, pullRequests));
  const followUps = updatedActionItems.flatMap((actionItem) => evaluateActionItem(actionItem, now, pullRequests));

  return {
    updatedActionItems,
    followUps
  };
}

function matchAndTransition(actionItem: ActionItem, pullRequests: PullRequest[]): ActionItem {
  const candidate = pullRequests
    .map((pr) => ({ pr, match: scorePullRequestMatch(actionItem, pr) }))
    .filter(({ match }) => match.confidence === "auto_match")
    .sort((a, b) => b.match.score - a.match.score)[0];

  if (!candidate) return actionItem;

  const matchedPrIds = actionItem.matchedPrIds.includes(candidate.pr.id)
    ? actionItem.matchedPrIds
    : [...actionItem.matchedPrIds, candidate.pr.id];

  return {
    ...actionItem,
    status: nextStatusForPullRequest({ ...actionItem, matchedPrIds }, candidate.pr),
    matchedPrIds,
    updatedAt: new Date()
  };
}
