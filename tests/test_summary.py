"""Tests for US2 — AI-based document summary generation."""
from unittest.mock import MagicMock
import pytest

from docstruct.agents.summary_agent import SummaryAgent


def generate_summary(pre_toc_text, toc_text, client):
    return SummaryAgent(client).run(pre_toc_text, toc_text)


# ---------------------------------------------------------------------------
# T018 — unit test with mocked Claude API
# ---------------------------------------------------------------------------

def test_generate_summary_returns_non_empty_string():
    """generate_summary() with mocked client returns a non-empty string."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="This is a notice of competition. It covers scholarships and accommodation.")
    ]

    result = generate_summary("Header text", "TOC text", mock_client)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_summary_calls_api_once():
    """generate_summary() makes exactly one API call."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="Summary sentence one. Summary sentence two.")
    ]

    generate_summary("pre_toc", "toc", mock_client)
    assert mock_client.messages.create.call_count == 1


def test_generate_summary_passes_content_to_api():
    """generate_summary() includes pre_toc and toc text in the API prompt."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="Result summary.")
    ]

    generate_summary("UNIQUE_HEADER_TOKEN", "UNIQUE_TOC_TOKEN", mock_client)

    call_args = mock_client.messages.create.call_args
    prompt = call_args[1]["messages"][0]["content"]
    assert "UNIQUE_HEADER_TOKEN" in prompt
    assert "UNIQUE_TOC_TOKEN" in prompt
