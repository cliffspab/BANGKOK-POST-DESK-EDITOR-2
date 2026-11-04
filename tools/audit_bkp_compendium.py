"""Audit that every meaningful Markdown text unit is present in the DOCX."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

from lxml import etree


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
SEPARATOR_RE = re.compile(r"^={20,}$")


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def inline_text(inlines):
    parts = []
    for item in inlines:
        kind = item["t"]
        content = item.get("c")
        if kind == "Str":
            parts.append(content)
        elif kind in ("Space", "SoftBreak", "LineBreak"):
            parts.append(" ")
        elif kind in ("Strong", "Emph", "Underline", "Strikeout", "SmallCaps", "Superscript", "Subscript"):
            parts.append(inline_text(content))
        elif kind == "Code":
            parts.append(content[1])
        elif kind in ("Link", "Image"):
            parts.append(inline_text(content[1]))
        elif kind == "Quoted":
            quote = '"' if content[0]["t"] == "DoubleQuote" else "'"
            parts.append(quote + inline_text(content[1]) + quote)
        elif kind == "RawInline":
            parts.append(content[1])
    return "".join(parts)


def block_text(block):
    kind = block["t"]
    content = block.get("c")
    if kind in ("Para", "Plain"):
        return inline_text(content)
    if kind == "Header":
        return inline_text(content[2])
    if kind == "CodeBlock":
        return content[1]
    return ""


def table_rows(block):
    content = block["c"]
    for row in content[3][1]:
        yield row[1]
    for body in content[4]:
        for row in body[3]:
            yield row[1]


def collect_units(blocks):
    units = []
    for block in blocks:
        kind = block["t"]
        if kind in ("Para", "Header", "CodeBlock"):
            text = normalize(block_text(block))
            if text and not SEPARATOR_RE.fullmatch(text):
                units.append(text)
        elif kind in ("BulletList", "OrderedList"):
            items = block["c"] if kind == "BulletList" else block["c"][1]
            for item in items:
                units.extend(collect_units(item))
        elif kind == "Table":
            for row in table_rows(block):
                for cell in row:
                    for cell_block in cell[4]:
                        text = normalize(block_text(cell_block))
                        if text:
                            units.append(text)
    return units


def parse_markdown(pandoc, source):
    with tempfile.TemporaryDirectory(prefix="bkp-audit-") as tmp:
        path = Path(tmp) / "ast.json"
        subprocess.run([str(pandoc), "-f", "gfm", "-t", "json", str(source), "-o", str(path)], check=True)
        return json.loads(path.read_text(encoding="utf-8"))


def docx_text(docx):
    # 010826: was document.xml only. Anything the build puts in a running head
    # or footer was invisible to the gate, so relocating content out of the
    # body read as content loss - which is precisely what this audit exists to
    # distinguish from. Headers and footers are part of the volume; read them.
    with ZipFile(docx) as archive:
        names = [n for n in archive.namelist()
                 if n == "word/document.xml"
                 or (n.startswith("word/header") or n.startswith("word/footer"))
                 and n.endswith(".xml")]
        roots = [etree.fromstring(archive.read(n)) for n in sorted(names)]
    paragraphs = []
    for paragraph in [p for r in roots for p in r.xpath("//w:p", namespaces=NS)]:
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{{{NS['w']}}}t" and node.text:
                parts.append(node.text)
            elif node.tag in (f"{{{NS['w']}}}br", f"{{{NS['w']}}}tab"):
                parts.append(" ")
        text = normalize("".join(parts))
        if text:
            paragraphs.append(text)
    return normalize(" ".join(paragraphs))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--docx", type=Path, required=True)
    parser.add_argument("--pandoc", type=Path, default=Path(r"C:\Program Files\Pandoc\pandoc.exe"))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    ast = parse_markdown(args.pandoc, args.source)
    units = collect_units(ast["blocks"])
    output = docx_text(args.docx)
    missing = [unit for unit in units if unit not in output]
    report = {
        "source_units": len(units),
        "matched_units": len(units) - len(missing),
        "missing_units": missing,
        "pass": not missing,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if not missing else 1)


if __name__ == "__main__":
    main()
