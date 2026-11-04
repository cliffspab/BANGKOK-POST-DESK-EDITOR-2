#!/usr/bin/env python3
"""Build or verify the exact once-daily, transport-named Shift handover."""

import argparse
import hashlib
import os
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SHIFT = ROOT / "Shift"
PARTS = {
    "BLUEPRINT.txt": "blueprint_sync.txt",
    "GUIDE.txt": "guide_sync.txt",
    "PROCESSES.txt": "processes_sync.txt",
    "DIRECTORY.yaml": "directory_sync.yaml",
    "CONTROL.txt": "control_sync.txt",
    "BLUEPRINT.docx": "blueprint_sync.docx",
    "VERSION.txt": "version_sync.txt",
}
INDEX_NAME = "index_sync.txt"
PUBLIC_BASE = "https://filedn.eu/llkhskhNM5iQj7czpUFCQ8V/BKP%20Shift/"
LEGACY_PARTS = {
    "BLUEPRINT.txt", "GUIDE.txt", "PROCESSES.txt", "DIRECTORY.yaml",
    "CONTROL.txt", "BLUEPRINT.docx",
}
SEAMED = ("GUIDE.txt", "PROCESSES.txt", "DIRECTORY.yaml")
SEAM = re.compile(r"PART:\s+(\S+)\s+(GUIDE|PROCESSES|DIRECTORY)")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tag_of(path):
    with path.open(encoding="utf-8") as fh:
        match = SEAM.search(fh.readline())
    return match.group(1) if match else None


def index_bytes(tag):
    names = list(PARTS.values()) + [INDEX_NAME]
    lines = ["BANGKOK POST SHIFT", f"Edition: {tag}", ""]
    for name in names:
        lines.extend((name, f"{PUBLIC_BASE}{name}", ""))
    return "\n".join(lines).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--target", type=Path, default=DEFAULT_SHIFT)
    args = parser.parse_args()
    check_only = args.check
    shift = args.target
    problems = []
    sources = {name: ROOT / name for name in PARTS if name != "BLUEPRINT.docx"}

    for name, src in sources.items():
        if not src.is_file():
            problems.append(f"missing source: {name}")
    if problems:
        print("\n".join(problems))
        return 1

    tags = {name: tag_of(sources[name]) for name in SEAMED}
    if None in tags.values() or len(set(tags.values())) != 1:
        print("FATAL: parts do not carry one matching build tag:", tags)
        return 1
    tag = next(iter(tags.values()))
    sources["BLUEPRINT.docx"] = ROOT / "Editions" / tag / "BLUEPRINT.docx"
    if not sources["BLUEPRINT.docx"].is_file():
        print(f"missing sealed document: Editions/{tag}/BLUEPRINT.docx")
        return 1

    # During the one-time transport-name rollout, the last sealed legacy set
    # remains a valid read-only handover until the guarded push refreshes it.
    if check_only and shift.is_dir() and set(p.name for p in shift.iterdir()) == LEGACY_PARTS:
        legacy_current = all(
            (shift / name).is_file() and digest(shift / name) == digest(sources[name])
            for name in LEGACY_PARTS
        )
        if legacy_current:
            for name in sorted(LEGACY_PARTS):
                print(f"current (legacy name): Shift/{name}")
            print(f"\nshift ready — build {tag}; legacy names current; `_sync` migration pending guarded push")
            return 0

    if not check_only and shift.is_dir():
        last_refresh = datetime.fromtimestamp(shift.stat().st_mtime).date()
        shift_guide = shift / PARTS["GUIDE.txt"]
        shift_tag = tag_of(shift_guide) if shift_guide.is_file() else None
        exact = set(p.name for p in shift.iterdir()) == set(PARTS.values()) | {INDEX_NAME}
        current = exact and all(
            (shift / target).is_file() and digest(shift / target) == digest(sources[source])
            for source, target in PARTS.items()
        )
        current = current and (shift / INDEX_NAME).read_bytes() == index_bytes(tag)
        if last_refresh == date.today() and shift_tag == tag and current:
            print(f"Shift already refreshed today ({last_refresh.isoformat()}); no write")
            return 0
        if last_refresh == date.today():
            print(f"Shift carries {shift_tag or 'no edition'}; refreshing newly sealed {tag}")

    if not check_only:
        shift.mkdir(exist_ok=True)

    if not shift.is_dir():
        problems.append("Shift folder does not exist")
    else:
        allowed = set(PARTS.values()) | {INDEX_NAME}
        stale = sorted(p.name for p in shift.iterdir() if p.name not in allowed)
        legacy = set(stale) and set(stale).issubset(LEGACY_PARTS)
        if stale and legacy and not check_only:
            for name in stale:
                (shift / name).unlink()
                print(f"retired legacy Shift/{name}")
            stale = []
        if stale:
            problems.append("stray in Shift/: " + ", ".join(stale))

    for source_name, src in sources.items():
        target_name = PARTS[source_name]
        dst = shift / target_name
        if dst.is_file() and digest(dst) == digest(src):
            print(f"current: Shift/{target_name}")
        else:
            problems.append(f"stale or missing: Shift/{target_name}")
            if not check_only:
                shutil.copy2(src, dst)
                print(f"written: Shift/{target_name}")

    index = shift / INDEX_NAME
    expected_index = index_bytes(tag)
    if index.is_file() and index.read_bytes() == expected_index:
        print(f"current: Shift/{INDEX_NAME}")
    else:
        problems.append(f"stale or missing: Shift/{INDEX_NAME}")
        if not check_only:
            index.write_bytes(expected_index)
            print(f"written: Shift/{INDEX_NAME}")

    if problems and check_only:
        print("\n".join(problems))
        print(f"\nbuild {tag} — NOT READY")
        return 1

    # Copying repairs missing or stale approved files, but never removes strays.
    remaining = [p for p in problems if p.startswith("stray in")]
    if remaining:
        print("\n".join(remaining))
        print(f"\nbuild {tag} — NOT READY; move strays to Archive and rerun")
        return 1

    if not check_only:
        os.utime(shift, None)
    print(f"\nshift ready — build {tag}; eight sync-named files; refresh daily or when a newly sealed edition supersedes it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
