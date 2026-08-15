#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controls for the scanner itself.

Grouped by the property being asserted, and every group has a case that must
*not* fire alongside the case that must, because a matcher that matches
everything passes a suite made only of positive cases.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import scan_forensic as S  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


PREREG = REPO / "docs/prereg.scan.md"
LITS = REPO / "config/literals.json"
prereg = S.load_prereg(PREREG)
lits = S.load_literals(LITS)
PATTERNS, EMPTY = S.compile_patterns(prereg, lits)


def hits(text, cls=None):
    got = S.scan_text(text, PATTERNS, "<t>")
    return [h for h in got if cls is None or h["class"] == cls]


print("== normalization ==")
lit = lits["a_proper_noun"]["literals"][0]
base = lit.replace("-", "")
check("N1 the plain literal matches", len(hits(base, "a_proper_noun")) > 0)
check("N2 case is ignored", len(hits(base.upper(), "a_proper_noun")) > 0)
check("N3 full-width is folded to half-width",
      len(hits("".join(chr(ord(c) + 0xFEE0) if "a" <= c <= "z" else c for c in base),
               "a_proper_noun")) > 0)
check("N4 separators expand (space / hyphen / underscore)",
      all(len(hits(lit.replace("-", sep), "a_proper_noun")) > 0 for sep in (" ", "-", "_", "")))
check("N5 **negative**: an unrelated word does not match",
      len(hits("ordinary prose about widgets", "a_proper_noun")) == 0)
# cross-review (cursor, P0): invisible characters and lookalike codepoints
zw = base[:2] + "​" + base[2:]
check("N6 a zero-width space inside the literal does not hide it",
      len(hits(zw, "a_proper_noun")) > 0, repr(zw))
soft = base[:2] + "­" + base[2:]
check("N7 a soft hyphen inside the literal does not hide it",
      len(hits(soft, "a_proper_noun")) > 0, repr(soft))
cyr = base.replace("e", "е", 1) if "e" in base else base.replace("a", "а", 1)
check("N8 a Cyrillic lookalike character does not hide it",
      len(hits(cyr, "a_proper_noun")) > 0, repr(cyr))

print("== the path is scanned, not just the contents ==")
for cls, payload in sorted(S.positive_controls(prereg, lits).items()):
    if cls == "e_third_party_oss":
        continue
    got = S.scan_path_name(f"notes/{payload}.txt", PATTERNS)
    check(f"PP1 {cls} is caught in a file name", any(h["class"] == cls for h in got),
          f"notes/{payload}.txt")
for ordinary in ("docs/architecture.md", "app/users/auth.py", "src/home/index.html",
                 "config.inc.php", "lib/common.inc.h"):
    got = S.scan_path_name(ordinary, PATTERNS)
    check(f"PP2 **negative**: {ordinary} is not flagged", got == [],
          str(got[:2]))
# which classes look at names is a declared decision, not an accident
declared = {c["id"]: c.get("scan_paths") for c in prereg["classes"]}
check("PP3 every class declares scan_paths", all(v is not None for v in declared.values()),
      str([k for k, v in declared.items() if v is None]))
check("PP4 the content-shape class opts out at class level",
      declared.get("c_secret") is False, str(declared))
check("PP5 **but its high-precision members opt back in**",
      any(q.cls == "c_secret" and q.scan_paths for q in PATTERNS),
      "no c_secret pattern is path-scanned, so a key in a file name would pass")

print("== exclusions are pattern-level, and still let the bare literal through ==")
compounded = [e for e in lits.get("d_person_literal", {}).get("literals", [])
              if isinstance(e, dict) and e.get("exclude_compounds")]
if compounded:
    entry = compounded[0]
    comp = entry["exclude_compounds"][0]
    check("X1 the literal inside a declared compound is suppressed",
          len(hits(f"see {comp} here", "d_person_literal")) == 0, comp)
    check("X2 **but the bare literal still fires**",
          len(hits(f"see {entry['literal']} here", "d_person_literal")) > 0,
          entry["literal"])
else:
    check("X0 the shipped literal list declares no compounds, so X1/X2 are unmeasurable "
          "(not asserted as passing)", False,
          "expected at least one exclude_compounds entry to exercise")

# Every pattern that carries an exclusion declares the two cases the exclusion
# must keep apart. They are read from the table, never written here: a copy in
# this file would go stale exactly when the rule was edited, which is the only
# moment this check matters.
inline = [(c["id"], p) for c in prereg["classes"] if c.get("source") == "inline"
          for p in c.get("patterns") or []]
# Two populations, and the difference matters. Every pattern carrying an
# exclusion MUST declare both cases, because an exclusion is where a guard gets
# widened until it excuses everything. Any other pattern MAY declare them, and
# several do — those are the ones a cross-review found holes in, so the case
# that closed the hole is stored next to the pattern rather than in a report.
must = [(cid, p) for cid, p in inline if "exclude_if_group1_matches" in p]
paired = [(cid, p) for cid, p in inline if "example_hit" in p or "example_miss" in p]
check("X0 every exclusion-bearing pattern declares both example cases",
      len(must) > 0 and all("example_hit" in p and "example_miss" in p for _, p in must),
      str([p["name"] for _, p in must if "example_hit" not in p or "example_miss" not in p]))
