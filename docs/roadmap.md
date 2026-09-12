# SWEwatchdog Implementation Roadmap

SWEwatchdog is the working project and repo title. Most backend work should be Python-first.

## Current Foundation

The repo now has a tested local core:

- Domain entities for people, commitments, action items, PRs, and follow-up decisions.
- Deadline resolution for common engineering calendar phrases.
- Commitment extraction from simple Slack/Granola-style text.
- PR matching by Jira key, owner, repo, source link, semantic overlap, and timing.
- Monitoring decisions for missing PRs, overdue reviews, requested changes, approved-but-unmerged PRs, and closed-without-merge PRs.
- Ports for future integrations.
- Local demo runner.

## Next Build Step

Build the local persistence and event ingestion layer. This is now underway in Python.

Recommended shape:

```text
SQLite store
  -> people
  -> commitments
  -> action_items
  -> pull_requests
  -> follow_ups
  -> integration_events
```

Then add offline ingestion commands:

```text
python3 -m swewatchdog.cli ingest fixtures/slack-message.json
python3 -m swewatchdog.cli ingest fixtures/granola-note.json
python3 -m swewatchdog.cli ingest fixtures/github-pr.json
```

This keeps progress fast before real OAuth/app setup.

## Milestone 1: Local Agent Loop

Goal: prove the loop on local fixture files.

- Add SQLite persistence.
- Add fixture-driven ingestion.
- Add idempotent upserts for events and action items. Current fixture ingestion now records stable integration events and skips duplicate source payloads.
- Add a `watchdog evaluate` command that prints follow-up drafts.
- Add tests for duplicate events, ambiguous owners, ambiguous repos, and multiple PR candidates.
- Keep account and integration connection records in the local schema, even before full magic-link/OAuth flows exist.

## Milestone 1.5: Local Connector Simulator

Goal: make local fixtures behave like polling integrations.

- Add a command that ingests every fixture in a directory. Current CLI includes `ingest-dir`.
- Add integration cursors for last-seen event time per provider. Current SQLite store tracks provider cursors.
- Add duplicate follow-up suppression so evaluation does not repeatedly create the same reminder. Current storage now uses stable follow-up signatures.
- Add a simple text summary command for open loops. Current CLI includes `summary`.

## Milestone 2: GitHub Read Integration

Goal: treat GitHub as the first real execution/evidence layer.

- Add GitHub connector implementation.
- Fetch PRs by repo and updated time.
- Fetch review requests and review states.
- Fetch PR author and reviewer identities.
- Match PRs to open action items.
- Keep sending disabled; only draft follow-ups.

## Milestone 2.5: SWEwatchdog Accounts And OAuth

Goal: introduce account and integration connection foundations.

- Add email magic-link login for SWEwatchdog accounts.
- Expand the existing integration connection records per user/workspace.
- Add OAuth flow skeletons for Slack, GitHub, Calendar, Jira, Granola, and email/messaging.
- Store encrypted integration tokens.
- Track requested scopes and connection health.
- Keep all external follow-ups draft-only until permissions are explicit.

## Milestone 3: Slack Read And Draft Integration

Goal: convert Slack commitments into action items.

- Read selected channels and threads.
- Extract `@mentions`, Jira keys, deadline phrases, and repo hints.
- Resolve Slack users to internal people records.
- Draft Slack follow-ups for missing PRs and overdue review.
- Require explicit confirmation before sending.

## Milestone 4: Calendar And Granola

Goal: improve task and deadline quality.

- Resolve feature presentations, standups, sprint reviews, and demos from Calendar.
- Ingest Granola notes as meeting action item sources.
- Attach meeting source links to action items.
- Add ambiguity prompts for multiple possible calendar matches.

## Milestone 5: Controlled Autopilot

Goal: send low-risk follow-ups automatically.

- Enable opt-in sending for high-confidence missing-PR reminders.
- Enable opt-in reviewer reminders after the configured grace period.
- Keep escalations draft-only until team policy is explicit.
- Add audit logs for every generated and sent follow-up.

## Product Principle

Do not optimize for more tasks. Optimize for fewer unclosed engineering loops.
