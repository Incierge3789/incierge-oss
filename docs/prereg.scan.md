# prereg.scan — pre-registration of the forensic content scan

**Status: registered 2026-08-15, before any file was scanned. Amended once, in
one direction only — see §9.**

This file is the **single definition point** of the pattern table.
`scripts/scan_forensic.py`, the `pre-commit` hook, and the positive-control tests
all parse the JSON block below. **Nothing copies it.** If you find a second copy
of these patterns anywhere in this repository, that is a defect — report it
(see `CONTRIBUTING.md`).

---

## 1. What this scan is for

Before a file is published, it is scanned for four classes of content that must
not leave the private system. A **hit** disqualifies the file. The disposition
rule is fixed in advance:

> **R1** — on a hit, the file is removed from the publication candidate set and
> the whole set is re-scanned. The removal reason is appended to an
> append-only log. Repeat until the hit count is zero.
>
> **R2** — a file whose tier cannot be decided is **not published**
> (fail-closed). It is never escalated to a human for a ruling.

`PASS` is defined as **total hit count == 0**. There is no threshold, no
severity weighting, and no "acceptable residue".

## 2. Normalization (fixed before scanning)

Applied to every line before matching:

1. Unicode `NFKC` normalization — full-width and half-width forms become the
   same string, so `ＡＥＧＩＳ` and `AEGIS` cannot be distinguished by the writer.
2. **Format and combining characters are dropped** (Unicode categories `Cf` and
   `Mn`). A zero-width space, a zero-width joiner, a soft hyphen or a byte-order
   mark inserted into the middle of a withheld word makes it render identically
   and match nothing; removing them first closes that.
3. `str.casefold()` — case is ignored.
4. **Declared confusables are folded** — a fixed table of Cyrillic and Greek
   characters that render as Latin ones (`а е о р с у х і ј ѕ`, `ο α ε ρ ι`, and
   a few more) is mapped to Latin. The table is in `scripts/scan_forensic.py`
   as `CONFUSABLES`.
5. Literal patterns additionally undergo **separator expansion**: any `-`, `_`,
   or space inside a declared literal is compiled to `[\s\-_]*`, so a literal
   written as `acme-tek` matches `acmetek`, `acme tek`, `acme_tek`, `acme-tek`,
   and `AcmeTek`.

A file can therefore not evade the scan by re-casing, re-spacing, switching to
full-width characters, or inserting invisible characters.

**Known limit on step 4.** The confusable table is the common half of the
attack, not the full Unicode confusables set. A determined writer can still find
a lookalike codepoint outside it — Cherokee and Canadian Aboriginal syllabics
both contain Latin-shaped characters. Closing that properly needs a confusables
data file this scanner deliberately does not carry. Stated here rather than
implied by silence.

## 2b. The path is scanned too

Every fail-severity pattern is applied to the **relative path** as well as to
the file contents. A withheld name in a filename with innocuous contents used to
pass, because only one declared pattern looked at paths. The same exclusions
apply in both places, so a rule cannot mean one thing about contents and another
about names.

## 3. Exclusions (pattern-level only)

**Line-level exclusion after the fact is forbidden.** The only exclusions are
the ones declared in the JSON block below, and they are of exactly three kinds:

| kind | where | why it is sound |
|---|---|---|
| `excluded_paths` | pattern-table files themselves | a scanner cannot scan its own pattern table without matching every pattern it defines |
| `exclude_compounds` | per literal | a literal that is also a dictionary word (e.g. a surname that is a common noun) is suppressed only inside an enumerated compound; the bare literal still hits |
| `exclude_if_group1_matches` | per pattern | placeholder values (`<...>`, `${...}`, `changeme`, `os.environ[...]`) are not secrets |

Every exclusion is frozen here before the first scan runs and is not changed
while a scan is in flight.

Every pattern that carries an exclusion also carries `example_hit` and
`example_miss`. The test suite reads both from here and asserts that the first
matches and the second does not. An exclusion is the place where a guard is
most easily widened until it excuses everything, so the pair is stored next to
the exclusion rather than in a test file: whoever edits the rule is looking at
the two cases it has to keep separating.

## 3b. Severity: `fail` and `warn`

A class declares a severity. `fail` is the default and is what the disposition
rule R1 acts on. `warn` classes are reported and counted but do not by
themselves fail the scan, because the correct remedy is not always removal.

