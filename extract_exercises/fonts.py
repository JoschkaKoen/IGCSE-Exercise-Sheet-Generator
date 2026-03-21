# -*- coding: utf-8 -*-
"""PIL fonts and drawing the page header band."""

import os

from PIL import Image, ImageDraw, ImageFont

from .config import EXAM_LABEL_FONT_PT


def pil_font(size_px: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        try:
            if path.lower().endswith((".ttc", ".otc")):
                return ImageFont.truetype(path, size_px, index=0)
            return ImageFont.truetype(path, size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_page_header_pil(
    img: Image.Image,
    subject_label: str,
    paper_label: str | None,
    header_px: int,
    scale: float,
) -> None:
    """Draw the page header band: subject on line 1, paper code on line 2 (if provided)."""
    draw = ImageDraw.Draw(img)
    lines = [l for l in [subject_label, paper_label] if l and l.strip()]
    if not lines:
        return
    n = len(lines)
    slot_h = header_px // n
    size_px = max(10, min(int(EXAM_LABEL_FONT_PT * scale), slot_h - 4))
    font = pil_font(size_px)
    colors = [(40, 40, 40), (90, 90, 90)]
    for i, text in enumerate(lines):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (img.width - tw) // 2
        y = i * slot_h + max(0, (slot_h - th) // 2)
        draw.text((x, y), text, fill=colors[i % len(colors)], font=font)


def draw_exam_label_pil(img: Image.Image, label: str, header_h: int, scale: float) -> None:
    """Center a single exam label in the top ``header_h`` pixels (legacy single-line helper)."""
    draw_page_header_pil(img, label, None, header_h, scale)


def header_band_px(header_label: str | None, scale: float, has_paper_label: bool = False) -> int:
    if not (header_label or "").strip():
        return 0
    n_lines = 2 if has_paper_label else 1
    return int((EXAM_LABEL_FONT_PT * 2 * n_lines) * scale)
