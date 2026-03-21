# -*- coding: utf-8 -*-
"""Paths and numeric constants for PDF extraction and layout."""

from pathlib import Path

# Project root: parent of this package (the "Exercise Sheet Generator" folder).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Natural-language mode lists both exam folders; the AI picks one subject per run.
OUTPUT_DIR = PROJECT_ROOT / "output"

_PROJECT_PARENT = PROJECT_ROOT.parent
PHYSICS_EXAM_DIR = _PROJECT_PARENT / "IGCSE Physics 25" / "Previous Exams IGCSE Physics"
COMPUTER_SCIENCE_EXAM_DIR = (
    _PROJECT_PARENT / "IGCSE Computer Science 25" / "Previous Exams IGCSE Computer Science"
)

EXAM_ROOT_BY_KEY = {
    "physics": PHYSICS_EXAM_DIR,
    "computer_science": COMPUTER_SCIENCE_EXAM_DIR,
}

# Rasterization resolution for pixmap → image → JPEG pages.
DPI = 1200

HEADER_ZONE_MAX_Y_PT = 110.0
STRIP_CROP_LEFT_PT = 45.0
STRIP_CROP_RIGHT_PT = 22.0
STRIP_CROP_TOP_PT = 8.0

MS_LANDSCAPE_H_THRESHOLD_PT = 700.0
MS_FOOTER_TOP_PT = 540.0
MS_HEADER_BOTTOM_PT = 72.0
MS_TABLE_LEFT_PT = 62.0
MS_MARKS_START_PT = 737.0
MS_LANDSCAPE_MARGIN_PT = 50.0

QR_MAX_SIZE_PT = 90.0
QR_MARGIN_ZONE_PT = 90.0

MARGIN_TOP = 55
MARGIN_BOTTOM = 790
QUESTION_X_MAX = 60
PADDING_ABOVE = 8
A4_WIDTH_PT = 595.0
A4_HEIGHT_PT = 842.0

EXAM_LABEL_FONT_PT = 11

PAGE_HEADER_BY_EXAM = {
    "physics": "IGCSE Physics",
    "computer_science": "IGCSE Computer Science",
}
