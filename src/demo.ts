import { runWatchdogEvaluation } from "./app/orchestrator.js";
import type { ActionItem, Person, PullRequest } from "./domain/entities.js";

const now = new Date("2026-09-12T18:30:00.000Z");

const rishikesh: Person = {
  id: "person_rishikesh",
  displayName: "Rishikesh",
  slackUserId: "U123",
  githubUsername: "rishikesh",
  githubAccountEmail: "rishikesh@example.com",
  workEmail: "rishikesh@company.com",
  calendarUserId: null,
  aliases: ["Rishi"]
};

const alex: Person = {
  id: "person_alex",
  displayName: "Alex",
  slackUserId: "U456",
  githubUsername: "alex",
  githubAccountEmail: "alex@example.com",
  workEmail: "alex@company.com",
  calendarUserId: null,
  aliases: []
};

const actionItems: ActionItem[] = [
  {
    id: "ai_web_412",
    title: "Add auth redirects",
    description: "Slack commitment from launch channel before feature presentation.",
    status: "awaiting_pr",
    owner: rishikesh,
    source: {
      system: "slack",
      url: "https://slack.example.com/thread/launch-auth",
      channelId: "C-launch",
      messageTs: "1799770012.100",
      meetingId: null
    },
    jira: {
      key: "WEB-412",
      url: "https://jira.example.com/browse/WEB-412"
    },
    deadline: {
      resolvedAt: new Date("2026-09-12T18:00:00.000Z"),
      originalText: "before the feature presentation",
      confidence: "high"
    },
    expectedArtifact: {
      type: "github_pr",
      repo: "web-app"
    },
    matchedPrIds: [],
    createdAt: new Date("2026-09-12T13:00:00.000Z"),
    updatedAt: new Date("2026-09-12T13:00:00.000Z"),
    lastCheckedAt: null,
    nextFollowUpAt: null
  },
  {
    id: "ai_empty_state",
    title: "Fix onboarding empty state",
    description: "Granola meeting action item before next standup.",
    status: "awaiting_pr",
    owner: rishikesh,
    source: {
      system: "granola",
      url: "https://granola.example.com/notes/onboarding",
      channelId: null,
      messageTs: null,
      meetingId: "meeting_onboarding"
    },
    jira: {
      key: null,
      url: null
    },
    deadline: {
      resolvedAt: new Date("2026-09-12T17:00:00.000Z"),
      originalText: "before next standup",
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
    nextFollowUpAt: null
  }
];

const pullRequests: PullRequest[] = [
  {
    id: "pr_184",
    githubPrNumber: 184,
    repo: "web-app",
    url: "https://github.com/example/web-app/pull/184",
    title: "WEB-412 Add auth redirects",
    description: "Implements auth redirects. Source: https://slack.example.com/thread/launch-auth",
    author: rishikesh,
    status: "open",
    reviewStatus: "review_requested",
    reviewers: [{ person: alex, status: "pending" }],
    createdAt: new Date("2026-09-12T15:00:00.000Z"),
    updatedAt: new Date("2026-09-10T16:00:00.000Z"),
    mergedAt: null,
    closedAt: null,
    linkedActionItemIds: []
  }
];

const result = runWatchdogEvaluation(actionItems, pullRequests, now);

console.log(JSON.stringify(result, null, 2));
