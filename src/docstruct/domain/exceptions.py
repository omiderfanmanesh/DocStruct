"""Unified exception hierarchy for DocStruct."""


class DocStructError(Exception):
    """Base exception for docstruct."""


class TOCExtractionError(DocStructError):
    """Error during TOC extraction."""


class BoundaryDetectionError(TOCExtractionError):
    """Error detecting TOC boundaries."""


class ClassificationError(TOCExtractionError):
    """Error classifying TOC entries."""


class MetadataExtractionError(TOCExtractionError):
    """Error extracting document metadata."""


class MarkdownError(DocStructError):
    """Error processing markdown files."""


class HeadingCorrectionError(MarkdownError):
    """Error correcting heading levels."""


class MarkdownParsingError(MarkdownError):
    """Error parsing markdown content."""


class JSONError(DocStructError):
    """Error processing JSON files."""


class JSONParsingError(JSONError):
    """Error parsing JSON file."""


class JSONValidationError(JSONError):
    """Error validating JSON structure."""


class BlockExtractionError(JSONError):
    """Error extracting blocks from JSON."""


class ConfigError(DocStructError):
    """Error with configuration."""


class ConfigValidationError(ConfigError):
    """Error validating configuration."""


class ProviderError(DocStructError):
    """Error with LLM provider."""


class ProviderConnectionError(ProviderError):
    """Error connecting to LLM provider."""


class ProviderAuthError(ProviderError):
    """Error authenticating with LLM provider."""


class EmbeddingError(DocStructError):
    """Error with embedding generation."""


class EmbeddingDimensionError(EmbeddingError):
    """Error: embedding vector dimension mismatch with index."""


__all__ = [
    "BlockExtractionError",
    "BoundaryDetectionError",
    "ClassificationError",
    "ConfigError",
    "ConfigValidationError",
    "DocStructError",
    "EmbeddingDimensionError",
    "EmbeddingError",
    "HeadingCorrectionError",
    "JSONError",
    "JSONParsingError",
    "JSONValidationError",
    "MarkdownError",
    "MarkdownParsingError",
    "MetadataExtractionError",
    "ProviderAuthError",
    "ProviderConnectionError",
    "ProviderError",
    "TOCExtractionError",
]

