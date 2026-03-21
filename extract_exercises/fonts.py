# -*- coding: utf-8 -*-
"""PIL fonts and drawing the page header band."""

import os

from PIL import Image, ImageDraw, ImageFont

from .config import EXAM_LABEL_FONT_PT, PROJECT_ROOT


def _lm_roman_paths(*, bold: bool) -> list[str]:
    """Latin Modern Roman (LaTeX ``lmodern`` / Computer Modern successor), bundled + TeX installs."""
    name = "lmroman10-bold.otf" if bold else "lmroman10-regular.otf"
    paths: list[str] = [str(PROJECT_ROOT / "fonts" / name)]
    for year in ("2025", "2024", "2023", "2022"):
        paths.append(f"/usr/local/texlive/{year}/texmf-dist/fonts/opentype/public/lm/{name}")
    paths.append(f"/usr/share/texmf/fonts/opentype/public/lm/{name}")
    return paths


def _try_truetype(paths: list[str], size_px: int) -> ImageFont.ImageFont | None:
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            if path.lower().endswith((".ttc", ".otc")):
                return ImageFont.truetype(path, size_px, index=0)
            return ImageFont.truetype(path, size_px)
        except OSError:
            continue
    return None


def pil_font(size_px: int) -> ImageFont.ImageFont:
    """Serif labels in bold weight: Latin Modern Roman bold, then regular, then system fonts."""
    f = _try_truetype(_lm_roman_paths(bold=True), size_px)
    if f is not None:
        return f
    f = _try_truetype(_lm_roman_paths(bold=False), size_px)
    if f is not None:
        return f
    fallbacks = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    f = _try_truetype(fallbacks, size_px)
    if f is not None:
        return f
    return ImageFont.load_default()


def pil_font_bold(size_px: int) -> ImageFont.ImageFont:
    """Same as ``pil_font`` for Latin Modern (bold OTF); extra sans-serif bold fallbacks."""
    f = _try_truetype(_lm_roman_paths(bold=True), size_px)
    if f is not None:
        return f
    fallbacks = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    f = _try_truetype(fallbacks, size_px)
    if f is not None:
        return f
    helv = "/System/Library/Fonts/Helvetica.ttc"
    if os.path.isfile(helv):
        try:
            return ImageFont.truetype(helv, size_px, index=1)
        except OSError:
            pass
    return pil_font(size_px)


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
