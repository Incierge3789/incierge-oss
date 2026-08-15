# Contributing

This repository exists to be falsified. The most useful thing you can send is
evidence that one of the gates does not do what it claims.

## Please report

**1. A gate let through something it must not.**

The content scanner is the main one. If you can construct input that carries
material of class (a), (b), (c) or (d) as defined in `docs/prereg.scan.md` and
still get `exit 0`, that is the report we most want. Same for the push guard
accepting a remote other than the single permitted one, and for the ledger gate
accepting a record that violates a declared rule.

What to include: the input, the exact command, the exit code you got.

**2. A positive control does not fire.**

Run `make test`. If a control passes while the thing it is supposed to prove is
broken — for example, if you can narrow a pattern until it matches nothing and
`scripts/control_selfcheck.py` still reports it live — that is a defect in the
control, and it is worse than a defect in the gate. A gate with a rotten
control is a gate nobody is watching.

The same applies to a control that passes for the wrong reason: if the hook
positive control rejects a commit because of class (c) while class (a) has
silently stopped matching, the test is green and the guard is half dead.

**3. A ledger discipline can be broken.**

Ways to get a record into a ledger that should not be there; ways to close a
record without meeting its own `close_predicate`; ways to make an empty check
report success. If you can find a path where zero findings is reported as a
clean result rather than as a population that was never read, that is the
category.

## Please do not send

- Style, formatting, or naming preferences.
- New features, new gates, or new abstractions. If a gate is missing, the useful
  form of that report is a case the current gates fail to catch.
- Reports that a Japanese-language document under `docs/ja/` should be
  translated or edited. Those files are byte-identical copies with recorded
  digests; changing them would break the provenance claim about them.

## Pull requests

**Pull requests are closed for now**, and each one will be closed with the
reason stated rather than left to time out.

The reason is provenance. Every file here was scanned against a frozen pattern
table before it was placed, and the repository asserts that it starts from an
empty root with nothing carried over from the private system it was extracted
from. Merging outside commits directly would mean that assertion could no
longer be checked the same way. If a report leads to a change, the change is
made here and the report is credited in the issue.

This is a constraint of the current arrangement, not a judgement about
contributions. If it changes, this file changes with it.

## Third-party material

If you notice material in this repository that carries another project's
copyright, report it as a licensing issue rather than a leak. The scanner has a
class for it — `e_third_party_oss`, severity `warn` — and it warns rather than
failing on purpose: the remedy is often separation in `NOTICE`, not removal,
and a gate that failed would push toward deleting the attribution.

## What happens to a report

External responses are tracked as their own instrument
(`external_response` in `schema/ledger.json`), separately from the system's
internal human-intervention count. They are deliberately not added together:
answering someone else's question is not the system handing work back to its
own operator, and merging the two would make the system look worse the more
useful it is to other people.

Nothing has been counted yet — the type exists so that the first report has
somewhere to go.
