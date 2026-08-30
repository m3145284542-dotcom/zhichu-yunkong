"""One-command entry point for Phase 5.7."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".mplconfig"))

from src.phase5_7 import run


if __name__ == "__main__":
    print(json.dumps(run(PROJECT_ROOT), ensure_ascii=False, indent=2, allow_nan=False))
