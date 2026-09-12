import { describe, expect, it } from "vitest";
import { resolveDeadline } from "../src/intelligence/deadlines.js";

describe("resolveDeadline", () => {
  it("resolves feature presentation language to the next matching calendar event", () => {
    const now = new Date("2026-09-12T12:00:00.000Z");
    const result = resolveDeadline("before the feature presentation", now, [
      {
        id: "event_1",
        title: "Feature Presentation",
        startsAt: new Date("2026-09-12T18:00:00.000Z"),
        endsAt: new Date("2026-09-12T19:00:00.000Z")
      }
    ]);

    expect(result.resolvedAt?.toISOString()).toBe("2026-09-12T18:00:00.000Z");
    expect(result.confidence).toBe("high");
    expect(result.matchedCalendarEventId).toBe("event_1");
  });

  it("marks unknown deadline text as low confidence", () => {
    const result = resolveDeadline("sometime soon", new Date("2026-09-12T12:00:00.000Z"), []);

    expect(result.resolvedAt).toBeNull();
    expect(result.confidence).toBe("low");
  });
});
