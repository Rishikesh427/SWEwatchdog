# SWEwatchdog: Software Engineering Execution Watchdog Agent

`SWEwatchdog` is the working project and repository title until a better name is chosen. The backend should be Python-first so the product owner can work with it comfortably; TypeScript can be introduced later where it is useful, especially for a web UI.

## Mission

Build a software-engineering execution watchdog that turns conversational commitments into tracked engineering action items, watches whether those items become GitHub pull requests on time, monitors review progress, and automatically follows up with the right person when the execution loop stalls.

The agent is not a general productivity assistant. Its first job is narrower and sharper:

> Detect engineering work that should result in a GitHub pull request, track it across Slack, Granola notes, Calendar, and GitHub, and close the loop when the work is missing, blocked, overdue, reviewed, rejected, approved, merged, or abandoned.

## Problem

Engineering work is often assigned outside the formal issue tracker:

- A teammate tags an engineer in Slack and asks them to make a change.
- A Jira ticket is pasted into a channel with an implicit owner and due date.
- A meeting produces action items in Granola notes.
- A feature presentation or standup creates a real deadline, even if nobody writes the date into the ticket.
- A pull request gets opened, but the reviewer does not approve or reject it before the next planning checkpoint.

The execution gap is not that teams lack tools. It is that responsibility, deadlines, and evidence of completion are spread across different systems.

This agent reconstructs the execution state continuously:

> What was someone supposed to do? Who owns it? By when? What GitHub evidence proves progress? Who needs to act next?

## Core Workflow

```text
Slack / Granola / Jira reference / Calendar context
        ->
Engineering action item with owner and timeframe
        ->
Expected GitHub pull request
        ->
Pull request opened and matched to action item
        ->
Review requested
        ->
Approved, rejected, changes requested, merged, closed, or stalled
        ->
Automatic follow-up to owner, reviewer, or escalation target
```

## Supported Environments

### Slack

Slack is the primary conversational source for engineering commitments.

The agent should extract action items from:

- Direct `@mentions` assigning work.
- Requests that imply ownership.
- Jira ticket references pasted into conversations.
- Commitments made by engineers, such as "I'll get this done before demo."
- Follow-up language, such as "Can you open a PR for this by tomorrow?"
- Channel context, such as project channel, team channel, incident channel, or launch channel.

### Granola Notes

Granola notes are the meeting-memory layer.

The agent should extract:

- Explicit meeting action items.
- Owners.
- Deadlines.
- Feature presentation or standup references.
- Decisions that imply implementation work.
- Follow-up items expected to become code changes.

Granola-derived items should enter the same action item lifecycle as Slack-derived commitments.

### Calendar

Calendar provides deadline context.

The agent should use calendar events to resolve relative deadlines such as:

- "Before the feature presentation."
- "By next standup."
- "Before demo."
- "Ahead of sprint review."
- "Before launch sync."

Calendar should not be treated as a source of tasks in the MVP unless a calendar event contains explicit action items. Its main MVP function is deadline resolution and escalation context.

### GitHub

GitHub is the critical execution and evidence layer.

The agent should monitor:

- Pull requests opened by action item owners.
- PR titles, descriptions, branches, commits, linked issues, and comments.
- Requested reviewers.
- Review status: pending, approved, changes requested, rejected, dismissed, or stale.
- Merge status.
- Closed-without-merge status.
- PR activity recency.

GitHub is the source of objective progress evidence. An action item is not considered execution-confirmed until a matching PR or explicit non-PR resolution is found.

### Jira

Jira is an input signal, especially when referenced in Slack or Granola.

For the MVP, Jira does not need to be a full execution system. The agent should recognize Jira ticket keys and URLs, attach them to action items, and use them for matching PRs when PR titles or descriptions reference the ticket.

## Account And Integration Authentication

The final product should support SWEwatchdog accounts with email magic-link login.

Required account behavior:

- A user enters their email address.
- SWEwatchdog sends a one-time magic link.
- Opening the link creates an authenticated SWEwatchdog session.
- The user can then connect integrations through OAuth.

Required OAuth integrations:

- Slack.
- GitHub.
- Calendar.
- Jira.
- Granola.
- Email or workspace messaging provider for reviewer follow-up when Slack identity is unavailable.

Auth and integration requirements:

- Store account identity separately from integration identity.
- Store OAuth tokens per user and workspace.
- Track scopes granted by each integration.
- Track whether each integration is connected, expired, revoked, or unhealthy.
- Make the permission boundary explicit: draft-only, send reminders, or escalate.
- Never send automated follow-ups until the user or workspace has explicitly enabled that behavior.

