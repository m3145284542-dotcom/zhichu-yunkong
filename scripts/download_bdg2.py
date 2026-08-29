"""Download only the three BDG2 files required by this project."""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
BASE = "https://media.githubusercontent.com/media/buds-lab/building-data-genome-project-2/master"
FILES = {
    "metadata.csv": "data/metadata/metadata.csv",
    "weather.csv": "data/weather/weather.csv",
    "electricity_cleaned.csv": "data/meters/cleaned/electricity_cleaned.csv",
}
PAGES = {
    name: f"https://github.com/buds-lab/building-data-genome-project-2/blob/master/{path}"
    for name, path in FILES.items()
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_lfs_pointer(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(200).startswith(b"version https://git-lfs.github.com/spec/v1")


def download_one(name: str, repository_path: str) -> dict[str, object]:
    destination = RAW_DIR / name
    if destination.exists() and destination.stat().st_size > 200 and not is_lfs_pointer(destination):
        print(f"Exists, keeping original: {destination}")
        return {"file": name, "source": PAGES[name], "bytes": destination.stat().st_size, "sha256": sha256(destination)}

    temporary = destination.with_suffix(destination.suffix + ".download")
    url = f"{BASE}/{repository_path}"
    print(f"Downloading {name} from official repository ...")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "bdg2-stage2-data-loader/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
    except (OSError, urllib.error.URLError) as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Download failed once for {name}: {error}") from error

    if temporary.stat().st_size <= 200 or is_lfs_pointer(temporary):
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Official endpoint returned an invalid payload for {name}")
    temporary.replace(destination)
    return {"file": name, "source": PAGES[name], "bytes": destination.stat().st_size, "sha256": sha256(destination)}


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    try:
        for name, repository_path in FILES.items():
            records.append(download_one(name, repository_path))
    except RuntimeError as error:
        print(f"\n{error}", file=sys.stderr)
        print("No automatic retry will be attempted. Download these official files manually:", file=sys.stderr)
        for name, page in PAGES.items():
            print(f"- {name}: {page}", file=sys.stderr)
        print(f"Place them in: {RAW_DIR}", file=sys.stderr)
        return 1

    manifest = {"dataset": "Building Data Genome Project 2", "files": records}
    (RAW_DIR / "download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("All required official files are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

