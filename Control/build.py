#!/usr/bin/env python3
"""Build the installable Desk Control plugin from CONTROL.txt."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "CONTROL.txt"
BLUEPRINT = ROOT.parent / "Blueprint" / "BLUEPRINT.txt"
OUT = ROOT / "plugin"
MODULES = ("EDIT", "PHOTO", "CHECK", "PR")
META = {
    "EDIT": {
        "description": "Edit Bangkok Post copy through the supplied GUIDE, COPY and VERIFICATION sections and triggered Directory lookups. Use for subbing, editing, fitting, headline, deck, brief, overspill, DCX or Style Log work; paid-placement and PR copy use the PR skill.",
        "display": "Bangkok Post Edit",
        "short": "Edit copy to Bangkok Post desk rules",
        "prompt": "Use $edit to edit this Bangkok Post copy with the supplied Blueprint sections.",
    },
    "CHECK": {
        "description": "Check placed Bangkok Post copy before initialling through the supplied CHECKING and VERIFICATION sections and triggered Directory lookups.",
        "display": "Bangkok Post Check",
        "short": "Check placed copy before initialling",
        "prompt": "Use $check to check this placed Bangkok Post copy with the supplied Blueprint sections.",
    },
    "PR": {
        "description": "Process Bangkok Post paid-placement, advertorial or PR copy through the supplied minimum-intervention PR section.",
        "display": "Bangkok Post PR",
        "short": "Process paid-placement copy",
        "prompt": "Use $pr to process this Bangkok Post paid-placement copy with the supplied Blueprint section.",
    },
    "PHOTO": {
        "description": "Handle standalone Bangkok Post headlines and captions through the supplied PHOTOS, COPY and VERIFICATION sections.",
        "display": "Bangkok Post Photo",
        "short": "Write and fit standalone captions",
        "prompt": "Use $photo to handle this Bangkok Post headline and caption with the supplied Blueprint sections.",
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"FATAL: {message}")


def extract(source: str, name: str) -> str:
    pattern = re.compile(
        rf"^=+ MODULE {name} — BEGIN =+\n(.*?)^=+ MODULE {name} — END =+$",
        re.MULTILINE | re.DOTALL,
    )
    matches = pattern.findall(source)
    if len(matches) != 1:
        fail(f"expected one {name} module, found {len(matches)}")
    return matches[0].strip() + "\n"


def expected_files(source: str) -> dict[Path, str]:
    if not source.startswith("# BANGKOK POST DESK CONTROL\n"):
        fail("CONTROL title is missing")
    edition = next((line.strip() for line in source.splitlines()[1:] if line.strip()), "")
    if not re.fullmatch(r"\d{6}_control_[a-z0-9-]+", edition):
        fail(f"invalid CONTROL edition: {edition!r}")
    common = extract(source, "COMMON")
    if "When the supplied Blueprint cannot be read, say so." not in common:
        fail("missing-Blueprint route is absent")
    if re.search(r"audit its completeness|compare it with a snapshot|matching .*edition", common, re.I):
        fail("model-side source audit instructions remain")

    if not BLUEPRINT.is_file():
        fail(f"authoritative Blueprint is missing: {BLUEPRINT}")
    blueprint = BLUEPRINT.read_text(encoding="utf-8")
    section_bounds = {
        "G1": (r"^# \[G1\] EDITING\s*$", r"^# \[G2\] PHOTO\s*$"),
        "G2": (r"^# \[G2\] PHOTO\s*$", r"^# \[P\] PROCESSES\s*$"),
        "P1": (r"^## \[P1\] COPY\s*$", r"^## \[P2\] VERIFICATION\s*$"),
        "P2": (r"^## \[P2\] VERIFICATION\s*$", r"^## \[P3\] PHOTOS\s*$"),
        "P3": (r"^## \[P3\] PHOTOS\s*$", r"^## \[P4\] CHECKING\s*$"),
        "P4": (r"^## \[P4\] CHECKING\s*$", r"^## \[P5\] PR\s*$"),
        "P5": (r"^## \[P5\] PR\s*$", r"^<!-- PART: .* DIRECTORY -->\s*$"),
    }
    sections = {}
    for code, (start, end) in section_bounds.items():
        match = re.search(f"({start}.*?)(?={end})", blueprint, re.M | re.S)
        if not match:
            fail(f"Blueprint section is missing or unbounded: {code}")
        sections[code] = match.group(1).rstrip() + "\n"

    routes = {
        "EDIT": ("G1", "P1", "P2"),
        "PHOTO": ("G2", "P3", "P1", "P2"),
        "CHECK": ("P4", "P2"),
        "PR": ("P5",),
    }
    task_sections = {}
    for name, codes in routes.items():
        control_module = extract(source, name)
        for code in codes:
            if f"`[{code}]" not in control_module:
                fail(f"CONTROL route {name} omits [{code}]")
        task_sections[name] = "\n".join(sections[code].rstrip() for code in codes) + "\n"

    files: dict[Path, str] = {}
    manifest = {
        "name": "edit",
        "version": "0.2.0",
        "description": "Bangkok Post desk workflows governed by the complete BLUEPRINT, comprising GUIDE rules and DIRECTORY lookups.",
        "author": {"name": "Bangkok Post desk"},
        "skills": "./skills/",
        "interface": {
            "displayName": "Bangkok Post Desk Control",
            "shortDescription": "Run Bangkok Post desk workflows",
            "longDescription": "Edit, check, caption and process PR copy using generated Blueprint sections and triggered Directory lookups.",
            "developerName": "Bangkok Post desk",
            "category": "Productivity",
            "capabilities": [
                "Edit Bangkok Post copy",
                "Check placed copy before initialling",
                "Write and fit standalone captions",
                "Apply the paid-placement PR workflow",
                "Apply GUIDE rules and DIRECTORY lookups",
            ],
            "defaultPrompt": [META[name]["prompt"] for name in MODULES],
        },
    }
    files[OUT / ".codex-plugin" / "plugin.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    for name in MODULES:
        slug = name.lower()
        module = task_sections[name]
        skill = (
            "---\n"
            f"name: {slug}\n"
            f"description: {META[name]['description']}\n"
            "---\n\n"
            f"{common}\n{module}"
        )
        agent = (
            "interface:\n"
            f"  display_name: \"{META[name]['display']}\"\n"
            f"  short_description: \"{META[name]['short']}\"\n"
            f"  default_prompt: \"{META[name]['prompt']}\"\n"
        )
        files[OUT / "skills" / slug / "SKILL.md"] = skill
        files[OUT / "skills" / slug / "agents" / "openai.yaml"] = agent
    return files


def main() -> int:
    check = "--check" in sys.argv
    source = SOURCE.read_text(encoding="utf-8")
    files = expected_files(source)
    stale = []
    for path, expected in files.items():
        actual = path.read_text(encoding="utf-8") if path.is_file() else None
        if actual == expected:
            print(f"current: {path.relative_to(ROOT)}")
        elif check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
            print(f"written: {path.relative_to(ROOT)}")
    if stale:
        fail("stale generated CONTROL files: " + ", ".join(stale))
    print(f"CONTROL {next(line for line in source.splitlines()[1:] if line.strip())}: PASS ({len(MODULES)} workflows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
