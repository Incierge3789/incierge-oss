#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Forensic content scanner. Single definition point: docs/prereg.scan.md.

Why this exists
---------------
A publication boundary that lives in a reviewer's attention is not a boundary.
This scanner is the machine form of the boundary: it reads the frozen pattern
table out of ``docs/prereg.scan.md`` and refuses to declare a file clean unless
it actually read it.

Design rules that are not negotiable here
----------------------------------------
* **The pattern table is not duplicated.** It is parsed out of the pre-registration
  document. Editing the document edits the scanner.
* **Undecidable is not clean.** Missing pattern table, missing literals file,
  unreadable file, or binary content all exit 2. "I could not look" never renders
  as "there was nothing there".
* **No post-hoc line exclusions.** The only exclusions are the ones declared in
  the pattern table before the scan ran.

Exit codes
----------
``0`` no hits, and every requested target was actually scanned.
``1`` at least one hit.
``2`` the scan could not be completed (fail-closed).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import re
import subprocess
import sys
import unicodedata

FENCE = re.compile(r"^```json\s*$")
FENCE_END = re.compile(r"^```\s*$")


class Undecidable(Exception):
    """The scan cannot be completed. Never downgraded to 'clean'."""


# --------------------------------------------------------------------------
# normalization
# --------------------------------------------------------------------------

# Declared confusable folding, prereg.scan.md §2 step 4. Cross-review (cursor,
# P0, 2026-08-15) got a literal past the scanner by spelling it with a Cyrillic
# character that renders identically. This is the common half of that attack;
# it is NOT the full Unicode confusables table, and §2 says so.
CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "ԛ": "q", "ԝ": "w", "һ": "h", "т": "t",
    "ο": "o", "α": "a", "ε": "e", "ρ": "p", "ι": "i",
    "κ": "k", "τ": "t", "υ": "u", "χ": "x", "ν": "v",
}
_CONFUSABLE_TABLE = str.maketrans(CONFUSABLES)

# Combining marks are stripped only in the Latin/Greek/Cyrillic diacritic
# blocks and the variation selectors. Stripping every Mn (the first attempt)
# corrupted scripts that need combining marks to spell ordinary words —
# Devanagari nukta, Arabic harakat, Ainu kana — which is a way of mangling text
# rather than normalizing it (agy, P1).
_STRIPPED_MARKS = (
    tuple(range(0x0300, 0x0370))   # combining diacritical marks
    + tuple(range(0x1AB0, 0x1B00))  # combining diacritical marks extended
    + tuple(range(0x1DC0, 0x1E00))  # combining diacritical marks supplement
    + tuple(range(0x20D0, 0x2100))  # combining marks for symbols
    + tuple(range(0xFE00, 0xFE10))  # variation selectors
)
_MARKS = frozenset(chr(c) for c in _STRIPPED_MARKS)


def _fold_confusables(token: str) -> str:
    """Fold lookalikes only inside a token that mixes scripts.

    A token written entirely in Greek or Cyrillic is ordinary text in that
    language, and folding it produced false positives: a Greek word folded into
    something that matched an identifier pattern and disqualified an innocent
    file (agy, P1; the worked example is in docs/prereg.scan.md §9). The attack
    this defends against is a lookalike smuggled *into* a Latin word, so folding
    is applied only where Latin and a confusable script appear in one token.
    """
    if not any(ch in CONFUSABLES for ch in token):
        return token
    if not any("a" <= ch <= "z" for ch in token):
        return token
    return token.translate(_CONFUSABLE_TABLE)


def normalize(text: str) -> str:
    """The normalization declared in prereg.scan.md §2.

    NFKC, casefold, drop format characters and Latin-range combining marks,
    then fold declared confusables in mixed-script tokens. Casefolding runs
    before the strip because casefolding some characters *produces* combining
    marks, and stripping first would leave those behind (agy, P1).
    """
    t = unicodedata.normalize("NFKC", text).casefold()
    t = "".join(ch for ch in t
                if unicodedata.category(ch) != "Cf" and ch not in _MARKS)
    return re.sub(r"\S+", lambda m: _fold_confusables(m.group(0)), t)


def _literal_to_regex(literal: str) -> str:
    """Separator expansion: '-', '_' and space inside a literal become [\\s\\-_]*."""
    parts = [p for p in re.split(r"[-_\s]+", literal) if p]
    if not parts:
        raise Undecidable(f"empty literal in literals file: {literal!r}")
    return r"[\s\-_]*".join(re.escape(p) for p in parts)


# --------------------------------------------------------------------------
# pattern table
# --------------------------------------------------------------------------

