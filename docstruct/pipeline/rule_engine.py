from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple
import re


PAGE_RX = re.compile(r"^(.*?)(?:\s+(\d{1,4}))?$")


@dataclass(frozen=True)
class Block:
    type: str
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Heading:
    kind: str
    key: str
    title: str
    page: Optional[int]
    level: int
    confidence: float
    rule: str
    raw: str
    block_index: int
    numbering: Optional[Tuple[int, ...]] = None


@dataclass
class ClassifyContext:
    current_section_key: Optional[str] = None
    current_article_num: Optional[int] = None
    last_numbering: Dict[Tuple[int, ...], str] = field(default_factory=dict)


class HeadingRule(Protocol):
    name: str
    priority: int

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Optional[Heading]:
        ...


def split_title_page(text: str) -> tuple[str, Optional[int]]:
    t = " ".join(text.split()).strip()
    m = PAGE_RX.match(t)
    if not m:
        return t, None
    title = (m.group(1) or "").strip()
    page = m.group(2)
    return title, int(page) if page else None


class ArticleRule:
    name = "ArticleRule"
    priority = 10
    RX = re.compile(r"^(?:ART|Art|Artigo)\.??\s*(\d+)\b(.*)$", re.IGNORECASE)

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Optional[Heading]:
        m = self.RX.match(block.text.strip())
        if not m:
            return None
        n = int(m.group(1))
        rest = (m.group(2) or "").strip()
        title_raw = f"Art. {n} {rest}".strip()
        title, page = split_title_page(title_raw)
        return Heading(
            kind="article",
            key=f"ART:{n}",
            title=title,
            page=page,
            level=2,
            confidence=0.98,
            rule=self.name,
            raw=block.text,
            block_index=index,
        )


class DecimalRule:
    name = "DecimalRule"
    priority = 20
    RX = re.compile(r"^(\d+(?:\.\d+)+)\s+(.*)$")

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Optional[Heading]:
        m = self.RX.match(block.text.strip())
        if not m:
            return None
        num_str = m.group(1)
        remainder = m.group(2).strip()
        segments = tuple(int(x) for x in num_str.split("."))
        if ctx.current_article_num is not None and segments[0] != ctx.current_article_num:
            return None
        title_raw = f"{num_str} {remainder}".strip()
        title, page = split_title_page(title_raw)
        depth = len(segments) - 1
        level = min(2 + depth, 6)
        return Heading(
            kind="subsection",
            key=f"NUM:{num_str}",
            title=title,
            page=page,
            level=level,
            confidence=0.95,
            rule=self.name,
            raw=block.text,
            block_index=index,
            numbering=segments,
        )


class SectionRule:
    name = "SectionRule"
    priority = 5
    RX = re.compile(r"^SECTION\s+([IVXLCDM]+|\d+)\b(.*)$", re.IGNORECASE)

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Optional[Heading]:
        m = self.RX.match(block.text.strip())
        if not m:
            return None
        sec = m.group(1).upper()
        rest = (m.group(2) or "").strip()
        title_raw = f"SECTION {sec} {rest}".strip()
        title, page = split_title_page(title_raw)
        return Heading("section", f"SEC:{sec}", title, page, 1, 0.98, self.name, block.text, index)


class AnnexRule:
    name = "AnnexRule"
    priority = 6
    RX = re.compile(r"^ANNEX\s+([A-Z0-9]+)\b(.*)$", re.IGNORECASE)

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Optional[Heading]:
        m = self.RX.match(block.text.strip())
        if not m:
            return None
        a = m.group(1).upper()
        rest = (m.group(2) or "").strip()
        title_raw = f"ANNEX {a} {rest}".strip()
        title, page = split_title_page(title_raw)
        return Heading("annex", f"ANNEX:{a}", title, page, 1, 0.97, self.name, block.text, index)


class CapsTopicRule:
    name = "CapsTopicRule"
    priority = 50

    def match(self, block: Block, index: int, ctx: ClassifyContext) -> Optional[Heading]:
        t = " ".join(block.text.split()).strip()
        if not (6 <= len(t) <= 60):
            return None
        if t.endswith("."):
            return None
        if not re.fullmatch(r"[A-Z0-9 ]+", t):
            return None
        return Heading("topic", f"TOPIC:{index}", t, None, 4, 0.6, self.name, block.text, index)


RULES: List[HeadingRule] = [
    SectionRule(),
    AnnexRule(),
    ArticleRule(),
    DecimalRule(),
    CapsTopicRule(),
]


class HeadingClassifier:
    def __init__(self, rules: Sequence[HeadingRule]):
        self.rules = sorted(rules, key=lambda r: (r.priority, r.name))

    def classify(self, blocks: Sequence[Block]) -> List[Heading]:
        ctx = ClassifyContext()
        out: List[Heading] = []
        for i, b in enumerate(blocks):
            heading = None
            for rule in self.rules:
                heading = rule.match(b, i, ctx)
                if heading is not None:
                    break
            if heading is None:
                heading = Heading(
                    kind="unknown",
                    key=f"UNK:{i}",
                    title=b.text.strip(),
                    page=None,
                    level=4,
                    confidence=0.1,
                    rule="UnknownRule",
                    raw=b.text,
                    block_index=i,
                )
            out.append(heading)
            self._update_context(ctx, heading)
        return out

    def _update_context(self, ctx: ClassifyContext, h: Heading) -> None:
        if h.kind == "section":
            ctx.current_section_key = h.key
            ctx.current_article_num = None
        elif h.kind == "article":
            try:
                ctx.current_article_num = int(h.key.split(":")[1])
            except Exception:
                ctx.current_article_num = None
        elif h.kind == "subsection" and h.numbering:
            ctx.last_numbering[h.numbering] = h.key


def make_classifier() -> HeadingClassifier:
    return HeadingClassifier(RULES)
