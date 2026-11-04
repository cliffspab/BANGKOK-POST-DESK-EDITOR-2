#!/usr/bin/env python3
"""Bangkok Post Desk Editor — Interactive Console, Unity Verifier & Google Drive Audit Server (Port 3000)."""

from __future__ import annotations

import difflib
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
FIREBASE_CONFIG_PATH = ROOT_DIR / "firebase-applet-config.json"

if str(UNITY_DIR) not in sys.path:
    sys.path.insert(0, str(UNITY_DIR))

# Configured Google Drive OAuth Scopes (synced with set_up_oauth)
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.activity",
    "https://www.googleapis.com/auth/drive.activity.readonly",
    "https://www.googleapis.com/auth/drive.appdata",
    "https://www.googleapis.com/auth/drive.apps.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.install",
    "https://www.googleapis.com/auth/drive.meet.readonly",
    "https://www.googleapis.com/auth/drive.metadata",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.photos.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.scripts",
]


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
        scoped = [
            e
            for e in all_entries
            if e["path"] == prefix or e["path"].startswith(prefix + ".")
        ]
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
        role = doc.get("role", "")
        desired_obj = updater.desired.get(role)
        projection = doc.get("desired_native_projection", {})
        docs.append({
            "role": role,
            "title": doc.get("title"),
            "document_id": doc.get("id") or (desired_obj.target.document_id if desired_obj else ""),
            "parent_path": doc.get("parent_path"),
            "source": doc.get("source"),
            "source_sha256": doc.get("source_sha256"),
            "desired_text_sha256": doc.get("desired_text_sha256"),
            "desired_source_projection_sha256": doc.get("source_projection_sha256"),
            "desired_native_projection_sha256": doc.get(
                "desired_native_projection_sha256"
            ),
            "paragraph_count": len(projection.get("paragraphs", [])),
            "transport_changes": len(doc.get("transport_changes", [])),
            "desired_text": desired_obj.text if desired_obj else "",
        })
    return {
        "edition": plan.payload.get("edition"),
        "root": plan.payload.get("root", {"id": config.root_id, "title": config.root_title}),
        "portable_hierarchy": list(config.portable_hierarchy),
        "status": plan.payload.get("status"),
        "unity_set_digest": plan.payload.get("unity_set_digest"),
        "plan_digest": plan.digest,
        "publish_order": list(config.publish_order),
        "google_apply": plan.payload.get("google_apply"),
        "documents": docs,
    }


def build_firebase_and_drive_config() -> dict[str, Any]:
    fb_config = (
        json.loads(_read_text(FIREBASE_CONFIG_PATH, "{}"))
        if FIREBASE_CONFIG_PATH.is_file()
        else {}
    )
    unity_cfg = (
        json.loads(_read_text(UNITY_DIR / "unity-config.json", "{}"))
        if (UNITY_DIR / "unity-config.json").is_file()
        else {}
    )
    return {
        "firebase": fb_config,
        "scopes": SCOPES,
        "unity_config": unity_cfg,
    }


def _evaluate_single_role(
    updater: Any,
    role: str,
    observed_payload: dict[str, Any],
) -> dict[str, Any]:
    """Compare an observed Google Drive document payload against local desired Unity state."""
    from unity_update import (
        CODEBLOCK_SOURCE_PROJECTION,
        NONBLANK_SOURCE_PROJECTION,
        UnityError,
        canonical_text,
        codeblock_projection_sha256,
        nonblank_projection_sha256,
        paragraph_projection_sha256,
        parse_identity,
        sha256_text,
    )

    desired = updater.desired[role]
    target = desired.target
    accessible = bool(observed_payload.get("accessible", False))
    error_msg = observed_payload.get("error")
    meta = observed_payload.get("meta") or {}
    raw_text = observed_payload.get("text")

    if not accessible or raw_text is None:
        return {
            "role": role,
            "title": target.title,
            "document_id": observed_payload.get("document_id") or target.document_id,
            "expected_parent_path": target.parent_path,
            "accessible": False,
            "status_code": "UNREACHABLE",
            "status_label": "Unreachable / Access Required",
            "error": error_msg or "Document could not be read from Google Drive.",
            "meta": meta,
            "identity": None,
            "checks": {
                "title_match": False,
                "mime_match": False,
                "not_trashed": False,
                "edition_match": False,
                "role_match": False,
                "status_match": False,
                "unity_set_match": False,
                "text_sha_match": False,
                "source_projection_match": False,
            },
            "hashes": {
                "desired_text_sha256": desired.text_sha256,
                "observed_text_sha256": None,
                "desired_source_projection_sha256": desired.source_projection_sha256,
                "observed_source_projection_sha256": None,
            },
            "diff": {
                "added": 0,
                "removed": 0,
                "unified_lines": [],
            },
            "desired_text": desired.text,
            "observed_text": "",
        }

    # Normalize text: Google Drive plain-text export may prepend UTF-8 BOM (\ufeff)
    cleaned_raw = str(raw_text).lstrip("\ufeff")
    norm_text = canonical_text(cleaned_raw)
    obs_text_sha = sha256_text(norm_text)
    paragraphs = tuple(norm_text.rstrip("\n").split("\n"))
    obs_para_sha = paragraph_projection_sha256(paragraphs)

    # Parse identity header
    identity_dict: dict[str, Any] | None = None
    identity_error: str | None = None
    try:
        parsed_id = parse_identity(norm_text, updater.config.header)
        identity_dict = {
            "role": parsed_id.role,
            "edition": parsed_id.edition,
            "status": parsed_id.status,
            "unity_set_digest": parsed_id.unity_set_digest,
            "source": parsed_id.source,
            "source_sha256": parsed_id.source_sha256,
        }
    except UnityError as exc:
        identity_error = str(exc)

    # Compute source projection hash for photo / directory if configured
    obs_source_proj_sha: str | None = None
    source_proj_error: str | None = None
    if target.native_source_projection is not None:
        proj_cfg = target.native_source_projection
        if len(paragraphs) >= proj_cfg.strip_leading_paragraphs:
            body_paras = paragraphs[proj_cfg.strip_leading_paragraphs :]
            try:
                if proj_cfg.algorithm == NONBLANK_SOURCE_PROJECTION:
                    obs_source_proj_sha = nonblank_projection_sha256(body_paras)
                elif proj_cfg.algorithm == CODEBLOCK_SOURCE_PROJECTION:
                    try:
                        obs_source_proj_sha = codeblock_projection_sha256(
                            body_paras, require_sentinels=True
                        )
                    except UnityError:
                        # Plain-text export may omit private-use sentinels; fall back to nonblank check
                        obs_source_proj_sha = nonblank_projection_sha256(
                            [p for p in body_paras if p not in ("\uec03", "\uec02")]
                        )
            except UnityError as exc:
                source_proj_error = str(exc)
        else:
            source_proj_error = "Document is shorter than its configured 5-line Unity envelope."

    title_match = meta.get("name") == target.title
    mime_match = meta.get("mimeType") == "application/vnd.google-apps.document"
    not_trashed = not bool(meta.get("trashed", False))
    edition_match = bool(identity_dict and identity_dict["edition"] == updater.edition)
    role_match = bool(identity_dict and identity_dict["role"] == role)
    status_match = bool(identity_dict and identity_dict["status"] == updater.config.status)
    unity_set_match = bool(
        identity_dict
        and identity_dict["unity_set_digest"] == updater.unity_set_digest
    )
    text_sha_match = obs_text_sha == desired.text_sha256
    source_proj_match = bool(
        desired.source_projection_sha256 is not None
        and obs_source_proj_sha == desired.source_projection_sha256
    )

    # Determine overall status
    if identity_error:
        status_code = "IDENTITY_ERROR"
        status_label = "Identity Header Error"
    elif not edition_match:
        status_code = "EDITION_DRIFT"
        status_label = f"Edition Drift ({identity_dict['edition'] if identity_dict else 'unknown'})"
    elif text_sha_match:
        status_code = "EXACT_MATCH"
        status_label = "Exact Match"
    elif source_proj_match and role_match and edition_match:
        status_code = "SOURCE_EQUIVALENT"
        status_label = "Native Source-Equivalent"
    else:
        status_code = "CONTENT_DIFF"
        status_label = "Content Diff Detected"

    # Compute unified diff
    desired_lines = desired.text.splitlines()
    observed_lines = norm_text.splitlines()
    diff_iter = difflib.unified_diff(
        desired_lines,
        observed_lines,
        fromfile=f"local/{target.source} ({updater.edition})",
        tofile=f"drive/{meta.get('name', target.title)}",
        lineterm="",
        n=3,
    )
    unified_lines = list(diff_iter)
    added = sum(1 for ln in unified_lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in unified_lines if ln.startswith("-") and not ln.startswith("---"))

    return {
        "role": role,
        "title": target.title,
        "document_id": observed_payload.get("document_id") or target.document_id,
        "expected_parent_path": target.parent_path,
        "accessible": True,
        "status_code": status_code,
        "status_label": status_label,
        "identity_error": identity_error,
        "source_projection_error": source_proj_error,
        "meta": meta,
        "identity": identity_dict,
        "checks": {
            "title_match": title_match,
            "mime_match": mime_match,
            "not_trashed": not_trashed,
            "edition_match": edition_match,
            "role_match": role_match,
            "status_match": status_match,
            "unity_set_match": unity_set_match,
            "text_sha_match": text_sha_match,
            "source_projection_match": source_proj_match,
        },
        "hashes": {
            "desired_text_sha256": desired.text_sha256,
            "observed_text_sha256": obs_text_sha,
            "desired_paragraph_sha256": desired.paragraph_projection_sha256,
            "observed_paragraph_sha256": obs_para_sha,
            "desired_source_projection_sha256": desired.source_projection_sha256,
            "observed_source_projection_sha256": obs_source_proj_sha,
        },
        "diff": {
            "added": added,
            "removed": removed,
            "unified_lines": unified_lines[:1200],
            "truncated": len(unified_lines) > 1200,
        },
        "desired_text": desired.text,
        "observed_text": norm_text,
    }


