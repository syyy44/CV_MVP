#!/usr/bin/env python3
"""试用百度千帆 PaddleOCR-VL，对比 PDF 文本提取效果。

用法:
  .venv/bin/python scripts/try_paddleocr_vl.py /path/to/resume.pdf
  .venv/bin/python scripts/try_paddleocr_vl.py /path/to/resume.pdf --compare

需在 .env 中设置 QIANFAN_API_KEY（Bearer 鉴权，勿提交到 git）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.workflows.paddle_ocr import (
    call_paddleocr_vl,
    extract_raw_markdown_pages,
    extract_text_from_response,
)
from app.workflows.parsing import _parse_pdf_local, normalize_text


def _metrics(text: str) -> dict:
    return {
        "chars": len(text),
        "lines": len(text.splitlines()),
        "cn_mid_breaks": len(re.findall(r"(?<=[\u4e00-\u9fff])\n(?=[\u4e00-\u9fff])", text)),
        "cn_space_splits": len(re.findall(r"[\u4e00-\u9fff] [\u4e00-\u9fff]", text)),
        "has_行业研究": "行业研究" in text,
        "has_实践经验": "实践经验" in text,
        "has_deepresearch": "金融 DeepResearch" in text or "DeepResearch" in text,
        "has_沈洋": "沈洋" in text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="试用千帆 PaddleOCR-VL 提取 PDF")
    parser.add_argument("pdf", type=Path, help="PDF 文件路径")
    parser.add_argument("--compare", action="store_true", help="与 pypdf 本地解析对比")
    parser.add_argument("--save-json", type=Path, help="保存完整 API 响应 JSON")
    parser.add_argument("--save-md", type=Path, help="保存 API 原始 markdown.text（未后处理）")
    parser.add_argument("--save-text", type=Path, help="保存后处理纯文本")
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"文件不存在: {args.pdf}", file=sys.stderr)
        return 1

    settings = get_settings()
    if not settings.qianfan_api_key:
        print("请在 .env 中设置 QIANFAN_API_KEY", file=sys.stderr)
        return 1

    data = args.pdf.read_bytes()
    print(f"调用 PaddleOCR-VL: {args.pdf.name} ({len(data) / 1024:.1f} KB)")
    payload = call_paddleocr_vl(
        data,
        settings.qianfan_api_key,
        timeout=settings.paddle_ocr_timeout_seconds,
    )
    text, pages = extract_text_from_response(payload)
    m = _metrics(text)

    print("\n=== PaddleOCR-VL ===")
    for k, v in m.items():
        print(f"  {k}: {v}")
    print(f"  pages: {len(pages)}")
    print(f"\n--- 预览 (前 1200 字) ---\n{text[:1200]}")

    if args.save_json:
        args.save_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n已保存 JSON: {args.save_json}")
    if args.save_md:
        md_pages = extract_raw_markdown_pages(payload)
        md_body = "\n\n---\n\n".join(
            f"<!-- page {index} -->\n{page}" for index, page in enumerate(md_pages, start=1)
        )
        args.save_md.parent.mkdir(parents=True, exist_ok=True)
        args.save_md.write_text(md_body, encoding="utf-8")
        print(f"已保存原始 Markdown: {args.save_md} ({len(md_pages)} 页)")
    if args.save_text:
        args.save_text.write_text(text, encoding="utf-8")
        print(f"已保存文本: {args.save_text}")

    if args.compare:
        status, pypdf_text, _pypdf_pages = _parse_pdf_local(data)
        print(f"\n=== pypdf (status={status}) ===")
        for k, v in _metrics(pypdf_text).items():
            print(f"  {k}: {v}")
        paddle_len = len(normalize_text(text))
        pypdf_len = len(normalize_text(pypdf_text))
        print(f"\n归一化后长度: paddle={paddle_len} pypdf={pypdf_len}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
