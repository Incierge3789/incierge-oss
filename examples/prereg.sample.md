# The pre-registration type, by example

The machine-readable sample is `examples/prereg.sample.json`. It validates
against the `prereg` type in `schema/ledger.json`:

```sh
python3 scripts/ledger_gate.py --type prereg --file examples/prereg.sample.json
```

This page explains what each field is for. It does not restate the values —
there is one copy of those, in the JSON.

| field | why the type demands it |
|---|---|
| `id`, `registered` | a registration that cannot be shown to predate the result is not a registration. The date is what makes "we always expected that" checkable. |
| `question` | the thing being asked, separately from the thing being claimed. |
| `claim` | what would have to be true. Written as an assertion so that it can fail. |
| `arms` | at least two. One arm is not an experiment, it is a demonstration. |
| `metric` | the number that decides it. |
| `metric_definition_point` | **a path.** The metric must exist in exactly one place in the code. When each arm computes its own version of "error", the comparison quietly stops being a comparison. |
| `decision_rule` | how the metric becomes a verdict, including the resampling procedure and its seed, fixed before the run. |
| `win_conditions` | the conditions for the claim to survive. Plural and conjunctive on purpose: a single condition tends to be the one that is easiest to satisfy. |
| `stop_conditions` | **the conditions under which nothing is scored at all.** This is the field that does the most work. Without it, a broken control produces a weak result with a caveat instead of no result, and weak results with caveats are what later get cited without the caveat. |
| `controls` | at least one, and it has to be able to fail. A control that cannot lose is decoration. |
| `negative_result_is_a_result` | asserted before the run, so that a null finding cannot afterwards be reframed as a failed experiment and quietly dropped. |

## The part that is easy to skip

`stop_conditions` and `controls` are the fields that cost something to write and
return nothing when the result is positive. They are also the two that decided
the outcome in three of the four entries in `ledger/negative_results.jsonl`:

- `NR-003` was withdrawn because a registered stop condition — *if the control
  is tautological, do not score* — fired after the control was found to be
  identical to the arm. Without that condition, the honest outcome would have
  been a published number with a footnote.
- `NR-004` records that its control never wins anywhere, which makes its
  "beats the control" condition a low bar. That is stated next to the result
  rather than left for a reader to notice.
- `NR-001` survived a harness check that was registered as a stop condition: at
  full budget every arm must agree, because every arm then uses everything.

A pre-registration whose stop conditions never fire has not been tested either.
