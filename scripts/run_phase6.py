"""Run Phase 6 decision-aware forecast and battery optimization."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.phase6 import run


if __name__ == "__main__":
    result = run(PROJECT_ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
