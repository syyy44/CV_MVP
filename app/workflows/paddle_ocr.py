"""百度千帆 PaddleOCR-VL PDF 文本提取。"""

from __future__ import annotations

import base64
import re

import httpx

from app.workflows.ocr_postprocess import postprocess_ocr_text

API_URL = "https://qianfan.baidubce.com/v2/ocr/paddleocr"
MODEL = "paddleocr-vl-0.9b"


def strip_markdown_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&nbsp;", " ").strip()


def call_paddleocr_vl(
    data: bytes,
    api_key: str,
    *,
    timeout: float = 120.0,
) -> dict:
    body = {
        "model": MODEL,
        "file": base64.b64encode(data).decode("ascii"),
        "fileType": 0,
        "useLayoutDetection": True,
        "useDocOrientationClassify": True,
        "useDocUnwarping": False,
        "useChartRecognition": False,
        "layoutNms": True,
        "visualize": False,
        "temperature": 0,
    }
    response = httpx.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    payload = response.json()
    if "error" in payload:
        err = payload["error"]
        raise RuntimeError(f"{err.get('code')}: {err.get('message')}")
    return payload


def extract_raw_markdown_pages(payload: dict) -> list[str]:
    pages: list[str] = []
    for item in (payload.get("result") or {}).get("layoutParsingResults") or []:
        md = (item.get("markdown") or {}).get("text") or ""
        if md:
            pages.append(md)
    if not pages:
        raise RuntimeError("paddle OCR 响应中无 markdown.text")
    return pages


def extract_text_from_response(payload: dict) -> tuple[str, list[str]]:
    """从 API 响应提取按页纯文本（剥离 HTML + 规则后处理）。"""
    pages: list[str] = []
    for item in (payload.get("result") or {}).get("layoutParsingResults") or []:
        markdown = (item.get("markdown") or {}).get("text") or ""
        md_plain = strip_markdown_html(markdown) if markdown else ""
        if md_plain:
            pages.append(md_plain)
            continue

        pruned = item.get("prunedResult") or {}
        blocks = pruned.get("parsing_res_list") or []
        keep_labels = {
            "text",
            "paragraph",
            "paragraph_title",
            "title",
            "header",
            "footer",
            "doc_title",
            "abstract",
        }
        text_blocks = [
            (b.get("block_order"), b.get("block_content", ""))
            for b in blocks
            if (b.get("block_label") in keep_labels or b.get("block_label") is None)
            and (b.get("block_content") or "").strip()
        ]
        text_blocks.sort(key=lambda x: (x[0] is None, x[0] if x[0] is not None else 9999))
        fallback = "\n".join(content.strip() for _, content in text_blocks).strip()
        if fallback:
            pages.append(fallback)

    if not pages:
        raise RuntimeError("paddle OCR 响应中无可用文本")

    raw = "\n\n".join(p for p in pages if p).strip()
    return postprocess_ocr_text(raw), pages
