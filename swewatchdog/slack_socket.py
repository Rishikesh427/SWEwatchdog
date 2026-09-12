from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from swewatchdog.slack_bot import SlackBot
from swewatchdog.storage import SQLiteStore


def build_socket_mode_app(
    store: SQLiteStore, bot_token: str | None = None, token_verification_enabled: bool = True
) -> App:
    """Build the real Slack application. Socket Mode supplies the transport."""
    token = bot_token or os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("Missing SLACK_BOT_TOKEN")

    app = App(token=token, token_verification_enabled=token_verification_enabled)
    watchdog = SlackBot(store)

    @app.command("/watchdog-action-items")
    def action_items(ack: Any, command: dict[str, Any]) -> None:
        response = watchdog.handle_command("/watchdog-action-items", command.get("text", ""))
        ack(response_type=response["response_type"], text=response["text"])

    @app.command("/watchdog-follow-up")
    def follow_up(ack: Any, command: dict[str, Any]) -> None:
        response = watchdog.handle_command("/watchdog-follow-up", command.get("text", ""))
        ack(response_type=response["response_type"], text=response["text"])

    @app.event("app_mention")
    def app_mention(event: dict[str, Any], say: Any) -> None:
        before = {item["id"] for item in store.list_action_items_raw()}
        watchdog.handle_event(
            {
                "type": "event_callback",
                "event_id": event.get("event_ts") or event.get("ts") or "slack-event",
                "event": event,
            }
        )
        created = [item for item in store.list_action_items_raw() if item["id"] not in before]
        if created:
            item_id = created[0]["id"].rsplit("_", 1)[-1]
            say(text=f"Tracking that as `{item_id}`. I will look for the matching GitHub PR and flag a stalled review.")
        else:
            say(text="I need an engineering task with an owner, a deadline, or a ticket reference to track it.")

    return app


def run_socket_bot(db_path: str | Path = "data/swewatchdog.db") -> None:
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN")
    missing = [name for name, value in (("SLACK_BOT_TOKEN", bot_token), ("SLACK_APP_TOKEN", app_token)) if not value]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)}. Add both values to your environment, then run slack-bot again.")

    store = SQLiteStore(db_path)
    store.init()
    app = build_socket_mode_app(store, bot_token=bot_token)
    print("SWEwatchdog Slack bot connected through Socket Mode")
    SocketModeHandler(app, app_token).start()
