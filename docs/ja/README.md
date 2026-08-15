# Copies from the private system (Japanese)

Seven files here came from the private repository at commit
`aa1a5a68e27b3992a26386edc301e898b8887153` (2026-08-15T06:59:46+09:00). Five are
in Japanese, which is the language the system is operated in.

They are copies rather than translations on purpose. A translated operating
document is a second definition point, and the translated one is the one that
stops being updated. Where an English explanation was needed it was written as
its own document (`docs/architecture.md`, `docs/goal.md`,
`docs/ledger_schema.md`, `docs/disclosure.md`) that refers to these rather than
restating them.

## Five of them are no longer verbatim, and that is stated rather than glossed

An open-world audit — one that ignored the pattern table and asked what a
stranger could infer — found that the copies published private path structure
and an internal identifier namespace that the curated English documents had
deliberately kept out. `docs/disclosure.md` rule **D5** says structure is
private, so the strings were removed.

Removing them costs the verbatim claim for those files. Keeping the claim would
have cost the boundary. The table below records which is which, so the claim
that survives is the one that is true.

### Verbatim — the published bytes equal the source bytes (2 files)

| path | sha256 (source **and** published) | what it is |
|---|---|---|
| `docs/ja/ADR-0003-naming.md` | `ea26dda9fd050d8fd0c9a8201f80d87520587febe0ade06bbf0ccb480ab0daa2` | the naming convention for layers |
| `docs/ja/guard_positive_tests.md` | `8bdb96629e361db7dcc094edf27fd7b3e97973fd08a4ef7e12a60b8f5ed23102` | the ledger of which guards have actually been seen firing, and which have not |

Compare a file here against its row to check that nothing was quietly edited.

### Adapted — declared changes only, everything else byte-identical (5 files)

| path | sha256 of the **source** | sha256 as **published** | what changed, and why |
|---|---|---|---|
| `docs/ja/ARCHITECTURE.md` | `29e30c4065562dd43063cce89f8df43142d6ae3578bbf9419f99d346386cfb85` | `7aea7db80af883d61e9f526c4be9ebce29858a8b2077b8192c7489391df9e9d9` | one private path replaced by the layer's name (D5) |
| `docs/ja/DISPOSITION.md` | `eb14cfb62e6bbcdcea7e0be6271e4fba56ce659740f76ef518f26aa3e9974f68` | `44ee7d2f70e5c33c438f51dcd43d983957b4b0677751ba6d92b365675c6067ac` | one private record path removed, and six internal work-item identifiers replaced by plain description (D5). **The measurements were kept** — see below |
| `schema/emit_reason_codes.yaml` | `277910b32753b8ef76cfb99d149da54f1a4d30322b241993cf68b3806b1a1171` | `f653ef721e074819e935bcfc99c3bc351687fe01372c340b52a14777628da978` | one doctrine path replaced by the doctrine's name (D5) |
| `scripts/tautological_control_gate.py` | `ee8366eb7f835369e6bea77ea85158dfc1eab8a1d9e03e5bb51cdd7a1c090a14` | `23af2366de121576ac30befbced3c198c4bb4b1c8f03a2a16b125cfd202edff0` | two glob patterns naming private lanes removed from `CONTROL_GLOBS`; the remaining one is the only path that exists here anyway (D5) |
| `scripts/tests/test_tautological_control_gate.py` | `024cc321a97ed6f9ab90e8fda4f4be13b52af70198876c6fcd69039fcd063632` | `02fe576afc83ccd4959ce8f804109ba254766b46f5fcb3dd2e0cf1d848fc3335` | one internal work-item identifier removed from its docstring (D5) |

Nothing was removed from these files except structure. **No measurement, no
threshold and no conclusion was cut.** The direction was deliberate: the
disclosure line says measured values and registered criteria are public, so the
correct repair for the divergence between these copies and the English ledger
was to **raise the ledger**, not to trim the copies. `NR-005` in
`ledger/negative_results.jsonl` now carries the numbers that only existed here.

`scripts/tests/test_disclosure_parity.py` fails if that divergence reopens.

## Reading notes

- Internal cross-references in these documents point at things that are not part
  of this publication. That is expected; they are copies of documents from a
  larger repository, not documents written for this one. Where such a reference
  was a **path**, it was replaced.
- `guard_positive_tests.md` is the most directly useful of them even without
  Japanese: the second table lists guards whose firing has **never been
  observed**, which are treated as absent rather than as working. That table is
  the one that would be missing from a document written to look good.
- `DISPOSITION.md` records why two lines of work were closed, including one
  closed as unfit for its substrate rather than as a failure to reach a
  threshold. Three of the five entries in `ledger/negative_results.jsonl`
  correspond to it.
