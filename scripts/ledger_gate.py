#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ledger schema gate. Single definition point: schema/ledger.json.

    python3 scripts/ledger_gate.py --type negative_result --file ledger/negative_results.jsonl
    python3 scripts/ledger_gate.py --type prereg --file examples/prereg.sample.json

Exit codes
----------
``0`` every record validated.
``1`` at least one record is invalid.
``2`` validation could not be performed (unreadable schema, unknown type,
      missing closed vocabulary). An empty input file is also 2: a validator
      that reports success over zero records is reporting that it did not run.

Standard library only, deliberately: a gate that needs an install step is a gate
that is skipped on the machine where it matters.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "schema/ledger.json"

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


class Undecidable(Exception):
    pass


# --------------------------------------------------------------------------
# closed vocabularies
# --------------------------------------------------------------------------

def parse_label_sections(text: str) -> dict:
    """Read `key:` / `  - value` sections. Deliberately tiny and strict.

    Only the shape actually used by schema/emit_reason_codes.yaml is accepted.
    Anything else raises, rather than being skipped — a vocabulary file that is
    half-parsed would silently shrink the closed set and let unknown labels in.
    """
    out, current = {}, None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current = line[:-1].strip()
            out[current] = []
            continue
        m = re.match(r"^\s+-\s+(\S+)\s*$", line)
        if m:
            if current is None:
                raise Undecidable(f"list item outside any section at line {lineno}")
            out[current].append(m.group(1))
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s*\S", line):
            continue  # scalar entry such as `version: 1`
        raise Undecidable(f"unsupported line in vocabulary file at line {lineno}: {raw!r}")
    return out


def load_vocabulary(schema: dict, name: str, root: pathlib.Path) -> set:
    spec = (schema.get("vocabularies") or {}).get(name)
    if not spec:
        raise Undecidable(f"field declares vocabulary {name!r} which the schema does not define")
    path = root / spec["file"]
    try:
        sections = parse_label_sections(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise Undecidable(f"vocabulary file unreadable: {path} ({e})") from e
    section = spec["section"]
    if section not in sections:
        raise Undecidable(f"vocabulary file {path} has no section {section!r}")
    labels = sections[section]
    if not labels:
        raise Undecidable(f"vocabulary section {section!r} is empty — an empty closed set "
                          f"accepts nothing and would make every record invalid for the wrong reason")
    return set(labels)


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def check_field(name: str, spec: dict, value, vocab_cache, schema, root) -> list:
    errs = []
    t = spec.get("type")
    if value is None:
        if spec.get("nullable"):
            return errs
        errs.append(f"{name}: null is not allowed")
        return errs
    if t == "string":
        if not isinstance(value, str):
            return [f"{name}: expected string, got {type(value).__name__}"]
    elif t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return [f"{name}: expected integer"]
    elif t == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return [f"{name}: expected number"]
    elif t == "boolean":
        if not isinstance(value, bool):
            return [f"{name}: expected boolean"]
    elif t == "array":
        if not isinstance(value, list):
            return [f"{name}: expected array"]
        if spec.get("items") == "string" and not all(isinstance(v, str) for v in value):
            errs.append(f"{name}: every item must be a string")
        if "min_length" in spec and len(value) < spec["min_length"]:
            errs.append(f"{name}: needs at least {spec['min_length']} item(s), has {len(value)}")
        return errs
    elif t == "object":
        if not isinstance(value, dict):
            return [f"{name}: expected object"]
        return errs
    elif t == "iso8601_date":
        if not (isinstance(value, str) and DATE.match(value)):
            return [f"{name}: expected YYYY-MM-DD, got {value!r}"]
        return errs
    elif t == "iso8601_datetime":
        if not (isinstance(value, str) and DATETIME.match(value)):
            return [f"{name}: expected an ISO-8601 timestamp with offset, got {value!r}"]
        return errs
    else:
        raise Undecidable(f"{name}: schema declares unsupported type {t!r}")

    if isinstance(value, str):
        if "min_length" in spec and len(value.strip()) < spec["min_length"]:
            errs.append(f"{name}: needs at least {spec['min_length']} characters")
        pat = spec.get("pattern")
        if pat and not re.match(pat, value):
            errs.append(f"{name}: does not match {pat}")
        if "enum" in spec and value not in spec["enum"]:
            errs.append(f"{name}: {value!r} is not one of {spec['enum']}")
        vname = spec.get("vocabulary")
        if vname:
            if vname not in vocab_cache:
                vocab_cache[vname] = load_vocabulary(schema, vname, root)
            if value not in vocab_cache[vname]:
                errs.append(f"{name}: {value!r} is not in the closed vocabulary {vname!r}")
    return errs


def validate_record(rec, fields, vocab_cache, schema, root) -> list:
    if not isinstance(rec, dict):
        return ["record is not an object"]
    errs = []
    for fname, spec in fields.items():
        if fname not in rec:
            if spec.get("required"):
                errs.append(f"{fname}: missing (required)")
            continue
        errs.extend(check_field(fname, spec, rec[fname], vocab_cache, schema, root))
    for extra in sorted(set(rec) - set(fields)):
        if not extra.startswith("_"):
            errs.append(f"{extra}: not declared in the schema "
                        f"(undeclared fields are rejected, not ignored)")
    return errs


def load_records(path: pathlib.Path) -> list:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise Undecidable(f"cannot read {path}: {e}") from e
    if path.suffix == ".jsonl":
        recs = []
        for lineno, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                recs.append((lineno, json.loads(line)))
            except json.JSONDecodeError as e:
                raise Undecidable(f"{path}:{lineno} is not valid JSON ({e})") from e
        return recs
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise Undecidable(f"{path} is not valid JSON ({e})") from e
    return [(1, o) for o in obj] if isinstance(obj, list) else [(1, obj)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ledger schema gate")
    ap.add_argument("--type", required=True, help="record type from schema/ledger.json")
    ap.add_argument("--file", required=True)
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        spath = pathlib.Path(a.schema)
        schema = json.loads(spath.read_text(encoding="utf-8"))
        root = spath.resolve().parent.parent
        types = schema.get("types") or {}
        if a.type not in types:
            raise Undecidable(f"unknown record type {a.type!r}; known: {sorted(types)}")
        fields = types[a.type]["fields"]
        records = load_records(pathlib.Path(a.file))
        if not records:
            raise Undecidable(f"{a.file} holds no records — 'all 0 records valid' is not a result")
        vocab_cache = {}
        bad = []
        for lineno, rec in records:
            errs = validate_record(rec, fields, vocab_cache, schema, root)
            if errs:
                bad.append((lineno, rec.get("id") if isinstance(rec, dict) else None, errs))
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"ledger-gate UNDECIDABLE: {e}", file=sys.stderr)
        return 2
    except Undecidable as e:
        print(f"ledger-gate UNDECIDABLE: {e}", file=sys.stderr)
        return 2

    if bad:
        for lineno, rid, errs in bad:
            for e in errs:
                print(f"ledger-gate BLOCK {a.file}:{lineno} [{rid}] {e}", file=sys.stderr)
        print(f"ledger-gate BLOCK: {len(bad)} of {len(records)} record(s) invalid",
              file=sys.stderr)
        return 1
    print(f"ledger-gate OK: {len(records)} record(s) of type {a.type} validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
