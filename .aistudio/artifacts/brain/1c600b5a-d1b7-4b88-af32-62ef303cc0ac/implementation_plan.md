# Google Drive Unity Inspector & Live Blueprint Diffing

Integrate read-only Google Drive inspection into the **Bangkok Post Desk Editor** console so supervisors and custodians can sign in with Google, audit the live `BKP 3.0 Live` Shared Drive hierarchy and all seven permanent Unity Google Docs (`Blueprint_bkp3-0`, `Edit_bkp3-0`, `Check_bkp3-0`, `Photo_bkp3-0`, `PR_bkp3-0`, `Directory_bkp3-0`, `Boot_bkp3-0`), verify identity envelopes (`ROLE`, `SOURCE EDITION`, `STATUS`, `UNITY SET`), and run side-by-side diffs against the local `301026_gpt_bkp3-1` Blueprint sources.

## User Review & Critical Decisions

> [!IMPORTANT]
> Review the confirmed scope and architectural choices below before we proceed to implementation.

- **Confirmed Workflow Scope**: Read-only inspection and live auditing of the `BKP 3.0 Live` Unity folder (`17KYiUX-VvCY5LWOKnENKoolGgRHT-bR6`) and the seven permanent Unity Google Docs (`*_bkp3-0`).
- **Confirmed Access Posture**: Strictly read-only inspection and live diffing against local Blueprint sources—no writes, moves, or mutations will be performed on Google Drive.
- **Confirmed Interface Layout**: A dedicated **Google Drive Audit** tab for deep folder hierarchy validation, document identity inspection, and side-by-side diffing, paired with live Drive synchronization status indicators directly inside the existing **Unity 3.x Plan** tab.

---

## 1. Overview & Core Concept

- **What It Does**: Connects the local Bangkok Post Desk Editor console to Google Drive using client-side Firebase Google OAuth (`Sign in with Google`), fetches live metadata, hierarchy parent chains, and exported plain-text bodies for the seven protected Unity documents, and compares them against the locally compiled `301026_gpt_bkp3-1` Unity projection.
- **Target Audience / Persona**: Bangkok Post Desk supervisors and repository custodians verifying that the live Google Drive `BKP 3.0 Live` deployment matches the sealed repository edition and build receipt without risking unintended writes.
- **Key Value**: Eliminates manual document-by-document readback checks by automating identity header verification (`BKP 3.0 UNITY`, `ROLE`, `SOURCE EDITION`, `STATUS`, `UNITY SET`, `SOURCE-SHA256`), parent folder hierarchy checks (`.`, `DEPLOY`, `DEPLOY/routed`, `DEPLOY/routed/modules`), and line-level diff inspection in a single read-only workbench.

---

## 2. User Experience & Visual Design

- **Key User Flows**:
  1. **Authentication Flow**: In the top bar or the Google Drive Audit tab, the user clicks the official **Sign in with Google** button. Firebase Auth opens a Google OAuth popup requesting the configured Drive scopes and caches the OAuth access token strictly in memory.
  2. **Live Unity 3.x Status Strip**: Once authenticated, the **Unity 3.x Plan** table automatically enriches each of the seven permanent targets (ordered content-first with `Boot_bkp3-0` last) with live Drive status text (`Exact Match`, `Edition Drift`, `Content Diff`, or `Unreachable`), observed Drive edition, last modified timestamp, and a direct link to open the Google Doc or inspect its diff.
  3. **Dedicated Google Drive Audit Tab**:
     - **Hierarchy & Envelope Summary**: Displays verification status for the `BKP 3.0 Live` root folder (`17KYiUX-VvCY5LWOKnENKoolGgRHT-bR6`), Shared Drive membership, and the portable folder tree (`.`, `DEPLOY`, `DEPLOY/routed`, `DEPLOY/routed/modules`).
     - **Seven-Target Audit Table**: Lists all seven permanent documents with their observed title, parent path verification, parsed `SOURCE EDITION`, `UNITY SET` digest match, `SOURCE-SHA256` match, last modifier, and revision metadata.
     - **Interactive Side-by-Side / Unified Diff Inspector**: Selecting any of the seven documents opens a live comparison between the **Observed Google Drive Document** (exported text and parsed identity header) and the **Desired Local Blueprint Projection** (`301026_gpt_bkp3-1`), highlighting any line additions, removals, or transport differences.
- **Visual Identity & Theme**:
  - *Aesthetic Direction*: Authoritative broadsheet-meets-engineering console matching the existing Bangkok Post Desk Editor aesthetic—clean warm paper surfaces, crisp hairline dividers, and zero decorative clutter.
  - *Color Palette & Mood*: Warm editorial paper canvas (`#f6f4ef`), crisp white structural cards (`#ffffff`), muted stone secondary surfaces (`#f0ede4`), deep navy primary interactive accents (`#1b3b6f`), and semantic text-paired status indicators (forest green `#2e7d32` for verified match, amber `#b45309` for edition/projection notice, crimson `#c62828` for guard mismatch).
  - *Typography & Hierarchy*: Editorial serif display headings paired with clean sans-serif UI controls and strict tabular monospace (`tabular-nums`) for SHA-256 digests, document IDs, byte counts, and line-by-line diffs.
  - *Component Styling & Layout*: Full-width 1400px desktop container, single-elevation bordered surfaces (`1px solid #d8d3c5`), unboxed inline metadata separated by middots (`·`), and single-line navigation controls.
