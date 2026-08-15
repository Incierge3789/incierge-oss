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
  G. a remote on the deny-list is rejected, **and the deny-list is what
     rejected it** — ordered after the allow-list it would be unreachable, and
     this case would pass anyway
  H. no remote supplied at all is rejected (undecidable, not permitted)
  I. hooks outside their own repository reject (marker file removed)
  J. rejections are appended to a log outside the work tree, and the one
     acceptance is not logged
  K. an allow-list edited to point at a deny-listed destination is rejected

The payloads are never written into this file. They are read from the single
definition point (docs/prereg.scan.md and the literal list), so that narrowing a
pattern is caught here rather than silently making the control a no-op.
"""
from __future__ import annotations

import hashlib
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


def first_entry(path: pathlib.Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            return line
    raise AssertionError(f"{path} declares nothing")


sys.path.insert(0, str(REPO / "scripts"))
import canonical_remote as C  # noqa: E402


def sha256(s: str) -> str:
    """Digest of the canonical form — the same thing the hook hashes."""
    return C.digest(s)


# Read from the configuration rather than repeating it. Cross-review (agy, P1)
# found this hard-coded here, which is the same single-definition-point break
# the repository asserts it does not have.
ALLOWED = first_entry(REPO / "config/allowed_remote.txt")
FORBIDDEN_FILE = "config/forbidden_remotes.txt"

print("== A/B/C/D. content guard ==")
with tempfile.TemporaryDirectory() as tmp:
    pc = payloads()
    box = sandbox(tmp)
    env = clean_env(tmp)

    # B first: the negative control establishes that a quiet sandbox is accepted
    clean = run_hook("pre-commit", box, tmp)
    check("B1 **negative control**: nothing planted -> accepted",
          clean.returncode == 0, f"rc={clean.returncode} {clean.stderr[-400:]}")

    # One payload per file. Two rounds of review found A2 passing for the wrong
    # reason: first because a bare class name appears in stderr even when the
    # self-check *fails* (cursor P1), then because one payload can trip a
    # second class — the shape control's payload contains the literal control's
    # payload — so a dead class still had its name printed (agy P1). The
    # assertion is now: this class produced a HIT on the file that carries only
    # its own payload.
    planted_files = {}
    for i, (cid, payload) in enumerate(sorted(pc.items())):
        name = f"planted_{i}.txt"
        (box / name).write_text(payload + "\n", encoding="utf-8")
        planted_files[cid] = name
        subprocess.run(["git", "add", name], cwd=box, env=env, check=True)
    hit = run_hook("pre-commit", box, tmp)
    check("A1 **positive**: a payload per class -> rejected",
          hit.returncode != 0, f"rc={hit.returncode}")
    for cid in REQUIRED_CLASSES:
        needle = f"{planted_files[cid]}:"
        lines = [ln for ln in hit.stderr.splitlines()
                 if ln.startswith("HIT ") and needle in ln and f"[{cid}/" in ln]
        check(f"A2 {cid} fires on its own payload alone", len(lines) > 0,
              f"no HIT line for {planted_files[cid]} in class {cid}")
    check("A3 the two runs actually differ (the control is not tautological)",
          clean.returncode != hit.returncode,
          f"{clean.returncode} vs {hit.returncode}")

    for name in planted_files.values():
        subprocess.run(["git", "rm", "-q", "--cached", name], cwd=box, env=env, check=True)
        (box / name).unlink()

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

    # Equivalent spellings of the same destination. Under the earlier string
    # comparison the first of these was rejected although it is the allowed
    # remote, and the deny-list missed every spelling but one (agy, P0).
    host_path = C.canonical(ALLOWED)
    for spelling in (f"git@{host_path.split('/', 1)[0]}:{host_path.split('/', 1)[1]}.git",
                     f"https://{host_path}",
                     f"https://{host_path}.git/"):
        alt = run_hook("pre-push", box, tmp, ["origin", spelling])
        check(f"E2 an equivalent spelling of the allowed remote is accepted: {spelling}",
              alt.returncode == 0, alt.stderr[-200:])

    # The deny-list holds digests, so the control supplies its own entry rather
    # than trying to recover a URL from one. It also asserts *which* rule
    # fired: with the deny-list checked after the allow-list it would be
    # unreachable, and this case would still "pass" — rejected by the
    # allow-list, while the deny-list did nothing.
    fpath = box / FORBIDDEN_FILE
    shipped = [l.split("#", 1)[0].strip() for l in
               fpath.read_text(encoding="utf-8").splitlines()]
    check("G0 the shipped deny-list is not empty",
          len([s for s in shipped if s]) > 0, "an empty deny-list is not a checked deny-list")
    test_url = "https://github.com/forbidden-destination/for-control.git"
    with fpath.open("a", encoding="utf-8") as fh:
        fh.write(sha256(test_url) + "\n")
    forb = run_hook("pre-push", box, tmp, ["origin", test_url])
    check("G1 a remote on the deny-list is rejected", forb.returncode != 0, forb.stdout[-200:])
    ssh_spelling = "git@" + C.canonical(test_url).replace("/", ":", 1)
    forb2 = run_hook("pre-push", box, tmp, ["origin", ssh_spelling])
    check("G3 **and a different spelling of it is also rejected**",
          forb2.returncode != 0 and "forbidden list" in forb2.stderr,
          f"{ssh_spelling}: {forb2.stderr[-200:]}")
    check("G2 and the deny-list is what rejected it, not the allow-list",
          "forbidden list" in forb.stderr, forb.stderr[-200:])

    # the allow-list's own value is checked against the deny-list
    (box / "config/allowed_remote.txt").write_text(test_url + "\n", encoding="utf-8")
    selfforb = run_hook("pre-push", box, tmp, ["origin", test_url])
    check("K1 an allowed remote that is on the deny-list is rejected",
          selfforb.returncode != 0 and "itself on the forbidden list" in selfforb.stderr,
          selfforb.stderr[-200:])
    (box / "config/allowed_remote.txt").write_text(ALLOWED + "\n", encoding="utf-8")

    none = run_hook("pre-push", box, tmp)
    check("H1 no remote supplied -> rejected as undecidable", none.returncode != 0,
          none.stdout[-200:])
    check("H2 and it says undecidable rather than mismatched",
          "not supplied" in none.stderr, none.stderr[-200:])

    log = box / ".git/push_guard_rejections.log"
    check("J1 rejections are logged outside the work tree", log.is_file(), str(log))
    if log.is_file():
        lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        # F1, G1, K1, H1 rejected; E1 was accepted and must not be logged
        check("J2 one line per rejection and none for the four acceptances",
              len(lines) == 5, f"{len(lines)} lines: {lines}")

    (box / "config/allowed_remote.txt").unlink()
    stray = run_hook("pre-push", box, tmp, ["origin", ALLOWED])
    check("I1 hooks outside their own repository reject", stray.returncode != 0,
          stray.stdout[-200:])

print(f"\npositive-control-hooks: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