def audit_drive_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Audit observed Google Drive folder + 7 Unity docs against local Blueprint."""
    from unity_update import UnityUpdater, load_config

    config = load_config(UNITY_DIR / "unity-config.json")
    updater = UnityUpdater(config, BLUEPRINT_DIR, None)

    root_obs = body.get("root") or {}
    hierarchy_obs = body.get("hierarchy") or {}
    docs_obs = body.get("documents") or {}

    root_meta = root_obs.get("meta") or {}
    root_accessible = bool(root_obs.get("accessible", False))
    root_checks = {
        "accessible": root_accessible,
        "id": config.root_id,
        "expected_title": config.root_title,
        "observed_title": root_meta.get("name"),
        "title_match": root_meta.get("name") == config.root_title,
        "is_folder": root_meta.get("mimeType") == "application/vnd.google-apps.folder",
        "in_shared_drive": bool(root_meta.get("driveId")),
        "drive_id": root_meta.get("driveId"),
        "not_trashed": not bool(root_meta.get("trashed", False)),
        "error": root_obs.get("error"),
    }

    results = []
    for role in config.publish_order:
        role_obs = docs_obs.get(role) or {}
        results.append(_evaluate_single_role(updater, role, role_obs))

    exact_count = sum(
        1 for r in results if r["status_code"] in ("EXACT_MATCH", "SOURCE_EQUIVALENT")
    )
    reachable_count = sum(1 for r in results if r["accessible"])

    return {
        "edition": updater.edition,
        "unity_set_digest": updater.unity_set_digest,
        "root": root_checks,
        "hierarchy": hierarchy_obs,
        "summary": {
            "total_targets": len(results),
            "reachable_targets": reachable_count,
            "verified_targets": exact_count,
            "all_verified": exact_count == len(results) and root_accessible,
        },
        "documents": results,
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

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        if route == "/api/health":
            self._send_json({"status": "ok"})
            return
        if route == "/api/firebase-config":
            self._send_json(build_firebase_and_drive_config())
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

        if route == "/api/unity/audit-drive":
            try:
                payload = self._read_json_body()
                self._send_json(audit_drive_payload(payload))
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if route == "/api/unity/diff-custom":
            try:
                from unity_update import UnityUpdater, load_config

                payload = self._read_json_body()
                role = str(payload.get("role", "edit")).lower()
                config = load_config(UNITY_DIR / "unity-config.json")
                updater = UnityUpdater(config, BLUEPRINT_DIR, None)
                if role not in updater.desired:
                    self._send_json({"error": f"Unknown Unity role: {role}"}, status=400)
                    return
                res = _evaluate_single_role(updater, role, payload.get("observed") or {})
                self._send_json(res)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        self._send_json({"error": "Not found"}, status=404)


def main() -> None:
    port = int(os.environ.get("PORT", 3000))
    server = ThreadingHTTPServer(("0.0.0.0", port), DeskRequestHandler)
    print(f"Bangkok Post Desk Editor listening on http://0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
