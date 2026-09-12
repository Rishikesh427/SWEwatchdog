
from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from swewatchdog.cli import _evaluate, _ingest_directory, _pull_request_from_raw
from swewatchdog.github import GitHubClient, GitHubConfig, GitHubRepoNotFoundError, resolve_github_token
from swewatchdog.slack_bot import SlackBot, SlackRequestVerifier
from swewatchdog.storage import JsonDataclassEncoder, SQLiteStore

DEFAULT_DB = "data/swewatchdog.db"


class SWEwatchdogHandler(BaseHTTPRequestHandler):
    server_version = "SWEwatchdog/0.1"

    @property
    def store(self) -> SQLiteStore:
        return SQLiteStore(self.server.db_path)  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/":
            self._dashboard()
        elif route == "/api/state":
            self._json(self._state())
        else:
            self._not_found()

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length) if length else b""

        if route in {"/slack/commands", "/slack/events"}:
            self._slack_request(route, body)
            return

        form = {key: values[0] for key, values in parse_qs(body.decode("utf-8")).items()}
        self.store.init()

        if route == "/actions/watch-repo":
            repo = form.get("repo", "").strip()
            if repo:
                self.store.watch_repository(repo)
            self._redirect("/")
            return

        if route == "/actions/github-fetch":
            repo = form.get("repo", "").strip()
            if repo:
                since = self.store.get_provider_cursor("github")
                try:
                    prs = GitHubClient(GitHubConfig()).fetch_recent_pull_requests(repo, since=since)
                    self.store.watch_repository(repo)
                    for pr in prs:
                        self.store.save_pull_request(pr)
                    if prs:
                        self.store.update_provider_cursor("github", max(pr.updated_at for pr in prs))
                except GitHubRepoNotFoundError:
                    pass
            self._redirect("/")
            return

        if route == "/actions/ingest-fixtures":
            _ingest_directory(self.store, Path("fixtures"))
            self._redirect("/")
            return

        if route == "/actions/evaluate":
            _evaluate(self.store)
            self._redirect("/")
            return

        self._not_found()

    def _slack_request(self, route: str, body: bytes) -> None:
        headers = {key.lower(): value for key, value in self.headers.items()}
        if not SlackRequestVerifier().verify(headers, body):
            self._plain("Slack request signature could not be verified.", HTTPStatus.UNAUTHORIZED)
            return

        bot = SlackBot(self.store)
        if route == "/slack/commands":
            form = {key: values[0] for key, values in parse_qs(body.decode("utf-8")).items()}
            response = bot.handle_command(form.get("command", ""), form.get("text", ""))
            self._json(response)
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._plain("Expected a JSON Slack event payload.", HTTPStatus.BAD_REQUEST)
            return
        response = bot.handle_event(payload)
        if response is None:
            self._empty()
        else:
            self._json(response)

    def _dashboard(self) -> None:
        self.store.init()
        self._html(render_dashboard(self._state()))

    def _state(self) -> dict:
        self.store.init()
        action_items, decisions = _evaluate(self.store)
        prs = [_pull_request_from_raw(raw) for raw in self.store.list_pull_requests_raw()]
        token, source = resolve_github_token(GitHubConfig())
        return {
            "github_auth": {"authenticated": bool(token), "source": source},
            "repos": self.store.list_watched_repositories_raw(),
            "cursors": self.store.list_provider_cursors_raw(),
            "action_items": action_items,
            "pull_requests": prs,
            "follow_ups": decisions,
        }

    def _html(self, body: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _json(self, payload: dict) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload, cls=JsonDataclassEncoder, indent=2).encode("utf-8"))

    def _plain(self, body: str, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _empty(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("location", location)
        self.end_headers()

    def _not_found(self) -> None:
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def render_dashboard(state: dict) -> str:
    auth = state["github_auth"]
    repos = state["repos"]
    action_items = state["action_items"]
    pull_requests = state["pull_requests"]
    follow_ups = state["follow_ups"]
    cursors = state["cursors"]
    default_repo = repos[0]["repo"] if repos else "Rishikesh427/ClimateGuard"
    auth_class = "ok" if auth["authenticated"] else "urgent"
    page = """<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>SWEwatchdog</title>
<style>
:root { --ink:#18202a; --muted:#627083; --line:#d8dee8; --panel:#f7f9fc; --accent:#0b6bcb; --warn:#b45309; --ok:#0f766e; }
* { box-sizing:border-box; } body { margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; color:var(--ink); background:white; }
header { border-bottom:1px solid var(--line); padding:18px 28px; display:flex; justify-content:space-between; gap:18px; align-items:center; }
h1 { margin:0; font-size:22px; letter-spacing:0; } h2 { margin:0 0 12px; font-size:16px; }
main { max-width:1180px; margin:0 auto; padding:24px; }.grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:20px; }
.metric { border:1px solid var(--line); border-radius:8px; padding:14px; background:var(--panel); }.metric strong { display:block; font-size:24px; margin-top:4px; }
.layout { display:grid; grid-template-columns:2fr 1fr; gap:18px; } section { border-top:1px solid var(--line); padding-top:18px; margin-top:20px; }
table { width:100%; border-collapse:collapse; } th,td { text-align:left; border-bottom:1px solid var(--line); padding:10px 8px; vertical-align:top; }
th { color:var(--muted); font-size:12px; text-transform:uppercase; font-weight:650; }.pill { display:inline-block; padding:2px 8px; border-radius:999px; background:#e8eef7; font-size:12px; white-space:nowrap; }
.urgent { color:var(--warn); font-weight:650; }.ok { color:var(--ok); font-weight:650; }.muted { color:var(--muted); }
form { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 14px; } input { border:1px solid var(--line); border-radius:6px; padding:8px 10px; min-width:260px; font:inherit; }
button { border:1px solid #0a5db0; background:var(--accent); color:white; border-radius:6px; padding:8px 11px; font:inherit; cursor:pointer; } button.secondary { background:white; color:var(--accent); }
.side { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }.stack { display:grid; gap:10px; }.item { border:1px solid var(--line); border-radius:8px; padding:12px; background:white; }
@media (max-width:850px) { .grid,.layout { grid-template-columns:1fr; } header { align-items:flex-start; flex-direction:column; } }
</style>
</head>
<body>
<header><div><h1>SWEwatchdog</h1><div class='muted'>Engineering commitments, PR evidence, and follow-up loops.</div></div><div class='__AUTH_CLASS__'>GitHub auth: __AUTH_SOURCE__</div></header>
<main>
<div class='grid'><div class='metric'>Watched repos<strong>__REPO_COUNT__</strong></div><div class='metric'>Action items<strong>__ITEM_COUNT__</strong></div><div class='metric'>Pull requests<strong>__PR_COUNT__</strong></div><div class='metric'>Follow-ups<strong>__FOLLOW_COUNT__</strong></div></div>
<div class='layout'><div>
<section><h2>Actions</h2><form method='post' action='/actions/watch-repo'><input name='repo' value='__DEFAULT_REPO__'><button>Watch repo</button></form><form method='post' action='/actions/github-fetch'><input name='repo' value='__DEFAULT_REPO__'><button>Fetch GitHub</button></form><form method='post' action='/actions/ingest-fixtures'><button class='secondary'>Ingest fixtures</button></form><form method='post' action='/actions/evaluate'><button class='secondary'>Evaluate now</button></form></section>
<section><h2>Action Items</h2>__ACTION_ITEMS__</section>
<section><h2>Pull Requests</h2>__PULL_REQUESTS__</section>
</div><aside class='side'><h2>Follow-Ups</h2>__FOLLOW_UPS__<section><h2>Watched Repos</h2>__REPOS__</section><section><h2>Cursors</h2>__CURSORS__</section></aside></div>
</main></body></html>"""
    replacements = {
        "__AUTH_CLASS__": auth_class,
        "__AUTH_SOURCE__": html.escape(str(auth["source"])),
        "__REPO_COUNT__": str(len(repos)),
        "__ITEM_COUNT__": str(len(action_items)),
        "__PR_COUNT__": str(len(pull_requests)),
        "__FOLLOW_COUNT__": str(len(follow_ups)),
        "__DEFAULT_REPO__": html.escape(default_repo),
        "__ACTION_ITEMS__": render_action_items(action_items),
        "__PULL_REQUESTS__": render_pull_requests(pull_requests),
        "__FOLLOW_UPS__": render_follow_ups(follow_ups),
        "__REPOS__": render_repos(repos),
        "__CURSORS__": render_cursors(cursors),
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page

def render_action_items(items) -> str:
    if not items:
        return "<p class='muted'>No action items yet.</p>"
    rows = "".join(
        "<tr><td>{}</td><td><span class='pill'>{}</span></td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(item.title), html.escape(item.status.value), html.escape(item.owner.display_name if item.owner else "Unknown"), html.escape(item.expected_artifact.repo or "Unknown"), html.escape(item.deadline.resolved_at.isoformat() if item.deadline.resolved_at else "Unknown")
        )
        for item in items
    )
    return "<table><thead><tr><th>Task</th><th>Status</th><th>Owner</th><th>Repo</th><th>Deadline</th></tr></thead><tbody>{}</tbody></table>".format(rows)


def render_pull_requests(prs) -> str:
    if not prs:
        return "<p class='muted'>No pull requests fetched yet.</p>"
    rows = "".join(
        "<tr><td><a href='{}'>#{}</a></td><td>{}</td><td><span class='pill'>{}</span></td><td>{}</td><td>{}</td></tr>".format(
            html.escape(pr.url), pr.github_pr_number, html.escape(pr.title), html.escape(pr.review_status.value), html.escape(pr.author.display_name), html.escape(pr.updated_at.isoformat())
        )
        for pr in prs
    )
    return "<table><thead><tr><th>PR</th><th>Title</th><th>Review</th><th>Author</th><th>Updated</th></tr></thead><tbody>{}</tbody></table>".format(rows)


def render_follow_ups(decisions) -> str:
    if not decisions:
        return "<p class='muted'>No follow-ups needed.</p>"
    cards = []
    for decision in decisions:
        urgency_class = "urgent" if decision.urgency == "urgent" else "muted"
        recipient = decision.recipient.display_name if decision.recipient else "Needs mapping"
        cards.append("<div class='item'><div><span class='pill'>{}</span> <span class='{}'>{}</span></div><p>{}</p><div class='muted'>To: {} via {}</div></div>".format(html.escape(decision.reason.value), urgency_class, html.escape(decision.urgency), html.escape(decision.message), html.escape(recipient), html.escape(decision.channel.value)))
    return "<div class='stack'>{}</div>".format("".join(cards))


def render_repos(repos) -> str:
    if not repos:
        return "<p class='muted'>No repos watched.</p>"
    return "<ul>" + "".join("<li>{}</li>".format(html.escape(repo["repo"])) for repo in repos) + "</ul>"


def render_cursors(cursors) -> str:
    if not cursors:
        return "<p class='muted'>No cursors yet.</p>"
    return "<ul>" + "".join("<li>{}: {}</li>".format(html.escape(cursor["provider"]), html.escape(cursor["last_seen_at"])) for cursor in cursors) + "</ul>"


def run(host: str = "127.0.0.1", port: int = 8787, db_path: str = DEFAULT_DB) -> None:
    server = ThreadingHTTPServer((host, port), SWEwatchdogHandler)
    server.db_path = db_path  # type: ignore[attr-defined]
    print(f"SWEwatchdog running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
