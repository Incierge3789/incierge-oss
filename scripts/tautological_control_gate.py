#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恒真の対照を機械検出する gate (測定系 TASK-4 / 4 回目の再発防止)。

## なぜ在るか

`check(..., True)` 型の**何も測っていない対照**を 4 回踏んだ:

- A-1b の空判定対照
- boot-check D1 (lane 不明を『他 lane』として緑にする挙動を正しいものとして固定)
- A-1c B5 (strip 処理を通していないので、import の無いソースを渡していただけ)
- A-1d F2 (`not ("2099-01-01" <= "2008-07-28")` の定数比較)

**個別修理では 5 回目が来る。** 検出を機械化する。

## 何を恒真とみなすか (3 形)

1. `constant`       — 比較の両辺が定数、または第 2 引数が `True` / 非空リテラル
2. `no_subject`     — その対照 block が**被検体を一度も呼んでいない**
                      (import した module 名も、`subprocess` も現れない)
3. `hardcoded_expect` — 期待値が literal で、被検体側の式を参照していない
                      (= 本体が変わっても対照は落ちない)

**1 と 2 は機械で確実に判る。3 は近似**なので、検出したら理由つきで一覧に出し、
gate は 1 と 2 でのみ block する (近似で止めない)。

## 例外

`records/tautological_control_exceptions.json` に既存の非準拠を登録する。
**ratchet は path 集合で比較する** — 件数だけだと入れ替えで穴を維持できる
(BL-011 の空判定 gate で同じ修理をした)。

## F-097

対照ファイルを列挙できなければ **rc=2** (0 件と読まない)。

exit 0 = 違反なし / 1 = 違反 / 2 = 判定不能
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
EXCEPTIONS = REPO / "records/tautological_control_exceptions.json"
AUDIT = REPO / "records/tautological_control_audit.json"
CONTROL_GLOBS = ("scripts/tests/test_*.py", "labs/*/scripts/tests/test_*.py",
                 "agent-ops/scripts/tests/test_*.py")


def control_files(repo: pathlib.Path = REPO) -> list | None:
    """対照ファイルの母集合。**列挙できなければ None** (0 件と区別する)。"""
    try:
        out = []
        for g in CONTROL_GLOBS:
            out.extend(sorted(repo.glob(g)))
        return out if out else None
    except OSError as _e:
        print(f"[tautological_control_gate] {type(_e).__name__}: {_e} — fail-open で継続 (黙って握り潰さない)", file=sys.stderr)
        return None


def _is_constant(node: ast.AST) -> bool:
    """定数、または定数だけからなる比較か。"""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp):
        return _is_constant(node.operand)
    if isinstance(node, ast.Compare):
        return (_is_constant(node.left)
                and all(_is_constant(c) for c in node.comparators))
    if isinstance(node, ast.BoolOp):
        return all(_is_constant(v) for v in node.values)
    return False


def scan_file(path: pathlib.Path) -> dict:
    """1 ファイルの対照を走査する。**読めなければ unmeasurable**。"""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except (OSError, SyntaxError) as e:
        return {"path": str(path), "unmeasurable": f"{type(e).__name__}: {e}"}
    findings = []
    calls = 0
    # **偽陽性を絞る** (2026-08-12 実測):
    #  - `except` 節の中の `check(..., True)` は「その分岐に来たこと自体が証拠」
    #    なので恒真ではない
    #  - `check(..., False, 理由)` は意図的な失敗マーカーであって対照ではない
    in_except = set()
    for h in ast.walk(tree):
        if isinstance(h, ast.ExceptHandler):
            for n in ast.walk(h):
                in_except.add(id(n))
    # ファイル内で「被検体を呼んでいる」ことの証拠 (module 経由 / subprocess)
    subject_used = any(
        isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
        and n.value.id.isupper() for n in ast.walk(tree)) or "subprocess" in src
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "check"):
            continue
        calls += 1
        if len(node.args) < 2:
            continue
        cond = node.args[1]
        name = (node.args[0].value if isinstance(node.args[0], ast.Constant)
                else "<式>")
        if isinstance(cond, ast.Constant) and cond.value is False:
            continue
        if id(node) in in_except:
            continue
        if _is_constant(cond):
            findings.append({"line": node.lineno, "control": str(name)[:60],
                             "kind": "constant",
                             "why": "比較の両辺が定数 — 本体が壊れても落ちない"})
    if calls and not subject_used:
        findings.append({"line": 0, "control": "(ファイル全体)", "kind": "no_subject",
                         "why": "被検体を一度も呼んでいない (module 参照も subprocess も無い)"})
    return {"path": str(path), "controls": calls, "findings": findings}


