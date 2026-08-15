# incierge-oss

Machine-enforced discipline for an operating system that is meant to run
without a human in the loop: a content boundary, a transition gate, ledger
schemas, and pre-registration — each one a program that exits non-zero, not a
convention someone is supposed to remember.

**What this is not:** a framework, an agent, or a product — there is nothing
here to build an application on.

## Why these four and not others

Each gate here exists because its absence was measured, not because it rounded
out a set.

- **A guard that has never been seen firing is treated as absent.** Every gate
  ships with a control that must fail on demand, and one control
  (`scripts/control_selfcheck.py`) exists only to detect controls that have
  quietly stopped matching what they were meant to prove.
- **"Could not check" never renders as "checked and clean."** Every gate has
  three outcomes — pass, block, undecidable — with distinct exit codes.
  Collapsing the last two is how a gate gets bypassed: if an unrecognised input
  produced the same code as a violation, the cheapest fix for a red gate would
  be to rename the input.
- **Definitions live in exactly one place.** The scanner has no pattern list of
  its own; it parses `docs/prereg.scan.md`. Two tests assert that no second copy
  of the pattern table or the phase list exists anywhere in the repository.

## Run it

Requires **Python 3.9 or newer, git, `make`, and a POSIX shell** with the usual
utilities (`sed`, `grep`, `mktemp`). No third-party Python packages — a gate
that needs an install step is a gate that gets skipped on the machine where it
matters. Developed and run on macOS; it assumes a POSIX environment, and the
hooks are POSIX `sh`.

If you have Python and git but not `make`, every target is a one-line command:
`make demo` is `sh examples/minimal/run.sh`, `make test` is
`python3 scripts/run_tests.py`, and `make setup` is a copy of
`config/literals.example.json` to `config/literals.json`.

```sh
git clone https://github.com/Incierge3789/incierge-oss.git
cd incierge-oss
make setup           # config/literals.json <- the example (fictional) deny-list
make demo            # the minimal working example
```

**`make setup` is not optional.** Without `config/literals.json` the scanner
exits 2 and every other target fails with it — that is the fail-closed
behaviour working, not a broken clone. The example file it copies contains
fictional entries and is enough to run everything here.

`make demo` runs each gate twice — once on input it must accept and once on
input it must reject — and prints both. It exits non-zero if any step behaves
differently from the specification.

```sh
make install-hooks   # git config core.hooksPath scripts/hooks
make test            # the full suite, including the hook positive controls
make check           # every gate once, over this repository
```

After `make install-hooks`, **the push guard permits exactly one remote** — the
one named in `config/allowed_remote.txt`. Pushing to your own fork is rejected
until you put your fork's URL there. That is the intended behaviour for the
repository this was extracted from; for a fork it is a one-line edit.

## What is in here

| path | what it is |
|---|---|
| `docs/prereg.scan.md` | the frozen pattern table and its positive controls. The single definition point; the scanner and the hooks parse it |
| `scripts/scan_forensic.py` | the content scanner. Fail-closed: missing deny-list, unreadable file, or binary content all exit 2 |
| `scripts/hooks/pre-commit` | content guard. Scans staged content, not the work tree |
| `scripts/hooks/pre-push` | push guard. Exactly one permitted remote; mismatch, unset and undecidable all reject, and rejections are appended to a log outside the work tree |
| `scripts/canonical_remote.py` | canonical form of a remote URL, so that the six common spellings of one destination are one destination |
| `scripts/phase_gate.py` + `schema/phase_transitions.json` | the transition type: nine phases, forward by one, no skipping, unknown names undecidable |
| `scripts/ledger_gate.py` + `schema/ledger.json` | record schemas for pre-registrations, negative results, decisions, failures. Closed label sets, undeclared fields rejected |
| `scripts/tautological_control_gate.py` | detects controls that cannot fail. Carried over unchanged from the private system |
| `examples/prereg.sample.json` + `.md` | the pre-registration type and a real registration |
| `ledger/negative_results.jsonl` | the negative results ledger |

