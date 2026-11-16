#!/usr/bin/env python3
"""Rebuild freeze-xfam batches from items-and-sources.txt."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ITEMS = REPO / "examples" / "freeze-xfam-v0" / "items-and-sources.txt"
DEFAULT_OUT = REPO / "examples" / "freeze-xfam-v0" / "batches"


def build_from(items_path: Path, out_dir: Path, batch_size: int) -> None:
    lines = items_path.read_text(encoding="utf-8").split("\n")
    if lines[0] != "TO AI":
        raise SystemExit(f"expected first line 'TO AI' in {items_path}")
    si = lines.index("SOURCES")
    ii = lines.index("ITEMS")
    header = "\n".join(lines[1:si])
    src_lines = lines[si + 1 : ii]
    items = [l for l in lines[ii + 1 :] if re.match(r"^M\d{3} ", l)]
    if len(items) != 150:
        raise SystemExit(f"expected 150 items, got {len(items)}")
    blocks: dict[str, list[str]] = {}
    order: list[str] = []
    for l in src_lines:
        m = re.match(r"^\[(S\d+)\] ", l)
        if m:
            sid = m.group(1)
            if sid not in blocks:
                blocks[sid] = []
                order.append(sid)
            blocks[sid].append(l)

    def build(batch: list[str]) -> str:
        need = {re.match(r"^M\d{3} \[(S\d+)\]", it).group(1) for it in batch}
        parts = [header, "SOURCES"]
        for sid in order:
            if sid in need:
                parts.append("\n".join(blocks[sid]))
                parts.append("")
        parts.append("ITEMS")
        parts.extend(batch)
        return "\n".join(parts)

    out_dir.mkdir(parents=True, exist_ok=True)
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    sha_lines = []
    for k, batch in enumerate(batches, 1):
        prompt = build(batch)
        dest = out_dir / f"batch{k:02d}.prompt.txt"
        dest.write_text(prompt, encoding="utf-8")
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        sha_lines.append(f"{digest}  batch{k:02d}.prompt.txt")
        print(f"batch{k:02d} {batch[0][:4]}-{batch[-1][:4]} {len(prompt)} bytes", file=sys.stderr)
    (out_dir / "prompts.sha256").write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--batch-size", type=int, default=25)
    args = p.parse_args()
    build_from(args.items, args.out, args.batch_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