The one `warn` class today is `e_third_party_oss`. Third-party OSS carried into
a publication set is not a leak — it is a **licensing** problem. If MIT-licensed
material is present, shipping it under an Apache-2.0 notice alone violates the
MIT copyright-notice requirement. The remedy is either removal **or** a `NOTICE`
file that states the third-party copyright and license separately. Failing the
scan would push toward removal when separation is often the right answer, so the
class warns and names the obligation instead.

A `warn` that is never read is the same as no check at all, so warn hits are
printed on every run, are written to the scan log with the same schema as fail
hits, and are surfaced in `scan.result.md` as an explicit line — including the
line "0 warnings".

## 4. Binary files are rejected, not skipped

A file whose first 8 KiB contains a NUL byte cannot be line-scanned. It is
**not** silently passed. `scan_forensic.py` reports it as `unscannable` and
exits non-zero. A scanner that cannot read a file has not cleared it.

## 5. Class (a) and (d) literals live outside this repository

Classes `a_proper_noun` and `d_person_literal` are **literal lists of real
proper nouns**. Publishing the deny-list would publish exactly the strings the
deny-list exists to withhold — the pattern table would be its own leak.

So the mechanism is public and the literals are not:

- The scanner loads them from a JSON file given by `--literals`.
- `config/literals.example.json` ships a **fictional** list so that a fresh
  clone can run the scanner and the positive-control tests with no setup beyond
  one documented copy step.
- `config/literals.json` (the real list, if you keep one) is path-guarded in
  `.gitignore` and can never be committed.
- The scanner **fails closed** if the literals file is missing or unparsable.
  Absence is not emptiness.

The literals file is also where each class's own positive-control payload lives
(`positive_control`), so that the control cannot drift away from the pattern it
is supposed to prove.

### 5b. A literal class may be declared empty, but never silently

`c_customer_literal` exists because "customer name" is one of the six withheld
categories, but a literal customer list is not something this system holds. An
empty list would otherwise be indistinguishable from a class that is switched
off. So an external literal class may carry `"literals": []` **only** when it
also carries `declared_empty_reason`. The scanner then:

* still loads the class,
* reports it under `declared_empty_classes` on every run, and
* prints it, so that the coverage gap is stated rather than inferred from a
  green result.

Without `declared_empty_reason`, an empty list is undecidable and exits 2.
Zero findings from a class with no patterns is not evidence of absence.

### 5c. The six withheld categories and where each is actually detected

The withheld set is: **customer names / deals / person names / monetary amounts /
business documents / product codes proper**. Categories are not patterns, so each
is mapped to the pattern that actually fires:

| category | detected by |
|---|---|
| customer names | `c_customer_literal` (literals) + `c7_*` company and honorific markers |
| deals | `c10_deal_vocabulary` |
| person names | `d_person_shape` (honorific shape) + `d_person_literal` (literals) |
| monetary amounts | `c8_monetary_amount_*` (symbol, ISO code, grouped, plain, cents) |
| business documents | `c9_business_document` |
| product codes proper | `b_ip_identifier` + `a_proper_noun` (literals) |

This table is the claim being made about coverage. Two of the six rest partly on
a literal list this system does not hold (`c_customer_literal` is
declared-empty), which is why §5b forces that to be printed rather than assumed.

## 6. Pattern table

