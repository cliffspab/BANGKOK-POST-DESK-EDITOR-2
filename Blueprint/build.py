from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path

VERSION_RE = re.compile(r"^<!-- MASTER ([A-Za-z0-9_.-]+) -->$", re.M)
PART_RE = re.compile(
    r"^<!-- COMPONENT: ([A-Z]+) -->\n(.*?)\n<!-- END COMPONENT: \1 -->$",
    re.M | re.S,
)

PART_PATHS = {
    "BOOT": Path("DEPLOY/routed/BOOT.md"),
    "EDIT": Path("DEPLOY/routed/edit.md"),
    "CHECK": Path("DEPLOY/routed/modules/check.md"),
    "PHOTO": Path("DEPLOY/routed/modules/photo.md"),
    "PR": Path("DEPLOY/routed/modules/pr.md"),
    "DIRECTORY": Path("DEPLOY/DIRECTORY.txt"),
}
SKILL_SOURCES = {
    "boot": "BOOT",
    "edit": "EDIT",
    "check": "CHECK",
    "photo": "PHOTO",
    "pr": "PR",
}
PLACEHOLDERS = ("ADDENDUM_LINK_BEFORE_PUSH",)
COMPAT_FILES = (
    "BLUEPRINT.txt",
    "GUIDE.txt",
    "PROCESSES.txt",
    "DIRECTORY.txt",
    "DIRECTORY.yaml",
    "VERSION.txt",
)

UPLOAD_BUNDLES = {
    "boot": ["EDIT", "CHECK", "PHOTO", "PR", "DIRECTORY"],
    "edit": ["DIRECTORY"],
    "check": ["EDIT", "DIRECTORY"],
    "photo": ["EDIT", "DIRECTORY"],
    "pr": ["EDIT", "DIRECTORY"],
}
UPLOAD_NAMES = {
    "EDIT": "edit.md", "CHECK": "check.md", "PHOTO": "photo.md", "PR": "pr.md",
    "DIRECTORY": "DIRECTORY.txt",
}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def remove_tree(path: Path) -> None:
    """Remove a generated tree even when Windows copied directory attributes."""
    def clear_readonly(function, target, _error):
        os.chmod(target, stat.S_IWRITE)
        function(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=clear_readonly)
    else:
        shutil.rmtree(path, onerror=clear_readonly)


def watermark(name: str, version: str, body: str) -> str:
    body = body.rstrip() + "\n"
    if name == "DIRECTORY":
        return f"# {version}\n" + body
    mark = f"<!-- {version} -->\n"
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end < 0:
            raise SystemExit(f"FATAL: {name} has unclosed front matter")
        end += len("\n---\n")
        return body[:end] + mark + body[end:]
    return mark + body


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source(source: Path):
    text = source.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        raise SystemExit("FATAL: BLUEPRINT.md has no MASTER edition mark")
    version = match.group(1)
    parts = {}
    for match in PART_RE.finditer(text):
        name, body = match.group(1), match.group(2)
        if name in parts:
            raise SystemExit(f"FATAL: duplicate component {name}")
        parts[name] = body
    missing = set(PART_PATHS) - set(parts)
    extra = set(parts) - set(PART_PATHS)
    if missing or extra:
        raise SystemExit(f"FATAL: component mismatch; missing={sorted(missing)} extra={sorted(extra)}")
    return text, version, parts


def validate_parts(parts):
    for part in ("BOOT", "EDIT", "CHECK", "PHOTO", "PR"):
        expected = part.lower()
        match = re.search(r"^---\n.*?^name:\s*[\"']?([^\"'\n]+)", parts[part], re.M | re.S)
        if not match or match.group(1).strip() != expected:
            raise SystemExit(f"FATAL: {part} front matter name is not {expected}")
    directory = parts["DIRECTORY"]
    if not directory.startswith("index:\n"):
        raise SystemExit("FATAL: DIRECTORY must begin with index:")
    if re.search(r"(?m)^status:", directory) or "status.apex" in directory:
        raise SystemExit("FATAL: volatile status material remains in DIRECTORY")
    if not re.search(r"(?m)^references:", directory):
        raise SystemExit("FATAL: DIRECTORY has no references branch")


def validate_release(parts):
    for name, body in parts.items():
        for token in PLACEHOLDERS:
            if token in body:
                raise SystemExit(f"FATAL: {name} still contains placeholder {token}")


def without_frontmatter(body: str) -> str:
    if not body.startswith("---\n"):
        return body
    end = body.find("\n---\n", 4)
    if end < 0:
        raise SystemExit("FATAL: unclosed component front matter")
    return body[end + len("\n---\n"):]


