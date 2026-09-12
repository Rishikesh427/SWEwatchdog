from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from swewatchdog.app import run_watchdog_evaluation
from swewatchdog.domain import (
    ActionItem,
    ActionItemStatus,
    Confidence,
    Deadline,
    ExpectedArtifact,
    JiraRef,
    Person,
    PullRequest,
    PullRequestStatus,
    ReviewerState,
    ReviewStatus,
    SourceRef,
)
from swewatchdog.github import GitHubClient, GitHubConfig, GitHubRepoNotFoundError, resolve_github_token
from swewatchdog.ingestion import (
    commitment_to_action_item,
    events_from_fixture,
    extract_commitment,
    integration_event_from_fixture,
    load_json_fixture,
    people_from_fixture,
    pull_request_from_fixture,
)
from swewatchdog.storage import JsonDataclassEncoder, SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="swewatchdog", description="Local SWEwatchdog backend prototype")
    parser.add_argument("--db", default="data/swewatchdog.db")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("fixture")

    ingest_dir = subparsers.add_parser("ingest-dir")
    ingest_dir.add_argument("directory")

    subparsers.add_parser("evaluate")
    subparsers.add_parser("summary")
    subparsers.add_parser("cursors")
    subparsers.add_parser("repos")
    subparsers.add_parser("slack-bot", help="Run the real Slack bot using Socket Mode.")

    web = subparsers.add_parser("web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8787)

    watch_repo = subparsers.add_parser("watch-repo")
    watch_repo.add_argument("repo", help="Repository to watch, in owner/name format")

    github_auth = subparsers.add_parser("github-auth")
    github_auth.add_argument("--token-env", default="GITHUB_TOKEN")
    github_auth.add_argument("--no-gh-token", action="store_true", help="Do not check `gh auth token`.")

    github_fetch = subparsers.add_parser("github-fetch")
    github_fetch.add_argument("repo", help="GitHub repository in owner/name format")
    github_fetch.add_argument("--since", help="ISO timestamp. Defaults to the stored GitHub cursor when available.")
    github_fetch.add_argument("--token-env", default="GITHUB_TOKEN")
    github_fetch.add_argument("--no-gh-token", action="store_true", help="Do not fall back to `gh auth token`.")

    args = parser.parse_args()

    if args.command == "github-auth":
        token, source = resolve_github_token(GitHubConfig(token_env=args.token_env, use_gh_cli_token=not args.no_gh_token))
        print(json.dumps({"authenticated": bool(token), "source": source}, indent=2))
        return

    if args.command == "slack-bot":
        from swewatchdog.slack_socket import run_socket_bot

        run_socket_bot(args.db)
        return

    if args.command == "web":
        from swewatchdog.web import run

        run(host=args.host, port=args.port, db_path=args.db)
        return

    store = SQLiteStore(args.db)

    if args.command == "init-db":
        store.init()
        print(f"Initialized {args.db}")
        return

    if args.command == "ingest":
        store.init()
        payload = load_json_fixture(args.fixture)
        ingested = _ingest_payload(store, payload)
        print(f"{'Ingested' if ingested else 'Skipped duplicate'} {args.fixture}")
        return

    if args.command == "ingest-dir":
        store.init()
        accepted, skipped = _ingest_directory(store, Path(args.directory))
        print(f"Ingested {accepted}; skipped {skipped} duplicate(s)")
        return

    if args.command == "evaluate":
        store.init()
        updated, decisions = _evaluate(store)
        print(json.dumps({"action_items": updated, "follow_ups": decisions}, cls=JsonDataclassEncoder, indent=2))
        return

    if args.command == "summary":
        store.init()
        print(_summary(store))
        return

    if args.command == "cursors":
        store.init()
        print(json.dumps(store.list_provider_cursors_raw(), indent=2))
        return

    if args.command == "repos":
        store.init()
        print(json.dumps(store.list_watched_repositories_raw(), indent=2))
        return

    if args.command == "watch-repo":
        store.init()
        store.watch_repository(args.repo)
        print(f"Watching {args.repo}")
        return

    if args.command == "github-fetch":
        store.init()
        since = _parse_optional_dt(args.since) or store.get_provider_cursor("github")
        token = __import__("os").getenv(args.token_env)
        config = GitHubConfig(token=token, token_env=args.token_env, use_gh_cli_token=not args.no_gh_token)
        try:
            prs = GitHubClient(config).fetch_recent_pull_requests(args.repo, since=since)
        except GitHubRepoNotFoundError as exc:
            raise SystemExit(f"Could not fetch {args.repo}: {exc}. Check that the repo exists and your token has access.") from exc
        store.watch_repository(args.repo)
        for pr in prs:
            store.save_pull_request(pr)
        if prs:
            store.update_provider_cursor("github", max(pr.updated_at for pr in prs))
        print(f"Fetched {len(prs)} pull request(s) from {args.repo}")
        return


def _ingest_directory(store: SQLiteStore, directory: Path) -> tuple[int, int]:
    accepted = 0
    skipped = 0
    for fixture in sorted(directory.glob("*.json")):
        if _ingest_payload(store, load_json_fixture(fixture)):
            accepted += 1
        else:
            skipped += 1
    return accepted, skipped


def _evaluate(store: SQLiteStore) -> tuple[list[ActionItem], list]:
    action_items = [_action_item_from_raw(raw) for raw in store.list_action_items_raw()]
    prs = [_pull_request_from_raw(raw) for raw in store.list_pull_requests_raw()]
    updated, decisions = run_watchdog_evaluation(action_items, prs, _utcnow())
    for item in updated:
        store.save_action_item(item)
    for decision in decisions:
        store.save_follow_up(decision)
    return updated, decisions


def _summary(store: SQLiteStore) -> str:
    updated, decisions = _evaluate(store)
    counts = Counter(item.status.value for item in updated)
    follow_up_counts = Counter(decision.reason.value for decision in decisions)
    lines = ["SWEwatchdog summary", ""]
    lines.append(f"Open action items: {len(updated)}")
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines.append("")
    lines.append(f"Current follow-up decisions: {len(decisions)}")
    for reason, count in sorted(follow_up_counts.items()):
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("Watched repositories:")
    repos = store.list_watched_repositories_raw()
    if repos:
        for repo in repos:
            lines.append(f"- {repo['repo']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Provider cursors:")
    cursors = store.list_provider_cursors_raw()
    if cursors:
        for cursor in cursors:
            lines.append(f"- {cursor['provider']}: {cursor['last_seen_at']}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def _ingest_payload(store: SQLiteStore, payload: dict) -> bool:
    event = integration_event_from_fixture(payload)
    if store.has_integration_event(event.id):
        return False
    store.save_integration_event(event)

    people = people_from_fixture(payload)
    if people:
        store.save_people(people)

    events = events_from_fixture(payload)
    now = _parse_dt(payload.get("now")) if payload.get("now") else _utcnow()

    if payload.get("kind") in {"slack_message", "granola_note"}:
        commitment = extract_commitment(payload)
        if commitment:
            action_item = commitment_to_action_item(
                commitment,
                people=people,
                events=events,
                now=now,
                default_repo=payload.get("default_repo"),
            )
            store.save_action_item(action_item)
        return True

    if payload.get("kind") == "github_pr":
        store.save_pull_request(pull_request_from_fixture(payload, people))
        return True

    raise ValueError(f"Unsupported fixture kind: {payload.get('kind')}")


def _action_item_from_raw(raw: dict) -> ActionItem:
    owner = _person_from_raw(raw["owner"]) if raw.get("owner") else None
    return ActionItem(
        id=raw["id"],
        title=raw["title"],
        description=raw["description"],
        status=ActionItemStatus(raw["status"]),
        owner=owner,
        source=SourceRef(**raw["source"]),
        jira=JiraRef(**raw["jira"]),
        deadline=Deadline(
            resolved_at=_parse_optional_dt(raw["deadline"]["resolved_at"]),
            original_text=raw["deadline"]["original_text"],
            confidence=Confidence(raw["deadline"]["confidence"]),
        ),
        expected_artifact=ExpectedArtifact(**raw["expected_artifact"]),
        matched_pr_ids=tuple(raw.get("matched_pr_ids", [])),
        created_at=_parse_dt(raw["created_at"]),
        updated_at=_parse_dt(raw["updated_at"]),
        last_checked_at=_parse_optional_dt(raw.get("last_checked_at")),
        next_follow_up_at=_parse_optional_dt(raw.get("next_follow_up_at")),
    )


def _pull_request_from_raw(raw: dict) -> PullRequest:
    return PullRequest(
        id=raw["id"],
        github_pr_number=raw["github_pr_number"],
        repo=raw["repo"],
        url=raw["url"],
        title=raw["title"],
        description=raw["description"],
        author=_person_from_raw(raw["author"]),
        status=PullRequestStatus(raw["status"]),
        review_status=ReviewStatus(raw["review_status"]),
        reviewers=tuple(
            ReviewerState(person=_person_from_raw(reviewer["person"]), status=reviewer["status"])
            for reviewer in raw.get("reviewers", [])
        ),
        created_at=_parse_dt(raw["created_at"]),
        updated_at=_parse_dt(raw["updated_at"]),
        merged_at=_parse_optional_dt(raw.get("merged_at")),
        closed_at=_parse_optional_dt(raw.get("closed_at")),
        linked_action_item_ids=tuple(raw.get("linked_action_item_ids", [])),
    )


def _person_from_raw(raw: dict) -> Person:
    return Person(
        id=raw["id"],
        display_name=raw["display_name"],
        slack_user_id=raw.get("slack_user_id"),
        github_username=raw.get("github_username"),
        github_account_email=raw.get("github_account_email"),
        work_email=raw.get("work_email"),
        calendar_user_id=raw.get("calendar_user_id"),
        aliases=tuple(raw.get("aliases", [])),
    )


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _parse_optional_dt(value: str | None) -> datetime | None:
    return _parse_dt(value) if value else None


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


if __name__ == "__main__":
    main()
