"""Validate the canonical narrated presentation video."""
from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(root/'scripts/validate_ppt_video_20261013.py'),'--directory','outputs/demo_video'],cwd=root,check=True)
