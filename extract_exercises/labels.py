# -*- coding: utf-8 -*-
"""Exam / paper labels derived from filenames and job lists."""

import re
from pathlib import Path

from .config import PAGE_HEADER_BY_EXAM


def exam_label_from_filename(filename: str) -> str | None:
    """Return compact label like 'w24 21' from a PDF name, or None if pattern unknown."""
    stem = Path(filename).stem.lower()
    for pattern in (
        r"_([smw]\d{2})_qp_(\d+)",
        r"_([smw]\d{2})_ms_(\d+)",
        r"_([smw]\d{2})_ci_(\d+)",
    ):
        m = re.search(pattern, stem)
        if m:
            return f"{m.group(1)} {m.group(2)}"
    return None


def build_exam_header_label_from_paths(paths: list[str | None]) -> str:
    """Comma-separated labels for distinct exams (e.g. 'w24 21, s23 42')."""
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if not p:
            continue
        lab = exam_label_from_filename(Path(p).name)
        if lab and lab not in seen:
            seen.add(lab)
            out.append(lab)
    if out:
        return ", ".join(out)
    return "Extracted exercises"


def build_exam_header_label(question_paper_path: str, mark_scheme_path: str | None) -> str:
    return build_exam_header_label_from_paths([question_paper_path, mark_scheme_path])


def paper_label_from_qp_path(qp_path: str) -> str:
    """Short paper id from the question-paper filename only (e.g. ``w24 21``)."""
    lab = exam_label_from_filename(Path(qp_path).name)
    if lab:
        return lab
    stem = Path(qp_path).stem
    if stem:
        return stem
    name = Path(qp_path).name
    if name:
        return name
    return "Extracted exercises"


def page_header_label(jobs: list[dict], exam_key: str | None) -> str:
    """
    Single line repeated at the top of every output page.

    When ``exam_key`` maps to a subject title, that title is used and the session/paper id
    (e.g. ``s25 21``) is shown in the body via markers / sub-labels — not in this string.

    Legacy / unknown exam: one paper → filename-based paper code in the header; several papers
    → a generic label (paper codes still appear above each block when multiple jobs are used).
    """
    if exam_key and exam_key in PAGE_HEADER_BY_EXAM:
        return PAGE_HEADER_BY_EXAM[exam_key]
    if len(jobs) == 1:
        return paper_label_from_qp_path(jobs[0]["input_pdf"])
    return "Extracted exercises"