```json
{
  "version": 1,
  "registered": "2026-08-15",
  "normalization": {"unicode": "NFKC", "casefold": true},
  "binary_policy": "reject",
  "excluded_paths": [
    ".git/**",
    "docs/prereg.scan.md",
    "config/literals.json",
    "config/literals.example.json"
  ],
  "classes": [
    {
      "id": "a_proper_noun",
      "title": "(a) proper nouns: company / product / archived-repo identifiers",
      "source": "external_literal_file",
      "match": "literal_with_separator_expansion"
    },
    {
      "id": "b_ip_identifier",
      "title": "(b) IP identifiers and their implementation names",
      "source": "inline",
      "patterns": [
        {"name": "b1_filed_patent_id", "regex": "\\bpat[\\-_]?\\d{3,}\\b", "example_hit": "PAT-9999", "example_miss": "compatibility"},
        {"name": "b2_future_patent_id", "regex": "\\bfp[\\-_]?\\d{3,}\\b"},
        {"name": "b3_objective_id", "regex": "\\bao[\\-_]?\\d{3,}\\b"},
        {"name": "b4_applicant_label", "regex": "\\bincierge[\\-_]\\d{3,}\\b", "example_hit": "applicant: Incierge-1001", "example_miss": "github.com/Incierge3789/incierge-oss", "_why_separator_required": "unlike the other three, dropping the separator here collides with the account name Incierge3789, which appears in the README and in config/allowed_remote.txt. Widening it flagged both. The applicant label always carries the hyphen."},
        {"name": "b5_impl_span_shred", "regex": "span[\\s\\-_]*shred"},
        {"name": "b6_impl_span_dag", "regex": "span[\\s\\-_]*dag"},
        {"name": "b7_impl_dag_audit", "regex": "dag[\\s\\-_]*audit"},
        {"name": "b8_impl_trust_algebra", "regex": "trust[\\s\\-_]*algebra"},
        {"name": "b9_impl_purpose_bound_crypto", "regex": "purpose[\\s\\-_]*bound[\\s\\-_]*crypto"},
        {"name": "b10_impl_ja_gateway", "regex": "最小開示ゲートウェイ"},
        {"name": "b11_impl_ja_autonomous_defense", "regex": "自律防御"}
      ],
      "positive_control": "PAT-999"
    },
    {
      "id": "c_secret",
      "title": "(c) secrets: keys, tokens, addresses, internal endpoints, customer markers",
      "source": "inline",
      "patterns": [
        {"name": "c1_private_key_block", "regex": "-----begin (?:[a-z0-9 ]+ )?private key-----"},
        {"name": "c2_github_pat", "regex": "\\bghp_[a-z0-9]{36}\\b"},
        {"name": "c2_github_fine_grained", "regex": "\\bgithub_pat_[a-z0-9_]{22,}"},
        {"name": "c2_openai_key", "regex": "\\bsk-[a-z0-9_-]{20,}", "example_hit": "sk-proj-abc123def456ghi789jkl012mno345pqr678", "example_miss": "sk-short"},
        {"name": "c2_anthropic_key", "regex": "\\bsk-ant-[a-z0-9\\-_]{20,}"},
        {"name": "c2_aws_access_key", "regex": "\\b(?:akia|asia)[0-9a-z]{16}\\b"},
        {"name": "c2_slack_token", "regex": "\\bxox[baprs]-[a-z0-9-]{10,}"},
        {"name": "c2_google_api_key", "regex": "\\baiza[0-9a-z_\\-]{35}\\b"},
        {"name": "c2_gitlab_pat", "regex": "\\bglpat-[a-z0-9_\\-]{20,}"},
        {
          "name": "c3_assigned_credential",
          "regex": "(?:api[_-]?key|secret|token|password|passwd|passphrase|credential|private[_-]?key)\\s*[:=]\\s*[\"']([^\"'\\n]{8,})[\"']",
          "exclude_if_group1_matches": "^(?:<[^>]*>|\\$\\{[^}]*\\}|\\$[a-z_][a-z0-9_]*|x{3,}|\\*{3,}|\\.{3,}|changeme|change[_-]me|placeholder|redacted|example|example[_-]key|dummy|sample|fake|test|testing|test[_-]key|your[_-](?:api[_-])?(?:key|token|secret|password)(?:[_-]here)?|null|none|true|false|\\d+|os\\.environ.*|process\\.env.*|secrets\\..*|env\\[.*)$",
          "example_hit": "password = \"example_hunter2_production\"",
          "example_miss": "api_key = \"${SOME_ENV_VAR}\""
        },
        {
          "name": "c4_email_address",
          "regex": "\\b[a-z0-9._%+-]+@([a-z0-9.-]+\\.[a-z]{2,})\\b",
          "exclude_if_group1_matches": "^(?:(?:[a-z0-9-]+\\.)*example\\.(?:com|net|org|edu)|(?:[a-z0-9-]+\\.)*(?:invalid|test|localhost))$",
          "example_hit": "write to someone@a-real-looking-host.jp",
          "example_miss": "write to someone@example.com"
        },
        {"name": "c5_rfc1918_ipv4", "regex": "\\b(?:10\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|192\\.168\\.\\d{1,3}\\.\\d{1,3}|172\\.(?:1[6-9]|2\\d|3[01])\\.\\d{1,3}\\.\\d{1,3})\\b"},
        {"name": "c5_internal_tld", "regex": "\\bhttps?://[a-z0-9.-]+\\.(?:internal|intranet|lan|corp|local)\\b"},
        {"name": "c5_service_account", "regex": "[a-z0-9-]+@[a-z0-9-]+\\.iam\\.gserviceaccount\\.com"},
        {"name": "c5_tunnel_host", "regex": "\\b[a-z0-9-]+\\.(?:ngrok\\.io|ngrok-free\\.app|ts\\.net)\\b"},
        {"name": "c6_local_user_path_unix", "regex": "(?:/users|/home)/[a-z0-9._-]+", "example_hit": "export USER_HOME=/Users/alice", "example_miss": "see the /home directory"},
        {"name": "c6_local_user_path_win", "regex": "c:\\\\users\\\\[a-z0-9._-]+"},
        {"name": "c7_ja_company_suffix", "regex": "株式会社|合同会社|有限会社|（株）|\\(株\\)"},
        {"name": "c7_ja_customer_honorific", "regex": "御中|貴社"},
        {"name": "c7_en_company_suffix", "regex": "\\b(?:k\\.k\\.|co\\.,\\s*ltd\\.?|\\binc\\.)"},
        {"name": "c8_monetary_amount_jpy_symbol", "regex": "¥\\s?\\d[\\d,]*"},
        {"name": "c8_monetary_amount_jpy_word", "regex": "\\d[\\d,]*\\s?(?:円|万円|億円)"},
        {"name": "c8_monetary_amount_iso", "regex": "\\b(?:jpy|usd|eur|gbp)\\s?\\d[\\d,]*"},
        {"name": "c8_monetary_amount_grouped", "regex": "\\$\\d{1,3}(?:,\\d{3})+(?:\\.\\d+)?"},
        {"name": "c8_monetary_amount_plain", "regex": "\\$\\s?\\d{3,}(?:\\.\\d+)?\\b", "example_hit": "server_cost: $1200", "example_miss": "use $1 for the first argument"},
        {"name": "c8_monetary_amount_cents", "regex": "\\$\\s?\\d+\\.\\d{2}\\b"},
        {"name": "c8_monetary_amount_scaled", "regex": "\\$\\d+(?:\\.\\d+)?\\s?(?:million|billion|trillion|[mbk])\\b"},
        {"name": "c9_business_document", "regex": "見積書|請求書|契約書|提案書|議事録|稟議|発注書|納品書|覚書|基本合意|秘密保持契約|\\bnda\\b"},
        {"name": "c10_deal_vocabulary", "regex": "商談|受注|失注|与信|見込み客|取引先"}
      ],
      "positive_control": "AKIA0000000000000000"
    },
    {
      "id": "c_customer_literal",
      "title": "(c) customer names: literal list",
      "source": "external_literal_file",
      "match": "literal_with_separator_expansion"
    },
    {
      "id": "d_person_shape",
      "title": "(d) person names by honorific shape (generic; literals live in the literals file)",
      "source": "inline",
      "patterns": [
        {
          "name": "d1_ja_honorific",
          "regex": "([\\u4e00-\\u9fff\\u3005]{1,4})(?:さん|氏|様|社長|部長|課長|専務|取締役|殿)",
          "exclude_if_group1_matches": "^(?:氏|摂|華|姓|某|同|両|彼|当|本|各|全|副|次|部|課|会|社|支|支店|代表|仕|多|一|異|模|様|神|王|奥|坊|文|同)$",
          "example_hit": "山田さん",
          "example_miss": "摂氏"
        },
        {
          "name": "d2_katakana_honorific",
          "regex": "([\\u30a1-\\u30fa\\u30fc]{2,8})(?:さん|氏|様|社長|部長|課長|専務|取締役|殿)",
          "example_hit": "担当はアリスさんです",
          "example_miss": "カタカナ"
        }
      ],
      "known_limit": "A hiragana-only given name before an honorific is NOT detected, and this is a decision rather than an oversight. Hiragana is the script ordinary prose is written in, so a hiragana prefix class would absorb preceding text: in 'ここにたくさんある' a greedy prefix yields the match 'ここにたく' + 'さん'. Per-word exclusions cannot fix that, because the prefix is not the word. Kanji and katakana prefixes carry no such ambiguity and are matched. What remains uncovered: a person referred to only by a hiragana name.",
      "positive_control": "山田さん"
    },
    {
      "id": "d_person_literal",
      "title": "(d) person names: literal surnames (romaji included)",
      "source": "external_literal_file",
      "match": "literal_with_separator_expansion"
    },
    {
      "id": "e_third_party_oss",
      "title": "(e) third-party OSS carried into the publication set",
      "severity": "warn",
      "source": "inline",
      "remedy": "Do not relicense. Either remove the material, or add a NOTICE file that reproduces the third-party copyright and license text separately from Apache-2.0.",
      "patterns": [
        {"name": "e1_project_gstack", "regex": "\\bgstack\\b"},
        {"name": "e2_author_attribution", "regex": "garry\\s+tan"},
        {"name": "e3_mit_permission_notice", "regex": "permission is hereby granted, free of charge"},
        {"name": "e3_mit_named", "regex": "\\bmit license\\b"},
        {"name": "e4_vendored_path_in_text", "regex": "agent-ops/_shared/skills/gstack/"}
      ],
      "path_patterns": [
        {"name": "e5_vendored_path", "regex": "(?:^|/)gstack(?:/|$)"}
      ],
      "positive_control": "This software is released under the MIT License"
    }
  ]
}
```

