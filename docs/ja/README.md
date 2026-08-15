# Verbatim copies (Japanese)

Seven files in this repository are byte-identical copies taken from the private
repository at commit `aa1a5a68e27b3992a26386edc301e898b8887153`
(2026-08-15T06:59:46+09:00). Five of them are in Japanese, which is the
language the system is operated in.

They are copies rather than translations on purpose. A translated operating
document is a second definition point, and the translated one is the one that
stops being updated. Where an English explanation was needed it was written as
its own document (`docs/architecture.md`, `docs/goal.md`,
`docs/ledger_schema.md`) that refers to these rather than restating them.

## Digests

Each was scanned against the frozen pattern table in `docs/prereg.scan.md`
before being placed here, and each returned zero hits.

| path | sha256 of the source file | what it is |
|---|---|---|
| `docs/ja/ARCHITECTURE.md` | `29e30c4065562dd43063cce89f8df43142d6ae3578bbf9419f99d346386cfb85` | the layer model of the private system |
| `docs/ja/DISPOSITION.md` | `eb14cfb62e6bbcdcea7e0be6271e4fba56ce659740f76ef518f26aa3e9974f68` | closed questions: what was rejected or frozen, and on what evidence |
| `docs/ja/ADR-0003-naming.md` | `ea26dda9fd050d8fd0c9a8201f80d87520587febe0ade06bbf0ccb480ab0daa2` | the naming convention for layers |
| `docs/ja/guard_positive_tests.md` | `8bdb96629e361db7dcc094edf27fd7b3e97973fd08a4ef7e12a60b8f5ed23102` | the ledger of which guards have actually been seen firing, and which have not |
| `schema/emit_reason_codes.yaml` | `277910b32753b8ef76cfb99d149da54f1a4d30322b241993cf68b3806b1a1171` | the closed label set used by `schema/ledger.json` |
| `scripts/tautological_control_gate.py` | `ee8366eb7f835369e6bea77ea85158dfc1eab8a1d9e03e5bb51cdd7a1c090a14` | detector for controls that cannot fail |
| `scripts/tests/test_tautological_control_gate.py` | `024cc321a97ed6f9ab90e8fda4f4be13b52af70198876c6fcd69039fcd063632` | its controls |

The digests are of the **source** files. Comparing a file here against its row
is how you check that nothing was quietly edited on the way out.

## Reading notes

- Internal cross-references in these documents point at paths that are not part
  of this publication. That is expected; they are copies of documents from a
  larger repository, not documents written for this one.
- `guard_positive_tests.md` is the most directly useful of them even without
  Japanese: the second table lists guards whose firing has **never been
  observed**, which are treated as absent rather than as working. That table is
  the one that would be missing from a document written to look good.
- `DISPOSITION.md` records why two lines of work were closed, including one
  closed as unfit for its substrate rather than as a failure to reach a
  threshold. Two of the four entries in `ledger/negative_results.jsonl`
  correspond to it.
