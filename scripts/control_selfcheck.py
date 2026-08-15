#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assert that every declared positive control still matches its own class.

This is the check that stops the positive controls from rotting. Editing a
pattern is easy; noticing that the payload which used to prove the pattern no
longer matches anything is not. Without this, a class can be narrowed to the
point of uselessness while its control test keeps passing, because the control
test only ever asserted "the commit was rejected" and some *other* class was
doing the rejecting.

Two assertions per class:

1. the class's ``positive_control`` payload matches at least one pattern
   **belonging to that class**;
2. no class is left without a declared control.

Exit codes: 0 all controls live, 1 a control does not fire, 2 undecidable.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import scan_forensic as S  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="positive-control self-check")
    ap.add_argument("--prereg", default=str(ROOT / "docs/prereg.scan.md"))
    ap.add_argument("--literals", default=str(ROOT / "config/literals.json"))
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        prereg = S.load_prereg(pathlib.Path(a.prereg))
        literals = S.load_literals(pathlib.Path(a.literals))
        patterns, declared_empty = S.compile_patterns(prereg, literals)
        controls = S.positive_controls(prereg, literals)
    except S.Undecidable as e:
        print(f"control-selfcheck UNDECIDABLE: {e}", file=sys.stderr)
        return 2

    declared = {c["id"] for c in prereg["classes"]}
    active = declared - set(declared_empty)
    missing = sorted(active - set(controls))
    dead = []
    for cid, payload in sorted(controls.items()):
        own = [p for p in patterns if p.cls == cid]
        hits = S.scan_text(payload, own, f"<control:{cid}>")
        if not hits:
            dead.append(cid)
        else:
            print(f"  live  {cid}: {hits[0]['pattern']} matched {hits[0]['matched']!r}")
    for cid, why in declared_empty.items():
        print(f"  empty {cid}: {why[:90]}")

    if missing:
        print(f"control-selfcheck BLOCK: classes with no declared control: {missing}",
              file=sys.stderr)
    if dead:
        print(f"control-selfcheck BLOCK: controls that no longer match their own class: "
              f"{dead}", file=sys.stderr)
    if missing or dead:
        return 1
    print(f"control-selfcheck OK: {len(controls)} control(s) live, "
          f"{len(declared_empty)} class(es) declared empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
