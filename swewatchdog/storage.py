from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from swewatchdog.domain import Account, ActionItem, FollowUpDecision, IntegrationConnection, IntegrationEvent, Person, PullRequest


class JsonDataclassEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def connection(self):
        db = self.connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def init(self) -> None:
        with self.connection() as db:
            db.executescript(
                """
                create table if not exists people (
                  id text primary key,
                  data text not null
                );

                create table if not exists accounts (
                  id text primary key,
                  email text not null unique,
                  data text not null
                );

                create table if not exists integration_connections (
                  id text primary key,
                  account_id text not null,
                  provider text not null,
                  status text not null,
                  workspace_id text,
                  connected_identity text,
                  data text not null
                );

                create table if not exists integration_events (
                  id text primary key,
                  provider text not null,
                  kind text not null,
                  source_url text not null,
                  source_created_at text not null,
                  payload_hash text not null,
                  processed_at text,
                  data text not null
                );

                create table if not exists provider_cursors (
                  provider text primary key,
                  last_seen_at text not null,
                  updated_at text not null default current_timestamp
                );

                create table if not exists watched_repositories (
                  repo text primary key,
                  provider text not null default 'github',
                  active integer not null default 1,
                  created_at text not null default current_timestamp
                );

                create table if not exists action_items (
                  id text primary key,
                  status text not null,
                  owner_id text,
                  deadline_at text,
                  repo text,
                  data text not null
                );

                create table if not exists pull_requests (
                  id text primary key,
                  repo text not null,
                  github_pr_number integer not null,
                  status text not null,
                  review_status text not null,
                  data text not null
                );

                create table if not exists follow_ups (
                  id integer primary key autoincrement,
                  signature text not null unique,
                  action_item_id text not null,
                  pull_request_id text,
                  reason text not null,
                  channel text not null,
                  urgency text not null,
                  data text not null,
                  created_at text not null default current_timestamp
                );
                """
            )

    def save_account(self, account: Account) -> None:
        with self.connection() as db:
            db.execute(
                "insert or replace into accounts (id, email, data) values (?, ?, ?)",
                (account.id, account.email, _to_json(account)),
            )

    def save_integration_connection(self, connection: IntegrationConnection) -> None:
        with self.connection() as db:
            db.execute(
                """
                insert or replace into integration_connections
                  (id, account_id, provider, status, workspace_id, connected_identity, data)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    connection.id,
                    connection.account_id,
                    connection.provider.value,
                    connection.status.value,
                    connection.workspace_id,
                    connection.connected_identity,
                    _to_json(connection),
                ),
            )

    def has_integration_event(self, event_id: str) -> bool:
        with self.connection() as db:
            row = db.execute("select 1 from integration_events where id = ?", (event_id,)).fetchone()
        return row is not None

    def save_integration_event(self, event: IntegrationEvent) -> None:
        with self.connection() as db:
            db.execute(
                """
                insert or replace into integration_events
                  (id, provider, kind, source_url, source_created_at, payload_hash, processed_at, data)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.provider.value,
                    event.kind.value,
                    event.source_url,
                    event.source_created_at.isoformat(),
                    event.payload_hash,
                    event.processed_at.isoformat() if event.processed_at else None,
                    _to_json(event),
                ),
            )
        self.update_provider_cursor(event.provider.value, event.source_created_at)

    def update_provider_cursor(self, provider: str, seen_at: datetime) -> None:
        current = self.get_provider_cursor(provider)
        if current and current >= seen_at:
            return
        with self.connection() as db:
            db.execute(
                """
                insert into provider_cursors (provider, last_seen_at) values (?, ?)
                on conflict(provider) do update set last_seen_at = excluded.last_seen_at, updated_at = current_timestamp
                """,
                (provider, seen_at.isoformat()),
            )

    def get_provider_cursor(self, provider: str) -> datetime | None:
        with self.connection() as db:
            row = db.execute("select last_seen_at from provider_cursors where provider = ?", (provider,)).fetchone()
        return datetime.fromisoformat(row["last_seen_at"]) if row else None

    def list_provider_cursors_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select provider, last_seen_at, updated_at from provider_cursors order by provider").fetchall()
        return [dict(row) for row in rows]

    def watch_repository(self, repo: str, provider: str = "github") -> None:
        with self.connection() as db:
            db.execute(
                "insert or replace into watched_repositories (repo, provider, active) values (?, ?, 1)",
                (repo, provider),
            )

    def list_watched_repositories_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select repo, provider, active, created_at from watched_repositories order by repo").fetchall()
        return [dict(row) for row in rows]

    def save_people(self, people: list[Person]) -> None:
        with self.connection() as db:
            db.executemany(
                "insert or replace into people (id, data) values (?, ?)",
                [(person.id, _to_json(person)) for person in people],
            )

    def save_action_item(self, action_item: ActionItem) -> None:
        with self.connection() as db:
            db.execute(
                """
                insert or replace into action_items (id, status, owner_id, deadline_at, repo, data)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    action_item.id,
                    action_item.status.value,
                    action_item.owner.id if action_item.owner else None,
                    action_item.deadline.resolved_at.isoformat() if action_item.deadline.resolved_at else None,
                    action_item.expected_artifact.repo,
                    _to_json(action_item),
                ),
            )

    def save_pull_request(self, pr: PullRequest) -> None:
        with self.connection() as db:
            db.execute(
                """
                insert or replace into pull_requests (id, repo, github_pr_number, status, review_status, data)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    pr.id,
                    pr.repo,
                    pr.github_pr_number,
                    pr.status.value,
                    pr.review_status.value,
                    _to_json(pr),
                ),
            )

    def save_follow_up(self, decision: FollowUpDecision) -> bool:
        signature = follow_up_signature(decision)
        with self.connection() as db:
            try:
                db.execute(
                    """
                    insert into follow_ups (signature, action_item_id, pull_request_id, reason, channel, urgency, data)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signature,
                        decision.action_item_id,
                        decision.pull_request_id,
                        decision.reason.value,
                        decision.channel.value,
                        decision.urgency,
                        _to_json(decision),
                    ),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def list_action_items_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select data from action_items order by id").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def list_pull_requests_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select data from pull_requests order by id").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def list_follow_ups_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select data from follow_ups order by id").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def list_accounts_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select data from accounts order by id").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def list_integration_connections_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select data from integration_connections order by id").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def list_integration_events_raw(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("select data from integration_events order by id").fetchall()
        return [json.loads(row["data"]) for row in rows]


def follow_up_signature(decision: FollowUpDecision) -> str:
    recipient_id = decision.recipient.id if decision.recipient else "unknown"
    pr_id = decision.pull_request_id or "none"
    return f"{decision.action_item_id}:{pr_id}:{recipient_id}:{decision.reason.value}"


def _to_json(value: Any) -> str:
    return json.dumps(value, cls=JsonDataclassEncoder, sort_keys=True)