def bounded_section(body: str, start: str, end: str) -> str:
    start_at = body.find(start)
    end_at = body.find(end, start_at + len(start))
    if start_at < 0 or end_at < 0:
        raise SystemExit(f"FATAL: cannot extract compatibility section {start}")
    return body[start_at:end_at].rstrip() + "\n"


def write_compatibility_files(
    root: Path, source_text: str, version: str, parts
) -> None:
    """Preserve the five former public paths as generated compatibility files."""
    edit = without_frontmatter(parts["EDIT"])
    write_text(root / "BLUEPRINT.txt", f"<!-- {version} -->\n" + source_text.rstrip() + "\n")
    write_text(
        root / "GUIDE.txt",
        watermark("GUIDE", version, bounded_section(edit, "# [G1] EDITING", "# [P] PROCESSES")),
    )
    write_text(
        root / "PROCESSES.txt",
        watermark("PROCESSES", version, bounded_section(edit, "# [P] PROCESSES", "# [R] RETURN")),
    )
    directory_text = watermark("DIRECTORY", version, parts["DIRECTORY"])
    write_text(root / "DIRECTORY.txt", directory_text)
    write_text(root / "DIRECTORY.yaml", directory_text)
    write_text(root / "VERSION.txt", version + "\n")


def write_upload_zips(root: Path, version: str, parts) -> None:
    """Build one self-contained, ready-to-upload archive per skill."""
    upload = root / "UPLOAD"
    upload.mkdir(parents=True, exist_ok=True)
    stamp = (2026, 1, 1, 0, 0, 0)
    for skill, part in SKILL_SOURCES.items():
        entries = [(f"{skill}/SKILL.md", watermark(part, version, parts[part]))]
        for ref in UPLOAD_BUNDLES[skill]:
            entries.append((
                f"{skill}/references/{UPLOAD_NAMES[ref]}",
                watermark(ref, version, parts[ref]),
            ))
        with zipfile.ZipFile(upload / f"{skill}.zip", "w", zipfile.ZIP_STORED) as zf:
            for name, text in entries:
                info = zipfile.ZipInfo(name, date_time=stamp)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, text.encode("utf-8"))


def validate_upload_zips(root: Path) -> None:
    upload = root / "UPLOAD"
    expected_zips = {f"{skill}.zip" for skill in SKILL_SOURCES}
    actual_zips = {path.name for path in upload.glob("*.zip")}
    if actual_zips != expected_zips:
        raise SystemExit(
            "FATAL: UPLOAD zip inventory differs; "
            f"missing={sorted(expected_zips - actual_zips)} "
            f"extra={sorted(actual_zips - expected_zips)}"
        )
    for skill in SKILL_SOURCES:
        archive = upload / f"{skill}.zip"
        expected_entries = {f"{skill}/SKILL.md"} | {
            f"{skill}/references/{UPLOAD_NAMES[ref]}"
            for ref in UPLOAD_BUNDLES[skill]
        }
        with zipfile.ZipFile(archive) as zf:
            bad = zf.testzip()
            if bad:
                raise SystemExit(f"FATAL: corrupt member {bad} in {archive.name}")
            actual_entries = set(zf.namelist())
            if actual_entries != expected_entries:
                raise SystemExit(
                    f"FATAL: {archive.name} contents differ; "
                    f"missing={sorted(expected_entries - actual_entries)} "
                    f"extra={sorted(actual_entries - expected_entries)}"
                )


