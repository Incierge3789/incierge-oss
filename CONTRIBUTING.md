# Contributing

## Issues: yes. Pull requests: no.

**Issues are open and read.** Bug reports, a control that does not fail when you
break it on purpose, a pattern the scanner misses, a rule that reads two ways —
those are the most useful thing you can send, and they are welcome.

**Pull requests are closed unmerged.** This is a policy, not a judgement about
the change. It is stated here so a contributor learns it before spending time
rather than after.

## Why

Every file here is an extract from a private system that still runs. The
extraction is recorded: `docs/ja/README.md` carries the digest of each source
file and the digest as published, so anyone can check that nothing was quietly
edited. Merging a patch here would break that chain — the published file would
no longer correspond to any source, and the provenance table would become a
claim rather than a check.

The same content is also governed by disclosure rules (`docs/disclosure.md`)
that are applied upstream, before publication. A patch merged downstream would
bypass that application entirely.

So a change that should exist gets made upstream and re-extracted. An issue is
how it gets there; a pull request is a path that cannot end anywhere.

## What a good issue looks like

The controls in this repository are supposed to fail on demand. If you can
make one stay green while the thing it guards is broken, that is the report we
most want, and it does not need a fix attached:

```
make setup && make check     # every gate once, over this repository
make test                    # the suite, including the positive controls
```

State what you ran, what you expected the control to do, and what it did.
A reproduction beats a description; a description beats silence.

## Scope

This repository is an extract, not a product. It is not accepting feature
requests, roadmap input, or requests to make the example configuration match a
particular organisation. `config/literals.example.json` is fictional by design
and stays that way.
