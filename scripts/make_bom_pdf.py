"""Typeset the bill of materials as docs/bill-of-materials.pdf.

The content is the appendix_bom() section of the submission report, so the
standalone PDF and Appendix A of the report cannot drift apart. The source of
record for the words is docs/bill-of-materials.md.

    python scripts/make_bom_pdf.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

import make_report as R

OUT = R.ROOT / "docs" / "bill-of-materials.pdf"


def build():
    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=23 * mm, rightMargin=23 * mm,
                          topMargin=20 * mm, bottomMargin=20 * mm,
                          title="Bill of materials - " + R.TITLE,
                          author="Capstone Project")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="body")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                       onPage=R.decorate)])
    f = []
    R.appendix_bom(f, standalone=True)
    doc.build(f)
    kb = OUT.stat().st_size / 1024
    print(f"  wrote {OUT.relative_to(R.ROOT)}  {kb:.0f} kB")


if __name__ == "__main__":
    build()
