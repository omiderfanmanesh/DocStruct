from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Protocol, Sequence


PAGE_RX = re.compile(r"^(.*?)(?:\s+(\d{1,4}))?$")


@dataclass(frozen=True)
class Block:
    type: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Heading:
    kind: str
    key: str
    title: str
    page: int | None
    level: int
    confidence: float
    rule: str
    raw: str
    block_index: int
    numbering: tuple[int, ...] | None = None


@dataclass
class ClassifyContext:
    current_section_key: str | None = None
    current_article_num: int | None = None
    last_numbering: dict[tuple[int, ...], str] = field(default_factory=dict)


class HeadingRule(Protocol):
    name: str
    priority: int

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Heading | None:
        ...


def split_title_page(text: str) -> tuple[str, int | None]:
    normalized = " ".join(text.split()).strip()
    match = PAGE_RX.match(normalized)
    if not match:
        return normalized, None
    title = (match.group(1) or "").strip()
    page = match.group(2)
    return title, int(page) if page else None


class ArticleRule:
    name = "ArticleRule"
    priority = 10
    RX = re.compile(r"^(?:ART|Art|Artigo)\.??\s*(\d+)\b(.*)$", re.IGNORECASE)

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Heading | None:
        del ctx
        match = self.RX.match(block.text.strip())
        if not match:
            return None
        number = int(match.group(1))
        rest = (match.group(2) or "").strip()
        title, page = split_title_page(f"Art. {number} {rest}".strip())
        return Heading("article", f"ART:{number}", title, page, 2, 0.98, self.name, block.text, index)


class DecimalRule:
    name = "DecimalRule"
    priority = 20
    RX = re.compile(r"^(\d+(?:\.\d+)+)\s+(.*)$")

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Heading | None:
        match = self.RX.match(block.text.strip())
        if not match:
            return None
        number_str = match.group(1)
        remainder = match.group(2).strip()
        segments = tuple(int(part) for part in number_str.split("."))
        if ctx.current_article_num is not None and segments[0] != ctx.current_article_num:
            return None
        title, page = split_title_page(f"{number_str} {remainder}".strip())
        depth = len(segments) - 1
        level = min(2 + depth, 6)
        return Heading(
            "subsection",
            f"NUM:{number_str}",
            title,
            page,
            level,
            0.95,
            self.name,
            block.text,
            index,
            numbering=segments,
        )


class SectionRule:
    name = "SectionRule"
    priority = 5
    RX = re.compile(r"^SECTION\s+([IVXLCDM]+|\d+)\b(.*)$", re.IGNORECASE)

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Heading | None:
        del ctx
        match = self.RX.match(block.text.strip())
        if not match:
            return None
        section = match.group(1).upper()
        rest = (match.group(2) or "").strip()
        title, page = split_title_page(f"SECTION {section} {rest}".strip())
        return Heading("section", f"SEC:{section}", title, page, 1, 0.98, self.name, block.text, index)


class AnnexRule:
    name = "AnnexRule"
    priority = 6
    RX = re.compile(r"^ANNEX\s+([A-Z0-9]+)\b(.*)$", re.IGNORECASE)

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Heading | None:
        del ctx
        match = self.RX.match(block.text.strip())
        if not match:
            return None
        annex = match.group(1).upper()
        rest = (match.group(2) or "").strip()
        title, page = split_title_page(f"ANNEX {annex} {rest}".strip())
        return Heading("annex", f"ANNEX:{annex}", title, page, 1, 0.97, self.name, block.text, index)


class CapsTopicRule:
    name = "CapsTopicRule"
    priority = 50

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Heading | None:
        del ctx
        text = " ".join(block.text.split()).strip()
        if not (6 <= len(text) <= 60):
            return None
        if text.endswith("."):
            return None
        if not re.fullmatch(r"[A-Z0-9 ]+", text):
            return None
        return Heading("topic", f"TOPIC:{index}", text, None, 4, 0.6, self.name, block.text, index)


RULES: list[HeadingRule] = [
    SectionRule(),
    AnnexRule(),
    ArticleRule(),
    DecimalRule(),
    CapsTopicRule(),
]


class HeadingClassifier:
    def __init__(self, rules: Sequence[HeadingRule]):
        self.rules = sorted(rules, key=lambda rule: (rule.priority, rule.name))

    def classify(self, blocks: Sequence[Block]) -> list[Heading]:
        ctx = ClassifyContext()
        output: list[Heading] = []
        for index, block in enumerate(blocks):
            heading = None
            for rule in self.rules:
                heading = rule.match(block, index, ctx)
                if heading is not None:
                    break
            if heading is None:
                heading = Heading("unknown", f"UNK:{index}", block.text.strip(), None, 4, 0.1, "UnknownRule", block.text, index)
            output.append(heading)
            self._update_context(ctx, heading)
        return output

    def _update_context(self, ctx: ClassifyContext, heading: Heading) -> None:
        if heading.kind == "section":
            ctx.current_section_key = heading.key
            ctx.current_article_num = None
        elif heading.kind == "article":
            try:
                ctx.current_article_num = int(heading.key.split(":")[1])
            except Exception:
                ctx.current_article_num = None
        elif heading.kind == "subsection" and heading.numbering:
            ctx.last_numbering[heading.numbering] = heading.key


def make_classifier() -> HeadingClassifier:
    return HeadingClassifier(RULES)