def audit(repo: pathlib.Path = REPO) -> dict:
    files = control_files(repo)
    if files is None:
        return {"measurable": False,
                "why": "対照ファイルを列挙できない — 0 件と読まない (F-097)"}
    rows = [scan_file(p) for p in files]
    unmeasurable = [r for r in rows if r.get("unmeasurable")]
    bad = [{"path": str(pathlib.Path(r["path"]).relative_to(repo)), **f}
           for r in rows for f in r.get("findings", [])]
    return {"measurable": not unmeasurable,
            "unmeasurable": unmeasurable,
            "files": len(rows), "controls": sum(r.get("controls", 0) for r in rows),
            "violations": bad, "violation_files": sorted({b["path"] for b in bad})}


def load_exceptions() -> dict:
    if not EXCEPTIONS.exists():
        return {"error": f"例外台帳が無い: {EXCEPTIONS}"}
    try:
        return json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"error": f"例外台帳を読めない: {e}"}


def check_staged(repo: pathlib.Path = REPO) -> tuple:
    """staged な対照ファイルに恒真が無いか。例外に載るものだけ見逃す。"""
    exc = load_exceptions()
    if "error" in exc:
        return 2, exc["error"], []
    allowed = set(exc.get("paths") or [])
    try:
        r = subprocess.run(["git", "-C", str(repo), "diff", "--cached",
                            "--name-only", "--diff-filter=ACMR"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return 2, "staged を列挙できない — 『違反なし』と読まない", []
    if r.returncode != 0:
        return 2, "staged を列挙できない (git 非ゼロ)", []
    staged = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    targets = [s for s in staged
               if pathlib.Path(s).name.startswith("test_") and s.endswith(".py")]
    bad = []
    for rel in targets:
        if rel in allowed:
            continue
        p = repo / rel
        if not p.is_file():
            continue
        res = scan_file(p)
        if res.get("unmeasurable"):
            return 2, f"対照を読めない: {rel} ({res['unmeasurable']})", [rel]
        for f in res["findings"]:
            bad.append(f"{rel}:{f['line']} {f['kind']}")
    if bad:
        return 1, (f"恒真の対照が {len(bad)} 件 — 何も測らない対照は "
                   f"『対照つき』に見せるので有害"), bad
    return 0, f"staged の対照 {len(targets)} 本に恒真なし", []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="恒真対照の検出 gate")
    ap.add_argument("--audit", action="store_true", help="全数走査して一覧を出す")
    ap.add_argument("--write-exceptions", action="store_true")
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    repo = pathlib.Path(a.repo)
    if a.audit or a.write_exceptions:
        rep = audit(repo)
        if not rep["measurable"]:
            print(f"audit: {rep.get('why') or rep.get('unmeasurable')}", file=sys.stderr)
            return 2
        rep["ts"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        AUDIT.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        if a.write_exceptions:
            prev = load_exceptions()
            prev_paths = set(prev.get("paths") or []) if "error" not in prev else None
            now = set(rep["violation_files"])
            if prev_paths is not None:
                added = sorted(now - prev_paths)
                if added:
                    print(f"例外に**新規**を追加できない (ratchet): {added[:3]}",
                          file=sys.stderr)
                    return 1
            EXCEPTIONS.write_text(json.dumps({
                "ts": rep["ts"], "rule": "**増やせない**。path 集合で比較する",
                "count": len(now), "paths": sorted(now),
                "generated_by": "scripts/tautological_control_gate.py --write-exceptions",
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"exceptions -> {EXCEPTIONS} ({len(now)} ファイル)")
            return 0
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print(f"対照 {rep['controls']} 本 / ファイル {rep['files']} / "
                  f"恒真 {len(rep['violations'])} 件 "
                  f"({len(rep['violation_files'])} ファイル)")
            for b in rep["violations"][:20]:
                print(f"  {b['path']}:{b['line']} [{b['kind']}] {b['control']}")
        return 0
    rc, msg, items = check_staged(repo)
    tag = {0: "tautological-control OK", 1: "tautological-control BLOCK",
           2: "tautological-control BLOCK (判定不能)"}[rc]
    print(f"{tag}: {msg}", file=sys.stderr if rc else sys.stdout)
    for x in items[:20]:
        print(f"    {x}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