## Identity Resolution

The agent needs a reliable identity map across Slack, GitHub, calendar, email, and notes.

Recommended identity fields:

```yaml
Person:
  id: string
  display_name: string
  slack_user_id: string | null
  github_username: string | null
  github_account_email: string | null
  work_email: string | null
  calendar_user_id: string | null
  aliases:
    - string
```

Identity resolution is required for two critical loops:

- Mapping a Slack or Granola owner to the GitHub user expected to open the PR.
- Mapping a GitHub reviewer to the Slack or email identity the agent should contact when review is overdue.

Reviewer follow-up should prefer Slack DM when the GitHub reviewer maps confidently to a Slack user. If Slack mapping is missing, the agent should use the reviewer's GitHub account email or work email, depending on what is available and permitted by workspace policy.

The agent should not send reviewer follow-ups when identity confidence is low. In that case, it should ask for a one-time mapping confirmation, such as:

```text
I need to follow up with GitHub reviewer @alexk for PR #184, but I do not have a confident Slack or email mapping. Is Alex Kim the right person?
```

## Primary Users

### Engineering Manager

Wants to know whether committed engineering work is actually moving through implementation and review before team rituals or delivery deadlines.

### Tech Lead

Wants to make sure engineers open PRs on time and reviewers respond before work gets blocked.

### Project Manager

Wants a reliable execution view across meetings, Slack, Jira references, and GitHub without manually reconciling all systems.

### Individual Engineer

Wants reminders about commitments they made or reviews they owe without maintaining a separate manual todo list.

## Entities And Data Model

### ActionItem

Represents a piece of engineering work expected to result in a GitHub PR.

Recommended fields:

```yaml
id: string
title: string
description: string
status: ActionItemStatus
owner:
  name: string
  slack_user_id: string | null
  github_username: string | null
  email: string | null
source:
  system: slack | granola | jira | manual
  url: string | null
  channel_id: string | null
  message_ts: string | null
  meeting_id: string | null
jira:
  key: string | null
  url: string | null
deadline:
  resolved_at: datetime | null
  original_text: string | null
  confidence: high | medium | low
expected_artifact:
  type: github_pr
  repo: string | null
matched_prs:
  - PullRequest.id
created_at: datetime
updated_at: datetime
last_checked_at: datetime | null
next_follow_up_at: datetime | null
```

### PullRequest

Represents GitHub evidence for an action item.

Recommended fields:

```yaml
id: string
github_pr_number: integer
repo: string
url: string
title: string
description: string
author:
  github_username: string
  email: string | null
status: open | merged | closed
review_status: no_review_requested | review_requested | approved | changes_requested | rejected | stale
reviewers:
  - github_username: string
    email: string | null
    status: pending | approved | changes_requested | commented | dismissed
created_at: datetime
updated_at: datetime
merged_at: datetime | null
closed_at: datetime | null
linked_action_items:
  - ActionItem.id
```

### Commitment

Represents a raw extracted promise, request, or assignment before it is normalized into an action item.

Recommended fields:

```yaml
id: string
source_system: slack | granola
source_url: string
raw_text: string
candidate_owner: string | null
candidate_deadline_text: string | null
candidate_jira_key: string | null
candidate_repo: string | null
confidence: high | medium | low
created_at: datetime
```

### FollowUp

Represents an outbound reminder, clarification, escalation, or status request.

Recommended fields:

```yaml
id: string
action_item_id: string
pull_request_id: string | null
recipient:
  slack_user_id: string | null
  github_username: string | null
  email: string | null
channel: slack_dm | slack_channel | email | github_comment
reason: missing_pr | overdue_review | changes_requested | awaiting_merge | ambiguity | stale_pr | closed_without_merge
message: string
sent_at: datetime | null
status: drafted | sent | skipped | failed
```

## Lifecycle And State Machine

### Action Item States

```text
candidate_commitment
    ->
needs_clarification
    ->
awaiting_pr
    ->
pr_detected
    ->
awaiting_review
    ->
changes_requested
    ->
approved
    ->
awaiting_merge
    ->
done
```

Terminal states:

```text
done
cancelled
not_pr_work
closed_without_merge
expired
```

Exceptional states:

```text
blocked
ambiguous_owner
ambiguous_deadline
ambiguous_repo
missing_pr_overdue
review_overdue
stale_pr
```

### State Definitions

