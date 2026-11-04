from __future__ import annotations

import copy
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from unity_update import (
    BLUEPRINT_BOOT_MARKER,
    BLUEPRINT_BOOT_POINTER,
    BLUEPRINT_EDIT_MARKER,
    CHECK_TRANSPORT_OLD,
    EDIT_TRANSPORT_OLD,
    GOOGLE_CODEBLOCK_SENTINELS,
    GOOGLE_DOC_MIME,
    GOOGLE_DOC_URL,
    GOOGLE_FOLDER_MIME,
    GoogleBackend,
    PHOTO_TRANSPORT_OLD,
    PR_TRANSPORT_OLD,
    JsonStateBackend,
    UnityError,
    UnityUpdater,
    _combine_projection,
    _envelope,
    _envelope_projection,
    _link_phrase_once,
    _render_boot,
    _unity_set_digest,
    canonical_text,
    compile_google_docs_requests,
    load_config,
    markdown_native_projection,
    nonblank_projection_sha256,
    parse_identity,
    review_snapshot_payload,
    require_rendering_acknowledgement,
    require_disposable_proof_target,
    sha256_text,
    stable_digest,
    transport_source,
    validate_reviewed_snapshot,
)


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = CANDIDATE_ROOT / "unity-config.json"


def module_source(role: str, edition: str) -> str:
    return canonical_text(
        f"---\nname: {role}\ndescription: fixture\n---\n"
        f"<!-- {edition} -->\n\n# {role.upper()}\n\nFixture {role}."
    )


class RecordingBackend(JsonStateBackend):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.writes: list[str] = []
        self.fail_id: str | None = None
        self.tamper_after_id: str | None = None
        self.tamper_id: str | None = None

    def replace_document(
        self, document_id: str, text: str, *, expected_revision_id: str,
        native_projection: dict
    ):
        self.writes.append(document_id)
        if document_id == self.fail_id:
            raise UnityError("injected write failure")
        result = super().replace_document(
            document_id,
            text,
            expected_revision_id=expected_revision_id,
            native_projection=native_projection,
        )
        if document_id == self.tamper_after_id and self.tamper_id:
            item = self._records[self.tamper_id]
            item["text"] = canonical_text(item["text"] + "concurrent tamper\n")
            item["revision_id"] = "r-tampered"
        return result


class UnityUpdaterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_root = self.root / "Blueprint"
        self.source_root.mkdir()
        self.config_path = self.root / "unity-config.json"
        self.config_path.write_bytes(BASE_CONFIG.read_bytes())
        self.config = load_config(self.config_path)
        self._write_sources("new_edition")
        self.state_path = self.root / "drive.json"
        self._write_state("old_edition")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, relative: str, text: str) -> None:
        path = self.source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(canonical_text(text), encoding="utf-8", newline="\n")

    def _write_sources(self, edition: str) -> None:
        self._write("VERSION.txt", edition)
        self._write(
            "BLUEPRINT.txt",
            f"<!-- {edition} -->\n<!-- MASTER {edition} -->\n# Blueprint\n\n"
            f"{BLUEPRINT_BOOT_MARKER}\n\n---\nname: boot\ndescription: fixture\n---\n\n"
            "# Old embedded Boot\n\nOld route rules.\n\n"
            f"{BLUEPRINT_EDIT_MARKER}\n\n---\nname: edit\ndescription: fixture\n---\n\n"
            f"# EDIT\n\n{EDIT_TRANSPORT_OLD}\n\n"
            "<!-- COMPONENT: CHECK -->\n\n---\nname: check\ndescription: fixture\n---\n\n"
            f"# CHECK\n\n{CHECK_TRANSPORT_OLD}\n\n"
            "<!-- COMPONENT: PHOTO -->\n\n---\nname: photo\ndescription: fixture\n---\n\n"
            f"# PHOTO\n\n{PHOTO_TRANSPORT_OLD}\n\n"
            "```text\nPhoto return\n```\n\n"
            "<!-- COMPONENT: PR -->\n\n---\nname: pr\ndescription: fixture\n---\n\n"
            f"# PR\n\n{PR_TRANSPORT_OLD}\n",
        )
        self._write("DIRECTORY.txt", f"# {edition}\nindex:\n  routes: []\n")
        self._write("DEPLOY/routed/BOOT.md", module_source("boot", edition))
        self._write(
            "DEPLOY/routed/edit.md",
            module_source("edit", edition)
            + f"\n- **Bold** and `code`; [link](https://example.test).\n\n"
            + EDIT_TRANSPORT_OLD
            + "\n",
        )
        self._write(
            "DEPLOY/routed/modules/check.md",
            module_source("check", edition) + "\n" + CHECK_TRANSPORT_OLD + "\n",
        )
        self._write(
            "DEPLOY/routed/modules/photo.md",
            module_source("photo", edition)
            + "\n"
            + PHOTO_TRANSPORT_OLD
            + "\n\n```text\nPhoto return\n```\n",
        )
        self._write(
            "DEPLOY/routed/modules/pr.md",
            module_source("pr", edition) + "\n" + PR_TRANSPORT_OLD + "\n",
        )
        hashes = {
            target.role: hashlib.sha256(
                (self.source_root / target.source).read_bytes()
            ).hexdigest()
            for target in self.config.targets
        }
        raw_config = json.loads(self.config_path.read_text(encoding="utf-8"))
        raw_config["expected_edition"] = edition
        raw_config["boot_projection_sha256"] = "0" * 64
        for item in raw_config["targets"]:
            item["source_sha256"] = hashes[item["role"]]
        self.config_path.write_text(
            json.dumps(raw_config, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        self.config = load_config(self.config_path)
        set_digest = _unity_set_digest(self.config, edition, hashes)
        boot_target = self.config.by_role["boot"]
        boot_source = canonical_text(
            (self.source_root / boot_target.source).read_text(encoding="utf-8")
        )
        rendered = _render_boot(
            self.config,
            boot_target,
            edition,
            boot_source,
            hashes["boot"],
            hashes,
            set_digest,
        )
        rendered_lines = rendered.rstrip("\n").split("\n")
        envelope_lines = _envelope(
            self.config, boot_target, edition, hashes["boot"], set_digest
        )
        body = markdown_native_projection(
            "\n".join(rendered_lines[len(envelope_lines) + 1:]) + "\n"
        )
        projection = _combine_projection(
            _envelope_projection(
                self.config, boot_target, edition, hashes["boot"], set_digest
            ),
            body,
        )
        for role in self.config.publish_order:
            mapped = self.config.by_role[role]
            _link_phrase_once(
                projection,
                mapped.title,
                GOOGLE_DOC_URL.format(document_id=mapped.document_id),
                context=f"fixture.{role}",
                exact_paragraph=f"TITLE: {mapped.title}",
            )
        raw_config["boot_projection_sha256"] = stable_digest(projection)
        self.config_path.write_text(
            json.dumps(raw_config, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        self.config = load_config(self.config_path)
        receipt = {
            "version": edition,
            "compatibility_files": {
                "BLUEPRINT.txt": hashes["blueprint"],
                "DIRECTORY.txt": hashes["directory"],
            },
        }
        self._write("build-receipt.json", json.dumps(receipt, indent=2))
        routed = [
            f"# {edition}",
            f"version: {edition}",
            "files:",
        ]
        for role in ("boot", "edit", "check", "photo", "pr"):
            target = self.config.by_role[role]
            relative = target.source.removeprefix("DEPLOY/routed/")
            path = self.source_root / target.source
            routed.extend([
                f"  - path: {relative}",
                f"    bytes: {path.stat().st_size}",
                f"    sha256: {hashes[role]}",
            ])
        self._write("DEPLOY/routed/INDEX.yaml", "\n".join(routed))

    def _identity_text(
        self, role: str, edition: str, status: str | None = None
    ) -> str:
        status = status or self.config.status
        return canonical_text(
            f"BKP 3.0 UNITY\nROLE: {role.upper()}\nSOURCE EDITION: {edition}\n"
            f"STATUS: {status.upper()}\n\nold {role} body\n"
        )

    def _write_state(self, edition: str, status: str | None = None) -> None:
        status = status or self.config.status
        drive = "shared-drive"
        root_id = self.config.root_id
        folders = [
            {
                "id": root_id,
                "name": self.config.root_title,
                "mime_type": GOOGLE_FOLDER_MIME,
                "parents": [],
                "drive_id": drive,
                "trashed": False,
            },
            {
                "id": "folder-deploy",
                "name": "DEPLOY",
                "mime_type": GOOGLE_FOLDER_MIME,
                "parents": [root_id],
                "drive_id": drive,
                "trashed": False,
            },
            {
                "id": "folder-routed",
                "name": "routed",
                "mime_type": GOOGLE_FOLDER_MIME,
                "parents": ["folder-deploy"],
                "drive_id": drive,
                "trashed": False,
            },
            {
                "id": "folder-modules",
                "name": "modules",
                "mime_type": GOOGLE_FOLDER_MIME,
                "parents": ["folder-routed"],
                "drive_id": drive,
                "trashed": False,
            },
        ]
        parent_ids = {
            ".": root_id,
            "DEPLOY/routed": "folder-routed",
            "DEPLOY/routed/modules": "folder-modules",
        }
        documents = []
        for target in self.config.targets:
            text = self._identity_text(target.role, edition, status)
            if target.role == "photo":
                opener, closer = GOOGLE_CODEBLOCK_SENTINELS
                text = canonical_text(
                    f"BKP 3.0 UNITY\nROLE: PHOTO\nSOURCE EDITION: {edition}\n"
                    f"STATUS: {status.upper()}\n\n{opener}\nold photo body\n{closer}\n"
                )
            documents.append({
                "id": target.document_id,
                "name": target.title,
                "mime_type": GOOGLE_DOC_MIME,
                "parents": [parent_ids[target.parent_path]],
                "drive_id": drive,
                "trashed": False,
                "revision_id": "r1",
                "text": text,
            })
        self.state_path.write_text(
            json.dumps({"files": folders + documents}, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _backend(self) -> RecordingBackend:
        return RecordingBackend(self.state_path)

    def _updater(self, backend: RecordingBackend) -> UnityUpdater:
        return UnityUpdater(self.config, self.source_root, backend)

    def test_source_map_has_all_roles_and_boot_last(self) -> None:
        updater = UnityUpdater(self.config, self.source_root, None)
        plan = updater.source_plan()
        roles = [item["role"] for item in plan.payload["documents"]]
        self.assertEqual(roles, list(self.config.publish_order))
        self.assertEqual(roles[-1], "boot")
        self.assertEqual(len(roles), 7)
        self.assertEqual(len(plan.digest), 64)
        self.assertEqual(len(plan.payload["unity_set_digest"]), 64)
        self.assertFalse(plan.payload["google_apply"]["enabled"])
        for item in plan.payload["documents"]:
            self.assertIn("desired_native_projection", item)
            self.assertEqual(len(item["desired_native_projection_sha256"]), 64)
            self.assertEqual(len(item["desired_format_link_sha256"]), 64)

    def test_transport_substitutions_are_exact_once_and_plan_bound(self) -> None:
        updater = UnityUpdater(self.config, self.source_root, None)
        expected_counts = {
            "blueprint": 5,
            "edit": 1,
            "check": 1,
            "photo": 1,
            "pr": 1,
            "directory": 0,
            "boot": 0,
        }
        plan = updater.source_plan()
        for item in plan.payload["documents"]:
            role = item["role"]
            self.assertEqual(
                len(item["transport_changes"]), expected_counts[role]
            )
            self.assertTrue(all(
                change["matches"] == 1
                for change in item["transport_changes"]
            ))
        blueprint = updater.desired["blueprint"].transport_text
        self.assertEqual(blueprint.count(BLUEPRINT_BOOT_MARKER), 1)
        self.assertEqual(blueprint.count(BLUEPRINT_EDIT_MARKER), 1)
        pointer_start = blueprint.index(BLUEPRINT_BOOT_MARKER)
        pointer_end = blueprint.index(BLUEPRINT_EDIT_MARKER)
        self.assertEqual(
            blueprint[pointer_start:pointer_end],
            BLUEPRINT_BOOT_POINTER,
        )
        self.assertIn("Boot is the sole manifest and ignition point", blueprint)
        self.assertNotIn("Old route rules.", blueprint)
        self.assertNotIn(EDIT_TRANSPORT_OLD, blueprint)

        projection = updater.desired["blueprint"].native_projection
        visible_projection = "\n".join(
            "".join(run.get("text", "") for run in paragraph["runs"])
            for paragraph in projection["paragraphs"]
        )
        self.assertNotIn("name: edit", visible_projection)
        self.assertNotIn("description: fixture", visible_projection)
        linked = [
            run
            for paragraph in projection["paragraphs"]
            for run in paragraph["runs"]
            if run.get("text") == "Boot document"
        ]
        self.assertEqual(len(linked), 1)
        self.assertEqual(
            linked[0]["link"],
            GOOGLE_DOC_URL.format(
                document_id=self.config.by_role["boot"].document_id
            ),
        )

        tampered = copy.deepcopy(plan.payload)
        target_projection = tampered["documents"][0]["desired_native_projection"]
        for paragraph in target_projection["paragraphs"]:
            for run in paragraph["runs"]:
                if run.get("text") == "Boot document":
                    run["link"] = "https://example.test/wrong"
        self.assertNotEqual(stable_digest(tampered), plan.digest)

    def test_transport_selector_ambiguity_is_fatal(self) -> None:
        with self.assertRaisesRegex(UnityError, "exactly once"):
            transport_source("edit", EDIT_TRANSPORT_OLD + "\n" + EDIT_TRANSPORT_OLD)
        with self.assertRaisesRegex(UnityError, "BOOT marker"):
            transport_source("blueprint", BLUEPRINT_EDIT_MARKER + "\n")

    def test_native_projection_carries_structure_and_inline_links(self) -> None:
        updater = UnityUpdater(self.config, self.source_root, None)
        projection = updater.desired["edit"].native_projection
        paragraphs = projection["paragraphs"]
        self.assertTrue(any(
            paragraph["named_style"].startswith("HEADING_")
            for paragraph in paragraphs
        ))
        self.assertTrue(any("list" in paragraph for paragraph in paragraphs))
        runs = [run for paragraph in paragraphs for run in paragraph["runs"]]
        self.assertTrue(any(run.get("bold") for run in runs))
        self.assertTrue(any(run.get("code") for run in runs))
        self.assertTrue(any(run.get("link") == "https://example.test" for run in runs))

    def test_google_request_compiler_preserves_structure_and_utf16_ranges(self) -> None:
        projection = {
            "schema": "bkp-google-docs-native-projection-v2",
            "paragraphs": [
                {
                    "named_style": "TITLE",
                    "runs": [{"text": "Writer proof"}],
                },
                {
                    "named_style": "NORMAL_TEXT",
                    "runs": [
                        {"text": "Emoji 🧭 and "},
                        {
                            "text": "Roadmap",
                            "bold": True,
                            "link": "https://example.test/roadmap",
                        },
                    ],
                },
                {
                    "named_style": "NORMAL_TEXT",
                    "runs": [{"text": "Parent"}],
                    "list": {"kind": "unordered", "nesting_level": 0},
                },
                {
                    "named_style": "NORMAL_TEXT",
                    "runs": [{"text": "Child"}],
                    "list": {"kind": "unordered", "nesting_level": 1},
                },
                {
                    "named_style": "NORMAL_TEXT",
                    "runs": [{"text": "Step one"}],
                    "list": {"kind": "ordered", "nesting_level": 0},
                },
                {
                    "named_style": "NORMAL_TEXT",
                    "runs": [{
                        "text": "ROLE: PROOF",
                        "code": True,
                        "font_family": "Roboto Mono",
                    }],
                },
            ],
        }
        requests = compile_google_docs_requests(
            projection, current_end_index=125, tab_id="t.0"
        )
        self.assertIn("deleteContentRange", requests[0])
        inserted = requests[1]["insertText"]["text"]
        self.assertIn("\tChild", inserted)
        self.assertEqual(inserted.count("🧭"), 1)
        self.assertEqual(
            [next(iter(request)) for request in requests[:5]],
            [
                "deleteContentRange",
                "insertText",
                "deleteParagraphBullets",
                "updateParagraphStyle",
                "updateTextStyle",
            ],
        )
        paragraph_reset = requests[3]["updateParagraphStyle"]["fields"]
        self.assertIn("indentStart", paragraph_reset)
        self.assertNotIn("namedStyleType", paragraph_reset)
        self.assertEqual(requests[4]["updateTextStyle"]["fields"], "*")
        bullet_requests = [
            request["createParagraphBullets"]
            for request in requests
            if "createParagraphBullets" in request
        ]
        self.assertEqual(
            [request["bulletPreset"] for request in bullet_requests],
            ["NUMBERED_DECIMAL_ALPHA_ROMAN", "BULLET_DISC_CIRCLE_SQUARE"],
        )
        link_request = next(
            request["updateTextStyle"]
            for request in requests
            if request.get("updateTextStyle", {}).get("textStyle", {}).get("link")
        )
        self.assertEqual(
            link_request["range"]["endIndex"]
            - link_request["range"]["startIndex"],
            len("Roadmap"),
        )
        emoji_paragraph = projection["paragraphs"][1]
        code_request = next(
            request["updateTextStyle"]
            for request in requests
            if request.get("updateTextStyle", {})
            .get("textStyle", {})
            .get("weightedFontFamily")
        )
        before_code = inserted[:inserted.index("ROLE: PROOF")]
        expected_code_start = 1 + len(before_code.encode("utf-16-le")) // 2
        self.assertEqual(code_request["range"]["startIndex"], expected_code_start)
        self.assertEqual(
            "".join(run["text"] for run in emoji_paragraph["runs"]),
            "Emoji 🧭 and Roadmap",
        )

    def test_google_request_compiler_rejects_unsafe_projection(self) -> None:
        with self.assertRaisesRegex(UnityError, "paragraph break"):
            compile_google_docs_requests(
                {
                    "schema": "bkp-google-docs-native-projection-v2",
                    "paragraphs": [{
                        "named_style": "NORMAL_TEXT",
                        "runs": [{"text": "unsafe\nbreak"}],
                    }],
                },
                current_end_index=2,
                tab_id="t.0",
            )
        with self.assertRaisesRegex(UnityError, "absolute HTTP"):
            compile_google_docs_requests(
                {
                    "schema": "bkp-google-docs-native-projection-v2",
                    "paragraphs": [{
                        "named_style": "NORMAL_TEXT",
                        "runs": [{"text": "bad link", "link": "javascript:bad"}],
                    }],
                },
                current_end_index=2,
                tab_id="t.0",
            )
        with self.assertRaisesRegex(UnityError, "Google Docs can strip"):
            compile_google_docs_requests(
                {
                    "schema": "bkp-google-docs-native-projection-v2",
                    "paragraphs": [{
                        "named_style": "NORMAL_TEXT",
                        "runs": [{"text": "private\uec03sentinel"}],
                    }],
                },
                current_end_index=2,
                tab_id="t.0",
            )
        with self.assertRaisesRegex(UnityError, "unsupported fields"):
            compile_google_docs_requests(
                {
                    "schema": "bkp-google-docs-native-projection-v2",
                    "paragraphs": [{
                        "named_style": "NORMAL_TEXT",
                        "runs": [{"text": "provenance"}],
                        "literal": True,
                    }],
                },
                current_end_index=2,
                tab_id="t.0",
            )

    def test_google_readback_normalises_provider_link_decoration(self) -> None:
        observed = GoogleBackend._native_projection(
            [{
                "paragraph": {
                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    "elements": [{
                        "textRun": {
                            "content": "Roadmap\n",
                            "textStyle": {
                                "underline": True,
                                "link": {"url": "https://example.test/roadmap"},
                            },
                        }
                    }],
                }
            }],
            {},
        )
        self.assertEqual(
            observed["paragraphs"][0]["runs"],
            [{"text": "Roadmap", "link": "https://example.test/roadmap"}],
        )

    def test_google_readback_distinguishes_bullets_from_numbering(self) -> None:
        elements = [
            {
                "paragraph": {
                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    "bullet": {"listId": "bullets"},
                    "elements": [{"textRun": {
                        "content": "Bullet\n", "textStyle": {}
                    }}],
                }
            },
            {
                "paragraph": {
                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    "bullet": {"listId": "ambiguous"},
                    "elements": [{"textRun": {
                        "content": "Format only\n", "textStyle": {}
                    }}],
                }
            },
            {
                "paragraph": {
                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    "bullet": {"listId": "numbers"},
                    "elements": [{"textRun": {
                        "content": "Number\n", "textStyle": {}
                    }}],
                }
            },
        ]
        lists = {
            "bullets": {"listProperties": {"nestingLevels": [{
                "glyphSymbol": "●", "glyphFormat": "%0"
            }]}},
            "numbers": {"listProperties": {"nestingLevels": [{
                "glyphType": "DECIMAL", "glyphFormat": "%0."
            }]}},
            "ambiguous": {"listProperties": {"nestingLevels": [{
                "glyphFormat": "%0"
            }]}},
        }
        observed = GoogleBackend._native_projection(elements, lists)
        self.assertEqual(observed["paragraphs"][0]["list"]["kind"], "unordered")
        self.assertEqual(observed["paragraphs"][1]["list"]["kind"], "unordered")
        self.assertEqual(observed["paragraphs"][2]["list"]["kind"], "ordered")

    def test_google_blank_mono_round_trip_and_default_font_suppression(self) -> None:
        observed = GoogleBackend._native_projection(
            [
                {
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "elements": [{"textRun": {
                            "content": "\n",
                            "textStyle": {"weightedFontFamily": {
                                "fontFamily": "Roboto Mono"
                            }},
                        }}],
                    }
                },
                {
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "elements": [{"textRun": {
                            "content": "Default face\n",
                            "textStyle": {"weightedFontFamily": {
                                "fontFamily": "Google Sans"
                            }},
                        }}],
                    }
                },
            ],
            {},
        )
        self.assertEqual(
            observed["paragraphs"][0]["runs"],
            [{"text": "", "font_family": "Roboto Mono", "code": True}],
        )
        self.assertEqual(
            observed["paragraphs"][1]["runs"],
            [{"text": "Default face"}],
        )
        requests = compile_google_docs_requests(
            {
                "schema": "bkp-google-docs-native-projection-v2",
                "paragraphs": [{
                    "named_style": "NORMAL_TEXT",
                    "runs": [{
                        "text": "", "font_family": "Roboto Mono", "code": True
                    }],
                }],
            },
            current_end_index=2,
            tab_id="t.0",
        )
        mono = next(
            request["updateTextStyle"]
            for request in requests
            if request.get("updateTextStyle", {})
            .get("textStyle", {})
            .get("weightedFontFamily")
        )
        self.assertEqual(mono["range"], {
            "startIndex": 1, "endIndex": 2, "tabId": "t.0"
        })

    def test_google_request_compiler_accepts_all_seven_locked_projections(self) -> None:
        updater = UnityUpdater(self.config, self.source_root, None)
        for role in self.config.publish_order:
            requests = compile_google_docs_requests(
                updater.desired[role].native_projection,
                current_end_index=2,
                tab_id="t.0",
            )
            self.assertTrue(requests, role)
            self.assertIn("insertText", requests[0])

    def test_disposable_writer_proof_refuses_all_protected_ids(self) -> None:
        for target in self.config.targets:
            with self.assertRaisesRegex(UnityError, "protected Unity"):
                require_disposable_proof_target(target.document_id, self.config)
        require_disposable_proof_target(
            "1cjseEGU5hMEc0MmKXRuqkc36kgDKxd12GjTw_BdJ-Xo",
            self.config,
        )

    def test_source_edition_label_is_mandatory(self) -> None:
        good = self._identity_text("edit", "old_edition")
        self.assertEqual(
            parse_identity(good, "BKP 3.0 UNITY").edition,
            "old_edition",
        )
        bad = good.replace("SOURCE EDITION:", "EDITION:")
        with self.assertRaisesRegex(UnityError, "SOURCE EDITION"):
            parse_identity(bad, "BKP 3.0 UNITY")

    def test_directory_nonblank_projection_drops_only_zero_length_lines(self) -> None:
        baseline = ["root:", "  child: value"]
        self.assertEqual(
            nonblank_projection_sha256(baseline),
            nonblank_projection_sha256(["", *baseline, ""]),
        )
        self.assertNotEqual(
            nonblank_projection_sha256(baseline),
            nonblank_projection_sha256(["root:", " ", "  child: value"]),
        )

    def test_boot_is_manifest_only_and_hides_permanent_ids(self) -> None:
        updater = UnityUpdater(self.config, self.source_root, None)
        boot = updater.desired["boot"].text
        self.assertIn("SOURCE EDITION: new_edition", boot)
        self.assertIn(f"UNITY SET: {updater.unity_set_digest}", boot)
        self.assertNotIn("DOCUMENT-ID", boot)
        self.assertNotIn("Fixture boot.", boot)
        for target in self.config.targets:
            self.assertNotIn(target.document_id, boot)
        self.assertIn("ROUTE: ../../BLUEPRINT.txt", boot)
        self.assertIn("ROUTE: edit.md", boot)
        self.assertIn("ROUTE: modules/check.md", boot)
        links = {
            run.get("link")
            for paragraph in updater.desired["boot"].native_projection["paragraphs"]
            for run in paragraph["runs"]
            if run.get("link")
        }
        expected_links = {
            GOOGLE_DOC_URL.format(document_id=target.document_id)
            for target in self.config.targets
        }
        self.assertTrue(expected_links.issubset(links))
        for desired in updater.desired.values():
            for target in self.config.targets:
                self.assertNotIn(target.document_id, desired.text)

    def test_current_matching_text_with_wrong_native_format_requires_new_edition(self) -> None:
        self._write_state("new_edition")
        backend = self._backend()
        updater = self._updater(backend)
        target = self.config.by_role["edit"]
        desired = updater.desired["edit"]
        backend._records[target.document_id]["text"] = desired.text
        backend._records[target.document_id]["native_projection"] = {
            "schema": "bkp-google-docs-native-projection-v2",
            "paragraphs": [
                {"named_style": "NORMAL_TEXT", "runs": [{"text": line}]}
                for line in desired.text.rstrip("\n").split("\n")
            ],
        }
        with self.assertRaisesRegex(
            UnityError, "current Unity content would change without a new edition"
        ):
            updater.full_plan()

    def test_google_apply_is_hard_disabled_even_with_acknowledgement(self) -> None:
        with self.assertRaisesRegex(UnityError, "disabled"):
            require_rendering_acknowledgement(
                "google", apply=True, acknowledged=False
            )
        with self.assertRaisesRegex(UnityError, "disabled"):
            require_rendering_acknowledgement(
                "google", apply=True, acknowledged=True
            )
        require_rendering_acknowledgement(
            "state", apply=True, acknowledged=False
        )

    def test_google_backend_writer_has_no_direct_bypass(self) -> None:
        backend = object.__new__(GoogleBackend)
        with self.assertRaisesRegex(UnityError, "writes are disabled"):
            backend.replace_document(
                "document-id",
                "text",
                expected_revision_id="revision",
                native_projection={"schema": "fixture", "paragraphs": []},
            )

    def test_stale_generated_source_is_refused_by_receipt(self) -> None:
        path = self.source_root / "DEPLOY/routed/modules/pr.md"
        path.write_text(path.read_text(encoding="utf-8") + "stale\n", encoding="utf-8")
        with self.assertRaisesRegex(UnityError, "hash mismatch"):
            UnityUpdater(self.config, self.source_root, None)

    def test_unexpected_registry_edition_is_refused(self) -> None:
        self._write("VERSION.txt", "another_edition")
        with self.assertRaisesRegex(UnityError, "locked expected edition"):
            UnityUpdater(self.config, self.source_root, None)

    def test_apply_writes_six_content_documents_then_boot(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        plan = updater.full_plan()
        actions = updater.apply(plan, plan.digest)
        expected = [
            self.config.by_role[role].document_id
            for role in self.config.publish_order
        ]
        self.assertEqual(backend.writes, expected)
        self.assertIn("written last and verified: Boot_bkp3-0", actions)
        final = updater.inspect()
        for role, observed in final.by_role.items():
            self.assertEqual(observed.text_sha256, updater.desired[role].text_sha256)

    def test_wrong_confirmation_writes_nothing(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        plan = updater.full_plan()
        with self.assertRaisesRegex(UnityError, "confirmation"):
            updater.apply(plan, "0" * 64)
        self.assertEqual(backend.writes, [])

    def test_duplicate_exact_title_is_refused(self) -> None:
        backend = self._backend()
        blueprint = self.config.by_role["blueprint"]
        duplicate = dict(backend._records[blueprint.document_id])
        duplicate["id"] = "duplicate-blueprint"
        backend._records[duplicate["id"]] = duplicate
        with self.assertRaisesRegex(UnityError, "duplicated"):
            self._updater(backend).full_plan()
        self.assertEqual(backend.writes, [])

    def test_renamed_target_is_refused(self) -> None:
        backend = self._backend()
        target = self.config.by_role["check"]
        backend._records[target.document_id]["name"] = "Check-renamed"
        with self.assertRaisesRegex(UnityError, "title mismatch"):
            self._updater(backend).full_plan()
        self.assertEqual(backend.writes, [])

    def test_recreated_target_with_same_title_is_refused(self) -> None:
        backend = self._backend()
        edit = self.config.by_role["edit"]
        recreated = dict(backend._records.pop(edit.document_id))
        recreated["id"] = "new-edit-id"
        backend._records[recreated["id"]] = recreated
        with self.assertRaisesRegex(UnityError, "configured document ID is missing"):
            self._updater(backend).full_plan()

    def test_wrong_hierarchy_is_refused(self) -> None:
        backend = self._backend()
        photo = self.config.by_role["photo"]
        backend._records[photo.document_id]["parents"] = [self.config.root_id]
        with self.assertRaisesRegex(UnityError, "parent mismatch"):
            self._updater(backend).full_plan()

    def test_directory_native_projection_reports_equivalence_but_updates_structure(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        target = self.config.by_role["directory"]
        source_lines = updater.desired["directory"].source_text.rstrip("\n").split("\n")
        body = "\n".join(line for line in source_lines if line != "")
        backend._records[target.document_id]["text"] = canonical_text(
            "BKP 3.0 UNITY\nROLE: DIRECTORY\nSOURCE EDITION: old_edition\n"
            f"STATUS: {self.config.status.upper()}\nUNITY SET: {updater.unity_set_digest}\n\n{body}\n"
        )
        plan = updater.full_plan()
        item = next(
            value for value in plan.payload["documents"]
            if value["role"] == "directory"
        )
        self.assertTrue(item["source_equivalent"])
        updater.apply(plan, plan.digest)
        self.assertIn(target.document_id, backend.writes)

    def test_directory_native_projection_preserves_indentation(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        target = self.config.by_role["directory"]
        source = updater.desired["directory"].source_text.replace(
            "  routes: []", " routes: []"
        )
        body = "\n".join(
            line for line in source.rstrip("\n").split("\n") if line != ""
        )
        backend._records[target.document_id]["text"] = canonical_text(
            "BKP 3.0 UNITY\nROLE: DIRECTORY\nSOURCE EDITION: old_edition\n"
            f"STATUS: {self.config.status.upper()}\nUNITY SET: {updater.unity_set_digest}\n\n{body}\n"
        )
        plan = updater.full_plan()
        item = next(
            value for value in plan.payload["documents"]
            if value["role"] == "directory"
        )
        self.assertFalse(item["source_equivalent"])

    def test_photo_projection_ignores_only_verified_codeblock_sentinels(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        target = self.config.by_role["photo"]
        lines = updater.desired["photo"].transport_text.rstrip("\n").split("\n")
        fence_positions = [
            index for index, value in enumerate(lines)
            if value.startswith("```")
        ]
        self.assertEqual(len(fence_positions), 2)
        opener, closer = GOOGLE_CODEBLOCK_SENTINELS
        first, second = fence_positions
        body_lines = (
            lines[:first]
            + [opener]
            + lines[first + 1:second]
            + [closer]
            + lines[second + 1:]
        )
        backend._records[target.document_id]["text"] = canonical_text(
            "BKP 3.0 UNITY\nROLE: PHOTO\nSOURCE EDITION: old_edition\n"
            f"STATUS: {self.config.status.upper()}\nUNITY SET: {updater.unity_set_digest}\n\n"
            + "\n".join(body_lines)
            + "\n"
        )
        plan = updater.full_plan()
        item = next(
            value for value in plan.payload["documents"]
            if value["role"] == "photo"
        )
        self.assertTrue(item["source_equivalent"])

        backend._records[target.document_id]["text"] = backend._records[
            target.document_id
        ]["text"].replace(opener, opener + " extra")
        with self.assertRaisesRegex(UnityError, "sentinel"):
            updater.full_plan()

    def test_review_snapshot_must_be_manually_approved_and_exact(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        plan = updater.full_plan()
        snapshot = review_snapshot_payload(plan)
        path = self.root / "review.json"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaisesRegex(UnityError, "not explicitly reviewed"):
            validate_reviewed_snapshot(path, plan, snapshot["snapshot_digest"])

        snapshot["approval"] = "REVIEWED"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        validate_reviewed_snapshot(path, plan, snapshot["snapshot_digest"])
        snapshot["documents"][0]["current_revision_id"] = "tampered"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaisesRegex(UnityError, "digest"):
            validate_reviewed_snapshot(path, plan, snapshot["snapshot_digest"])

    def test_backend_without_safe_renderer_cannot_apply(self) -> None:
        backend = self._backend()
        backend.supports_safe_apply = False
        updater = self._updater(backend)
        plan = updater.full_plan()
        with self.assertRaisesRegex(UnityError, "formatting-preserving"):
            updater.apply(plan, plan.digest)
        self.assertEqual(backend.writes, [])

    def test_content_failure_never_writes_boot(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        plan = updater.full_plan()
        boot_id = self.config.by_role["boot"].document_id
        original_boot = backend.read_document(boot_id)
        backend.fail_id = self.config.by_role["photo"].document_id
        with self.assertRaisesRegex(UnityError, "injected write failure"):
            updater.apply(plan, plan.digest)
        self.assertNotIn(boot_id, backend.writes)
        self.assertEqual(backend.read_document(boot_id), original_boot)

    def test_exact_partial_stage_can_resume_with_boot_last(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        blueprint = self.config.by_role["blueprint"]
        backend.replace_document(
            blueprint.document_id,
            updater.desired["blueprint"].text,
            expected_revision_id="r1",
            native_projection=updater.desired["blueprint"].native_projection,
        )
        backend.writes.clear()
        plan = updater.full_plan()
        updater.apply(plan, plan.digest)
        self.assertNotEqual(backend.writes[0], blueprint.document_id)
        self.assertEqual(backend.writes[-1], self.config.by_role["boot"].document_id)

    def test_current_set_refuses_same_edition_content_change(self) -> None:
        raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        raw["status"] = "current"
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        self.config = load_config(self.config_path)
        self._write_sources("same_edition")
        self._write_state("same_edition", status="current")
        backend = self._backend()
        with self.assertRaisesRegex(UnityError, "without a new edition"):
            self._updater(backend).full_plan()

    def test_final_failure_restores_old_boot(self) -> None:
        backend = self._backend()
        updater = self._updater(backend)
        plan = updater.full_plan()
        boot_id = self.config.by_role["boot"].document_id
        edit_id = self.config.by_role["edit"].document_id
        original_boot_text = backend.read_document(boot_id).text
        backend.tamper_after_id = boot_id
        backend.tamper_id = edit_id
        with self.assertRaisesRegex(UnityError, "Boot restored"):
            updater.apply(plan, plan.digest)
        self.assertEqual(backend.read_document(boot_id).text, original_boot_text)
        self.assertEqual(backend.writes[-1], boot_id)

    def test_build_unity_plan_exposes_native_projection_visible_text_and_distinct_hashes(self) -> None:
        import dataclasses
        import sys

        repo_root = CANDIDATE_ROOT.parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import app as console_app
        from unity_update import _projection_text

        plan_data = console_app.build_unity_plan(
            config_path=self.config_path,
            source_root=self.source_root,
        )
        updater = UnityUpdater(self.config, self.source_root, None)
        by_role = {doc["role"]: doc for doc in plan_data["documents"]}
        self.assertEqual(set(by_role), set(self.config.publish_order))

        for role, doc in by_role.items():
            desired = updater.desired[role]
            expected_visible = canonical_text(_projection_text(desired.native_projection))
            expected_wording = console_app.normalize_wording_text(expected_visible)
            self.assertEqual(doc["desired_visible_text"], expected_visible)
            self.assertEqual(
                doc["desired_visible_text_sha256"],
                sha256_text(expected_visible),
            )
            self.assertEqual(doc["desired_wording_text"], expected_wording)
            self.assertEqual(
                doc["desired_wording_sha256"],
                sha256_text(expected_wording),
            )
            self.assertNotIn("desired_text", doc)
            self.assertNotIn("desired_text_sha256", doc)
            self.assertEqual(doc["source_markdown_sha256"], desired.source_sha256)
            self.assertEqual(
                doc["desired_native_projection_sha256"],
                desired.native_projection_sha256,
            )
            self.assertEqual(
                doc["desired_format_link_sha256"],
                desired.format_link_sha256,
            )
            self.assertNotEqual(
                doc["source_markdown_sha256"],
                doc["desired_visible_text_sha256"],
            )
            self.assertNotEqual(
                doc["desired_native_projection_sha256"],
                doc["desired_visible_text_sha256"],
            )

        # Even if DesiredDocument.text held raw Markdown, visible_text_from_native_projection
        # derives solely from desired.native_projection.
        edit_desired = updater.desired["edit"]
        mutated_edit = dataclasses.replace(
            edit_desired,
            text="---\nname: edit\n---\n# Raw Markdown\n- **Bold** [link](https://example.test)\n",
            text_sha256=sha256_text("---\nname: edit\n---\n# Raw Markdown\n- **Bold** [link](https://example.test)\n"),
        )
        updater.desired["edit"] = mutated_edit
        eval_res = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {
                    "name": edit_desired.target.title,
                    "mimeType": GOOGLE_DOC_MIME,
                    "trashed": False,
                },
                "text": console_app.visible_text_from_native_projection(
                    edit_desired.native_projection
                ),
            },
        )
        self.assertEqual(eval_res["status_code"], "WORDING_MATCH")
        self.assertEqual(eval_res["status_label"], "Wording Match")
        self.assertEqual(eval_res["exact_text_status_code"], "EXACT_TEXT_MATCH")
        self.assertEqual(eval_res["exact_text_status_label"], "Exact Text/Paragraph Match")
        self.assertEqual(eval_res["diff"]["label"], "Exact Text/Paragraph Diff")
        self.assertEqual(eval_res["diff"]["added"], 0)
        self.assertEqual(eval_res["diff"]["removed"], 0)

    def test_markdown_to_native_formatting_changes_produce_visible_text_match_without_false_diff(self) -> None:
        import sys

        repo_root = CANDIDATE_ROOT.parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import app as console_app
        from unity_update import _projection_text

        updater = UnityUpdater(self.config, self.source_root, None)

        # Verify that Markdown syntax in source_text/transport_text was stripped/converted
        # in desired.native_projection visible text (headings, bullets, bold, code, links, fences).
        edit_visible = console_app.visible_text_from_native_projection(
            updater.desired["edit"].native_projection
        )
        self.assertNotIn("# EDIT", edit_visible)
        self.assertNotIn("**Bold**", edit_visible)
        self.assertNotIn("`code`", edit_visible)
        self.assertNotIn("[link](https://example.test)", edit_visible)
        self.assertNotIn("--- GENERATED AUTHORITY ---", edit_visible)
        self.assertIn("GENERATED AUTHORITY", edit_visible)
        self.assertIn("Bold and code; link.", edit_visible)

        photo_visible = console_app.visible_text_from_native_projection(
            updater.desired["photo"].native_projection
        )
        self.assertNotIn("```", photo_visible)
        self.assertIn("Photo return", photo_visible)

        # Simulate Google Drive plain-text export (including UTF-8 BOM and CRLF line endings)
        docs_payload = {}
        for role in self.config.publish_order:
            desired = updater.desired[role]
            exported_body = "\ufeff" + _projection_text(desired.native_projection).replace(
                "\n", "\r\n"
            )
            docs_payload[role] = {
                "accessible": True,
                "document_id": desired.target.document_id,
                "meta": {
                    "name": desired.target.title,
                    "mimeType": GOOGLE_DOC_MIME,
                    "trashed": False,
                },
                "text": exported_body,
            }

        audit = console_app.audit_drive_payload(
            {
                "root": {
                    "accessible": True,
                    "meta": {
                        "name": self.config.root_title,
                        "mimeType": GOOGLE_FOLDER_MIME,
                        "driveId": "shared-drive",
                        "trashed": False,
                    },
                },
                "hierarchy": {"folders": {"DEPLOY": "f1", "DEPLOY/routed": "f2"}},
                "documents": docs_payload,
            },
            config_path=self.config_path,
            source_root=self.source_root,
        )

        self.assertFalse(audit["native_structure_verified"])
        self.assertEqual(audit["summary"]["wording_matched_targets"], 7)
        self.assertEqual(audit["summary"]["exact_text_matched_targets"], 7)
        self.assertEqual(audit["summary"]["verified_targets"], 7)
        self.assertTrue(audit["summary"]["all_wording_matched"])

        for doc in audit["documents"]:
            self.assertEqual(doc["status_code"], "WORDING_MATCH", doc["role"])
            self.assertEqual(doc["status_label"], "Wording Match", doc["role"])
            self.assertEqual(doc["exact_text_status_code"], "EXACT_TEXT_MATCH", doc["role"])
            self.assertEqual(doc["diff"]["label"], "Exact Text/Paragraph Diff", doc["role"])
            self.assertEqual(doc["diff"]["added"], 0, doc["role"])
            self.assertEqual(doc["diff"]["removed"], 0, doc["role"])
            self.assertEqual(doc["diff"]["unified_lines"], [], doc["role"])
            self.assertFalse(doc["native_structure_verified"], doc["role"])
            self.assertFalse(doc["checks"]["native_projection_verified"], doc["role"])
            self.assertIsNone(doc["hashes"]["observed_native_projection_sha256"])
            self.assertEqual(
                doc["hashes"]["desired_wording_sha256"],
                doc["hashes"]["observed_wording_sha256"],
            )
            self.assertEqual(
                doc["hashes"]["desired_visible_text_sha256"],
                doc["hashes"]["observed_exported_visible_text_sha256"],
            )

    def test_extra_blank_paragraphs_do_not_cause_wording_diff(self) -> None:
        import sys

        repo_root = CANDIDATE_ROOT.parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import app as console_app

        updater = UnityUpdater(self.config, self.source_root, None)
        edit_desired = updater.desired["edit"]
        valid_visible = console_app.visible_text_from_native_projection(
            edit_desired.native_projection
        )
        # Insert extra blank paragraphs throughout the body (after the identity header)
        header_part, body_part = valid_visible.split("\n\n", 1)
        body_with_extra_blanks = "\n\n\n".join(body_part.split("\n"))
        exported_with_blanks = f"{header_part}\n\n\n\n{body_with_extra_blanks}\n\n\n"

        result = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {
                    "name": edit_desired.target.title,
                    "mimeType": GOOGLE_DOC_MIME,
                    "trashed": False,
                },
                "text": exported_with_blanks,
            },
        )
        # Primary editorial status MUST be Wording Match
        self.assertEqual(result["status_code"], "WORDING_MATCH")
        self.assertEqual(result["status_label"], "Wording Match")
        self.assertTrue(result["checks"]["wording_sha_match"])
        self.assertEqual(
            result["hashes"]["desired_wording_sha256"],
            result["hashes"]["observed_wording_sha256"],
        )
        # Secondary diagnostic records Exact Text/Paragraph Diff
        self.assertFalse(result["checks"]["exact_text_sha_match"])
        self.assertEqual(result["exact_text_status_code"], "EXACT_TEXT_DIFF")
        self.assertEqual(result["exact_text_status_label"], "Exact Text/Paragraph Diff")
        self.assertEqual(result["diff"]["label"], "Exact Text/Paragraph Diff")
        self.assertGreater(result["diff"]["added"], 0)

    def test_different_paragraph_boundaries_around_identical_wording_do_not_cause_wording_diff(self) -> None:
        import sys

        repo_root = CANDIDATE_ROOT.parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import app as console_app

        updater = UnityUpdater(self.config, self.source_root, None)
        edit_desired = updater.desired["edit"]
        valid_visible = console_app.visible_text_from_native_projection(
            edit_desired.native_projection
        )
        header_part, body_part = valid_visible.split("\n\n", 1)
        # Reflow body paragraphs: split words across lines AND merge lines with runs of whitespace
        words = body_part.split()
        reflowed_lines = [
            "   ".join(words[i:i + 2])
            for i in range(0, len(words), 2)
        ]
        exported_reflowed = f"{header_part}\n\n" + "\n\n".join(reflowed_lines) + "\n"

        result = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {
                    "name": edit_desired.target.title,
                    "mimeType": GOOGLE_DOC_MIME,
                    "trashed": False,
                },
                "text": exported_reflowed,
            },
        )
        self.assertEqual(result["status_code"], "WORDING_MATCH")
        self.assertEqual(result["status_label"], "Wording Match")
        self.assertTrue(result["checks"]["wording_sha_match"])
        self.assertEqual(
            result["hashes"]["desired_wording_sha256"],
            result["hashes"]["observed_wording_sha256"],
        )
        self.assertFalse(result["checks"]["exact_text_sha_match"])
        self.assertEqual(result["exact_text_status_code"], "EXACT_TEXT_DIFF")
        self.assertEqual(result["exact_text_status_label"], "Exact Text/Paragraph Diff")
        self.assertTrue(result["diff"]["unified_lines"])

    def test_changes_in_punctuation_spelling_case_numbers_or_words_cause_wording_diff(self) -> None:
        import sys

        repo_root = CANDIDATE_ROOT.parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import app as console_app

        updater = UnityUpdater(self.config, self.source_root, None)
        edit_desired = updater.desired["edit"]
        valid_visible = console_app.visible_text_from_native_projection(
            edit_desired.native_projection
        )
        mutations = {
            "punctuation_removed": valid_visible.replace("Bold and code; link.", "Bold and code link."),
            "punctuation_changed": valid_visible.replace("Bold and code; link.", "Bold and code: link!"),
            "spelling_changed": valid_visible.replace("Bold and code; link.", "Bould and code; link."),
            "case_changed": valid_visible.replace("Bold and code; link.", "bold and code; link."),
            "number_changed": valid_visible.replace("Bold and code; link.", "Bold 2 and code; link."),
            "word_changed": valid_visible.replace("Bold and code; link.", "Bold and script; link."),
        }
        for label, mutated_text in mutations.items():
            with self.subTest(mutation=label):
                self.assertNotEqual(mutated_text, valid_visible, label)
                result = console_app._evaluate_single_role(
                    updater,
                    "edit",
                    {
                        "accessible": True,
                        "document_id": edit_desired.target.document_id,
                        "meta": {
                            "name": edit_desired.target.title,
                            "mimeType": GOOGLE_DOC_MIME,
                            "trashed": False,
                        },
                        "text": mutated_text,
                    },
                )
                self.assertEqual(result["status_code"], "WORDING_DIFF", label)
                self.assertEqual(result["status_label"], "Wording Diff", label)
                self.assertFalse(result["checks"]["wording_sha_match"], label)
                self.assertNotEqual(
                    result["hashes"]["desired_wording_sha256"],
                    result["hashes"]["observed_wording_sha256"],
                    label,
                )

        # Also verify changing a digit in existing numbered text ([P1] -> [P2]) in photo role causes WORDING_DIFF
        photo_desired = updater.desired["photo"]
        photo_visible = console_app.visible_text_from_native_projection(
            photo_desired.native_projection
        )
        photo_digit_mutated = photo_visible.replace("[P1]", "[P9]", 1)
        self.assertNotEqual(photo_digit_mutated, photo_visible)
        photo_res = console_app._evaluate_single_role(
            updater,
            "photo",
            {
                "accessible": True,
                "document_id": photo_desired.target.document_id,
                "meta": {
                    "name": photo_desired.target.title,
                    "mimeType": GOOGLE_DOC_MIME,
                    "trashed": False,
                },
                "text": photo_digit_mutated,
            },
        )
        self.assertEqual(photo_res["status_code"], "WORDING_DIFF")
        self.assertEqual(photo_res["status_label"], "Wording Diff")
        self.assertFalse(photo_res["checks"]["wording_sha_match"])

    def test_browser_and_python_wording_normalisation_produce_identical_results(self) -> None:
        import re as _re
        import shutil
        import subprocess
        import sys

        repo_root = CANDIDATE_ROOT.parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import app as console_app

        html_path = repo_root / "static" / "index.html"
        html_text = html_path.read_text(encoding="utf-8")

        # Extract the exact JS regex and normalizeWordingText function from static/index.html
        re_match = _re.search(
            r"const\s+WORDING_WHITESPACE_RE\s*=\s*(/[^/]+/[a-z]*)\s*;",
            html_text,
        )
        fn_match = _re.search(
            r"(function\s+normalizeWordingText\s*\(rawText\)\s*\{.*?\n\s*\})",
            html_text,
            flags=_re.DOTALL,
        )
        self.assertIsNotNone(re_match, "WORDING_WHITESPACE_RE must exist in static/index.html")
        self.assertIsNotNone(fn_match, "normalizeWordingText must exist in static/index.html")
        js_regex_literal = re_match.group(1)
        self.assertEqual(
            js_regex_literal.strip("/"),
            console_app.WORDING_WHITESPACE_RE.pattern,
        )

        updater = UnityUpdater(self.config, self.source_root, None)
        samples = [
            "",
            "   \n\r\n\t  ",
            "\ufeffBKP 3.0 UNITY\r\nROLE: EDIT\n\n\nFirst\t\tparagraph.\n\nSecond\u00a0paragraph — 100% intact!",
            "Cafe\u0301 vs Café; 'quotes', \"double\", (parens), [brackets], 301026_gpt_bkp3-1.",
            "Line1\u2028Line2\u2029Line3\u2003WideSpace\u3000IdeographicSpace",
            *[
                console_app.visible_text_from_native_projection(
                    updater.desired[role].native_projection
                )
                for role in self.config.publish_order
            ],
        ]

        node_bin = shutil.which("node")
        self.assertIsNotNone(node_bin, "Node.js is required to verify browser JS parity")
        js_script = (
            f"const WORDING_WHITESPACE_RE = {js_regex_literal};\n"
            f"{fn_match.group(1)}\n"
            "const crypto = require('crypto');\n"
            "const inputs = JSON.parse(process.argv[1]);\n"
            "const out = inputs.map((s) => {\n"
            "  const norm = normalizeWordingText(s);\n"
            "  const sha = crypto.createHash('sha256').update(Buffer.from(norm, 'utf8')).digest('hex');\n"
            "  return { norm, sha };\n"
            "});\n"
            "process.stdout.write(JSON.stringify(out));\n"
        )
        proc = subprocess.run(
            [node_bin, "-e", js_script, json.dumps(samples)],
            capture_output=True,
            text=True,
            check=True,
        )
        js_results = json.loads(proc.stdout)
        self.assertEqual(len(js_results), len(samples))

        for sample, js_item in zip(samples, js_results):
            py_norm = console_app.normalize_wording_text(sample)
            py_sha = sha256_text(py_norm)
            self.assertEqual(js_item["norm"], py_norm)
            self.assertEqual(js_item["sha"], py_sha)

    def test_existing_identity_edition_unity_set_and_source_hash_checks_remain_enforced(self) -> None:
        import sys

        repo_root = CANDIDATE_ROOT.parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import app as console_app

        updater = UnityUpdater(self.config, self.source_root, None)
        edit_desired = updater.desired["edit"]
        valid_visible = console_app.visible_text_from_native_projection(
            edit_desired.native_projection
        )

        # 1. Tampered edition -> EDITION_DRIFT
        wrong_edition = valid_visible.replace(
            f"SOURCE EDITION: {updater.edition}",
            "SOURCE EDITION: 010125_old_edition",
            1,
        )
        res_edition = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {"name": edit_desired.target.title, "mimeType": GOOGLE_DOC_MIME, "trashed": False},
                "text": wrong_edition,
            },
        )
        self.assertEqual(res_edition["status_code"], "EDITION_DRIFT")
        self.assertFalse(res_edition["checks"]["edition_match"])

        # 2. Tampered role -> IDENTITY_ERROR
        wrong_role = valid_visible.replace("ROLE: EDIT", "ROLE: PHOTO", 1)
        res_role = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {"name": edit_desired.target.title, "mimeType": GOOGLE_DOC_MIME, "trashed": False},
                "text": wrong_role,
            },
        )
        self.assertEqual(res_role["status_code"], "IDENTITY_ERROR")
        self.assertFalse(res_role["checks"]["role_match"])

        # 3. Tampered UNITY SET digest -> IDENTITY_ERROR
        wrong_set = valid_visible.replace(
            f"UNITY SET: {updater.unity_set_digest}",
            f"UNITY SET: {'0' * 64}",
            1,
        )
        res_set = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {"name": edit_desired.target.title, "mimeType": GOOGLE_DOC_MIME, "trashed": False},
                "text": wrong_set,
            },
        )
        self.assertEqual(res_set["status_code"], "IDENTITY_ERROR")
        self.assertFalse(res_set["checks"]["unity_set_match"])

        # 4. Tampered SOURCE-SHA256 witness -> IDENTITY_ERROR
        wrong_src_sha = valid_visible.replace(
            f"SOURCE-SHA256: {edit_desired.source_sha256}",
            f"SOURCE-SHA256: {'f' * 64}",
            1,
        )
        res_src_sha = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {"name": edit_desired.target.title, "mimeType": GOOGLE_DOC_MIME, "trashed": False},
                "text": wrong_src_sha,
            },
        )
        self.assertEqual(res_src_sha["status_code"], "IDENTITY_ERROR")
        self.assertFalse(res_src_sha["checks"]["header_source_markdown_sha_match"])

        # 5. Missing BKP 3.0 UNITY header -> IDENTITY_ERROR
        missing_header = valid_visible.replace("BKP 3.0 UNITY\n", "", 1)
        res_missing = console_app._evaluate_single_role(
            updater,
            "edit",
            {
                "accessible": True,
                "document_id": edit_desired.target.document_id,
                "meta": {"name": edit_desired.target.title, "mimeType": GOOGLE_DOC_MIME, "trashed": False},
                "text": missing_header,
            },
        )
        self.assertEqual(res_missing["status_code"], "IDENTITY_ERROR")
        self.assertIsNotNone(res_missing["identity_error"])


if __name__ == "__main__":
    unittest.main()

