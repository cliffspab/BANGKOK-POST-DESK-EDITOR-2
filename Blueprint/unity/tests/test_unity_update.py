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


if __name__ == "__main__":
    unittest.main()
