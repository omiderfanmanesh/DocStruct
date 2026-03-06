#!/bin/bash
#
# MinerU TOC Extraction
# Usage: ./scripts/run-extract.sh <markdown_file> [options]
#

set -e

# Configuration
MARKDOWN_FILE="$1"
OUTPUT_FILE=""
PROVIDER="${LLM_PROVIDER:-anthropic}"

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

# Show usage
usage() {
    cat << EOF
MinerU TOC Extraction

Usage: $0 <markdown_file> [options]

Options:
  -o, --output <file>   Output JSON file (default: output/<filename>.json)
  -p, --provider        LLM provider: anthropic or azure (default: anthropic)
  -h, --help           Show this help message

Environment:
  ANTHROPIC_API_KEY    API key for Anthropic (required for anthropic provider)
  LLM_PROVIDER         LLM provider (anthropic or azure)

Examples:
  $0 data/notice.md
  $0 data/notice.md -o output/notice_toc.json
  $0 data/notice.md --provider azure

EOF
    exit 1
}

# Parse arguments
if [ -z "$MARKDOWN_FILE" ] || [ "$MARKDOWN_FILE" = "-h" ] || [ "$MARKDOWN_FILE" = "--help" ]; then
    usage
fi

while [[ $# -gt 1 ]]; do
    case "$2" in
        -o|--output)
            OUTPUT_FILE="$3"
            shift 2
            ;;
        -p|--provider)
            PROVIDER="$3"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $2"
            exit 1
            ;;
    esac
done

# Main script
main() {
    log_section "MinerU TOC Extraction"

    # Validate markdown file
    if [ ! -f "$MARKDOWN_FILE" ]; then
        log_error "Markdown file not found: $MARKDOWN_FILE"
        exit 1
    fi

    log_success "Input: $(cd "$(dirname "$MARKDOWN_FILE")" && pwd)/$(basename "$MARKDOWN_FILE")"

    # Determine output file
    if [ -z "$OUTPUT_FILE" ]; then
        filename=$(basename "$MARKDOWN_FILE" .md)
        OUTPUT_FILE="output/${filename}.json"
    fi

    log_success "Output: $OUTPUT_FILE"

    # Create output directory
    output_dir=$(dirname "$OUTPUT_FILE")
    if [ ! -d "$output_dir" ]; then
        mkdir -p "$output_dir"
        log_info "Created output directory: $output_dir"
    fi

    # Set LLM provider
    log_info "Provider: $PROVIDER"
    export LLM_PROVIDER="$PROVIDER"

    # Validate API key
    if [ "$PROVIDER" = "anthropic" ]; then
        if [ -z "$ANTHROPIC_API_KEY" ]; then
            log_error "ANTHROPIC_API_KEY environment variable not set"
            log_info "Set it with: export ANTHROPIC_API_KEY='sk-ant-...'"
            exit 1
        fi
        log_success "Using Anthropic API"
    elif [ "$PROVIDER" = "azure" ]; then
        for var in AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_DEPLOYMENT; do
            if [ -z "${!var}" ]; then
                log_error "$var environment variable not set"
                exit 1
            fi
        done
        log_success "Using Azure OpenAI API"
    else
        log_error "Unknown provider: $PROVIDER"
        exit 1
    fi

    echo ""
    log_info "Starting extraction..."
    echo ""

    # Run extraction
    if python -m miner_mineru extract "$MARKDOWN_FILE" --output "$OUTPUT_FILE"; then
        echo ""
        log_success "Extraction completed successfully!"
        log_success "Output: $(cd "$(dirname "$OUTPUT_FILE")" && pwd)/$(basename "$OUTPUT_FILE")"

        # Show file size
        if [ -f "$OUTPUT_FILE" ]; then
            size=$(wc -c < "$OUTPUT_FILE")
            size_kb=$((size / 1024))
            log_info "File size: ${size_kb} KB"
        fi

        echo ""
        exit 0
    else
        echo ""
        log_error "Extraction failed"
        exit 1
    fi
}

# Run main
main
