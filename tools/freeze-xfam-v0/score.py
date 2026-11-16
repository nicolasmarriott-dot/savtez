#!/usr/bin/env python3
"""Score a freeze-xfam result against Checker A's judgments plus the M009 rule."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINE_RE = re.compile(
    r"^(M\d{3})\s*\|\s*supported:\s*(yes|no)\s*\|\s*keeps:\s*(yes|no)\s*\|\s*ok:\s*(yes|no)\b",
    re.IGNORECASE,
)


def parse_verdicts(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = LINE_RE.match(raw.strip())
        if not m:
            continue
        item = m.group(1).upper()
        ok = m.group(4).lower()
        if item in out:
            raise SystemExit(f"duplicate verdict for {item} in {path}")
        out[item] = ok
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("judgment", type=Path, help="Checker A verdict file (150 lines)")
    p.add_argument("result", type=Path, help="Model verdict file to score")
    args = p.parse_args(argv)

    judgment = parse_verdicts(args.judgment)
    result = parse_verdicts(args.result)
    if len(judgment) != 150:
        raise SystemExit(f"expected 150 judgment verdicts, got {len(judgment)}")
    if len(result) != 150:
        raise SystemExit(f"expected 150 result verdicts, got {len(result)}")
    missing = [i for i in judgment if i not in result]
    extra = [i for i in result if i not in judgment]
    if missing or extra:
        raise SystemExit(f"item set mismatch: missing={missing} extra={extra}")

    planted = {i for i, ok in judgment.items() if ok == "no"}
    planted.add("M009")
    clean = set(judgment) - planted
    if len(planted) != 125 or len(clean) != 25:
        raise SystemExit(f"key counts failed: planted={len(planted)} clean={len(clean)}")

    missed = sorted(i for i in planted if result[i] == "yes")
    caught = sorted(i for i in planted if result[i] == "no")
    false_alarms = sorted(i for i in clean if result[i] == "no")
    passed_clean = sorted(i for i in clean if result[i] == "yes")

    print(
        f"VERDICT | Qwen caught {len(caught)} of {len(planted)} planted items "
        f"and raised {len(false_alarms)} false alarms on {len(clean)} clean items."
    )
    print(f"Count check: planted {len(planted)}, clean {len(clean)}. PASS.")
    print(f"Caught: {len(caught)}")
    print(f"Missed: {len(missed)}. " + (", ".join(missed) if missed else "none"))
    print(f"False alarms: {len(false_alarms)}. " + (", ".join(false_alarms) if false_alarms else "none"))
    print(f"Clean passed: {len(passed_clean)}")
    return 0 if len(caught) == 121 and not false_alarms and missed == ["M046", "M066", "M124", "M127"] else 1


if __name__ == "__main__":
    sys.exit(main())
