#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The guards are actually on git's path, not merely runnable.

Every other control in this suite executes the hook scripts directly. That
proves they behave correctly when called, and says nothing about whether git
calls them. A correct check that is never invoked is worth exactly nothing, and
"the script works" is the reassuring half of that sentence.

So this one drives real `git commit` and real `git push` and asserts the
outcome by the state that would have changed:

  A. a commit carrying planted payloads is refused, and HEAD does not move
  B. **negative control** — a clean commit in the same repository succeeds, so
     A is not passing because commits are broken
  C. a push to a remote that is not the single permitted one is refused, and
     the receiving repository ends up with zero objects
  D. **negative control** — the push guard accepts the permitted remote, so C
     is not passing because pushes are broken
  E. a staged **type change** is scanned. Neither reviewer found this; the
     staged-file enumeration omitted `T`, so replacing a tracked file with a
     symlink slipped past, and a symlink's target is a place to put a string

C pushes to a throwaway bare repository on disk. Nothing leaves the machine,
and the assertion is that nothing arrives even there.
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


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


def clean_env(home: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["HOME"] = home
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "control"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "control@example.com"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(args, cwd, env, **kw):
    return subprocess.run(["git", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=300, **kw)


def payload_text() -> str:
    pr = S.load_prereg(REPO / "docs/prereg.scan.md")
    li = S.load_literals(REPO / "config/literals.json")
    return "\n".join(p for cid, p in sorted(S.positive_controls(pr, li).items())
                     if cid != "e_third_party_oss") + "\n"


with tempfile.TemporaryDirectory() as tmp:
    env = clean_env(tmp)
    work = pathlib.Path(tmp) / "work"
    shutil.copytree(REPO, work, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    git(["init", "-q", "-b", "main"], work, env)
    git(["config", "core.hooksPath", "scripts/hooks"], work, env)
    git(["add", "-A"], work, env)
    first = git(["commit", "-q", "-m", "base"], work, env)
    base_head = git(["rev-parse", "HEAD"], work, env).stdout.strip()
    check("setup: the baseline commit was created", first.returncode == 0 and len(base_head) == 40,
          first.stderr[-300:])

    print("== A/B. git commit ==")
    (work / "planted_e2e.txt").write_text(payload_text(), encoding="utf-8")
    git(["add", "planted_e2e.txt"], work, env)
    bad = git(["commit", "-q", "-m", "should be refused"], work, env)
    head_now = git(["rev-parse", "HEAD"], work, env).stdout.strip()
    check("A1 git commit is refused", bad.returncode != 0, f"rc={bad.returncode}")
    check("A2 and HEAD did not move", head_now == base_head, f"{base_head} -> {head_now}")
    check("A3 the refusal came from the content guard",
          "pre-commit" in bad.stderr and "HIT" in bad.stderr, bad.stderr[-300:])
    git(["reset", "-q", "HEAD", "planted_e2e.txt"], work, env)
    (work / "planted_e2e.txt").unlink()

    (work / "ordinary.txt").write_text("nothing withheld here\n", encoding="utf-8")
    git(["add", "ordinary.txt"], work, env)
    good = git(["commit", "-q", "-m", "ordinary"], work, env)
    head_after = git(["rev-parse", "HEAD"], work, env).stdout.strip()
    check("B1 **negative control**: an ordinary commit succeeds", good.returncode == 0,
          good.stderr[-300:])
    check("B2 and HEAD moved", head_after != base_head, head_after)

    print("== E. a staged type change is not a blind spot ==")
    # Found by self-falsification, not by either reviewer: the staged-file
    # enumeration used --diff-filter=ACMR, which omits T. Replacing a tracked
    # file with a symlink is a staged change, and `git show :path` on a symlink
    # returns its target — a place to put a string.
    target = payload_text().splitlines()[0]
    (work / "ordinary.txt").unlink()
    (work / "ordinary.txt").symlink_to(target)
    git(["add", "ordinary.txt"], work, env)
    kinds = git(["diff", "--cached", "--name-status"], work, env).stdout
    check("E0 the change really is staged as a type change",
          kinds.startswith("T"), kinds.strip()[:80])
    typed = git(["commit", "-q", "-m", "type change"], work, env)
    check("E1 a staged type change is scanned and refused", typed.returncode != 0,
          f"rc={typed.returncode}")
    check("E2 and the payload in the link target is what was caught",
          "HIT" in typed.stderr and "ordinary.txt" in typed.stderr, typed.stderr[-300:])
    git(["reset", "-q", "--hard", "HEAD"], work, env)

    print("== C/D. git push ==")
    bare = pathlib.Path(tmp) / "elsewhere.git"
    git(["init", "-q", "--bare", str(bare)], pathlib.Path(tmp), env)
    git(["remote", "add", "elsewhere", str(bare)], work, env)
    pushed = git(["push", "elsewhere", "main"], work, env)
    counted = git(["count-objects", "-v"], bare, env).stdout
    objects = next((int(l.split(":")[1]) for l in counted.splitlines()
                    if l.startswith("count:")), -1)
    check("C1 the push is refused", pushed.returncode != 0, f"rc={pushed.returncode}")
    check("C2 the refusal came from the push guard", "pre-push REJECT" in pushed.stderr,
          pushed.stderr[-300:])
    check("C3 **and the receiving repository got nothing**", objects == 0,
          f"{objects} objects arrived")

    allowed = [l.split("#", 1)[0].strip() for l in
               (work / "config/allowed_remote.txt").read_text(encoding="utf-8").splitlines()]
    allowed = next(a for a in allowed if a)
    direct = subprocess.run([str(work / "scripts/hooks/pre-push"), "origin", allowed],
                            cwd=work, env=env, capture_output=True, text=True, timeout=60)
    check("D1 **negative control**: the permitted remote is accepted by the same hook",
          direct.returncode == 0, direct.stderr[-300:])

print(f"\nhooks-are-invoked: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
