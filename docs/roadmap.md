# SWEwatchdog Roadmap

## Ready Now: Slack Bot MVP

- Socket Mode Slack bot with no public URL or dashboard requirement.
- `/watchdog-action-items` and `/watchdog-follow-up` commands.
- `app_mention` commitment capture and confirmation reply.
- GitHub PR and review matching.
- Targeted Slack DMs for due owner and reviewer follow-ups.
- Importable Slack app manifest.

## Next: Reliability

1. Run a scheduled GitHub sync for watched repositories.
2. Add GitHub webhooks for review and merge events.
3. Store Slack workspace and identity mappings explicitly.
4. Add an audit log and configurable reminder policy.

## Later: Productize

1. Replace local GitHub credentials with a GitHub App.
2. Persist encrypted Slack installations per workspace.
3. Add magic-link accounts and hosted deployment.

Calendar, Jira, Granola, email, and a web dashboard are explicitly deferred until this Slack-to-GitHub loop proves useful.
