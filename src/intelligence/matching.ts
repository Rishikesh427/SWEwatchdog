import type { ActionItem, PullRequest } from "../domain/entities.js";

export interface MatchResult {
  score: number;
  confidence: "auto_match" | "tentative" | "no_match";
  reasons: string[];
}

export function scorePullRequestMatch(actionItem: ActionItem, pr: PullRequest, openedNearMs = 1000 * 60 * 60 * 24 * 3): MatchResult {
  let score = 0;
  const reasons: string[] = [];
  const searchablePrText = `${pr.title} ${pr.description}`.toLowerCase();

  if (actionItem.jira.key && searchablePrText.includes(actionItem.jira.key.toLowerCase())) {
    score += 45;
    reasons.push("jira_key_match");
  }

  if (actionItem.owner?.githubUsername && actionItem.owner.githubUsername === pr.author.githubUsername) {
    score += 20;
    reasons.push("owner_author_match");
  }

  if (actionItem.expectedArtifact.repo && actionItem.expectedArtifact.repo === pr.repo) {
    score += 15;
    reasons.push("repo_match");
  }

  if (hasSemanticTokenOverlap(actionItem.title, searchablePrText)) {
    score += 15;
    reasons.push("semantic_title_overlap");
  }

  const openedNearDeadline =
    actionItem.deadline.resolvedAt &&
    Math.abs(actionItem.deadline.resolvedAt.getTime() - pr.createdAt.getTime()) <= openedNearMs;
  if (openedNearDeadline) {
    score += 10;
    reasons.push("temporal_proximity");
  }

  if (actionItem.source.url && pr.description.includes(actionItem.source.url)) {
    score += 30;
    reasons.push("source_link_in_pr");
  }

  if (actionItem.owner?.githubUsername && actionItem.owner.githubUsername !== pr.author.githubUsername) {
    score -= 30;
    reasons.push("conflicting_owner");
  }

  if (pr.status === "closed") {
    score -= 20;
    reasons.push("closed_pr_penalty");
  }

  return {
    score,
    confidence: score >= 70 ? "auto_match" : score >= 45 ? "tentative" : "no_match",
    reasons
  };
}

function hasSemanticTokenOverlap(actionTitle: string, prText: string): boolean {
  const stopWords = new Set(["the", "a", "an", "to", "for", "and", "or", "of", "in", "on", "by"]);
  const tokens = actionTitle
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length > 2 && !stopWords.has(token));

  if (tokens.length === 0) return false;

  const matches = tokens.filter((token) => prText.includes(token));
  return matches.length / tokens.length >= 0.5;
}
