from __future__ import annotations

from app.workflows.ocr_postprocess import (
    dedupe_paragraphs,
    join_cjk_line_breaks,
    postprocess_ocr_text,
    trim_duplicate_prefix,
)


def test_trim_duplicate_prefix_keeps_structured_section():
    raw = "乱序片段\n第二行\n## 沈洋\n\n## 个人总结\n内容"
    out = trim_duplicate_prefix(raw)
    assert out.startswith("## 沈洋")
    assert "乱序片段" not in out


def test_join_cjk_line_breaks():
    assert join_cjk_line_breaks("行业研\n究") == "行业研究"


def test_dedupe_paragraphs():
    para = (
        "设计并实现一套证据驱动的多智能体投研报告生成系统，"
        "构建了从用户问题到研究报告输出的端到端闭环。"
    )
    raw = f"{para}\n\n{para}"
    out = dedupe_paragraphs(raw)
    assert out == para


def test_postprocess_pipeline():
    raw = "## 个人总结\n\n经验\n\n经验\n\n行研\n究"
    out = postprocess_ocr_text(raw, trim_prefix=False)
    assert "【个人总结】" in out
    assert "行研究" in out or "行业研究" in join_cjk_line_breaks("行研\n究")
