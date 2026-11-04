#!/usr/bin/env python3
"""Extract a verified, disposable delivery from the single BLUEPRINT source."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEAM = re.compile(r"<!-- PART: (\S+) (GUIDE|PROCESSES|DIRECTORY) -->")
FENCE = re.compile(r"```yaml\n(.*?)\n```", re.S)
TASKS = {
    "edit": (r"^# \[G1\] EDITING\s*$", r"\Z"),
    "fit": (r"^## \[P1\] COPY\s*$", r"^## \[P2\] VERIFICATION\s*$"),
    "verify": (r"^## \[P2\] VERIFICATION\s*$", r"^## \[P3\] PHOTOS\s*$"),
    "photo": (r"^## \[P3\] PHOTOS\s*$", r"^## \[P4\] CHECKING\s*$"),
    "check": (r"^## \[P4\] CHECKING\s*$", r"^## \[P5\] PR\s*$"),
    "pr": (r"^## \[P5\] PR\s*$", r"\Z"),
}


def fail(message: str) -> None:
    raise SystemExit(f"FATAL: {message}")


def load(source: Path) -> tuple[str, str, str, str, str]:
    text = source.read_text(encoding="utf-8")
    hits = list(SEAM.finditer(text))
    if [m.group(2) for m in hits] != ["GUIDE", "PROCESSES", "DIRECTORY"]:
        fail("BLUEPRINT must contain GUIDE, PROCESSES and DIRECTORY in order")
    tags = {m.group(1) for m in hits}
    if len(tags) != 1:
        fail("BLUEPRINT seams carry different editions")
    tag = tags.pop()
    front = text.split("\n\n", 2)[1].strip()
    if front != tag:
        fail("front edition does not match the part seams")
    guide = text[hits[0].start():hits[1].start()]
    processes = text[hits[1].start():hits[2].start()]
    directory = text[hits[2].start():]
    return text, tag, guide, processes, directory


def bounded(text: str, start: str, end: str) -> str:
    match = re.search(f"({start}.*?)(?={end})", text, re.M | re.S)
    if not match:
        fail(f"required section is missing or unbounded: {start}")
    return match.group(1).rstrip() + "\n"


def extract(source: Path, name: str) -> str:
    text, tag, guide, processes, directory = load(source)
    if name == "version":
        return tag + "\n"
    if name == "master":
        return text
    if name == "guide":
        return guide.rstrip() + "\n"
    if name == "processes":
        return processes.rstrip() + "\n"
    if name == "directory":
        match = FENCE.search(directory)
        if not match:
            fail("DIRECTORY YAML fence is missing")
        return f"# PART: {tag} DIRECTORY\n{match.group(1)}\n"
    start, end = TASKS[name]
    body = bounded(guide if name == "edit" else processes, start, end)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=("master", "version", "guide", "processes", "directory", *TASKS))
    parser.add_argument("--source", type=Path, default=Path("BLUEPRINT.txt"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-version")
    args = parser.parse_args()
    payload = extract(args.source, args.name)
    _, tag, _, _, _ = load(args.source)
    if args.expect_version and args.expect_version != tag:
        fail(f"expected {args.expect_version}, master carries {tag}")
    if args.output:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
