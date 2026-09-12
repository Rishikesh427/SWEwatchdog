from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from swewatchdog.app import run_watchdog_evaluation
from swewatchdog.domain import (
    ActionItem,
    ActionItemStatus,
    Account,
    Confidence,
    Deadline,
    ExpectedArtifact,
    IntegrationConnection,
    IntegrationProvider,
    IntegrationStatus,
    JiraRef,
    Person,
    PullRequest,
    PullRequestStatus,
    ReviewerState,
    ReviewStatus,
    SourceRef,
)
from swewatchdog.cli import _ingest_directory, _ingest_payload, _summary
from swewatchdog.ingestion import commitment_to_action_item, extract_commitment, integration_event_from_fixture, load_json_fixture
from swewatchdog.intelligence import CalendarEvent, resolve_deadline, score_pull_request_match
from swewatchdog.monitoring import choose_channel, evaluate_action_item
from swewatchdog.storage import SQLiteStore


NOW = datetime(2026, 9, 12, 14, 0, 0)


def owner() -> Person:
    return Person(
        id="person_rishikesh",
        display_name="Rishikesh",
        slack_user_id="U123",
        github_username="rishikesh",
        github_account_email="rishikesh@example.com",
        work_email="rishikesh@company.com",
        aliases=("Rishi",),
    )


def reviewer() -> Person:
    return Person(
        id="person_alex",
        display_name="Alex",
        slack_user_id="U456",
        github_username="alex",
        github_account_email="alex@example.com",
        work_email="alex@company.com",
    )


def action_item(**overrides) -> ActionItem:
    values = {
        "id": "ai_1",
        "title": "Add auth redirects",
        "description": "Add redirects for authentication callback flow.",
        "status": ActionItemStatus.AWAITING_PR,
        "owner": owner(),
        "source": SourceRef(system="slack", url="https://slack.example.com/thread/launch-auth"),
        "jira": JiraRef(key="WEB-412", url="https://jira.example.com/browse/WEB-412"),
        "deadline": Deadline(datetime(2026, 9, 12, 18, 0, 0), "before feature presentation", Confidence.HIGH),
        "expected_artifact": ExpectedArtifact(repo="web-app"),
        "created_at": datetime(2026, 9, 12, 12, 0, 0),
        "updated_at": datetime(2026, 9, 12, 12, 0, 0),
    }
    values.update(overrides)
    return ActionItem(**values)


def pull_request(**overrides) -> PullRequest:
    values = {
        "id": "pr_184",
        "github_pr_number": 184,
        "repo": "web-app",
        "url": "https://github.com/example/web-app/pull/184",
        "title": "WEB-412 Add auth redirects",
        "description": "Implements auth redirects. Source: https://slack.example.com/thread/launch-auth",
        "author": owner(),
        "status": PullRequestStatus.OPEN,
        "review_status": ReviewStatus.REVIEW_REQUESTED,
        "reviewers": (ReviewerState(person=reviewer(), status="pending"),),
        "created_at": datetime(2026, 9, 12, 15, 0, 0),
        "updated_at": datetime(2026, 9, 10, 16, 0, 0),
    }
    values.update(overrides)
    return PullRequest(**values)


