#!/usr/bin/env python3
"""Refresh or verify the stable Google Drive master and version witness.

Run only after seal.py. Every source comes from the sealed edition, and every
destination must already exist so a misspelt path cannot create a duplicate
Drive file with a new ID.
"""

import argparse
import hashlib
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYNC_ROUTE_EDITION = "140926_sync_workspace-direct"
DEFAULT_TARGET = Path(r"D:\GoogleDrive\My Drive\BKP_SYNC_MASTER")
TARGET_FOLDER_ID = "13kYSk0V4JEiUs5IclNB9nPDQJYkfHa7d"
CONTAINERS = {
    "BLUEPRINT.txt": ("blueprint_sync.txt", "1MdhPBNEUVdExgKseGkL-3yLe7YZuBVhI"),
    "VERSION.txt": ("version_sync.txt", "1w45w9bn_kQwHJfmwC488tA9e_YtsDr9S"),
}
TAG = re.compile(r"PART:\s+(\S+)\s+GUIDE")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_tag():
    source = (ROOT / "BLUEPRINT.txt").read_text(encoding="utf-8")
    match = TAG.search(source)
    if not match:
        raise SystemExit("FATAL: BLUEPRINT.txt has no GUIDE edition seam.")
    return match.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(os.environ.get("BKP_SYNC_MASTER_DIR", DEFAULT_TARGET)),
    )
    args = parser.parse_args()

    print(f"sync route: {SYNC_ROUTE_EDITION}")

    tag = current_tag()
    edition = ROOT / "Editions" / tag
    if not edition.is_dir():
        raise SystemExit(f"FATAL: edition is not sealed: Editions/{tag}")
    if not args.target.is_dir():
        raise SystemExit(f"FATAL: Drive container folder is unavailable: {args.target}")

    missing_sources = [name for name in CONTAINERS if not (edition / name).is_file()]
    missing_targets = [name for name, _ in CONTAINERS.values()
                       if not (args.target / name).is_file()]
    if missing_sources:
        raise SystemExit("FATAL: sealed outputs missing: " + ", ".join(missing_sources))
    if missing_targets:
        raise SystemExit("FATAL: Drive containers missing: " + ", ".join(missing_targets))

    witness = (edition / "VERSION.txt").read_text(encoding="utf-8")
    if witness != tag + "\n":
        raise SystemExit("FATAL: sealed VERSION.txt does not match the sealed master")

    stale = []
    for source_name, (target_name, file_id) in CONTAINERS.items():
        source = edition / source_name
        target = args.target / target_name
        identity = f"  [{file_id}]" if file_id else ""
        if digest(source) == digest(target):
            print(f"current: {target_name}{identity}")
            continue
        stale.append(target_name)
        if not args.check:
            shutil.copy2(source, target)
            if digest(source) != digest(target):
                raise SystemExit(f"FATAL: container verification failed: {target_name}")
            print(f"written: {target_name}{identity}")

    if stale and args.check:
        print("stale: " + ", ".join(stale))
        print(f"\nDrive containers — NOT CURRENT for {tag}")
        return 1

    print(f"\nDrive master ready — {tag}; master plus version witness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
