import { describe, expect, it } from "vitest";
import { chooseChannel } from "../src/monitoring/rules.js";
import { reviewer } from "./fixtures.js";

describe("chooseChannel", () => {
  it("prefers Slack DM when a Slack identity is available", () => {
    expect(chooseChannel(reviewer)).toBe("slack_dm");
  });

  it("falls back to email when Slack identity is missing", () => {
    expect(chooseChannel({ ...reviewer, slackUserId: null })).toBe("email");
  });

  it("asks for identity mapping when no contact route is available", () => {
    expect(
      chooseChannel({
        ...reviewer,
        slackUserId: null,
        githubAccountEmail: null,
        workEmail: null
      })
    ).toBe("needs_identity_mapping");
  });
});
