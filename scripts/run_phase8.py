"""One-command entry point for Phase 8."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase8 import run


if __name__ == "__main__":
    run(ROOT)
