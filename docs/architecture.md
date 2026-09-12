# SWEwatchdog Architecture

## Runtime Flow

```text
Slack Socket Mode WebSocket
  -> Bolt command or app_mention handler
  -> action-item capture or status command
  -> SQLite state
  -> GitHub pull-request and review evidence
  -> matching and monitoring rules
  -> Slack direct-message follow-up
```

There is no HTTP callback server or browser product requirement. The running process is:

```bash
python3 -m swewatchdog.cli --db data/swewatchdog.db slack-bot
```

## Key Modules

```text
swewatchdog/slack_socket.py
  Slack Bolt Socket Mode runtime with command and event listeners.

swewatchdog/slack_bot.py
  Command behavior, bot-mention ingestion, summaries, and follow-up delivery.

swewatchdog/slack.py
  Slack Web API client for direct messages.

swewatchdog/github.py
  Read-only GitHub REST client for PRs and review state.

swewatchdog/ingestion.py
  Normalizes Slack commitments into action items.

swewatchdog/intelligence.py
  Scores action-item to pull-request matches.

swewatchdog/monitoring.py
  Determines whether missing PRs and stalled reviews need follow-up.

swewatchdog/storage.py
  SQLite persistence for people, action items, pull requests, events, and follow-ups.
```

## Credentials

- `SLACK_BOT_TOKEN` is the installed Slack app's `xoxb-...` bot token.
- `SLACK_APP_TOKEN` is the `xapp-...` app-level Socket Mode token with `connections:write`.
- GitHub authentication comes from `GITHUB_TOKEN` or the local GitHub CLI.

## Intentional MVP Limit

GitHub state is currently refreshed on demand. A scheduler or GitHub webhooks are the next reliability step, but the Slack bot itself is now the actual product surface.
