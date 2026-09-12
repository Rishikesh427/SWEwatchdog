from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from swewatchdog.slack_socket import build_socket_mode_app, run_socket_bot
from swewatchdog.storage import SQLiteStore


class TestSlackSocketMode(TestCase):
    def test_builds_a_bolt_application_with_a_bot_token(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "watchdog.db")
            app = build_socket_mode_app(store, bot_token="xoxb-test-token", token_verification_enabled=False)

            assert app is not None

    def test_run_explains_missing_socket_tokens(self):
        with patch.dict(os.environ, {}, clear=True):
            try:
                run_socket_bot("/tmp/unused-watchdog.db")
            except SystemExit as exc:
                assert "SLACK_BOT_TOKEN" in str(exc)
                assert "SLACK_APP_TOKEN" in str(exc)
            else:
                raise AssertionError("Expected missing tokens to stop startup")

    def test_manifest_declares_socket_mode_and_the_two_commands(self):
        manifest = json.loads(Path("slack-manifest.json").read_text())

        assert manifest["settings"]["socket_mode_enabled"] is True
        assert [command["command"] for command in manifest["features"]["slash_commands"]] == [
            "/watchdog-action-items",
            "/watchdog-follow-up",
        ]
        assert "connections:write" not in manifest["oauth_config"]["scopes"]["bot"]
