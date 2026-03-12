#!/usr/bin/env python3
"""
combine_pdf.py — Merge a return form PDF and a shipping label PDF onto one page.

Usage:
    python3 combine_pdf.py <return_form.pdf> <shipping_label.pdf> [output.pdf]

The return form is placed on the top portion of the page and the shipping
label is placed on the bottom portion, matching the Weekly Hype layout.

Requirements:
    pip install pymupdf reportlab Pillow
"""

import sys
import io
from pathlib import Path

import fitz  # pymupdf
from PIL import Image as PilImage
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


# ── layout constants ─────────────────────────────────────────────────────────
PAGE_W, PAGE_H    = letter     # 612 × 792 pts  (8.5 × 11 in)
MARGIN            = 18         # pts (~0.25 in) around each block
LABEL_H_RATIO     = 0.33       # shipping label = ~33 % of page height
GAP               = 10         # pts gap between form and label
RASTER_DPI        = 200        # render quality for source pages


def _pdf_page_to_png_bytes(pdf_path: str, page_index: int = 0,
                            dpi: int = RASTER_DPI) -> bytes:
    """Rasterise one page of a PDF to PNG bytes via pymupdf."""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


def _scale_to_fit(src_w: float, src_h: float,
                  box_w: float, box_h: float) -> tuple[float, float]:
    """Return (draw_w, draw_h) that fits src inside box, preserving aspect."""
    scale = min(box_w / src_w, box_h / src_h)
    return src_w * scale, src_h * scale


def combine(return_form_path: str,
            shipping_label_path: str,
            output_path: str = "combined_return.pdf") -> None:
    """Combine return form (top) and shipping label (bottom) onto one PDF page."""

    # ── destination zones ────────────────────────────────────────────────────
    label_zone_h = PAGE_H * LABEL_H_RATIO
    form_zone_h  = PAGE_H - label_zone_h - GAP

    # Each zone: (left_x, bottom_y, usable_width, usable_height)
    form_zone  = (MARGIN,
                  label_zone_h + GAP,
                  PAGE_W - 2 * MARGIN,
                  form_zone_h  - MARGIN)

    label_zone = (MARGIN,
                  MARGIN,
                  PAGE_W - 2 * MARGIN,
                  label_zone_h - MARGIN)

    # ── build canvas ─────────────────────────────────────────────────────────
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    for pdf_path, (zx, zy, zw, zh) in (
        (return_form_path,   form_zone),
        (shipping_label_path, label_zone),
    ):
        png = _pdf_page_to_png_bytes(pdf_path)
        img_buf = io.BytesIO(png)

        with PilImage.open(io.BytesIO(png)) as im:
            px_w, px_h = im.size

        draw_w, draw_h = _scale_to_fit(px_w, px_h, zw, zh)

        # Centre inside zone
        draw_x = zx + (zw - draw_w) / 2
        draw_y = zy + (zh - draw_h) / 2

        c.drawImage(ImageReader(img_buf), draw_x, draw_y, draw_w, draw_h,
                    preserveAspectRatio=True, mask="auto")

    # ── subtle separator line between the two sections ───────────────────────
    sep_y = label_zone_h + GAP / 2
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.setLineWidth(0.5)
    c.setDash(4, 4)
    c.line(MARGIN, sep_y, PAGE_W - MARGIN, sep_y)

    c.save()

    # ── write final PDF ───────────────────────────────────────────────────────
    buf.seek(0)
    # Re-open with pymupdf and save cleanly
    doc = fitz.open("pdf", buf.getvalue())
    doc.save(output_path, garbage=4, deflate=True)
    print(f"Saved: {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    return_form    = sys.argv[1]
    shipping_label = sys.argv[2]
    output         = sys.argv[3] if len(sys.argv) > 3 else "combined_return.pdf"

    for p in (return_form, shipping_label):
        if not Path(p).is_file():
            print(f"Error: file not found: {p}", file=sys.stderr)
            sys.exit(1)

    combine(return_form, shipping_label, output)
