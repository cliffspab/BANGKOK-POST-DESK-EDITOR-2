"""Emit one desired Unity native projection as compact ASCII JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    matches = [item for item in plan["documents"] if item["role"] == args.role]
    if len(matches) != 1:
        raise SystemExit(f"role {args.role!r} occurs {len(matches)} times")
    payload = json.dumps(
        matches[0]["desired_native_projection"],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8", newline="")
    else:
        print(payload)


if __name__ == "__main__":
    main()
