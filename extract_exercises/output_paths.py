# -*- coding: utf-8 -*-
"""Run output directory and bare-filename resolution."""

import datetime
from pathlib import Path

from .config import OUTPUT_DIR

_CURRENT_RUN_DIR: Path | None = None


def ensure_run_output_dir() -> Path:
    """Create ``output/run_<timestamp>/`` once per script run; return that directory."""
    global _CURRENT_RUN_DIR
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if _CURRENT_RUN_DIR is None:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        _CURRENT_RUN_DIR = OUTPUT_DIR / f"run_{stamp}"
        _CURRENT_RUN_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {_CURRENT_RUN_DIR}")
    return _CURRENT_RUN_DIR


def resolve_output_path(output_pdf: str) -> Path:
    """Bare filenames → ``output/run_<timestamp>/``; absolute or nested relative paths unchanged."""
    p = Path(output_pdf)
    if p.is_absolute() or p.parent != Path("."):
        return p
    return ensure_run_output_dir() / p.name