## Facts from running it

Measured on the private system this was extracted from, as of 2026-08-15. They
are reported because a claim about a discipline is worth what its numbers are
worth.

- The instrument that matters most is the human-intervention rate, and it is
  **red**. Over a window of 104 completed tasks: 6 occasions where the work
  actually moved back to a person (0.0577), and 19 attempts to move it
  (0.1827), of which 13 were stopped by a gate. The pass condition is not a
  threshold, it is **numerator zero** — so 0.0577 is red, and a figure like
  0.0112 would also be red. A target you can reach by tightening a threshold is
  not the target.
- The phase order and the gate chain described here are the ones the private
  system runs on; `scripts/tautological_control_gate.py` is carried over
  byte-for-byte rather than reimplemented for publication.
- Cross-review runs with a quorum of two independent bases. That is an
  operating practice, **not something this repository ships** — there is no
  cross-review tool, hook, or config here, and nothing in `make check` enforces
  it. It is stated because it is how the findings below were produced, not as a
  feature.

**None of the underlying data is in this repository, and you cannot re-derive
these numbers from it.** The 104-task window is private operational telemetry;
what is published is the schema those records have (`schema/ledger.json`), not
the records. The `source` field on each negative result likewise names a path
inside the private repository at the anchor commit — those paths do not resolve
here, by design. Treat the figures as reported, not as reproducible: the
reproducible part of this repository is the gates, and those you can run.

## Negative results

Claims that were pre-registered, measured, and did not survive. The data is
`ledger/negative_results.jsonl`; a test asserts this table matches it.

| id | verdict | claim |
|---|---|---|
| NR-001 | refuted | information-gain selection beats uniform spacing at equal budget |
| NR-002 | not_supported | ordering work by estimated expected loss beats a simple structural rule |
| NR-003 | withdrawn | a selector's recall advantage on a standard defect corpus |
| NR-004 | not_supported | a selector's measured recall transfers between repositories |

NR-003 is the one worth reading. A positive result had already been produced
before self-audit found that only the treatment arm could see an input derived
from the fix commit. With that input removed the treatment became identical to
the control, a registered stop condition fired, and the number was withdrawn
rather than republished with a caveat.

## Provenance

Extracted from a private repository at commit
`aa1a5a68e27b3992a26386edc301e898b8887153`, dated 2026-08-15T06:59:46+09:00.
This repository has no history in common with it: it starts from an empty root,
and every file here was scanned before it was placed. The Japanese-language
documents under `docs/ja/` are byte-identical copies from that commit; their
digests are in `docs/ja/README.md`.

## What this does not claim

No priority and no superiority. Nothing here is asserted to be first, novel, or
better than anything else, and the repository assumes contemporaneous work
exists that it does not cite — a prior-art search has **not** been performed.

That is a structural constraint rather than a stylistic preference:
`config/claim_terms.json` lists the terms this repository may not use about
itself, and a test fails if any of them appears in the documents it guards. A
priority claim is the cheapest sentence to write and the most expensive one to
withdraw, and the record here already contains one withdrawal (`NR-003`).

What is claimed is narrower and checkable: the gates in this repository do what
their controls demonstrate, on the machine you run them on.

## What is deliberately included

`docs/ja/` and the `source` fields in the negative-results ledger name the
private system's own layer and directory structure. That is a decision, not a
leak the scanner missed: the layer model is the thing `docs/ja/ARCHITECTURE.md`
exists to describe, and a provenance pointer with the path removed would not be
a provenance pointer. What is withheld is the content of those layers — the
ledgers, the logs, the calibration values, and the identifiers listed in
`docs/prereg.scan.md`.

## On the execution substrate

The execution substrate is not the point. This implementation is operated with
Claude Code, and cross-review is performed on two independent bases (agy and
cursor).

## Contributing

Issues, please — see `CONTRIBUTING.md`. Pull requests are closed for now, with
the reason given each time.

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.
