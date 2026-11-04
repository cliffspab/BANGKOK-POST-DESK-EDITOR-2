# BKP Markdown-to-Word conversion specification

## Authority

- Content and structural authority: `compare/COMPILED.md`
- Visual authority: the BKP severe black-and-white design system embodied in
  `compare/the_bangkok_post_blueprint_compendium_final.docx` and refined by
  `compare/BKP_conversion_design_proof.docx`
- Generated Word output is a build artifact, never an independent content
  master.

## Deterministic mapping

| Markdown role | Native Word result |
|---|---|
| Initial title and metadata | Monumental cover and source metadata |
| `# PART: name` | New Word section, active register, part label and H1 |
| Redundant component `#` after a part marker | Folded into the part opening |
| `##` | Ruled major section |
| `###` | Compact operational subsection |
| `####` | Mixed-case fine division |
| Short doctrine after `###` | AXIOM component when the deterministic length/position rule matches |
| Paragraph | Native body paragraph with inline emphasis and links |
| Ordered/unordered list | Native Word numbering definitions |
| Fenced code | Fixed-width bordered code panel |
| Markdown table | Fixed-geometry native Word table with repeating header |
| Horizontal rule | Native paragraph border |

The equal-sign separator lines surrounding `PART:` markers are treated as
source-side structural markup and are not emitted as literal text.

## Build

```powershell
& $python tools/build_bkp_compendium.py `
  --source compare/COMPILED.md `
  --reference compare/the_bangkok_post_blueprint_compendium_final.docx `
  --output compare/BKP_PIPELINE_COMPILED_GOVERNANCE_SET.docx
```

Pandoc is used only to parse GitHub-flavoured Markdown into a JSON syntax tree.
The Word document itself is constructed with native Word styles, lists,
tables, hyperlinks, sections, headers, footers and fields.

## Push-time requirements

- Python with `python-docx`
- Pandoc
- Arial and Arial Black, or an explicitly approved metrically compatible font set
- Structural audit on every build
- Word rendering on a Windows runner for authoritative pagination
- Page-image inspection or visual-regression review before promotion

LibreOffice may be used as a secondary portability check but is not the
authoritative renderer for this design.
