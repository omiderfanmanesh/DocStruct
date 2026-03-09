"""Tests for JSON loader module."""

import json
from pathlib import Path
import pytest

from miner_mineru.pipeline.json_loader import (
    load_mineru_json,
    save_cleaned_json,
    _extract_text_from_spans,
    _extract_min_confidence,
)


class TestTextExtraction:
    """Test text extraction from spans."""

    def test_extract_text_from_empty_lines(self):
        """Test extraction from empty lines."""
        result = _extract_text_from_spans([])
        assert result == ""

    def test_extract_text_from_single_span(self):
        """Test extraction from single span."""
        lines = [
            {
                "spans": [
                    {"content": "Hello"}
                ]
            }
        ]
        result = _extract_text_from_spans(lines)
        assert result == "Hello"

    def test_extract_text_from_multiple_spans(self):
        """Test extraction from multiple spans in single line."""
        lines = [
            {
                "spans": [
                    {"content": "Hello"},
                    {"content": "World"}
                ]
            }
        ]
        result = _extract_text_from_spans(lines)
        assert "Hello" in result and "World" in result

    def test_extract_confidence_from_spans(self):
        """Test confidence extraction from spans."""
        lines = [
            {
                "spans": [
                    {"content": "Hello", "score": 0.99},
                    {"content": "World", "score": 0.95}
                ]
            }
        ]
        result = _extract_min_confidence(lines)
        assert result == 0.95

    def test_extract_confidence_from_empty_lines(self):
        """Test confidence extraction from empty lines."""
        result = _extract_min_confidence([])
        assert result is None


class TestJSONLoader:
    """Test JSON loader."""

    def test_load_mineru_json_returns_document(self):
        """Test loading MinerU JSON returns Document."""
        json_file = Path("data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json")

        if not json_file.exists():
            pytest.skip("Test data file not found")

        doc = load_mineru_json(str(json_file))
        assert doc is not None
        assert doc.total_pages > 0
        assert len(doc.pages) > 0
        assert len(doc.get_all_blocks()) > 0

    def test_loaded_document_has_no_spatial_keys(self):
        """Test loaded document removes spatial keys."""
        json_file = Path("data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json")

        if not json_file.exists():
            pytest.skip("Test data file not found")

        doc = load_mineru_json(str(json_file))
        blocks = doc.get_all_blocks()

        # Check no spatial keys
        unnecessary_keys = {"bbox", "angle", "index"}

        for block in blocks:
            block_dict = block.to_dict()
            for key in unnecessary_keys:
                assert key not in block_dict, f"Found unexpected key: {key}"

    def test_loaded_document_preserves_block_types(self):
        """Test loaded document preserves all block types."""
        json_file = Path("data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json")

        if not json_file.exists():
            pytest.skip("Test data file not found")

        doc = load_mineru_json(str(json_file))
        blocks = doc.get_all_blocks()

        types = set(block.type.value for block in blocks)

        # Should have at least title and text
        assert "title" in types
        assert "text" in types

    def test_loaded_document_extracts_lists(self):
        """Test loaded document extracts list items."""
        json_file = Path("data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json")

        if not json_file.exists():
            pytest.skip("Test data file not found")

        doc = load_mineru_json(str(json_file))
        blocks = doc.get_all_blocks()

        list_blocks = [b for b in blocks if b.list_items]
        assert len(list_blocks) > 0, "Should have list blocks"

        for block in list_blocks:
            assert block.type.value == "list"
            assert len(block.list_items) > 0
            # Check structure of first item
            item = block.list_items[0]
            assert "index" in item
            assert "content" in item

    def test_loaded_document_extracts_tables(self):
        """Test loaded document extracts table content."""
        json_file = Path("data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json")

        if not json_file.exists():
            pytest.skip("Test data file not found")

        doc = load_mineru_json(str(json_file))
        blocks = doc.get_all_blocks()

        table_blocks = [b for b in blocks if b.table]
        assert len(table_blocks) > 0, "Should have table blocks"

        for block in table_blocks:
            assert block.type.value == "table"
            assert block.table is not None
            assert "html" in block.table

    def test_to_dict_output_clean(self):
        """Test to_dict output has only required keys."""
        json_file = Path("data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json")

        if not json_file.exists():
            pytest.skip("Test data file not found")

        doc = load_mineru_json(str(json_file))
        output = doc.to_dict()

        # Check metadata structure
        assert "metadata" in output
        assert "source_file" in output["metadata"]
        assert "total_pages" in output["metadata"]
        assert "total_blocks" in output["metadata"]

        # Check blocks structure
        assert "blocks" in output
        assert len(output["blocks"]) > 0

        # Check block keys
        for block in output["blocks"]:
            assert "type" in block
            # Other keys depend on block type
            allowed_keys = {"type", "content", "list", "table"}
            block_keys = set(block.keys())
            assert block_keys.issubset(allowed_keys), f"Unexpected keys: {block_keys - allowed_keys}"

    def test_save_and_load_roundtrip(self):
        """Test saving and reloading preserves content."""
        json_file = Path("data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json")

        if not json_file.exists():
            pytest.skip("Test data file not found")

        import tempfile

        # Load original
        doc1 = load_mineru_json(str(json_file))
        blocks1 = doc1.get_all_blocks()

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            temp_path = f.name
            output = doc1.to_dict()
            json.dump(output, f)

        try:
            # Load from temp file (note: we're loading JSON, not using json_loader which expects raw MinerU format)
            with open(temp_path, encoding='utf-8') as f:
                output_data = json.load(f)

            assert output_data["metadata"]["total_blocks"] == len(blocks1)
            assert len(output_data["blocks"]) == len(blocks1)

        finally:
            Path(temp_path).unlink()
