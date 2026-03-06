#!/bin/bash
#
# MinerU Markdown Fixer - Normalize heading levels
# Usage: ./scripts/run-fixer.sh [options]
#

set -e

# Configuration
DATA_DIR="${DATA_DIR:-.}"
OUTPUT_DIR="${OUTPUT_DIR:-output}"
FIXED_DIR="${FIXED_DIR:-output/fixed}"
VERBOSE="${VERBOSE:-false}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_section() {
    echo ""
    echo "================================================================================"
    echo -e "${CYAN}$1${NC}"
    echo "================================================================================"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --fixed-dir)
            FIXED_DIR="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main script
main() {
    log_section "MinerU Markdown Fixer - Normalize Heading Levels"

    # Check data directory
    if [ ! -d "$DATA_DIR" ]; then
        log_error "Data directory not found: $DATA_DIR"
        exit 1
    fi

    # Find markdown files
    log_info "Scanning for markdown files in: $DATA_DIR"
    mapfile -t md_files < <(find "$DATA_DIR" -name "MinerU_markdown*.md" -type f | sort)

    if [ ${#md_files[@]} -eq 0 ]; then
        log_error "No MinerU markdown files found in: $DATA_DIR"
        exit 1
    fi

    log_success "Found ${#md_files[@]} markdown file(s)"
    echo ""

    # Find TOC files
    log_info "Scanning for TOC files in: $OUTPUT_DIR"
    if [ ! -d "$OUTPUT_DIR" ]; then
        log_error "Output directory not found: $OUTPUT_DIR"
        exit 1
    fi

    mapfile -t toc_files < <(find "$OUTPUT_DIR" -maxdepth 1 -name "*.json" ! -name "*_report.json" -type f | sort)

    if [ ${#toc_files[@]} -eq 0 ]; then
        log_error "No TOC JSON files found in: $OUTPUT_DIR"
        log_info "Please extract TOC files first using:"
        log_info "  python -m miner_mineru extract <markdown_file> --output output/<name>.json"
        exit 1
    fi

    log_success "Found ${#toc_files[@]} TOC file(s)"
    echo ""

    # Match files
    declare -a pairs_md
    declare -a pairs_toc
    declare -a skipped

    for md_file in "${md_files[@]}"; do
        md_name=$(basename "$md_file" .md)
        found=false

        # Look for exact match
        for toc_file in "${toc_files[@]}"; do
            toc_name=$(basename "$toc_file" .json)
            if [ "$md_name" = "$toc_name" ]; then
                pairs_md+=("$md_file")
                pairs_toc+=("$toc_file")
                found=true
                break
            fi
        done

        # Look for partial match
        if [ "$found" = false ]; then
            for toc_file in "${toc_files[@]}"; do
                toc_name=$(basename "$toc_file" .json)
                if [[ "$md_name" == "$toc_name"* ]]; then
                    pairs_md+=("$md_file")
                    pairs_toc+=("$toc_file")
                    found=true
                    break
                fi
            done
        fi

        if [ "$found" = false ]; then
            skipped+=("$(basename "$md_file")")
        fi
    done

    # Show skipped files
    if [ ${#skipped[@]} -gt 0 ]; then
        log_warning "Skipping ${#skipped[@]} file(s) without matching TOC:"
        for file in "${skipped[@]}"; do
            echo "  - $file"
        done
        echo ""
    fi

    if [ ${#pairs_md[@]} -eq 0 ]; then
        log_error "No markdown/TOC pairs found to process"
        exit 1
    fi

    log_info "Processing ${#pairs_md[@]} file pair(s):"
    echo ""

    # Create fixed directory
    mkdir -p "$FIXED_DIR"

    # Process each pair
    local successful=0
    local failed=0

    for i in "${!pairs_md[@]}"; do
        md_file="${pairs_md[$i]}"
        toc_file="${pairs_toc[$i]}"

        echo "================================================================================"
        echo "[$((i + 1))/${#pairs_md[@]}] Processing"
        echo "================================================================================"
        echo ""

        md_name=$(basename "$md_file")
        toc_name=$(basename "$toc_file")

        log_info "File: $md_name"
        log_info "TOC:  $toc_name"
        echo ""

        # Run fixer
        log_info "Running markdown fixer..."

        if python -m miner_mineru fix "$md_file" --toc "$toc_file" --output-dir "$FIXED_DIR" 2>&1 | grep -E "INFO:|Lines changed" || true; then
            log_success "Completed"
            ((successful++))

            # Show report
            md_stem=$(basename "$md_file" .md)
            report_file="$FIXED_DIR/${md_stem}_report.json"

            if [ -f "$report_file" ]; then
                log_info "Results:"
                if command -v jq &> /dev/null; then
                    echo "  Total lines:         $(jq -r '.total_lines' "$report_file")"
                    echo "  Lines changed:       $(jq -r '.lines_changed' "$report_file")"
                    echo "  Lines demoted:       $(jq -r '.lines_demoted' "$report_file")"
                    echo "  Unmatched TOC items: $(jq -r '.unmatched_toc_entries | length' "$report_file")"
                else
                    echo "  Report: $report_file"
                fi
            fi
        else
            log_error "Failed"
            ((failed++))
        fi

        echo ""
    done

    # Summary
    log_section "Pipeline Complete"
    log_success "Successful: $successful/${#pairs_md[@]}"
    if [ $failed -gt 0 ]; then
        log_warning "Failed: $failed/${#pairs_md[@]}"
    fi
    echo ""
    log_info "Output directory: $(cd "$FIXED_DIR" && pwd)"
    log_info "Reports:         $FIXED_DIR/*_report.json"
    echo ""

    if [ $failed -gt 0 ]; then
        exit 1
    fi
}

# Run main
main