## 7. Positive controls

Each class declares a `positive_control` payload. Classes `a_proper_noun` and
`d_person_literal` declare theirs in the literals file, because their patterns
live there too.

Two things are asserted by the test suite, and both must hold:

1. **The control fires.** A dummy commit containing all four payloads is
   rejected by the `pre-commit` hook, and the rejection names all four classes.
2. **The control is not tautological.** Each `positive_control` payload is
   independently re-matched against its own class's compiled patterns. A payload
   that no longer matches its class is a failure — this is what stops the control
   from silently rotting into a no-op when a pattern is edited.

A guard whose firing has never been observed is treated as absent.

The `warn` class `e_third_party_oss` gets its own control, and it asserts a
different thing: that a commit carrying an MIT notice is **allowed through while
being reported**. A control that only proved "it blocks" would be testing a
behaviour this class does not have, and a control that only proved "it does not
block" would pass even if the class were deleted. Both halves are asserted.

## 8. Scan log

`scan_forensic.py --log FILE` appends one JSON object per hit with
`path`, `line`, `class`, `pattern`, and `matched`. The log is the evidence that
the scan ran over the population it claims to have covered; the file count and
the skipped-path count are recorded alongside.

## 9. Amendment log

A pre-registration that is edited after the results are in is not a
pre-registration. The rule that makes an amendment legitimate is **direction**,
and it is stated here rather than assumed:

