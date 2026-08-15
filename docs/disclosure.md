# The disclosure line

**Single definition point.** Every decision about what this repository may
contain resolves here. `scripts/tests/test_disclosure_parity.py` is the reader.

The earlier version of this boundary was a list of *functional categories*
("architecture is public, calibration is private"). That failed in a specific
way: two publication paths — a curated English ledger and a verbatim Japanese
copy — applied it independently and disclosed different things, and neither
violated the categories. Categories are not decidable. Rules are.

## The rules

```json
{
  "version": 1,
  "registered": "2026-08-15",
  "rules": [
    {
      "id": "D1",
      "kind": "prereg_criterion",
      "tier": "public",
      "decides": "a pass/fail condition, threshold, floor, or stopping rule that was registered before the measurement ran",
      "why": "a criterion is what makes a result checkable. Withholding it turns every published number into an assertion"
    },
    {
      "id": "D2",
      "kind": "measured_value",
      "tier": "public",
      "decides": "a number produced by running the registered procedure — including interval widths, counts, and sample sizes"
    },
    {
      "id": "D3",
      "kind": "calibration_value",
      "tier": "private",
      "decides": "a value that parameterises the instrument rather than reporting its output",
      "overrides": "D2",
      "why": "a calibration value is measured too, so D2 alone would publish it. This rule exists because that is exactly the case the category-based boundary got wrong"
    },
    {
      "id": "D4",
      "kind": "raw_log",
      "tier": "private",
      "decides": "the record stream itself, as opposed to a value computed from it"
    },
    {
      "id": "D5",
      "kind": "structure",
      "tier": "private",
      "overrides": "D1, D2",
      "decides": "file paths, directory names, lane names, and internal identifier namespaces of the private system",
      "why": "structure is not a result. A criterion or a measurement expressed as a path publishes the path as well, and the path is the part that keeps being useful to someone else after the number stops being interesting"
    }
  ],
  "precedence": "D3 over D2; D5 over D1 and D2. Where two rules disagree, the private one wins.",
  "undecidable": "not_published",
  "parity_requirement": "Every publication path applies these rules to the same content. A value disclosed on one path and withheld on another is a defect in the process, not a difference in judgement — schema/disclosure_parity.json declares the pairs that must agree."
}
```

## What each rule decided here

| content | rule | tier |
|---|---|---|
| `±0.03` reopen threshold for the frozen predicate-drafting work | D1 | **public** |
| Wilson 95% interval width `0.0808` | D2 | **public** |
| required sample size `D=234` | D2 | **public** |
| discrimination results `0.0 / 0.48 / 0.0 / 0.12` | D2 | **public** |
| counts `19 independent units (10 required)`, `11 unmeasurable` | D2 | **public** |
| `σ_t`, `λ_design`, `f_c`, SNR — the forward-model parameters | D3 | private |
| the per-trial error arrays behind the reported medians | D4 | private |
| `labs/<lane>/records/<file>.json` and every other private path | D5 | private |
| `TASK-*`, `BL-*`, `SIG-*` internal identifier namespaces | D5 | private |

Two of these went the other way before this document existed. The thresholds
and counts in the first four rows were published by the Japanese copy and
withheld by the English ledger; the paths in the last two rows were published by
both. **The line was not the problem — having two of them was.**

## Direction of the correction

The English ledger was **raised to match**, not the Japanese copy cut down.
D1 and D2 say those numbers are public, so removing them from one path would
have been the wrong repair: it would have made the disclosure smaller and the
process no more consistent. `NR-005` now carries them.

The paths went the other way, because D5 says private and both paths were wrong.

## The check

`scripts/tests/test_disclosure_parity.py` asserts:

1. every number disclosed on one path is disclosed on the other, or is listed
   in `schema/disclosure_parity.json` with a reason;
2. no private-structure path appears on any path;
3. no internal identifier namespace appears on any path.

It fails if a future edit re-opens the divergence. That is the whole point: the
rules above are prose, and prose does not stay applied.
