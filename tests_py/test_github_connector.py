from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from swewatchdog.domain import PullRequestStatus, ReviewStatus
from swewatchdog.github import GitHubClient, GitHubConfig, GitHubError, GitHubRepoNotFoundError, github_pull_to_domain, resolve_github_config, resolve_github_token


def sample_pull(**overrides):
    payload = {
        "number": 184,
        "html_url": "https://github.com/example/web-app/pull/184",
        "title": "WEB-412 Add auth redirects",
        "body": "Implements auth redirects",
        "user": {"login": "rishikesh", "name": "Rishikesh", "email": "rishikesh@example.com"},
        "requested_reviewers": [{"login": "alex", "name": "Alex", "email": "alex@example.com"}],
        "created_at": "2026-09-12T15:00:00Z",
        "updated_at": "2026-09-12T16:00:00Z",
        "merged_at": None,
        "closed_at": None,
    }
    payload.update(overrides)
    return payload


class TestGitHubConnector(TestCase):
    def test_maps_pull_request_with_pending_reviewer(self):
        pr = github_pull_to_domain("example/web-app", sample_pull(), [])

        assert pr.id == "github_pr_example/web-app_184"
        assert pr.status == PullRequestStatus.OPEN
        assert pr.review_status == ReviewStatus.REVIEW_REQUESTED
        assert pr.reviewers[0].person.github_username == "alex"

    def test_maps_approved_review(self):
        pr = github_pull_to_domain(
            "example/web-app",
            sample_pull(requested_reviewers=[]),
            [
                {
                    "state": "APPROVED",
                    "submitted_at": "2026-09-12T17:00:00Z",
                    "user": {"login": "alex", "name": "Alex"},
                }
            ],
        )

        assert pr.review_status == ReviewStatus.APPROVED
        assert pr.reviewers[0].status == "approved"

    def test_client_fetches_recent_pull_requests_with_injected_transport(self):
        calls = []

        def transport(url, headers):
            calls.append((url, headers))
            if url.endswith("/pulls?state=all&sort=updated&direction=desc&per_page=100"):
                return [sample_pull(), sample_pull(number=185, updated_at="2026-09-10T16:00:00Z")]
            if url.endswith("/pulls/184/reviews"):
                return []
            if url.endswith("/pulls/185/reviews"):
                return []
            raise AssertionError(url)

        client = GitHubClient(GitHubConfig(api_base="https://api.github.test", token="token"), transport=transport)
        prs = client.fetch_recent_pull_requests("example/web-app", since=datetime(2026, 9, 11, 0, 0, 0))

        assert len(prs) == 1
        assert prs[0].github_pr_number == 184
        assert calls[0][1]["Authorization"] == "Bearer token"

    def test_resolves_explicit_token_without_gh_cli(self):
        config = resolve_github_config(GitHubConfig(token="explicit", use_gh_cli_token=False))

        assert config.token == "explicit"

    def test_client_can_disable_gh_cli_token_fallback(self):
        client = GitHubClient(
            GitHubConfig(api_base="https://api.github.test", use_gh_cli_token=False),
            transport=lambda _url, _headers: [],
        )

        assert client.config.token is None

    def test_resolves_token_from_environment(self):
        with patch.dict("os.environ", {"SWEWATCHDOG_GITHUB_TOKEN": "env-token"}):
            token, source = resolve_github_token(GitHubConfig(token_env="SWEWATCHDOG_GITHUB_TOKEN", use_gh_cli_token=False))

        assert token == "env-token"
        assert source == "SWEWATCHDOG_GITHUB_TOKEN"

    def test_split_repo_validation_surfaces_as_value_error(self):
        client = GitHubClient(GitHubConfig(use_gh_cli_token=False), transport=lambda _url, _headers: [])

        try:
            client.fetch_recent_pull_requests("missing-owner")
        except ValueError as exc:
            assert "owner/name" in str(exc)
        else:
            raise AssertionError("Expected ValueError")

    def test_repo_not_found_error_is_available_for_cli_handling(self):
        error = GitHubRepoNotFoundError("not found")

        assert isinstance(error, GitHubError)
