---

name: boot

description: Entry point and router for the Bangkok Post desk modules and resources.

---
<!-- 301026_gpt_bkp3-1 -->

***

## QUICKSTART — `boot.md`

Package router. Resolves paths, mounts core dependencies and dispatches the active mode. Carries no editorial rules or real-world facts.

**1. Mount sequence** (provider-, account-, path- and version-agnostic):
- **Index:** From a link or folder, resolve sibling `INDEX.yaml` relative to `boot.md`, then resolve all indexed paths relative to `INDEX.yaml`. In a skill deployment, use only the bundled skill files.
- **Hard dependency:** Load `edit.md` before accepting or acting on any job. If unreachable, halt and request it from the supervisor.
- **Soft dependencies:** Load `DIRECTORY.txt` (from DEPLOY root or `references/DIRECTORY.txt`) and live [`addendum.doc`](https://docs.google.com/document/d/1KukKHnoSOAuZiyg_u1k1NiRAQDx4QbuePCVxz4ehXsk/export?format=txt). If either is unreachable, `edit.md` ([S], [G1-A]) governs fallback.

**2. Dispatch** (read job first; supervisor instruction controls; no acknowledgement turn or narration; modes last one turn and reset to EDIT):
- **EDIT (default / bare slug / fit):** Load edit → [R1] return (fit jobs apply [G1-C1] and [P1]).
- **CHECK / QC:** Load edit + check → check scope and return (QC reviews a Job Report).
- **PHOTO:** Load edit + photo → photo method and return.
- **PR:** Load edit + pr → pr scope and return.

***
