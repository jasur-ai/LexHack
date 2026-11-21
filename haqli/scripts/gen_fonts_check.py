#!/usr/bin/env python3
"""Verify that the PDF font resolved for ReportLab covers Uzbek Latin and Cyrillic glyphs (Ў Қ Ғ Ҳ)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engines.pdf.generator import REQUIRED_GLYPHS, check_font_glyph_coverage


def main() -> int:
    report = check_font_glyph_coverage()
    print(f"Font resolved: {report['font_name']} ({report['font_path']})")
    print(f"Required sample: {REQUIRED_GLYPHS}")
    print(f"Missing glyphs: {report['missing_glyphs']}")
    if not report["ok"]:
        print("FAIL: Install NotoSans-Regular.ttf into backend/app/engines/pdf/fonts/ for full Cyrillic support.")
        return 1
    print("OK: All required Latin + Uzbek Cyrillic glyphs are supported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
