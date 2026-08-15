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

print("== docs/ja provenance: verbatim rows match, adapted rows are declared ==")
# Two tables, and the difference is the claim. A verbatim row asserts the
# published bytes equal the source bytes. An adapted row asserts they do NOT,
# and says what changed. Checking only the first kind would let an edited file
# keep a verbatim claim, which is the failure this split exists to prevent.
verbatim = re.findall(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|[^|]*\|\s*$", JA, re.M)
adapted = re.findall(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|\s*`([0-9a-f]{64})`\s*\|", JA, re.M)
check("Q0 **negative control**: both tables parsed and are non-empty",
      len(verbatim) >= 2 and len(adapted) >= 2, f"verbatim={len(verbatim)} adapted={len(adapted)}")
check("Q0b the two tables are disjoint",
      not (set(r for r, _ in verbatim) & set(r for r, _, _ in adapted)),
      "a file claims to be both verbatim and adapted")

for rel, want in verbatim:
    p2 = REPO / rel
    if not p2.is_file():
        check(f"Q1 {rel} exists", False, "listed as verbatim but not present")
        continue
    got = hashlib.sha256(p2.read_bytes()).hexdigest()
    check(f"Q1 {rel} is byte-identical to its recorded source", got == want,
          f"recorded {want[:16]} / actual {got[:16]}")

for rel, src, pub in adapted:
    p2 = REPO / rel
    if not p2.is_file():
        check(f"Q2 {rel} exists", False, "listed as adapted but not present")
        continue
    got = hashlib.sha256(p2.read_bytes()).hexdigest()
    check(f"Q2 {rel} matches its recorded published digest", got == pub,
          f"recorded {pub[:16]} / actual {got[:16]}")
    check(f"Q3 {rel} really differs from its source (otherwise 'adapted' is a false claim)",
          src != pub, "source and published digests are equal")

listed = {r for r, _ in verbatim} | {r for r, _, _ in adapted}
copied_here = {"scripts/tautological_control_gate.py",
               "scripts/tests/test_tautological_control_gate.py",
               "schema/emit_reason_codes.yaml"}
check("Q4 the non-Japanese copies are listed too",
      copied_here <= listed, str(sorted(copied_here - listed)))
check("Q5 all seven copies are accounted for", len(listed) == 7, f"{len(listed)} listed")

print("== the provenance anchor is stated consistently ==")
anchors = set(re.findall(r"\b([0-9a-f]{40})\b", README)) | set(re.findall(r"\b([0-9a-f]{40})\b", JA))
check("A1 exactly one anchor commit is referenced", len(anchors) == 1, str(anchors))
check("A2 it appears in both documents",
      all(any(a in doc for a in anchors) for doc in (README, JA)))

print("== the repository does not claim priority or superiority ==")
# ADR-0002 in the private repository makes a prior-art check a precondition of
# publication. That check has not been performed, so the mitigation is
# structural rather than a promise: the terms are declared in one place and a
# failing test is what keeps them out.
rules = json.loads((REPO / "config/claim_terms.json").read_text(encoding="utf-8"))
banned = rules["banned_terms"]
check("R0 **negative control**: the banned list is non-empty", len(banned) >= 5,
      f"{len(banned)} terms")
for rel in rules["guarded_files"]:
    body = (REPO / rel).read_text(encoding="utf-8").lower()
    found = sorted({b for b in banned if b.lower() in body})
    check(f"R1 {rel} makes no priority or superiority claim", found == [], str(found))
anchor = rules["required_anchor"]
check("R2 the disclaimer is present in README", anchor in README, anchor)
check("R3 **negative control**: the guard can fail",
      any(b.lower() in (anchor + " " + banned[0]).lower() for b in banned),
      "the matcher does not match its own term, so R1 proves nothing")

print(f"\ndocs-parity: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
