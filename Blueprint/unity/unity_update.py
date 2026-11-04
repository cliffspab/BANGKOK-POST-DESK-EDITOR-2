#!/usr/bin/env python3
"""Plan and verify guarded BKP 3.0 Unity projections.

Dry-run/source validation is the default.  The state backend can rehearse a
digest-confirmed content-first/Boot-last update, but Google writes are hard
disabled until an approved formatting-preserving renderer and verifier exist.
The module has no build or publication side effects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Protocol


GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
REQUIRED_ROLES = {
    "boot", "blueprint", "edit", "check", "photo", "pr", "directory"
}
EDITION_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROJECTION_NORMALIZATION = "paragraph-lf-nfc-v1"
NONBLANK_SOURCE_PROJECTION = "nonblank-lines-lf-nfc-v1"
CODEBLOCK_SOURCE_PROJECTION = (
    "codeblock-sentinels-nonblank-lines-lf-nfc-v1"
)
GOOGLE_CODEBLOCK_SENTINELS = ("\uec03", "\uec02")
REVIEW_SNAPSHOT_KIND = "unity-observed-baseline"
NATIVE_PROJECTION_SCHEMA = "bkp-google-docs-native-projection-v2"
GOOGLE_DOC_URL = "https://docs.google.com/document/d/{document_id}/edit"

BLUEPRINT_BOOT_MARKER = "<!-- COMPONENT: BOOT -->"
BLUEPRINT_EDIT_MARKER = "<!-- COMPONENT: EDIT -->"
BLUEPRINT_BOOT_POINTER = (
    "<!-- COMPONENT: BOOT -->\n\n"
    "# BOOT\n\n"
    "Boot is the sole manifest and ignition point for this Unity set. Open the "
    "current Boot document to select and validate the Blueprint, Edit, Check, "
    "Photo, PR and Directory roles. This embedded section is a pointer only; "
    "it does not duplicate Boot's routes or rules.\n\n"
)

EDIT_TRANSPORT_OLD = (
    "- Package structure. In a BOOT-routed deployment use its `INDEX.yaml`. In "
    "a skill deployment use only the companions deliberately bundled with that "
    "skill. If the package supplies `references/edit.md`, read it once while it "
    "remains in context and reopen it when needed. For the Directory, use the "
    "generated `DIRECTORY.txt` at the DEPLOY umbrella root; a skill deployment "
    "bundles it as `references/DIRECTORY.txt`. Read its index, then consult each "
    "route the copy touches: names, places, organisations, dates, numbers, units or "
    "titles. Reopen routes as needed. Another target system may use "
    "a format-equivalent name. Do not depend on a provider, account, URL or "
    "installation path. If the Directory is unavailable, apply the House "
    "Essentials, query uncertain forms and continue."
)
EDIT_TRANSPORT_NEW = (
    "- Package structure. Load this role through the current Boot manifest. In "
    "Google Drive, follow Boot's permanent document links. In a GitHub, website "
    "or local tree, resolve Boot's portable route relative to Boot. Read the "
    "Directory index, then consult each route the copy touches: names, places, "
    "organisations, dates, numbers, units, titles or vocabulary. Reopen routes as "
    "needed. Accept a document only when its ROLE and SOURCE EDITION match Boot. "
    "Do not depend on a provider, account or installation path. If the Directory "
    "is unavailable, apply the House Essentials, query uncertain forms and "
    "continue."
)
CHECK_TRANSPORT_OLD = (
    "Runs on top of the shared edit method bundled with the installed skill or "
    "named by the selected deployment. This file sets scope and return; edit "
    "supplies the shared rules, including [P2] verification."
)
CHECK_TRANSPORT_NEW = (
    "Runs on top of the Edit role selected by Boot. This document sets scope and "
    "return; Edit supplies the shared rules, including [P2] verification."
)
PHOTO_TRANSPORT_OLD = (
    "Runs on top of the shared edit method bundled with the installed skill or "
    "named by the selected deployment: its House Essentials, [P1] fit and [P2] "
    "verification apply. This file alone holds the photo method and return."
)
PHOTO_TRANSPORT_NEW = (
    "Runs on top of the Edit role selected by Boot: its House Essentials, [P1] "
    "fit and [P2] verification apply. This document alone holds the photo method "
    "and return."
)
PR_TRANSPORT_OLD = (
    "Runs on top of the shared edit method bundled with the installed skill or "
    "named by the selected deployment. This file sets PR scope and return; `edit` "
    "supplies shared house forms and [P2] verification."
)
PR_TRANSPORT_NEW = (
    "Runs on top of the Edit role selected by Boot. This document sets PR scope "
    "and return; Edit supplies shared house forms and [P2] verification."
)


class UnityError(RuntimeError):
    """A guard failed; no further publication step is permitted."""


def canonical_text(text: str) -> str:
    """Canonical text representation used for plans and post-write checks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n") + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(canonical_text(text).encode("utf-8")).hexdigest()


def normalized_paragraph_text(paragraphs: Iterable[str]) -> str:
    """NFC paragraphs joined by LF with exactly one terminal LF.

    This is the target-observation normalization used by the connector audit
    and by review snapshots.  Paragraph values stay otherwise byte-sensitive:
    leading/trailing spaces and non-empty whitespace-only paragraphs survive.
    """
    values = [
        unicodedata.normalize(
            "NFC", value.replace("\r\n", "\n").replace("\r", "\n")
        )
        for value in paragraphs
    ]
    return "\n".join(values) + "\n"


def paragraph_projection_sha256(paragraphs: Iterable[str]) -> str:
    return hashlib.sha256(
        normalized_paragraph_text(paragraphs).encode("utf-8")
    ).hexdigest()


def nonblank_source_projection(lines: Iterable[str]) -> str:
    """NFC/LF projection dropping only zero-length lines.

    A line containing spaces is not empty and is retained.  No non-empty line
    is stripped, so YAML indentation and trailing whitespace remain guarded.
    """
    kept: list[str] = []
    for line in lines:
        value = unicodedata.normalize(
            "NFC", line.replace("\r\n", "\n").replace("\r", "\n")
        ).rstrip("\n")
        if value != "":
            kept.append(value)
    return "\n".join(kept).rstrip("\n") + "\n"


def nonblank_projection_sha256(lines: Iterable[str]) -> str:
    return hashlib.sha256(
        nonblank_source_projection(lines).encode("utf-8")
    ).hexdigest()


def codeblock_projection_sha256(
    paragraphs: Iterable[str], *, require_sentinels: bool,
    markdown_source: bool = False
) -> str:
    """Project a native code block without treating its sentinels as text.

    The two private-use markers are accepted only as distinct, standalone
    paragraphs with at least one paragraph between them.  This proves their
    structural bracketing before omitting them; other private-use content is
    not ignored.
    """
    values = list(paragraphs)
    if markdown_source:
        if require_sentinels:
            raise UnityError(
                "photo: markdown-source projection cannot require native sentinels"
            )
        fence_positions = [
            index for index, value in enumerate(values)
            if re.fullmatch(r"```(?:[A-Za-z0-9_-]+)?\s*", value)
        ]
        if len(fence_positions) != 2 or fence_positions[0] >= fence_positions[1] - 1:
            raise UnityError(
                "photo: source projection requires exactly one non-empty fenced block"
            )
        values = [
            value for index, value in enumerate(values)
            if index not in set(fence_positions)
        ]
        return nonblank_projection_sha256(values)
    positions: list[int] = []
    for sentinel in GOOGLE_CODEBLOCK_SENTINELS:
        matches = [index for index, value in enumerate(values) if value == sentinel]
        if require_sentinels and len(matches) != 1:
            raise UnityError(
                "photo: native code-block projection requires one standalone "
                f"U+{ord(sentinel):04X} sentinel; found {len(matches)}"
            )
        if len(matches) > 1:
            raise UnityError(
                f"photo: repeated U+{ord(sentinel):04X} code-block sentinel"
            )
        positions.extend(matches)
    if positions:
        if (
            len(positions) != 2
            or positions[0] >= positions[1] - 1
        ):
            raise UnityError(
                "photo: code-block sentinels do not bracket native content"
            )
        sentinel_set = set(GOOGLE_CODEBLOCK_SENTINELS)
        values = [value for value in values if value not in sentinel_set]
    elif require_sentinels:
        raise UnityError("photo: native code-block sentinels are missing")
    return nonblank_projection_sha256(values)


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TransportChange:
    name: str
    before_sha256: str
    after_sha256: str


def _exact_once_replace(
    text: str, before: str, after: str, *, name: str
) -> tuple[str, TransportChange]:
    count = text.count(before)
    if count != 1:
        raise UnityError(
            f"{name}: transport selector must match exactly once; found {count}"
        )
    return (
        text.replace(before, after, 1),
        TransportChange(name, sha256_text(before), sha256_text(after)),
    )


def _replace_blueprint_boot(text: str) -> tuple[str, TransportChange]:
    if text.count(BLUEPRINT_BOOT_MARKER) != 1:
        raise UnityError(
            "blueprint.boot_pointer: COMPONENT: BOOT marker must occur exactly once"
        )
    if text.count(BLUEPRINT_EDIT_MARKER) != 1:
        raise UnityError(
            "blueprint.boot_pointer: COMPONENT: EDIT marker must occur exactly once"
        )
    start = text.index(BLUEPRINT_BOOT_MARKER)
    end = text.index(BLUEPRINT_EDIT_MARKER)
    if end <= start:
        raise UnityError(
            "blueprint.boot_pointer: COMPONENT: EDIT must follow COMPONENT: BOOT"
        )
    before = text[start:end]
    replaced = text[:start] + BLUEPRINT_BOOT_POINTER + text[end:]
    return (
        replaced,
        TransportChange(
            "blueprint.boot_pointer",
            sha256_text(before),
            sha256_text(BLUEPRINT_BOOT_POINTER),
        ),
    )


def transport_source(
    role: str, source_text: str
) -> tuple[str, tuple[TransportChange, ...]]:
    """Apply only the reviewed, exact-once Unity transport substitutions."""
    text = canonical_text(source_text)
    changes: list[TransportChange] = []
    if role == "blueprint":
        text, change = _replace_blueprint_boot(text)
        changes.append(change)
        replacements = (
            ("blueprint.edit_transport", EDIT_TRANSPORT_OLD, EDIT_TRANSPORT_NEW),
            ("blueprint.check_transport", CHECK_TRANSPORT_OLD, CHECK_TRANSPORT_NEW),
            ("blueprint.photo_transport", PHOTO_TRANSPORT_OLD, PHOTO_TRANSPORT_NEW),
            ("blueprint.pr_transport", PR_TRANSPORT_OLD, PR_TRANSPORT_NEW),
        )
    elif role == "edit":
        replacements = (("edit.transport", EDIT_TRANSPORT_OLD, EDIT_TRANSPORT_NEW),)
    elif role == "check":
        replacements = (("check.transport", CHECK_TRANSPORT_OLD, CHECK_TRANSPORT_NEW),)
    elif role == "photo":
        replacements = (("photo.transport", PHOTO_TRANSPORT_OLD, PHOTO_TRANSPORT_NEW),)
    elif role == "pr":
        replacements = (("pr.transport", PR_TRANSPORT_OLD, PR_TRANSPORT_NEW),)
    else:
        replacements = ()
    for name, before, after in replacements:
        text, change = _exact_once_replace(text, before, after, name=name)
        changes.append(change)
    return canonical_text(text), tuple(changes)


