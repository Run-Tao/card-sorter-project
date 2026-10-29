# -*- coding: utf-8 -*-
"""Download a small, reproducible subset of public playing-card datasets.

Datasets
--------
1. JackFurby/playing-cards (MIT, machine-generated single-card scenes, 52 classes)
   https://huggingface.co/datasets/JackFurby/playing-cards
   We download N images per class from the official train split and M from val.
   Each image ships with 4 card corners in the JSON metadata, so it can be
   rectified into a clean single-card image.
2. drFarid/French-Playing-Cards (MIT, real photographs, 52 class folders)
   https://huggingface.co/datasets/drFarid/French-Playing-Cards
   We download K photos per class.  The folder names are French; map them to
   S/H/D/C labels.

This script only downloads data.  It does not train or evaluate anything.
All URLs, licenses and the exact selection are written to download_manifest.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HF = "https://huggingface.co/datasets"
UA = {"User-Agent": "card-classifier-stage2/1.0 (course project; data download)"}

RANK_ORDER = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUIT_ORDER = ["S", "H", "D", "C"]

FRENCH_SUIT = {"coeur": "H", "carreau": "D", "pique": "S", "trefle": "C"}
FRENCH_RANK = {"valet": "J", "dame": "Q", "roi": "K", "as": "A"}


def fetch_bytes(url: str, retries: int = 4) -> bytes:
    # Folder names contain spaces; urllib requires them to be percent-encoded.
    url = urllib.parse.quote(url, safe=":/?&=%#")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - retry all network errors
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed after {retries} tries: {url}: {last}")


def fetch_json(url: str):
    return json.loads(fetch_bytes(url).decode("utf-8"))


def download_one(args):
    url, dst = args
    dst = Path(dst)
    if dst.exists() and dst.stat().st_size > 0:
        return "skip", dst, dst.stat().st_size
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_bytes(url)
    if not data:
        raise RuntimeError(f"empty response: {url}")
    tmp = dst.with_suffix(dst.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dst)
    return "ok", dst, len(data)


def parallel_download(jobs, workers=12):
    ok = skip = failed = 0
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(download_one, job) for job in jobs]
        for fut in as_completed(futures):
            try:
                status, path, size = fut.result()
                if status == "ok":
                    ok += 1
                else:
                    skip += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                errors.append(str(exc))
    return ok, skip, failed, errors


def jackfurby(base: Path, per_class_train: int, per_class_val: int):
    repo = f"{HF}/JackFurby/playing-cards/resolve/main"
    raw = base / "raw" / "jackfurby"
    raw.mkdir(parents=True, exist_ok=True)

    classes_txt = fetch_bytes(f"{repo}/splits/single/classes.txt").decode("utf-8")
    class_index = {}
    for line in classes_txt.splitlines():
        parts = line.split()
        if len(parts) == 2:
            class_index[parts[0]] = int(parts[1])
    if len(class_index) != 52:
        raise RuntimeError(f"expected 52 classes, got {len(class_index)}")

    split_info = {}
    for split, per_class in (("train", per_class_train), ("val", per_class_val)):
        meta = fetch_json(f"{repo}/splits/single/{split}.json")
        by_class: dict[int, list[dict]] = {}
        for sample_id, item in meta.items():
            by_class.setdefault(int(item["class_label"]), []).append(item)
        chosen = []
        for label_idx in sorted(by_class):
            # deterministic: first N entries in the official split
            for item in by_class[label_idx][:per_class]:
                chosen.append(item)
        split_info[split] = chosen
        print(f"[jackfurby] {split}: {len(chosen)} images "
              f"({per_class}/class, classes={len(by_class)})")

    jobs = []
    records = []
    for split, items in split_info.items():
        for item in items:
            rel = item["img_path"]
            url = f"{repo}/{rel}"
            dst = raw / split / rel
            jobs.append((url, dst))
            records.append({
                "source": "JackFurby/playing-cards",
                "license": "MIT",
                "split": split,
                "img_path": rel,
                "url": url,
                "class_label_index": int(item["class_label"]),
                "class_label": next(k for k, v in class_index.items()
                                    if v == int(item["class_label"])),
                "card_points": item.get("card_points"),
                "local_path": str(dst.relative_to(base)),
            })
    print(f"[jackfurby] downloading {len(jobs)} files ...")
    ok, skip, failed, errors = parallel_download(jobs)
    print(f"[jackfurby] ok={ok} skip={skip} failed={failed}")
    if errors:
        print("\n".join(errors[:5]), file=sys.stderr)
    return class_index, records


def head_size(url: str) -> int:
    try:
        url = urllib.parse.quote(url, safe=":/?&=%#")
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def drfarid(base: Path, per_class: int, candidates: int = 10,
            smallest: bool = False):
    repo = f"{HF}/drFarid/French-Playing-Cards/resolve/main"
    api = "https://huggingface.co/api/datasets/drFarid/French-Playing-Cards"
    meta = fetch_json(api)
    files = [s["rfilename"] for s in meta["siblings"]
             if s["rfilename"].startswith("data/") and re.search(r"\.(jpg|jpeg|png)$", s["rfilename"], re.I)]
    by_class: dict[str, list[str]] = {}
    for rel in files:
        parts = rel.split("/")
        if len(parts) >= 3:
            by_class.setdefault(parts[1], []).append(rel)

    selected: dict[str, list[str]] = {}
    if smallest:
        # Real photos can be 3-8 MB each.  Probe a few candidates per class and
        # download the smallest ones to keep the course-project download small.
        def probe(item):
            folder, rel = item
            return folder, rel, head_size(f"{repo}/{rel}")
        probe_items = [(folder, rel) for folder in sorted(by_class)
                       for rel in sorted(by_class[folder])[:candidates]]
        print(f"[drfarid] probing {len(probe_items)} candidates for smallest files ...")
        probed = []
        with ThreadPoolExecutor(max_workers=16) as ex:
            for folder, rel, size in ex.map(probe, probe_items):
                probed.append((folder, rel, size))
        for folder in sorted(by_class):
            pool = sorted([x for x in probed if x[0] == folder and x[2] > 0],
                          key=lambda x: x[2])
            selected[folder] = [x[1] for x in pool[:per_class]]
            if len(selected[folder]) < per_class:
                selected[folder] = sorted(by_class[folder])[:per_class]
    else:
        for folder in sorted(by_class):
            selected[folder] = sorted(by_class[folder])[:per_class]

    jobs, records = [], []
    for folder in sorted(selected):
        for rel in selected[folder]:
            url = f"{repo}/{rel}"
            dst = base / "raw" / "drfarid" / rel
            jobs.append((url, dst))
            records.append({
                "source": "drFarid/French-Playing-Cards",
                "license": "MIT",
                "folder": folder,
                "url": url,
                "local_path": str(dst.relative_to(base)),
            })
    print(f"[drfarid] {len(by_class)} class folders, {len(jobs)} images ({per_class}/class)")
    print(f"[drfarid] downloading ...")
    ok, skip, failed, errors = parallel_download(jobs)
    print(f"[drfarid] ok={ok} skip={skip} failed={failed}")
    if errors:
        print("\n".join(errors[:5]), file=sys.stderr)
    return sorted(by_class), records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data", help="data root (default: data)")
    ap.add_argument("--jackfurby-train", type=int, default=20, help="images/class from official train split")
    ap.add_argument("--jackfurby-val", type=int, default=5, help="images/class from official val split")
    ap.add_argument("--drfarid", type=int, default=2, help="photos/class from drFarid")
    ap.add_argument("--drfarid-candidates", type=int, default=10,
                    help="probe this many files/class and pick the smallest")
    ap.add_argument("--real-smallest", action="store_true", default=True,
                    help="pick smallest real photos (default: true)")
    ap.add_argument("--skip-drfarid", action="store_true")
    args = ap.parse_args()

    base = Path(args.out).resolve()
    base.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "datasets": [
            {
                "name": "JackFurby/playing-cards",
                "url": "https://huggingface.co/datasets/JackFurby/playing-cards",
                "license": "MIT",
                "kind": "machine-generated single-card scenes (synthetic)",
                "note": "train/val JSON splits and card corner points provided; images rectified later",
            },
            {
                "name": "drFarid/French-Playing-Cards",
                "url": "https://huggingface.co/datasets/drFarid/French-Playing-Cards",
                "license": "MIT",
                "kind": "real photographs, 52 class folders",
                "note": "each class folder appears to contain repeated photos of one physical card; use only as a robustness / cross-source test set",
            },
        ],
        "jackfurby": {},
        "drfarid": {},
    }
    class_index, jf_records = jackfurby(
        base, args.jackfurby_train, args.jackfurby_val)
    manifest["jackfurby"] = {
        "class_index": class_index,
        "num_images": len(jf_records),
        "images": jf_records,
    }
    if not args.skip_drfarid:
        folders, df_records = drfarid(base, args.drfarid, args.drfarid_candidates,
                                      smallest=args.real_smallest)
        manifest["drfarid"] = {
            "folders": folders,
            "num_images": len(df_records),
            "images": df_records,
        }
    (base / "download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest written: {base / 'download_manifest.json'}")


if __name__ == "__main__":
    main()