| State | Meaning | Next Agent Action |
|---|---|---|
| `candidate_commitment` | A possible engineering task was detected. | Validate owner, deadline, expected artifact, and confidence. |
| `needs_clarification` | The item is likely real but missing owner, deadline, or repo. | Ask the relevant person or channel a focused clarification question. |
| `awaiting_pr` | A valid action item exists and no matching PR has been found. | Monitor GitHub and remind owner before or after deadline. |
| `pr_detected` | A likely matching PR has been found. | Confirm match and transition to review monitoring. |
| `awaiting_review` | PR exists and review is needed. | Watch reviewer response time. |
| `changes_requested` | Reviewer requested changes. | Remind owner if no update occurs within the configured window. |
| `approved` | PR has approval. | Watch for merge or closure. |
| `awaiting_merge` | PR is approved but not merged. | Remind owner or maintainer if merge stalls. |
| `done` | PR is merged or action item is otherwise resolved. | Close the loop quietly or post a completion note if useful. |

## Deadline Resolution

The agent must convert conversational deadlines into concrete timestamps.

### Deadline Sources

Priority order:

1. Explicit timestamp in the message or note.
2. Explicit date without time, using team default end-of-workday.
3. Relative phrase tied to Calendar, such as "before next feature presentation."
4. Relative phrase tied to team ritual, such as "by standup."
5. Project/channel default SLA.
6. User or team fallback default.

### Calendar-Based Resolution

Examples:

| Phrase | Resolution |
|---|---|
| "before the feature presentation" | Start time of the next calendar event matching feature presentation/demo keywords. |
| "by next standup" | Start time of the next standup event for the relevant team calendar. |
| "before sprint review" | Start time of the next sprint review event. |
| "by EOD" | Team-local end-of-day for the message date. |
| "tomorrow" | Team-local next business day unless context indicates otherwise. |

### Deadline Confidence

The agent should attach confidence to every resolved deadline.

- `high`: explicit date/time or clear calendar match.
- `medium`: relative date resolved from a likely calendar event.
- `low`: inferred from project defaults or ambiguous phrasing.

Low-confidence deadlines should trigger clarification before enforcement.

## Cross-System Matching

The central intelligence of the agent is matching conversational commitments to GitHub PRs.

### Matching Signals

Strong signals:

- Jira key appears in both action item and PR title/body.
- Slack thread URL or meeting note URL is linked in PR body.
- PR author matches action item owner.
- Repository is explicitly named in the source commitment.
- Branch name contains Jira key or normalized task phrase.

Medium signals:

- PR title semantically matches action item title.
- PR description references the same feature, endpoint, bug, or component.
- PR opened by owner near the expected timeframe.
- Commit messages reference similar language.

Weak signals:

- Same owner opened any PR near the deadline.
- Same repo had PR activity around the relevant time.
- Similar words appear in PR title but no owner or Jira match.

### Matching Behavior

- Auto-match when confidence is high.
- Suggest a match when confidence is medium.
- Ask for clarification when multiple candidate PRs are plausible.
- Do not mark an action item as complete based only on weak matching.
- Preserve source links so humans can audit why a match was made.

### Suggested Match Score

```text
Jira key match: +45
Owner/author match: +20
Repo match: +15
Semantic title/body match: +15
Temporal proximity: +10
Slack/Granola source link in PR: +30
Conflicting owner: -30
Closed unrelated PR: -20
```

Suggested thresholds:

- `>= 70`: auto-match.
- `45-69`: tentative match, ask or display for confirmation.
- `< 45`: do not match.

## Monitoring Rules

### Awaiting PR

When an action item is expected to result in a PR:

- Check GitHub for matching PRs on a schedule.
- Increase check frequency as deadline approaches.
- Remind the owner before the deadline if no PR exists.
- Remind the owner after the deadline if no PR exists.
- Include source context and the original commitment in the reminder.

Recommended default:

```text
First reminder: halfway between creation time and deadline, if no PR exists.
Urgent reminder: 2 hours before deadline, if no PR exists.
Overdue reminder: at deadline + 15 minutes, if no PR exists.
Escalation: deadline + configured team grace period.
```

### Awaiting Review

When a PR exists and review is requested:

- Track requested reviewers.
- Detect whether review has been approved, rejected, commented, or changes requested.
- Follow up with reviewers when review is overdue.
- Prefer Slack DM when reviewer identity maps cleanly to Slack.
- Use email when reviewer is not reachable by Slack or the user specifically configured email follow-up.
- Use GitHub comment only when team policy allows it.

Recommended default:

```text
Initial reviewer follow-up: review requested + 24 business hours.
Urgent reviewer follow-up: 2 hours before the action item deadline.
Escalation: reviewer follow-up + configured team grace period.
```

