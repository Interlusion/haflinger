# Backlog

Quick items. Items with detail have their own file (`item-NNN-*.md`); done or rejected ones move to `archive/`. Requirements already in the specs are not repeated here: the specs are the contract, the tickets come from them.

- [ ] A link check: no wiki-links, and every relative link and `#anchor` resolves (lychee, offline), in CI.
- [ ] Check the Python version of Frappe/ERPNext v16 benches against `requires-python = ">=3.14"` ([ADR-002](../arc42/adr/ADR-002-toolchain.md), trigger 2).
- [ ] Reserve `haflinger` on PyPI (free on 2026-10-30).
- [ ] Before the first release: confirm the licence of `saxonche` and check shipping CEN's EUPL-1.2 files in the Apache-2.0 package ([ADR-009](../arc42/adr/ADR-009-licences-and-name.md)).
- [ ] Is about 105 MB of Saxon acceptable in a bench, and does any target run on musl, for which there is no wheel ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md))?
- [ ] Peppol BIS rules, when Haflinger sends through Peppol: incoming Peppol invoices get the EN 16931 rules and `HAFL-PROFILE` until then ([REQ-002-PRS-F004](../specs/req-002-conformance.md#req-002-prs-f004-profiles-not-supported)); the licence of OpenPeppol's files is still to check ([ITEM-002](item-002-official-test-material.md)).
- [ ] A coverage report for maintainers: KoSIT's reading stylesheet over the official test files and the ZUGFeRD corpus, listing the business terms they carry that the model doesn't hold, by how often they occur; it orders the model's growth by what incoming invoices commonly carry ([ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)).
- [ ] Java tools as oracles in CI, never at runtime: KoSIT's validator over every invoice Haflinger writes; phax's `en16931-cii2ubl` as a third reader of the KoSIT suite.
