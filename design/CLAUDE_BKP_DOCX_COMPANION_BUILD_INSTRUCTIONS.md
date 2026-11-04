# Claude hand-off: build the BKP Word companions

## Purpose

Use these instructions whenever any constituent Bangkok Post governance module
is updated. Every Markdown change must produce:

1. a newly generated Word companion for each changed module; and
2. a newly generated complete Word edition compiled from all four modules.

The Word files are build artifacts. Markdown remains the sole content authority.
Never repair wording in Word, and never allow a Word-only change to become
canonical.

## Governing modules

The four modules, in fixed compilation order, are:

1. `CORE.md`
2. `PROCESSES.md`
3. `STATUS.md`
4. `REFERENCES.md`

The current six-file hand-off pack is:

```text
handoff/BKP_GEMINI_DEPLOYMENT_SET/
    COMPILED.md
    COMPILED.docx
    CORE.md
    PROCESSES.md
    STATUS.md
    REFERENCES.md
```

The deployed or synchronised copies may live elsewhere. Resolve their actual
paths before building; do not silently substitute archived, near-live or
historical versions.

## Required outputs

For a change to any module, generate:

```text
The Bangkok Post Blueprint 2026 — Core.docx
The Bangkok Post Blueprint 2026 — Processes.docx
The Bangkok Post Blueprint 2026 — Status.docx
The Bangkok Post Blueprint 2026 — References.docx
The Bangkok Post Blueprint 2026.docx
```

Only the changed module companions must be replaced on an incremental build,
but the complete `The Bangkok Post Blueprint 2026.docx` must always be rebuilt
from all four current Markdown modules.

Do not rename, overwrite or promote deployed source files unless the operator
has explicitly approved that action.

## Existing design implementation

Do not recreate the styling from memory. Reuse these files:

```text
tools/bkp_docx_design.py
tools/build_bkp_compendium.py
tools/audit_bkp_compendium.py
design/BKP_MARKDOWN_TO_WORD_SPEC.md
compare/BKP_conversion_design_proof.docx
compare/the_bangkok_post_blueprint_compendium_final.docx
```

Their roles are:

- `bkp_docx_design.py` — reusable Word/OOXML design primitives.
- `build_bkp_compendium.py` — authoritative production converter.
- `audit_bkp_compendium.py` — Markdown-to-DOCX content-coverage audit.
- `BKP_MARKDOWN_TO_WORD_SPEC.md` — semantic conversion specification.
- `BKP_conversion_design_proof.docx` — approved visual proof.
- `the_bangkok_post_blueprint_compendium_final.docx` — retained Word
  foundation and secondary visual reference.

The severe black-and-white styling is intentional. Do not soften it into a
generic corporate report.

## Non-negotiable visual language

Preserve all of the following:

- Arial Black for monumental titles and the principal heading ladder.
- Arial for body copy.
- Black, white and neutral grey only.
- The institutional register with:
  - a narrow black numeral column;
  - white numerals;
  - a wider descriptive column;
  - alternating white and pale-grey rows;
  - deliberate black rules and fixed geometry.
- The four-part active register:
  `01 CORE / 02 PROCESSES / 03 STATUS / 04 REFERENCES`.
- A black active component cell and restrained inactive cells.
- Ruled section headings.
- AXIOM bars where the deterministic source rule applies.
- Native Word lists, hyperlinks, tables, headers, footers and page-number
  fields.
- Fixed-width bordered panels for page-ready, search and log material.
- Repeating table headers and fixed column geometry.
- Continuous folios in the complete edition.

Forbidden substitutions:

- no blue headings;
- no coloured corporate theme;
- no manually typed bullets or page numbers;
- no tables used merely to fake ordinary paragraphs;
- no screenshots of text in place of selectable Word text;
- no hand-formatting after generation;
- no changes to content merely to improve pagination.

## Deterministic Markdown mapping

Apply the existing mapping exactly:

| Markdown role | Word result |
|---|---|
| Document title and metadata | Severe cover and source metadata |
| `# PART: NAME` | Component opening, active register and Word section |
| Redundant component `#` after `PART:` | Fold into the part opening |
| `##` | Ruled major section |
| `###` | Compact operational subsection |
| `####` | Fine division |
| Qualified short doctrine after `###` | AXIOM treatment |
| Paragraph | Native body paragraph |
| Ordered/unordered list | Native Word numbering |
| Fenced code | Fixed-width bordered panel |
| Markdown table | Fixed-width native Word table |
| Horizontal rule | Native paragraph rule |

The equal-sign lines around `PART:` markers are compilation syntax and must not
print as literal content.

## Build sequence

### 1. Resolve and validate inputs

- Confirm all four current module paths.
- Confirm there are exactly four modules.
- Confirm their order is CORE, PROCESSES, STATUS, REFERENCES.
- Reject empty files, duplicate component headings or accidental archive input.
- Preserve UTF-8 text, punctuation, links, code fences, list order and tables.

