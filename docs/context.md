# SWEwatchdog Current Context

## Product Decision

SWEwatchdog is a Slack bot. There is no user-facing website in the MVP. The bot runs locally through Slack Socket Mode and connects to Slack over a WebSocket.

## Mission

Turn a Slack engineering commitment into an action item, find the GitHub pull request that proves the work is moving, and close the loop in Slack when the work stalls.

## Slack Experience

A team member mentions the bot with a concrete commitment:

```text
@SWEwatchdog @rishikesh fix the auth redirect before tomorrow
```

When one GitHub repository is watched, the bot uses it as the expected PR destination. It stores the action item, matches GitHub PR evidence later, and detects missing PRs or overdue review.

```text
/watchdog-action-items 5
/watchdog-follow-up <task-id-or-title>
```

The first command is private to the requester. The second sends a direct Slack message only when a monitoring rule identifies a due follow-up.

## Scope

In scope:

- Slack Socket Mode, bot mentions, slash commands, and direct-message follow-ups.
- GitHub PR, review, and merge evidence.
- SQLite persistence, deterministic matching, and monitoring rules.

Out of scope:

- A browser product surface.
- Calendar, Jira, Granola, email, and broader task management.
- Automatic PR creation, approval, merge, or rejection.
- Hosted deployment, multi-workspace tenancy, and first-party user accounts.

## Product Rule

A task is not complete because it was discussed. GitHub provides execution evidence; Slack provides the human follow-through.
