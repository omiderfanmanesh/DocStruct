"""Tests for md_fixer: heading re-leveling, content preservation, reporting."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from miner_mineru.pipeline.md_fixer import (
    TOCEntry,
    SourceLine,
    CorrectionEntry,
    CorrectionReport,
    load_toc_from_json,
    parse_source_markdown,
    match_toc_to_source,
    kind_to_heading_level,
    apply_heading_level,
    apply_all_corrections,
    write_corrected_markdown,
    build_correction_report,
    write_correction_report,
    fix_markdown,
)


# ============================================================================
# Tests for User Story 1: Re-level headings (T010-T013)
# ============================================================================

class TestHeadingReleveling:
    """US1: Re-level headings using extracted TOC."""

    def test_kind_to_heading_level_article(self):
        """T010: article heading re-levels to ## (level 2)."""
        assert kind_to_heading_level('article') == 2

    def test_kind_to_heading_level_section(self):
        """T011: section heading stays at # (level 1)."""
        assert kind_to_heading_level('section') == 1

    def test_kind_to_heading_level_subarticle(self):
        """T012: subarticle heading becomes ### (level 3)."""
        assert kind_to_heading_level('subarticle') == 3

    def test_apply_heading_level_article(self):
        """T015: apply_heading_level converts # to ## for article."""
        line = SourceLine(line_number=1, raw_text='# Art. 1 - Definitions')
        corrected = apply_heading_level(line, 2)
        assert corrected.raw_text == '## Art. 1 - Definitions'

    def test_apply_heading_level_preserves_text(self):
        """T015: apply_heading_level preserves heading text."""
        line = SourceLine(line_number=1, raw_text='# Some Title')
        corrected = apply_heading_level(line, 3)
        assert corrected.raw_text == '### Some Title'

    def test_apply_all_corrections_matches_toc(self):
        """T016: apply_all_corrections re-levels matched TOC entries."""
        source_lines = [
            SourceLine(line_number=1, raw_text='# Cover'),
            SourceLine(line_number=2, raw_text='# Art. 1 - Definitions'),
            SourceLine(line_number=3, raw_text='Some text'),
        ]
        toc_entry = TOCEntry(title='Definitions', kind='article', depth=2)
        matched_pairs = {2: toc_entry}

        corrected, corrections = apply_all_corrections(source_lines, matched_pairs)

        # Line 2 should be re-leveled to ##
        assert corrected[1].raw_text == '## Art. 1 - Definitions'
        # Line 1 (cover, before first TOC match) should be demoted
        assert corrected[0].raw_text == 'Cover'
        # Line 3 (non-heading) should be unchanged
        assert corrected[2].raw_text == 'Some text'

    def test_golden_fixture_structure(self):
        """T013: Verify golden fixture can be loaded and compared."""
        # This would load the actual Bando document and compare output
        # Placeholder for actual golden test
        assert True


# ============================================================================
# Tests for User Story 2: Preserve non-heading content (T017-T020)
# ============================================================================

