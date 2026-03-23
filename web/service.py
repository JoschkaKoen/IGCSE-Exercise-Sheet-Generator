# -*- coding: utf-8 -*-
"""Run the same NL → extraction flow as the CLI (for the web worker thread)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from extract_exercises.natural_language import resolve_natural_language
from extract_exercises.output_paths import resolve_output_path
from extract_exercises.pipeline import run_extraction_jobs


def run_nl_prompt(
    prompt: str,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[Path, Path | None]:
    """
    Resolve natural language, run extraction jobs, return main PDF path and optional answers PDF.

    When ``on_progress`` is set (web UI), each user-visible line is pushed to the callback
    **and** printed — no reliance on stdout redirection in threads.

    Answers PDF is returned only when that file exists on disk (mark scheme path produced output).
    """

    def emit(msg: str) -> None:
        print(msg, flush=True)
        if on_progress:
            on_progress(msg)

    emit("Resolving natural-language request…")
    exam_root, data = resolve_natural_language(prompt, on_progress=on_progress)
    emit(f"Exam folder: {exam_root} ({data.get('exam', '')})")
    emit(f"Papers in this run: {len(data['extractions'])}")
    jobs = []
    for ex in data["extractions"]:
        jobs.append(
            {
                "input_pdf": str(exam_root / ex["input_pdf"]),
                "questions": ex["questions"],
                "mark_scheme_pdf": str(exam_root / ex["mark_scheme_pdf"])
                if ex.get("mark_scheme_pdf")
                else None,
            }
        )
    emit("Preparing output and extracting PDFs…")

    def extract_phase() -> str:
        output_pdf = resolve_output_path(data["output_pdf"])
        output_str = str(output_pdf)
        run_extraction_jobs(jobs, output_str, exam_key=data.get("exam"))
        return output_str

    if on_progress:
        from .process_log import run_with_last_log_line

        output_str = run_with_last_log_line(extract_phase, on_progress)
    else:
        output_str = extract_phase()

    out_path = Path(output_str)
    answers_path = out_path.parent / f"{out_path.stem}_answers{out_path.suffix}"
    if answers_path.is_file():
        return out_path, answers_path
    return out_path, None


def run_nl_prompt_logged(
    prompt: str,
    on_line: Callable[[str], None],
) -> tuple[Path, Path | None]:
    """Web worker entry: same as ``run_nl_prompt`` with live progress lines."""
    return run_nl_prompt(prompt, on_progress=on_line)


def list_library_pdfs() -> dict[str, list[dict[str, str]]]:
    """Scan bundled exam dirs; return { subject_key: [{ name, download_url }, ...] }."""
    from urllib.parse import quote

    from extract_exercises.config import EXAM_ROOT_BY_KEY

    out: dict[str, list[dict[str, str]]] = {}
    for key, root in EXAM_ROOT_BY_KEY.items():
        if not root.is_dir():
            out[key] = []
            continue
        names = sorted(p.name for p in root.glob("*.pdf"))
        out[key] = [
            {"name": n, "download_url": f"/api/library/{key}/{quote(n, safe='')}"}
            for n in names
        ]
    return out
