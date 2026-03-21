# -*- coding: utf-8 -*-
"""Natural language → extraction options (xAI / Grok, OpenAI-compatible API)."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import EXAM_ROOT_BY_KEY, PROJECT_ROOT

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _load_env():
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(Path.cwd() / ".env")


def _list_pdf_names(exam_root: Path):
    if not exam_root.is_dir():
        return []
    return sorted(p.name for p in exam_root.glob("*.pdf"))


def resolve_natural_language(instruction: str) -> tuple[Path, dict]:
    """Call AI; return (exam_root, data) with ``data[\"extractions\"]`` and ``output_pdf``."""
    if OpenAI is None:
        print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    _load_env()
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("Set XAI_API_KEY in .env (next to this script or cwd).", file=sys.stderr)
        sys.exit(1)

    catalogs = {}
    for key, root in EXAM_ROOT_BY_KEY.items():
        names = _list_pdf_names(root)
        catalogs[key] = {"root": root, "pdfs": names}

    total_pdfs = sum(len(c["pdfs"]) for c in catalogs.values())
    if total_pdfs == 0:
        print("No PDFs found in either exam folder:", file=sys.stderr)
        for key, c in catalogs.items():
            print(f"  {key}: {c['root']}", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("XAI_MODEL", "grok-4-1-fast-non-reasoning")
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    system = (
        "You map the user's request to extraction options for Cambridge-style exam PDFs. "
        "Two subjects are available: physics and computer_science. "
        "Respond with a single JSON object only, no markdown fences.\n"
        "Always include: "
        '\"exam\": \"physics\" or \"computer_science\", '
        '\"output_pdf\": short descriptive name ending in .pdf, '
        "and EITHER a single-paper shape OR a multi-paper shape:\n"
        "  • Single paper: "
        '\"input_pdf\", \"questions\" (array of integers), \"mark_scheme_pdf\" (string or null).\n'
        "  • Multiple papers (different qp files in one run): use "
        '\"extractions\": array of objects, each with '
        '\"input_pdf\", \"questions\", \"mark_scheme_pdf\" (or null). '
        "All items must use the same subject and filenames from that subject's list only. "
        "Order extractions as the user asked. "
        "Do not use one extraction per output page; the user wants one continuous PDF with questions flowing across pages.\n"
        "If the user names several papers (e.g. s25 paper 21, 41, 62), you must use the extractions array. "
        "Infer session/paper from filenames (e.g. w24, s25). Match qp/ms pairs when possible."
    )
    blocks = []
    for key, c in catalogs.items():
        blocks.append(
            f"Subject key: {key}\nDirectory: {c['root']}\n"
            "PDF filenames (only for this subject):\n"
            + ("\n".join(c["pdfs"]) if c["pdfs"] else "(none)")
        )
    user = (
        "\n\n".join(blocks)
        + "\n\nUser request:\n"
        + instruction.strip()
    )

    def _complete(**kwargs):
        return client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )

    try:
        completion = _complete(response_format={"type": "json_object"})
    except Exception:
        try:
            completion = _complete()
        except Exception as e:
            print(f"API error ({model}): {e}", file=sys.stderr)
            sys.exit(1)

    raw = (completion.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Model did not return valid JSON:\n", raw[:2000], file=sys.stderr)
        sys.exit(1)

    for key in ("exam", "output_pdf"):
        if key not in data:
            print(f"JSON missing key: {key}", file=sys.stderr)
            sys.exit(1)

    exam_key = data["exam"]
    if exam_key not in EXAM_ROOT_BY_KEY:
        print(f'exam must be "physics" or "computer_science"; got: {exam_key!r}', file=sys.stderr)
        sys.exit(1)

    exam_root = EXAM_ROOT_BY_KEY[exam_key]
    pdf_names = set(catalogs[exam_key]["pdfs"])
    if not pdf_names:
        print(f"No PDFs available for subject {exam_key!r} under {exam_root}", file=sys.stderr)
        sys.exit(1)

    def _one_extraction(ex: dict, idx: str) -> dict:
        for key in ("input_pdf", "questions"):
            if key not in ex:
                print(f"JSON missing {key} in extractions[{idx}]", file=sys.stderr)
                sys.exit(1)
        if ex["input_pdf"] not in pdf_names:
            print(f'input_pdf must be listed for {exam_key}; got: {ex["input_pdf"]!r} ({idx})', file=sys.stderr)
            sys.exit(1)
        ms = ex.get("mark_scheme_pdf")
        if ms is not None and ms not in pdf_names:
            print(f'mark_scheme_pdf must be from the list or null ({idx}); got: {ms!r}', file=sys.stderr)
            sys.exit(1)
        qs = ex["questions"]
        if not isinstance(qs, list) or not qs:
            print(f'"questions" must be a non-empty array ({idx}).', file=sys.stderr)
            sys.exit(1)
        try:
            qn = [int(x) for x in qs]
        except (TypeError, ValueError):
            print(f'"questions" must be integers ({idx}).', file=sys.stderr)
            sys.exit(1)
        return {"input_pdf": ex["input_pdf"], "questions": qn, "mark_scheme_pdf": ms}

    extractions = data.get("extractions")
    if extractions is not None:
        if not isinstance(extractions, list) or not extractions:
            print('"extractions" must be a non-empty array when present.', file=sys.stderr)
            sys.exit(1)
        normalized = [_one_extraction(ex, str(i)) for i, ex in enumerate(extractions)]
        return exam_root, {"exam": exam_key, "output_pdf": data["output_pdf"], "extractions": normalized}

    for key in ("input_pdf", "questions"):
        if key not in data:
            print(f"JSON missing key: {key}", file=sys.stderr)
            sys.exit(1)

    single = _one_extraction(
        {
            "input_pdf": data["input_pdf"],
            "questions": data["questions"],
            "mark_scheme_pdf": data.get("mark_scheme_pdf"),
        },
        "0",
    )
    return exam_root, {"exam": exam_key, "output_pdf": data["output_pdf"], "extractions": [single]}
