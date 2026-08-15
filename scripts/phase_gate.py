#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase transition gate. Single definition point: schema/phase_transitions.json.

    python3 scripts/phase_gate.py --from Build --to Review     # 0
    python3 scripts/phase_gate.py --from Build --to Ship       # 1  (skips Test)
    python3 scripts/phase_gate.py --from Build --to Refactor   # 2  (unknown name)

Exit codes
----------
``0`` the transition is permitted.
``1`` the transition is defined and rejected.
``2`` the transition cannot be decided (unknown phase, unreadable definition).

Why 2 is separate from 1
------------------------
"rejected" and "I do not know what you are talking about" are different states,
and collapsing them is how a gate gets bypassed: if an unrecognised phase name
returned the same code as a recognised violation, the fix for a red gate would
be to rename the phase.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "schema/phase_transitions.json"


class Undecidable(Exception):
    pass


def load(path: pathlib.Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Undecidable(f"transition definition unreadable: {path} ({e})") from e
    if not d.get("phases"):
        raise Undecidable(f"transition definition has no phases: {path}")
    return d


def order(d: dict) -> list:
    return [p["id"] for p in d["phases"]]


def decide(d: dict, frm: str | None, to: str) -> tuple:
    """Return (permitted, why). Raises Undecidable for names not in the definition."""
    names = order(d)
    terminal = d.get("terminal")
    if to == terminal:
        if frm is None:
            raise Undecidable("terminal state requested with no current phase")
        if frm not in names:
            raise Undecidable(f"unknown phase {frm!r}")
        allowed_from = d["rules"].get("terminal_from")
        ok = frm == allowed_from
        return ok, (f"{terminal} is reachable only from {allowed_from}"
                    if not ok else f"{frm} -> {terminal}")
    if to not in names:
        raise Undecidable(f"unknown phase {to!r} — not in the transition definition")
    if frm is None:
        ok = to == names[0]
        return ok, (f"entry is only permitted at {names[0]}" if not ok else f"entry at {to}")
    if frm not in names:
        raise Undecidable(f"unknown phase {frm!r} — not in the transition definition")
    i, j = names.index(frm), names.index(to)
    if j == i:
        return True, f"re-entering {to}"
    if j == i + 1:
        return True, f"{frm} -> {to}"
    if j < i:
        return False, f"backward transition {frm} -> {to} is rejected"
    return False, (f"{frm} -> {to} skips " + ", ".join(names[i + 1:j]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="phase transition gate")
    ap.add_argument("--from", dest="frm", default=None,
                    help="current phase; omit to test entry")
    ap.add_argument("--to", required=True, help="proposed next phase")
    ap.add_argument("--definition", default=str(DEFAULT))
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        d = load(pathlib.Path(a.definition))
        ok, why = decide(d, a.frm, a.to)
    except Undecidable as e:
        print(f"phase-gate UNDECIDABLE: {e}", file=sys.stderr)
        return 2
    if ok:
        print(f"phase-gate OK: {why}")
        return 0
    print(f"phase-gate BLOCK: {why}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
