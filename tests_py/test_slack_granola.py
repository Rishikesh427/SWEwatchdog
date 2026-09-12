from unittest import TestCase
from tempfile import TemporaryDirectory
from pathlib import Path
import json

from swewatchdog.granola import granola_note_to_source, load_granola_export
from swewatchdog.slack import SlackClient, SlackConfig, slack_message_to_source


class TestSlackGranolaConnectors(TestCase):
    def test_slack_message_maps_to_source_payload(self):
        source = slack_message_to_source("C123", {"ts": "1799770012.100", "text": "@rishikesh fix auth by standup"})

        assert source["kind"] == "slack_message"
        assert source["system"] == "slack"
        assert source["channel_id"] == "C123"
        assert "fix auth" in source["text"]

    def test_slack_client_uses_injected_transport(self):
        def transport(url, headers):
            assert "conversations.history" in url
            assert headers["Authorization"] == "Bearer token"
            return {"ok": True, "messages": [{"ts": "1799770012.100", "text": "@rishikesh fix auth by standup"}]}

        client = SlackClient(SlackConfig(token="token"), transport=transport)
        messages = client.fetch_channel_messages("C123")

        assert len(messages) == 1
        assert messages[0]["system"] == "slack"

    def test_granola_note_maps_to_source_payload(self):
        source = granola_note_to_source({"id": "n1", "text": "Rishikesh to fix onboarding before standup", "created_at": "2026-09-12T12:00:00Z"})

        assert source["kind"] == "granola_note"
        assert source["meeting_id"] == "n1"

    def test_load_granola_export(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "granola.json"
            path.write_text(json.dumps({"notes": [{"id": "n1", "text": "Maya to update billing by demo", "created_at": "2026-09-12T12:00:00Z"}]}))

            notes = load_granola_export(path)

            assert len(notes) == 1
            assert notes[0]["system"] == "granola"
