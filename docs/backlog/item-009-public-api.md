# ITEM-009: The public API, as wide as documented

| Meta | Value |
| :- | :- |
| **Status** | CANDIDATE |
| **Type** | question |
| **Origin** | Third review of 2026-11-01 |
| **Created** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Summary

Decide what Haflinger's public API is, and make the package say so, before the ERPNext app is written against it ([ITEM-003](item-003-erpnext-app.md)) and before the first release. Today it is wider than the specs document, and some of what a caller needs isn't exported.

## Context / Motivation

The specs define `read_invoice`, `validate`, `write_cii`, `haflinger.pdf.extract_xml` and `haflinger.pdf.embed`, with the model, `ReadResult`, `Finding` and the two errors, which `haflinger.__all__` exports. What the review found beyond that (2026-11-01):

- **Public names in modules that aren't private**, which a caller can import and come to rely on, though no spec defines them and some skip what the entry points guarantee:
  - `haflinger.kosit.read_invoice`, the tests' second reader ([ADR-005](../arc42/adr/ADR-005-own-mapping-kosit-as-check.md)): it takes no `max_size` and takes minutes on large files;
  - `haflinger.validation.check_rules`, which runs the rules without the XML Schema check first ([REQ-002-PRS-F011](../specs/req-002-conformance.md#req-002-prs-f011-xml-schema-first));
  - `haflinger.write.check_written` and `haflinger.write.refuse_if_invalid`;
  - `haflinger.cii.write`, which writes CII without any check ([REQ-004-PRS-F004](../specs/req-004-outgoing-invoices.md#req-004-prs-f004-xml-schema), [REQ-004-PRS-F005](../specs/req-004-outgoing-invoices.md#req-004-prs-f005-official-rules)).
- **No `__all__` in the submodules**, so nothing tells their public names from helpers.
- **Not exported**: `Flag`, the type of a finding's flag, and the target profiles of writing (`haflinger.write.TARGET_PROFILES`), which a caller needs to choose BT-24 before `write_cii`.
- **No helper says whether findings make an invoice invalid.** The rule, no finding with flag `fatal` or `error`, lives only in [REQ-002-PRS-F002](../specs/req-002-conformance.md#req-002-prs-f002-findings); each caller would write it again.
- **Sequences of findings differ in type**: `validate` returns a `list`, while `ReadResult.findings` and `InvoiceWriteError.findings` are tuples.
- **The package docstring is one line**, so `help(haflinger)` says little about the entry points.

## Options

- **Private modules**: rename the modules that aren't API (`_kosit`, `_validation`, `_write`, `_cii`, `_ubl` and so on), so that only `haflinger` and `haflinger.pdf` are public. Clear, but the tests and scripts import through private names.
- **`__all__` per module**: keep the modules, declare in each what is public, and give the helpers a leading underscore. Lighter; leaves more names to keep stable.
- **Exports and helpers**: either way, export `Flag` and the target profiles from `haflinger`, add a helper such as `is_valid(findings)` that applies REQ-002-PRS-F002's rule, and return tuples from `validate`, as everywhere else.

## Open Questions

- Which of the above, and which names the app needs beyond the five entry points?
- Should `validate` return a tuple, changing REQ-002-PRS-F001's signature, or the others a list?
- Is the helper for validity a function, or a property of a result type that `validate` would return instead of a bare sequence?
- Where the API is documented for callers: the package docstring, the README, or generated reference documentation.
