"""Application ports used for dependency inversion."""

from __future__ import annotations

from typing import Any, Protocol


class LLMPort(Protocol):
    supports_structured_output: bool

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        ...

    def create_structured_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        schema: Any,
    ) -> Any:
        ...


class FileReaderPort(Protocol):
    def read_lines(self, path: str) -> list[str]:
        ...
