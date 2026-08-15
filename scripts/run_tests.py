#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every control in scripts/tests/.

Enumerating the suite is itself a check: if the glob returns nothing, that is
reported as a failure rather than as a green run over zero tests.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = sorted((ROOT / "scripts/tests").glob("test_*.py"))


def main() -> int:
    if not TESTS:
        print("run_tests: no tests found — that is a failure, not a pass", file=sys.stderr)
        return 2
    failed = []
    for t in TESTS:
        rel = t.relative_to(ROOT).as_posix()
        print(f"\n### {rel}")
        r = subprocess.run([sys.executable, str(t)], cwd=ROOT)
        if r.returncode != 0:
            failed.append((rel, r.returncode))
    print(f"\n=== {len(TESTS) - len(failed)}/{len(TESTS)} test files passed ===")
    for rel, rc in failed:
        print(f"  FAILED {rel} (rc={rc})", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
