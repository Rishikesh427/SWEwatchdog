from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from swewatchdog.cli import _ingest_payload
from swewatchdog.ingestion import load_json_fixture
from swewatchdog.slack import SlackClient, SlackConfig
from swewatchdog.slack_bot import SlackBot, SlackRequestVerifier
from swewatchdog.storage import SQLiteStore


class TestSlackBot(TestCase):
    def test_verifies_current_slack_signature(self):
        body = b"command=%2Fwatchdog-action-items&text=5"
        timestamp = "1000"
        secret = "signing-secret"
        base = f"v0:{timestamp}:".encode("utf-8") + body
        signature = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

        verifier = SlackRequestVerifier(secret)

        assert verifier.verify(
            {"x-slack-request-timestamp": timestamp, "x-slack-signature": signature}, body, now=1001
        )
        assert not verifier.verify(
            {"x-slack-request-timestamp": timestamp, "x-slack-signature": "v0=not-valid"}, body, now=1001
        )
        assert not verifier.verify(
            {"x-slack-request-timestamp": timestamp, "x-slack-signature": signature}, body, now=1400
        )

    def test_action_items_command_renders_private_summary(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "watchdog.db")
            store.init()
            _ingest_payload(store, load_json_fixture("fixtures/slack-message.json"))

            response = SlackBot(store).handle_command("/watchdog-action-items", "1")

            assert response["response_type"] == "ephemeral"
            assert "SWEwatchdog action items" in response["text"]
            assert "auth redirects" in response["text"]

    def test_follow_up_command_sends_a_dm_to_an_overdue_reviewer(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "watchdog.db")
            store.init()
            _ingest_payload(store, load_json_fixture("fixtures/slack-message.json"))
            _ingest_payload(store, load_json_fixture("fixtures/github-pr.json"))
            calls = []

            def post_transport(url, headers, payload):
                calls.append((url, headers, payload))
                if url.endswith("/conversations.open"):
                    return {"ok": True, "channel": {"id": "D456"}}
                return {"ok": True}

            client = SlackClient(SlackConfig(token="xoxb-test"), post_transport=post_transport)
            bot = SlackBot(store, client)
            action_id = store.list_action_items_raw()[0]["id"].rsplit("_", 1)[-1]

            response = bot.handle_command("/watchdog-follow-up", action_id)

            assert "Sent a Slack follow-up" in response["text"]
            assert calls[0][2] == {"users": "U456"}
            assert calls[1][2]["channel"] == "D456"
            assert "waiting on your review" in calls[1][2]["text"]

    def test_app_mention_creates_a_slack_action_item(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "watchdog.db")
            store.init()
            store.watch_repository("Rishikesh427/ClimateGuard")

            SlackBot(store).handle_event(
                {
                    "type": "event_callback",
                    "event_id": "Ev-123",
                    "event": {
                        "type": "app_mention",
                        "channel": "C123",
                        "ts": "1799770012.100",
                        "user": "U123",
                        "text": "<@UBOT> <@U123> fix auth before tomorrow",
                    },
                }
            )

            action_items = store.list_action_items_raw()
            assert len(action_items) == 1
            assert action_items[0]["owner"]["slack_user_id"] == "U123"
            assert action_items[0]["expected_artifact"]["repo"] == "Rishikesh427/ClimateGuard"
