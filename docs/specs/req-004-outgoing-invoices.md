# REQ-004: Haflinger Outgoing Invoices — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Draft |
| **Version** | 0.8 |
| **Date** | 2026-11-03 |
| **Author** | loxy (drafted with Claude) |

## Intended Use

Sending an invoice: turning the model into the XML and PDF that leave the company. Outgoing invoices are CII only, in two profiles ([ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md)): XRechnung for public authorities, ZUGFeRD EN 16931 for businesses. Haflinger hands out an invoice only when it passes the XML Schema and the official rules of its profile.

Writing is checked with what the read side has: Haflinger's reader, KoSIT's reading stylesheet, the XML Schema of CII and the official rules; no hand-written expected XML.

Out of scope: writing UBL; sending by e-mail, portal or Peppol (the caller, providers); rendering the readable PDF, and making it PDF/A (the caller; for ERPNext, [ITEM-003](../backlog/item-003-erpnext-app.md)); completeness under German VAT law beyond the official rules, such as the tax number or VAT ID and the delivery date of §14(4) UStG (the caller; for ERPNext, [ITEM-003](../backlog/item-003-erpnext-app.md)); the Sales Invoice in ERPNext (the app, [ITEM-003](../backlog/item-003-erpnext-app.md)).

Read [REQ-001](req-001-core.md) first: it holds the personas, stories and terms, and the rules every spec follows.

Key constraints: an invoice is handed out only when it passes the rules of its profile, which refuse it, naming what is missing, while the model lacks terms the profile requires ([ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)); ZUGFeRD PDF handling is in the library, in the optional extra `pdf` ([ADR-001](../arc42/adr/ADR-001-library-and-app.md)).

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

