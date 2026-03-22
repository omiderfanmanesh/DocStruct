"""Build a nested heading tree from flat HeadingEntry objects."""

from __future__ import annotations

import copy

from docstruct.domain.models import HeadingEntry


def build_heading_map(flat_entries: list[HeadingEntry]) -> list[HeadingEntry]:
    roots: list[HeadingEntry] = []
    stack: list[HeadingEntry] = []
    for entry in flat_entries:
        node = copy.copy(entry)
        node.children = []
        while stack and stack[-1].depth >= node.depth:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots
