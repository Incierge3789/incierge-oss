#!/bin/sh
# Minimal working example.
#
# Runs each gate twice: once on input it must accept, once on input it must
# reject. A gate is only shown to work by watching it fail on demand, so every
# step below prints both directions.
set -u

cd "$(dirname "$0")/../.." || exit 1
PY=${PYTHON:-python3}
TMP=$(mktemp -d) || exit 1
trap 'rm -rf "$TMP"' EXIT
fail=0

hr() { printf '\n== %s ==\n' "$1"; }
expect() {
    want=$1; got=$2; what=$3
    if [ "$want" = "$got" ]; then
        printf '   ok    exit %s  %s\n' "$got" "$what"
    else
        printf '   FAIL  exit %s (wanted %s)  %s\n' "$got" "$want" "$what"
        fail=1
    fi
}

if [ ! -f config/literals.json ]; then
    echo "config/literals.json is missing. Run: make setup" >&2
    exit 2
fi

hr "1. content scan — the whole repository must be clean"
$PY scripts/scan_forensic.py --all >/dev/null 2>"$TMP/scan.err"
expect 0 $? "scan of every tracked file"
sed -n 's/^/   /p' "$TMP/scan.err" | tail -n 3

hr "2. content scan — planted material must be caught"
$PY - <<'PY' > "$TMP/planted.txt"
import json, pathlib, sys
sys.path.insert(0, "scripts")
import scan_forensic as S
prereg = S.load_prereg(pathlib.Path("docs/prereg.scan.md"))
lits = S.load_literals(pathlib.Path("config/literals.json"))
for cid, payload in sorted(S.positive_controls(prereg, lits).items()):
    print(f"{cid}: {payload}")
PY
cp "$TMP/planted.txt" ./_demo_planted.txt
$PY scripts/scan_forensic.py --paths _demo_planted.txt >/dev/null 2>"$TMP/hits.err"
expect 1 $? "scan of a file carrying one payload per class"
grep -c '^HIT' "$TMP/hits.err" | sed 's/^/   hits: /'
grep -c '^WARN' "$TMP/hits.err" | sed 's/^/   warnings: /'
rm -f ./_demo_planted.txt

hr "3. positive controls must still match their own class"
$PY scripts/control_selfcheck.py
expect 0 $? "control self-check"

hr "4. ledger schema — the negative results ledger"
$PY scripts/ledger_gate.py --type negative_result --file ledger/negative_results.jsonl
expect 0 $? "4 negative results validate"
printf '{"id":"NR-999","date":"2026-01-01","claim":"a claim that is long enough","prereg_criteria":"criteria that are long enough","measured":"numbers go here","verdict":"probably_fine","withdrawn_claim":null,"reopen_condition":"never"}\n' > "$TMP/bad.jsonl"
$PY scripts/ledger_gate.py --type negative_result --file "$TMP/bad.jsonl" 2>"$TMP/ledger.err" >/dev/null
expect 1 $? "a record with a verdict outside the enum is rejected"
sed -n 's/^/   /p' "$TMP/ledger.err" | head -n 1

hr "5. ledger schema — the pre-registration sample"
$PY scripts/ledger_gate.py --type prereg --file examples/prereg.sample.json
expect 0 $? "pre-registration sample validates"

hr "6. phase transition gate"
$PY scripts/phase_gate.py --from Build --to Review >/dev/null
expect 0 $? "Build -> Review is permitted"
$PY scripts/phase_gate.py --from Build --to Ship 2>/dev/null >/dev/null
expect 1 $? "Build -> Ship is rejected (skips Review and Test)"
$PY scripts/phase_gate.py --from Build --to Refactor 2>/dev/null >/dev/null
expect 2 $? "an unknown phase name is undecidable, not permitted"

hr "result"
if [ "$fail" -eq 0 ]; then
    echo "all steps behaved as specified"
else
    echo "at least one step did not behave as specified" >&2
fi
exit $fail
