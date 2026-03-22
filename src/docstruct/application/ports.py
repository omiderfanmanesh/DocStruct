"""Application ports used for dependency inversion."""

from __future__ import annotations

from typing import Protocol


class LLMPort(Protocol):
    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        ...


class FileReaderPort(Protocol):
    def read_lines(self, path: str) -> list[str]:
        ...
