"""Run the reproducible BDG2 stage-two pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.pipeline import run_pipeline


if __name__ == "__main__":
    result = run_pipeline(PROJECT_ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))

