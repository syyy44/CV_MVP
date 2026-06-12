"""OCR 文本后处理（规则优先，保持证据可溯源）。

原则：只做可预测、可复现的变换，便于与 evidence 逐字/近似匹配对齐。
LLM 润色应使用独立副本，不要覆盖 canonical raw_text。
"""

from __future__ import annotations

import re
import unicodedata

# 常见简历章节标题（Markdown 或纯文本）
_SECTION_MARKERS = (
    "个人总结",
    "教育经历",
    "荣誉奖项",
    "项目经历",
    "工作经历",
    "实习经历",
    "专业技能",
    "技能",
)


def nfkc_normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _strip_markdown_headers(line: str) -> str:
    return re.sub(r"^#+\s*", "", line).strip()


def trim_duplicate_prefix(text: str) -> str:
    """去掉 OCR 脚本误拼的「正文前缀重复」：保留首个结构化章节起点。"""
    lines = text.splitlines()
    name_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if re.match(r"^##\s+[\u4e00-\u9fa5]{2,4}\s*$", line.strip())
        ),
        None,
    )
    if name_idx is not None:
        return "\n".join(lines[name_idx:]).strip()

    for index, line in enumerate(lines):
        plain = _strip_markdown_headers(line.strip())
        if plain in _SECTION_MARKERS:
            return "\n".join(lines[index:]).strip()
    return text


def collapse_blank_lines(text: str, *, max_blank: int = 1) -> str:
    if max_blank < 1:
        return text
    pattern = r"\n{" + str(max_blank + 2) + r",}"
    replacement = "\n" * (max_blank + 1)
    return re.sub(pattern, replacement, text)


def join_cjk_line_breaks(text: str) -> str:
    """合并汉字之间的孤立换行（OCR 偶尔仍会有）。"""
    prev = None
    current = text
    while prev != current:
        prev = current
        current = re.sub(r"(?<=[\u4e00-\u9fff])\n(?=[\u4e00-\u9fff])", "", current)
    return current


def dedupe_paragraphs(text: str, *, min_len: int = 40) -> str:
    """去掉重复段落（版面+Markdown 双通道常见）。"""
    paragraphs = re.split(r"\n\s*\n", text)
    seen: set[str] = set()
    kept: list[str] = []
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        key = re.sub(r"\s+", "", stripped)
        if len(key) >= min_len and key in seen:
            continue
        if len(key) >= min_len:
            seen.add(key)
        kept.append(stripped)
    return "\n\n".join(kept)


def strip_markdown_heading_marks(text: str) -> str:
    """将 ## 标题转为【章节】行，便于下游 prompt 阅读。"""
    out: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^(#+)\s+(.*)$", line.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if level <= 2:
                out.append(f"【{title}】")
            else:
                out.append(title)
        else:
            out.append(line)
    return "\n".join(out)


def redact_contact_lines(text: str) -> str:
    """移除明显联系方式行（筛查场景减少 PII 进入 LLM）。"""
    out: list[str] = []
    email = re.compile(r"[@]")
    phone = re.compile(r"1[3-9]\d{9}")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if email.search(stripped) and phone.search(stripped):
            continue
        if phone.search(stripped) and "|" in stripped:
            continue
        if re.search(r"\d{2,3}岁\s*\|", stripped):
            continue
        out.append(line)
    return "\n".join(out)


def postprocess_ocr_text(
    text: str,
    *,
    trim_prefix: bool = True,
    nfkc: bool = False,
    join_cjk: bool = True,
    dedupe: bool = True,
    collapse_blanks: bool = True,
    strip_md: bool = True,
    redact_contacts: bool = False,
) -> str:
    """规则链后处理。默认保留联系方式（redact_contacts=False）以便审计对照。"""
    out = text
    if trim_prefix:
        out = trim_duplicate_prefix(out)
    if nfkc:
        out = nfkc_normalize(out)
    if join_cjk:
        out = join_cjk_line_breaks(out)
    if dedupe:
        out = dedupe_paragraphs(out)
    if collapse_blanks:
        out = collapse_blank_lines(out)
    if strip_md:
        out = strip_markdown_heading_marks(out)
    if redact_contacts:
        out = redact_contact_lines(out)
    return out.strip()
