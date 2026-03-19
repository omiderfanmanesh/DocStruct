"""
Unified exception hierarchy for docstruct.

Covers both TOC extraction and JSON processing.
"""


class DocStructError(Exception):
    """Base exception for docstruct."""
    pass


# TOC/Extraction Exceptions
class TOCExtractionError(DocStructError):
    """Error during TOC extraction."""
    pass


class BoundaryDetectionError(TOCExtractionError):
    """Error detecting TOC boundaries."""
    pass


class ClassificationError(TOCExtractionError):
    """Error classifying TOC entries."""
    pass


class MetadataExtractionError(TOCExtractionError):
    """Error extracting document metadata."""
    pass


# Markdown Processing Exceptions
class MarkdownError(DocStructError):
    """Error processing markdown files."""
    pass


class HeadingCorrectionError(MarkdownError):
    """Error correcting heading levels."""
    pass


class MarkdownParsingError(MarkdownError):
    """Error parsing markdown content."""
    pass


# JSON Processing Exceptions
class JSONError(DocStructError):
    """Error processing JSON files."""
    pass


class JSONParsingError(JSONError):
    """Error parsing JSON file."""
    pass


class JSONValidationError(JSONError):
    """Error validating JSON structure."""
    pass


class BlockExtractionError(JSONError):
    """Error extracting blocks from JSON."""
    pass


# Configuration Exceptions
class ConfigError(DocStructError):
    """Error with configuration."""
    pass


class ConfigValidationError(ConfigError):
    """Error validating configuration."""
    pass


# Provider Exceptions
class ProviderError(DocStructError):
    """Error with LLM provider."""
    pass


class ProviderConnectionError(ProviderError):
    """Error connecting to LLM provider."""
    pass


class ProviderAuthError(ProviderError):
    """Error authenticating with LLM provider."""
    pass


__all__ = [
    "DocStructError",
    "TOCExtractionError",
    "BoundaryDetectionError",
    "ClassificationError",
    "MetadataExtractionError",
    "MarkdownError",
    "HeadingCorrectionError",
    "MarkdownParsingError",
    "JSONError",
    "JSONParsingError",
    "JSONValidationError",
    "BlockExtractionError",
    "ConfigError",
    "ConfigValidationError",
    "ProviderError",
    "ProviderConnectionError",
    "ProviderAuthError",
]
