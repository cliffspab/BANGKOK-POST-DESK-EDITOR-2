# BKP Desk — start here

This page is the permanent handover point for the supervisor and the assistant.
A previous chat is optional context, not operational memory.

## Start

1. Open the project at `D:\Documents\BANGKOK POST DESK EDITOR`.
2. Read root `00_START-HERE.md` and `AGENTS.md`.
3. Establish current state from live files and checks; never assume an old chat
   is current.
4. Use `BLUEPRINT.txt` for complete editorial authority and `CONTROL.txt` for
   task routing.

The pinned Codex task is named **BKP Desk — Start Here**. If it is unavailable,
start a new task in the project: the root files supply the whole cold start.

Codex tasks are host-backed. To continue the pinned task away from home, pair
Codex Remote from the home desktop app's **Settings → Connections → Control
this PC** using the same account and workspace, and keep the host awake and
online. QR/device approval is a human-only step. An office computer does not
automatically receive the home host's local task or files; use this bootstrap
against an available project copy when the host cannot be reached.

For Claude, use the complete adjacent `CLAUDE.md` as the project's instruction
text and keep the root copy beside `AGENTS.md` in the live workspace.

## Live-state proof

Before reporting readiness, read `VERSION.txt` and
`pipeline-registry\COMMITS-PENDING.md`, inspect the registry working tree, and
run `python shift.py --check`. Run root `python build.py` when build validation
is relevant. Report the edition, pending payload, working-tree state and any
failed check.

Shift is the sealed eight-file `_sync`-named handover mirrored by rclone to
`pCloud:Public Folder/BKP Shift`; Google Docs are optional manual reading copies.

Do not publish, push, seal, refresh Shift or pCloud, move or delete material,
change edition identity, or widen a requested change without supervisor
authority.
