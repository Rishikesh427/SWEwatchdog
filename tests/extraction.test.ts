import { describe, expect, it } from "vitest";
import { commitmentToActionItem, extractCommitment } from "../src/intelligence/extraction.js";
import { owner, now } from "./fixtures.js";

describe("extractCommitment", () => {
  it("extracts Slack mentions, Jira keys, and deadline language", () => {
    const commitment = extractCommitment({
      system: "slack",
      text: "@rishikesh can you add auth redirects before the feature presentation? WEB-412 repo: web-app",
      url: "https://slack.example.com/thread/1",
      createdAt: now
    });

    expect(commitment?.candidateOwnerHandle).toBe("rishikesh");
    expect(commitment?.candidateJiraKey).toBe("WEB-412");
    expect(commitment?.candidateDeadlineText).toBe("before the feature presentation");
    expect(commitment?.candidateRepo).toBe("web-app");
    expect(commitment?.confidence).toBe("high");
  });

  it("ignores casual non-engineering chatter", () => {
    const commitment = extractCommitment({
      system: "slack",
      text: "Great meeting today, thanks everyone.",
      url: "https://slack.example.com/thread/2",
      createdAt: now
    });

    expect(commitment).toBeNull();
  });
});

describe("commitmentToActionItem", () => {
  it("normalizes an extracted commitment into an action item", () => {
    const commitment = extractCommitment({
      system: "slack",
      text: "@rishikesh can you add auth redirects before the feature presentation? WEB-412 repo: web-app",
      url: "https://slack.example.com/thread/1",
      createdAt: now
    });

    if (!commitment) throw new Error("Expected commitment");

    const actionItem = commitmentToActionItem(commitment, {
      now,
      calendarEvents: [
        {
          id: "feature_presentation",
          title: "Feature Presentation",
          startsAt: new Date("2026-09-12T18:00:00.000Z"),
          endsAt: new Date("2026-09-12T19:00:00.000Z")
        }
      ],
      people: [owner],
      defaultRepo: null
    });

    expect(actionItem.owner?.githubUsername).toBe("rishikesh");
    expect(actionItem.expectedArtifact.repo).toBe("web-app");
    expect(actionItem.deadline.resolvedAt?.toISOString()).toBe("2026-09-12T18:00:00.000Z");
  });
});
