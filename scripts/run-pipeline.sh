#!/bin/bash
#
# MinerU Complete Pipeline - Extract TOC and Fix Markdown
# Usage: ./scripts/run-pipeline.sh [options]
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${DATA_DIR:-data}"
OUTPUT_DIR="${OUTPUT_DIR:-output}"
FIXED_DIR="${FIXED_DIR:-output/fixed}"
PROVIDER="${LLM_PROVIDER:-anthropic}"
SKIP_EXTRACTION="${SKIP_EXTRACTION:-false}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
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
    echo -e "${MAGENTA}$1${NC}"
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
        --provider)
            PROVIDER="$2"
            shift 2
            ;;
        --skip-extraction)
            SKIP_EXTRACTION=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

show_help() {
    cat << EOF
MinerU Complete Pipeline

Usage: $0 [options]

Options:
  --data-dir <path>      Directory with markdown files (default: data)
  --output-dir <path>    Directory for TOC files (default: output)
  --provider <provider>  LLM provider: anthropic or azure (default: anthropic)
  --skip-extraction      Skip step 1, only run fixer
  -h, --help            Show this help message

Environment:
  ANTHROPIC_API_KEY     API key for Anthropic
  LLM_PROVIDER          LLM provider (anthropic or azure)

Examples:
  $0                              # Full pipeline
  $0 --skip-extraction            # Only fix (no extraction)
  $0 --provider azure             # Use Azure

EOF
    exit 0
}

# Main script
main() {
    cd "$REPO_ROOT"

    log_section "MinerU Complete Pipeline"

    # Step 1: Extract TOC
    if [ "$SKIP_EXTRACTION" != "true" ]; then
        log_section "Step 1: Extract TOC from Markdown Files"

        # Find markdown files
        log_info "Scanning for markdown files in: $DATA_DIR"
        mapfile -t md_files < <(find "$DATA_DIR" -name "MinerU_markdown*.md" -type f | sort)

        if [ ${#md_files[@]} -eq 0 ]; then
            log_error "No markdown files found in: $DATA_DIR"
            exit 1
        fi

        log_success "Found ${#md_files[@]} markdown file(s)"
        echo ""

        # Create output directory
        mkdir -p "$OUTPUT_DIR"

        # Set provider
        export LLM_PROVIDER="$PROVIDER"

        # Validate API key for Anthropic
        if [ "$PROVIDER" = "anthropic" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
            log_error "ANTHROPIC_API_KEY environment variable not set"
            exit 1
        fi

        local extracted=0
        local failed=0

        for md_file in "${md_files[@]}"; do
            md_name=$(basename "$md_file")
            output_path="$OUTPUT_DIR/$(basename "$md_file" .md).json"

            echo "Processing: $md_name"

            # Skip if already extracted
            if [ -f "$output_path" ]; then
                log_info "Already extracted (skipping)"
                ((extracted++))
                echo ""
                continue
            fi

            # Run extraction
            if python -m miner_mineru extract "$md_file" --output "$output_path" 2>&1 | grep -E "INFO:|Extraction complete" || true; then
                log_success "Extracted"
                ((extracted++))
            else
                log_error "Failed"
                ((failed++))
            fi

            echo ""
        done

        log_success "Extraction complete: $extracted/${#md_files[@]} successful"
        if [ $failed -gt 0 ]; then
            log_warning "$failed file(s) failed"
        fi

        echo ""
    fi

    # Step 2: Fix Markdown
    log_section "Step 2: Fix Heading Levels"
    echo ""

    # Run fixer script
    fixer_script="$SCRIPT_DIR/run-fixer.sh"

    if [ ! -f "$fixer_script" ]; then
        log_error "Fixer script not found: $fixer_script"
        exit 1
    fi

    bash "$fixer_script" --data-dir "$DATA_DIR" --output-dir "$OUTPUT_DIR" --fixed-dir "$FIXED_DIR"
    fix_exit_code=$?

    # Final summary
    echo ""
    log_section "Pipeline Complete"

    if [ $fix_exit_code -eq 0 ]; then
        log_success "All steps completed successfully!"
        echo ""
        log_info "Next steps:"
        log_info "  1. Review corrected markdown files:"
        echo "     ls -lh output/fixed/*.md"
        echo ""
        log_info "  2. Check correction reports:"
        echo "     ls -lh output/fixed/*_report.json"
        echo ""
        exit 0
    else
        log_warning "Pipeline completed with errors"
        exit 1
    fi
}

# Run pipeline
main
