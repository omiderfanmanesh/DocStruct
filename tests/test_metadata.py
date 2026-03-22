"""Tests for US3 — document metadata extraction."""
from unittest.mock import MagicMock
import pytest

from docstruct.application.agents.metadata_agent import MetadataAgent
from docstruct.domain.models import DocumentMetadata


def extract_metadata(pre_toc_text, client):
    return MetadataAgent(client).run(pre_toc_text)


# ---------------------------------------------------------------------------
# T023 — unit test with mocked Claude API
# ---------------------------------------------------------------------------

def test_extract_metadata_returns_document_metadata():
    """extract_metadata() with mocked client returns a DocumentMetadata object."""
    mock_client = MagicMock()
    mock_client.create_message.return_value = '{"title": "Notice of competition", "source": "explicit", "year": "2025/26", "document_type": "Notice", "organization": "EDISU"}'

    result = extract_metadata("Header text", mock_client)
    assert isinstance(result, DocumentMetadata)
    assert result.title == "Notice of competition"
    assert result.source == "explicit"


def test_extract_metadata_handles_minimal_response():
    """extract_metadata() works with only title and source in response."""
    mock_client = MagicMock()
    mock_client.create_message.return_value = '{"title": "Test Document", "source": "inferred"}'

    result = extract_metadata("Some header", mock_client)
    assert isinstance(result, DocumentMetadata)
    assert result.title == "Test Document"
    assert result.source == "inferred"
    assert result.year is None
    assert result.document_type is None
    assert result.organization is None


def test_extract_metadata_handles_markdown_fenced_response():
    """extract_metadata() strips markdown code fences from response."""
    mock_client = MagicMock()
    mock_client.create_message.return_value = '```json\n{"title": "My Doc", "source": "explicit"}\n```'

    result = extract_metadata("Header", mock_client)
    assert result.title == "My Doc"


def test_extract_metadata_makes_one_api_call():
    """extract_metadata() makes exactly one API call."""
    mock_client = MagicMock()
    mock_client.create_message.return_value = '{"title": "Doc", "source": "inferred"}'

    extract_metadata("header text", mock_client)
    assert mock_client.create_message.call_count == 1


def test_extract_metadata_normalizes_blank_fields():
    mock_client = MagicMock()
    mock_client.create_message.return_value = '{"title": "", "source": "", "year": "", "document_type": "", "organization": ""}'

    result = extract_metadata("header text", mock_client)

    assert result.title == "Unknown"
    assert result.source == "inferred"
    assert result.year is None
    assert result.document_type is None
    assert result.organization is None