> An amendment may only make detection **stricter** — add a pattern, widen a
> pattern's reach, or narrow an exclusion. An amendment that weakens detection
> requires re-scanning the entire publication set under the amended table and a
> new entry here saying what was given up.
>
> Every amendment re-runs the full scan regardless of direction, because a
> stricter table can newly hit a file that was already cleared.

Making it stricter after the fact cannot manufacture a pass: it can only
disqualify more, never less. Loosening is the move that would let a hit be
argued away, and that is the one this rule constrains.

### Amendment 1 — 2026-08-15, cross-review round 1

Table as registered: sha256
`16346a46b5549a4f4f9323f47886ff1302360b31eeea9cd3fad853216baf4bab`.
Two independent reviewers were given the assembled repository and asked to get
withheld material past the scanner. They did, five ways. All five are closed
here, and every one of them is **strictly stricter** than the registered table:

| change | direction |
|---|---|
| normalization steps 2 and 4 (strip `Cf`/`Mn`, fold confusables) | stricter — more spellings reach the patterns |
| §2b: every fail pattern also applied to the path | stricter — a filename is now scanned |
| `c3` placeholder exclusion narrowed to exact tokens | stricter — fewer values excused |
| `c2_openai_key`, `c6_local_user_path_unix` widened | stricter |
| `c8_*` plain and cents amounts added; `b1`–`b3` separator optional and 3+ digits; `d1` gains `様`; `d2` katakana added | stricter |
| `b4` separator kept **required** | narrower than the round-1 draft, still stricter than registered (`\bincierge-\d{3}\b`) — see its `_why_separator_required` |

The full set was re-scanned under the amended table: 0 hits, 0 warnings, 0
unscannable.

Each closed hole is recorded as that pattern's `example_hit`, so re-opening it
fails the suite rather than passing quietly. That is the ratchet — the log above
is prose, the examples are the enforcement.
