from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.phase9_1 import run


if __name__ == "__main__":
    summary = run(ROOT)
    result = summary["building_level_bootstrap"]
    print(
        "Phase 9.1 PASS: "
        f"point={result['point_estimate']:.8f}, "
        f"95% CI=[{result['ci95_lower']:.8f}, {result['ci95_upper']:.8f}]"
    )