def _merge_runs(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for raw in runs:
        run = {key: value for key, value in raw.items() if value not in (None, False)}
        text = str(run.get("text", ""))
        run["text"] = text
        prepared.append(run)
    nonempty = [run for run in prepared if run["text"] != ""]
    if not nonempty:
        styled = [run for run in prepared if set(run) != {"text"}]
        return [styled[0]] if styled else [{"text": ""}]

    merged: list[dict[str, Any]] = []
    for run in nonempty:
        if merged:
            previous_style = {key: value for key, value in merged[-1].items() if key != "text"}
            current_style = {key: value for key, value in run.items() if key != "text"}
            if previous_style == current_style:
                merged[-1]["text"] += text
                continue
        merged.append(run)
    return merged


def _inline_runs(text: str) -> list[dict[str, Any]]:
    """Parse the bounded inline Markdown used by the reviewed source set."""
    tokens = re.compile(
        r"\[([^\]\n]+)\]\(([^)\n]+)\)|"
        r"\*\*([^*\n]+)\*\*|"
        r"`([^`\n]+)`|"
        r"(?<!\*)\*([^*\n]+)\*(?!\*)"
    )
    runs: list[dict[str, Any]] = []
    cursor = 0
    for match in tokens.finditer(text):
        if match.start() > cursor:
            runs.append({"text": text[cursor:match.start()]})
        if match.group(1) is not None:
            runs.append({"text": match.group(1), "link": match.group(2)})
        elif match.group(3) is not None:
            runs.append({"text": match.group(3), "bold": True})
        elif match.group(4) is not None:
            runs.append({
                "text": match.group(4),
                "code": True,
                "font_family": "Roboto Mono",
            })
        else:
            runs.append({"text": match.group(5), "italic": True})
        cursor = match.end()
    if cursor < len(text):
        runs.append({"text": text[cursor:]})
    return _merge_runs(runs)


def _paragraph(
    text: str, *, named_style: str = "NORMAL_TEXT",
    list_kind: str | None = None, nesting_level: int = 0,
    code_block: bool = False, literal: bool = False,
) -> dict[str, Any]:
    if code_block or literal:
        runs = _merge_runs([{
            "text": text,
            "code": True,
            "font_family": "Roboto Mono",
        }])
    else:
        runs = _inline_runs(text)
    result: dict[str, Any] = {
        "named_style": named_style,
        "runs": runs,
    }
    if list_kind is not None:
        result["list"] = {
            "kind": list_kind,
            "nesting_level": nesting_level,
        }
    return result


def _strip_source_frontmatter(text: str) -> list[str]:
    lines = canonical_text(text).rstrip("\n").split("\n")
    if lines and lines[0] == "---":
        try:
            end = lines.index("---", 1)
        except ValueError as exc:
            raise UnityError("source front matter is not closed") from exc
        lines = lines[end + 1:]
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(r"\s*<!--\s*COMPONENT:\s*[^>]+-->\s*", line):
            index += 1
            while index < len(lines) and lines[index] == "":
                index += 1
            if index < len(lines) and lines[index] == "---":
                try:
                    end = lines.index("---", index + 1)
                except ValueError as exc:
                    raise UnityError("embedded component front matter is not closed") from exc
                index = end + 1
                while index < len(lines) and lines[index] == "":
                    index += 1
            continue
        if re.fullmatch(r"\s*<!--.*?-->\s*", line):
            index += 1
            continue
        result.append(line)
        index += 1
    return result


def markdown_native_projection(text: str) -> dict[str, Any]:
    """Create a deterministic proposed Google Docs structure from Markdown.

    This is a planning representation, not a writer.  It deliberately covers
    the structures present in the locked source set: headings, lists, bold,
    emphasis, inline code, hyperlinks and fenced monospace blocks.
    """
    lines = _strip_source_frontmatter(text)
    paragraphs: list[dict[str, Any]] = []
    pending: list[str] = []
    pending_list: tuple[str, int] | None = None
    in_code = False

    def flush() -> None:
        nonlocal pending, pending_list
        if not pending:
            return
        value = " ".join(part.strip() for part in pending).strip()
        if pending_list is None:
            paragraphs.append(_paragraph(value))
        else:
            paragraphs.append(_paragraph(
                value,
                list_kind=pending_list[0],
                nesting_level=pending_list[1],
            ))
        pending = []
        pending_list = None

    for line in lines:
        if re.fullmatch(r"\s*```(?:[A-Za-z0-9_-]+)?\s*", line):
            flush()
            in_code = not in_code
            continue
        if in_code:
            paragraphs.append(_paragraph(line, code_block=True))
            continue
        if re.fullmatch(r"\s*<!--.*?-->\s*", line):
            continue
        heading = re.fullmatch(r"\s*(#{1,6})\s+(.+?)\s*", line)
        if heading:
            flush()
            paragraphs.append(_paragraph(
                heading.group(2),
                named_style=f"HEADING_{len(heading.group(1))}",
            ))
            continue
        if re.fullmatch(
            r"(?:ROLE|TITLE|ROUTE|SOURCE|SOURCE-SHA256|UNITY SET):\s+.+",
            line,
        ):
            flush()
            paragraphs.append(_paragraph(line))
            continue
        unordered = re.fullmatch(r"(\s*)[-+*]\s+(.+)", line)
        ordered = re.fullmatch(r"(\s*)\d+[.)]\s+(.+)", line)
        if unordered or ordered:
            flush()
            match = unordered or ordered
            assert match is not None
            pending = [match.group(2)]
            pending_list = (
                "unordered" if unordered else "ordered",
                len(match.group(1).expandtabs(4)) // 2,
            )
            continue
        if line == "":
            flush()
            paragraphs.append(_paragraph(""))
            continue
        if pending_list is not None:
            pending.append(line)
        else:
            pending.append(line)
    if in_code:
        raise UnityError("source contains an unclosed fenced code block")
    flush()

    # Google Docs cannot retain an orphan list item at a deep nesting level:
    # createParagraphBullets normalises it to level 0 unless the immediately
    # preceding list structure supplies its parent chain.  Normalise the
    # planned projection the same way so indented YAML-like bullets embedded
    # in the complete Blueprint have a stable native representation.  The
    # standalone Directory remains literal and preserves its exact indentation.
    previous_level: int | None = None
    for paragraph in paragraphs:
        list_data = paragraph.get("list")
        if list_data is None:
            previous_level = None
            continue
        level = int(list_data["nesting_level"])
        if level > 0 and (previous_level is None or level > previous_level + 1):
            list_data["nesting_level"] = 0
            level = 0
        previous_level = level
    return {"schema": NATIVE_PROJECTION_SCHEMA, "paragraphs": paragraphs}


def literal_native_projection(text: str) -> dict[str, Any]:
    lines = canonical_text(text).rstrip("\n").split("\n")
    return {
        "schema": NATIVE_PROJECTION_SCHEMA,
        "paragraphs": [_paragraph(line, literal=True) for line in lines],
    }


def _paragraph_text_value(paragraph: dict[str, Any]) -> str:
    return "".join(str(run.get("text", "")) for run in paragraph.get("runs", []))


def _projection_text(projection: dict[str, Any]) -> str:
    return normalized_paragraph_text(
        _paragraph_text_value(paragraph)
        for paragraph in projection.get("paragraphs", [])
    )


def _projection_format_link_payload(
    projection: dict[str, Any]
) -> dict[str, Any]:
    paragraphs: list[dict[str, Any]] = []
    for index, paragraph in enumerate(projection.get("paragraphs", [])):
        item: dict[str, Any] = {
            "index": index,
            "named_style": paragraph.get("named_style", "NORMAL_TEXT"),
            "runs": [],
        }
        for run in paragraph.get("runs", []):
            item["runs"].append({
                "length": len(str(run.get("text", ""))),
                **{key: value for key, value in run.items() if key != "text"},
            })
        for key in ("list",):
            if key in paragraph:
                item[key] = paragraph[key]
        paragraphs.append(item)
    return {"schema": NATIVE_PROJECTION_SCHEMA, "paragraphs": paragraphs}


GOOGLE_NAMED_STYLES = {
    "NORMAL_TEXT",
    "TITLE",
    "SUBTITLE",
    "HEADING_1",
    "HEADING_2",
    "HEADING_3",
    "HEADING_4",
    "HEADING_5",
    "HEADING_6",
}
GOOGLE_LIST_PRESETS = {
    "unordered": "BULLET_DISC_CIRCLE_SQUARE",
    "ordered": "NUMBERED_DECIMAL_ALPHA_ROMAN",
}
GOOGLE_PARAGRAPH_RESET_FIELDS = (
    "alignment,avoidWidowAndOrphan,borderBetween,borderBottom,borderLeft,"
    "borderRight,borderTop,indentEnd,indentFirstLine,indentStart,"
    "keepLinesTogether,keepWithNext,lineSpacing,pageBreakBefore,shading,"
    "spaceAbove,spaceBelow,spacingMode"
)


def _utf16_length(value: str) -> int:
    """Return the number of Google Docs index units in *value*."""
    return len(value.encode("utf-16-le")) // 2


def require_disposable_proof_target(
    document_id: str, config: "UnityConfig"
) -> None:
    """Refuse a writer proof aimed at any protected Unity document."""
    if not isinstance(document_id, str) or not document_id:
        raise UnityError("disposable proof requires an explicit document ID")
    protected = {target.document_id for target in config.targets}
    if document_id in protected:
        raise UnityError(
            "disposable writer proof refuses every protected Unity document ID"
        )


def compile_google_docs_requests(
    native_projection: dict[str, Any], *, current_end_index: int,
    tab_id: str,
) -> list[dict[str, Any]]:
    """Compile a complete native projection into guarded Docs API requests.

    The caller supplies the current body end index and sends the returned
    requests with ``writeControl.requiredRevisionId``.  This function does not
    perform a write and cannot enable Google apply.  List nesting is encoded as
    leading tabs because ``createParagraphBullets`` consumes those tabs and
    converts them to native nesting levels.
    """
    if native_projection.get("schema") != NATIVE_PROJECTION_SCHEMA:
        raise UnityError("native projection schema is unsupported")
    if not isinstance(current_end_index, int) or current_end_index < 2:
        raise UnityError("current Google document end index is invalid")
    if not isinstance(tab_id, str) or not tab_id:
        raise UnityError("Google document tab ID is required")
    paragraphs = native_projection.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise UnityError("native projection must contain at least one paragraph")

    allowed_paragraph_keys = {"named_style", "runs", "list"}
    allowed_run_keys = {
        "text", "bold", "italic", "underline", "strikethrough",
        "link", "code", "font_family",
    }
    insertion_parts: list[str] = []
    paragraph_ranges: list[dict[str, Any]] = []
    cursor = 1

    for paragraph_index, paragraph in enumerate(paragraphs):
        if not isinstance(paragraph, dict):
            raise UnityError(
                f"native projection paragraph {paragraph_index} is not an object"
            )
        unknown_paragraph = set(paragraph) - allowed_paragraph_keys
        if unknown_paragraph:
            raise UnityError(
                f"native projection paragraph {paragraph_index} has unsupported "
                f"fields: {sorted(unknown_paragraph)}"
            )
        named_style = paragraph.get("named_style", "NORMAL_TEXT")
        if named_style not in GOOGLE_NAMED_STYLES:
            raise UnityError(
                f"native projection paragraph {paragraph_index} has unsupported "
                f"named style {named_style!r}"
            )
        runs = paragraph.get("runs")
        if not isinstance(runs, list) or not runs:
            raise UnityError(
                f"native projection paragraph {paragraph_index} has no runs"
            )

        list_data = paragraph.get("list")
        prefix = ""
        list_kind: str | None = None
        if list_data is not None:
            if not isinstance(list_data, dict):
                raise UnityError(
                    f"native projection paragraph {paragraph_index} list is malformed"
                )
            if set(list_data) != {"kind", "nesting_level"}:
                raise UnityError(
                    f"native projection paragraph {paragraph_index} list fields "
                    "are malformed"
                )
            list_kind = list_data.get("kind")
            nesting_level = list_data.get("nesting_level")
            if list_kind not in GOOGLE_LIST_PRESETS:
                raise UnityError(
                    f"native projection paragraph {paragraph_index} list kind "
                    f"is unsupported: {list_kind!r}"
                )
            if (
                not isinstance(nesting_level, int)
                or isinstance(nesting_level, bool)
                or not 0 <= nesting_level <= 8
            ):
                raise UnityError(
                    f"native projection paragraph {paragraph_index} nesting level "
                    "must be an integer from 0 to 8"
                )
            prefix = "\t" * nesting_level

        paragraph_start = cursor
        text_start = paragraph_start + _utf16_length(prefix)
        run_ranges: list[dict[str, Any]] = []
        visible_parts: list[str] = []
        run_cursor = text_start
        for run_index, run in enumerate(runs):
            if not isinstance(run, dict):
                raise UnityError(
                    f"native projection paragraph {paragraph_index} run "
                    f"{run_index} is not an object"
                )
            unknown_run = set(run) - allowed_run_keys
            if unknown_run:
                raise UnityError(
                    f"native projection paragraph {paragraph_index} run {run_index} "
                    f"has unsupported fields: {sorted(unknown_run)}"
                )
            value = run.get("text")
            if not isinstance(value, str):
                raise UnityError(
                    f"native projection paragraph {paragraph_index} run {run_index} "
                    "text must be a string"
                )
            if "\n" in value or "\r" in value:
                raise UnityError(
                    f"native projection paragraph {paragraph_index} run {run_index} "
                    "contains a paragraph break"
                )
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ue000-\uf8ff]", value):
                raise UnityError(
                    f"native projection paragraph {paragraph_index} run {run_index} "
                    "contains a character Google Docs can strip"
                )
            visible_parts.append(value)
            run_end = run_cursor + _utf16_length(value)
            run_ranges.append({
                "start": run_cursor,
                "end": run_end,
                "run": run,
            })
            run_cursor = run_end

        visible_text = "".join(visible_parts)
        insertion_parts.append(prefix + visible_text)
        paragraph_end = run_cursor + 1
        paragraph_ranges.append({
            "start": paragraph_start,
            "end": paragraph_end,
            "named_style": named_style,
            "list_kind": list_kind,
            "runs": run_ranges,
        })
        cursor = paragraph_end

    inserted_text = "\n".join(insertion_parts)
    requests: list[dict[str, Any]] = []
    if current_end_index > 2:
        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": 1,
                    "endIndex": current_end_index - 1,
                    "tabId": tab_id,
                }
            }
        })
    inserted_units = _utf16_length(inserted_text)
    if inserted_text:
        requests.append({
            "insertText": {
                "location": {"index": 1, "tabId": tab_id},
                "text": inserted_text,
            }
        })
    body_range = {
        "startIndex": 1,
        "endIndex": 2 + inserted_units,
        "tabId": tab_id,
    }
    requests.extend([
        {"deleteParagraphBullets": {"range": dict(body_range)}},
        {
            "updateParagraphStyle": {
                "range": dict(body_range),
                "paragraphStyle": {},
                # namedStyleType cannot be cleared; every paragraph receives
                # an explicit named style below.  These inherited/local fields
                # are the residue that must be reset first.
                "fields": GOOGLE_PARAGRAPH_RESET_FIELDS,
            }
        },
        {
            "updateTextStyle": {
                "range": dict(body_range),
                "textStyle": {},
                "fields": "*",
            }
        },
    ])

    for paragraph in paragraph_ranges:
        requests.append({
            "updateParagraphStyle": {
                "range": {
                    "startIndex": paragraph["start"],
                    "endIndex": paragraph["end"],
                    "tabId": tab_id,
                },
                "paragraphStyle": {
                    "namedStyleType": paragraph["named_style"],
                },
                "fields": "namedStyleType",
            }
        })
        for run_data in paragraph["runs"]:
            run = run_data["run"]
            style_start = run_data["start"]
            style_end = run_data["end"]
            if style_start == style_end:
                if len(paragraph["runs"]) != 1:
                    continue
                style_start = paragraph["end"] - 1
                style_end = paragraph["end"]
            text_style: dict[str, Any] = {}
            fields: list[str] = []
            for key in ("bold", "italic", "underline", "strikethrough"):
                if run.get(key) is True:
                    text_style[key] = True
                    fields.append(key)
            link = run.get("link")
            if link is not None:
                if run.get("underline") is True:
                    raise UnityError(
                        "native projection cannot distinguish explicit underline "
                        "from Google Docs link decoration"
                    )
                if not isinstance(link, str) or not re.fullmatch(r"https?://\S+", link):
                    raise UnityError(
                        "native projection hyperlink must be an absolute HTTP(S) URL"
                    )
                text_style["link"] = {"url": link}
                fields.append("link")
            family = run.get("font_family")
            if family is None and run.get("code") is True:
                family = "Roboto Mono"
            if family is not None:
                if family != "Roboto Mono":
                    raise UnityError(
                        "native projection supports only the reviewed Roboto Mono "
                        "code family"
                    )
                if run.get("code") is not True:
                    raise UnityError(
                        "native projection Roboto Mono runs must carry code: true"
                    )
                text_style["weightedFontFamily"] = {"fontFamily": family}
                fields.append("weightedFontFamily")
            if fields:
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": style_start,
                            "endIndex": style_end,
                            "tabId": tab_id,
                        },
                        "textStyle": text_style,
                        "fields": ",".join(fields),
                    }
                })

    list_groups: list[dict[str, Any]] = []
    for paragraph in paragraph_ranges:
        kind = paragraph["list_kind"]
        if kind is None:
            continue
        if list_groups and (
            list_groups[-1]["kind"] == kind
            and list_groups[-1]["end"] == paragraph["start"]
        ):
            list_groups[-1]["end"] = paragraph["end"]
        else:
            list_groups.append({
                "kind": kind,
                "start": paragraph["start"],
                "end": paragraph["end"],
            })
    for group in reversed(list_groups):
        requests.append({
            "createParagraphBullets": {
                "range": {
                    "startIndex": group["start"],
                    "endIndex": group["end"],
                    "tabId": tab_id,
                },
                "bulletPreset": GOOGLE_LIST_PRESETS[group["kind"]],
            }
        })
    return requests


