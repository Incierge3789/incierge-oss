# Ledger schemas

`schema/ledger.json` is the single definition point for every record type.
`scripts/ledger_gate.py` is its only reader.

```sh
python3 scripts/ledger_gate.py --type negative_result --file ledger/negative_results.jsonl
python3 scripts/ledger_gate.py --type prereg          --file examples/prereg.sample.json
```

There is deliberately **no JSON Schema version** of these types. A second
machine-readable copy would drift, and the copy that gets fixed is the one
someone happens to be running.

## Record types

| type | id prefix | what it is for |
|---|---|---|
| `prereg` | `PR-` | a claim registered before it is measured. See `examples/prereg.sample.md` |
| `negative_result` | `NR-` | a claim that was measured and did not survive |
| `decision` | `D-` | a decision, with the reasoning that produced it |
| `failure` | `F-` | a failure, with the machine condition that closes it |
| `external_response` | `XR-` | a response to something reported from outside |

## Rules the gate enforces

- **Undeclared fields are rejected, not ignored.** A field the schema does not
  know about is usually a field someone added instead of extending the schema,
  and once one record has it the shape of the ledger is no longer described by
  anything.
- **Closed label sets.** `failure.cause_code` must come from the vocabulary in
  `schema/emit_reason_codes.yaml`. Free text in a cause field makes recurrence
  uncountable — you cannot ask "how many times has this happened" of prose.
  If a cause genuinely has no label, the answer is to add one to the closed
  set, which is a visible change.
- **Zero records is exit 2, not exit 0.** "All 0 records valid" is a statement
  about a file that was not read, dressed as a result.
- **An empty vocabulary is exit 2.** A closed set with nothing in it would
  reject every record, and would do so for a reason unrelated to the records.
- **Minimum lengths on the fields that carry evidence.** `measured` cannot be
  `"n/a"`. This does not stop someone writing something useless, but it stops
  the shortest useless thing, and it makes the field's purpose legible.

Every one of these has a test that mutates a valid record until it fails, plus
a negative control asserting the unmutated record still passes. A validator
tested only on records that should pass is a validator that might accept
everything.

## Why `negative_result` has the fields it has

| field | why |
|---|---|
| `claim` | stated as an assertion, so it can fail |
| `prereg_criteria` | the pass/fail rule **as registered**, not as it reads in hindsight |
| `measured` | numbers. "it did not work" is not a measurement |
| `verdict` | from a closed set: `refuted`, `not_supported`, `withdrawn`, `substrate_unfit`, `inconclusive`. These are not synonyms — `refuted` means the measurement went against the claim, `not_supported` means it did not go for it, and `withdrawn` means something previously asserted is being taken back |
| `withdrawn_claim` | the retracted wording, verbatim. Nullable, because most negative results never had a positive phase — but when there was one, the exact sentence being taken back is recorded rather than paraphrased |
| `reopen_condition` | either the evidence that would reopen this, or an explicit statement that nothing will. A negative result with no reopen condition is indistinguishable from one that was abandoned |
| `source` | **a path inside the private repository at the anchor commit, which does not resolve in this repository.** It is a provenance pointer, not a link. The measurement records themselves are not published; what is published is the claim, the registered criteria, the numbers, and the verdict |

## `external_response` is a separate instrument

It is defined and **not yet counted**. It must never be added to the numerator
of the human-intervention rate.

Those two numbers measure different things. The intervention numerator counts
occasions when the system handed its own work back to its operator. An external
response is the system answering someone else. Adding them together would mean
the metric gets worse the more useful the project is to other people, which
creates a standing incentive to ignore reports — and a metric that rewards
ignoring evidence is worse than no metric.

It also distinguishes **where the report came in**. `intake` is
`canonical_site` for <https://incierge.jp/challenge/>, which is the canonical
endpoint and is projected into the event log, or `github_issue` for an Issue on
this repository, whose projection **is not yet built**. `projected_to_event_log`
records that per record rather than leaving it to be remembered, so the value is
`false` for every Issue until the projection exists — which makes the gap a
number instead of a footnote.

One combined count would hide the only thing worth measuring here: whether the
secondary path carries anything at all once it is wired.