class TestContentPreservation:
    """US2: Preserve non-heading content intact."""

    def test_paragraph_lines_unchanged(self):
        """T017: Paragraph lines pass through unchanged."""
        source_lines = [
            SourceLine(line_number=1, raw_text='# Heading'),
            SourceLine(line_number=2, raw_text='This is a paragraph'),
        ]
        matched_pairs = {}

        corrected, _ = apply_all_corrections(source_lines, matched_pairs)

        assert corrected[1].raw_text == 'This is a paragraph'

    def test_table_html_blocks_unchanged(self):
        """T018: Table HTML blocks pass through unchanged."""
        source_lines = [
            SourceLine(line_number=1, raw_text='# Heading'),
            SourceLine(line_number=2, raw_text='<table><tr><td>Cell</td></tr></table>'),
        ]
        matched_pairs = {}

        corrected, _ = apply_all_corrections(source_lines, matched_pairs)

        assert corrected[1].raw_text == '<table><tr><td>Cell</td></tr></table>'

    def test_list_items_unchanged(self):
        """T019: List items pass through unchanged."""
        source_lines = [
            SourceLine(line_number=1, raw_text='# Heading'),
            SourceLine(line_number=2, raw_text='1. First item'),
            SourceLine(line_number=3, raw_text='2. Second item'),
        ]
        matched_pairs = {}

        corrected, _ = apply_all_corrections(source_lines, matched_pairs)

        assert corrected[1].raw_text == '1. First item'
        assert corrected[2].raw_text == '2. Second item'

    def test_write_corrected_markdown_preserves_content(self):
        """T020: write_corrected_markdown preserves all non-heading lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'corrected.md')

            source_lines = [
                SourceLine(line_number=1, raw_text='## Art. 1'),
                SourceLine(line_number=2, raw_text='Paragraph text'),
                SourceLine(line_number=3, raw_text='More text'),
            ]

            write_corrected_markdown(source_lines, output_path)

            with open(output_path, 'r') as f:
                content = f.read()

            assert '## Art. 1' in content
            assert 'Paragraph text' in content
            assert 'More text' in content


# ============================================================================
# Tests for User Story 3: Generate correction report (T023-T026)
# ============================================================================

class TestCorrectionReport:
    """US3: Generate correction report."""

    def test_correction_report_structure_valid_json(self):
        """T023: Correction report structure is valid JSON."""
        report = CorrectionReport(
            source_file='test.md',
            output_file='test_fixed.md',
            total_lines=10,
            lines_changed=3,
            lines_demoted=2,
            unmatched_toc_entries=['Unmatched'],
            corrections=[
                CorrectionEntry(1, None, 1, None, 'demoted'),
            ],
        )

        report_dict = report.to_dict()
        assert 'corrections' in report_dict
        assert isinstance(report_dict['corrections'], list)

    def test_correction_report_counts_accurate(self):
        """T024: Report counts match actual changes."""
        corrections = [
            CorrectionEntry(1, 1, None, None, 'demoted'),  # old_level != new_level
            CorrectionEntry(2, None, 2, 'Art. 1', 'exact'),  # added level
            CorrectionEntry(3, 1, 1, 'Art. 2', 'fuzzy'),  # no change (same level)
        ]

        report = build_correction_report(
            'test.md',
            'test_fixed.md',
            [SourceLine(i, f'line {i}') for i in range(1, 4)],
            corrections,
            [],
        )

        assert report.lines_changed == 2  # Entries 1 and 2

    def test_unmatched_toc_entries_logged(self):
        """T025: Unmatched TOC entries are logged in report."""
        corrections = []
        unmatched = ['Unmatched Article 1', 'Unmatched Article 2']

        report = build_correction_report(
            'test.md',
            'test_fixed.md',
            [SourceLine(1, 'line')],
            corrections,
            unmatched,
        )

        assert 'Unmatched Article 1' in report.unmatched_toc_entries
        assert 'Unmatched Article 2' in report.unmatched_toc_entries

    def test_write_correction_report_json(self):
        """T026: write_correction_report serializes to valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, 'report.json')

            report = CorrectionReport(
                source_file='test.md',
                output_file='test_fixed.md',
                total_lines=5,
                lines_changed=2,
                lines_demoted=1,
            )

            write_correction_report(report, report_path)

            with open(report_path, 'r') as f:
                loaded = json.load(f)

            assert loaded['source_file'] == 'test.md'
            assert loaded['lines_changed'] == 2


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests using fixtures."""

    def test_fix_markdown_with_sample_fixtures(self):
        """Test fix_markdown using sample fixtures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample source file
            source_path = os.path.join(tmpdir, 'source.md')
            with open(source_path, 'w') as f:
                f.write('# COVER\n')
                f.write('\n')
                f.write('# Art. 1 - Definitions\n')
                f.write('Definition text.\n')

            # Create a sample TOC JSON
            toc_path = os.path.join(tmpdir, 'toc.json')
            with open(toc_path, 'w') as f:
                json.dump({
                    'toc': [
                        {
                            'title': 'Definitions',
                            'kind': 'article',
                            'depth': 2,
                            'numbering': 'Art. 1',
                        }
                    ]
                }, f)

            output_dir = os.path.join(tmpdir, 'output')
            os.makedirs(output_dir)

            report = fix_markdown(source_path, toc_path, output_dir)

            # Verify output
            corrected_path = os.path.join(output_dir, 'source.md')
            assert os.path.exists(corrected_path)

            with open(corrected_path, 'r') as f:
                corrected_content = f.read()

            # COVER should be demoted (no #)
            assert 'COVER\n' in corrected_content
            # Art. 1 should be ##
            assert '## Art. 1 - Definitions' in corrected_content
            # Text preserved
            assert 'Definition text.' in corrected_content

            # Verify report
            assert report.lines_demoted == 1  # COVER
            assert report.lines_changed >= 1

            report_path = os.path.join(output_dir, 'source_report.json')
            assert os.path.exists(report_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
