#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Documents that restate machine-readable data must be checked against it.

Two summaries in this repository are convenient enough to be worth keeping and
exactly the kind of thing that goes stale:

  * the negative-results table in README.md, which restates ids and verdicts
    that live in ledger/negative_results.jsonl
  * the digest table in docs/ja/README.md, which claims the copied files are
    byte-identical to their sources

Both are asserted here. A summary nobody checks is a second definition point
wearing a table.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess  # noqa: F401  (exercised via the digest comparison below)
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


README = (REPO / "README.md").read_text(encoding="utf-8")
JA = (REPO / "docs/ja/README.md").read_text(encoding="utf-8")

print("== README negative-results table matches the ledger ==")
ledger = [json.loads(l) for l in
          (REPO / "ledger/negative_results.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
ledger_pairs = [(r["id"], r["verdict"]) for r in ledger]
readme_pairs = re.findall(r"^\|\s*(NR-\d+)\s*\|\s*([a-z_]+)\s*\|", README, re.M)
check("P1 the table has a row per ledger record",
      len(readme_pairs) == len(ledger_pairs), f"{len(readme_pairs)} vs {len(ledger_pairs)}")
check("P2 ids and verdicts agree", readme_pairs == ledger_pairs,
      f"{readme_pairs} vs {ledger_pairs}")
check("P3 **negative control**: the parse found something to compare",
      len(readme_pairs) > 0, "the regex matched no rows, so P1/P2 would pass vacuously")

print("== docs/ja digest table matches the files actually present ==")
rows = re.findall(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", JA, re.M)
check("Q0 **negative control**: the digest table parsed", len(rows) >= 5, f"{len(rows)} rows")
for rel, want in rows:
    p = REPO / rel
    if not p.is_file():
        check(f"Q1 {rel} exists", False, "listed in the digest table but not present")
        continue
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    check(f"Q2 {rel} is byte-identical to its recorded source", got == want,
          f"recorded {want[:16]} / actual {got[:16]}")

listed = {rel for rel, _ in rows}
copied_here = {"scripts/tautological_control_gate.py",
               "scripts/tests/test_tautological_control_gate.py",
               "schema/emit_reason_codes.yaml"}
check("Q3 the non-Japanese verbatim copies are listed too",
      copied_here <= listed, str(sorted(copied_here - listed)))

print("== the provenance anchor is stated consistently ==")
anchors = set(re.findall(r"\b([0-9a-f]{40})\b", README)) | set(re.findall(r"\b([0-9a-f]{40})\b", JA))
check("A1 exactly one anchor commit is referenced", len(anchors) == 1, str(anchors))
check("A2 it appears in both documents",
      all(any(a in doc for a in anchors) for doc in (README, JA)))

print(f"\ndocs-parity: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
