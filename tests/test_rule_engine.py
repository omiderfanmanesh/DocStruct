from docstruct.pipeline.rule_engine import (
    ArticleRule,
    Block,
    CapsTopicRule,
    ClassifyContext,
    DecimalRule,
    make_classifier,
)


def test_article_rule_match():
    block = Block(type="title", text="Art. 10 Admissions and Fees")
    rule = ArticleRule()
    ctx = ClassifyContext()
    h = rule.match(block, 0, ctx)
    assert h is not None
    assert h.kind == "article"
    assert h.key == "ART:10"
    assert "Art." in h.title or "10" in h.title


def test_decimal_rule_match_and_numbering():
    block = Block(type="title", text="2.1 Admission requirements")
    rule = DecimalRule()
    ctx = ClassifyContext()
    h = rule.match(block, 1, ctx)
    assert h is not None
    assert h.kind == "subsection"
    assert h.key.startswith("NUM:2.1")
    assert h.numbering == (2, 1)


def test_decimal_rule_respects_current_article():
    block = Block(type="title", text="3.1 Something else")
    rule = DecimalRule()
    ctx = ClassifyContext(current_article_num=2)
    h = rule.match(block, 2, ctx)
    assert h is None


def test_caps_topic_rule_match():
    block = Block(type="title", text="ADMISSIONS")
    rule = CapsTopicRule()
    ctx = ClassifyContext()
    h = rule.match(block, 3, ctx)
    assert h is not None
    assert h.kind == "topic"


def test_classifier_integration():
    blocks = [
        Block(type="header", text="SECTION I GENERAL"),
        Block(type="title", text="Art. 2 Eligibility"),
        Block(type="title", text="2.1 Eligible candidates"),
        Block(type="title", text="APPLICATIONS"),
    ]
    clf = make_classifier()
    out = clf.classify(blocks)
    assert len(out) == 4
    assert out[0].kind == "section"
    assert out[1].kind == "article"
    assert out[2].kind == "subsection"
    assert out[3].kind in ("topic", "unknown")