def load_prereg(path: pathlib.Path) -> dict:
    """Parse the first ```json fenced block of the pre-registration document."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise Undecidable(f"pattern table unreadable: {path} ({e})") from e
    block, inside = [], False
    for line in lines:
        if not inside and FENCE.match(line):
            inside = True
            continue
        if inside and FENCE_END.match(line):
            break
        if inside:
            block.append(line)
    if not block:
        raise Undecidable(f"no ```json pattern table found in {path}")
    try:
        return json.loads("\n".join(block))
    except json.JSONDecodeError as e:
        raise Undecidable(f"pattern table is not valid JSON: {path} ({e})") from e


def load_literals(path: pathlib.Path | None) -> dict:
    """Load the external literal lists. Absent is NOT empty — it is undecidable."""
    if path is None:
        raise Undecidable("no --literals given; the literal classes cannot be evaluated")
    if not path.is_file():
        raise Undecidable(
            f"literals file missing: {path}. Absence is not emptiness — "
            f"copy config/literals.example.json to config/literals.json first")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Undecidable(f"literals file unreadable: {path} ({e})") from e
    if not isinstance(data, dict):
        raise Undecidable(f"literals file must be a JSON object: {path}")
    return data


class Pattern:
    __slots__ = ("cls", "name", "rx", "excl_g1", "excl_compounds", "severity",
                 "target", "scan_paths")

    def __init__(self, cls, name, rx, excl_g1=None, excl_compounds=(),
                 severity="fail", target="content", scan_paths=False):
        self.cls = cls
        self.name = name
        self.rx = rx
        self.excl_g1 = excl_g1
        self.excl_compounds = tuple(excl_compounds)
        self.severity = severity
        self.target = target
        self.scan_paths = scan_paths


def _compile_inline(cid, spec, severity, target, scan_paths):
    try:
        rx = re.compile(spec["regex"])
    except (KeyError, re.error) as e:
        raise Undecidable(f"bad pattern in class {cid}: {e}") from e
    g1 = spec.get("exclude_if_group1_matches")
    try:
        g1rx = re.compile(g1) if g1 else None
    except re.error as e:
        raise Undecidable(f"bad exclusion in {cid}/{spec.get('name')}: {e}") from e
    return Pattern(cid, spec.get("name") or "unnamed", rx, g1rx,
                   severity=severity, target=target,
                   scan_paths=bool(spec.get("scan_paths", scan_paths)))


def compile_patterns(prereg: dict, literals: dict) -> tuple:
    """Build the compiled pattern set. Any surprise in the table is undecidable.

    Returns (patterns, declared_empty) where declared_empty maps a class id to
    the reason its literal list is empty. An empty list without a declared
    reason is undecidable — silence and absence are not the same reading.
    """
    out, declared_empty = [], {}
    for cls in prereg.get("classes") or []:
        cid = cls.get("id")
        if not cid:
            raise Undecidable("a class in the pattern table has no id")
        severity = cls.get("severity", "fail")
        if severity not in ("fail", "warn"):
            raise Undecidable(f"class {cid} has unknown severity {severity!r}")
        # No default. Whether a class's patterns are applied to file names is a
        # decision with false positives on one side and a blind spot on the
        # other, so the table has to state it rather than inherit it.
        if "scan_paths" not in cls:
            raise Undecidable(f"class {cid} does not declare scan_paths")
        scan_paths = bool(cls["scan_paths"])
        source = cls.get("source")
        for spec in cls.get("path_patterns") or []:
            out.append(_compile_inline(cid, spec, severity, "path", True))
        if source == "inline":
            for spec in cls.get("patterns") or []:
                out.append(_compile_inline(cid, spec, severity, "content", scan_paths))
        elif source == "external_literal_file":
            entry = literals.get(cid)
            if entry is None:
                raise Undecidable(
                    f"literals file has no section '{cid}' — the class cannot be evaluated")
            items = entry.get("literals")
            if not isinstance(items, list):
                raise Undecidable(f"literals section '{cid}' is not a list")
            if not items:
                reason = entry.get("declared_empty_reason")
                if not reason:
                    raise Undecidable(
                        f"literals section '{cid}' is empty with no declared_empty_reason — "
                        f"an empty class cannot be read as 'nothing to find'")
                declared_empty[cid] = reason
                continue
            for item in items:
                if isinstance(item, str):
                    lit, compounds = item, ()
                elif isinstance(item, dict):
                    lit = item.get("literal")
                    compounds = item.get("exclude_compounds") or ()
                    if not isinstance(lit, str):
                        raise Undecidable(f"literal entry without 'literal' in {cid}")
                else:
                    raise Undecidable(f"unsupported literal entry type in {cid}")
                rx = re.compile(_literal_to_regex(normalize(lit)))
                out.append(Pattern(cid, f"{cid}:{normalize(lit)}", rx, None,
                                   [normalize(c) for c in compounds],
                                   severity=severity, target="content",
                                   scan_paths=scan_paths))
        else:
            raise Undecidable(f"class {cid} has unknown source {source!r}")
    if not out:
        raise Undecidable("the compiled pattern set is empty — refusing to call anything clean")
    return out, declared_empty


def positive_controls(prereg: dict, literals: dict) -> dict:
    """class id -> declared positive-control payload."""
    ctrl = {}
    for cls in prereg.get("classes") or []:
        cid = cls["id"]
        if cls.get("source") == "external_literal_file":
            entry = literals.get(cid) or {}
            pc = entry.get("positive_control")
        else:
            pc = cls.get("positive_control")
        if pc:
            ctrl[cid] = pc
    return ctrl


# --------------------------------------------------------------------------
# scanning
# --------------------------------------------------------------------------

def _suppressed_by_compound(line: str, span: tuple, compounds) -> bool:
    for comp in compounds:
        start = 0
        while True:
            i = line.find(comp, start)
            if i < 0:
                break
            if i <= span[0] and span[1] <= i + len(comp):
                return True
            start = i + 1
    return False


def _record(p, path, lineno, m):
    return {"path": path, "line": lineno, "class": p.cls, "pattern": p.name,
            "severity": p.severity, "matched": m.group(0)[:80]}


def scan_path_name(rel: str, patterns: list) -> list:
    """Match against the relative path itself, with **every** pattern.

    Cross-review (cursor, P0) pointed out that a file called
    `people/<withheld name>.txt` with innocuous contents used to pass: only the
    one declared path pattern was applied to paths, so a filename was a place
    to put withheld material where nothing looked.

    Applying *every* pattern was the wrong correction, and the next round said
    so (agy, P0): ordinary source paths in unrelated projects became violations.
    Which patterns look at names is now declared per class in the table, so the
    trade is visible instead of incidental. The worked examples are in
    docs/prereg.scan.md §9 — which is not itself scanned, so they can be spelled
    out there without disqualifying the file they are written in.
    """
    selected = [p for p in patterns if p.target == "path" or p.scan_paths]
    return _match_line(normalize(rel), selected, rel, 0)


def _match_line(line: str, patterns: list, path: str, lineno: int) -> list:
    """Apply patterns to one normalized line, honouring the declared exclusions.

    Shared by the path scan and the content scan on purpose: an exclusion that
    applied to file contents but not to file names would be two rules wearing
    one name.
    """
    hits = []
    for p in patterns:
        for m in p.rx.finditer(line):
            if p.excl_g1 is not None and m.lastindex:
                if p.excl_g1.match(m.group(1) or ""):
                    continue
            if p.excl_compounds and _suppressed_by_compound(line, m.span(), p.excl_compounds):
                continue
            hits.append(_record(p, path, lineno, m))
    return hits


def scan_text(text: str, patterns: list, path: str) -> list:
    content = [p for p in patterns if p.target == "content"]
    hits = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = normalize(raw)
        if line:
            hits.extend(_match_line(line, content, path, lineno))
    return hits


def is_excluded(rel: str, globs) -> bool:
    if rel == ".git" or rel.startswith(".git/"):
        return True
    return any(fnmatch.fnmatch(rel, g) for g in globs)


def read_target(root: pathlib.Path, rel: str, staged: bool) -> bytes:
    if staged:
        r = subprocess.run(["git", "-C", str(root), "show", f":{rel}"],
                           capture_output=True)
        if r.returncode != 0:
            raise Undecidable(f"cannot read staged content of {rel}")
        return r.stdout
    p = root / rel
    try:
        return p.read_bytes()
    except OSError as e:
        raise Undecidable(f"cannot read {rel}: {e}") from e


def scan_paths(root: pathlib.Path, rels, prereg: dict, patterns: list,
               staged: bool = False) -> dict:
    globs = prereg.get("excluded_paths") or []
    binary_policy = prereg.get("binary_policy", "reject")
    found, scanned, skipped, unscannable = [], [], [], []
    for rel in rels:
        if is_excluded(rel, globs):
            skipped.append(rel)
            continue
        found.extend(scan_path_name(rel, patterns))
        blob = read_target(root, rel, staged)
        if b"\0" in blob[:8192]:
            if binary_policy == "reject":
                unscannable.append({"path": rel, "why": "binary (NUL in first 8KiB)"})
                continue
            raise Undecidable(f"unknown binary_policy {binary_policy!r}")
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError as e:
            unscannable.append({"path": rel, "why": f"not utf-8: {e}"})
            continue
        found.extend(scan_text(text, patterns, rel))
        scanned.append(rel)
    return {"hits": [h for h in found if h["severity"] == "fail"],
            "warnings": [h for h in found if h["severity"] == "warn"],
            "scanned": scanned, "skipped_by_pattern_table": skipped,
            "unscannable": unscannable}


def staged_paths(root: pathlib.Path) -> list:
    # ACMRT, not ACMR. A type change — a tracked regular file replaced by a
    # symlink — is a staged change that the shorter filter walked straight
    # past, and `git show :path` on a symlink returns its target, which is
    # somewhere to put a string. Deletions stay out: there is nothing to read.
    r = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only",
         "--diff-filter=ACMRT"], capture_output=True, text=True)
    if r.returncode != 0:
        raise Undecidable("cannot enumerate staged files — not reading that as 'no violations'")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def all_paths(root: pathlib.Path) -> tuple:
    """The publication population.

    Inside a git work tree that is the tracked set, because that is what would
    actually be published; build caches and ignored scratch are not part of it.
    Outside one it is every file on disk, and the caller is told which
    population was used — a coverage claim that does not say what it covered is
    not a coverage claim.
    """
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                       capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip("\0").strip():
        return [f for f in r.stdout.split("\0") if f], "git-tracked"
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            out.append(p.relative_to(root).as_posix())
    return out, "filesystem-walk"


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    here = pathlib.Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="forensic content scan (fail-closed)")
    ap.add_argument("--root", default=str(here), help="repository root to scan")
    ap.add_argument("--prereg", default=None, help="path to prereg.scan.md")
    ap.add_argument("--literals", default=None, help="path to literals JSON")
    ap.add_argument("--paths", nargs="*", help="explicit paths, relative to --root")
    ap.add_argument("--paths-from", help="file with one relative path per line")
    ap.add_argument("--staged", action="store_true", help="scan git staged content")
    ap.add_argument("--all", action="store_true", help="scan every file under --root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--log", help="append one JSON object per hit to this file")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)

    root = pathlib.Path(a.root).resolve()
    prereg_path = pathlib.Path(a.prereg) if a.prereg else here / "docs/prereg.scan.md"
    lit_path = pathlib.Path(a.literals) if a.literals else here / "config/literals.json"

    try:
        prereg = load_prereg(prereg_path)
        literals = load_literals(lit_path)
        patterns, declared_empty = compile_patterns(prereg, literals)
        if a.paths:
            rels = list(a.paths)
        elif a.paths_from:
            rels = [l.strip() for l in
                    pathlib.Path(a.paths_from).read_text(encoding="utf-8").splitlines()
                    if l.strip()]
        elif a.staged:
            rels = staged_paths(root)
        elif a.all:
            rels, population = all_paths(root)
            print(f"population: {population} ({len(rels)} file(s))", file=sys.stderr)
        else:
            raise Undecidable("no target selected (--staged / --all / --paths / --paths-from)")
        res = scan_paths(root, rels, prereg, patterns, staged=a.staged)
    except Undecidable as e:
        print(f"scan UNDECIDABLE: {e}", file=sys.stderr)
        print("  refusing to report 'clean' for a population that was not read",
              file=sys.stderr)
        return 2

    res["patterns"] = len(patterns)
    res["classes"] = sorted({p.cls for p in patterns})
    res["declared_empty_classes"] = declared_empty

    if a.log:
        with open(a.log, "a", encoding="utf-8") as fh:
            for h in res["hits"] + res["warnings"]:
                fh.write(json.dumps(h, ensure_ascii=False) + "\n")

    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for h in res["hits"]:
            print(f"HIT {h['path']}:{h['line']} [{h['class']}/{h['pattern']}] {h['matched']}",
                  file=sys.stderr)
        for w in res["warnings"]:
            print(f"WARN {w['path']}:{w['line']} [{w['class']}/{w['pattern']}] {w['matched']}",
                  file=sys.stderr)
        for u in res["unscannable"]:
            print(f"UNSCANNABLE {u['path']} — {u['why']}", file=sys.stderr)
        for cid, why in declared_empty.items():
            print(f"DECLARED-EMPTY {cid} — {why}", file=sys.stderr)
        print(f"scanned {len(res['scanned'])} file(s) with {len(patterns)} pattern(s); "
              f"skipped {len(res['skipped_by_pattern_table'])} by pattern table; "
              f"{len(res['hits'])} hit(s); {len(res['warnings'])} warning(s); "
              f"{len(res['unscannable'])} unscannable",
              file=sys.stderr if (res["hits"] or res["unscannable"]) else sys.stdout)

    if res["unscannable"]:
        return 2
    return 1 if res["hits"] else 0


if __name__ == "__main__":
    sys.exit(main())
