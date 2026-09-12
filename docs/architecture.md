# SWEwatchdog Product Architecture

SWEwatchdog is the working project and repository title until a stronger product name is chosen.

## Architecture Goal

The first version should prove the product loop before it invests in heavy integrations:

```text
Slack / Granola / Jira mention / Calendar context
        ->
Normalized engineering action item
        ->
GitHub PR expectation and matching
        ->
Review and merge monitoring
        ->
Targeted follow-up
```

The backend should be Python-first because it is easier for the product owner to work with directly. TypeScript may still be useful later for a web UI, but the core backend, persistence, orchestration, and integration logic should live in Python unless there is a specific reason to change.

It can later become an API server, background worker, Slack app, GitHub app, or hosted agent without rewriting the domain model.

## Module Boundaries

```text
swewatchdog/domain.py
  Core entities, states, and transition rules.

swewatchdog/intelligence.py
  Matching and deadline-resolution logic. This is where LLM-backed extraction can plug in later.

swewatchdog/monitoring.py
  Decision rules that decide who should be reminded, when, and why.

swewatchdog/integrations.py
  Connector interfaces for Slack, Granola, Calendar, GitHub, Jira, and outbound messaging.

swewatchdog/storage.py
  SQLite persistence for the local MVP.

swewatchdog/app.py
  Orchestration use cases that combine domain, intelligence, monitoring, and integrations.
```

## First Implementation Slice

The initial code intentionally avoids live API calls. It defines:

- Action item and PR schemas.
- The state machine for action item lifecycle transitions.
- Calendar deadline resolution for common software team phrases.
- PR/action-item matching score.
- Monitoring rules for missing PRs, overdue reviews, changes requested, approved-but-unmerged PRs, and closed-without-merge PRs.
- Tests that validate the core product behavior.
- SQLite storage and fixture ingestion so the product loop can run locally before OAuth setup.

## Near-Term Runtime Shape

The next practical step is a local worker with adapters:

```text
Polling scheduler
  -> fetch recent Slack/Granola/GitHub/Calendar events
  -> normalize commitments
  -> upsert action items
  -> match PRs
  -> evaluate monitoring decisions
  -> draft or send follow-ups
```

## Persistence

Start with a simple repository interface. Back it with SQLite or Postgres once the domain loop is stable.

Important tables later:

- `people`
- `commitments`
- `action_items`
- `pull_requests`
- `follow_ups`
- `integration_events`
- `identity_mappings`

## Integration Strategy

Use connectors behind interfaces so the domain logic can be tested without network calls.

- Slack connector: fetch channel/thread messages, resolve users, send DMs or channel replies.
- Granola connector: fetch meeting notes and action items.
- Calendar connector: find next feature presentation, standup, sprint review, or demo.
- GitHub connector: fetch PRs, reviews, reviewers, checks, merge status, and user emails when available.
- Jira connector: parse and enrich ticket references.
- Messaging connector: choose Slack, email, or GitHub comment according to policy.

## Account And OAuth Architecture

The final product should have first-party SWEwatchdog accounts with email magic-link login.

Recommended auth model:

- User enters email.
- SWEwatchdog sends a one-time magic link.
- Magic link creates a secure session.
- User connects integrations through OAuth.
- OAuth tokens are scoped by user and workspace.
- Integration connection state is separate from action item state.

OAuth integrations to support:

- Slack for source messages and follow-ups.
- GitHub for PRs, reviewers, reviews, merge state, and account identity.
- Calendar for standups, feature presentations, demos, and sprint reviews.
- Jira for ticket enrichment.
- Granola for meeting notes and action items.
- Email or workspace messaging for reviewer follow-up when Slack identity is missing.

The agent must preserve a clear permissions distinction between drafting follow-ups and sending them automatically.

## MVP Guardrails

- Only track engineering action items expected to result in GitHub PRs.
- Ask for clarification when owner, deadline, repo, or PR match is low confidence.
- Do not auto-escalate low-confidence items.
- Do not auto-create PRs.
- Do not auto-merge PRs.
- Keep every decision traceable to source evidence.
