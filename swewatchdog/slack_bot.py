from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from typing import Any, Mapping

from swewatchdog.cli import _evaluate, _ingest_payload
from swewatchdog.domain import ActionItem, FollowUpChannel, FollowUpDecision, Person
from swewatchdog.slack import SlackClient, SlackError, slack_message_to_source
from swewatchdog.storage import SQLiteStore


class SlackRequestVerifier:
    """Validates Slack request signatures before commands and events are processed."""

    def __init__(self, signing_secret: str | None = None, max_age_seconds: int = 60 * 5):
        self.signing_secret = signing_secret or os.getenv("SLACK_SIGNING_SECRET")
        self.max_age_seconds = max_age_seconds

    def verify(self, headers: Mapping[str, str], body: bytes, now: int | None = None) -> bool:
        if not self.signing_secret:
            return False
        timestamp = headers.get("x-slack-request-timestamp", "")
        signature = headers.get("x-slack-signature", "")
        try:
            sent_at = int(timestamp)
        except ValueError:
            return False
        if abs((now if now is not None else int(time.time())) - sent_at) > self.max_age_seconds:
            return False
        base = f"v0:{timestamp}:".encode("utf-8") + body
        expected = "v0=" + hmac.new(self.signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class SlackBot:
    """The Slack-specific surface for the local watchdog service."""

    def __init__(self, store: SQLiteStore, client: SlackClient | None = None):
        self.store = store
        self.client = client or SlackClient()

    def handle_command(self, command: str, text: str) -> dict[str, str]:
        self.store.init()
        if command == "/watchdog-action-items":
            return self._action_items_response(text)
        if command == "/watchdog-follow-up":
            return self._follow_up_response(text)
        return _ephemeral("Unknown command. Try `/watchdog-action-items 5` or `/watchdog-follow-up <task-id-or-title>`.")

    def handle_event(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        self.store.init()
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge", "")}
        if payload.get("type") != "event_callback":
            return None

        event = payload.get("event", {})
        if event.get("type") != "app_mention" or event.get("bot_id"):
            return None
        channel_id = event.get("channel")
        timestamp = event.get("ts")
        if not channel_id or not timestamp:
            return None

        text = event.get("text", "")
        if text.startswith("<@") and ">" in text:
            text = text.split(">", 1)[1].strip()
        source = slack_message_to_source(channel_id, {"ts": timestamp, "text": text})
        source["id"] = payload.get("event_id", source["url"])
        source["default_repo"] = _default_repo(self.store)
        people_ids = set(re.findall(r"<@([A-Z0-9]+)>", text))
        if event.get("user"):
            people_ids.add(event["user"])
        source["people"] = [_slack_person(user_id) for user_id in sorted(people_ids)]
        _ingest_payload(self.store, source)
        return None

    def _action_items_response(self, text: str) -> dict[str, str]:
        limit = _parse_limit(text)
        if limit is None:
            return _ephemeral("Use a number from 1 to 20, for example `/watchdog-action-items 5`.")
        action_items, decisions = _evaluate(self.store)
        lines = [f"*SWEwatchdog action items* ({len(action_items)} tracked)"]
        if not action_items:
            lines.append("No action items yet. Mention the bot in a Slack commitment to start tracking one.")
        else:
            for item in action_items[:limit]:
                owner = _slack_person_label(item.owner)
                repo = item.expected_artifact.repo or "repo not set"
                lines.append(f"- `{_action_ref(item)}` *{item.title}* - {item.status.value}; {owner}; {repo}")
        if decisions:
            lines.append(f"\n{len(decisions)} follow-up(s) are currently due. Run `/watchdog-follow-up <task-id>` to send one.")
        return _ephemeral("\n".join(lines))

    def _follow_up_response(self, text: str) -> dict[str, str]:
        query = text.strip()
        if not query:
            return _ephemeral("Name a task id or a distinctive title, for example `/watchdog-follow-up a1b2c3`.")
        action_items, decisions = _evaluate(self.store)
        matches = _find_action_items(action_items, query)
        if not matches:
            return _ephemeral("I could not find that action item. Run `/watchdog-action-items 20` to see task ids.")
        if len(matches) > 1:
            choices = ", ".join(f"`{_action_ref(item)}` {item.title}" for item in matches[:5])
            return _ephemeral(f"That matches more than one task: {choices}. Use its task id.")

        item = matches[0]
        decision = next((candidate for candidate in decisions if candidate.action_item_id == item.id), None)
        if decision is None:
            return _ephemeral(f"`{_action_ref(item)}` does not need a follow-up right now.")
        if decision.channel != FollowUpChannel.SLACK_DM or not decision.recipient or not decision.recipient.slack_user_id:
            return _ephemeral(
                f"`{_action_ref(item)}` needs identity mapping before I can send this Slack follow-up: {decision.message}"
            )

        try:
            self.client.send_direct_message(decision.recipient.slack_user_id, _format_follow_up(item, decision))
        except SlackError as exc:
            return _ephemeral(f"I could not send the Slack follow-up: {exc}")
        self.store.save_follow_up(decision)
        return _ephemeral(f"Sent a Slack follow-up to {_slack_person_label(decision.recipient)} for `{_action_ref(item)}`.")


def _ephemeral(text: str) -> dict[str, str]:
    return {"response_type": "ephemeral", "text": text}


def _parse_limit(text: str) -> int | None:
    if not text.strip():
        return 5
    try:
        limit = int(text.strip())
    except ValueError:
        return None
    return limit if 1 <= limit <= 20 else None


def _find_action_items(items: list[ActionItem], query: str) -> list[ActionItem]:
    normalized = query.removeprefix("#").lower()
    exact = [item for item in items if item.id.lower() == normalized or _action_ref(item).lower() == normalized]
    if exact:
        return exact
    return [item for item in items if normalized in item.title.lower()]


def _action_ref(item: ActionItem) -> str:
    return item.id.rsplit("_", 1)[-1]


def _slack_person_label(person: Person | None) -> str:
    if person is None:
        return "owner unknown"
    return f"<@{person.slack_user_id}>" if person.slack_user_id else person.display_name


def _format_follow_up(item: ActionItem, decision: FollowUpDecision) -> str:
    return f"SWEwatchdog follow-up for *{item.title}* (`{_action_ref(item)}`): {decision.message}"


def _slack_person(user_id: str) -> dict[str, Any]:
    return {
        "id": f"slack_user_{user_id}",
        "display_name": user_id,
        "slack_user_id": user_id,
        "aliases": [user_id],
    }


def _default_repo(store: SQLiteStore) -> str | None:
    repos = store.list_watched_repositories_raw()
    return repos[0]["repo"] if len(repos) == 1 else None
