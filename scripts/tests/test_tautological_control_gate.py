#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恒真対照 gate の対照 (TASK-4)。**この検査自身も gate の対象である**。

  A. **陽性**: 恒真の対照を 1 本作ると発火する
  B. **偽陽性**: 正しい対照では発火しない
  C. **鍵不能**: 対照ファイルを列挙できなければ rc=2 (F-097)
  D. 例外は path 集合 ratchet (件数比較へ戻っていない)
  E. gate が pre-commit に配線されている (advisory でない)
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location(
    "tcg", REPO / "scripts/tautological_control_gate.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAILED.append(name)


TAUTOLOGICAL = '''
import importlib.util
SUBJ = importlib.util.spec_from_file_location("x", "/dev/null")


def check(n, c, d=""):
    pass


check("恒真", True)
check("定数比較", 1 == 1)
'''
HONEST = '''
import importlib.util
spec = importlib.util.spec_from_file_location("x", __file__)
SUBJ = importlib.util.module_from_spec(spec)


def check(n, c, d=""):
    pass


check("実測", SUBJ.__name__ == "x")
'''

print("== A/B. 陽性 / 偽陽性 ==")
with tempfile.TemporaryDirectory() as tmp:
    bad = pathlib.Path(tmp, "test_bad.py")
    bad.write_text(TAUTOLOGICAL, encoding="utf-8")
    good = pathlib.Path(tmp, "test_good.py")
    good.write_text(HONEST, encoding="utf-8")
    rb = G.scan_file(bad)
    rg = G.scan_file(good)
    check("A1 **陽性**: 恒真の対照を検出する", len(rb["findings"]) >= 2, str(rb))
    check("A2 どの行かを名指しする", all(f["line"] > 0 for f in rb["findings"]
                                          if f["kind"] == "constant"), str(rb))
    check("B1 **偽陽性対照**: 実測している対照では発火しない",
          rg["findings"] == [], str(rg))
    # **恒真でないことの対照**: 2 つの結果が実際に違う
    check("B2 陽性と偽陽性の結果が実際に別 (対照そのものが恒真でない)",
          len(rb["findings"]) != len(rg["findings"]),
          f'{len(rb["findings"])} vs {len(rg["findings"])}')

print("== C. F-097: 鍵が引けない時 ==")
with tempfile.TemporaryDirectory() as tmp:
    rep = G.audit(pathlib.Path(tmp))       # 対照ファイルが 1 本も無い
    check("C1 列挙できなければ measurable=false", rep["measurable"] is False, str(rep)[:120])
    check("C2 『0 件』と読まないと述べる", "0 件と読まない" in rep.get("why", ""),
          rep.get("why", ""))
    rc, msg, _ = G.check_staged(pathlib.Path(tmp))
    check("C3 staged を列挙できなければ rc=2", rc == 2, f"rc={rc} {msg}")
_real = G.EXCEPTIONS
try:
    G.EXCEPTIONS = pathlib.Path("/nonexistent/exc.json")
    rc, msg, _ = G.check_staged(REPO)
    check("C4 例外台帳を読めなければ rc=2 (空集合として通さない)", rc == 2, f"rc={rc}")
finally:
    G.EXCEPTIONS = _real

print("== D/E. ratchet と配線 ==")
exc = G.load_exceptions()
check("D1 例外台帳が在る", "error" not in exc, str(exc)[:100])
check("D2 path 集合で比較する規則を持つ", "path 集合" in exc.get("rule", ""), str(exc)[:120])
src = (REPO / "scripts/tautological_control_gate.py").read_text(encoding="utf-8")
check("D3 実装が集合演算 (件数比較へ戻っていない)", "now - prev_paths" in src)
pc = (REPO / "scripts/hooks/pre-commit").read_text(encoding="utf-8", errors="replace")
check("E1 pre-commit に配線されている (advisory でない)",
      "tautological_control_gate.py" in pc and "fail=1" in
      pc.split("tautological_control_gate.py", 1)[1][:400])

print("== F. 本検査自身が gate を通る (自己適用) ==")
self_scan = G.scan_file(pathlib.Path(__file__))
check("F1 この検査ファイル自身に恒真が無い", self_scan["findings"] == [], str(self_scan))

print(f"\ntautological-control-gate: PASS {12 - len(FAILED)} / FAIL {len(FAILED)}")
sys.exit(1 if FAILED else 0)
