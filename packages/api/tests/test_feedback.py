"""Tests for the feedback router and GitHub issue creation."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from lecturelink_api.routers.feedback import _create_github_issue


# ---------------------------------------------------------------------------
# App fixture with mocked auth + settings
# ---------------------------------------------------------------------------

@pytest.fixture
def _mock_settings():
    settings = MagicMock()
    settings.SUPABASE_URL = "https://test.supabase.co"
    settings.SUPABASE_ANON_KEY = "test-anon-key"
    settings.SUPABASE_SERVICE_KEY = "test-service-key"
    settings.GITHUB_TOKEN = "ghp_test_token"
    settings.GITHUB_FEEDBACK_REPO = "thivian17/LectureLink-2.0"
    settings.ENVIRONMENT = "test"
    settings.REDIS_URL = ""
    settings.GOOGLE_API_KEY = ""
    settings.GOOGLE_CLOUD_PROJECT = ""
    return settings


@pytest.fixture
def client(_mock_settings, test_user):
    from lecturelink_api.auth import get_current_user
    from lecturelink_api.config import get_settings
    from lecturelink_api.main import app

    app.dependency_overrides[get_current_user] = lambda: {**test_user, "token": "fake-token"}
    app.dependency_overrides[get_settings] = lambda: _mock_settings

    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/feedback
# ---------------------------------------------------------------------------

class TestSubmitFeedback:
    def test_valid_bug_submission(self, client, test_user):
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "fb-001"}]
        )
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        with (
            patch("lecturelink_api.auth.create_client", return_value=mock_sb), patch("lecturelink_api.routers.feedback.create_client", return_value=mock_sb),
            patch(
                "lecturelink_api.routers.feedback._create_github_issue",
                new_callable=AsyncMock,
                return_value="https://github.com/thivian17/LectureLink-2.0/issues/42",
            ),
        ):
            resp = client.post("/api/feedback", json={
                "type": "bug",
                "description": "The quiz page crashes when I click submit",
                "page_url": "https://lecturelink.app/quiz/123",
                "page_title": "Quiz - Thermo",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "fb-001"
        assert data["github_issue_url"] == "https://github.com/thivian17/LectureLink-2.0/issues/42"
        assert data["message"] == "Thank you for your feedback!"

    def test_invalid_type_rejects_422(self, client):
        with patch("lecturelink_api.auth.create_client", return_value=MagicMock()), patch("lecturelink_api.routers.feedback.create_client", return_value=MagicMock()):
            resp = client.post("/api/feedback", json={
                "type": "complaint",
                "description": "This is a long enough description",
                "page_url": "https://lecturelink.app/home",
            })
        assert resp.status_code == 422

    def test_description_too_short_rejects_422(self, client):
        with patch("lecturelink_api.auth.create_client", return_value=MagicMock()), patch("lecturelink_api.routers.feedback.create_client", return_value=MagicMock()):
            resp = client.post("/api/feedback", json={
                "type": "bug",
                "description": "short",
                "page_url": "https://lecturelink.app/home",
            })
        assert resp.status_code == 422

    def test_praise_skips_github_issue(self, client, test_user):
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "fb-002"}]
        )

        with (
            patch("lecturelink_api.auth.create_client", return_value=mock_sb), patch("lecturelink_api.routers.feedback.create_client", return_value=mock_sb),
            patch(
                "lecturelink_api.routers.feedback._create_github_issue",
                new_callable=AsyncMock,
            ) as mock_gh,
        ):
            resp = client.post("/api/feedback", json={
                "type": "praise",
                "description": "I love the study coach feature so much!",
                "page_url": "https://lecturelink.app/coach",
            })

        assert resp.status_code == 200
        mock_gh.assert_not_called()
        assert resp.json()["github_issue_url"] is None


# ---------------------------------------------------------------------------
# POST /api/feedback/upload-screenshot
# ---------------------------------------------------------------------------

class TestUploadScreenshot:
    def test_valid_png_upload(self, client, test_user):
        mock_sb = MagicMock()
        mock_sb.storage.from_.return_value.upload.return_value = None

        with patch("lecturelink_api.auth.create_client", return_value=mock_sb), patch("lecturelink_api.routers.feedback.create_client", return_value=mock_sb):
            resp = client.post(
                "/api/feedback/upload-screenshot",
                files={"file": ("screenshot.png", BytesIO(b"\x89PNG" + b"\x00" * 100), "image/png")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["storage_path"].startswith("feedback-screenshots/")
        assert data["storage_path"].endswith(".png")

    def test_oversized_file_rejects(self, client, test_user):
        # 6 MB payload
        big_content = b"\x00" * (6 * 1024 * 1024)

        with patch("lecturelink_api.auth.create_client", return_value=MagicMock()), patch("lecturelink_api.routers.feedback.create_client", return_value=MagicMock()):
            resp = client.post(
                "/api/feedback/upload-screenshot",
                files={"file": ("big.png", BytesIO(big_content), "image/png")},
            )

        assert resp.status_code == 413

    def test_invalid_content_type_rejects(self, client, test_user):
        with patch("lecturelink_api.auth.create_client", return_value=MagicMock()), patch("lecturelink_api.routers.feedback.create_client", return_value=MagicMock()):
            resp = client.post(
                "/api/feedback/upload-screenshot",
                files={"file": ("doc.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
            )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# _create_github_issue helper
# ---------------------------------------------------------------------------

class TestCreateGithubIssue:
    @pytest.mark.anyio
    async def test_returns_url_on_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "html_url": "https://github.com/thivian17/LectureLink-2.0/issues/99"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("lecturelink_api.routers.feedback.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            url = await _create_github_issue(
                feedback_id="fb-001",
                feedback_type="bug",
                description="Something is broken on the quiz page",
                page_url="https://lecturelink.app/quiz",
                browser_info={"user_agent": "Mozilla/5.0", "viewport_width": 1920, "viewport_height": 1080},
                console_errors=["TypeError: undefined is not a function"],
                github_token="ghp_test",
                repo="thivian17/LectureLink-2.0",
            )

        assert url == "https://github.com/thivian17/LectureLink-2.0/issues/99"

    @pytest.mark.anyio
    async def test_failure_raises(self):
        """GitHub API failure raises — the router catches this."""
        with patch("lecturelink_api.routers.feedback.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
            )
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.HTTPStatusError):
                await _create_github_issue(
                    feedback_id="fb-002",
                    feedback_type="feature",
                    description="Add dark mode to the dashboard page",
                    page_url="https://lecturelink.app/dashboard",
                    browser_info=None,
                    console_errors=None,
                    github_token="ghp_test",
                    repo="thivian17/LectureLink-2.0",
                )

    def test_github_failure_nonfatal_in_endpoint(self, client, test_user):
        """GitHub failure doesn't crash the feedback submission."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "fb-003"}]
        )

        with (
            patch("lecturelink_api.auth.create_client", return_value=mock_sb), patch("lecturelink_api.routers.feedback.create_client", return_value=mock_sb),
            patch(
                "lecturelink_api.routers.feedback._create_github_issue",
                new_callable=AsyncMock,
                side_effect=Exception("GitHub is down"),
            ),
        ):
            resp = client.post("/api/feedback", json={
                "type": "bug",
                "description": "Something is broken and GitHub is also down",
                "page_url": "https://lecturelink.app/quiz",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "fb-003"
        assert data["github_issue_url"] is None
