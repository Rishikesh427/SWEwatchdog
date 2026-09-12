from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JsonDict = dict[str, Any]
Transport = Callable[[str, dict[str, str]], JsonDict]
PostTransport = Callable[[str, dict[str, str], JsonDict], JsonDict]


@dataclass(frozen=True)
class SlackConfig:
    api_base: str = "https://slack.com/api"
    token: str | None = None
    token_env: str = "SLACK_BOT_TOKEN"


class SlackError(RuntimeError):
    pass


class SlackClient:
    def __init__(
        self,
        config: SlackConfig | None = None,
        transport: Transport | None = None,
        post_transport: PostTransport | None = None,
    ):
        self.config = config or SlackConfig()
        self.token = self.config.token or os.getenv(self.config.token_env)
        self.transport = transport or self._default_transport
        self.post_transport = post_transport or self._default_post_transport

    def fetch_channel_messages(self, channel_id: str, oldest: datetime | None = None, limit: int = 100) -> list[dict[str, Any]]:
        params = {"channel": channel_id, "limit": str(limit)}
        if oldest:
            params["oldest"] = str(oldest.timestamp())
        payload = self._get(f"/conversations.history?{urlencode(params)}")
        if not payload.get("ok"):
            raise SlackError(payload.get("error", "Slack API request failed"))
        return [slack_message_to_source(channel_id, message) for message in payload.get("messages", [])]

    def _get(self, path: str) -> JsonDict:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return self.transport(f"{self.config.api_base.rstrip('/')}{path}", headers)

    def post_message(self, channel_id: str, text: str) -> JsonDict:
        payload = self._post("/chat.postMessage", {"channel": channel_id, "text": text})
        if not payload.get("ok"):
            raise SlackError(payload.get("error", "Slack message could not be sent"))
        return payload

    def send_direct_message(self, user_id: str, text: str) -> JsonDict:
        opened = self._post("/conversations.open", {"users": user_id})
        if not opened.get("ok") or not opened.get("channel", {}).get("id"):
            raise SlackError(opened.get("error", "Slack direct-message channel could not be opened"))
        return self.post_message(opened["channel"]["id"], text)

    def _post(self, path: str, payload: JsonDict) -> JsonDict:
        if not self.token:
            raise SlackError(f"Missing {self.config.token_env}; configure a Slack bot token before sending messages")
        headers = {"Authorization": f"Bearer {self.token}"}
        return self.post_transport(f"{self.config.api_base.rstrip('/')}{path}", headers, payload)

    @staticmethod
    def _default_transport(url: str, headers: dict[str, str]) -> JsonDict:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=20) as response:  # nosec: Slack URL is fixed by config
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _default_post_transport(url: str, headers: dict[str, str], payload: JsonDict) -> JsonDict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=20) as response:  # nosec: Slack URL is fixed by config
            return json.loads(response.read().decode("utf-8"))


def slack_message_to_source(channel_id: str, message: dict[str, Any]) -> dict[str, Any]:
    ts = message["ts"]
    created_at = datetime.fromtimestamp(float(ts.split(".")[0])).isoformat()
    return {
        "kind": "slack_message",
        "system": "slack",
        "text": message.get("text", ""),
        "url": f"slack://channel/{channel_id}/message/{ts}",
        "created_at": created_at,
        "channel_id": channel_id,
        "message_ts": ts,
    }
