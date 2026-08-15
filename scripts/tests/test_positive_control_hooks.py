#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Positive controls for both guards. **The guards are only real if seen firing.**

Content guard (scripts/hooks/pre-commit):
  A. a staged file carrying one payload per class (a)(b)(c)(d) is rejected,
     and every class is named in the rejection
  B. **negative control** — the same sandbox with nothing planted is accepted,
     so A cannot pass merely because the sandbox is dirty
  C. class (e) is severity warn: the commit is accepted *and* reported
  D. fail-closed — with the literal list removed, the guard rejects rather
     than treating the missing class as empty

Push guard (scripts/hooks/pre-push):
  E. the one allowed remote is accepted
  F. any other remote is rejected
  G. a remote on the forbidden list is rejected
  H. no remote supplied at all is rejected (undecidable, not permitted)
  I. hooks outside their own repository reject (marker file removed)
  J. rejections are appended to a log that lives outside the work tree

The payloads are never written into this file. They are read from the single
definition point (docs/prereg.scan.md and the literal list), so that narrowing a
pattern is caught here rather than silently making the control a no-op.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import scan_forensic as S  # noqa: E402

FAILED = []
REQUIRED_CLASSES = ["a_proper_noun", "b_ip_identifier", "c_secret", "d_person_shape",
                    "d_person_literal"]


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


def payloads() -> dict:
    prereg = S.load_prereg(REPO / "docs/prereg.scan.md")
    lits = S.load_literals(REPO / "config/literals.json")
    return S.positive_controls(prereg, lits)


def clean_env(home: str) -> dict:
    """Strip inherited git state. A fixture that inherits the caller's
    core.hooksPath passes in an interactive shell and nowhere else."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["HOME"] = home
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "control"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "control@example.com"
    return env


def sandbox(tmp: str) -> pathlib.Path:
    """A throwaway clone of the work tree with a fresh index."""
    dst = pathlib.Path(tmp) / "sandbox"
    shutil.copytree(REPO, dst,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    env = clean_env(tmp)
    subprocess.run(["git", "init", "-q"], cwd=dst, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dst, env=env, check=True)
    return dst


def run_hook(hook: str, cwd: pathlib.Path, tmp: str, args=()) -> subprocess.CompletedProcess:
    return subprocess.run([str(cwd / "scripts/hooks" / hook), *args],
                          cwd=cwd, env=clean_env(tmp),
                          capture_output=True, text=True, timeout=300)


ALLOWED = "https://github.com/Incierge3789/incierge-oss.git"

print("== A/B/C/D. content guard ==")
with tempfile.TemporaryDirectory() as tmp:
    pc = payloads()
    box = sandbox(tmp)
    env = clean_env(tmp)

    # B first: the negative control establishes that a quiet sandbox is accepted
    clean = run_hook("pre-commit", box, tmp)
    check("B1 **negative control**: nothing planted -> accepted",
          clean.returncode == 0, f"rc={clean.returncode} {clean.stderr[-400:]}")

    planted = box / "planted.txt"
    planted.write_text("\n".join(f"{cid}: {p}" for cid, p in sorted(pc.items())) + "\n",
                       encoding="utf-8")
    subprocess.run(["git", "add", "planted.txt"], cwd=box, env=env, check=True)
    hit = run_hook("pre-commit", box, tmp)
    check("A1 **positive**: a payload per class -> rejected",
          hit.returncode != 0, f"rc={hit.returncode}")
    for cid in REQUIRED_CLASSES:
        check(f"A2 rejection names {cid}", cid in hit.stderr,
              hit.stderr[-500:])
    check("A3 the two runs actually differ (the control is not tautological)",
          clean.returncode != hit.returncode,
          f"{clean.returncode} vs {hit.returncode}")

    subprocess.run(["git", "rm", "-q", "--cached", "planted.txt"], cwd=box, env=env, check=True)
    planted.unlink()

    # C: warn severity is reported without blocking
    mit = box / "vendored_notice.txt"
    mit.write_text(pc["e_third_party_oss"] + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "vendored_notice.txt"], cwd=box, env=env, check=True)
    warned = run_hook("pre-commit", box, tmp)
    check("C1 class (e) does not block", warned.returncode == 0,
          f"rc={warned.returncode} {warned.stderr[-400:]}")
    check("C2 class (e) is still reported", "e_third_party_oss" in warned.stderr,
          warned.stderr[-400:])
    subprocess.run(["git", "rm", "-q", "--cached", "vendored_notice.txt"],
                   cwd=box, env=env, check=True)
    mit.unlink()

    # D: fail-closed on a missing literal list
    (box / "config/literals.json").unlink()
    closed = run_hook("pre-commit", box, tmp)
    check("D1 missing literal list -> reject (absence is not emptiness)",
          closed.returncode != 0, f"rc={closed.returncode}")
    check("D2 and it says so", "literals file missing" in closed.stderr,
          closed.stderr[-300:])

print("== E..J. push guard ==")
with tempfile.TemporaryDirectory() as tmp:
    box = sandbox(tmp)
    ok = run_hook("pre-push", box, tmp, ["origin", ALLOWED])
    check("E1 the one allowed remote is accepted", ok.returncode == 0,
          f"rc={ok.returncode} {ok.stderr[-300:]}")

    other = run_hook("pre-push", box, tmp,
                     ["origin", "https://github.com/someone/else.git"])
    check("F1 any other remote is rejected", other.returncode != 0, other.stdout[-200:])

    forbidden_url = [l.strip() for l in
                     (box / "config/forbidden_remotes.txt").read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")][0]
    forb = run_hook("pre-push", box, tmp, ["origin", forbidden_url])
    check("G1 a forbidden remote is rejected", forb.returncode != 0, forb.stdout[-200:])

    none = run_hook("pre-push", box, tmp)
    check("H1 no remote supplied -> rejected as undecidable", none.returncode != 0,
          none.stdout[-200:])
    check("H2 and it says undecidable rather than mismatched",
          "not supplied" in none.stderr, none.stderr[-200:])

    log = box / ".git/push_guard_rejections.log"
    check("J1 rejections are logged outside the work tree", log.is_file(), str(log))
    if log.is_file():
        lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        check("J2 one line per rejection so far", len(lines) == 3, f"{len(lines)} lines")

    (box / "config/allowed_remote.txt").unlink()
    stray = run_hook("pre-push", box, tmp, ["origin", ALLOWED])
    check("I1 hooks outside their own repository reject", stray.returncode != 0,
          stray.stdout[-200:])

print(f"\npositive-control-hooks: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
