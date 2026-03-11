"""Tests for the material text extraction agent."""

from __future__ import annotations

from unittest.mock import patch

import pytest

_MOD = "lecturelink_api.agents.material_extractor"


class TestExtractMaterialText:
    @pytest.mark.asyncio
    async def test_rejects_unsupported_extension(self):
        from lecturelink_api.agents.material_extractor import (
            MaterialExtractionError,
            extract_material_text,
        )

        with pytest.raises(MaterialExtractionError, match="Unsupported"):
            await extract_material_text("http://example.com/file.exe", ".exe")

    @pytest.mark.asyncio
    @patch(f"{_MOD}._extract_from_pdf")
    async def test_routes_pdf_to_pdf_extractor(self, mock_pdf):
        from lecturelink_api.agents.material_extractor import extract_material_text

        mock_pdf.return_value = {
            "full_text": "hello",
            "page_count": 1,
            "sections": [],
            "preview": "hello",
        }
        result = await extract_material_text("http://example.com/file.pdf", ".pdf")
        mock_pdf.assert_called_once()
        assert result["full_text"] == "hello"

    @pytest.mark.asyncio
    @patch(f"{_MOD}._extract_from_text")
    async def test_routes_txt_to_text_extractor(self, mock_txt):
        from lecturelink_api.agents.material_extractor import extract_material_text

        mock_txt.return_value = {
            "full_text": "plain text",
            "page_count": None,
            "sections": [],
            "preview": "plain text",
        }
        await extract_material_text("http://example.com/file.txt", ".txt")
        mock_txt.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{_MOD}._extract_from_text")
    async def test_routes_md_to_text_extractor(self, mock_txt):
        from lecturelink_api.agents.material_extractor import extract_material_text

        mock_txt.return_value = {
            "full_text": "# Markdown",
            "page_count": None,
            "sections": [],
            "preview": "# Markdown",
        }
        await extract_material_text("http://example.com/file.md", ".md")
        mock_txt.assert_called_once()
