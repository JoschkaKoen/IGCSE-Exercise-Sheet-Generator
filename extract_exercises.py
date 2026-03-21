#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point for the exercise extractor (implementation lives in the ``extract_exercises`` package).

Environment (recommended):
    cd "/path/to/Exercise Sheet Generator"
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    source .venv/bin/activate

Usage:
    python extract_exercises.py "Winter 2024 Physics paper 21, questions 12–14, include mark scheme"
    python extract_exercises.py <input_pdf> <output_pdf> <question_numbers...> [--ms <mark_scheme.pdf>]

See ``extract_exercises/__init__.py`` and module docstrings for behaviour details.
"""

from extract_exercises.cli import main

if __name__ == "__main__":
    main()
