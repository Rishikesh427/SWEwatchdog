from unittest import TestCase

from swewatchdog.web import render_dashboard


class TestWebDashboard(TestCase):
    def test_dashboard_renders_core_sections(self):
        page = render_dashboard(
            {
                "github_auth": {"authenticated": True, "source": "gh"},
                "repos": [{"repo": "Rishikesh427/ClimateGuard", "provider": "github", "active": 1}],
                "cursors": [{"provider": "github", "last_seen_at": "2026-09-12T15:00:00"}],
                "action_items": [],
                "pull_requests": [],
                "follow_ups": [],
            }
        )

        assert "SWEwatchdog" in page
        assert "Action Items" in page
        assert "Pull Requests" in page
        assert "Rishikesh427/ClimateGuard" in page
