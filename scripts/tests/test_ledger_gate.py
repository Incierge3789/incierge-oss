#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controls for the ledger schema gate.

Each rule is exercised in both directions: a record that must pass and a
mutation of that same record that must fail. Asserting only that the shipped
ledger validates would pass even if the validator accepted everything.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import subprocess  # noqa: F401  (subject is exercised through the module below)
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location("lg", REPO / "scripts/ledger_gate.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


SCHEMA = REPO / "schema/ledger.json"
LEDGER = REPO / "ledger/negative_results.jsonl"


def run(records, rtype="negative_result"):
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp, "r.jsonl")
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                     encoding="utf-8")
        return G.main(["--type", rtype, "--file", str(p), "--schema", str(SCHEMA)])


base = json.loads(LEDGER.read_text(encoding="utf-8").splitlines()[0])

print("== the shipped ledger ==")
rc = G.main(["--type", "negative_result", "--file", str(LEDGER), "--schema", str(SCHEMA)])
check("L1 the shipped negative-results ledger validates", rc == 0, f"rc={rc}")
rc = G.main(["--type", "prereg", "--file", str(REPO / "examples/prereg.sample.json"),
             "--schema", str(SCHEMA)])
check("L2 the pre-registration sample validates", rc == 0, f"rc={rc}")

print("== every rule fails on demand ==")
mutations = [
    ("M1 a missing required field", lambda r: r.pop("measured")),
    ("M2 a verdict outside the enum", lambda r: r.update(verdict="probably_fine")),
    ("M3 an id that does not match its pattern", lambda r: r.update(id="nr-1")),
    ("M4 a date that is not ISO-8601", lambda r: r.update(date="15/08/2026")),
    ("M5 a string below its minimum length", lambda r: r.update(measured="n/a")),
    ("M6 a field the schema does not declare", lambda r: r.update(vibes="good")),
    ("M7 null in a field that is not nullable", lambda r: r.update(claim=None)),
]
for name, mutate in mutations:
    rec = copy.deepcopy(base)
    mutate(rec)
    check(name + " is rejected", run([rec]) == 1)
check("M0 **negative control**: the unmutated record still passes", run([copy.deepcopy(base)]) == 0)
rec = copy.deepcopy(base)
rec["withdrawn_claim"] = None
check("M8 null IS accepted where the schema declares nullable", run([rec]) == 0)

print("== closed vocabulary ==")
failure = {"id": "F-001", "ts": "2026-08-15T00:00:00Z",
           "symptom": "the guard did not fire on planted input",
           "cause_code": "contract_violation", "detected_by": "positive control",
           "close_predicate": "the control fires again on the same input",
           "status": "open"}
check("V1 a label from the closed set is accepted", run([failure], "failure") == 0)
bad = dict(failure, cause_code="something_went_wrong")
check("V2 a label outside the closed set is rejected", run([bad], "failure") == 1)

print("== undecidable is not success ==")
with tempfile.TemporaryDirectory() as tmp:
    empty = pathlib.Path(tmp, "empty.jsonl")
    empty.write_text("", encoding="utf-8")
    rc = G.main(["--type", "negative_result", "--file", str(empty), "--schema", str(SCHEMA)])
    check("U1 zero records is undecidable, not 'all valid'", rc == 2, f"rc={rc}")
    rc = G.main(["--type", "no_such_type", "--file", str(LEDGER), "--schema", str(SCHEMA)])
    check("U2 an unknown record type is undecidable", rc == 2, f"rc={rc}")
    rc = G.main(["--type", "negative_result", "--file", str(LEDGER),
                 "--schema", str(pathlib.Path(tmp, "absent.json"))])
    check("U3 an unreadable schema is undecidable", rc == 2, f"rc={rc}")

    broken = pathlib.Path(tmp, "vocab.yaml")
    broken.write_text("failure_cause:\n", encoding="utf-8")
    sch = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sch["vocabularies"]["failure_cause"]["file"] = "vocab.yaml"
    alt_root = pathlib.Path(tmp, "root", "schema")
    alt_root.mkdir(parents=True)
    (alt_root.parent / "vocab.yaml").write_text("failure_cause:\n", encoding="utf-8")
    (alt_root / "ledger.json").write_text(json.dumps(sch), encoding="utf-8")
    p = pathlib.Path(tmp, "f.jsonl")
    p.write_text(json.dumps(failure) + "\n", encoding="utf-8")
    rc = G.main(["--type", "failure", "--file", str(p), "--schema", str(alt_root / "ledger.json")])
    check("U4 an empty closed vocabulary is undecidable rather than reject-everything",
          rc == 2, f"rc={rc}")

print("== the external-response instrument is defined and separate ==")
sch = json.loads(SCHEMA.read_text(encoding="utf-8"))
check("E1 the type exists", "external_response" in sch["types"])
note = " ".join(sch["types"]["external_response"].get("_defined_but_not_counted", []))
check("E2 it states that it must not join the intervention numerator",
      "numerator" in note and "never" in note, note[:120])

print(f"\nledger-gate: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