def build(source: Path, root: Path, release: bool = False) -> None:
    source_text, version, parts = load_source(source)
    validate_parts(parts)
    if release:
        validate_release(parts)
    deploy = root / "DEPLOY"
    if deploy.exists():
        remove_tree(deploy)

    for name, rel in PART_PATHS.items():
        write_text(root / rel, watermark(name, version, parts[name]))

    # Alternative skill deployment. Installation and companion selection are manual.
    for skill, part in SKILL_SOURCES.items():
        skill_dir = deploy / "skills" / skill
        write_text(skill_dir / "SKILL.md", watermark(part, version, parts[part]))

    routed_files = [
        "BOOT.md", "edit.md", "modules/check.md", "modules/photo.md", "modules/pr.md",
    ]
    routed_lines = [
        f"# {version}",
        f"version: {version}",
        "entrypoint: BOOT.md",
        "default: edit.md",
        "directory_source: ../DIRECTORY.txt",
        "modes:",
        "  check: modules/check.md",
        "  photo: modules/photo.md",
        "  pr: modules/pr.md",
        "files:",
    ]
    for rel in routed_files:
        path = deploy / "routed" / rel
        routed_lines.extend([
            f"  - path: {rel}",
            f"    bytes: {path.stat().st_size}",
            f"    sha256: {sha256(path)}",
        ])
    write_text(deploy / "routed" / "INDEX.yaml", "\n".join(routed_lines) + "\n")

    skill_files = [f"{skill}/SKILL.md" for skill in SKILL_SOURCES]
    skill_lines = [
        f"# {version}",
        f"version: {version}",
        "directory_source: ../DIRECTORY.txt",
        "installation: select a skill and bundle only the companions it needs",
        "skills:",
        "  boot: boot/SKILL.md",
        "  edit: edit/SKILL.md",
        "  check: check/SKILL.md",
        "  photo: photo/SKILL.md",
        "  pr: pr/SKILL.md",
        "files:",
    ]
    for rel in skill_files:
        path = deploy / "skills" / rel
        skill_lines.extend([
            f"  - path: {rel}",
            f"    bytes: {path.stat().st_size}",
            f"    sha256: {sha256(path)}",
        ])
    write_text(deploy / "skills" / "INDEX.yaml", "\n".join(skill_lines) + "\n")

    indexed = sorted(
        str(p.relative_to(deploy)).replace("\\", "/")
        for p in deploy.rglob("*") if p.is_file()
    )
    umbrella_lines = [
        f"# {version}",
        f"version: {version}",
        "directory: DIRECTORY.txt",
        "deployments:",
        "  routed: routed/INDEX.yaml",
        "  skills: skills/INDEX.yaml",
        "instruction: choose one deployment; do not ingest the whole umbrella",
        "files:",
    ]
    for rel in indexed:
        path = deploy / rel
        umbrella_lines.extend([
            f"  - path: {rel}",
            f"    bytes: {path.stat().st_size}",
            f"    sha256: {sha256(path)}",
        ])
    write_text(deploy / "INDEX.yaml", "\n".join(umbrella_lines) + "\n")

    write_upload_zips(root, version, parts)
    validate_upload_zips(root)
    write_compatibility_files(root, source_text, version, parts)

    # Build receipt is outside DEPLOY so DEPLOY remains the exact transport payload.
    upload_receipt = {
        path.name: sha256(path)
        for path in sorted((root / "UPLOAD").glob("*.zip"))
    }
    receipt = {
        "version": version,
        "source": source.name,
        "source_sha256": sha256(source),
        "deploy_files": len(indexed) + 1,
        "upload_zips": upload_receipt,
        "compatibility_files": {
            name: sha256(root / name) for name in COMPAT_FILES
        },
    }
    write_text(root / "build-receipt.json", json.dumps(receipt, indent=2) + "\n")
    print(
        f"built {version}: {len(indexed) + 1} DEPLOY files, "
        f"{len(SKILL_SOURCES)} upload zips"
    )


def check(source: Path, root: Path, release: bool = False) -> None:
    temp = root / ".check"
    if temp.exists():
        remove_tree(temp)
    temp.mkdir(parents=True)
    build(source, temp, release)
    expected = root / "DEPLOY"
    actual = temp / "DEPLOY"
    expected_files = sorted(p.relative_to(expected) for p in expected.rglob("*") if p.is_file())
    actual_files = sorted(p.relative_to(actual) for p in actual.rglob("*") if p.is_file())
    if expected_files != actual_files:
        raise SystemExit("FATAL: DEPLOY inventory differs from a fresh build")
    for rel in expected_files:
        if (expected / rel).read_bytes() != (actual / rel).read_bytes():
            raise SystemExit(f"FATAL: generated file differs: {rel}")
    expected_upload = root / "UPLOAD"
    actual_upload = temp / "UPLOAD"
    expected_zips = sorted(path.name for path in expected_upload.glob("*.zip"))
    actual_zips = sorted(path.name for path in actual_upload.glob("*.zip"))
    if expected_zips != actual_zips:
        raise SystemExit("FATAL: UPLOAD zip inventory differs from a fresh build")
    for name in expected_zips:
        if (expected_upload / name).read_bytes() != (actual_upload / name).read_bytes():
            raise SystemExit(f"FATAL: generated upload differs: {name}")
    validate_upload_zips(root)
    for name in COMPAT_FILES:
        if (root / name).read_bytes() != (temp / name).read_bytes():
            raise SystemExit(f"FATAL: generated compatibility file differs: {name}")
    remove_tree(temp)
    print("check: PASS — DEPLOY, UPLOAD and compatibility files reproduce byte-for-byte")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--release", action="store_true",
                        help="refuse to build while any placeholder remains")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    source = here / "BLUEPRINT.md"
    check(source, here, args.release) if args.check else build(source, here, args.release)
