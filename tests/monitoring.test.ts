import { describe, expect, it } from "vitest";
import { evaluateActionItem } from "../src/monitoring/rules.js";
import { makeActionItem, makePullRequest, now } from "./fixtures.js";

describe("evaluateActionItem", () => {
  it("reminds the owner when a PR is missing after the deadline grace period", () => {
    const actionItem = makeActionItem({
      deadline: {
        resolvedAt: new Date("2026-09-12T13:00:00.000Z"),
        originalText: "before standup",
        confidence: "high"
      }
    });

    const decisions = evaluateActionItem(actionItem, now, []);

    expect(decisions).toHaveLength(1);
    expect(decisions[0]?.reason).toBe("missing_pr");
    expect(decisions[0]?.channel).toBe("slack_dm");
  });

  it("reminds pending reviewers when review is overdue", () => {
    const actionItem = makeActionItem({ matchedPrIds: ["pr_184"] });
    const pr = makePullRequest({
      updatedAt: new Date("2026-09-10T12:00:00.000Z")
    });

    const decisions = evaluateActionItem(actionItem, now, [pr]);

    expect(decisions).toHaveLength(1);
    expect(decisions[0]?.reason).toBe("overdue_review");
    expect(decisions[0]?.recipient?.githubUsername).toBe("alex");
  });

  it("asks for clarification when a matched PR closes without merging", () => {
    const actionItem = makeActionItem({ matchedPrIds: ["pr_184"] });
    const pr = makePullRequest({ status: "closed", closedAt: now });

    const decisions = evaluateActionItem(actionItem, now, [pr]);

    expect(decisions).toHaveLength(1);
    expect(decisions[0]?.reason).toBe("closed_without_merge");
  });
});
