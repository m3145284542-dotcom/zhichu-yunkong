"""Derive competition-ready Phase 9 artifacts without rerunning any model."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase9_cleanup import finalize_phase9_outputs


if __name__ == "__main__":
    result = finalize_phase9_outputs(ROOT)
    print(json.dumps({
        "final_algorithm": result["final_algorithm"],
        "doef_vs_lightgbm": result["doef_vs_lightgbm"],
        "catboost_peak_reduction_pct": result["catboost_peak_reduction_pct"],
    }, ensure_ascii=False, indent=2))
