"""Tests for syllabus status endpoint — validates Gap 1 fix.

The status endpoint must read the actual `status` column instead of
deriving status from `needs_review`. Key regression: after processing
completes, status='processed' + needs_review=True must return 'complete'.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.conftest import mock_chain


class TestSyllabusStatusProgression:
    """Verify the status endpoint reads the actual status column."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_pending_after_creation(self, client):
        """Newly created syllabus with status='pending' returns 'processing'."""
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(
                [{"id": sid, "status": "pending", "needs_review": True}]
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processing"
        assert data["needs_review"] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_processing_during_pipeline(self, client):
        """During pipeline run: status='processing' returns 'processing'."""
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(
                [{"id": sid, "status": "processing", "needs_review": False}]
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_complete_after_processing(self, client):
        """KEY REGRESSION: status='processed' + needs_review=True → 'complete'.

        Before the fix, the endpoint derived status from needs_review,
        so this case would incorrectly return 'processing'.
        """
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(
                [{"id": sid, "status": "processed", "needs_review": True}]
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["needs_review"] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_complete_after_review(self, client):
        """After review: status='processed' + needs_review=False → 'complete'."""
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(
                [{"id": sid, "status": "processed", "needs_review": False}]
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["needs_review"] is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_error_on_failure(self, client):
        """Pipeline failure: status='error' → 'error'."""
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(
                [{"id": sid, "status": "error", "needs_review": True}]
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_not_found(self, client):
        """Unknown syllabus returns 404."""
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 404
