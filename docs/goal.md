# Goal — public edition

This is the public edition of the goal document the private system runs against.
The private original carries names and identifiers that are out of scope here;
what follows is the part that is a claim about engineering rather than about a
particular organisation.

## The goal

**A system that keeps running without a person detecting, reacting, or ruling.**

Not "a person is rarely needed". Not "a person is needed less than before".
Human involvement is limited to an explicitly enumerated list, and everything
else executes on its own with an auditable trail.

## The instrument

The goal is measured by one number:

```
human_intervention_requests / completed_tasks
```

The numerator is not counted by looking for question marks. It counts
**occasions on which the next actor became a human** — the work stopped and
waited for someone.

**The pass condition is that the numerator is zero.** Not that the ratio is
small. This is the part that is easy to get wrong and expensive to get wrong,
so it is worth being explicit: a threshold-based version of this metric can be
satisfied by making the denominator larger, and a system that does more work
while handing back the same amount of it has not improved at the thing being
measured. A rate of 0.0112 is red for the same reason 0.9 is red.

The rate is still reported, because the trend is informative and because a
single number with no denominator hides how much work was done at all. It is
just not the pass condition.

### Two numbers, not one

Attempts to hand work back are counted separately from completed hand-backs.
When a gate stops an attempt, the work did not move to a person and the task is
not finished either. Reporting only the completed hand-backs would make a
system that constantly tries to escalate look identical to one that never does;
reporting only the attempts would credit the gate with a problem it merely
contained. Both are published, and neither is allowed to turn the other green.

## What stays with a person

The list is closed, and its being closed is the point — an open-ended "use
judgement" clause is how everything eventually becomes a human decision:

1. irreversible operations
2. changes to a pre-registration
3. adding a new principle or rule
4. spending a budget
5. design branches not uniquely determined by existing principles
6. legal declarations of intent
7. facts only the person holds

Anything not on this list is not a human decision, and classifying something
as human is itself a machine judgement rather than a default. The failure mode
being guarded against is not laziness; it is that "this one needs a person"
sounds responsible and is unfalsifiable, so it expands until it covers
everything.

## Why the negative ledger exists

A system that reports only what worked cannot be checked. The negative results
ledger holds claims that were registered in advance, measured, and did not
survive — each with the criteria as they were registered, the numbers as they
came out, and the condition under which the claim could be reopened.

The discipline it enforces is narrow and specific: **a result that fails a
registered stop condition is not reported with a caveat.** It is not reported.
Numbers published with caveats get cited without them.

## What this repository is, relative to that goal

The gates here are the enforcement layer, not the system. They are the parts
that can be published on their own and still be usable: a content boundary, a
transition type, ledger schemas, and the pre-registration type.

The measured state of the goal is in `README.md` under "Facts from running it",
and at the time of publication it is **red**.
