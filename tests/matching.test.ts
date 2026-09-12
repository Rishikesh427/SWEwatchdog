import { describe, expect, it } from "vitest";
import { scorePullRequestMatch } from "../src/intelligence/matching.js";
import { makeActionItem, makePullRequest, owner } from "./fixtures.js";

describe("scorePullRequestMatch", () => {
  it("auto-matches when Jira, owner, repo, semantic text, and source link line up", () => {
    const result = scorePullRequestMatch(makeActionItem(), makePullRequest());

    expect(result.confidence).toBe("auto_match");
    expect(result.score).toBeGreaterThanOrEqual(70);
    expect(result.reasons).toContain("jira_key_match");
    expect(result.reasons).toContain("owner_author_match");
  });

  it("does not match weak unrelated PRs", () => {
    const result = scorePullRequestMatch(
      makeActionItem(),
      makePullRequest({
        title: "Update copy",
        description: "Small copy tweak",
        repo: "marketing-site",
        author: { ...owner, githubUsername: "someone-else" }
      })
    );

    expect(result.confidence).toBe("no_match");
  });
});
