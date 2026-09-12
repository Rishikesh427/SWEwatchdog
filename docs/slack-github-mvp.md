# Submit In 10 Minutes: Run The Slack Bot

SWEwatchdog runs as a real Slack Socket Mode bot. It does not need a website, public URL, or tunnel.

## 1. Import The Manifest

1. Open `https://api.slack.com/apps`.
2. Select **Create New App** then **From an app manifest**.
3. Pick your workspace.
4. Copy the contents of [slack-manifest.json](../slack-manifest.json) into the manifest editor and create the app.

The manifest creates the bot, enables Socket Mode, subscribes to `app_mention`, adds both slash commands, and requests the minimum bot scopes.

## 2. Get Two Tokens

1. In **Basic Information**, go to **App-Level Tokens**.
2. Create a token named `local-development` with the `connections:write` scope. Copy its `xapp-...` value.
3. In **OAuth & Permissions**, select **Install to Workspace**. Copy the Bot User OAuth Token, which starts with `xoxb-`.
4. In **Socket Mode**, make sure Socket Mode is enabled.

## 3. Start The Bot

In a terminal at the project folder:

```bash
export SLACK_APP_TOKEN='xapp-your-token'
export SLACK_BOT_TOKEN='xoxb-your-token'
python3 -m swewatchdog.cli --db data/swewatchdog.db init-db
python3 -m swewatchdog.cli --db data/swewatchdog.db watch-repo Rishikesh427/ClimateGuard
python3 -m swewatchdog.cli --db data/swewatchdog.db slack-bot
```

Keep that terminal open. The process prints that it is connected through Socket Mode.

## 4. Demo It In Slack

Invite the app to a test channel, then try:

```text
@SWEwatchdog @your-name fix the auth redirect before tomorrow
/watchdog-action-items 5
```

The mention should receive a confirmation message. The slash command should show the action item privately. Use the task id from that response with:

```text
/watchdog-follow-up <task-id>
```

## GitHub

The bot uses your existing `gh auth login` session or `GITHUB_TOKEN` to read pull requests. For the demo, the selected repository is `Rishikesh427/ClimateGuard`.

## If It Does Not Start

- Missing `xapp-...`: create the app-level token with `connections:write`.
- Missing `xoxb-...`: install the app to the workspace.
- Command not visible: reinstall the app after manifest changes.
- Bot does not receive mentions: invite it to the channel first.

Official Slack references: [Socket Mode](https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/), [Bolt for Python quickstart](https://docs.slack.dev/tools/bolt-python/getting-started), and [app mentions](https://docs.slack.dev/reference/events/app_mention/).
