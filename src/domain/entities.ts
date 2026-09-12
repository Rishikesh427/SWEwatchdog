import { z } from "zod";

export const ConfidenceSchema = z.enum(["high", "medium", "low"]);
export type Confidence = z.infer<typeof ConfidenceSchema>;

export const ActionItemStatusSchema = z.enum([
  "candidate_commitment",
  "needs_clarification",
  "awaiting_pr",
  "pr_detected",
  "awaiting_review",
  "changes_requested",
  "approved",
  "awaiting_merge",
  "done",
  "cancelled",
  "not_pr_work",
  "closed_without_merge",
  "expired",
  "blocked",
  "ambiguous_owner",
  "ambiguous_deadline",
  "ambiguous_repo",
  "missing_pr_overdue",
  "review_overdue",
  "stale_pr"
]);
export type ActionItemStatus = z.infer<typeof ActionItemStatusSchema>;

export const PersonSchema = z.object({
  id: z.string(),
  displayName: z.string(),
  slackUserId: z.string().nullable().default(null),
  githubUsername: z.string().nullable().default(null),
  githubAccountEmail: z.string().email().nullable().default(null),
  workEmail: z.string().email().nullable().default(null),
  calendarUserId: z.string().nullable().default(null),
  aliases: z.array(z.string()).default([])
});
export type Person = z.infer<typeof PersonSchema>;

export const ActionItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().default(""),
  status: ActionItemStatusSchema,
  owner: PersonSchema.nullable(),
  source: z.object({
    system: z.enum(["slack", "granola", "jira", "manual"]),
    url: z.string().url().nullable().default(null),
    channelId: z.string().nullable().default(null),
    messageTs: z.string().nullable().default(null),
    meetingId: z.string().nullable().default(null)
  }),
  jira: z.object({
    key: z.string().nullable().default(null),
    url: z.string().url().nullable().default(null)
  }),
  deadline: z.object({
    resolvedAt: z.date().nullable(),
    originalText: z.string().nullable(),
    confidence: ConfidenceSchema
  }),
  expectedArtifact: z.object({
    type: z.literal("github_pr"),
    repo: z.string().nullable().default(null)
  }),
  matchedPrIds: z.array(z.string()).default([]),
  createdAt: z.date(),
  updatedAt: z.date(),
  lastCheckedAt: z.date().nullable().default(null),
  nextFollowUpAt: z.date().nullable().default(null)
});
export type ActionItem = z.infer<typeof ActionItemSchema>;

export const CommitmentSchema = z.object({
  id: z.string(),
  sourceSystem: z.enum(["slack", "granola"]),
  sourceUrl: z.string().url(),
  rawText: z.string(),
  candidateOwnerHandle: z.string().nullable().default(null),
  candidateDeadlineText: z.string().nullable().default(null),
  candidateJiraKey: z.string().nullable().default(null),
  candidateRepo: z.string().nullable().default(null),
  confidence: ConfidenceSchema,
  createdAt: z.date()
});
export type Commitment = z.infer<typeof CommitmentSchema>;

export const PullRequestSchema = z.object({
  id: z.string(),
  githubPrNumber: z.number().int().positive(),
  repo: z.string(),
  url: z.string().url(),
  title: z.string(),
  description: z.string().default(""),
  author: PersonSchema,
  status: z.enum(["open", "merged", "closed"]),
  reviewStatus: z.enum([
    "no_review_requested",
    "review_requested",
    "approved",
    "changes_requested",
    "rejected",
    "stale"
  ]),
  reviewers: z.array(
    z.object({
      person: PersonSchema,
      status: z.enum(["pending", "approved", "changes_requested", "commented", "dismissed"])
    })
  ),
  createdAt: z.date(),
  updatedAt: z.date(),
  mergedAt: z.date().nullable().default(null),
  closedAt: z.date().nullable().default(null),
  linkedActionItemIds: z.array(z.string()).default([])
});
export type PullRequest = z.infer<typeof PullRequestSchema>;

export const FollowUpReasonSchema = z.enum([
  "missing_pr",
  "overdue_review",
  "changes_requested",
  "awaiting_merge",
  "ambiguity",
  "stale_pr",
  "closed_without_merge"
]);
export type FollowUpReason = z.infer<typeof FollowUpReasonSchema>;

export const FollowUpChannelSchema = z.enum(["slack_dm", "slack_channel", "email", "github_comment"]);
export type FollowUpChannel = z.infer<typeof FollowUpChannelSchema>;

export interface FollowUpDecision {
  actionItemId: string;
  pullRequestId: string | null;
  recipient: Person | null;
  channel: FollowUpChannel | "needs_identity_mapping";
  reason: FollowUpReason;
  urgency: "normal" | "urgent" | "escalate";
  message: string;
}
