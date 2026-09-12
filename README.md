# SWEwatchdog

SWEwatchdog is a Python-first Slack bot for engineering work that gets stuck between a commitment, a pull request, and a review.

The product lives in Slack. It uses Slack Socket Mode, so it connects directly to Slack without a webpage, public URL, or tunnel.

## What The Bot Does

- `@SWEwatchdog @owner fix the auth redirect before tomorrow` becomes a tracked engineering action item.
- `/watchdog-action-items 5` shows a private action-item snapshot.
- `/watchdog-follow-up <task-id-or-title>` DMs the owner or pending reviewer when the watchdog finds a follow-up is due.
- GitHub provides pull-request, review, and merge evidence. Slack handles the human loop-closing.

## Fast Start

1. Import [slack-manifest.json](slack-manifest.json) into a new Slack app.
2. Generate an `xapp-...` app token with `connections:write` and install the app to your workspace to get an `xoxb-...` bot token.
3. Set `SLACK_APP_TOKEN` and `SLACK_BOT_TOKEN` in your shell.
4. Run:

```bash
python3 -m swewatchdog.cli --db data/swewatchdog.db init-db
python3 -m swewatchdog.cli --db data/swewatchdog.db watch-repo Rishikesh427/ClimateGuard
python3 -m swewatchdog.cli --db data/swewatchdog.db slack-bot
```

Then invite `@SWEwatchdog` to a test channel and use the commands there.

## Documentation

- [Submission setup: Slack Socket Mode](docs/slack-github-mvp.md)
- [Current product context](docs/context.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