**Description**: `haflinger.write_cii(invoice: Invoice, *, timeout: float = …) -> bytes` SHALL return a CII D16B document, UTF-8 with an XML declaration, when it passes REQ-004-PRS-F004 and REQ-004-PRS-F005. Otherwise it SHALL raise `haflinger.InvoiceWriteError`, and no other exception, with a reason that names the business term where there is one ([REQ-001-PRS-F005](req-001-core.md#req-001-prs-f005-refusals-and-findings-name-their-subject)). `InvoiceWriteError` SHALL carry `findings` and `document`:

- **Before writing**, with no findings and no document, when the argument isn't an `Invoice`; the `timeout` isn't valid ([REQ-002-PRS-NF004](req-002-conformance.md#req-002-prs-nf004-time-limit)); the model's BT-24 is no supported target profile (REQ-004-PRS-F002); a value has the wrong type (an amount, quantity, price or rate that isn't a finite `Decimal`, a date that isn't a `date`, a text that isn't a `str`, a group that isn't of its class or a tuple of it); a number has more than 1,000 digits in plain notation; a text is empty, has surrounding whitespace, or holds a character XML 1.0 doesn't allow; a note (BG-1) holds neither subject code nor text, a contact (BG-6, BG-9) no term, an identifier (BT-29, BT-34, BT-46, BT-49) no value, an electronic address (BT-34, BT-49) no scheme, payment instructions (BG-16) no means code (BT-81), a credit transfer (BG-17) no account (BT-84), a card (BG-18) no account number (BT-87), a direct debit (BG-19) no term; the buyer holds a tax registration identifier, which only the seller has (BT-32), or more than one identifier (BT-46); or the model holds a term without one it needs to be written (BT-111 without BT-6, BT-130 without BT-129).
- **After writing**, with the findings and the written document, when it fails REQ-004-PRS-F004 or REQ-004-PRS-F005, or can't be checked by them (for example, larger than the size limit validation accepts, or when the rules don't end within `timeout` or their worker dies, [REQ-002-PRS-NF004](req-002-conformance.md#req-002-prs-nf004-time-limit), [REQ-002-PRS-NF005](req-002-conformance.md#req-002-prs-nf005-rules-in-a-worker-process)).

**Related URS**: REQ-004-URS-F001, REQ-004-URS-F002

**Definition of Done**: a test writes a valid invoice and gets UTF-8 bytes with an XML declaration; a test writes an invoice whose BT-112 is off by one cent and gets `InvoiceWriteError` with `BR-CO-15` among its findings and the document; a number of exactly 1,000 digits is written; one test per refusal before writing, each naming its business term (a float in BT-112, a string in BT-2, `" Example GmbH"` in BT-27, a control character in BT-153, BT-111 without BT-6, an empty contact, an identifier without value, an electronic address without scheme, payment instructions without means code, a credit transfer without account, an empty direct debit, a buyer with BT-32 or two identifiers).

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
- **Parties**: an identifier (BT-29, BT-46) with a scheme as `ram:GlobalID` with that `schemeID`, one without as `ram:ID`; those without come first, as the XML Schema orders the two elements and as reading orders the model (REQ-003-PRS-F002); a model in another order reads back in that one. The seller's tax registration identifier (BT-32) as `ram:SpecifiedTaxRegistration/ram:ID` with `schemeID` `FC`, after the VAT identifier's; the contact point (BT-41, BT-56) as `ram:PersonName`.
- **Payment instructions (BG-16)**: one `ram:SpecifiedTradeSettlementPaymentMeans` for each credit transfer (BG-17), or one where there is none, each with the means code (BT-81) and text (BT-82); the card (BG-18) and the debited account (BT-91, as `ram:PayerPartyDebtorFinancialAccount/ram:IBANID`) in the first. A credit transfer's account (BT-84) as `ram:IBANID` where it has an IBAN's form (two capital letters, two digits, then up to 30 letters and digits), else as `ram:ProprietaryID`; its provider (BT-86) as its payment means' `ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID`. The remittance information (BT-83) as `ram:PaymentReference`, the creditor identifier (BT-90) as `ram:CreditorReferenceID`. The payment terms (BT-20), the due date (BT-9) and the mandate reference (BT-89) in one `ram:SpecifiedTradePaymentTerms`. Payment terms that hold a line starting with `#`, as XRechnung's discount terms do, and end with a `#…#` run end with a line feed after it, which XRechnung's `BR-DE-18` requires and reading removes again as whitespace around the value.
- **VAT totals**: BT-110 as `ram:TaxTotalAmount` with `currencyID` BT-5; BT-111 as a second `ram:TaxTotalAmount` with `currencyID` BT-6.
- **Numbers** in plain notation with the digits the model holds: `Decimal("10.50")` stays `10.50`; `Decimal("1E+2")` is written `100` (the exception of [REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)).
- The elements the XML Schema requires and that need no content (`ram:ApplicableHeaderTradeAgreement`, `ram:ApplicableHeaderTradeDelivery` and `ram:ApplicableHeaderTradeSettlement`; in a line, `ram:AssociatedDocumentLineDocument` and `ram:SpecifiedLineTradeSettlement`) are written even when empty.

**Related URS**: REQ-004-URS-F001

**Definition of Done**: a test writes numbers with trailing zeros and reads them back with the same digits, and writes `Decimal("1E+2")` as `100`; a test writes a model without optional terms and finds none of their elements; a test writes identifiers with and without scheme, BT-32, address lines 2 and 3, the subdivision and a contact, finds them where this requirement puts them, and reads them back; so does a test with payment terms and instructions holding two credit transfers, one IBAN and one other account, a card and a direct debit, and ones with XRechnung's discount terms, last and before a closing note; the rest is covered by REQ-004-PRS-F004 to REQ-004-PRS-F006.

#### REQ-004-PRS-F004: XML Schema

**Description**: A written invoice SHALL be valid against the CII D16B XML Schema and, for the target profile `urn:cen.eu:en16931:2017`, against Factur-X's XML Schema of the EN 16931 profile. A schema violation is a `HAFL-XSD` finding ([REQ-002-PRS-F010](req-002-conformance.md#req-002-prs-f010-haflingers-own-findings)).

**Related URS**: REQ-004-URS-F002

**Definition of Done**: every invoice written in the round trip of REQ-004-PRS-F006 is schema-valid; a deliberately broken document gets a `HAFL-XSD` finding (tests).

#### REQ-004-PRS-F005: Official rules

**Description**: A written invoice SHALL be validated with the rule set of its target profile ([REQ-002-PRS-F003](req-002-conformance.md#req-002-prs-f003-rule-sets)) and, for the target profile `urn:cen.eu:en16931:2017`, which a ZUGFeRD PDF labels Factur-X EN 16931 (REQ-004-PRS-F007), also with FeRD's Factur-X rules of the EN 16931 profile. It SHALL be handed out only when it is valid as [REQ-002-PRS-F002](req-002-conformance.md#req-002-prs-f002-findings) defines.

**Related URS**: REQ-004-URS-F002 | **Rationale**: A recipient may check a ZUGFeRD PDF with FeRD's rules rather than CEN's; FeRD's rules of the profile also reject what the profile doesn't use, such as a line's VAT exemption reason.

**Definition of Done**: in the round trip of REQ-004-PRS-F006, every `fatal` or `error` finding of a written KoSIT file is a rule that needs a business term the model doesn't hold yet; the test lists those rules with the missing terms, and a further test fails once a listed rule no longer fires on any file, so that the list shrinks as the model grows; every invoice handed out passes FeRD's EN 16931 rules without `fatal` or `error`.

#### REQ-004-PRS-F006: Round trip over the KoSIT suite

**Description**: For every file of the KoSIT test suite, CII and UBL, the document written from its model (handed out, or carried by the refusal) SHALL read back to that model with `haflinger.read_invoice`, without findings, and with KoSIT's reading stylesheet.

**Related URS**: REQ-004-URS-F003, REQ-004-URS-NF001

**Definition of Done**: one test per file and reader.

#### REQ-004-PRS-F007: ZUGFeRD PDF

**Description**: With the extra `pdf` installed, `haflinger.pdf.embed(pdf: bytes, xml: bytes, *, timeout: float = …) -> bytes` SHALL return the given PDF as PDF/A-3 with the XML embedded as `factur-x.xml`, with the relationship `/Alternative` and the XMP metadata (profile, version) that ZUGFeRD and Factur-X require, and the pages unchanged. The PDF's XMP metadata and document information are replaced by those of the invoice (title and subject from BT-1, BT-2 and BT-27, author BT-27), and a reader opening it shows its attachments (`/PageMode /UseAttachments`). It SHALL raise `InvoiceWriteError`, and no other exception, when:

- either argument isn't `bytes`, or the `timeout` isn't valid; the PDF isn't readable, or its XMP metadata declares no conformance to PDF/A-1, -2 or -3 (the reason says that the input must be PDF/A); or the PDF holds what embedding would drop: a name tree (`/Names`: embedded files, named destinations and the others) or associated files of the document (`/AF`);
- the XML isn't a CII invoice whose BT-24 is exactly `urn:cen.eu:en16931:2017`, with no whitespace around it, the ZUGFeRD / Factur-X EN 16931 profile; XRechnung, the other target profile of REQ-004-PRS-F002, is sent as XML;
- the XML fails REQ-004-PRS-F004 or REQ-004-PRS-F005, with the findings, or can't be checked by them because the rules don't end within `timeout` or their worker dies ([REQ-002-PRS-NF004](req-002-conformance.md#req-002-prs-nf004-time-limit), [REQ-002-PRS-NF005](req-002-conformance.md#req-002-prs-nf005-rules-in-a-worker-process)).

**Related URS**: REQ-004-URS-F002, REQ-004-URS-F004 | **Rationale**: ZUGFeRD PDFs go to businesses, XRechnung to public authorities as XML (Intended Use). ZUGFeRD 2.5.2 allows only `/Alternative` for the EN 16931 profile in Germany, and Factur-X allows it in France: the PDF shows the same invoice as the XML, which is up to the caller, who renders the PDF. ZUGFeRD's XRECHNUNG profile in a PDF (`xrechnung.xml`) is an open question; `factur-x` doesn't write it.

**Definition of Done**: for a CII invoice of the EN 16931 profile and a PDF/A test file, and for the same file after incremental updates, the result is one PDF that a strict reader reads, `haflinger.pdf.extract_xml` on the result returns the XML byte for byte, the result reads with `read_invoice` to the invoice's model, the XMP names the invoice's profile, the embedded file's relationship is `/Alternative`, the page content equals the input's, and veraPDF, the reference PDF/A validator, finds the result conformant to PDF/A-3 (tests; veraPDF runs where it is installed, as an oracle); a PDF/A whose page content holds the text `%PDF-`, one whose XMP uses another prefix for the PDF/A namespace, one with a catalogue `/Dests`, and an invoice with an attachment (BG-24) of more than 10 MB are embedded; one test per refusal, among them a description that mentions `pdfaid:part` without declaring it, a name tree other than embedded files, `/AF`, a BT-24 with whitespace around it, and an invoice that fails only FeRD's rules.

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

- Until the model holds the terms of [ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)'s first step, `write_cii` refuses every XRechnung invoice and the EN 16931 invoices that need terms the model lacks (as EN 16931, 60 of the 86 KoSIT models are handed out), with the findings that say which terms are missing.
- Factur-X's XML Schemas are vendored under [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md) ([ITEM-002](../backlog/item-002-official-test-material.md)).
- `factur-x` produces PDF/A-3 when its input is PDF/A, as its changelog states (tested there with veraPDF); it doesn't convert other PDFs to PDF/A.

## Open Questions

- More target profiles (EXTENDED, BASIC) when a customer needs them?
- XRechnung as a ZUGFeRD PDF (profile XRECHNUNG, `xrechnung.xml`), which `factur-x` doesn't write: needed by any recipient?
