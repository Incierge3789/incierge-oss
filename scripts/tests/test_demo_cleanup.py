#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The demo's interrupt cleanup, observed firing.

`examples/minimal/run.sh` plants payloads in the repository root on purpose, to
show the scanner catching them. If the run is interrupted between planting and
removal, that file stays, and every later commit is rejected by the content
guard — correct behaviour, baffling cause. A `trap ... EXIT INT TERM` was added
for that.

It was then listed as **not fixed**, because nobody had ever seen it fire, and
by this repository's own rule a guard whose firing has not been observed is
treated as absent. This is that observation.

  A. the planted file really does exist mid-run — otherwise everything below is
     vacuous
  B. SIGINT during that window leaves no planted file behind
  C. **negative control** — an uninterrupted run also leaves none, so B is not
     passing because the file was never created
  D. **negative control** — with the trap removed, the same interruption *does*
     leave the file behind, so B is measuring the trap and not something else

D is the one that matters. Without it, B would pass just as happily if the shell
happened to clean up on its own.

The wait is made deterministic by a shim on $PYTHON that sleeps only for the
invocation that scans the planted file. Nothing in the shipped script changes.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
PLANTED = "_demo_planted.txt"

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


def build(tmp: str, keep_trap: bool = True) -> pathlib.Path:
    work = pathlib.Path(tmp) / ("with_trap" if keep_trap else "no_trap")
    shutil.copytree(REPO, work, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    shutil.copy(work / "config/literals.example.json", work / "config/literals.json")
    if not keep_trap:
        run_sh = work / "examples/minimal/run.sh"
        src = run_sh.read_text(encoding="utf-8")
        src = src.replace("trap 'rm -rf \"$TMP\" \"$PLANTED\"' EXIT INT TERM",
                          "trap 'rm -rf \"$TMP\"' EXIT")
        run_sh.write_text(src, encoding="utf-8")
    shim = work / "slow_python.sh"
    shim.write_text(
        "#!/bin/sh\n"
        "# sleep only for the invocation that scans the planted file, so the\n"
        "# interrupt lands inside the window the trap exists for\n"
        'case "$*" in *_demo_planted*) sleep 5 ;; esac\n'
        'exec python3 "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return work


def run_until_planted(work: pathlib.Path, timeout: float = 30.0):
    env = dict(os.environ, PYTHON=str(work / "slow_python.sh"))
    proc = subprocess.Popen(["sh", "examples/minimal/run.sh"], cwd=work, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    target = work / PLANTED
    deadline = time.monotonic() + timeout
    seen = False
    while time.monotonic() < deadline:
        if target.exists():
            seen = True
            break
        if proc.poll() is not None:
            break
        time.sleep(0.005)
    return proc, seen


def interrupt(proc, grace: float = 20.0):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait(timeout=grace)


with tempfile.TemporaryDirectory() as tmp:
    print("== A/B. interrupted run, trap in place ==")
    work = build(tmp, keep_trap=True)
    proc, seen = run_until_planted(work)
    check("A1 the planted file exists mid-run (otherwise B is vacuous)", seen,
          "never observed; the timing shim did not hold the window open")
    interrupt(proc)
    left = (work / PLANTED).exists()
    check("B1 SIGINT leaves no planted file behind", not left,
          f"{PLANTED} survived the interrupt")

    print("== C. uninterrupted run ==")
    env = dict(os.environ, PYTHON="python3")
    done = subprocess.run(["sh", "examples/minimal/run.sh"], cwd=work, env=env,
                          capture_output=True, text=True, timeout=300)
    check("C1 **negative control**: a complete run also leaves none",
          not (work / PLANTED).exists() and done.returncode == 0,
          f"rc={done.returncode}")

    print("== D. the trap is what did it ==")
    bare = build(tmp, keep_trap=False)
    proc2, seen2 = run_until_planted(bare)
    check("D0 the planted file exists mid-run here too", seen2, "window not observed")
    interrupt(proc2)
    survived = (bare / PLANTED).exists()
    check("D1 **negative control**: without the trap the file DOES survive", survived,
          "removing the trap changed nothing, so B was not measuring the trap")

print(f"\ndemo-cleanup: FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
