#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controls for the phase transition gate.

The property that matters is the three-way split: permitted / rejected /
undecidable. If "I do not recognise this phase" collapsed into "rejected", the
cheapest way past a red gate would be to rename the phase.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess  # noqa: F401  (subject is exercised through the module below)
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location("pg", REPO / "scripts/phase_gate.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


DEF = REPO / "schema/phase_transitions.json"
d = G.load(DEF)
names = G.order(d)

print("== permitted ==")
for i in range(len(names) - 1):
    ok, why = G.decide(d, names[i], names[i + 1])
    check(f"P{i + 1} {names[i]} -> {names[i + 1]}", ok, why)
ok, _ = G.decide(d, names[0], names[0])
check("P0 re-entering the same phase", ok)
ok, _ = G.decide(d, None, names[0])
check("P9 entry at the first phase", ok)
ok, _ = G.decide(d, names[-1], d["terminal"])
check("P10 terminal from the last phase", ok)

print("== rejected ==")
ok, why = G.decide(d, names[0], names[2])
check("R1 skipping a phase is rejected", not ok, why)
ok, why = G.decide(d, names[3], names[1])
check("R2 going backward is rejected", not ok, why)
ok, why = G.decide(d, None, names[3])
check("R3 entering in the middle is rejected", not ok, why)
ok, why = G.decide(d, names[0], d["terminal"])
check("R4 terminal from anywhere else is rejected", not ok, why)

print("== undecidable is its own outcome ==")
for frm, to, label in [(names[0], "Refactor", "unknown target"),
                       ("Refactor", names[0], "unknown source")]:
    try:
        G.decide(d, frm, to)
        raised = False
    except G.Undecidable:
        raised = True
    check(f"U1 {label} raises rather than returning a verdict", raised)

rc = G.main(["--from", names[0], "--to", "Refactor", "--definition", str(DEF)])
check("U2 exit code for undecidable is 2, distinct from rejected", rc == 2, f"rc={rc}")
rc = G.main(["--from", names[0], "--to", names[2], "--definition", str(DEF)])
check("U3 exit code for rejected is 1", rc == 1, f"rc={rc}")
rc = G.main(["--from", names[0], "--to", names[1], "--definition", str(DEF)])
check("U4 exit code for permitted is 0", rc == 0, f"rc={rc}")

with tempfile.TemporaryDirectory() as tmp:
    empty = pathlib.Path(tmp, "empty.json")
    empty.write_text(json.dumps({"phases": []}), encoding="utf-8")
    rc = G.main(["--from", names[0], "--to", names[1], "--definition", str(empty)])
    check("U5 an empty definition is undecidable, not permissive", rc == 2, f"rc={rc}")
    rc = G.main(["--to", names[0], "--definition", str(pathlib.Path(tmp, "absent.json"))])
    check("U6 an unreadable definition is undecidable", rc == 2, f"rc={rc}")

print("== the definition is not duplicated ==")
# The probe is taken from the definition rather than written here: spelling it
# out would make this file a copy of the thing it is checking for, and the
# check would then always fail on itself.
probe = [n for n in names if " " in n][0]
copies = [p.relative_to(REPO).as_posix() for p in sorted(REPO.rglob("*"))
          if p.is_file() and ".git" not in p.parts and p != DEF
          and p.suffix in (".json", ".py")
          and probe in p.read_text(encoding="utf-8", errors="replace")]
check("D1 the phase list exists in exactly one machine-readable place",
      copies == [], str(copies))
check("D2 **negative control**: the probe really is present in the definition",
      probe in DEF.read_text(encoding="utf-8"), probe)

print(f"\nphase-gate: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
