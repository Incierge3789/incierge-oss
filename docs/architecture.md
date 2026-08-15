# Architecture

Four gates, one pattern table, two schemas. Everything else is a control.

```
                     docs/prereg.scan.md          <- the only pattern table
                              |
                              | parsed (never copied)
                              v
     scripts/scan_forensic.py  --- config/literals.json   (deny-list, never committed)
                    |    |
        --staged    |    |  --all
                    v    v
   scripts/hooks/pre-commit          scripts/hooks/pre-push
     |  scan_forensic   (content)      |  exactly one permitted remote
     |  control_selfcheck              |  marker files prove repo identity
     |  tautological_control_gate      |  rejections appended outside the work tree
     |  ledger_gate      (schemas)
     |  phase_gate       (transition definition parses)
```

## The three-outcome rule

Every gate returns one of three things, with distinct exit codes:

| exit | meaning |
|---|---|
| 0 | checked, and clean |
| 1 | checked, and in violation |
| 2 | **could not check** |

Exit 2 is the load-bearing one. A missing deny-list, an unreadable file, an
unparsable pattern table, a binary blob, an empty record set, an unknown phase
name — all of these exit 2 rather than 0.

The reason is not tidiness. If "could not check" returned 0, then every gate
would have a documented way to be satisfied by breaking it, and breaking a
check is always cheaper than passing it. If it returned 1, the cheapest fix for
a red gate would be to rename the input until the gate stopped recognising it.

## The single-definition-point rule

`docs/prereg.scan.md` holds the patterns. `schema/phase_transitions.json` holds
the phase list. `schema/ledger.json` holds the record types. Each is parsed by
exactly one reader, and two tests assert that no second copy exists anywhere in
the repository — searching for probes taken from the definitions themselves,
rather than for strings written into the test.

Duplicated definitions do not stay in sync; one copy gets fixed and the other
keeps running. Writing the check as "there is no second copy" rather than "the
copies agree" removes the failure mode instead of monitoring it.

## Why the deny-list is not in the repository

Classes (a) and (d) are literal lists of real proper nouns. Publishing the
deny-list would publish exactly the strings the deny-list exists to withhold:
the pattern table would be its own leak.

So the mechanism is public and the literals are not. `config/literals.json` is
loaded at run time, is path-guarded in `.gitignore`, and its absence is
**undecidable**, not empty — a scanner that cannot load its deny-list has not
cleared anything. `config/literals.example.json` ships fictional entries so a
fresh clone can run every control without any real list.

A class may be declared empty (`c_customer_literal` is), but only with a stated
reason, and the scanner prints that reason on every run. Zero findings from a
class with no patterns is not evidence of absence, and the difference has to be
visible in the output rather than inferable from the configuration.

## Why controls are stored next to what they prove

Positive-control payloads live in the pattern table, not in the test files.
Exclusion rules carry `example_hit` and `example_miss` in the same object as
the exclusion regex.

This is not about tidiness either. The moment a control matters is the moment
someone edits the rule it guards; if the control lives in a separate file, that
edit is exactly when the two drift apart, and the test keeps passing over a
payload that no longer matches anything. Keeping them adjacent means whoever
narrows a pattern is looking at the two cases the pattern has to keep apart.

`scripts/control_selfcheck.py` closes the loop: it re-matches every declared
control against its own class and fails if a control has stopped firing. It
runs in `pre-commit`, not only in the test suite, because a check that only
runs when someone remembers to run it is a check with an availability problem.

## The layer model of the system this came from

`docs/ja/ARCHITECTURE.md` is the private system's own layer document, copied
byte-for-byte. It describes a larger structure than what is published here, and
its internal cross-references point at files that are not part of this
publication. It is included because the gates here are meaningful in relation
to that structure, not because the structure is reproduced.