- **Interactive Feedback & Motion**:
  - Immediate skeleton/loading states while querying the Drive API across the 7 targets, clear permission/access guidance if the signed-in Google account does not have access to the `BKP 3.0 Live` Shared Drive, plus a custom Drive Folder/Doc Inspector lookup bar to inspect any other accessible Drive folder or Google Doc by ID or search query in read-only mode.

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1: In-Memory Client OAuth Token + Server-Assisted Unity Diff Engine**
  - *Chosen Approach*: Authenticate in the browser using the Firebase JS SDK (`signInWithPopup` and `GoogleAuthProvider` with all configured Drive scopes), store the access token exclusively in memory, fetch Drive file metadata and exported document text (`text/plain`), and pass the observed payload to a local read-only Python verification endpoint that runs `parse_identity`, normalization (`paragraph-lf-nfc-v1`, `nonblank-lines-lf-nfc-v1`, code-block sentinel checks), and `difflib` unified diffing against `UnityUpdater.desired`.
  - *Why*: Avoids server-side OAuth redirect URI issues in ephemeral preview environments while leveraging the exact Python normalization and identity parsing rules already defined in `unity_update.py`.
  - *Alternatives Considered*: Pure client-side string comparison was rejected because `unity_update.py` implements specialized NFC/LF normalization, code-block sentinel handling (`U+EC03`/`U+EC02`), and non-blank YAML line projections for `Photo_bkp3-0` and `Directory_bkp3-0`.
- **Decision 2: Strict Read-Only Enforcement & Fallback Drive Explorer**
  - *Chosen Approach*: Only issue `GET` requests (`files.get`, `files.list`, `files.export`) to `https://www.googleapis.com/drive/v3`. In addition to the pre-configured `BKP 3.0 Live` targets, include a read-only **Drive File & Folder Lookup** drawer so if the user is testing with an account that stores working copies in another Drive folder, they can search or select any Google Doc in their Drive and diff it against any of the 7 local Blueprint roles.
  - *Why*: Guarantees zero risk of mutating production documents while ensuring the tool remains 100% functional and testable regardless of which Google account or Drive folder the operator signs in with.

---

## 4. Technical Architecture & Data Strategy *(Technical Reference)*

- **Architecture & Component Diagram**:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Browser Client (Desk Editor Console)                     │
│                                                                              │
│  ┌────────────────────────────┐      ┌────────────────────────────────────┐  │
│  │ Firebase Google OAuth      │      │ Top Bar & Auth Status              │  │
│  │ - In-memory accessToken    │─────▶│ - Official Sign in with Google     │  │
│  │ - All 13 Drive OAuth Scopes│      │ - Active user email & Sign out     │  │
│  └─────────────┬──────────────┘      └────────────────────────────────────┘  │
│                │                                                             │
│                ▼                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ Google Drive REST Client (Read-Only GET Calls)                         │  │
│  │ - GET /drive/v3/files/{id}?supportsAllDrives=true                      │  │
│  │ - GET /drive/v3/files?q=...&supportsAllDrives=true                     │  │
│  │ - GET /drive/v3/files/{id}/export?mimeType=text/plain                  │  │
│  └─────────────┬──────────────────────────────────────┬───────────────────┘  │
│                │                                      │                      │
│                ▼                                      ▼                      │
│  ┌───────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │ Unity 3.x Plan Tab                │  │ Google Drive Audit Tab          │  │
│  │ - Live Drive Sync Status column   │  │ - BKP 3.0 Live Hierarchy Audit  │  │
│  │ - Observed Edition & Match state  │  │ - 7-Target Identity & Hash Grid │  │
│  │ - Quick "Inspect Diff" trigger    │  │ - Side-by-Side / Unified Diff   │  │
│  └───────────────────────────────────┘  │ - Custom Drive Doc Diff Picker  │  │
│                                         └──────────────┬──────────────────┘  │
└────────────────────────────────────────────────────────┼─────────────────────┘
                                                         │ POST /api/unity/diff
                                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Python Backend Server (Port 3000)                        │
│                                                                              │
│  ┌────────────────────────────────────┐  ┌────────────────────────────────┐  │
│  │ GET /api/firebase-config           │  │ POST /api/unity/audit-drive    │  │
│  │ - Serves firebase-applet-config    │  │ - Runs unity_update.py         │  │
│  │   and configured Drive scopes      │  │   parse_identity & projections │  │
│  └────────────────────────────────────┘  │ - Generates unified line diffs │  │
│                                          │   against local 301026_gpt_bkp │  │
│                                          └────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Data Model & State**:
  - `authState`: `{ user: { displayName, email, photoURL } | null, accessToken: string | null, isSigningIn: boolean }` (held strictly in memory; cleared on sign-out via `onAuthStateChanged`).
  - `driveAuditState`: `{ rootStatus, folderHierarchyStatus, targetsByRole: Record<Role, ObservedDriveAudit>, lastCheckedAt }`.
  - `ObservedDriveAudit`: `{ role, documentId, title, accessible, meta, parsedIdentity, editionMatch, textMatch, sourceProjectionMatch, unifiedDiffLines, diffStats }`.
- **Interactive Component & State Mapping**:
  - **Sign in with Google / Sign Out Button**: Invokes `signInWithPopup` with all configured Drive scopes; upon authentication, triggers `runLiveDriveAudit()` to populate both the **Unity 3.x Plan** badges and the **Google Drive Audit** tab.
  - **Audit BKP 3.0 Live Button**: Queries the `BKP 3.0 Live` root folder and the 7 permanent document IDs concurrently, posts observed texts and metadata to `/api/unity/audit-drive`, and updates the 7-row audit table and Unity status column.
  - **Target Row Selection / Diff Modal**: Clicking any of the 7 roles (or selecting any Drive Google Doc from the fallback search list) displays the parsed `BKP 3.0 UNITY` header fields alongside a line-numbered diff against the local desired projection, with filter toggles (`All Lines` vs. `Changed Blocks Only`).