class TestPythonCore(TestCase):
    def test_resolves_feature_presentation_deadline(self):
        deadline = resolve_deadline(
            "before the feature presentation",
            NOW,
            [CalendarEvent("event_1", "Feature Presentation", datetime(2026, 9, 12, 18, 0, 0), datetime(2026, 9, 12, 19, 0, 0))],
        )

        assert deadline.resolved_at == datetime(2026, 9, 12, 18, 0, 0)
        assert deadline.confidence == Confidence.HIGH

    def test_extracts_slack_commitment_and_normalizes_action_item(self):
        commitment = extract_commitment(
            {
                "system": "slack",
                "text": "@rishikesh can you add auth redirects before the feature presentation? WEB-412 repo: web-app",
                "url": "https://slack.example.com/thread/launch-auth",
                "created_at": "2026-09-12T13:00:00Z",
            }
        )

        assert commitment is not None
        item = commitment_to_action_item(
            commitment,
            people=[owner()],
            events=[CalendarEvent("event_1", "Feature Presentation", datetime(2026, 9, 12, 18, 0, 0), datetime(2026, 9, 12, 19, 0, 0))],
            now=NOW,
            default_repo=None,
        )

        assert item.owner and item.owner.github_username == "rishikesh"
        assert item.jira.key == "WEB-412"
        assert item.expected_artifact.repo == "web-app"
        assert item.status == ActionItemStatus.AWAITING_PR

    def test_scores_high_confidence_pr_match(self):
        result = score_pull_request_match(action_item(), pull_request())

        assert result.confidence == "auto_match"
        assert "jira_key_match" in result.reasons

    def test_evaluation_matches_pr_and_flags_overdue_review(self):
        updated, follow_ups = run_watchdog_evaluation([action_item()], [pull_request()], datetime(2026, 9, 12, 18, 30, 0))

        assert updated[0].status == ActionItemStatus.AWAITING_REVIEW
        assert updated[0].matched_pr_ids == ("pr_184",)
        assert follow_ups[0].reason.value == "overdue_review"

    def test_missing_pr_generates_owner_follow_up(self):
        item = action_item(deadline=Deadline(datetime(2026, 9, 12, 13, 0, 0), "before standup", Confidence.HIGH))

        decisions = evaluate_action_item(item, NOW, [])

        assert decisions[0].reason.value == "missing_pr"
        assert decisions[0].channel.value == "slack_dm"

    def test_channel_falls_back_to_email_then_identity_mapping(self):
        assert choose_channel(reviewer()).value == "slack_dm"
        assert choose_channel(Person(id="p", display_name="No Slack", github_account_email="x@example.com")).value == "email"
        assert choose_channel(Person(id="p", display_name="Unknown")).value == "needs_identity_mapping"

    def test_sqlite_store_round_trips_action_items_prs_and_follow_ups(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(f"{tmp}/swewatchdog.db")
            store.init()
            item = action_item()
            pr = pull_request()
            decisions = evaluate_action_item(action_item(matched_pr_ids=("pr_184",)), NOW, [pr])

            store.save_people([owner(), reviewer()])
            store.save_action_item(item)
            store.save_pull_request(pr)
            assert store.save_follow_up(decisions[0]) is True

            assert store.list_action_items_raw()[0]["id"] == "ai_1"
            assert store.list_pull_requests_raw()[0]["id"] == "pr_184"
            assert store.list_follow_ups_raw()[0]["reason"] == "overdue_review"

    def test_sqlite_store_skips_duplicate_follow_up_signatures(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(f"{tmp}/swewatchdog.db")
            store.init()
            decision = evaluate_action_item(action_item(matched_pr_ids=("pr_184",)), NOW, [pull_request()])[0]

            assert store.save_follow_up(decision) is True
            assert store.save_follow_up(decision) is False
            assert len(store.list_follow_ups_raw()) == 1

    def test_sqlite_store_tracks_accounts_and_oauth_connections(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(f"{tmp}/swewatchdog.db")
            store.init()
            account = Account(id="acct_1", email="rishikesh@example.com", display_name="Rishikesh")
            connection = IntegrationConnection(
                id="conn_github_1",
                account_id="acct_1",
                provider=IntegrationProvider.GITHUB,
                status=IntegrationStatus.CONNECTED,
                scopes=("repo", "read:user"),
                workspace_id="example",
                connected_identity="rishikesh",
            )

            store.save_account(account)
            store.save_integration_connection(connection)

            assert store.list_accounts_raw()[0]["email"] == "rishikesh@example.com"
            assert store.list_integration_connections_raw()[0]["provider"] == "github"

    def test_integration_event_fixture_has_stable_identity(self):
        payload = load_json_fixture("fixtures/slack-message.json")

        first = integration_event_from_fixture(payload)
        second = integration_event_from_fixture(payload)

        assert first.id == second.id
        assert first.provider.value == "slack"
        assert first.kind.value == "slack_message"
        assert first.payload_hash == second.payload_hash

    def test_fixture_ingestion_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(f"{tmp}/swewatchdog.db")
            store.init()
            payload = load_json_fixture("fixtures/slack-message.json")

            assert _ingest_payload(store, payload) is True
            assert _ingest_payload(store, payload) is False

            assert len(store.list_integration_events_raw()) == 1
            assert len(store.list_action_items_raw()) == 1
            assert store.list_provider_cursors_raw()[0]["provider"] == "slack"

    def test_ingest_directory_and_summary(self):
        with TemporaryDirectory() as tmp:
            store = SQLiteStore(f"{tmp}/swewatchdog.db")
            store.init()

            accepted, skipped = _ingest_directory(store, Path("fixtures"))
            accepted_again, skipped_again = _ingest_directory(store, Path("fixtures"))
            summary = _summary(store)

            assert accepted == 3
            assert skipped == 0
            assert accepted_again == 0
            assert skipped_again == 3
            assert "SWEwatchdog summary" in summary
            assert "awaiting_review" in summary
            assert "Provider cursors:" in summary