### Changes Requested

When changes are requested:

- Transition the action item back to owner-needed work.
- Remind the PR author if there is no push, comment, or status update within the configured window.
- Keep the original deadline active unless reviewer feedback makes it impossible.

### Approved But Not Merged

When a PR is approved:

- Check whether required checks have passed.
- Check whether the PR is mergeable.
- Remind owner or maintainer if it remains approved but unmerged past the configured threshold.

### Closed Without Merge

When a PR is closed without merge:

- Do not automatically mark the action item done.
- Ask whether the action item was cancelled, moved, superseded, or completed elsewhere.
- If linked to a replacement PR, update the match.

## Follow-Up And Escalation Rules

### Follow-Up Principles

Follow-ups should be specific, low-friction, and grounded in evidence.

Each message should include:

- The task.
- The source context.
- The deadline or elapsed time.
- The current missing action.
- A direct link to the relevant Slack message, Granola note, Jira ticket, or PR.

The agent should avoid vague reminders like "Any update?" unless there is no richer context available.

### Owner Follow-Up For Missing PR

Example:

```text
Hey Rishikesh, you were assigned "Add authentication flow" from the #launch Slack thread, and it looks like the expected PR has not been opened yet. This is due before the feature presentation today at 2:00 PM.

Can you open the PR or reply if this is no longer expected to ship?
```

### Reviewer Follow-Up For Overdue Review

Example:

```text
Hey Alex, PR #184 for "Add authentication flow" is waiting on your review and is tied to work due before today's feature presentation at 2:00 PM.

Could you approve, request changes, or reject it when you get a chance?
```

### Owner Follow-Up After Changes Requested

Example:

```text
Hey Maya, Jordan requested changes on PR #231 yesterday, and there has not been a new push or comment since then. This action item is still due before tomorrow's standup.

Can you update the PR or note if the task is blocked?
```

### Escalation

Escalation should be configurable and conservative.

Escalate only when:

- A critical deadline is at risk.
- The owner or reviewer has already received a direct follow-up.
- The item remains unresolved after the configured grace period.
- The agent has high confidence in the task, owner, and deadline.

Possible escalation targets:

- Engineering manager.
- Tech lead.
- Project channel.
- Original requester.

Escalation example:

```text
Heads up: "Add authentication flow" is still awaiting reviewer action from Alex, and the feature presentation starts in 45 minutes. PR #184 is open and linked to the original Slack request.
```

## Ambiguity Handling

The agent should not over-enforce uncertain interpretations.

### Ambiguous Owner

If a task is detected but no owner is clear:

```text
Quick clarification: who owns the PR for "Add authentication flow" from this thread?
```

### Ambiguous Deadline

If the deadline is unclear:

```text
Quick clarification: when should the PR for "Add authentication flow" be opened by? I saw "before demo" but found multiple possible demo events.
```

### Ambiguous Repository

If the expected repo is unclear:

```text
Quick clarification: which GitHub repo should the PR for "Add authentication flow" land in?
```

### Ambiguous PR Match

If multiple PRs may correspond to the same action item:

```text
I found two possible PRs for "Add authentication flow": #184 in web-app and #91 in auth-service. Which one should I track?
```

## Agent Behavior

### What The Agent Should Do

- Extract only likely engineering execution commitments.
- Maintain traceability back to source messages, notes, tickets, and PRs.
- Resolve owners and deadlines before enforcing reminders.
- Treat GitHub PRs as execution evidence.
- Detect when the next required action belongs to the owner, reviewer, or maintainer.
- Message the responsible person with context-rich follow-ups.
- Close the loop when the PR is merged or otherwise resolved.
- Stay quiet when there is no meaningful change or required action.

### What The Agent Should Avoid

- Creating noisy todos for every casual mention.
- Treating general discussion as committed work.
- Marking work done without GitHub evidence or explicit human confirmation.
- Publicly escalating low-confidence items.
- Following up on reviewers before a reasonable review window has passed.
- Reassigning work without human confirmation.
- Acting as a full Jira replacement in the MVP.

## MVP Scope

The MVP should focus tightly on engineering action items expected to become GitHub PRs.

### In Scope

- Slack action item extraction from messages, threads, Jira links, and `@mentions`.
- Granola meeting-note action item extraction.
- Calendar-based deadline resolution for feature presentations, standups, demos, and sprint reviews.
- Normalized action item creation with owner, timeframe, source, and expected GitHub PR artifact.
- GitHub PR monitoring.
- PR/action item matching.
- Missing-PR reminders.
- Overdue-review reminders.
- Changes-requested follow-ups.
- Approved-but-unmerged follow-ups.
- Closed-without-merge clarification.
- Basic escalation after direct follow-ups fail.

