import type { Confidence } from "../domain/entities.js";

export interface CalendarEvent {
  id: string;
  title: string;
  startsAt: Date;
  endsAt: Date;
}

export interface ResolvedDeadline {
  resolvedAt: Date | null;
  originalText: string | null;
  confidence: Confidence;
  matchedCalendarEventId: string | null;
}

const ritualKeywords = [
  ["feature presentation", ["feature presentation", "feature demo", "demo"]],
  ["standup", ["standup", "daily"]],
  ["sprint review", ["sprint review", "review"]],
  ["launch sync", ["launch sync", "launch"]]
] as const;

export function resolveDeadline(text: string, now: Date, calendarEvents: CalendarEvent[]): ResolvedDeadline {
  const normalized = text.toLowerCase();

  for (const [, aliases] of ritualKeywords) {
    const alias = aliases.find((candidate) => normalized.includes(candidate));
    if (!alias) continue;

    const event = findNextEvent(calendarEvents, now, aliases);
    if (event) {
      return {
        resolvedAt: event.startsAt,
        originalText: text,
        confidence: "high",
        matchedCalendarEventId: event.id
      };
    }
  }

  if (normalized.includes("eod")) {
    const endOfDay = new Date(now);
    endOfDay.setHours(17, 0, 0, 0);
    return {
      resolvedAt: endOfDay,
      originalText: text,
      confidence: "medium",
      matchedCalendarEventId: null
    };
  }

  if (normalized.includes("tomorrow")) {
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(10, 0, 0, 0);
    return {
      resolvedAt: tomorrow,
      originalText: text,
      confidence: "medium",
      matchedCalendarEventId: null
    };
  }

  return {
    resolvedAt: null,
    originalText: text || null,
    confidence: "low",
    matchedCalendarEventId: null
  };
}

function findNextEvent(events: CalendarEvent[], now: Date, aliases: readonly string[]): CalendarEvent | null {
  const matches = events
    .filter((event) => event.startsAt > now)
    .filter((event) => aliases.some((alias) => event.title.toLowerCase().includes(alias)))
    .sort((a, b) => a.startsAt.getTime() - b.startsAt.getTime());

  return matches[0] ?? null;
}
