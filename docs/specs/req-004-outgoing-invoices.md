# REQ-004: Haflinger Outgoing Invoices — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Draft |
| **Version** | 0.3 |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Intended Use

Sending an invoice: turning the model into the XML and PDF that leave the company. Outgoing invoices are CII only, in two profiles ([ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md)): XRechnung for public authorities, ZUGFeRD EN 16931 for businesses. Haflinger hands out an invoice only when it passes the XML Schema and the official rules of its profile.

Writing is checked with what the read side has: Haflinger's reader, KoSIT's reading stylesheet, the XML Schema of CII and the official rules; no hand-written expected XML.

Out of scope: writing UBL; sending by e-mail, portal or Peppol (the caller, providers); rendering the readable PDF, and making it PDF/A (the caller; for ERPNext, [ITEM-003](../backlog/item-003-erpnext-app.md)); completeness under German VAT law beyond the official rules, such as the tax number or VAT ID and the delivery date of §14(4) UStG (the caller; for ERPNext, [ITEM-003](../backlog/item-003-erpnext-app.md)); the Sales Invoice in ERPNext (the app, [ITEM-003](../backlog/item-003-erpnext-app.md)).

Read [REQ-001](req-001-core.md) first: it holds the personas, stories and terms, and the rules every spec follows.

Key constraints: a profile is written only when the model holds every term its rules require ([ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)); ZUGFeRD PDF handling is in the library, in the optional extra `pdf` ([ADR-001](../arc42/adr/ADR-001-library-and-app.md)).

## User Stories

