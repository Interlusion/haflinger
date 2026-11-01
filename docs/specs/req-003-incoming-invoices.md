# REQ-003: Haflinger Incoming Invoices — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Draft |
| **Version** | 0.4 |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Intended Use

Receiving an invoice: reading what a supplier sent, as CII, UBL or a ZUGFeRD PDF, into the model, so that a person can see it and it can be booked. Reading takes in everything an invoice holds of the model's terms, even when the invoice is incomplete, and reports what it couldn't take in; validation (REQ-002) then says what is wrong with the invoice. Reading refuses only what it can't read at all.

Out of scope: receiving by e-mail or Peppol (the caller, providers); rendering an invoice for people; archiving (the caller keeps the original bytes); checks of the PDF container itself ([ITEM-004](../backlog/item-004-pdf-checks.md)); the Purchase Invoice in ERPNext (the app, [ITEM-003](../backlog/item-003-erpnext-app.md)).

Read [REQ-001](req-001-core.md) first: it holds the personas, stories and terms, and the rules every spec follows.

Key constraints: incoming invoices are outside input ([REQ-001-URS-NF003](req-001-core.md#req-001-urs-nf003-safe-with-outside-input)); Haflinger's own mapping reads, KoSIT's reading stylesheet checks it ([ADR-005](../arc42/adr/ADR-005-own-mapping-kosit-as-check.md)).

## User Stories

The personas are [REQ-001's](req-001-core.md#personas).

- REQ-003-P1-1. As the operator, I need invoices in CII, UBL and as ZUGFeRD PDFs read into the same form, so that the format a supplier chose makes no difference to me.
- REQ-003-P1-2. As the operator, I need an incomplete invoice still read, with what is wrong reported, so that I can see it and ask the supplier for a correct one.
- REQ-003-P1-3. As the operator, I need an input that isn't a readable invoice refused with a reason that says what it is, so that I know whether to ask for another file.
- REQ-003-P2-1. As the maintainer, I need the reading checked by an independent reader over the official files, so that a mistake can't hide in a round trip through Haflinger alone.
- REQ-003-P3-1. As the integrator, I need one call that takes the bytes received and returns the model with what reading noticed, so that I don't have to handle each format myself.

## Requirement Rules

- SHALL = mandatory · SHOULD = recommended · MAY = optional
- Every SHALL verifiable (test / benchmark / inspection / analysis)
- One requirement = one idea

## URS — Functional

#### REQ-003-URS-F001: Read CII and UBL

**Description**: The library SHALL read an invoice or credit note in CII or UBL into the model.

**Related User Stories**: REQ-003-P1-1, REQ-003-P3-1

#### REQ-003-URS-F002: Read ZUGFeRD PDFs

**Description**: The library SHALL read the invoice embedded in a ZUGFeRD PDF, and give the embedded XML exactly as embedded.

**Related User Stories**: REQ-003-P1-1 | **Rationale**: Most German invoices between businesses arrive as ZUGFeRD PDFs; the embedded XML is the invoice to archive.

#### REQ-003-URS-F003: The same invoice in both syntaxes

**Description**: The same invoice in CII and in UBL SHALL give the same model.

**Related User Stories**: REQ-003-P1-1

#### REQ-003-URS-F004: Read what is there

**Description**: An invoice that lacks terms EN 16931 requires SHALL still be read, with what it holds.

**Related User Stories**: REQ-003-P1-2 | **Rationale**: ZUGFeRD MINIMUM and BASIC WL invoices hold no lines by design, yet they arrive and a person must see them. For an invoice whose profile requires the missing terms, the official rules report what is missing (REQ-002).

#### REQ-003-URS-F005: Refuse what can't be read

**Description**: An input that can't be read as an invoice SHALL be refused with a reason that says what was found.

**Related User Stories**: REQ-003-P1-3

#### REQ-003-URS-F006: Nothing lost without a word

**Description**: A value of a business term the model holds that reading can't take in SHALL be reported, naming its business term.

**Related User Stories**: REQ-003-P1-2 | **Rationale**: [REQ-001-URS-NF002](req-001-core.md#req-001-urs-nf002-refuse-or-report-never-guess); the operator's underlying fear. Terms the model doesn't hold yet aren't reported: naming them would need their binding, which is exactly what adding a term to the model brings. They stay in the original invoice, and showing the original is the caller's ([ITEM-005](../backlog/item-005-rendering.md)); which terms the model holds is fixed by [REQ-001-PRS-F001](req-001-core.md#req-001-prs-f001-business-terms).

## URS — Non-Functional

#### REQ-003-URS-NF001: Checked by an independent reader

**Description**: The reading SHALL be checked against an independent implementation over the official test files.

**Related User Stories**: REQ-003-P2-1 | **Rationale**: [ADR-005](../arc42/adr/ADR-005-own-mapping-kosit-as-check.md). The KoSIT test suite's CII and UBL files were made with one converter and aligned by hand, so their agreement alone proves little.

#### REQ-003-URS-NF002: Large invoices

**Description**: Invoices of tens of megabytes SHALL be read in seconds.

**Related User Stories**: REQ-003-P1-1 | **Rationale**: Utilities and telecoms send invoices with tens of thousands of lines. The limit beyond which input is refused is REQ-001's ([REQ-001-PRS-NF003](req-001-core.md#req-001-prs-nf003-size-limit)).

#### REQ-003-URS-NF003: Hostile PDFs

**Description**: A malformed or hostile PDF SHALL lead to a refusal, never to another failure.

**Related User Stories**: REQ-003-P1-3 | **Rationale**: [REQ-001-URS-NF003](req-001-core.md#req-001-urs-nf003-safe-with-outside-input).

## PRS — Functional

#### REQ-003-PRS-F001: One entry point

**Description**: `haflinger.read_invoice(data: bytes, *, max_size: int = …) -> ReadResult` SHALL detect the syntax from the root element's namespace and name (CII `CrossIndustryInvoice`, UBL `Invoice`, UBL `CreditNote`), read the invoice and record the syntax (REQ-001-PRS-F002). `ReadResult` SHALL carry `invoice`, the model, and `findings`, the findings reading reports (REQ-003-PRS-F002), in document order.

**Related URS**: REQ-003-URS-F001, REQ-003-URS-F006

**Definition of Done**:

- Every file of the KoSIT test suite is read, with the syntax its name says (`_uncefact` CII, `_ubl` UBL), and without findings.
- A UBL file with a prefixed root (`ubl:Invoice`) and one with a default namespace (`Invoice`) are both read.
- A UBL credit note from the official test files is read, with the type code it holds (BT-3).
- KoSIT case 01.01a reads to one exact expected model in both syntaxes (REQ-001-PRS-F001).

#### REQ-003-PRS-F002: Reading choices

**Description**: Each business term SHALL be read from the element the EN 16931 syntax bindings assign to it (EN 16931-3-3 for CII, EN 16931-3-2 for UBL), with these choices where the bindings leave room:

- **Notes (BG-1)**: in UBL, a `cbc:Note` starting with `#XXX#` carries the subject code `XXX` (the convention of XRechnung and Peppol), the rest is the text.
- **VAT totals (BT-110, BT-111)**: chosen by currency. In CII, the `TaxTotalAmount` in the invoice currency (BT-5) is BT-110 and the one in the VAT accounting currency (BT-6) is BT-111; one without `currencyID` is BT-110. In UBL, the `cac:TaxTotal` whose `cbc:TaxAmount` is in the invoice currency gives BT-110 and the VAT breakdown, the one in the VAT accounting currency gives BT-111; when no `cac:TaxTotal` gives BT-110, the first one holding a `cac:TaxSubtotal` gives the VAT breakdown, and the subtotals of every other `cac:TaxTotal` are left out with a `HAFL-DROPPED` finding. Where BT-6 equals BT-5, the first total in that currency is BT-110 and the second BT-111. A VAT total in another currency is left out with a `HAFL-DROPPED` finding.
- **Taxes other than VAT**: in CII, only an `ram:ApplicableTradeTax` whose `ram:TypeCode` is `VAT`, or that has no type code, gives the VAT breakdown (BG-23) and a line's VAT information (BG-30). Another tax, which Factur-X EXTENDED allows, is left out with a `HAFL-DROPPED` finding.
- **Repeated values**: where the invoice holds a term more often than the model does (two due dates, BT-9, in an EXTENDED invoice; two VAT totals in one currency), the first that holds a value is read and each further one that holds a value is left out with a `HAFL-DROPPED` finding. The same holds for the groups the model holds once and for the elements within a party or a line that hold several of its terms (the postal address, the legal organisation or entity, the line's VAT information BG-30, its price BG-29, its item BG-31): the first element that holds any value is read, all of its terms from it, and each further one holding a value is left out with a `HAFL-DROPPED` finding, so that no group mixes the terms of two. The VAT totals (BT-110, BT-111) are read also where the document totals (BG-22) are missing, and the unit of measure (BT-130) also where its quantity element is empty.
- **Whitespace**: XML whitespace (space, tab, carriage return, line feed) around a value is removed, and an element empty after that counts as missing (the exception of [REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)); other whitespace, such as a no-break space, is kept. An invoice line (BG-25) or a VAT breakdown (BG-23) whose element holds no value counts as missing too.
- **Malformed values**: a number not written as `xs:decimal` (REQ-001's term Value as written), a CII date not written as `YYYYMMDD` with `format="102"`, or a UBL date not written as `YYYY-MM-DD`, and a value whose element holds elements instead of only text, whichever term it gives, is read as missing, with a `HAFL-VALUE` finding. A number keeps its value and decimal places, not its notation (the exception of [REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)).

The findings are those of [REQ-002-PRS-F010](req-002-conformance.md#req-002-prs-f010-haflingers-own-findings).

**Related URS**: REQ-003-URS-F001, REQ-003-URS-F006

**Definition of Done**: one test per choice: a UBL note with `#AAI#`; a KoSIT case with BT-6 for both VAT totals; a CII `TaxTotalAmount` without `currencyID`; a VAT total in a third currency; an invoice with two due dates (first read, one `HAFL-DROPPED`; constructed, and FeRD's EXTENDED sample X07 where the maintainer's copy of the package is present); an element holding only whitespace, and a no-break space kept; `1E+2` as BT-112 and `2026-10-30` as a CII date (missing, one `HAFL-VALUE` each), and `+0336.90` as BT-112 (`336.90`); a constructed EXTENDED line with another tax before its VAT; BT-110, BT-31 and a UBL note whose element holds an element (missing, one `HAFL-VALUE` each); a multi-line UBL note with `#AAI#`; for each group read from one element (postal address, legal organisation or entity, BG-29, BG-30, BG-31) and for the VAT identifier, in both syntaxes, a second one dropped with a finding naming its term; a UBL `cac:TaxTotal` in the VAT accounting currency before the one in the invoice currency; an empty invoice line.

#### REQ-003-PRS-F003: Missing terms

**Description**: A term or group that EN 16931 requires but the invoice lacks SHALL be missing in the model, as REQ-001-PRS-F001 says, without a refusal or a finding from reading.

**Related URS**: REQ-003-URS-F004

**Definition of Done**: FeRD's MINIMUM and BASIC WL samples read with no lines and with every term they hold (from the maintainer's copy of FeRD's package, skipped where it isn't present, [ITEM-002](../backlog/item-002-official-test-material.md)), and their validation with the rules of their profile gives no `fatal` or `error` finding; a constructed EN 16931 invoice without lines reads, and its validation reports `BR-16` (tests).

#### REQ-003-PRS-F004: CII and UBL agree

**Description**: For every business case of the KoSIT test suite, the CII file and the UBL file SHALL read to equal models, except that an optional sum (BT-107, BT-108, BT-113, BT-114) one file gives as zero and the other leaves out counts as agreeing. The model keeps what each file says.

**Related URS**: REQ-003-URS-F003

**Definition of Done**: one test per business case compares the two models; differences in the official files themselves are recorded as [REQ-002-PRS-F008](req-002-conformance.md#req-002-prs-f008-differences-in-the-official-files) says.

#### REQ-003-PRS-F005: Two readers agree

**Description**: For every file of the KoSIT test suite, every file of the ZUGFeRD corpus selection kept with the tests, and the UBL credit note, KoSIT's reading stylesheet SHALL give the same model as Haflinger's reading, for every term both cover. Files that `read_invoice` refuses, and CEN's unit-test fragments, are not part of this.

**Related URS**: REQ-003-URS-NF001

**Definition of Done**: one test per file; a difference that is a limit of KoSIT's stylesheet (for example repeated EXTENDED values joined into one) is recorded with its reason.

#### REQ-003-PRS-F006: Refusals

**Description**: `read_invoice` SHALL raise `haflinger.InvoiceReadError`, and no other exception, with a reason that names the problem, when the input:

- isn't `bytes` (the reason names its type);
- is not well-formed XML, which includes a byte order mark that contradicts the encoding declaration, or has the PDF header `%PDF-` within its first 1,024 bytes, before any `<`, but isn't a readable PDF;
- contains a document type or entity declaration (REQ-001-PRS-NF001);
- has a root element that is neither a CII invoice nor a UBL invoice or credit note; for a ZUGFeRD 1.0 invoice (`CrossIndustryDocument`) and an Italian FatturaPA invoice the reason names the format, also when it is embedded in a PDF;
- follows an edition other than 2017 ([REQ-002-PRS-F009](req-002-conformance.md#req-002-prs-f009-editions-supported));
- is a PDF that `haflinger.pdf.extract_xml` refuses (REQ-003-PRS-F007), or a PDF while the `pdf` extra isn't installed (the reason says so);
- is larger than `max_size` (REQ-001-PRS-NF003).

**Related URS**: REQ-003-URS-F005

**Definition of Done**: one test per case.

#### REQ-003-PRS-F007: ZUGFeRD PDFs

**Description**: With the extra `pdf` installed, `read_invoice` SHALL read a PDF through its embedded invoice, and `haflinger.pdf.extract_xml(data: bytes, *, max_size: int = …) -> bytes` SHALL return the embedded invoice byte for byte, without parsing it. The embedded invoice is the embedded file named `factur-x.xml`, `zugferd-invoice.xml`, `xrechnung.xml` or, for ZUGFeRD 1.0, `ZUGFeRD-invoice.xml`; it is read whatever its syntax. `extract_xml` SHALL raise `InvoiceReadError` when the input isn't a readable PDF, holds none of these files, holds more than one of them (two files of the same name included), or the file exceeds `max_size`. It SHALL also raise it when looking for the invoice would take more than these limits allow, which no ZUGFeRD PDF seen comes near: a tree of embedded files of more than 100 entries; a stream on the way to the invoice (an object or cross-reference stream) that decodes to more than 2 MB; more than 3 s spent looking for the invoice. A ZUGFeRD PDF takes milliseconds; no limit on sizes or counts bounds the time every malformed PDF keeps the parser busy. Importing `haflinger.pdf` without the extra SHALL raise `ImportError` naming the extra.

**Related URS**: REQ-003-URS-F002

**Definition of Done**: for the vendored ZUGFeRD PDFs (EN 16931, EXTENDED) and, where the maintainer's copy of FeRD's package is present, its PDFs of every profile, the model equals that of the embedded XML read on its own, and the extracted bytes equal the embedded file; a PDF with UBL embedded as `xrechnung.xml` reads; one test per refusal (tests).

#### REQ-003-PRS-F008: Findings on incoming invoices

**Description**: `read_invoice` SHALL NOT validate: its findings are only those of REQ-003-PRS-F002, and validation is a separate call (`validate`, REQ-002) on the same bytes. No finding, from reading or validation, SHALL stop an invoice from being read.

**Related URS**: REQ-003-URS-F004, REQ-003-URS-F006

**Definition of Done**: a KoSIT file with BT-112 changed by one cent reads with that value and no findings, and `validate` reports `BR-CO-15` for it (test).

## PRS — Non-Functional

#### REQ-003-PRS-NF001: Embedded files within the limit

**Description**: The XML embedded in a PDF SHALL count against `max_size` (REQ-001-PRS-NF003) as it is decompressed, so that a small PDF can't unpack into an oversized file.

**Related URS**: REQ-003-URS-NF003

**Definition of Done**: a PDF of under 1 MB whose embedded file inflates to more than `max_size` is refused without being inflated completely (test).

#### REQ-003-PRS-NF002: Speed

**Description**: Reading the 61.1 MB Peppol invoice of the ZUGFeRD corpus (`PEPPOL/Valid/Qvalia/Large_Invoice_sample2.xml`, at corpus commit `82e886f`) SHALL take at most 10 s, and a file of the KoSIT test suite at most 20 ms, on the reference machine.

**Related URS**: REQ-003-URS-NF002

**Definition of Done**: a benchmark run against the KoSIT suite and the ZUGFeRD corpus, its figures and the peak memory of reading the 61.1 MB invoice recorded with the release, together with the machine they ran on (processor, Python version).

#### REQ-003-PRS-NF003: Malformed PDFs

**Description**: Every malformed PDF SHALL lead to `InvoiceReadError`, from `read_invoice` and from `extract_xml`, never to another exception.

**Related URS**: REQ-003-URS-NF003

**Definition of Done**: tests with the ZUGFeRD corpus's broken PDFs kept with the tests, a truncated PDF and a PDF whose embedded file is not XML; a PDF with deeply nested objects, and one whose tree of embedded files has thousands of entries, and one whose tree leads through object streams each just under the limits of REQ-003-PRS-F007, get `InvoiceReadError` within 5 s and 200 MB; a fuzz test over mutated copies of the test PDFs gets only `InvoiceReadError` or a result, each within 5 s. A loop or crash found in a dependency is recorded in the test and reported upstream.

## Acceptance Criteria

- Every KoSIT test file reads in both syntaxes to equal models, and KoSIT's stylesheet agrees for every term both cover.
- ZUGFeRD PDFs read through their embedded XML, which is handed out byte for byte.
- Incomplete invoices read with what they hold; the rules report the rest.
- Every value of a term the model holds that reading leaves out or can't read is reported with a `HAFL-DROPPED` or `HAFL-VALUE` finding.
- Unreadable input is refused with `InvoiceReadError` naming the problem, never another exception.
- Large invoices read within the limits; a PDF can't unpack beyond the size limit.

## Assumptions

- The Mustang project's PDFs of the ZUGFeRD corpus (Apache-2.0), valid and broken, are vendored with the tests ([ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md)); FeRD's and FNFE-MPE's samples aren't, as no terms name them ([ITEM-002](../backlog/item-002-official-test-material.md)).
- The official test files include a UBL credit note (Peppol BIS or CEN examples).
- The library bounds the time of looking for the invoice in a PDF, not the time of reading the XML, which grows with its size (REQ-003-PRS-NF002). The bound on PDFs works within the thread: pypdf is pure Python, and a profile function that Python calls on every function call raises once the time is up. A caller that reads outside input still runs it where a time limit applies, such as a background job with a timeout ([ITEM-003](../backlog/item-003-erpnext-app.md)); validation has no time bound ([REQ-002](req-002-conformance.md#assumptions)).

## Open Questions

None at present.
