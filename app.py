#!/usr/bin/env python3
"""Bangkok Post Desk Editor — Interactive Console & Verification Server (Port 3000)."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent
BLUEPRINT_DIR = ROOT_DIR / "Blueprint"
UNITY_DIR = BLUEPRINT_DIR / "unity"
STATIC_DIR = ROOT_DIR / "static"

if str(UNITY_DIR) not in sys.path:
    sys.path.insert(0, str(UNITY_DIR))


def _read_text(path: Path, default: str = "") -> str:
    if not path.is_file():
        return default
    return path.read_text(encoding="utf-8")


def _parse_directory_entries(yaml_text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse Blueprint/DIRECTORY.yaml indentation hierarchy into searchable entries."""
    branches: list[str] = []
    entries: list[dict[str, str]] = []
    stack: list[tuple[int, str]] = []
    in_references = False
    multiline_key: str | None = None
    multiline_path: str = ""
    multiline_indent: int = 0
    multiline_lines: list[str] = []

    def flush_multiline() -> None:
        nonlocal multiline_key, multiline_path, multiline_lines
        if multiline_key is not None:
            entries.append({
                "path": multiline_path,
                "key": multiline_key,
                "value": " ".join(line.strip() for line in multiline_lines if line.strip()),
            })
            multiline_key = None
            multiline_path = ""
            multiline_lines = []

    for raw_line in yaml_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if multiline_key is not None:
            if indent > multiline_indent:
                multiline_lines.append(stripped)
                continue
            flush_multiline()

        if indent == 0 and stripped == "references:":
            in_references = True
            stack = [(0, "references")]
            continue
        if indent == 0 and stripped.endswith(":"):
            in_references = False
            continue
        if not in_references:
            continue

        while stack and stack[-1][0] >= indent:
            stack.pop()

        if stripped.startswith("- "):
            item_val = stripped[2:].strip().strip("\"'")
            parent_path = ".".join(p for _, p in stack)
            parent_key = stack[-1][1] if stack else "item"
            entries.append({
                "path": parent_path,
                "key": parent_key,
                "value": item_val,
            })
            continue

        if ":" in stripped:
            key_part, val_part = stripped.split(":", 1)
            key = key_part.strip().strip("\"'")
            val = val_part.strip()
            if indent == 2 and key not in branches:
                branches.append(key)

            current_path = ".".join([p for _, p in stack] + [key])
            if not val:
                stack.append((indent, key))
            elif val in (">", "|"):
                multiline_key = key
                multiline_path = current_path
                multiline_indent = indent
                multiline_lines = []
            else:
                clean_val = val.strip("\"'")
                entries.append({
                    "path": current_path,
                    "key": key,
                    "value": clean_val,
                })

    flush_multiline()
    return branches, entries


def _parse_decisions_yaml(yaml_text: str) -> list[dict[str, str]]:
    """Parse DECISIONS-OPEN.yaml entries using pure standard library."""
    decisions: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    active_field: str | None = None
    field_indent: int = 0

    for raw_line in yaml_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if indent == 2 and stripped.startswith("- key:"):
            if current:
                decisions.append(current)
            current = {"key": stripped.split(":", 1)[1].strip().strip("\"'")}
            active_field = None
            continue

        if current is None:
            continue

        if indent == 4 and ":" in stripped:
            k, v = stripped.split(":", 1)
            key_name = k.strip()
            val_str = v.strip()
            if val_str in (">", "|", ""):
                current[key_name] = ""
                active_field = key_name
                field_indent = indent
            else:
                current[key_name] = val_str.strip("\"'")
                active_field = None
        elif active_field and indent > field_indent:
            prev = current.get(active_field, "")
            current[active_field] = (prev + "\n" + stripped).strip()

    if current:
        decisions.append(current)
    return decisions


def build_overview() -> dict[str, Any]:
    version = _read_text(BLUEPRINT_DIR / "VERSION.txt", "unknown").strip()
    receipt_path = BLUEPRINT_DIR / "build-receipt.json"
    receipt = (
        json.loads(_read_text(receipt_path, "{}"))
        if receipt_path.is_file()
        else {}
    )
    plugin_path = ROOT_DIR / "Control" / "plugin" / ".codex-plugin" / "plugin.json"
    plugin_manifest = (
        json.loads(_read_text(plugin_path, "{}"))
        if plugin_path.is_file()
        else {}
    )
    return {
        "edition": version,
        "receipt": receipt,
        "control_plugin": plugin_manifest,
        "workplan": _read_text(ROOT_DIR / "WORKPLAN.md"),
        "commits_pending": _read_text(ROOT_DIR / "COMMITS-PENDING.md"),
        "changelog": _read_text(ROOT_DIR / "CHANGELOG.md"),
        "start_here": _read_text(ROOT_DIR / "bootstrap" / "00_START-HERE.md"),
    }