def _link_phrase_once(
    projection: dict[str, Any], phrase: str, url: str, *,
    context: str, exact_paragraph: str | None = None,
) -> None:
    matches: list[tuple[int, int]] = []
    paragraphs = projection.get("paragraphs", [])
    for index, paragraph in enumerate(paragraphs):
        value = _paragraph_text_value(paragraph)
        if exact_paragraph is not None and value != exact_paragraph:
            continue
        start = 0
        while True:
            found = value.find(phrase, start)
            if found < 0:
                break
            matches.append((index, found))
            start = found + len(phrase)
    if len(matches) != 1:
        raise UnityError(
            f"{context}: link phrase {phrase!r} must occur exactly once; "
            f"found {len(matches)}"
        )
    paragraph_index, phrase_start = matches[0]
    phrase_end = phrase_start + len(phrase)
    paragraph = paragraphs[paragraph_index]
    rebuilt: list[dict[str, Any]] = []
    cursor = 0
    for run in paragraph.get("runs", []):
        run_text = str(run.get("text", ""))
        run_start, run_end = cursor, cursor + len(run_text)
        cursor = run_end
        cuts = sorted({
            run_start,
            run_end,
            max(run_start, min(run_end, phrase_start)),
            max(run_start, min(run_end, phrase_end)),
        })
        for left, right in zip(cuts, cuts[1:]):
            if right <= left:
                continue
            piece = dict(run)
            piece["text"] = run_text[left - run_start:right - run_start]
            if left >= phrase_start and right <= phrase_end:
                if piece.get("link") not in (None, url):
                    raise UnityError(f"{context}: reviewed link overlaps another link")
                piece["link"] = url
            rebuilt.append(piece)
    paragraph["runs"] = _merge_runs(rebuilt)


def _envelope_projection(
    config: "UnityConfig", target: "TargetConfig", edition: str,
    source_sha256: str, unity_set_digest: str,
) -> list[dict[str, Any]]:
    lines = _envelope(config, target, edition, source_sha256, unity_set_digest)
    return [
        _paragraph(lines[0], named_style="TITLE"),
        *[_paragraph(line) for line in lines[1:]],
    ]


def _combine_projection(
    envelope: list[dict[str, Any]], body: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema": NATIVE_PROJECTION_SCHEMA,
        "paragraphs": [
            *envelope,
            _paragraph(""),
            _paragraph("GENERATED AUTHORITY", named_style="HEADING_1"),
            _paragraph(""),
            *body["paragraphs"],
        ],
    }


@dataclass(frozen=True)
class NativeSourceProjection:
    algorithm: str
    strip_leading_paragraphs: int


@dataclass(frozen=True)
class TargetConfig:
    role: str
    document_id: str
    title: str
    parent_path: str
    source: str
    expected_source_sha256: str
    native_source_projection: NativeSourceProjection | None = None


@dataclass(frozen=True)
class UnityConfig:
    schema_version: int
    family: str
    header: str
    status: str
    expected_edition: str
    projection_normalization: str
    boot_projection_sha256: str
    edition_file: str
    root_id: str
    root_title: str
    portable_hierarchy: tuple[str, ...]
    required_roles: tuple[str, ...]
    publish_order: tuple[str, ...]
    targets: tuple[TargetConfig, ...]

    @property
    def by_role(self) -> dict[str, TargetConfig]:
        return {target.role: target for target in self.targets}


@dataclass(frozen=True)
class FileMeta:
    file_id: str
    name: str
    mime_type: str
    parents: tuple[str, ...]
    drive_id: str | None
    trashed: bool = False


@dataclass(frozen=True)
class DocumentData:
    text: str
    revision_id: str
    paragraphs: tuple[str, ...] = ()
    native_projection: dict[str, Any] | None = None


@dataclass(frozen=True)
class DocumentIdentity:
    role: str
    edition: str
    status: str
    unity_set_digest: str | None
    source: str | None
    source_sha256: str | None


@dataclass(frozen=True)
class DesiredDocument:
    target: TargetConfig
    edition: str
    source_text: str
    source_sha256: str
    source_projection_sha256: str | None
    transport_text: str
    transport_sha256: str
    transport_changes: tuple[TransportChange, ...]
    text: str
    text_sha256: str
    paragraph_projection_sha256: str
    native_projection: dict[str, Any]
    native_projection_sha256: str
    format_link_sha256: str


@dataclass(frozen=True)
class ObservedTarget:
    target: TargetConfig
    meta: FileMeta
    document: DocumentData
    identity: DocumentIdentity
    text_sha256: str
    paragraph_projection_sha256: str
    native_projection_sha256: str | None
    format_link_sha256: str | None
    source_projection_sha256: str | None
    source_equivalent: bool
    parent_id: str


@dataclass(frozen=True)
class Inspection:
    drive_id: str
    targets: tuple[ObservedTarget, ...]

    @property
    def by_role(self) -> dict[str, ObservedTarget]:
        return {observed.target.role: observed for observed in self.targets}


