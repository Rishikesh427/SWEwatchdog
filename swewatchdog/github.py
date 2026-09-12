from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from swewatchdog.domain import Person, PullRequest, PullRequestStatus, ReviewerState, ReviewStatus

JsonDict = dict[str, Any]
Transport = Callable[[str, dict[str, str]], JsonDict | list[JsonDict]]


class GitHubError(RuntimeError):
    pass


class GitHubRepoNotFoundError(GitHubError):
    pass


@dataclass(frozen=True)
class GitHubConfig:
    api_base: str = "https://api.github.com"
    token: str | None = None
    token_env: str = "GITHUB_TOKEN"
    use_gh_cli_token: bool = True


class GitHubClient:
    def __init__(self, config: GitHubConfig | None = None, transport: Transport | None = None):
        self.config = resolve_github_config(config or GitHubConfig())
        self.transport = transport or self._default_transport

    def fetch_recent_pull_requests(self, repo: str, since: datetime | None = None) -> list[PullRequest]:
        owner, name = _split_repo(repo)
        query = urlencode({"state": "all", "sort": "updated", "direction": "desc", "per_page": "100"})
        pulls = self._get(f"/repos/{owner}/{name}/pulls?{query}")
        if not isinstance(pulls, list):
            raise ValueError("GitHub pulls response was not a list")

        results: list[PullRequest] = []
        for pull in pulls:
            updated_at = _parse_dt(pull["updated_at"])
            if since and updated_at < since:
                continue
            reviews = self._get(f"/repos/{owner}/{name}/pulls/{pull['number']}/reviews")
            if not isinstance(reviews, list):
                reviews = []
            results.append(github_pull_to_domain(repo, pull, reviews))
        return results

    def _get(self, path: str) -> JsonDict | list[JsonDict]:
        url = path if path.startswith("http") else f"{self.config.api_base.rstrip('/')}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SWEwatchdog",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return self.transport(url, headers)

    @staticmethod
    def _default_transport(url: str, headers: dict[str, str]) -> JsonDict | list[JsonDict]:
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=20) as response:  # nosec: user-configured GitHub URL only
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise GitHubRepoNotFoundError("GitHub repository was not found or is not accessible with current auth") from exc
            raise GitHubError(f"GitHub API request failed with HTTP {exc.code}") from exc


def resolve_github_config(config: GitHubConfig) -> GitHubConfig:
    token, _source = resolve_github_token(config)
    return GitHubConfig(
        api_base=config.api_base,
        token=token,
        token_env=config.token_env,
        use_gh_cli_token=config.use_gh_cli_token,
    )


def resolve_github_token(config: GitHubConfig) -> tuple[str | None, str]:
    if config.token:
        return config.token, "explicit"
    env_token = os.getenv(config.token_env)
    if env_token:
        return env_token, config.token_env
    if config.use_gh_cli_token:
        gh_token = _token_from_gh_cli()
        if gh_token:
            return gh_token, "gh"
    return None, "none"


def _token_from_gh_cli() -> str | None:
    try:
        completed = subprocess.run(
            ["gh", "auth", "token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    token = completed.stdout.strip()
    return token or None


def github_pull_to_domain(repo: str, pull: JsonDict, reviews: list[JsonDict]) -> PullRequest:
    author = _person_from_github_user(pull["user"])
    requested_reviewers = tuple(
        ReviewerState(person=_person_from_github_user(user), status="pending")
        for user in pull.get("requested_reviewers", [])
    )
    completed_reviewers = _latest_completed_reviewers(reviews)
    reviewers = _merge_reviewers(requested_reviewers, completed_reviewers)

    return PullRequest(
        id=f"github_pr_{repo}_{pull['number']}",
        github_pr_number=int(pull["number"]),
        repo=repo,
        url=pull["html_url"],
        title=pull["title"],
        description=pull.get("body") or "",
        author=author,
        status=_pull_status(pull),
        review_status=_review_status(tuple(reviewers), reviews),
        reviewers=tuple(reviewers),
        created_at=_parse_dt(pull["created_at"]),
        updated_at=_parse_dt(pull["updated_at"]),
        merged_at=_parse_optional_dt(pull.get("merged_at")),
        closed_at=_parse_optional_dt(pull.get("closed_at")),
    )


def _latest_completed_reviewers(reviews: list[JsonDict]) -> tuple[ReviewerState, ...]:
    latest_by_user: dict[str, ReviewerState] = {}
    for review in sorted(reviews, key=lambda item: item.get("submitted_at") or ""):
        user = review.get("user")
        state = review.get("state", "").lower()
        if not user or state in {"commented", "dismissed", "pending"}:
            continue
        latest_by_user[user["login"]] = ReviewerState(person=_person_from_github_user(user), status=state)
    return tuple(latest_by_user.values())


def _merge_reviewers(requested: tuple[ReviewerState, ...], completed: tuple[ReviewerState, ...]) -> list[ReviewerState]:
    merged = {reviewer.person.github_username: reviewer for reviewer in completed}
    for reviewer in requested:
        merged.setdefault(reviewer.person.github_username, reviewer)
    return list(merged.values())


def _pull_status(pull: JsonDict) -> PullRequestStatus:
    if pull.get("merged_at"):
        return PullRequestStatus.MERGED
    if pull.get("closed_at"):
        return PullRequestStatus.CLOSED
    return PullRequestStatus.OPEN


def _review_status(reviewers: tuple[ReviewerState, ...], reviews: list[JsonDict]) -> ReviewStatus:
    statuses = {reviewer.status for reviewer in reviewers}
    if "changes_requested" in statuses:
        return ReviewStatus.CHANGES_REQUESTED
    if "approved" in statuses:
        return ReviewStatus.APPROVED
    if any(review.get("state") == "CHANGES_REQUESTED" for review in reviews):
        return ReviewStatus.CHANGES_REQUESTED
    if any(review.get("state") == "APPROVED" for review in reviews):
        return ReviewStatus.APPROVED
    if any(reviewer.status == "pending" for reviewer in reviewers):
        return ReviewStatus.REVIEW_REQUESTED
    return ReviewStatus.NO_REVIEW_REQUESTED


def _person_from_github_user(user: JsonDict) -> Person:
    login = user["login"]
    email = user.get("email")
    return Person(
        id=f"github_user_{login}",
        display_name=user.get("name") or login,
        github_username=login,
        github_account_email=email,
    )


def _split_repo(repo: str) -> tuple[str, str]:
    parts = repo.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError("GitHub repo must be in owner/name format")
    return parts[0], parts[1]


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _parse_optional_dt(value: str | None) -> datetime | None:
    return _parse_dt(value) if value else None
