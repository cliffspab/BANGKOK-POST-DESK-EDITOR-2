#!/usr/bin/env python3
"""
Close the loop after a push: wait for the compile job, pull its output, and
seal the edition.

The Word volume is NOT built locally. build.py writes the parts and the PDF;
tools/build_bkp_compendium.py builds the docx and it runs inside the compile
job. Building it here as well would mean pushing a docx that CI immediately
rebuilds and commits over — a binary conflict on the next rebase, for nothing.

So the docx comes back rather than going out. This waits for compile-bot to
commit, rebases onto it, checks the volume carries the current build tag, and
copies the edition into Editions\\<tag>\\.

    python3 seal.py             wait for CI, pull, seal
    python3 seal.py --no-wait   pull and seal whatever is already on origin

Run it from push.bat after a confirmed push, or by hand any time afterwards —
it is idempotent and safe to repeat.

NOT A QUALITY GATE. The design spec keeps two checks off the machine: Word on
Windows is the authoritative renderer for pagination, and the accessibility
audit is manual. A sealed volume is a build artifact, not an approved one.
"""

import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLONE = ROOT / "pipeline-registry"
BLUEPRINT = CLONE / "Blueprint"
POLL_SECONDS = 15
TIMEOUT_SECONDS = 480

# Copied into the edition. The docx AND the pdf come from CI; the rest are
# local build output and are already correct before the push.
#
# The pdf moved to FROM_CLONE on 100826. It used to be rendered locally by
# build.py through pandoc/xelatex, in parallel with the volume - two toolchains,
# two designs, one document. It is now a LibreOffice conversion of the volume
# itself, made by the compile job, so it comes back with the docx rather than
# going out ahead of it.
FROM_ROOT = ["BLUEPRINT.txt", "GUIDE.txt", "PROCESSES.txt", "DIRECTORY.yaml",
             "DIRECTORY.txt", "VERSION.txt", "build.py", "extract.py"]
FROM_CLONE = ["BLUEPRINT.docx", "BLUEPRINT.pdf", "BLUEPRINT.manifest.json"]


def git(*args, check=True):
    return subprocess.run(["git", "-C", str(CLONE), *args],
                          capture_output=True, text=True, check=check)


def current_tag():
    """The build tag, read from the source's own front matter."""
    src = (ROOT / "BLUEPRINT.txt").read_text(encoding="utf-8")
    m = re.search(r"<!-- PART: (\S+) GUIDE -->", src)
    if not m:
        sys.exit("FATAL: no GUIDE seam in BLUEPRINT.txt — cannot name the edition.")
    return m.group(1)


def docx_stamp(path):
    """The tag printed in the volume's section headers."""
    tags = set()
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".xml") and ("header" in name or "document" in name):
                text = z.read(name).decode("utf-8", errors="ignore")
                tags.update(re.findall(r"\d{6}_[a-z]+_[a-z-]+", text))
    return tags


def remote_head():
    out = git("ls-remote", "origin", "refs/heads/main").stdout.split()
    return out[0][:7] if out else None


def main():
    wait = "--no-wait" not in sys.argv
    tag = current_tag()
    print("edition: %s" % tag)

    if git("status", "--porcelain").stdout.strip():
        sys.exit("FATAL: the clone has uncommitted changes. Push first, then seal.")

    local = git("rev-parse", "--short", "HEAD").stdout.strip()
    if wait:
        print("waiting for the compile job (up to %d min)..." % (TIMEOUT_SECONDS // 60))
        waited = 0
        while remote_head() == local and waited < TIMEOUT_SECONDS:
            time.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            print("  %ds" % waited, end="\r", flush=True)
        if remote_head() == local:
            print("\nCI has not committed yet. The job may still be running, or it "
                  "may have failed at a guard.\nCheck the Actions tab, then re-run "
                  "this script. Nothing has been sealed.")
            return 1
        print("\ncompile-bot has committed.")

    git("fetch", "origin")
    r = git("rebase", "origin/main", check=False)
    if r.returncode:
        git("rebase", "--abort", check=False)
        sys.exit("FATAL: rebase onto origin/main failed. Resolve by hand; "
                 "nothing sealed.")
    print("pulled: now at %s" % git("rev-parse", "--short", "HEAD").stdout.strip())

    docx = BLUEPRINT / "BLUEPRINT.docx"
    if not docx.exists():
        sys.exit("FATAL: no BLUEPRINT.docx in the clone after the pull.")
    stamps = docx_stamp(docx)
    if tag not in stamps:
        print("  volume carries: %s" % (", ".join(sorted(stamps)) or "no stamp"))
        sys.exit("FATAL: the volume does not carry %s. It is from an earlier "
                 "build — the compile job has not produced this edition yet. "
                 "Nothing sealed." % tag)
    print("volume stamp: %s — matches" % tag)

    dest = ROOT / "Editions" / tag
    dest.mkdir(parents=True, exist_ok=True)
    for name in FROM_ROOT:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, dest / name)
            print("  sealed %s" % name)
    for name in FROM_CLONE:
        src = BLUEPRINT / name
        if src.exists():
            shutil.copy2(src, dest / name)
            print("  sealed %s  (from CI)" % name)

    print("\nedition sealed: Editions/%s" % tag)
    print("NOT an approved volume — Word-on-Windows pagination and the "
          "accessibility audit are operator gates and are still outstanding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
