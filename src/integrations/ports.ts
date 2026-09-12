import type { ActionItem, FollowUpDecision, PullRequest } from "../domain/entities.js";
import type { CalendarEvent } from "../intelligence/deadlines.js";

export interface SlackPort {
  fetchRecentCommitmentMessages(since: Date): Promise<unknown[]>;
  sendFollowUp(decision: FollowUpDecision): Promise<void>;
}

export interface GranolaPort {
  fetchRecentMeetingNotes(since: Date): Promise<unknown[]>;
}

export interface CalendarPort {
  fetchUpcomingEvents(from: Date, to: Date): Promise<CalendarEvent[]>;
}

export interface GitHubPort {
  fetchRecentPullRequests(since: Date): Promise<PullRequest[]>;
}

export interface ActionItemRepository {
  listOpenActionItems(): Promise<ActionItem[]>;
  saveActionItem(actionItem: ActionItem): Promise<void>;
}