@dataclass(frozen=True)
class Plan:
    payload: dict[str, Any]
    digest: str
    inspection: Inspection | None


class Backend(Protocol):
    def get_file(self, file_id: str) -> FileMeta | None: ...

    def list_children(
        self, parent_id: str, *, name: str | None = None,
        mime_type: str | None = None
    ) -> list[FileMeta]: ...

    def list_exact_name(self, drive_id: str, name: str) -> list[FileMeta]: ...

    def read_document(self, document_id: str) -> DocumentData: ...

    def replace_document(
        self, document_id: str, text: str, *, expected_revision_id: str,
        native_projection: dict[str, Any]
    ) -> DocumentData: ...


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UnityError(f"config field {key!r} must be a non-empty string")
    return value.strip()


def _validate_parent_path(value: str) -> str:
    value = value.replace("\\", "/")
    if value == ".":
        return value
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in ("", ".", "..") for part in pure.parts):
        raise UnityError(f"unsafe parent_path: {value!r}")
    return str(pure)


def load_config(path: Path) -> UnityConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnityError(f"cannot read config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise UnityError("config root must be an object")
    if raw.get("schema_version") != 1:
        raise UnityError("unsupported config schema_version (expected 1)")

    root = raw.get("root_folder")
    if not isinstance(root, dict):
        raise UnityError("root_folder must be an object")
    status = _require_string(raw, "status").lower()
    if status not in {"candidate", "current"}:
        raise UnityError("status must be candidate or current")

    expected_edition = _require_string(raw, "expected_edition")
    if not EDITION_RE.fullmatch(expected_edition):
        raise UnityError("expected_edition is malformed")
    projection_normalization = _require_string(raw, "projection_normalization")
    if projection_normalization != PROJECTION_NORMALIZATION:
        raise UnityError(
            f"projection_normalization must be {PROJECTION_NORMALIZATION!r}"
        )
    boot_projection_sha256 = _require_string(
        raw, "boot_projection_sha256"
    ).lower()
    if not SHA256_RE.fullmatch(boot_projection_sha256):
        raise UnityError("boot_projection_sha256 is malformed")

    hierarchy_raw = raw.get("portable_hierarchy")
    if not isinstance(hierarchy_raw, list) or not all(
        isinstance(item, str) for item in hierarchy_raw
    ):
        raise UnityError("portable_hierarchy must be a string list")
    hierarchy = tuple(_validate_parent_path(item) for item in hierarchy_raw)
    if not hierarchy or hierarchy[0] != "." or len(set(hierarchy)) != len(hierarchy):
        raise UnityError(
            "portable_hierarchy must begin with root '.' and contain unique paths"
        )
    hierarchy_set = set(hierarchy)
    for relative in hierarchy[1:]:
        parent = str(PurePosixPath(relative).parent)
        if parent == ".":
            parent = "."
        if parent not in hierarchy_set:
            raise UnityError(
                f"portable_hierarchy omits parent {parent!r} for {relative!r}"
            )

    required_raw = raw.get("required_roles")
    order_raw = raw.get("publish_order")
    target_raw = raw.get("targets")
    if not isinstance(required_raw, list) or not all(isinstance(x, str) for x in required_raw):
        raise UnityError("required_roles must be a string list")
    if not isinstance(order_raw, list) or not all(isinstance(x, str) for x in order_raw):
        raise UnityError("publish_order must be a string list")
    if not isinstance(target_raw, list):
        raise UnityError("targets must be a list")

    required = tuple(x.lower() for x in required_raw)
    order = tuple(x.lower() for x in order_raw)
    if set(required) != REQUIRED_ROLES or len(required) != len(REQUIRED_ROLES):
        raise UnityError("required_roles must contain the seven Unity roles exactly once")
    if set(order) != REQUIRED_ROLES or len(order) != len(REQUIRED_ROLES):
        raise UnityError("publish_order must contain the seven Unity roles exactly once")
    if order[-1] != "boot":
        raise UnityError("publish_order must put boot last")

    targets: list[TargetConfig] = []
    for index, item in enumerate(target_raw):
        if not isinstance(item, dict):
            raise UnityError(f"targets[{index}] must be an object")
        role = _require_string(item, "role").lower()
        source_sha256 = _require_string(item, "source_sha256").lower()
        if not SHA256_RE.fullmatch(source_sha256):
            raise UnityError(f"targets[{index}] source_sha256 is malformed")
        native_projection_raw = item.get("native_source_projection")
        native_projection: NativeSourceProjection | None = None
        if native_projection_raw is not None:
            if not isinstance(native_projection_raw, dict):
                raise UnityError(
                    f"targets[{index}] native_source_projection must be an object"
                )
            algorithm = _require_string(native_projection_raw, "algorithm")
            if algorithm not in {
                NONBLANK_SOURCE_PROJECTION,
                CODEBLOCK_SOURCE_PROJECTION,
            }:
                raise UnityError(
                    f"targets[{index}] unsupported native projection {algorithm!r}"
                )
            strip_count = native_projection_raw.get("strip_leading_paragraphs")
            if not isinstance(strip_count, int) or isinstance(strip_count, bool):
                raise UnityError(
                    f"targets[{index}] strip_leading_paragraphs must be an integer"
                )
            if strip_count < 0 or strip_count > 32:
                raise UnityError(
                    f"targets[{index}] strip_leading_paragraphs is outside 0..32"
                )
            native_projection = NativeSourceProjection(algorithm, strip_count)
        parent_path = _validate_parent_path(_require_string(item, "parent_path"))
        if parent_path not in hierarchy_set:
            raise UnityError(
                f"targets[{index}] parent_path is absent from portable_hierarchy"
            )
        targets.append(TargetConfig(
            role=role,
            document_id=_require_string(item, "document_id"),
            title=_require_string(item, "title"),
            parent_path=parent_path,
            source=_validate_parent_path(_require_string(item, "source")),
            expected_source_sha256=source_sha256,
            native_source_projection=native_projection,
        ))

    roles = [target.role for target in targets]
    ids = [target.document_id for target in targets]
    titles = [target.title for target in targets]
    if set(roles) != REQUIRED_ROLES or len(roles) != len(REQUIRED_ROLES):
        raise UnityError("targets must define the seven Unity roles exactly once")
    if len(set(ids)) != len(ids):
        raise UnityError("configured document IDs are not unique")
    if len(set(titles)) != len(titles):
        raise UnityError("configured titles are not unique")

    return UnityConfig(
        schema_version=1,
        family=_require_string(raw, "family"),
        header=_require_string(raw, "header"),
        status=status,
        expected_edition=expected_edition,
        projection_normalization=projection_normalization,
        boot_projection_sha256=boot_projection_sha256,
        edition_file=_validate_parent_path(_require_string(raw, "edition_file")),
        root_id=_require_string(root, "id"),
        root_title=_require_string(root, "title"),
        portable_hierarchy=hierarchy,
        required_roles=required,
        publish_order=order,
        targets=tuple(targets),
    )


def _source_path(source_root: Path, relative: str) -> Path:
    source_root = source_root.resolve()
    path = (source_root / Path(relative)).resolve()
    try:
        path.relative_to(source_root)
    except ValueError as exc:
        raise UnityError(f"source escapes source root: {relative}") from exc
    if not path.is_file():
        raise UnityError(f"missing generated source: {relative}")
    return path


def _read_source(source_root: Path, relative: str) -> str:
    path = _source_path(source_root, relative)
    try:
        return canonical_text(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise UnityError(f"cannot read generated source {relative}: {exc}") from exc


def _source_sha256(source_root: Path, relative: str) -> str:
    path = _source_path(source_root, relative)
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise UnityError(f"cannot hash generated source {relative}: {exc}") from exc


def _assert_source_witness(target: TargetConfig, text: str, edition: str) -> None:
    first_kb = text[:1024]
    markers = (f"<!-- {edition} -->", f"# {edition}")
    if not any(marker in first_kb for marker in markers):
        raise UnityError(
            f"{target.source} does not carry edition {edition} near its start"
        )
    if target.role in {"boot", "edit", "check", "photo", "pr"}:
        match = re.search(
            r"^---\n.*?^name:\s*[\"']?([^\"'\n]+)", text, re.M | re.S
        )
        if not match or match.group(1).strip().lower() != target.role:
            raise UnityError(
                f"{target.source} front-matter role does not match {target.role}"
            )


def _envelope(
    config: UnityConfig, target: TargetConfig, edition: str, source_sha256: str,
    unity_set_digest: str
) -> list[str]:
    return [
        config.header,
        f"ROLE: {target.role.upper()}",
        f"SOURCE EDITION: {edition}",
        f"STATUS: {config.status.upper()}",
        f"UNITY SET: {unity_set_digest}",
        f"SOURCE: {target.source}",
        f"SOURCE-SHA256: {source_sha256}",
    ]


def _render_standard(
    config: UnityConfig, target: TargetConfig, edition: str,
    source_text: str, source_sha256: str, unity_set_digest: str
) -> str:
    lines = _envelope(
        config, target, edition, source_sha256, unity_set_digest
    )
    lines.extend([
        "",
        "--- GENERATED AUTHORITY ---",
        "",
        source_text.rstrip("\n"),
        "",
    ])
    return canonical_text("\n".join(lines))


def _render_boot(
    config: UnityConfig, target: TargetConfig, edition: str,
    _source_text: str, source_sha256: str,
    source_hashes: dict[str, str], unity_set_digest: str
) -> str:
    boot_parent = posixpath.dirname(target.source)
    lines = _envelope(
        config, target, edition, source_sha256, unity_set_digest
    )
    lines.extend([
        "",
        "# BKP 3.0 Unity ignition",
        "",
        "This manifest is the ignition document. Resolve each named route through",
        "the active environment: protected permanent references in Drive, or the",
        "relative hierarchy in a local, GitHub or website package. Permanent Drive",
        "IDs stay in protected updater configuration rather than visible content.",
        "Accept a role only when its title, route, source edition and source hash",
        "match this map. Re-read Boot after loading it and refuse the job if Boot",
        "or any mapped witness changed.",
        "",
        "## Unity document map",
        "",
        f"UNITY SET: {unity_set_digest}",
        "",
    ])
    for role in config.publish_order:
        mapped = config.by_role[role]
        portable_route = posixpath.relpath(mapped.source, boot_parent)
        lines.extend([
            f"ROLE: {role}",
            f"TITLE: {mapped.title}",
            f"ROUTE: {portable_route}",
            f"SOURCE: {mapped.source}",
            f"SOURCE-SHA256: {source_hashes[role]}",
            "",
        ])
    lines.extend([
        "## Consistency rule",
        "",
        "Read Boot, load only the role documents needed for the job, validate",
        "their witnesses against this map, then re-read Boot. Zero matches,",
        "multiple exact-title matches, a changed Boot or any witness mismatch is",
        "a stop condition. Do not guess or combine editions.",
        "",
    ])
    return canonical_text("\n".join(lines))


def _validate_registry_receipts(
    source_root: Path, edition: str, source_hashes: dict[str, str],
    config: UnityConfig
) -> None:
    """Prove that the selected generated sources belong to one fresh build."""
    receipt_path = _source_path(source_root, "build-receipt.json")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnityError(f"cannot read build-receipt.json: {exc}") from exc
    if not isinstance(receipt, dict) or receipt.get("version") != edition:
        raise UnityError("build-receipt.json version does not match VERSION.txt")
    compatibility = receipt.get("compatibility_files")
    if not isinstance(compatibility, dict):
        raise UnityError("build-receipt.json lacks compatibility_files")
    for role in ("blueprint", "directory"):
        source_name = config.by_role[role].source
        if compatibility.get(source_name) != source_hashes[role]:
            raise UnityError(
                f"build receipt hash mismatch for generated {source_name}"
            )

    index_text = _read_source(source_root, "DEPLOY/routed/INDEX.yaml")
    if not index_text.startswith(f"# {edition}\n"):
        raise UnityError("routed INDEX.yaml edition does not match VERSION.txt")
    entries = dict(re.findall(
        r"(?m)^  - path: ([^\n]+)\n    bytes: \d+\n    sha256: ([0-9a-f]{64})$",
        index_text,
    ))
    for role in ("boot", "edit", "check", "photo", "pr"):
        source_name = config.by_role[role].source
        prefix = "DEPLOY/routed/"
        if not source_name.startswith(prefix):
            raise UnityError(f"{role} source is outside routed deployment")
        routed_name = source_name[len(prefix):]
        if entries.get(routed_name) != source_hashes[role]:
            raise UnityError(
                f"routed INDEX.yaml hash mismatch for generated {source_name}"
            )


def _unity_set_digest(
    config: UnityConfig, edition: str, source_hashes: dict[str, str]
) -> str:
    """Bind all seven protected identities, routes and sources as one set."""
    return stable_digest({
        "schema": "bkp3-unity-set-v1",
        "family": config.family,
        "status": config.status,
        "edition": edition,
        "portable_hierarchy": list(config.portable_hierarchy),
        "publish_order": list(config.publish_order),
        "documents": [
            {
                "role": role,
                "id": config.by_role[role].document_id,
                "title": config.by_role[role].title,
                "parent_path": config.by_role[role].parent_path,
                "source": config.by_role[role].source,
                "source_sha256": source_hashes[role],
            }
            for role in config.publish_order
        ],
    })


def load_desired(
    config: UnityConfig, source_root: Path
) -> tuple[str, str, dict[str, DesiredDocument]]:
    edition = _read_source(source_root, config.edition_file).strip()
    if not edition or not EDITION_RE.fullmatch(edition):
        raise UnityError(f"invalid edition witness in {config.edition_file}: {edition!r}")
    if edition != config.expected_edition:
        raise UnityError(
            f"source edition {edition!r} does not match locked expected edition "
            f"{config.expected_edition!r}"
        )

    raw: dict[str, tuple[str, str]] = {}
    for target in config.targets:
        text = _read_source(source_root, target.source)
        _assert_source_witness(target, text, edition)
        source_sha = _source_sha256(source_root, target.source)
        if source_sha != target.expected_source_sha256:
            raise UnityError(
                f"configured source hash mismatch for {target.source}: expected "
                f"{target.expected_source_sha256}, found {source_sha}"
            )
        raw[target.role] = (text, source_sha)

    source_hashes = {role: digest for role, (_text, digest) in raw.items()}
    _validate_registry_receipts(source_root, edition, source_hashes, config)
    unity_set_digest = _unity_set_digest(config, edition, source_hashes)
    desired: dict[str, DesiredDocument] = {}
    for role in config.publish_order:
        target = config.by_role[role]
        source_text, source_sha = raw[role]
        transported, transport_changes = transport_source(role, source_text)
        if role == "boot":
            rendered = _render_boot(
                config, target, edition, source_text, source_sha, source_hashes,
                unity_set_digest
            )
            rendered_lines = rendered.rstrip("\n").split("\n")
            envelope_lines = _envelope(
                config, target, edition, source_sha, unity_set_digest
            )
            if (
                rendered_lines[:len(envelope_lines)] != envelope_lines
                or rendered_lines[len(envelope_lines)] != ""
            ):
                raise UnityError("Boot renderer did not preserve the guarded envelope")
            body_projection = markdown_native_projection(
                "\n".join(rendered_lines[len(envelope_lines) + 1:]) + "\n"
            )
            native_projection = _combine_projection(
                _envelope_projection(
                    config, target, edition, source_sha, unity_set_digest
                ),
                body_projection,
            )
            for mapped_role in config.publish_order:
                mapped = config.by_role[mapped_role]
                _link_phrase_once(
                    native_projection,
                    mapped.title,
                    GOOGLE_DOC_URL.format(document_id=mapped.document_id),
                    context=f"boot.{mapped_role}_link",
                    exact_paragraph=f"TITLE: {mapped.title}",
                )
        else:
            body_projection = (
                literal_native_projection(transported)
                if role == "directory"
                else markdown_native_projection(transported)
            )
            native_projection = _combine_projection(
                _envelope_projection(
                    config, target, edition, source_sha, unity_set_digest
                ),
                body_projection,
            )
            if role == "blueprint":
                boot = config.by_role["boot"]
                _link_phrase_once(
                    native_projection,
                    "Boot document",
                    GOOGLE_DOC_URL.format(document_id=boot.document_id),
                    context="blueprint.boot_document_link",
                )
            rendered = _render_standard(
                config, target, edition, transported, source_sha,
                unity_set_digest
            )
        source_projection_sha: str | None = None
        if target.native_source_projection is not None:
            source_lines = transported.rstrip("\n").split("\n")
            if (
                target.native_source_projection.algorithm
                == CODEBLOCK_SOURCE_PROJECTION
            ):
                source_projection_sha = codeblock_projection_sha256(
                    source_lines,
                    require_sentinels=False,
                    markdown_source=True,
                )
            else:
                source_projection_sha = nonblank_projection_sha256(source_lines)
        del rendered
        visible_text = _projection_text(native_projection)
        visible_sha = sha256_text(visible_text)
        paragraph_sha = paragraph_projection_sha256(
            _paragraph_text_value(paragraph)
            for paragraph in native_projection["paragraphs"]
        )
        native_projection_sha = stable_digest(native_projection)
        format_link_sha = stable_digest(
            _projection_format_link_payload(native_projection)
        )
        for protected_id in (item.document_id for item in config.targets):
            if protected_id in visible_text:
                raise UnityError(
                    f"{role}: visible text exposes a protected permanent document ID"
                )
        if (
            role == "boot"
            and native_projection_sha != config.boot_projection_sha256
        ):
            raise UnityError(
                "Boot projection hash differs from the reviewed template lock: "
                f"expected {config.boot_projection_sha256}, "
                f"found {native_projection_sha}"
            )
        desired[role] = DesiredDocument(
            target=target,
            edition=edition,
            source_text=source_text,
            source_sha256=source_sha,
            source_projection_sha256=source_projection_sha,
            transport_text=transported,
            transport_sha256=sha256_text(transported),
            transport_changes=transport_changes,
            text=visible_text,
            text_sha256=visible_sha,
            paragraph_projection_sha256=paragraph_sha,
            native_projection=native_projection,
            native_projection_sha256=native_projection_sha,
            format_link_sha256=format_link_sha,
        )
    return edition, unity_set_digest, desired


def parse_identity(text: str, expected_header: str) -> DocumentIdentity:
    lines = canonical_text(text).splitlines()
    if not lines or lines[0] != expected_header:
        raise UnityError(
            f"document identity must begin with exact header {expected_header!r}"
        )
    recognised = {
        "ROLE", "SOURCE EDITION", "STATUS", "UNITY SET", "SOURCE",
        "SOURCE-SHA256"
    }
    fields: dict[str, str] = {}
    for line in lines[1:33]:
        if line == "":
            break
        match = re.fullmatch(r"([A-Z][A-Z -]*):\s*(\S.*?)\s*", line)
        if match is None or match.group(1) not in recognised:
            break
        label, field_value = match.group(1), match.group(2).strip()
        if label in fields:
            raise UnityError(f"document identity repeats {label}")
        fields[label] = field_value

    def value(label: str, required: bool = True) -> str | None:
        field_value = fields.get(label)
        if field_value is None and required:
            raise UnityError(f"document identity lacks {label}")
        return field_value

    edition = value("SOURCE EDITION")
    assert edition is not None

    source_sha = value("SOURCE-SHA256", required=False)
    if source_sha is not None:
        source_sha = source_sha.lower()
        if not SHA256_RE.fullmatch(source_sha):
            raise UnityError("document SOURCE-SHA256 is malformed")
    unity_set_digest = value("UNITY SET", required=False)
    if unity_set_digest is not None:
        unity_set_digest = unity_set_digest.lower()
        if not SHA256_RE.fullmatch(unity_set_digest):
            raise UnityError("document UNITY SET is malformed")
    return DocumentIdentity(
        role=(value("ROLE") or "").lower(),
        edition=edition,
        status=(value("STATUS") or "").lower(),
        unity_set_digest=unity_set_digest,
        source=value("SOURCE", required=False),
        source_sha256=source_sha,
    )


class UnityUpdater:
    def __init__(
        self, config: UnityConfig, source_root: Path, backend: Backend | None
    ) -> None:
        self.config = config
        self.source_root = source_root
        self.backend = backend
        self.edition, self.unity_set_digest, self.desired = load_desired(
            config, source_root
        )

    def source_plan(self) -> Plan:
        payload = {
            "schema_version": 1,
            "plan_kind": "sources-only",
            "family": self.config.family,
            "status": self.config.status,
            "edition": self.edition,
            "unity_set_digest": self.unity_set_digest,
            "projection_normalization": self.config.projection_normalization,
            "native_projection_schema": NATIVE_PROJECTION_SCHEMA,
            "google_apply": {
                "enabled": False,
                "reason": (
                    "formatting-preserving compiler proved only on an isolated "
                    "disposable Doc; protected backend transport and full-size "
                    "proofs remain unapproved"
                ),
            },
            "root": {
                "id": self.config.root_id,
                "title": self.config.root_title,
            },
            "portable_hierarchy": list(self.config.portable_hierarchy),
            "publish_order": list(self.config.publish_order),
            "documents": [
                {
                    "role": role,
                    "id": self.desired[role].target.document_id,
                    "title": self.desired[role].target.title,
                    "parent_path": self.desired[role].target.parent_path,
                    "source": self.desired[role].target.source,
                    "source_sha256": self.desired[role].source_sha256,
                    "source_projection_sha256": (
                        self.desired[role].source_projection_sha256
                    ),
                    "transport_sha256": self.desired[role].transport_sha256,
                    "transport_changes": [
                        {
                            "name": change.name,
                            "matches": 1,
                            "before_sha256": change.before_sha256,
                            "after_sha256": change.after_sha256,
                        }
                        for change in self.desired[role].transport_changes
                    ],
                    "desired_text_sha256": self.desired[role].text_sha256,
                    "desired_paragraph_projection_sha256": (
                        self.desired[role].paragraph_projection_sha256
                    ),
                    "desired_native_projection_sha256": (
                        self.desired[role].native_projection_sha256
                    ),
                    "desired_format_link_sha256": (
                        self.desired[role].format_link_sha256
                    ),
                    "desired_native_projection": (
                        self.desired[role].native_projection
                    ),
                }
                for role in self.config.publish_order
            ],
        }
        return Plan(payload=payload, digest=stable_digest(payload), inspection=None)

    @staticmethod
    def _paragraphs(document: DocumentData) -> tuple[str, ...]:
        if document.paragraphs:
            return document.paragraphs
        return tuple(canonical_text(document.text).rstrip("\n").split("\n"))

    def _source_projection(
        self, target: TargetConfig, document: DocumentData
    ) -> str | None:
        projection = target.native_source_projection
        if projection is None:
            return None
        paragraphs = self._paragraphs(document)
        if len(paragraphs) < projection.strip_leading_paragraphs:
            raise UnityError(
                f"{target.role}: document is shorter than its configured native envelope"
            )
        body = paragraphs[projection.strip_leading_paragraphs:]
        if projection.algorithm == NONBLANK_SOURCE_PROJECTION:
            return nonblank_projection_sha256(body)
        if projection.algorithm == CODEBLOCK_SOURCE_PROJECTION:
            return codeblock_projection_sha256(body, require_sentinels=True)
        raise UnityError(
            f"{target.role}: unsupported native projection {projection.algorithm!r}"
        )

    def _is_desired(self, role: str, observed: ObservedTarget) -> bool:
        desired = self.desired[role]
        return (
            observed.text_sha256 == desired.text_sha256
            and observed.native_projection_sha256
            == desired.native_projection_sha256
            and observed.format_link_sha256 == desired.format_link_sha256
        )

    def _root(self) -> FileMeta:
        if self.backend is None:
            raise UnityError("a target backend is required for a full plan")
        root = self.backend.get_file(self.config.root_id)
        if root is None or root.trashed:
            raise UnityError("configured Unity root folder is missing or trashed")
        if root.name != self.config.root_title:
            raise UnityError(
                f"root title mismatch: expected {self.config.root_title!r}, got {root.name!r}"
            )
        if root.mime_type != GOOGLE_FOLDER_MIME:
            raise UnityError("configured Unity root is not a Google Drive folder")
        if not root.drive_id:
            raise UnityError("configured Unity root is not in a Shared Drive")
        return root

    def _resolve_parent(
        self, root: FileMeta, relative: str, cache: dict[str, FileMeta]
    ) -> FileMeta:
        if relative == ".":
            return root
        current = root
        walked: list[str] = []
        for part in PurePosixPath(relative).parts:
            walked.append(part)
            key = "/".join(walked)
            if key in cache:
                current = cache[key]
                continue
            matches = self.backend.list_children(  # type: ignore[union-attr]
                current.file_id, name=part, mime_type=GOOGLE_FOLDER_MIME
            )
            if len(matches) != 1:
                raise UnityError(
                    f"hierarchy segment {'/'.join(walked)!r} has {len(matches)} exact folders"
                )
            child = matches[0]
            if child.trashed or child.drive_id != root.drive_id:
                raise UnityError(f"invalid hierarchy folder at {key!r}")
            cache[key] = child
            current = child
        return current

    def inspect(self) -> Inspection:
        if self.backend is None:
            raise UnityError("a target backend is required for inspection")
        root = self._root()
        cache: dict[str, FileMeta] = {".": root}
        observed: list[ObservedTarget] = []
        for role in self.config.publish_order:
            target = self.config.by_role[role]
            parent = self._resolve_parent(root, target.parent_path, cache)
            meta = self.backend.get_file(target.document_id)
            if meta is None or meta.trashed:
                raise UnityError(
                    f"{role}: configured document ID is missing or trashed; refusing a replacement"
                )
            if meta.name != target.title:
                raise UnityError(
                    f"{role}: title mismatch: expected {target.title!r}, got {meta.name!r}"
                )
            if meta.mime_type != GOOGLE_DOC_MIME:
                raise UnityError(f"{role}: configured target is not a native Google Doc")
            if meta.drive_id != root.drive_id:
                raise UnityError(f"{role}: target is outside the configured Shared Drive")
            if tuple(meta.parents) != (parent.file_id,):
                raise UnityError(
                    f"{role}: parent mismatch for {target.parent_path!r}; got {list(meta.parents)!r}"
                )
            same_name = self.backend.list_exact_name(root.drive_id, target.title)
            if len(same_name) != 1 or same_name[0].file_id != target.document_id:
                ids = [item.file_id for item in same_name]
                raise UnityError(
                    f"{role}: exact title is missing, duplicated or points elsewhere: {ids!r}"
                )
            document = self.backend.read_document(target.document_id)
            try:
                identity = parse_identity(document.text, self.config.header)
            except UnityError as exc:
                raise UnityError(f"{role}: {exc}") from exc
            if identity.role != role:
                raise UnityError(
                    f"{role}: body role mismatch: found {identity.role!r}"
                )
            if identity.status != self.config.status:
                raise UnityError(
                    f"{role}: status mismatch: expected {self.config.status!r}, found {identity.status!r}"
                )
            text_sha = sha256_text(document.text)
            source_projection_sha = (
                self.desired[role].source_projection_sha256
                if text_sha == self.desired[role].text_sha256
                else self._source_projection(target, document)
            )
            source_equivalent = (
                source_projection_sha is not None
                and source_projection_sha
                == self.desired[role].source_projection_sha256
            )
            native_projection_sha = (
                stable_digest(document.native_projection)
                if document.native_projection is not None
                else None
            )
            format_link_sha = (
                stable_digest(
                    _projection_format_link_payload(document.native_projection)
                )
                if document.native_projection is not None
                else None
            )
            observed.append(ObservedTarget(
                target=target,
                meta=meta,
                document=document,
                identity=identity,
                text_sha256=text_sha,
                paragraph_projection_sha256=paragraph_projection_sha256(
                    self._paragraphs(document)
                ),
                native_projection_sha256=native_projection_sha,
                format_link_sha256=format_link_sha,
                source_projection_sha256=source_projection_sha,
                source_equivalent=source_equivalent,
                parent_id=parent.file_id,
            ))
        inspection = Inspection(root.drive_id, tuple(observed))
        self._validate_current_set(inspection)
        return inspection

    def _validate_current_set(self, inspection: Inspection) -> None:
        current = inspection.by_role
        boot = current["boot"]
        boot_edition = boot.identity.edition
        desired_edition = self.edition

        for role in self.config.publish_order:
            item = current[role]
            desired = self.desired[role]
            if item.identity.edition == boot_edition:
                continue
            if (
                role != "boot"
                and item.identity.edition == desired_edition
                and self._is_desired(role, item)
            ):
                # Safe resumable staging: Boot still publishes the old edition,
                # while this content target is already the exact next payload.
                continue
            raise UnityError(
                f"{role}: edition {item.identity.edition!r} neither matches Boot "
                f"{boot_edition!r} nor an exact staged {desired_edition!r} payload"
            )

        all_desired = all(
            self._is_desired(role, current[role])
            for role in self.config.publish_order
        )
        content_desired = all(
            self._is_desired(role, current[role])
            for role in self.config.publish_order if role != "boot"
        )
        if boot_edition == desired_edition:
            if boot.text_sha256 == self.desired["boot"].text_sha256 and not content_desired:
                raise UnityError("Boot publishes the desired edition before all content is exact")
            if self.config.status == "current" and not all_desired:
                raise UnityError(
                    "current Unity content would change without a new edition identity"
                )

    def full_plan(self) -> Plan:
        inspection = self.inspect()
        current = inspection.by_role
        payload = {
            "schema_version": 1,
            "plan_kind": "drive",
            "family": self.config.family,
            "status": self.config.status,
            "edition": self.edition,
            "unity_set_digest": self.unity_set_digest,
            "projection_normalization": self.config.projection_normalization,
            "native_projection_schema": NATIVE_PROJECTION_SCHEMA,
            "google_apply": {
                "enabled": False,
                "reason": (
                    "formatting-preserving compiler proved only on an isolated "
                    "disposable Doc; protected backend transport and full-size "
                    "proofs remain unapproved"
                ),
            },
            "root": {
                "id": self.config.root_id,
                "title": self.config.root_title,
                "drive_id": inspection.drive_id,
            },
            "portable_hierarchy": list(self.config.portable_hierarchy),
            "publish_order": list(self.config.publish_order),
            "documents": [
                {
                    "role": role,
                    "id": self.desired[role].target.document_id,
                    "title": self.desired[role].target.title,
                    "parent_path": self.desired[role].target.parent_path,
                    "source": self.desired[role].target.source,
                    "source_sha256": self.desired[role].source_sha256,
                    "source_projection_sha256": (
                        self.desired[role].source_projection_sha256
                    ),
                    "transport_sha256": self.desired[role].transport_sha256,
                    "transport_changes": [
                        {
                            "name": change.name,
                            "matches": 1,
                            "before_sha256": change.before_sha256,
                            "after_sha256": change.after_sha256,
                        }
                        for change in self.desired[role].transport_changes
                    ],
                    "desired_text_sha256": self.desired[role].text_sha256,
                    "desired_paragraph_projection_sha256": (
                        self.desired[role].paragraph_projection_sha256
                    ),
                    "desired_native_projection_sha256": (
                        self.desired[role].native_projection_sha256
                    ),
                    "desired_format_link_sha256": (
                        self.desired[role].format_link_sha256
                    ),
                    "desired_native_projection": (
                        self.desired[role].native_projection
                    ),
                    "current_text_sha256": current[role].text_sha256,
                    "current_paragraph_projection_sha256": (
                        current[role].paragraph_projection_sha256
                    ),
                    "current_native_projection_sha256": (
                        current[role].native_projection_sha256
                    ),
                    "current_format_link_sha256": (
                        current[role].format_link_sha256
                    ),
                    "current_source_projection_sha256": (
                        current[role].source_projection_sha256
                    ),
                    "source_equivalent": current[role].source_equivalent,
                    "current_revision_id": current[role].document.revision_id,
                    "current_edition": current[role].identity.edition,
                    "current_unity_set_digest": (
                        current[role].identity.unity_set_digest
                    ),
                    "current_source": current[role].identity.source,
                    "current_source_sha256": current[role].identity.source_sha256,
                }
                for role in self.config.publish_order
            ],
        }
        return Plan(payload=payload, digest=stable_digest(payload), inspection=inspection)

    def _require_all_content_exact(self, inspection: Inspection) -> None:
        current = inspection.by_role
        wrong = [
            role for role in self.config.publish_order
            if role != "boot"
            and not self._is_desired(role, current[role])
        ]
        if wrong:
            raise UnityError(f"content verification failed before Boot: {wrong}")

    def _require_all_exact(self, inspection: Inspection) -> None:
        current = inspection.by_role
        wrong = [
            role for role in self.config.publish_order
            if not self._is_desired(role, current[role])
            or current[role].identity.edition != self.edition
            or current[role].identity.role != role
        ]
        if wrong:
            raise UnityError(f"final Unity verification failed: {wrong}")

    @staticmethod
    def _require_write_result_exact(
        role: str, result: DocumentData, desired: DesiredDocument
    ) -> None:
        if sha256_text(result.text) != desired.text_sha256:
            raise UnityError(f"{role}: immediate post-write text hash mismatch")
        if result.native_projection is None:
            raise UnityError(f"{role}: writer returned no native projection proof")
        if stable_digest(result.native_projection) != desired.native_projection_sha256:
            raise UnityError(f"{role}: immediate native projection mismatch")
        if stable_digest(
            _projection_format_link_payload(result.native_projection)
        ) != desired.format_link_sha256:
            raise UnityError(f"{role}: immediate format/link digest mismatch")

    def _restore_boot(self, original: ObservedTarget) -> str:
        if self.backend is None:
            return "no backend"
        now = self.backend.read_document(original.target.document_id)
        if original.document.native_projection is None:
            raise UnityError("Boot rollback lacks the original native projection")
        restored = self.backend.replace_document(
            original.target.document_id,
            original.document.text,
            expected_revision_id=now.revision_id,
            native_projection=original.document.native_projection,
        )
        if (
            sha256_text(restored.text) != original.text_sha256
            or restored.native_projection is None
            or stable_digest(restored.native_projection)
            != original.native_projection_sha256
        ):
            raise UnityError(
                "Boot rollback write did not reproduce its original native state"
            )
        check = self.backend.read_document(original.target.document_id)
        if (
            sha256_text(check.text) != original.text_sha256
            or check.native_projection is None
            or stable_digest(check.native_projection)
            != original.native_projection_sha256
        ):
            raise UnityError("Boot rollback verification failed")
        return check.revision_id

    def apply(self, plan: Plan, confirmation: str) -> list[str]:
        if self.backend is None or plan.inspection is None:
            raise UnityError("cannot apply a source-only plan")
        if not getattr(self.backend, "supports_safe_apply", True):
            raise UnityError(
                "this backend has no approved direct formatting-preserving "
                "transport for the proved native-request compiler; apply is "
                "disabled"
            )
        if confirmation != plan.digest:
            raise UnityError("confirmation does not match the fresh full-plan digest")

        # Re-read metadata, hierarchy, bodies and revisions immediately before
        # the first write.  A Drive move/rename need not change a Docs revision,
        # so optimistic revision locks alone are insufficient.
        fresh = self.full_plan()
        if fresh.digest != plan.digest:
            raise UnityError(
                "target or source state changed after planning; run a new dry run"
            )
        plan = fresh

        initial = plan.inspection.by_role
        original_boot = initial["boot"]
        actions: list[str] = []
        boot_written = False

        try:
            for role in self.config.publish_order:
                if role == "boot":
                    continue
                observed = initial[role]
                desired = self.desired[role]
                if self._is_desired(role, observed):
                    qualifier = (
                        "native source-equivalent"
                        if observed.text_sha256 != desired.text_sha256
                        else "exact"
                    )
                    actions.append(
                        f"current ({qualifier}): {desired.target.title}"
                    )
                    continue
                result = self.backend.replace_document(
                    desired.target.document_id,
                    desired.text,
                    expected_revision_id=observed.document.revision_id,
                    native_projection=desired.native_projection,
                )
                self._require_write_result_exact(role, result, desired)
                actions.append(f"written and verified: {desired.target.title}")

            before_boot = self.inspect()
            self._require_all_content_exact(before_boot)
            boot_now = before_boot.by_role["boot"]
            if (
                boot_now.text_sha256 != original_boot.text_sha256
                or boot_now.document.revision_id != original_boot.document.revision_id
                or boot_now.native_projection_sha256
                != original_boot.native_projection_sha256
                or boot_now.format_link_sha256
                != original_boot.format_link_sha256
            ):
                raise UnityError("Boot changed after planning; refusing commit")

            desired_boot = self.desired["boot"]
            if boot_now.text_sha256 == desired_boot.text_sha256:
                actions.append(f"current: {desired_boot.target.title}")
            else:
                result = self.backend.replace_document(
                    desired_boot.target.document_id,
                    desired_boot.text,
                    expected_revision_id=boot_now.document.revision_id,
                    native_projection=desired_boot.native_projection,
                )
                boot_written = True
                self._require_write_result_exact("boot", result, desired_boot)
                actions.append(f"written last and verified: {desired_boot.target.title}")

            final = self.inspect()
            self._require_all_exact(final)
            actions.append(f"Unity verified: {self.edition}")
            return actions
        except Exception as exc:
            if boot_written:
                try:
                    revision = self._restore_boot(original_boot)
                except Exception as rollback_exc:
                    raise UnityError(
                        f"{exc}; Boot changed and automatic rollback FAILED: {rollback_exc}"
                    ) from exc
                raise UnityError(
                    f"{exc}; Boot restored to its pre-apply text (revision {revision})"
                ) from exc
            if isinstance(exc, UnityError):
                raise
            raise UnityError(str(exc)) from exc


class JsonStateBackend:
    """Local state-file backend for full offline rehearsals and tests."""

    supports_safe_apply = True

    def __init__(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UnityError(f"cannot read state backend {path}: {exc}") from exc
        files = raw.get("files") if isinstance(raw, dict) else None
        if not isinstance(files, list):
            raise UnityError("state backend needs a files list")
        self._records: dict[str, dict[str, Any]] = {}
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise UnityError("malformed state file record")
            self._records[item["id"]] = dict(item)

    def get_file(self, file_id: str) -> FileMeta | None:
        item = self._records.get(file_id)
        if item is None:
            return None
        return FileMeta(
            file_id=file_id,
            name=str(item.get("name", "")),
            mime_type=str(item.get("mime_type", "")),
            parents=tuple(item.get("parents", [])),
            drive_id=item.get("drive_id"),
            trashed=bool(item.get("trashed", False)),
        )

    def list_children(
        self, parent_id: str, *, name: str | None = None,
        mime_type: str | None = None
    ) -> list[FileMeta]:
        result: list[FileMeta] = []
        for file_id in self._records:
            meta = self.get_file(file_id)
            assert meta is not None
            if parent_id not in meta.parents or meta.trashed:
                continue
            if name is not None and meta.name != name:
                continue
            if mime_type is not None and meta.mime_type != mime_type:
                continue
            result.append(meta)
        return result

    def list_exact_name(self, drive_id: str, name: str) -> list[FileMeta]:
        result: list[FileMeta] = []
        for file_id in self._records:
            meta = self.get_file(file_id)
            assert meta is not None
            if not meta.trashed and meta.drive_id == drive_id and meta.name == name:
                result.append(meta)
        return result

    def read_document(self, document_id: str) -> DocumentData:
        item = self._records.get(document_id)
        if item is None or item.get("mime_type") != GOOGLE_DOC_MIME:
            raise UnityError(f"state document unavailable: {document_id}")
        text = canonical_text(str(item.get("text", "")))
        projection = item.get("native_projection")
        if projection is None:
            projection = {
                "schema": NATIVE_PROJECTION_SCHEMA,
                "paragraphs": [
                    _paragraph(line)
                    for line in text.rstrip("\n").split("\n")
                ],
            }
        if not isinstance(projection, dict):
            raise UnityError(f"state native projection is malformed: {document_id}")
        return DocumentData(
            text=text,
            revision_id=str(item.get("revision_id", "r1")),
            paragraphs=tuple(text.rstrip("\n").split("\n")),
            native_projection=projection,
        )

    def replace_document(
        self, document_id: str, text: str, *, expected_revision_id: str,
        native_projection: dict[str, Any]
    ) -> DocumentData:
        current = self.read_document(document_id)
        if current.revision_id != expected_revision_id:
            raise UnityError(
                f"revision changed for {document_id}: expected {expected_revision_id}, "
                f"found {current.revision_id}"
            )
        item = self._records[document_id]
        if _projection_text(native_projection) != canonical_text(text):
            raise UnityError(
                f"state write text/projection mismatch for {document_id}"
            )
        match = re.fullmatch(r"r(\d+)", current.revision_id)
        revision = f"r{int(match.group(1)) + 1}" if match else "r-" + sha256_text(text)[:12]
        item["text"] = canonical_text(text)
        item["native_projection"] = json.loads(json.dumps(native_projection))
        item["revision_id"] = revision
        return self.read_document(document_id)

    def save(self, path: Path) -> None:
        payload = {"files": list(self._records.values())}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def _drive_query_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleBackend:
    """Thin Google Drive/Docs API backend; imported only when explicitly used."""

    # Reads and dry-run snapshots are supported.  The provisional body writer
    # below remains testable code, but apply must not reach it until it is
    # replaced by an approved native-format renderer.
    supports_safe_apply = False

    SCOPES = (
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    )

    def __init__(self, credentials_path: Path) -> None:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise UnityError(
                "Google backend dependencies are absent; install requirements-google.txt"
            ) from exc
        try:
            credentials = Credentials.from_authorized_user_file(
                str(credentials_path), scopes=list(self.SCOPES)
            )
            self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
            self.docs = build("docs", "v1", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            raise UnityError(f"cannot initialise Google backend: {exc}") from exc

    @staticmethod
    def _meta(raw: dict[str, Any]) -> FileMeta:
        return FileMeta(
            file_id=raw["id"],
            name=raw.get("name", ""),
            mime_type=raw.get("mimeType", ""),
            parents=tuple(raw.get("parents", [])),
            drive_id=raw.get("driveId"),
            trashed=bool(raw.get("trashed", False)),
        )

    def get_file(self, file_id: str) -> FileMeta | None:
        try:
            raw = self.drive.files().get(
                fileId=file_id,
                supportsAllDrives=True,
                fields="id,name,mimeType,parents,driveId,trashed",
            ).execute()
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 404:
                return None
            raise UnityError(f"Drive metadata read failed for {file_id}: {exc}") from exc
        return self._meta(raw)

    def _list(self, **kwargs: Any) -> list[FileMeta]:
        result: list[FileMeta] = []
        token: str | None = None
        while True:
            request = self.drive.files().list(
                fields="nextPageToken,files(id,name,mimeType,parents,driveId,trashed)",
                pageSize=1000,
                pageToken=token,
                **kwargs,
            )
            raw = request.execute()
            result.extend(self._meta(item) for item in raw.get("files", []))
            token = raw.get("nextPageToken")
            if not token:
                return result

    def list_children(
        self, parent_id: str, *, name: str | None = None,
        mime_type: str | None = None
    ) -> list[FileMeta]:
        parent = self.get_file(parent_id)
        if parent is None or not parent.drive_id:
            raise UnityError(f"cannot resolve Shared Drive for folder {parent_id}")
        clauses = [f"'{_drive_query_literal(parent_id)}' in parents", "trashed = false"]
        if name is not None:
            clauses.append(f"name = '{_drive_query_literal(name)}'")
        if mime_type is not None:
            clauses.append(f"mimeType = '{_drive_query_literal(mime_type)}'")
        return self._list(
            q=" and ".join(clauses),
            corpora="drive",
            driveId=parent.drive_id,
            spaces="drive",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )

    def list_exact_name(self, drive_id: str, name: str) -> list[FileMeta]:
        return self._list(
            q=f"name = '{_drive_query_literal(name)}' and trashed = false",
            corpora="drive",
            driveId=drive_id,
            spaces="drive",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )

    @staticmethod
    def _structural_text(elements: Iterable[dict[str, Any]]) -> str:
        pieces: list[str] = []
        for element in elements:
            paragraph = element.get("paragraph")
            if paragraph:
                for item in paragraph.get("elements", []):
                    run = item.get("textRun")
                    if run:
                        pieces.append(run.get("content", ""))
            table = element.get("table")
            if table:
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        pieces.append(GoogleBackend._structural_text(cell.get("content", [])))
            toc = element.get("tableOfContents")
            if toc:
                pieces.append(GoogleBackend._structural_text(toc.get("content", [])))
        return "".join(pieces)

    @staticmethod
    def _paragraph_values(elements: Iterable[dict[str, Any]]) -> list[str]:
        """Return paragraph text in document order for projection hashing.

        Google terminates each paragraph's final text run with LF; the
        connector's paragraph value does not include that structural marker,
        so exactly one terminal LF is removed here.  All other whitespace is
        retained.  Tables and table-of-contents blocks are walked in their
        visible structural order.
        """
        values: list[str] = []
        for element in elements:
            paragraph = element.get("paragraph")
            if paragraph:
                value = "".join(
                    item.get("textRun", {}).get("content", "")
                    for item in paragraph.get("elements", [])
                    if item.get("textRun")
                )
                if value.endswith("\n"):
                    value = value[:-1]
                values.append(value)
            table = element.get("table")
            if table:
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        values.extend(
                            GoogleBackend._paragraph_values(cell.get("content", []))
                        )
            toc = element.get("tableOfContents")
            if toc:
                values.extend(
                    GoogleBackend._paragraph_values(toc.get("content", []))
                )
        return values

    @staticmethod
    def _native_projection(
        elements: Iterable[dict[str, Any]], lists: dict[str, Any]
    ) -> dict[str, Any]:
        paragraphs: list[dict[str, Any]] = []

        def walk(items: Iterable[dict[str, Any]]) -> None:
            for element in items:
                paragraph = element.get("paragraph")
                if paragraph:
                    runs: list[dict[str, Any]] = []
                    for content in paragraph.get("elements", []):
                        text_run = content.get("textRun")
                        if not text_run:
                            continue
                        value = str(text_run.get("content", ""))
                        style = text_run.get("textStyle", {}) or {}
                        run: dict[str, Any] = {"text": value}
                        for key in ("bold", "italic", "underline", "strikethrough"):
                            if style.get(key) is True:
                                run[key] = True
                        family = (
                            style.get("weightedFontFamily", {}) or {}
                        ).get("fontFamily")
                        if family and "mono" in str(family).casefold():
                            run["font_family"] = (
                                "Roboto Mono"
                                if str(family).casefold() == "roboto mono"
                                else str(family)
                            )
                            run["code"] = True
                        link = style.get("link") or {}
                        if link.get("url"):
                            run["link"] = link["url"]
                            # Google supplies its standard blue/underlined link
                            # appearance as effective text style.  The locked
                            # projection records the semantic link, not that
                            # provider-generated presentation detail.
                            run.pop("underline", None)
                        elif link.get("bookmarkId"):
                            run["link"] = f"bookmark:{link['bookmarkId']}"
                            run.pop("underline", None)
                        elif link.get("headingId"):
                            run["link"] = f"heading:{link['headingId']}"
                            run.pop("underline", None)
                        runs.append(run)
                    if runs and str(runs[-1].get("text", "")).endswith("\n"):
                        runs[-1]["text"] = str(runs[-1]["text"])[:-1]
                    item: dict[str, Any] = {
                        "named_style": (
                            paragraph.get("paragraphStyle", {}) or {}
                        ).get("namedStyleType", "NORMAL_TEXT"),
                        "runs": _merge_runs(runs),
                    }
                    bullet = paragraph.get("bullet")
                    if bullet:
                        level = int(bullet.get("nestingLevel", 0))
                        list_id = str(bullet.get("listId", ""))
                        nesting = (
                            ((lists.get(list_id, {}) or {}).get("listProperties", {}) or {})
                            .get("nestingLevels", [])
                        )
                        level_data = (
                            nesting[level]
                            if isinstance(nesting, list) and level < len(nesting)
                            else {}
                        )
                        # Unordered lists also carry a ``%0`` glyphFormat.
                        # Only a typed glyph is a numbering witness.
                        ordered = bool(level_data.get("glyphType"))
                        item["list"] = {
                            "kind": "ordered" if ordered else "unordered",
                            "nesting_level": level,
                        }
                    paragraphs.append(item)
                table = element.get("table")
                if table:
                    for row in table.get("tableRows", []):
                        for cell in row.get("tableCells", []):
                            walk(cell.get("content", []))
                toc = element.get("tableOfContents")
                if toc:
                    walk(toc.get("content", []))

        walk(elements)
        return {"schema": NATIVE_PROJECTION_SCHEMA, "paragraphs": paragraphs}

    def read_document(self, document_id: str) -> DocumentData:
        try:
            raw = self.docs.documents().get(documentId=document_id).execute()
        except Exception as exc:
            raise UnityError(f"Docs read failed for {document_id}: {exc}") from exc
        body = raw.get("body", {}).get("content", [])
        revision = raw.get("revisionId")
        if not revision:
            raise UnityError(f"Docs response lacks revisionId for {document_id}")
        projection = self._native_projection(body, raw.get("lists", {}) or {})
        return DocumentData(
            text=_projection_text(projection),
            revision_id=str(revision),
            paragraphs=tuple(
                _paragraph_text_value(paragraph)
                for paragraph in projection["paragraphs"]
            ),
            native_projection=projection,
        )

    def replace_document(
        self, document_id: str, text: str, *, expected_revision_id: str,
        native_projection: dict[str, Any]
    ) -> DocumentData:
        del document_id, text, expected_revision_id, native_projection
        raise UnityError(
            "Google document writes are disabled in this candidate: no approved "
            "formatting-preserving renderer is installed"
        )


def review_snapshot_payload(plan: Plan, *, approval: str = "UNREVIEWED") -> dict[str, Any]:
    """Build an auditable observation snapshot; never auto-approve it."""
    if plan.inspection is None or plan.payload.get("plan_kind") != "drive":
        raise UnityError("a review snapshot requires a full target inspection")
    core = {
        "schema_version": 1,
        "kind": REVIEW_SNAPSHOT_KIND,
        "normalization": PROJECTION_NORMALIZATION,
        "plan_digest": plan.digest,
        "family": plan.payload["family"],
        "edition": plan.payload["edition"],
        "unity_set_digest": plan.payload["unity_set_digest"],
        "root": plan.payload["root"],
        "portable_hierarchy": plan.payload["portable_hierarchy"],
        "publish_order": plan.payload["publish_order"],
        "documents": plan.payload["documents"],
    }
    payload = dict(core)
    payload["approval"] = approval
    payload["snapshot_digest"] = stable_digest(core)
    return payload


def validate_reviewed_snapshot(path: Path, plan: Plan, confirmation: str) -> None:
    """Require a manually reviewed, exact snapshot of the fresh target state."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnityError(f"cannot read reviewed snapshot {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise UnityError("reviewed snapshot root must be an object")
    if raw.get("approval") != "REVIEWED":
        raise UnityError(
            "snapshot is not explicitly reviewed; inspect it and change approval "
            "from UNREVIEWED to REVIEWED"
        )
    expected = review_snapshot_payload(plan, approval="REVIEWED")
    if set(raw) != set(expected):
        raise UnityError("reviewed snapshot fields differ from the guarded schema")
    supplied_digest = raw.get("snapshot_digest")
    if not isinstance(supplied_digest, str) or not SHA256_RE.fullmatch(supplied_digest):
        raise UnityError("reviewed snapshot digest is missing or malformed")
    core = {
        key: value
        for key, value in raw.items()
        if key not in {"approval", "snapshot_digest"}
    }
    if stable_digest(core) != supplied_digest:
        raise UnityError("reviewed snapshot digest does not match its content")
    if confirmation != supplied_digest:
        raise UnityError(
            "reviewed snapshot confirmation does not match the full snapshot digest"
        )
    if raw != expected:
        raise UnityError(
            "reviewed snapshot is stale or belongs to a different source/target state"
        )


def _write_review_snapshot(path: Path, plan: Plan) -> None:
    payload = review_snapshot_payload(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_plan(path: Path, plan: Plan) -> None:
    payload = dict(plan.payload)
    payload["plan_digest"] = plan.digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _print_plan(plan: Plan) -> None:
    print(
        f"plan: {plan.payload['plan_kind']} — {plan.payload['edition']} — "
        f"{len(plan.payload['documents'])} permanent documents"
    )
    for item in plan.payload["documents"]:
        current = item.get("current_text_sha256")
        state = "current" if current == item["desired_text_sha256"] else "update"
        if item.get("source_equivalent"):
            state = (
                "native exact"
                if item.get("current_unity_set_digest")
                == plan.payload.get("unity_set_digest")
                else "native source"
            )
        if current is None:
            state = "source ready"
        print(
            f"  {item['role']:9} {state:12} {item['title']} "
            f"[{item['parent_path']}] {item['source_sha256'][:12]}"
        )
    print(f"plan digest: {plan.digest}")


def require_rendering_acknowledgement(
    backend_name: str, *, apply: bool, acknowledged: bool
) -> None:
    """Fail closed until a reviewed native-Docs renderer exists.

    The acknowledgement flag is retained in the candidate CLI so an old run
    book cannot accidentally bypass the new guard.  It deliberately has no
    power to enable Google writes.
    """
    if backend_name == "google" and apply:
        raise UnityError(
            "Google apply is disabled: the available writer replaces native "
            "Docs with plain text, flattening headings/lists and risking native "
            "code-block structure. Use Google dry-run/snapshot only until an "
            "approved formatting-preserving renderer passes visual review. "
            "--acknowledge-plain-text-replacement cannot override this guard."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument("--config", type=Path, default=here / "unity-config.json")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--backend", choices=("source", "state", "google"), default="source")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--state-out", type=Path)
    parser.add_argument("--credentials", type=Path)
    parser.add_argument("--plan-out", type=Path)
    parser.add_argument(
        "--snapshot-out",
        type=Path,
        help=(
            "write an UNREVIEWED observation snapshot during a full dry run; "
            "this never grants apply authority"
        ),
    )
    parser.add_argument(
        "--reviewed-snapshot",
        type=Path,
        help="manually reviewed observation snapshot required for Google apply",
    )
    parser.add_argument(
        "--confirm-reviewed-snapshot",
        default="",
        help="full digest printed inside the manually reviewed snapshot",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument(
        "--acknowledge-plain-text-replacement",
        action="store_true",
        help=(
            "deprecated no-op: Google apply remains fail-closed until a native "
            "formatting-preserving renderer is approved"
        ),
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        backend: Backend | None
        state_backend: JsonStateBackend | None = None
        if args.backend == "source":
            backend = None
        elif args.backend == "state":
            if args.state is None:
                raise UnityError("--backend state requires --state")
            state_backend = JsonStateBackend(args.state)
            backend = state_backend
        else:
            if args.credentials is None:
                raise UnityError("--backend google requires --credentials")
            backend = GoogleBackend(args.credentials)

        updater = UnityUpdater(config, args.source_root, backend)
        plan = updater.source_plan() if backend is None else updater.full_plan()
        _print_plan(plan)
        if args.plan_out:
            _write_plan(args.plan_out, plan)
            print(f"plan written: {args.plan_out}")
        if args.snapshot_out:
            _write_review_snapshot(args.snapshot_out, plan)
            print(
                f"UNREVIEWED observation snapshot written: {args.snapshot_out}"
            )

        if not args.apply:
            print("dry run only — no target content changed")
            return 0
        require_rendering_acknowledgement(
            args.backend,
            apply=args.apply,
            acknowledged=args.acknowledge_plain_text_replacement,
        )
        if backend is None:
            raise UnityError("source-only backend cannot apply")
        if not args.confirm:
            raise UnityError("--apply requires --confirm with the full plan digest")
        if args.backend == "state":
            if args.state_out is None:
                raise UnityError("state apply requires a distinct --state-out")
            if args.state.resolve() == args.state_out.resolve():
                raise UnityError("state apply refuses to overwrite its input fixture")
        if args.backend == "google":
            if args.reviewed_snapshot is None:
                raise UnityError(
                    "Google apply requires --reviewed-snapshot from a prior dry run"
                )
            if not args.confirm_reviewed_snapshot:
                raise UnityError(
                    "Google apply requires --confirm-reviewed-snapshot with its full digest"
                )
            validate_reviewed_snapshot(
                args.reviewed_snapshot,
                plan,
                args.confirm_reviewed_snapshot,
            )

        actions = updater.apply(plan, args.confirm)
        for action in actions:
            print(action)
        if state_backend is not None:
            state_backend.save(args.state_out)
            print(f"offline result written: {args.state_out}")
        return 0
    except UnityError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
