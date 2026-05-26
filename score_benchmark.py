#!/usr/bin/env python3
"""Shim: run `python tools/score_benchmark.py` (see README)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "tools" / "score_benchmark.py"
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
