# -*- coding: utf-8 -*-
"""Create the deliverable zip (code + processed data + results, excluding raw downloads)."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "card_classifier_stage2_deliverable.zip"
EXCLUDE_DIRS = {"data/raw", "data/raw_inspect", "data/raw_jackfurby",
                "__pycache__", ".venv", ".git", ".pytest_cache"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".part"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    for d in EXCLUDE_DIRS:
        if rel == d or rel.startswith(d + "/"):
            return False
    if path.suffix.lower() in EXCLUDE_SUFFIX:
        return False
    return True


def main():
    files = [p for p in ROOT.rglob("*") if p.is_file() and included(p)]
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(files):
            zf.write(p, arcname=(Path(ROOT.name) / p.relative_to(ROOT)).as_posix())
    print(f"wrote {OUT}  files={len(files)}  size={OUT.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
