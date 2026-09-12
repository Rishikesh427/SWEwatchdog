import { describe, expect, it } from "vitest";
import { runWatchdogEvaluation } from "../src/app/orchestrator.js";
import { makeActionItem, makePullRequest, now } from "./fixtures.js";

describe("runWatchdogEvaluation", () => {
  it("matches a high-confidence PR and transitions to awaiting review", () => {
    const result = runWatchdogEvaluation([makeActionItem()], [makePullRequest()], now);

    expect(result.updatedActionItems[0]?.matchedPrIds).toEqual(["pr_184"]);
    expect(result.updatedActionItems[0]?.status).toBe("awaiting_review");
  });
});
