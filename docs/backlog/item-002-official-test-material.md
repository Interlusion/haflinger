# ITEM-002: More official test material

| Meta | Value |
| :- | :- |
| **Status** | CANDIDATE |
| **Type** | feature |
| **Origin** | Approach review, KoSIT XSLT spike and ZUGFeRD corpus spike of 2026-10-30; the Definitions of Done of [REQ-002](../specs/req-002-conformance.md), [REQ-003](../specs/req-003-incoming-invoices.md) and [REQ-004](../specs/req-004-outgoing-invoices.md) |
| **Created** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Summary

Vendor the official material beyond KoSIT's test suite that the specs' Definitions of Done need, under [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md): CEN's per-rule unit tests, a selection of the ZUGFeRD corpus, a UBL credit note, the Factur-X rules and XML Schemas, and later KoSIT's technical and extension cases and Peppol's examples.

## Context / Motivation

| Source | Content | Needed by | Licence |
| :- | :- | :- | :- |
| CEN [`eInvoicing-EN16931`](https://github.com/ConnectingEurope/eInvoicing-EN16931) | 206 UBL invoice and 71 UBL credit note unit tests, a few for CII; 19 UBL and 15 CII examples | REQ-002-PRS-F007 | EUPL-1.2 |
| [`ZUGFeRD/corpus`](https://github.com/ZUGFeRD/corpus) | 240 files (151 PDFs) from many producers, with `fail/` folders | REQ-002-PRS-F003, REQ-002-PRS-F007, REQ-003-PRS-F003, REQ-003-PRS-F005, REQ-003-PRS-F007, REQ-003-PRS-NF003 | Apache-2.0 |
| KoSIT [`xrechnung-testsuite`](https://github.com/itplr-kosit/xrechnung-testsuite) | 6 extension cases; technical cases (comprehensive, minimal, CVD) | REQ-002-PRS-F003 (extension); more coverage of REQ-003 | Apache-2.0 |
| OpenPeppol [`peppol-bis-invoice-3`](https://github.com/OpenPEPPOL/peppol-bis-invoice-3) | Unit tests (`unit-UBL-PEPPOL` 63, `unit-CII-PEPPOL` 47, national rules), examples including credit notes | REQ-003-PRS-F001 (credit note) | to check |
| FeRD's [ZUGFeRD package](https://www.ferd-net.de/en/downloads/publications) (2.5.2, technically identical to Factur-X 1.09.2, 2026-08-04) | Official samples per profile; the Factur-X rules and XML Schemas per profile | REQ-002-PRS-F003, REQ-004-PRS-F004 | Schemas and Schematron Apache-2.0 by FeRD's [rights of use](https://www.ferd-net.de/en/ueber-uns/ressourcen-1/veroeffentlichungen/disclaimer-and-rights-of-use-zugferd); XSLT and samples not named (REQ-002 open question) |

**CEN's unit tests** are in VEFA `testSet` format: each `<test>` holds an `<assert>` with the rule IDs expected to succeed (`<success>`) or fail (`<error>`, `<warning>`), and an invoice fragment. A test is met when every expected failure fires and no expected success does. On 2026-10-30, with CEN's stylesheet of the tests' own commit (`b17b269`, rules 1.3.17), all 1,131 were met; the tests of tag `validation-1.3.16` against the 1.3.16 rules bundled in KoSIT's configuration, all 1,131 too; the 1.3.17 tests against the 1.3.16 rules, 1,066 (the misses all in BR-IG and BR-IP, changed in 1.3.17). The tests must therefore come from the release of the rules in use. The runner is now `tests/conformance/test_validate_official.py`: it serialises each fragment with ElementTree and validates it; fragments are constructed test input, so the original-bytes rule ([REQ-002-PRS-F006](../specs/req-002-conformance.md#req-002-prs-f006-the-document-as-received)) doesn't apply to them.

**The ZUGFeRD corpus** is 152 MB; only a selection is vendored. Since 2026-10-31, Mustang's own PDFs are in `tests/data/zugferd-corpus/`; the corpus's copies of FeRD's and FNFE-MPE's samples wait for their terms (open question below). The selection planned:

- one valid file per supported Factur-X profile (MINIMUM, BASIC WL, BASIC, EN 16931, EXTENDED, as XML and as PDF);
- one file per alternative spelling of BT-24 the corpus has (`urn:zugferd.de:2p0:minimum`, the ZUGFeRD 2.0 BASIC and EXTENDED identifiers, the colon spellings of BASIC and EXTENDED), for REQ-002-PRS-F003;
- a Peppol BIS invoice and an XRechnung 2.1 invoice, for REQ-002-PRS-F004;
- the EXTENDED invoice with two due dates, for REQ-003-PRS-F002;
- the broken PDFs REQ-003-PRS-NF003 uses, and a ZUGFeRD 1.0 and a FatturaPA file for the refusals of REQ-003-PRS-F006.

The two large Peppol invoices (25.7 MB, 61.1 MB) stay out; the benchmarks use a local clone.

**A PDF/A test file** for REQ-004-PRS-F007, with a licence that allows vendoring; none is chosen yet.

The KoSIT suite's CII and UBL pairs aren't independent (made with phax's converter, aligned by hand), which is one more reason for material from other producers.

## Open Questions

- The licences of Peppol's test files and FeRD's samples.
- FeRD's package is downloaded through a form (name, e-mail, consent to the rights of use): the maintainer downloads it; the provenance README records the version and the archive's SHA-256.
- Does the selection of the corpus need its own README per subfolder, or one with a table of the chosen files?

## Notes

The corpus was examined at commit `82e886fb21369e3e83c1e97170a4ff406deceee7` (2026-10-13).
