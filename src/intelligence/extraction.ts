import type { ActionItem, Commitment, Person } from "../domain/entities.js";
import { resolveDeadline, type CalendarEvent } from "./deadlines.js";

export interface RawConversationSource {
  system: "slack" | "granola";
  text: string;
  url: string;
  createdAt: Date;
  channelId?: string;
  messageTs?: string;
  meetingId?: string;
}

export interface ExtractionContext {
  now: Date;
  calendarEvents: CalendarEvent[];
  people: Person[];
  defaultRepo: string | null;
}

const jiraKeyPattern = /\b[A-Z][A-Z0-9]+-\d+\b/;
const repoPattern = /\brepo[:\s]+([a-zA-Z0-9_.-]+\/?[a-zA-Z0-9_.-]*)/i;
const deadlinePattern = /\b(before|by|ahead of)\s+([^?.,;\n]+)/i;

export function extractCommitment(source: RawConversationSource): Commitment | null {
  const jiraKey = source.text.match(jiraKeyPattern)?.[0] ?? null;
  const ownerHandle = extractOwnerHandle(source.text);
  const deadlineText = cleanDeadlineText(source.text.match(deadlinePattern)?.[0] ?? null);
  const repo = source.text.match(repoPattern)?.[1] ?? null;
  const likelyTask = Boolean(ownerHandle || jiraKey || deadlineText) && hasEngineeringVerb(source.text);

  if (!likelyTask) return null;

  return {
    id: `commitment_${source.system}_${source.createdAt.getTime()}`,
    sourceSystem: source.system,
    sourceUrl: source.url,
    rawText: source.text,
    candidateOwnerHandle: ownerHandle,
    candidateDeadlineText: deadlineText,
    candidateJiraKey: jiraKey,
    candidateRepo: repo,
    confidence: ownerHandle && (deadlineText || jiraKey) ? "high" : "medium",
    createdAt: source.createdAt
  };
}

export function commitmentToActionItem(commitment: Commitment, context: ExtractionContext): ActionItem {
  const owner = commitment.candidateOwnerHandle
    ? findPersonByHandle(context.people, commitment.candidateOwnerHandle)
    : null;
  const deadline = resolveDeadline(commitment.candidateDeadlineText ?? "", context.now, context.calendarEvents);

  return {
    id: `action_${commitment.id}`,
    title: summarizeTaskTitle(commitment.rawText),
    description: commitment.rawText,
    status: "candidate_commitment",
    owner,
    source: {
      system: commitment.sourceSystem,
      url: commitment.sourceUrl,
      channelId: null,
      messageTs: null,
      meetingId: null
    },
    jira: {
      key: commitment.candidateJiraKey,
      url: commitment.candidateJiraKey ? `https://jira.example.com/browse/${commitment.candidateJiraKey}` : null
    },
    deadline: {
      resolvedAt: deadline.resolvedAt,
      originalText: deadline.originalText,
      confidence: deadline.confidence
    },
    expectedArtifact: {
      type: "github_pr",
      repo: commitment.candidateRepo ?? context.defaultRepo
    },
    matchedPrIds: [],
    createdAt: commitment.createdAt,
    updatedAt: commitment.createdAt,
    lastCheckedAt: null,
    nextFollowUpAt: null
  };
}

function extractOwnerHandle(text: string): string | null {
  const mention = text.match(/@([a-zA-Z0-9_.-]+)/);
  if (mention?.[1]) return mention[1];

  const assignment = text.match(/\b([A-Z][a-z]+)\s+(?:to|will|should|can)\b/);
  return assignment?.[1] ?? null;
}

function findPersonByHandle(people: Person[], handle: string): Person | null {
  const normalized = handle.toLowerCase();
  return (
    people.find((person) => {
      return (
        person.displayName.toLowerCase() === normalized ||
        person.githubUsername?.toLowerCase() === normalized ||
        person.aliases.some((alias) => alias.toLowerCase() === normalized)
      );
    }) ?? null
  );
}

function hasEngineeringVerb(text: string): boolean {
  return /\b(add|fix|update|ship|implement|open|merge|review|wire|refactor|build|remove)\b/i.test(text);
}

function cleanDeadlineText(text: string | null): string | null {
  if (!text) return null;
  return (
    text
      .replace(jiraKeyPattern, "")
      .replace(repoPattern, "")
      .replace(/\s+/g, " ")
      .trim() || null
  );
}

function summarizeTaskTitle(text: string): string {
  const cleaned = text
    .replace(/https?:\/\/\S+/g, "")
    .replace(/@[a-zA-Z0-9_.-]+/g, "")
    .replace(jiraKeyPattern, "")
    .replace(/\s+/g, " ")
    .trim();

  const withoutDeadline = cleaned.split(/\b(?:before|by|ahead of)\b/i)[0]?.trim() ?? cleaned;
  return withoutDeadline.replace(/^(can you|please|to)\s+/i, "").trim() || "Untitled engineering action item";
}
