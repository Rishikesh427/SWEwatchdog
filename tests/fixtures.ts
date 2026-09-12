import type { ActionItem, Person, PullRequest } from "../src/domain/entities.js";

export const now = new Date("2026-09-12T14:00:00.000Z");

export const owner: Person = {
  id: "person_rishikesh",
  displayName: "Rishikesh",
  slackUserId: "U123",
  githubUsername: "rishikesh",
  githubAccountEmail: "rishikesh@example.com",
  workEmail: "rishikesh@company.com",
  calendarUserId: null,
  aliases: ["Rishi"]
};

export const reviewer: Person = {
  id: "person_alex",
  displayName: "Alex",
  slackUserId: "U456",
  githubUsername: "alex",
  githubAccountEmail: "alex@example.com",
  workEmail: "alex@company.com",
  calendarUserId: null,
  aliases: []
};

export function makeActionItem(overrides: Partial<ActionItem> = {}): ActionItem {
  return {
    id: "ai_1",
    title: "Add auth redirects",
    description: "Add redirects for authentication callback flow.",
    status: "awaiting_pr",
    owner,
    source: {
      system: "slack",
      url: "https://slack.example.com/thread/1",
      channelId: "C123",
      messageTs: "123.456",
      meetingId: null
    },
    jira: {
      key: "WEB-412",
      url: "https://jira.example.com/browse/WEB-412"
    },
    deadline: {
      resolvedAt: new Date("2026-09-12T18:00:00.000Z"),
      originalText: "before feature presentation",
      confidence: "high"
    },
    expectedArtifact: {
      type: "github_pr",
      repo: "web-app"
    },
    matchedPrIds: [],
    createdAt: new Date("2026-09-12T12:00:00.000Z"),
    updatedAt: new Date("2026-09-12T12:00:00.000Z"),
    lastCheckedAt: null,
    nextFollowUpAt: null,
    ...overrides
  };
}

export function makePullRequest(overrides: Partial<PullRequest> = {}): PullRequest {
  return {
    id: "pr_184",
    githubPrNumber: 184,
    repo: "web-app",
    url: "https://github.com/example/web-app/pull/184",
    title: "WEB-412 Add auth redirects",
    description: "Implements auth redirects. Source: https://slack.example.com/thread/1",
    author: owner,
    status: "open",
    reviewStatus: "review_requested",
    reviewers: [{ person: reviewer, status: "pending" }],
    createdAt: new Date("2026-09-12T13:00:00.000Z"),
    updatedAt: new Date("2026-09-12T13:00:00.000Z"),
    mergedAt: null,
    closedAt: null,
    linkedActionItemIds: [],
    ...overrides
  };
}
