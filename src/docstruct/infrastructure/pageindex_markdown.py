"""Minimal markdown-only PageIndex runtime vendored into DocStruct.

This module is adapted from the markdown tree-building logic in the upstream
PageIndex repository, trimmed to the subset DocStruct needs:
- markdown heading parsing
- heading-to-tree conversion
- stable node ids
- deterministic output formatting

It intentionally excludes the unused PDF, config, and LLM-summary code paths.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any


_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_CODE_BLOCK_RE = re.compile(r"^```")


def _extract_nodes_from_markdown(markdown_content: str) -> tuple[list[dict[str, Any]], list[str]]:
    node_list: list[dict[str, Any]] = []
    lines = markdown_content.split("\n")
    in_code_block = False

    for line_num, line in enumerate(lines, start=1):
        stripped_line = line.strip()
        if _CODE_BLOCK_RE.match(stripped_line):
            in_code_block = not in_code_block
            continue
        if not stripped_line or in_code_block:
            continue

        match = _HEADER_RE.match(stripped_line)
        if match:
            node_list.append({"node_title": match.group(2).strip(), "line_num": line_num})

    return node_list, lines


def _extract_node_text_content(
    node_list: list[dict[str, Any]],
    markdown_lines: list[str],
) -> list[dict[str, Any]]:
    all_nodes: list[dict[str, Any]] = []
    for node in node_list:
        line_content = markdown_lines[node["line_num"] - 1]
        header_match = re.match(r"^(#{1,6})", line_content)
        if header_match is None:
            continue

        all_nodes.append(
            {
                "title": node["node_title"],
                "line_num": node["line_num"],
                "level": len(header_match.group(1)),
            }
        )

    for index, node in enumerate(all_nodes):
        start_line = node["line_num"] - 1
        end_line = all_nodes[index + 1]["line_num"] - 1 if index + 1 < len(all_nodes) else len(markdown_lines)
        node["text"] = "\n".join(markdown_lines[start_line:end_line]).strip()

    return all_nodes


def _build_tree_from_nodes(node_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not node_list:
        return []

    stack: list[tuple[dict[str, Any], int]] = []
    root_nodes: list[dict[str, Any]] = []
    node_counter = 1

    for node in node_list:
        current_level = node["level"]
        tree_node = {
            "title": node["title"],
            "node_id": str(node_counter).zfill(4),
            "text": node["text"],
            "line_num": node["line_num"],
            "nodes": [],
        }
        node_counter += 1

        while stack and stack[-1][1] >= current_level:
            stack.pop()

        if not stack:
            root_nodes.append(tree_node)
        else:
            parent_node, _ = stack[-1]
            parent_node["nodes"].append(tree_node)

        stack.append((tree_node, current_level))

    return root_nodes


def _write_node_id(data: dict[str, Any] | list[dict[str, Any]], node_id: int = 0) -> int:
    if isinstance(data, dict):
        data["node_id"] = str(node_id).zfill(4)
        node_id += 1
        if "nodes" in data:
            node_id = _write_node_id(data["nodes"], node_id)
        return node_id

    for item in data:
        node_id = _write_node_id(item, node_id)
    return node_id


def _reorder_dict(data: dict[str, Any], key_order: list[str]) -> dict[str, Any]:
    return {key: data[key] for key in key_order if key in data}


def _format_structure(structure: dict[str, Any] | list[dict[str, Any]], order: list[str]) -> Any:
    if isinstance(structure, dict):
        structure_copy = deepcopy(structure)
        if "nodes" in structure_copy:
            structure_copy["nodes"] = _format_structure(structure_copy["nodes"], order)
        if not structure_copy.get("nodes"):
            structure_copy.pop("nodes", None)
        return _reorder_dict(structure_copy, order)
    return [_format_structure(item, order) for item in structure]


def build_markdown_tree(markdown_path: str) -> dict[str, Any]:
    markdown_file = Path(markdown_path)
    markdown_content = markdown_file.read_text(encoding="utf-8")

    node_list, markdown_lines = _extract_nodes_from_markdown(markdown_content)
    nodes_with_content = _extract_node_text_content(node_list, markdown_lines)
    tree_structure = _build_tree_from_nodes(nodes_with_content)
    _write_node_id(tree_structure)
    tree_structure = _format_structure(
        tree_structure,
        ["title", "node_id", "text", "line_num", "nodes"],
    )

    return {
        "doc_name": markdown_file.stem,
        "structure": tree_structure,
    }