### 2. Rebuild `COMPILED.md`

Compile the four modules mechanically using the established wrapper:

```markdown
# BKP PIPELINE — COMPILED GOVERNANCE SET

[build metadata]

============================================================
# PART: CORE
============================================================

[verbatim CORE.md]
```

Repeat the `PART:` wrapper for PROCESSES, STATUS and REFERENCES.

The module payloads must be inserted verbatim. The compiler may add only the
standard cover metadata and part wrappers.

Run a reconstruction or hash-based comparison proving that no constituent text
was lost, duplicated or reordered.

### 3. Build the complete Word edition

Use the packaged Python runtime and Pandoc. The established command shape is:

```powershell
& $python tools/build_bkp_compendium.py `
  --source path/to/COMPILED.md `
  --reference compare/the_bangkok_post_blueprint_compendium_final.docx `
  --output "path/to/The Bangkok Post Blueprint 2026.docx"
```

Pandoc is a parser only. `python-docx` and the existing OOXML helpers construct
the Word file.

### 4. Build each changed component companion

Do not hand-format a component file.

Use the same converter and design primitives in component scope:

- retain the severe cover;
- show the complete four-part register;
- activate only the component being built;
- include only that module’s content after its part opening;
- retain the same styles, lists, code panels, tables, headers and footer logic;
- title the output with the component suffix shown under **Required outputs**.

If `build_bkp_compendium.py` does not yet expose component scope, add a thin,
backwards-compatible `--component CORE|PROCESSES|STATUS|REFERENCES` option.
The default, with no `--component`, must remain the full compiled build.

Component scope must select content; it must not create a second styling
implementation.

## Required audits

Every generated Word file must pass all applicable checks.

### Content

- Every meaningful Markdown unit appears in the DOCX.
- No unrecognised source unit is silently dropped.
- Quotations, names, figures, links and code are unchanged.
- Lists retain item order and nesting.
- Tables retain all rows and cells.
- The complete edition contains all four modules in the fixed order.

For the complete edition, run:

```powershell
& $python tools/audit_bkp_compendium.py `
  --source path/to/COMPILED.md `
  --docx "path/to/The Bangkok Post Blueprint 2026.docx"
```

The build fails unless the audit reports:

```json
{"missing_units": [], "pass": true}
```

Extend the same coverage audit to component inputs when component companions are
built.

### Structure

Verify:

- real Word headings;
- real numbering definitions;
- fixed page geometry;
- fixed table geometry;
- repeating table headers;
- active register matches the component;
- headers and footers are not accidentally linked across incompatible sections;
- page-number fields are present;
- no unexplained blank pages;
- no fake headings, bullets or rules.

### Accessibility

Run the packaged DOCX accessibility audit. The release target is:

```text
high: 0
medium: 0
```

Every image must have useful alternative text.

### Visual rendering

Microsoft Word on Windows is the authoritative renderer for this design.

For every final output:

1. update fields;
2. repaginate in Word;
3. save the updated DOCX;
4. export a QA PDF;
5. render every PDF page to PNG;
6. inspect every page at full readable size.

Reject the build for:

- clipping or overlapping text;
- missing glyphs;
- detached headings;
- broken list indents;
- split or unreadable register rows;
- broken table widths;
- stale page fields;
- excessive blank space caused by avoidable pagination;
- accidental colour;
- visual drift from the approved proof.

LibreOffice may be used as a secondary portability check, but it is not the
authoritative pagination engine.

## Push-time behaviour

The intended automated flow is:

```text
component Markdown change
        ↓
validate four-module authority set
        ↓
rebuild COMPILED.md
        ↓
prove module reconstruction
        ↓
build changed component DOCX companion(s)
        ↓
build complete Blueprint DOCX
        ↓
content + structure + accessibility audits
        ↓
Word render and visual-regression gate
        ↓
publish build artifacts
```

Do not commit QA PNGs or temporary PDFs unless the operator requests them.

## Failure policy

Stop and report rather than guessing if:

- an authoritative module cannot be located;
- two candidates claim to be current;
- a module boundary is ambiguous;
- a content audit fails;
- Word rendering changes page structure unexpectedly;
- fonts are unavailable;
- an existing generated DOCX is open or locked.

When an output is locked, write a clearly labelled candidate file. Never force
an overwrite or destroy the last good build.

## Completion report

Return only:

1. the Markdown inputs used;
2. the Word outputs created;
3. audit results;
4. page counts;
5. any unresolved rendering or source-authority issue.

Do not claim success until content coverage and page-image inspection both pass.

## Operator instruction to Claude

Treat everything above as binding production requirements. Preserve existing
source wording and preserve the existing design implementation. Your job is to
regenerate faithful Word companions, not to redesign the Blueprint or edit its
content.
