#!/usr/bin/env python3
"""
Bangkok Post Blueprint — build.

Four accessible working sources are edited:

    BLUEPRINT.front.md  title, edition witness and contents
    GUIDE.md            the editorial brief, part delivery for /guide
    PROCESSES.md        the operational methods and task sections
    DIRECTORY.yaml      the lookups, part delivery for /dir

BLUEPRINT.txt is compiled from those sources. The text deliveries are
byte-identical compatibility twins:

    GUIDE.txt
    PROCESSES.txt
    DIRECTORY.txt
    VERSION.txt       the exact current edition for /ver
    BLUEPRINT.pdf     the rendered artifact of record

The extension is inert. Nothing in the chain reads it: pandoc is told the
format explicitly and raw.githubusercontent serves every extension as
text/plain. The markdown SYNTAX is load-bearing and is not optional — it is
what makes headings headings in the rendered volume.

The register travels verbatim. Between the seam and the fence the bytes are
the register exactly, which is what makes the split reversible: cut on the
seam, strip the fence, restore the comment seam, and DIRECTORY.yaml is back.
The invertibility guard below checks that on every build.

BLUEPRINT.pdf is downstream. Rendered, never edited.

Run:  python3 build.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

MASTER = "BLUEPRINT.txt"
FRONT = "BLUEPRINT.front.md"
EXPECT = ["GUIDE", "PROCESSES", "DIRECTORY"]

SEAM = re.compile(r"<!-- PART: (\S+) (\w+) -->")
FENCE = re.compile(r"```yaml\n(.*?)\n```", re.S)
GUIDE_CODE = re.compile(r"^#{1,6} \[([GP](?:\d+(?:-[A-Z]\d*)?))\] ", re.M)
CONTENTS_CODE = re.compile(r"^\s*- \[([GP](?:\d+(?:-[A-Z]\d*)?))\] \S", re.M)


def fail(msg):
    sys.exit(f"FATAL: {msg}")


def assemble_sources():
    """Compile the complete compatibility master from the working authorities."""
    required = (FRONT, "GUIDE.md", "PROCESSES.md", "DIRECTORY.yaml")
    missing = [name for name in required if not os.path.exists(name)]
    if missing:
        fail("missing working source(s): " + ", ".join(missing))

    front = open(FRONT, encoding="utf-8").read().rstrip("\n") + "\n\n"
    edition_lines = [p.strip() for p in front.split("\n\n") if p.strip()]
    if len(edition_lines) < 2:
        fail(f"{FRONT} has no edition witness")
    tag = edition_lines[1]

    guide = open("GUIDE.md", encoding="utf-8").read().rstrip("\n") + "\n"
    processes = open("PROCESSES.md", encoding="utf-8").read().rstrip("\n") + "\n"
    for name, text, part in (("GUIDE.md", guide, "GUIDE"),
                             ("PROCESSES.md", processes, "PROCESSES")):
        expected = f"<!-- PART: {tag} {part} -->"
        if not text.startswith(expected):
            fail(f"{name} must begin with {expected}")

    directory = open("DIRECTORY.yaml", encoding="utf-8").read()
    marker = f"# PART: {tag} DIRECTORY\n"
    if not directory.startswith(marker):
        fail(f"DIRECTORY.yaml must begin with {marker.strip()}")
    yaml_body = directory[len(marker):].strip("\n")
    directory_part = (
        f"<!-- PART: {tag} DIRECTORY -->\n\n"
        "go.fuzzylogic.page/dir\n\n"
        "# [D] DIRECTORY\n\n"
        "`````yaml\n" + yaml_body + "\n```\n"
    )
    src = front + guide + processes + directory_part
    open(MASTER, "w", encoding="utf-8", newline="").write(src)
    print(f"source assembly guard: PASS ({MASTER} from Markdown/YAML authorities)")
    return src


# ---------- guards ----------

def guard_dollars(src):
    """A markdown-to-docx converter reads $...$ as inline maths and silently
    deletes what is between them. This removed 'Aus$, S$' from the published
    volume before 270726.

    Counted per PARAGRAPH, not per line. Markdown merges consecutive lines
    into one paragraph before the converter sees them, so two lines carrying
    one sign each — with no blank line between — pair up just as one line
    with two would. A per-line count passes that and the text still goes."""
    bad, line_no = [], 1
    for para in src.split("\n\n"):
        if para.count("$") > 1:
            bad.append((line_no, para.count("$"), para))
        line_no += para.count("\n") + 2
    if bad:
        for n, count, para in bad:
            print(f"  paragraph at line {n}: {count} signs")
            for l in para.split("\n"):
                if "$" in l:
                    print(f"      {l[:100]}")
        fail("two or more '$' in one paragraph. Separate the forms, or drop "
             "the sign — a list of prefixes carries the rule without it.")
    print("dollar-pairing guard: PASS (per paragraph)")


def guard_edition(tags, preamble):
    """The parts share one edition stamp. A part left on an old tag passes
    every other gate and only shows up as a slug readback disagreeing with
    itself, weeks later."""
    if len(set(tags.values())) != 1:
        for k, v in tags.items():
            print(f"  {k:<10} {v}")
        fail("the parts do not agree on the edition.")
    tag = next(iter(tags.values()))
    front = preamble.split("\n\n")[1].strip() if "\n\n" in preamble else ""
    if front and front != tag:
        fail(f"front matter is at {front}, the parts at {tag}.")
    print(f"edition guard: PASS (all parts at {tag})")
    return tag


def guard_invertible(preamble, parts, src):
    """Parts carry their own seam, so reassembly is plain concatenation."""
    rebuilt = preamble + "".join(parts[k] for k in EXPECT)
    if rebuilt != src:
        fail("the split is not invertible. Refusing to publish.")
    print("invertibility guard: PASS (parts recompile byte-for-byte)")


def guard_guide_codes(src):
    """Require one target heading for every edition-bound section code."""
    contents = CONTENTS_CODE.findall(src)
    headings = GUIDE_CODE.findall(src)
    duplicate_contents = sorted({code for code in contents if contents.count(code) > 1})
    duplicate_headings = sorted({code for code in headings if headings.count(code) > 1})
    if duplicate_contents:
        fail("duplicate section codes in CONTENTS: " + ", ".join(duplicate_contents))
    if duplicate_headings:
        fail("duplicate section codes on headings: " + ", ".join(duplicate_headings))
    missing = sorted(set(contents) - set(headings))
    orphaned = sorted(set(headings) - set(contents))
    if missing:
        fail("section codes in CONTENTS without headings: " + ", ".join(missing))
    if orphaned:
        fail("section heading codes absent from CONTENTS: " + ", ".join(orphaned))
    if not contents:
        fail("no coded sections found")
    print(f"section-code guard: PASS ({len(contents)} edition-bound nodes)")


# ---------- split ----------

def split(src):
    hits = list(SEAM.finditer(src))
    names = [m.group(2) for m in hits]
    if names != EXPECT:
        fail(f"expected part seams {EXPECT}, found {names}.")

    preamble = src[:hits[0].start()]
    parts, tags = {}, {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(src)
        parts[m.group(2)] = src[m.start():end]
        tags[m.group(2)] = m.group(1)
    return preamble, parts, tags


def register_yaml(part, tag):
    """Lift the fenced Directory and validate its source-owned routing index."""
    m = FENCE.search(part)
    if not m:
        fail("no ```yaml fence found in the DIRECTORY part.")
    body = m.group(1)
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError as e:
        fail(f"the register does not parse as YAML:\n{e}")
    for branch in ("status", "references"):
        if branch not in parsed:
            fail(f"the register is missing the '{branch}' branch")
    guard_index(parsed)
    print(f"register parse guard: PASS "
          f"(apex {len(parsed['status']['apex'])}, "
          f"provinces {len(parsed['references']['thai_places']['provinces'])})")
    return f"# PART: {tag} DIRECTORY\n{body}\n", parsed


def guard_index(parsed):
    """Require every source-owned routing-index path to resolve."""
    index = parsed.get("index")
    if not isinstance(index, dict):
        fail("the Directory is missing the source-owned 'index' branch")

    routes = index.get("routes")
    if not isinstance(routes, dict):
        fail("index.routes must be a mapping")

    expected_groups = {"status", "references"}
    if set(routes) != expected_groups:
        fail("index.routes must contain status and references")

    seen = set()
    for group, paths in routes.items():
        if not isinstance(paths, list) or not paths:
            fail(f"index.routes.{group} must be a non-empty list")
        for path in paths:
            if not isinstance(path, str) or path in seen:
                fail(f"invalid or duplicate Directory route: {path!r}")
            seen.add(path)
            keys = path.split(".")
            if keys[0] != group:
                fail(f"Directory route is in the wrong group: {path}")
            held = parsed
            for key in keys:
                if not isinstance(held, dict) or key not in held:
                    fail(f"Directory route does not resolve: {path}")
                held = held[key]

    print(f"routing-index guard: PASS ({len(seen)} live paths)")
# ---------- rendered artifact ----------

def render_pdf(src):
    """RETIRED 100826. The PDF is no longer rendered here.

    It used to come from pandoc/xelatex straight off the markdown, in parallel
    with the Word volume built by tools/build_bkp_compendium.py. That meant two
    toolchains and two designs for one document: the volume had the running
    heads, part openings and rendered register, the PDF had a LaTeX default and
    a generated TOC. The operator's verdict on 100826 - the PDF looks terrible,
    the docx great - is what a second design buys you.

    The PDF is now a CONVERSION of the volume, made by the compile job with
    LibreOffice and committed beside the docx. Same rule as the docx: not built
    locally, pulled back by seal.py. Left in place rather than deleted so the
    reason is where the code was.
    """
    return "  from CI — converted from the volume, pulled back by seal.py"


def _retired_render_pdf(src):
    if not shutil.which("pandoc"):
        return "  skipped — pandoc not on PATH"

    # seams are HTML comments; surface them so they survive into the PDF
    visible = SEAM.sub(r"### PART: \1 \2", src)

    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8",
                                     delete=False) as fh:
        fh.write(visible)
        tmp = fh.name
    try:
        subprocess.run(
            ["pandoc", tmp,
             # tex_math_dollars off: currency ($1, US$, B500) is not maths.
             # raw_tex off: nothing in the copy is a LaTeX instruction.
             "-f", "markdown-tex_math_dollars-raw_tex",
             "-o", "BLUEPRINT.pdf",
             "--pdf-engine=xelatex", "--toc", "--toc-depth=3",
             # DejaVu covers ¥ € £ ½ ü and the em-dash; the LaTeX default does not
             "-V", "mainfont=DejaVu Serif", "-V", "monofont=DejaVu Sans Mono",
             "-V", "geometry:margin=2.5cm", "-V", "fontsize=10pt",
             "-V", "colorlinks=true", "-V", "linkcolor=black",
             # underscores in the tag are subscript to LaTeX outside math mode
             "-V", "title=The Bangkok Post Blueprint",
             "-V", "subtitle=" + TAG_HOLDER[0].replace("_", r"\_")],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        return f"  FAILED — {e.stderr.decode()[-200:]}"
    finally:
        os.unlink(tmp)
    return f"{os.path.getsize('BLUEPRINT.pdf'):>7,} bytes  (rendered, do not edit)"


TAG_HOLDER = [""]


# ---------- build ----------

def main():
    src = assemble_sources()

    guard_dollars(src)
    preamble, parts, tags = split(src)
    tag = guard_edition(tags, preamble)
    TAG_HOLDER[0] = tag
    guard_invertible(preamble, parts, src)
    guard_guide_codes(src)

    reg_text, _ = register_yaml(parts["DIRECTORY"], tag)
    guide_text = parts["GUIDE"].rstrip("\n") + "\n"
    processes_text = parts["PROCESSES"].rstrip("\n") + "\n"
    open("GUIDE.txt", "w", encoding="utf-8").write(guide_text)
    open("PROCESSES.txt", "w", encoding="utf-8").write(processes_text)
    # The YAML working authority and text compatibility surface are literal
    # byte twins, including line endings and the final newline.
    shutil.copyfile("DIRECTORY.yaml", "DIRECTORY.txt")
    open("VERSION.txt", "w", encoding="utf-8").write(tag + "\n")

    pdf = render_pdf(src)

    print()
    print(f"{MASTER:<15}{len(src):>8,} chars  {src.count(chr(10)) + 1:>5,} lines   COMPILED")
    for f in ("GUIDE.md", "GUIDE.txt", "PROCESSES.md", "PROCESSES.txt",
              "DIRECTORY.yaml", "DIRECTORY.txt", "VERSION.txt"):
        role = "source" if f in ("GUIDE.md", "PROCESSES.md", "DIRECTORY.yaml") else "derived"
        print(f"{f:<15}{len(open(f, encoding='utf-8').read()):>8,} chars"
              f"{'':>13}{role}")
    print(f"{'BLUEPRINT.pdf':<15}{pdf}")


if __name__ == "__main__":
    main()