check("X0b every declared pair is complete",
      all("example_hit" in p and "example_miss" in p for _, p in paired),
      str([p["name"] for _, p in paired if "example_hit" not in p or "example_miss" not in p]))
for cid, p in paired:
    own = [q for q in PATTERNS if q.name == p["name"]]
    # Without this, a renamed or dropped pattern makes X-miss pass over an
    # empty pattern set — the control would go green because nothing was
    # tested (agy, P2).
    check(f"X-own  {p['name']} resolves to a compiled pattern", len(own) == 1,
          f"{len(own)} compiled patterns named {p['name']}")
    if not own:
        continue
    check(f"X-hit  {p['name']} fires on its declared example",
          len(S.scan_text(p["example_hit"], own, "<t>")) > 0, p["example_hit"])
    check(f"X-miss {p['name']} **does not** fire on its declared exclusion",
          len(S.scan_text(p["example_miss"], own, "<t>")) == 0, p["example_miss"])

print("== severity ==")
warn_cls = [c["id"] for c in prereg["classes"] if c.get("severity") == "warn"]
check("S1 at least one class is declared warn", len(warn_cls) > 0, str(warn_cls))
for cid in warn_cls:
    check(f"S2 {cid} patterns carry the warn severity",
          all(p.severity == "warn" for p in PATTERNS if p.cls == cid))
check("S3 every other class is fail",
      all(p.severity == "fail" for p in PATTERNS if p.cls not in warn_cls))

print("== fail-closed ==")
with tempfile.TemporaryDirectory() as tmp:
    t = pathlib.Path(tmp)
    (t / "docs").mkdir()
    missing = S.main(["--root", str(REPO), "--prereg", str(PREREG),
                      "--literals", str(t / "nope.json"), "--paths", "README.md"])
    check("F1 a missing literal list is undecidable, not empty", missing == 2, f"rc={missing}")

    bad = t / "bad.md"
    bad.write_text("```json\n{not json}\n```\n", encoding="utf-8")
    rc = S.main(["--root", str(REPO), "--prereg", str(bad), "--literals", str(LITS),
                 "--paths", "README.md"])
    check("F2 an unparsable pattern table is undecidable", rc == 2, f"rc={rc}")

    binf = t / "b.bin"
    binf.write_bytes(b"\x00\x01\x02binary")
    rc = S.main(["--root", str(t), "--prereg", str(PREREG), "--literals", str(LITS),
                 "--paths", "b.bin"])
    check("F3 a binary file is rejected rather than skipped", rc == 2, f"rc={rc}")

    clean = t / "clean.txt"
    clean.write_text("ordinary text\n", encoding="utf-8")
    rc = S.main(["--root", str(t), "--prereg", str(PREREG), "--literals", str(LITS),
                 "--paths", "clean.txt"])
    check("F4 **negative**: a clean text file returns 0", rc == 0, f"rc={rc}")

print("== the pattern table is not duplicated ==")
# Probes are taken from the table itself. Writing them out here would make this
# file a copy of what it is looking for.
# Every regex, not just the first of each class: cross-review (cursor, P2)
# pointed out that a copy of any later pattern would have gone undetected.
probes = [spec["regex"] for c in prereg["classes"]
          for key in ("patterns", "path_patterns")
          for spec in c.get(key) or []]
copies = []
for p in sorted(REPO.rglob("*")):
    if not p.is_file() or ".git" in p.parts or p == PREREG:
        continue
    try:
        txt = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    found = [pr for pr in probes if pr in txt]
    if found:
        copies.append((p.relative_to(REPO).as_posix(), found[0]))
check("D1 no second copy of the pattern table exists", copies == [], str(copies))
raw = PREREG.read_text(encoding="utf-8")


def escaped(s):
    return json.dumps(s, ensure_ascii=False)[1:-1]


check("D2 **negative control**: the probes are present in the table itself",
      all(escaped(pr) in raw for pr in probes) and len(probes) >= 2,
      f"{len(probes)} probes, missing={[pr for pr in probes if escaped(pr) not in raw]}")

print("== the scan covers the population it claims to ==")
# There is no skip branch here. Cross-review (agy, P1) found the earlier version
# printing SKIP and exiting 0 when .git was absent — from a release tarball, the
# suite would have reported success without ever scanning the repository, which
# is the exact reading ("could not check" as "checked and clean") that the rest
# of this codebase refuses. S.all_paths falls back to the filesystem and says
# which population it used.
files, population = S.all_paths(REPO)
check("C0 the population is non-empty", len(files) > 0, f"{population}: {len(files)}")
res = S.scan_paths(REPO, files, prereg, PATTERNS)
covered = len(res["scanned"]) + len(res["skipped_by_pattern_table"]) + len(res["unscannable"])
check(f"C1 every file in the {population} population is accounted for",
      covered == len(files), f"{covered} of {len(files)}")
check("C2 the repository itself is clean", res["hits"] == [],
      json.dumps(res["hits"][:3], ensure_ascii=False))
check("C3 nothing in it was unreadable", res["unscannable"] == [],
      json.dumps(res["unscannable"][:3], ensure_ascii=False))

print(f"\nscan-forensic: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
