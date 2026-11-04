# RECORDS & CONSOLIDATION

`100826_all_retiring-a-category`

Repository administration for the pipeline-registry clone. Extracted from BLUEPRINT on 24 July 2026: these procedures govern how ruled changes reach the registry, not how copy is edited. Not part of the published volume.

---

## Corpus and deployment subset

The operating corpus has two peer governance sources. `BLUEPRINT.txt` governs editorial work. `CONTROL.txt` governs command invocation, workflow selection and routing into the complete Blueprint. CONTROL does not duplicate or reduce the editorial rules.

BLUEPRINT is delivered whole or as three generated parts: `GUIDE.txt` carries EDITING in Markdown; `PROCESSES.txt` carries the task methods in Markdown; `DIRECTORY.yaml` carries STATUS and REFERENCES in YAML. `DIRECTORY.txt` is a byte-identical text-extension twin. CONTROL generates the four active command workflows under `Control/plugin/`: `/edit`, `/check`, `/photo` and `/pr`.

The corpus is everything the desk holds. The deployment subset is what a processor receives to work a shift. A file is corpus by being held; it enters the subset by being needed at the point of work.

**Corpus whole**

* **Peer sources** — `BLUEPRINT.txt` and `CONTROL.txt`; the only governance files edited.
* **Derived governance** — `GUIDE.txt`, `PROCESSES.txt`, `DIRECTORY.yaml`, `DIRECTORY.txt`, and `Control/plugin/`.
* **Artifacts of record** — `BLUEPRINT.docx`, PDF and manifest outputs.
* **Administration** — this file, `VERSION_HISTORY.md`, `COMMITS-PENDING.md`, `DECISIONS-OPEN.yaml`, and dated handoffs.
* **Machinery** — the Blueprint and CONTROL builders, CI workflow, `tools/`, `prompts/`, `config/` and `index`.

**Deployment subset** — the current editorial guidance plus CONTROL or the required generated command workflow. Where a destination takes one editorial file, use `BLUEPRINT.txt`; where it takes split delivery, use `GUIDE.txt`, `PROCESSES.txt` and `DIRECTORY.yaml`. CONTROL supplies the steering layer in either case.

The GitHub registry and sealed Drive master are peer official publication surfaces. A processor uses the supplied edition. If that copy cannot be read, another official copy may be used when its edition can be identified; otherwise the supervisor is asked for the current text. Edition selection and source custody remain the supervisor's responsibility.

---

Pending source or machinery changes are recorded in this file set on the turn they are made.

They must be:

* recoverable in an emergency handoff; and
* scannable against the active sources afterwards to confirm the work landed.

Operator-approved changes to BLUEPRINT or CONTROL are written into the matching local source and clone source on the turn they are ruled, then logged one line each in `COMMITS-PENDING.md` at the clone root. Generated BLUEPRINT parts and `Control/plugin/` are rebuilt from their respective sources and never hand-edited. The operator checks the pending list before every push. Lines clear on push. The desk never touches the clone without a ruling. (Op-ruled 2026-07-04; extended to the peer CONTROL source 2026-09-03.)

Full drop-in drafts of other changed documents are produced once, at shift close or on request, not turn by turn.

Between shifts, candidate rule changes, amendments and refinements collect in `DECISIONS-OPEN.yaml` — one file, keyed to the standing series (LEN/NAM/ARC/OUT/VER/STA/OTH), swept by the operator periodically. Nothing there is authoritative until ruled.

### Retiring a category

When a group or heading is retired, its members are re-argued from scratch or they go. They do not migrate to another branch by default. **A category going extinct is evidence about the category, not about its contents** — salvage is not merit, and the fact that an entry needs a new home is not an argument that it deserves one. This holds even where a sound fact is available for the entry: a good fact establishes that a claim is true, not that the Directory should carry it.

Two questions decide it, in order. Would this entry be written today if it did not already exist? If not, it goes. If yes, which branch does it argue its own way into?

Inherited material is the common case and gets no allowance for being inherited. An entry that predates the desk's custody, has drawn no feedback across it, and supports no durable fact is cut rather than carried. The cut is logged like any other change — a deletion sweep takes a `VERSION_HISTORY.md` entry.

(Op-ruled 2026-08-10, on the removal of Cristina Kirchner: struck from `references/foreign_people/shortened_names` when that group was retired, briefly promoted to `status/global`, then cut outright once the promotion route was recognised as salvage.)

At close:

* hand back patches rather than full reprints. `BLUEPRINT`, `GUIDE`, `DIRECTORY` and `CONTROL` are source or delivery documents, not chat-sized reprints.
