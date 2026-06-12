#!/usr/bin/env python3
"""对 OCR 纯文本做规则后处理并输出对比指标。

  .venv/bin/python scripts/postprocess_ocr_text.py data/ocr_samples/沈洋简历_0526_paddleocr.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.workflows.ocr_postprocess import postprocess_ocr_text


def metrics(text: str) -> dict:
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return {
        "chars": len(text),
        "lines": len(text.splitlines()),
        "paragraphs": len(paras),
        "cn_mid_breaks": len(re.findall(r"(?<=[\u4e00-\u9fff])\n(?=[\u4e00-\u9fff])", text)),
        "duplicate_paras_est": len(paras) - len({re.sub(r'\s+', '', p) for p in paras if len(p) > 40}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--redact-contacts", action="store_true")
    args = parser.parse_args()

    raw = args.input.read_text(encoding="utf-8")
    cleaned = postprocess_ocr_text(raw, redact_contacts=args.redact_contacts)

    print("=== before ===")
    for k, v in metrics(raw).items():
        print(f"  {k}: {v}")
    print("=== after (rules) ===")
    for k, v in metrics(cleaned).items():
        print(f"  {k}: {v}")

    out = args.output or args.input.with_name(args.input.stem + "_cleaned.txt")
    out.write_text(cleaned, encoding="utf-8")
    print(f"\n已写入: {out}")
    print("\n--- 预览 (前 1500 字) ---\n")
    print(cleaned[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
