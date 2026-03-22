"""Unit tests for find_toc_boundaries() — LLM-agent based detection."""
import json
import pytest
from unittest.mock import MagicMock
from docstruct.application.agents.boundary_agent import BoundaryAgent


def find_toc_boundaries(lines, client):
    boundary, _ = BoundaryAgent(client).run(lines)
    return boundary


def _lines(text: str) -> list[str]:
    return [l + "\n" for l in text.splitlines()]


def _mock_client(responses: list[dict]):
    """Return a mock client that yields successive JSON responses."""
    calls = [0]

    def side_effect(**kwargs):
        n = calls[0]
        calls[0] += 1
        resp = responses[n] if n < len(responses) else {"toc_start": -1, "toc_end": -1, "status": "searching"}
        return json.dumps(resp)

    client = MagicMock()
    client.create_message.side_effect = side_effect
    return client


def test_table_of_contents_marker():
    lines = _lines("# Intro\n\nsome text\n\n# TABLE OF CONTENTS\n\nArt. 1 Title 5\n\n# SECTION I")
    client = _mock_client([{"toc_start": 4, "toc_end": 6, "status": "done"}])
    result = find_toc_boundaries(lines, client)
    assert result is not None
    assert result.start_line == 4
    assert result.end_line == 6


def test_summary_marker():
    lines = _lines("# Notice\n\npreamble\n\n# Summary\n\nArt. 1 Title 5\n\n# SECTION I Body")
    client = _mock_client([{"toc_start": 4, "toc_end": 6, "status": "done"}])
    result = find_toc_boundaries(lines, client)
    assert result is not None
    assert result.start_line == 4


def test_sommario_marker():
    lines = _lines("# Bando\n\n# Sommario\n\n1.1 Titolo 3\n\n# SEZIONE I")
    client = _mock_client([{"toc_start": 2, "toc_end": 4, "status": "done"}])
    result = find_toc_boundaries(lines, client)
    assert result is not None
    assert result.start_line == 2


def test_case_insensitive():
    lines = _lines("# TABLE OF CONTENTS\n\nArt. 1 5\n\n# Body")
    client = _mock_client([{"toc_start": 0, "toc_end": 2, "status": "done"}])
    result = find_toc_boundaries(lines, client)
    assert result is not None


def test_no_marker_returns_none():
    lines = _lines("# Introduction\n\nSome text without any TOC.\n\n# SECTION I\n\nContent.")
    client = _mock_client([{"toc_start": -1, "toc_end": -1, "status": "searching"}])
    result = find_toc_boundaries(lines, client)
    assert result is None


def test_empty_file_returns_none():
    client = _mock_client([])
    result = find_toc_boundaries([], client)
    assert result is None


def test_marker_at_first_line():
    lines = _lines("# Summary\n\nArt. 1 Title 5\n\n# SECTION I Body starts here")
    client = _mock_client([{"toc_start": 0, "toc_end": 2, "status": "done"}])
    result = find_toc_boundaries(lines, client)
    assert result is not None
    assert result.start_line == 0


def test_duplicate_markers_uses_first():
    lines = _lines("# Summary\n\nArt. 1 5\n\n# Summary\n\nArt. 2 6\n\n# Body")
    client = _mock_client([{"toc_start": 0, "toc_end": 6, "status": "done"}])
    result = find_toc_boundaries(lines, client)
    assert result is not None
    assert result.start_line == 0


def test_end_line_before_next_h1():
    lines = _lines(
        "# Preamble\n"
        "\n"
        "# TABLE OF CONTENTS\n"
        "\n"
        "Art. 1 Title 5\n"
        "Art. 2 Title 6\n"
        "\n"
        "# SECTION I\n"
        "\n"
        "Body content here.\n"
    )
    # Agent says TOC ends at line 5 (Art. 2 Title 6), before # SECTION I at line 7
    client = _mock_client([{"toc_start": 2, "toc_end": 5, "status": "done"}])
    result = find_toc_boundaries(lines, client)
    assert result is not None
    section_line = next(i for i, l in enumerate(lines) if l.strip() == "# SECTION I")
    assert result.end_line < section_line


def test_toc_spans_two_chunks(monkeypatch):
    """TOC starts in chunk 1, ends in chunk 2 — agent returns in_toc then done."""
    # Create 150 lines: TOC starts at line 5, ends at line 110
    lines = [f"line {i}\n" for i in range(150)]
    client = _mock_client([
        {"toc_start": 5, "toc_end": -1, "status": "in_toc"},   # chunk 0-99
        {"toc_start": -1, "toc_end": 110, "status": "done"},   # chunk 100-149
    ])
    # patch chunk size to 100 for this test
    import docstruct.application.agents.boundary_agent as mod
    original = mod._CHUNK_SIZE
    mod._CHUNK_SIZE = 100
    try:
        result = find_toc_boundaries(lines, client)
    finally:
        mod._CHUNK_SIZE = original
    assert result is not None
    assert result.start_line == 5
    assert result.end_line == 110
