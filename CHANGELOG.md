# Changelog

User-facing update map for the Blueprint beta and its delivered skills. It lets
a user update only the affected documents instead of comparing or replacing the
whole set. Planned work stays under **Unreleased** and moves into its own
versioned entry after a confirmed push and successful validation.

Each released entry names the version, date, affected deliveries and required
user action. This is a change summary, not editorial authority or a substitute
for `VERSION_HISTORY.md`, `COMMITS-PENDING.md` or the detailed shared workplan.

## Unreleased

Nothing pending.

## 301026_gpt_bkp3-1 — 2026-10-30

**Changed instructions:** `boot`, `blueprint`, `edit`, `check`, `photo` and
`pr`. Directory content is unchanged apart from the edition witness.

**Affected install bundles:** all five static skill archives and every routed
delivery.

**User action after publication:** reinstall any installed skill package. The
archive names remain `boot.zip`, `edit.zip`, `check.zip`, `photo.zip` and
`pr.zip`. Permanent native-document IDs and unique `*_bkp3-0` titles remain
unchanged.

#### Changed

- Adopted the supervisor-supplied BKP 3.1 compact source and its reorganised
  Boot, Edit, Check, Photo and PR instructions.
- Made the hard Edit dependency and soft Directory/Addendum fallbacks explicit
  in Boot.
- Consolidated setup, desk workflow, verification and return handling while
  preserving the generated single-source deployment architecture.
- Replaced the former empty `CLEARED:` terminator with `OUTSTANDING` as the
  final Job Report line, as specified by the supplied 3.1 source.
- Preserved static upload filenames and permanent Unity document names; only
  edition witnesses, content and guarded hashes advance.

#### Validation

- Release build and byte-for-byte rebuild check pass: 14 deployment files and
  five deterministic upload archives.
- Every supplied archive matches the supplied Blueprint components exactly.
- Unity transport selectors were adjusted for the compact wording; its 34
  updater tests pass.
- GitHub validation passed at `bfb83cc`. All seven permanent native documents
  were then updated in place, content first and Boot last; final readback
  confirms the 3.1 edition, expected source hash and `CURRENT` status in each.

## 271026_gpt_bkp3-0 — 2026-10-27

**Changed instructions:** all seven Unity volumes: `boot`, `blueprint`, `edit`,
`check`, `photo`, `pr` and `directory`.

**Affected install bundles:** all five skill archives and every routed delivery.

**User action:** reinstall any installed skill package. For human use, open the
permanent `BKP 3.0 Live` Drive folder or the refreshed Click Index; existing
Google Docs links and IDs remain unchanged.

### Changed

- Adopted the audited BKP 3.0 wording and current deployment vocabulary.
- Removed the repeated `CHECKING & PR / P4 / P5 / CHECKING [P4]` presentation.
- Kept the Directory return section last so the authority is read before return
  handling begins.
- Added the concise human-facing P5 while retaining full PR closure in the PR
  skill.
- Rebuilt the human Word/PDF volume as `Blueprint_bkp3-0` and regenerated all
  text, routed and skill deliveries from the single source.
- Installed guarded seven-document Unity update machinery and promoted the
  permanent Drive set from Candidate to Live, content first and Boot last.

### Validation

- Reproducible release build and all source guards passed.
- The 22-page Word/PDF render was visually inspected; links and bookmarks were
  checked and the DOCX sanitizer passed.
- Unity updater tests passed (34 tests); all permanent document IDs were
  preserved and Boot now witnesses `271026_gpt_bkp3-0` as `CURRENT`.
- Registry push and Click Index deployment are recorded when publication
  completes.

## 231026_gpt_return-qc-addendum — 2026-10-23

**Changed instructions:** `boot`, `edit` and `check`.

**Affected install bundles:** all five archives, because `boot`, `check`,
`photo` and `pr` deliberately bundle the shared `edit` companion. Package
indexes and receipts will also be regenerated mechanically.

**User action:** reinstall any of the five skills currently in
use. Users maintaining loose routed files need replace only `BOOT.md`,
`edit.md`, `modules/check.md` and the regenerated indexes.

### Added

- Shared `WORKPLAN.md` for current plans, candidate status, open decisions and
  publication discipline.
- Added `QC` command under Check for reviewing another operator's Job Report,
  listing required factual and Bangkok Post style changes, and returning
  `Clear to initial.` when no changes are required.
- Added `ORIGINAL FILING` record for domestic news-desk jobs, reproducing the
  exact filing unmarked and unfenced after the Style Log.
- Added a standing Cabinet section to the Desk Addendum, dated 23 October 2026
  and verified against the current Royal Thai Government register and the
  March 30 Royal Command, as the sole maintained Cabinet roster.

### Changed

- Added the universal copy-box rule: edited, held and replacement copy returned
  to chat is fenced; a single `HOLD:` or `Query:` line sits directly above it.
- Set mode lifetime to one assistant turn, with no carry-over unless the
  supervisor invokes the mode again.
- Added direct Boot discovery of the Desk Addendum and explicit Edit routing
  to its Cabinet section; the roster is not duplicated in Directory or skill
  bundles.
- Deprecated `Shift/` as a handover route and retained it empty as a reusable
  named space while skills become the active delivery direction.

### Removed

- Removed stray duplicate Directory files from `Blueprint/DEPLOY/skills/`.
- Cleared the former Shift handover payload and two stray Obsidian directories
  from `Shift/`; nothing unique lived there under the former contract.

### Validation

- Published commit `fc0afa4`; GitHub **Validate Blueprint beta** completed
  successfully, and a cache-busted raw fetch returned the new Boot edition.

## 171026d_gpt_single-source-candidate — 2026-10-20

**Changed instructions:** `boot` and `edit`. Generated package indexes, all
skill archives and integrity receipts changed as mechanical consequences.

**User action:** replace the linked routed package or reinstall any skill whose
bundle carries Boot or the shared Edit companion. Loose routed deployments need
replace `BOOT.md`, `edit.md` and the regenerated indexes.

### Changed

- Hardened linked Boot discovery: `BOOT.md` now explicitly resolves its sibling
  index and indexed paths, and loads `edit.md` plus the Directory in the same
  turn.
- Aligned routed and skill Directory locations and rebuilt deployment indexes,
  skill archives and integrity receipts.
- Updated the guarded push for beta publication: validate the single-source
  Blueprint, fail closed on unsupported Control changes, verify GitHub, and
  leave sealing, Shift and pCloud paused.

### Validation

- Published commit `5639cbe`; GitHub **Validate Blueprint beta** completed
  successfully.