def build_skills() -> dict[str, Any]:
    skill_map = {
        "boot": BLUEPRINT_DIR / "DEPLOY" / "routed" / "BOOT.md",
        "edit": BLUEPRINT_DIR / "DEPLOY" / "routed" / "edit.md",
        "check": BLUEPRINT_DIR / "DEPLOY" / "routed" / "modules" / "check.md",
        "photo": BLUEPRINT_DIR / "DEPLOY" / "routed" / "modules" / "photo.md",
        "pr": BLUEPRINT_DIR / "DEPLOY" / "routed" / "modules" / "pr.md",
    }
    receipt_path = BLUEPRINT_DIR / "build-receipt.json"
    receipt = (
        json.loads(_read_text(receipt_path, "{}"))
        if receipt_path.is_file()
        else {}
    )
    upload_zips = receipt.get("upload_zips", {})

    items = []
    for key, path in skill_map.items():
        content = _read_text(path)
        zip_name = f"{key}.zip"
        zip_path = BLUEPRINT_DIR / "UPLOAD" / zip_name
        items.append({
            "id": key,
            "name": key.upper(),
            "routed_path": str(path.relative_to(ROOT_DIR)),
            "bytes": path.stat().st_size if path.is_file() else 0,
            "lines": content.count("\n") + (1 if content else 0),
            "zip_name": zip_name,
            "zip_bytes": zip_path.stat().st_size if zip_path.is_file() else 0,
            "zip_sha256": upload_zips.get(zip_name, ""),
            "content": content,
        })
    return {"skills": items}


def build_directory(q: str, branch: str) -> dict[str, Any]:
    dir_path = BLUEPRINT_DIR / "DIRECTORY.yaml"
    yaml_text = _read_text(dir_path)
    branches, all_entries = _parse_directory_entries(yaml_text)

    if branch and branch != "all":
        prefix = f"references.{branch}"
        scoped = [e for e in all_entries if e["path"] == prefix or e["path"].startswith(prefix + ".")]
    else:
        scoped = all_entries

    query_norm = q.strip().lower()
    if query_norm:
        filtered = [
            item
            for item in scoped
            if query_norm in item["path"].lower()
            or query_norm in item["key"].lower()
            or query_norm in item["value"].lower()
        ]
    else:
        filtered = scoped

    return {
        "branches": branches,
        "total_entries": len(scoped),
        "matched_entries": len(filtered),
        "entries": filtered[:250],
    }


def build_unity_plan() -> dict[str, Any]:
    from unity_update import UnityUpdater, load_config

    config = load_config(UNITY_DIR / "unity-config.json")
    updater = UnityUpdater(config, BLUEPRINT_DIR, None)
    plan = updater.source_plan()
    docs = []
    for doc in plan.payload.get("documents", []):
        projection = doc.get("desired_native_projection", {})
        docs.append({
            "role": doc.get("role"),
            "title": doc.get("title"),
            "document_id": doc.get("document_id"),
            "parent_path": doc.get("parent_path"),
            "source": doc.get("source"),
            "source_sha256": doc.get("source_sha256"),
            "desired_text_sha256": doc.get("desired_text_sha256"),
            "desired_native_projection_sha256": doc.get(
                "desired_native_projection_sha256"
            ),
            "paragraph_count": len(projection.get("paragraphs", [])),
            "transport_changes": len(doc.get("transport_changes", [])),
        })
    return {
        "edition": plan.payload.get("edition"),
        "root_title": plan.payload.get("root_title"),
        "status": plan.payload.get("status"),
        "unity_set_digest": plan.payload.get("unity_set_digest"),
        "plan_digest": plan.digest,
        "publish_order": list(config.publish_order),
        "google_apply": plan.payload.get("google_apply"),
        "documents": docs,
    }


class DeskRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, download_name: str | None = None) -> None:
        if not path.is_file():
            self._send_json({"error": "Not found"}, status=404)
            return
        data = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(path))
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{download_name}"'
            )
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        if route == "/api/health":
            self._send_json({"status": "ok"})
            return
        if route == "/api/overview":
            self._send_json(build_overview())
            return
        if route == "/api/skills":
            self._send_json(build_skills())
            return
        if route == "/api/directory":
            q = qs.get("q", [""])[0]
            branch = qs.get("branch", ["all"])[0]
            self._send_json(build_directory(q, branch))
            return
        if route == "/api/decisions":
            text = _read_text(ROOT_DIR / "DECISIONS-OPEN.yaml")
            self._send_json({"decisions": _parse_decisions_yaml(text)})
            return
        if route == "/api/unity/plan":
            try:
                self._send_json(build_unity_plan())
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        zip_match = re.fullmatch(r"/api/upload/(boot|edit|check|photo|pr)\.zip", route)
        if zip_match:
            skill_name = zip_match.group(1)
            zip_path = BLUEPRINT_DIR / "UPLOAD" / f"{skill_name}.zip"
            self._send_file(zip_path, download_name=f"{skill_name}.zip")
            return

        if route.startswith("/static/"):
            rel = route.removeprefix("/static/")
            target = (STATIC_DIR / rel).resolve()
            if STATIC_DIR.resolve() in target.parents and target.is_file():
                self._send_file(target)
                return
            self._send_json({"error": "Asset not found"}, status=404)
            return

        self._send_file(STATIC_DIR / "index.html")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path

        if route == "/api/verify/blueprint":
            proc = subprocess.run(
                [sys.executable, str(BLUEPRINT_DIR / "build.py"), "--check", "--release"],
                cwd=str(BLUEPRINT_DIR),
                capture_output=True,
                text=True,
                timeout=30,
            )
            self._send_json({
                "passed": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            })
            return

        if route == "/api/verify/unity":
            env = os.environ.copy()
            env["PYTHONPATH"] = str(UNITY_DIR)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(UNITY_DIR / "tests"),
                    "-v",
                ],
                cwd=str(ROOT_DIR),
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self._send_json({
                "passed": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            })
            return

        self._send_json({"error": "Not found"}, status=404)


def main() -> None:
    port = int(os.environ.get("PORT", 3000))
    server = ThreadingHTTPServer(("0.0.0.0", port), DeskRequestHandler)
    print(f"Bangkok Post Desk Editor listening on http://0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
