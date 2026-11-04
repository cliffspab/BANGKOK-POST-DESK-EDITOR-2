# Deployment

The Blueprint is one document in two parts.

* **CORE** — core and processes. Markdown syntax.
* **REGISTER** — register and status. YAML syntax.

Both are delivered as `.txt`. The extension is inert: nothing in the chain reads it, and raw.githubusercontent serves every extension as `text/plain`. The syntax is load-bearing and is not optional.

## What to pull

`CORE.txt` + `REGISTER.txt`, confirmed latest only. Nothing else.

| Link | Serves |
| :---- | :---- |
| `/core` | CORE.txt |
| `/reg` | REGISTER.txt — same bytes as REGISTER.yaml |
| `/blue` | BLUEPRINT.txt — both parts across one seam, where a destination takes one file |

`/status`, `/refs` and `/full` are compatibility shims and are retiring. `/pro` is retired: PROCESSES is a section inside CORE and the file is no longer produced. Do not deploy from a shim.

Artifacts of record — the PDF and the compendium volume — never deploy. They fix a build in amber and carry no seam that can be checked.

## Confirmed latest

A file is confirmed latest on a checked tag, not on a filename and not on a modification date. Check the tag before the file travels; the conditions are in `system.md`.

## Producing a system prompt

Deployment is per model. Each model produces its own system prompt from the two parts — self-contained, no external reference files, optimised for its own processing.

One caution carried from the parts themselves: not every model can execute code. Where the parts offer a verified-count route and a substitution route, the model takes whichever its own capability allows. Neither is deprecated.
