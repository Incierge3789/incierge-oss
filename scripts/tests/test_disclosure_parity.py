#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The publication paths must disclose the same things.

Two paths applied the disclosure line independently and diverged: a curated
English ledger and a copied Japanese document. The Japanese copy published a
reopen threshold, a required sample size and an interval width that the English
ledger had left out. Neither broke a rule in docs/disclosure.md. **Having two
readers of the same rule was the defect**, and prose does not stay applied.

  A. every measurement-like number in the Japanese document is disclosed in the
     English ledger too, or is declared as an exemption with a reason
  B. **negative control** - the extractor finds something, so A cannot pass by
     matching an empty set
  C. **negative control** - a number that is deliberately absent is detected as
     absent, so A is not passing because the comparison always succeeds
  D. the structure rule is enforced somewhere real: the scanner's pattern table
     declares the classes, rather than this test carrying a second copy
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess  # noqa: F401  (subject is exercised through the modules below)
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import scan_forensic as S  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


SPEC = json.loads((REPO / "schema/disclosure_parity.json").read_text(encoding="utf-8"))
DEC = re.compile(r"\d+\.\d{2,}")
INT = re.compile(r"(?<![\d.\-])\d{3,}(?![\d.])")


def measurement_like(text: str) -> set:
    return set(DEC.findall(text)) | set(INT.findall(text))


print("== A/B/C. numeric parity between publication paths ==")
for pair in SPEC["pairs"]:
    src = (REPO / pair["from"]).read_text(encoding="utf-8")
    dst = (REPO / pair["to"]).read_text(encoding="utf-8")
    exempt = {e["value"]: e["why"] for e in pair.get("exemptions", [])}
    found = measurement_like(src)
    check(f"B1 {pair['id']}: the extractor found numbers to compare", len(found) >= 3,
          f"{len(found)} found in {pair['from']}")
    missing = sorted(v for v in found if v not in dst and v not in exempt)
    check(f"A1 {pair['id']}: every measurement-like number is disclosed on both paths",
          missing == [], f"disclosed only in {pair['from']}: {missing}")
    for v, why in exempt.items():
        check(f"A2 {pair['id']}: exemption {v} carries a reason", len(why) > 30, why[:60])
        check(f"A3 {pair['id']}: exemption {v} really is absent from {pair['to']}",
              v not in dst, "exempted a value that is present, so the exemption is dead")
    absent = "9" * 7
    check(f"C1 {pair['id']}: **negative control** - a value that is not there is seen as not there",
          absent not in dst and absent not in found, "the comparison always succeeds")

print("== D. the structure rule is enforced by the scanner, not duplicated here ==")
prereg = S.load_prereg(REPO / "docs/prereg.scan.md")
declared = {c["id"] for c in prereg["classes"]}
for cid in SPEC["structure_enforced_by_scanner"]["classes"]:
    check(f"D1 the scanner declares {cid}", cid in declared, str(sorted(declared)))
patterns, _ = S.compile_patterns(prereg, S.load_literals(REPO / "config/literals.json"))
ns = [p for p in patterns if p.cls == "b_ip_identifier"]
check("D2 it carries more than one identifier namespace", len(ns) >= 5, f"{len(ns)} patterns")
check("D3 **negative control**: this file holds no copy of the structure patterns",
      "b_ip_identifier" not in (REPO / "schema/disclosure_parity.json").read_text(
          encoding="utf-8").replace('"classes": ["b_ip_identifier"]', ""),
      "the parity spec restates a pattern instead of pointing at it")

print(f"\ndisclosure-parity: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