### Out Of Scope For MVP

- Full Jira workflow automation.
- General personal todo management.
- Non-engineering tasks that do not result in GitHub PRs.
- Automatic code generation.
- Automatic PR creation on behalf of engineers.
- Automatic reviewer reassignment.
- Automatic merge decisions.
- Broad project management dashboards.
- Multi-month capacity planning.

## Expansion Model

The model should be designed to expand later without changing the core state machine.

Potential expansions:

- Jira as a first-class task source and status sink.
- Linear, Asana, or Shortcut integration.
- Support for non-PR artifacts such as design docs, migrations, runbooks, feature flags, or deployments.
- Risk summaries for engineering managers.
- Team-level execution dashboard.
- SLA customization by repo, team, project, or severity.
- Learning reviewer norms and preferred channels.
- Detecting decision reversals that invalidate existing action items.
- Release readiness reconstruction across many PRs.

## Concrete End-To-End Examples

### Example 1: Slack Mention To PR To Approval

Slack message:

```text
@Rishikesh can you add auth redirects before the feature presentation?
Jira: WEB-412
```

Calendar context:

```text
Feature Presentation - today at 2:00 PM
```

Created action item:

```yaml
title: Add auth redirects
owner: Rishikesh
jira_key: WEB-412
deadline: today 2:00 PM
expected_artifact: github_pr
status: awaiting_pr
source: Slack thread
```

GitHub event:

```text
PR #184 opened in web-app
Title: WEB-412 Add auth redirects
Author: rishikesh
Reviewer: alex
```

Agent transition:

```text
awaiting_pr -> pr_detected -> awaiting_review
```

Reviewer does not act within the review window.

Agent follow-up:

```text
Hey Alex, PR #184 for WEB-412 is waiting on your review and is tied to work due before today's feature presentation at 2:00 PM. Could you approve, request changes, or reject it?
```

Reviewer approves.

Agent transition:

```text
awaiting_review -> approved -> awaiting_merge
```

PR merges.

Agent transition:

```text
awaiting_merge -> done
```

### Example 2: Granola Meeting Action Item To Missing PR Reminder

Granola note:

```text
Maya to fix the onboarding empty state before next standup.
```

Calendar context:

```text
Engineering Standup - tomorrow at 10:00 AM
```

Created action item:

```yaml
title: Fix onboarding empty state
owner: Maya
deadline: tomorrow 10:00 AM
expected_artifact: github_pr
status: awaiting_pr
source: Granola meeting notes
```

No matching PR appears.

Agent reminder:

```text
Hey Maya, from today's meeting notes you own "Fix onboarding empty state," and I do not see a matching PR yet. This is due before tomorrow's 10:00 AM standup. Can you open the PR or reply if this is no longer expected to be code work?
```

### Example 3: Changes Requested And Owner Follow-Up

Slack commitment:

```text
Jordan: I'll update the billing webhook handling by Friday EOD.
```

GitHub match:

```text
PR #231: Update billing webhook handling
Reviewer: Priya
Review result: changes requested
```

No new push or comment occurs for 24 business hours.

Agent follow-up:

```text
Hey Jordan, Priya requested changes on PR #231 for "Update billing webhook handling," and I do not see a new push or comment since then. This is still due Friday EOD. Can you update the PR or note if it is blocked?
```

### Example 4: Closed PR Without Merge

Action item:

```text
Add audit logging for admin actions.
```

GitHub event:

```text
PR #302 closed without merge.
```

Agent behavior:

```text
Do not mark done.
Ask whether the work was cancelled, superseded, or moved to another PR.
```

Clarification message:

```text
PR #302 for "Add audit logging for admin actions" was closed without merge. Should I mark the action item cancelled, or is there a replacement PR I should track?
```

## Success Criteria

The MVP is successful if it can reliably answer:

- Which engineering commitments are currently awaiting PRs?
- Which action items have matching PRs?
- Which PRs are waiting on review?
- Which reviewers are overdue?
- Which approved PRs are not merged?
- Which commitments are at risk before the next feature presentation, standup, or demo?
- Who needs to be reminded, and why?

## Product Positioning

This is best positioned as an engineering execution loop closer, not a todo app.

The core promise:

> The agent watches the informal places where engineering work is committed, verifies whether that work appears in GitHub, and nudges the right person when the next step is missing.

The magic is not extracting tasks. The magic is connecting commitments to evidence.