The personas are [REQ-001's](req-001-core.md#personas).

- REQ-004-P1-1. As the operator, I need the invoice I send to be read by the recipient exactly as it stands in my books.
- REQ-004-P1-2. As the operator, I need Haflinger to stop an invoice the recipient's system would reject, and tell me why, before it leaves.
- REQ-004-P2-1. As the maintainer, I need the writer checked by the official reading and rules, so that I don't have to keep expected XML up to date by hand.
- REQ-004-P3-1. As the integrator, I need one call that turns the model into CII, and one that turns CII and a rendered PDF into a ZUGFeRD PDF.

## Requirement Rules

- SHALL = mandatory · SHOULD = recommended · MAY = optional
- Every SHALL verifiable (test / benchmark / inspection / analysis)
- One requirement = one idea

## Terms

- **Round trip**: read a file, write its model as CII, read the result again.
- **Target profile**: the profile named in the model's BT-24, which decides the rules an outgoing invoice must pass.

## URS — Functional

#### REQ-004-URS-F001: Write CII

**Description**: The library SHALL write an invoice model as CII XML.

**Related User Stories**: REQ-004-P3-1

#### REQ-004-URS-F002: Only valid invoices leave

**Description**: The library SHALL hand out a written invoice, as XML or embedded in a PDF, only when it passes the XML Schema and the official rules of its target profile, and SHALL otherwise refuse it with the reasons.

**Related User Stories**: REQ-004-P1-2 | **Rationale**: [ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md); a rejected invoice is a late payment.

#### REQ-004-URS-F003: Read back unchanged

**Description**: A written invoice SHALL read back to the model it was written from, with Haflinger's reader and with KoSIT's.

**Related User Stories**: REQ-004-P1-1, REQ-004-P2-1

#### REQ-004-URS-F004: ZUGFeRD PDFs

**Description**: The library SHALL embed a written invoice into a PDF/A file so that the result is a ZUGFeRD PDF of the invoice's profile.

**Related User Stories**: REQ-004-P3-1

## URS — Non-Functional

#### REQ-004-URS-NF001: Checked by the read side

**Description**: The writer SHALL be tested through the read side and the official rules over the official test files, not against expected XML.

**Related User Stories**: REQ-004-P2-1

#### REQ-004-URS-NF002: Writing adds little to validation

**Description**: Writing SHALL add little to the time validation takes, large invoices included.

**Related User Stories**: REQ-004-P1-2

## PRS — Functional

#### REQ-004-PRS-F001: One entry point

**Description**: `haflinger.write_cii(invoice: Invoice) -> bytes` SHALL return a CII D16B document, UTF-8 with an XML declaration, when it passes REQ-004-PRS-F004 and REQ-004-PRS-F005. Otherwise it SHALL raise `haflinger.InvoiceWriteError`, and no other exception, with a reason that names the business term where there is one ([REQ-001-PRS-F005](req-001-core.md#req-001-prs-f005-refusals-and-findings-name-their-subject)). `InvoiceWriteError` SHALL carry `findings` and `document`:

- **Before writing**, with no findings and no document, when the model's BT-24 is no supported target profile (REQ-004-PRS-F002); a value has the wrong type (an amount, quantity, price or rate that isn't a finite `Decimal`, a date that isn't a `date`, a text that isn't a `str`); a text is empty, has surrounding whitespace, or holds a character XML 1.0 doesn't allow; or the model holds a term without one it needs to be written (BT-111 without BT-6).
- **After writing**, with the findings and the written document, when it fails REQ-004-PRS-F004 or REQ-004-PRS-F005.

**Related URS**: REQ-004-URS-F001, REQ-004-URS-F002

**Definition of Done**: a test writes a valid invoice and gets UTF-8 bytes with an XML declaration; a test writes an invoice whose BT-112 is off by one cent and gets `InvoiceWriteError` with `BR-CO-15` among its findings and the document; one test per refusal before writing, each naming its business term (a float in BT-112, a string in BT-2, `" Example GmbH"` in BT-27, a control character in BT-153, BT-111 without BT-6).

#### REQ-004-PRS-F002: Supported target profiles

**Description**: `write_cii` SHALL write only these target profiles, by their BT-24 exactly as given, and SHALL refuse every other BT-24, the alternative spellings of [REQ-002-PRS-F003](req-002-conformance.md#req-002-prs-f003-rule-sets) and the other editions of [REQ-002-PRS-F009](req-002-conformance.md#req-002-prs-f009-editions-supported) included:

| Target profile | BT-24 |
| :- | :- |
| ZUGFeRD / Factur-X EN 16931, also plain EN 16931 | `urn:cen.eu:en16931:2017` |
| XRechnung 3.0 | `urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0` |

**Related URS**: REQ-004-URS-F002

**Definition of Done**: tests with the Peppol BIS identifier, the Factur-X MINIMUM identifier, `urn:cen.eu:en16931:2017:compliant:factur-x.eu:1p0:basic` and `urn:cen.eu:en16931:2026` in BT-24 each get the refusal, naming BT-24.

#### REQ-004-PRS-F003: Writing choices

**Description**: Each business term SHALL be written to the element the EN 16931 syntax binding for CII (EN 16931-3-3) assigns to it, in the order the CII D16B XML Schema requires, with these choices where the binding leaves room:

- **Missing terms** (`None`, empty tuple) are left out, with any element that would hold nothing but them.
- **VAT totals**: BT-110 as `ram:TaxTotalAmount` with `currencyID` BT-5; BT-111 as a second `ram:TaxTotalAmount` with `currencyID` BT-6.
- **Numbers** in plain notation with the digits the model holds: `Decimal("10.50")` stays `10.50`; `Decimal("1E+2")` is written `100` (the exception of [REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)).
- `ram:ApplicableHeaderTradeDelivery` is written even when empty, as the XML Schema requires it.

**Related URS**: REQ-004-URS-F001

**Definition of Done**: a test writes numbers with trailing zeros and reads them back with the same digits, and writes `Decimal("1E+2")` as `100`; a test writes a model without optional terms and finds none of their elements; the rest is covered by REQ-004-PRS-F004 to REQ-004-PRS-F006.

#### REQ-004-PRS-F004: XML Schema

**Description**: A written invoice SHALL be valid against the CII D16B XML Schema and, for the target profile `urn:cen.eu:en16931:2017`, against Factur-X's XML Schema of the EN 16931 profile. A schema violation is a `HAFL-XSD` finding ([REQ-002-PRS-F010](req-002-conformance.md#req-002-prs-f010-haflingers-own-findings)).

**Related URS**: REQ-004-URS-F002

**Definition of Done**: every invoice written in the round trip of REQ-004-PRS-F006 is schema-valid; a deliberately broken document gets a `HAFL-XSD` finding (tests).

#### REQ-004-PRS-F005: Official rules

**Description**: A written invoice SHALL be validated with the rule set of its target profile ([REQ-002-PRS-F003](req-002-conformance.md#req-002-prs-f003-rule-sets)) and handed out only when it is valid as [REQ-002-PRS-F002](req-002-conformance.md#req-002-prs-f002-findings) defines.

**Related URS**: REQ-004-URS-F002

**Definition of Done**: in the round trip of REQ-004-PRS-F006, every `fatal` or `error` finding of a written KoSIT file is a rule that needs a business term the model doesn't hold yet; the test lists those rules with the missing terms, and a further test fails once a listed rule no longer fires on any file, so that the list shrinks as the model grows.

#### REQ-004-PRS-F006: Round trip over the KoSIT suite

**Description**: For every file of the KoSIT test suite, CII and UBL, the document written from its model (handed out, or carried by the refusal) SHALL read back to that model with `haflinger.read_invoice`, without findings, and with KoSIT's reading stylesheet.

**Related URS**: REQ-004-URS-F003, REQ-004-URS-NF001

**Definition of Done**: one test per file and reader.

#### REQ-004-PRS-F007: ZUGFeRD PDF

**Description**: With the extra `pdf` installed, `haflinger.pdf.embed(pdf: bytes, xml: bytes) -> bytes` SHALL return the given PDF as PDF/A-3 with the XML embedded under the file name its profile prescribes, with the relationship and the XMP metadata (profile, version) that ZUGFeRD and Factur-X require, and the pages unchanged. It SHALL raise `InvoiceWriteError`, and no other exception, when:

- the PDF isn't readable, or its XMP metadata declares no PDF/A conformance (the reason says that the input must be PDF/A);
- the XML isn't a CII invoice whose BT-24 is a target profile of REQ-004-PRS-F002;
- the XML fails REQ-004-PRS-F004 or REQ-004-PRS-F005, with the findings.

**Related URS**: REQ-004-URS-F002, REQ-004-URS-F004

**Definition of Done**: for a CII invoice of each target profile and a PDF/A test file, `haflinger.pdf.extract_xml` on the result returns the XML byte for byte, the result reads with `read_invoice` to the invoice's model, the XMP names the invoice's profile, the page content equals the input's, and veraPDF, the reference PDF/A validator, finds the result conformant to PDF/A-3 (tests; veraPDF runs where it is installed, as an oracle); one test per refusal.

## PRS — Non-Functional

#### REQ-004-PRS-NF001: Speed

**Description**: Writing, without the checks of REQ-004-PRS-F004 and REQ-004-PRS-F005, SHALL take at most 10 ms for a file of the KoSIT test suite and 5 s for the 25.7 MB Peppol invoice of [REQ-002-PRS-NF002](req-002-conformance.md#req-002-prs-nf002-speed), on the reference machine. The rules' time is bounded by REQ-002-PRS-NF002.

**Related URS**: REQ-004-URS-NF002

**Definition of Done**: a benchmark run against the KoSIT suite and the ZUGFeRD corpus, its figures recorded with the release, together with the machine they ran on (processor, Python version).

## Acceptance Criteria

- `write_cii` writes only the two target profiles, hands out only invoices that pass the XML Schema and the rules, and refuses the rest with the reason, and after writing with findings and the document.
- Every KoSIT file round-trips through the writer and reads back unchanged with both readers.
- Every rule a written KoSIT file still fails is listed with the business term the model lacks.
- ZUGFeRD PDFs are made only from PDF/A input and valid XML, carry the XML byte for byte with the metadata of their profile, and are PDF/A-3 by veraPDF's verdict.

## Assumptions

- Until the model holds the terms of [ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)'s first step, `write_cii` refuses XRechnung and most ZUGFeRD invoices, with the findings that say which terms are missing.
- Factur-X's XML Schemas are vendored under [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md) ([ITEM-002](../backlog/item-002-official-test-material.md)).
- `factur-x` produces PDF/A-3 when its input is PDF/A, as its changelog states (tested there with veraPDF); it doesn't convert other PDFs to PDF/A.

## Open Questions

- More target profiles (EXTENDED, BASIC) when a customer needs them?
