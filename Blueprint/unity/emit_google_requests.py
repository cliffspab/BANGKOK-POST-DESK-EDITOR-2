"""Emit reviewed Google Docs batchUpdate requests for one Unity role.

The desired native projection comes from a source-only Unity plan.  Current
document geometry is supplied from a fresh connector read immediately before
the guarded write.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from unity_update import compile_google_docs_requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--current-end-index", required=True, type=int)
    parser.add_argument("--tab-id", required=True)
    parser.add_argument("--out")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    matches = [item for item in plan["documents"] if item["role"] == args.role]
    if len(matches) != 1:
        raise SystemExit(f"role {args.role!r} occurs {len(matches)} times")
    requests = compile_google_docs_requests(
        matches[0]["desired_native_projection"],
        current_end_index=args.current_end_index,
        tab_id=args.tab_id,
    )
    # ASCII-only output is deliberate: the connector bridge can retrieve a
    # large request file in bounded text chunks without splitting a Unicode
    # code point. JSON parsing restores the original characters exactly.
    payload = json.dumps(requests, ensure_ascii=True, separators=(",", ":"))
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8", newline="")
    if args.summary:
        print(json.dumps({"requests": len(requests), "utf8_bytes": len(payload.encode("utf-8"))}))
    elif not args.out:
        print(payload)


if __name__ == "__main__":
    main()
