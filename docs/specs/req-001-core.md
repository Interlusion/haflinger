# REQ-001: Haflinger Core — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Draft |
| **Version** | 0.13 |
| **Date** | 2026-11-06 |
| **Author** | loxy (drafted with Claude) |

## Intended Use

Haflinger is a Python library for e-invoicing, `haflinger`. It holds one model of the EN 16931 business terms, reads invoices received in CII, UBL and ZUGFeRD PDFs into it, validates them with the official rules, and writes invoices as CII and ZUGFeRD PDFs. Any Python software can build on it; the first is an ERPNext app, later and in its own repository, that maps ERPNext's purchase and sales invoices to and from the model.

This base spec holds what every other spec shares: the personas, stories and terms, the model, and the rules for values, outside input and its size, refusals and findings. Conformance (REQ-002), incoming invoices (REQ-003) and outgoing invoices (REQ-004) build on it; the [specs index](README.md) says what goes where.

Out of scope: Peppol transport; the ERPNext app and its requirements (its own repository, [ADR-001](../arc42/adr/ADR-001-library-and-app.md)).

Key constraints: few runtime dependencies, installable next to the versions its host pins ([ADR-002](../arc42/adr/ADR-002-toolchain.md)); official artefacts are used unchanged and no business rule is reimplemented ([ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md)); Apache-2.0 ([ADR-009](../arc42/adr/ADR-009-licences-and-name.md)).

## Personas

### REQ-001-P1. The operator

- **Role**: Runs a company's books in software built on Haflinger, ERPNext first; sends invoices to customers and receives invoices from suppliers.
- **Expectations**: Invoices in whatever format the other side uses, CII or UBL, ZUGFeRD or XRechnung, handled the same way.
- **Pain points**: An e-invoicing app that rejects UBL or an unfamiliar profile and leaves the invoice to be typed by hand.
- **Underlying fear**: A value dropped or misread without a word, so that a wrong amount reaches the books, or an invoice sent that the customer's system rejects.

### REQ-001-P2. The maintainer

- **Role**: Keeps Haflinger current with new releases of XRechnung, EN 16931 and ZUGFeRD. Usually an agent, reviewed by a person.
- **Expectations**: Official test files and rules as the reference, so that a new release shows exactly what changed.
- **Pain points**: Behaviour that can only be checked inside a running ERP system.
- **Underlying fear**: A new release that breaks something no test notices.

### REQ-001-P3. The integrator

- **Role**: Builds software on the library: the ERPNext app, another ERP integration, a service or a script.
- **Expectations**: One typed model, independent of the syntax; refusals and findings that say what is wrong.
- **Pain points**: Exceptions that differ by syntax or entry point, and values whose type depends on the input.
- **Underlying fear**: Building on a value the library guessed.

## User Stories

- REQ-001-P1-1. As the operator, I need every invoice in the same form, whatever syntax it came in or goes out in, so that the format a supplier or customer chose makes no difference to me.
- REQ-001-P1-2. As the operator, I need anything Haflinger can't handle refused or reported with a reason, so that nothing wrong reaches the books or a customer unnoticed.
- REQ-001-P2-1. As the maintainer, I need behaviour checked against the official test files and rules, so that I can adopt a new release of them and see what changed.
- REQ-001-P3-1. As the integrator, I need each value named by its EN 16931 business term, so that I can map it to my own system without reading CII or UBL.

## Requirement Rules

- SHALL = mandatory · SHOULD = recommended · MAY = optional
- Every SHALL verifiable (test / benchmark / inspection / analysis)
- One requirement = one idea
- The requirements of this spec apply to every spec listed in the [index](README.md); another spec may tighten them, never loosen them. An exception is made only here, by naming it and the spec it applies to.

## Terms

General vocabulary (CIUS, Leitweg-ID, Peppol …): the [E-Invoicing 101 glossary](../guides/e-invoicing-101.md#glossary).

- **Business term**: a value defined by EN 16931-1, with its ID (`BT-n`); a **business group** (`BG-n`) is a set of them. A field ERPNext has but EN 16931 doesn't define is not one.
- **CII**: the UN/CEFACT Cross Industry Invoice syntax, version D16B, root `rsm:CrossIndustryInvoice` in namespace `urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100`. ZUGFeRD, Factur-X and XRechnung use it. ZUGFeRD 1.0's `CrossIndustryDocument` is not CII in this sense.
- **UBL**: the OASIS UBL 2.1 syntax, roots `Invoice` and `CreditNote` in their UBL 2.1 namespaces. Peppol BIS and XRechnung use it.
- **Edition**: the version of EN 16931-1 an invoice follows, as its specification identifier (BT-24) names it. A BT-24 that starts with `urn:cen.eu:en16931:` names the four-digit year that follows as its edition (`urn:cen.eu:en16931:2017#compliant#…` and `urn:cen.eu:en16931:2017:compliant:…` name 2017). The identifiers of REQ-002-PRS-F003 that don't start that way (Factur-X and ZUGFeRD MINIMUM and BASIC WL) name 2017. Any other BT-24, or none, names no edition.
- **Profile**: the CIUS or ZUGFeRD/Factur-X profile an invoice claims in BT-24, with its version: XRechnung 3.0, Factur-X EXTENDED, plain EN 16931 and so on.
- **Model**: the Python objects that hold an invoice's business terms.
- **Outside input**: anything Haflinger receives to read or validate, and the XML embedded in a PDF it receives. An invoice Haflinger has just written is not outside input to the writer, but is to anyone who receives it.
- **Value as written**: a value's characters in the XML. A number is written in the lexical form of XML Schema's `xs:decimal`: an optional sign, ASCII digits, and an optional decimal point with more digits; no exponent, no grouping, no other digits. A date is written in the form its syntax binding sets.
- **Refusal**: an exception with a reason, raised instead of a result.
- **Finding**: one failed rule of a validation, or one problem Haflinger itself reports, with the rule's ID; defined in REQ-002.
- **Official rules**: the Schematron rules published by CEN (EN 16931), KoSIT (XRechnung) and FeRD (Factur-X/ZUGFeRD profiles), compiled to XSLT. Rules Haflinger writes itself are not official rules.
- **Rule set**: the official rules an invoice is checked against, chosen by its syntax and profile (REQ-002).
- **Official test files**: test material published with the official rules or by the standards' communities: KoSIT's XRechnung test suite, CEN's per-rule unit tests, the ZUGFeRD corpus. Files Haflinger's own tests construct are not.
- **KoSIT test suite**: the business cases of [`itplr-kosit/xrechnung-testsuite`](https://github.com/itplr-kosit/xrechnung-testsuite), each as a CII and a UBL file.
- **ZUGFeRD PDF**: a PDF with an invoice in XML embedded as a file, as ZUGFeRD 2 and Factur-X define it. A PDF without such a file, or with a ZUGFeRD 1.0 file, is not one.
- **Reference machine**: the machine speed requirements are measured on: a laptop or server processor from 2023 or later, measured on one core with the file already in memory. The limits leave several times the time measured in the spikes, so that machines of this description meet them; each benchmark records the machine it ran on.

## URS — Functional

#### REQ-001-URS-F001: One model for every syntax

**Description**: The library SHALL hold an invoice as one model of EN 16931 business terms, the same whatever syntax the invoice is read from or written to.

**Related User Stories**: REQ-001-P1-1, REQ-001-P3-1 | **Rationale**: Everything built on the model (writing, validation of results, the software that uses the library) is then built once ([ADR-001](../arc42/adr/ADR-001-library-and-app.md)).

#### REQ-001-URS-F002: Values named by business term

**Description**: Each value in the model SHALL be identifiable by its EN 16931 business term or group ID.

**Related User Stories**: REQ-001-P3-1

#### REQ-001-URS-F003: The edition known

**Description**: The model SHALL record which EN 16931 edition an invoice follows.

**Related User Stories**: REQ-001-P1-2 | **Rationale**: Both editions are in use until March 2029; an invoice read as the wrong one is misread ([ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)).

## URS — Non-Functional

#### REQ-001-URS-NF001: Values exactly as they are

**Description**: The library SHALL NOT round, reformat, fill in or invent a value, on reading or on writing.

**Related User Stories**: REQ-001-P1-2 | **Rationale**: The operator's underlying fear.

**Exceptions**, the only ones:

- **Surrounding whitespace on reading** (REQ-003): whitespace around a value is removed, and an element empty after that counts as missing.
- **Exponent notation on writing** (REQ-004): a `Decimal` in exponent notation, which only a model built in code can hold, is written in plain notation with the same value.
- **Notation of numbers on reading** (REQ-003): a number keeps its value and its decimal places, not the characters that carry neither: a `+` sign, leading zeros, a decimal point without digits after it, a missing zero before it. `+0336.90` reads as `336.90`, `336.` as `336` and `.5` as `0.5`.

#### REQ-001-URS-NF002: Refuse or report, never guess

**Description**: What the library can't handle SHALL be refused or reported, naming the business term or the rule concerned.

**Related User Stories**: REQ-001-P1-2, REQ-001-P3-1

#### REQ-001-URS-NF003: Safe with outside input

**Description**: Processing outside input SHALL NOT expand entities, resolve external resources, access the network or execute content.

**Related User Stories**: REQ-001-P1-2 | **Rationale**: Incoming invoices come from anyone.

#### REQ-001-URS-NF004: Standalone

**Description**: The library SHALL run and be tested without any ERP system.

**Related User Stories**: REQ-001-P2-1, REQ-001-P3-1 | **Rationale**: Behaviour checkable against the official files alone, and usable by any software ([ADR-001](../arc42/adr/ADR-001-library-and-app.md)).

## PRS — Functional

#### REQ-001-PRS-F001: Business terms

**Description**: The model SHALL hold these business terms under these names; the table is what identifies each field's business term. The column EN 16931 marks the terms EN 16931 requires; what happens when one is missing is REQ-003's on reading and REQ-004's on writing. A missing term is `None`, a missing repeated group an empty tuple.

| Model | BT | Term | EN 16931 |
| :- | :- | :- | :- |
| `Invoice.number` | BT-1 | Invoice number | required |
| `Invoice.issue_date` | BT-2 | Invoice issue date | required |
| `Invoice.type_code` | BT-3 | Invoice type code | required |
| `Invoice.currency_code` | BT-5 | Invoice currency code | required |
| `Invoice.tax_currency_code` | BT-6 | VAT accounting currency code |  |
| `Invoice.due_date` | BT-9 | Payment due date |  |
| `Invoice.buyer_reference` | BT-10 | Buyer reference (Leitweg-ID) |  |
| `Invoice.project_reference` | BT-11 | Project reference |  |
| `Invoice.contract_reference` | BT-12 | Contract reference |  |
| `Invoice.purchase_order_reference` | BT-13 | Purchase order reference |  |
| `Invoice.sales_order_reference` | BT-14 | Sales order reference |  |
| `Invoice.receiving_advice_reference` | BT-15 | Receiving advice reference |  |
| `Invoice.despatch_advice_reference` | BT-16 | Despatch advice reference |  |
| `Invoice.tender_or_lot_reference` | BT-17 | Tender or lot reference |  |
| `Invoice.invoiced_object_id` | BT-18 | Invoiced object identifier, an Identifier: `value` BT-18 (required in the group), `scheme` BT-18-1 |  |
| `Invoice.buyer_accounting_reference` | BT-19 | Buyer accounting reference |  |
| `Invoice.business_process` | BT-23 | Business process type |  |
| `Invoice.specification_id` | BT-24 | Specification identifier | required |
| `Invoice.payment_terms` | BT-20 | Payment terms |  |
| `Invoice.notes` | BG-1 | Invoice note: `subject_code` BT-21, `text` BT-22 (required in the group) |  |
| `Invoice.preceding_invoices` | BG-3 | Preceding invoice references, any number: `number` BT-25 (required in the group), `issue_date` BT-26 |  |
| `Invoice.seller` | BG-4 | Seller | required |
| `Invoice.buyer` | BG-7 | Buyer | required |
| `Party.name` | BT-27, BT-44 | Seller name, buyer name | required |
| `Party.trading_name` | BT-28, BT-45 | Trading name |  |
| `Party.identifiers` | BT-29, BT-46 | Seller identifiers, any number; buyer identifier, at most one; each an Identifier: `value` BT-29, BT-46 (required in the group), `scheme` BT-29-1, BT-46-1 |  |
| `Party.legal_registration_id` | BT-30, BT-47 | Legal registration identifier, an Identifier: `value` BT-30, BT-47 (required in the group), `scheme` BT-30-1, BT-47-1 |  |
| `Party.vat_id` | BT-31, BT-48 | VAT identifier |  |
| `Party.tax_registration_id` | BT-32 | Seller tax registration identifier; the seller's alone |  |
| `Party.additional_legal_information` | BT-33 | Seller additional legal information; the seller's alone |  |
| `Party.electronic_address` | BT-34, BT-49 | Electronic address, an Identifier: `value` BT-34, BT-49 (required in the group), `scheme` BT-34-1, BT-49-1 (required in the group) |  |
| `Party.address_line_1` | BT-35, BT-50 | Address line 1 |  |
| `Party.address_line_2` | BT-36, BT-51 | Address line 2 |  |
| `Party.address_line_3` | BT-162, BT-163 | Address line 3 |  |
| `Party.city` | BT-37, BT-52 | City |  |
| `Party.post_code` | BT-38, BT-53 | Post code |  |
| `Party.country_subdivision` | BT-39, BT-54 | Country subdivision |  |
| `Party.country_code` | BT-40, BT-55 | Country code | required |
| `Party.contact` | BG-6, BG-9 | Contact: `point` BT-41, BT-56, `telephone` BT-42, BT-57, `email` BT-43, BT-58 |  |
| `Invoice.payee` | BG-10 | Payee, where it isn't the seller: `name` BT-59 (required in the group), `identifier` BT-60, an Identifier with its scheme BT-60-1, `legal_registration_id` BT-61, an Identifier with its scheme BT-61-1 |  |
| `Invoice.tax_representative` | BG-11 | Seller tax representative party: `name` BT-62 (required in the group), `vat_id` BT-63 (required in the group), and its postal address (BG-12, required in the group): `address_line_1` BT-64, `address_line_2` BT-65, `address_line_3` BT-164, `city` BT-66, `post_code` BT-67, `country_subdivision` BT-68, `country_code` BT-69 (required in the group) |  |
| `Invoice.delivery` | BG-13 | Delivery information: `party_name` BT-70, `location` BT-71, an Identifier with its scheme BT-71-1, `date` BT-72, and the deliver to address (BG-15): `address_line_1` BT-75, `address_line_2` BT-76, `address_line_3` BT-165, `city` BT-77, `post_code` BT-78, `country_subdivision` BT-79, `country_code` BT-80 (required in the address) |  |
| `Invoice.invoicing_period` | BG-14 | Invoicing period: `start` BT-73, `end` BT-74 |  |
| `Invoice.payment_instructions` | BG-16 | Payment instructions: `means_code` BT-81 (required in the group), `means_text` BT-82, `remittance_information` BT-83 |  |
| `PaymentInstructions.credit_transfers` | BG-17 | Credit transfers, any number: `account_id` BT-84 (required in the group), `account_name` BT-85, `provider_id` BT-86 |  |
| `PaymentInstructions.card` | BG-18 | Payment card information: `account_number` BT-87 (required in the group), `holder_name` BT-88 |  |
| `PaymentInstructions.direct_debit` | BG-19 | Direct debit: `mandate_reference` BT-89, `creditor_id` BT-90, `debited_account_id` BT-91 |  |
| `Invoice.allowances` | BG-20 | Document level allowances, any number: `amount` BT-92 (required in the group), `base_amount` BT-93, `percentage` BT-94, `vat_category_code` BT-95 (required in the group), `vat_rate` BT-96, `reason` BT-97, `reason_code` BT-98 |  |
| `Invoice.charges` | BG-21 | Document level charges, any number, with the fields of an allowance: `amount` BT-99 (required in the group), `base_amount` BT-100, `percentage` BT-101, `vat_category_code` BT-102 (required in the group), `vat_rate` BT-103, `reason` BT-104, `reason_code` BT-105 |  |
| `Invoice.totals` | BG-22 | Document totals | required |
| `Totals.line_net_total` | BT-106 | Sum of invoice line net amounts | required |
| `Totals.allowance_total` | BT-107 | Sum of allowances on document level |  |
| `Totals.charge_total` | BT-108 | Sum of charges on document level |  |
| `Totals.total_without_vat` | BT-109 | Invoice total amount without VAT | required |
| `Totals.vat_total` | BT-110 | Invoice total VAT amount |  |
| `Totals.vat_total_in_tax_currency` | BT-111 | Invoice total VAT amount in accounting currency |  |
| `Totals.total_with_vat` | BT-112 | Invoice total amount with VAT | required |
| `Totals.prepaid_amount` | BT-113 | Paid amount |  |
| `Totals.rounding_amount` | BT-114 | Rounding amount |  |
| `Totals.amount_due` | BT-115 | Amount due for payment | required |
| `Invoice.vat_breakdown` | BG-23 | VAT breakdown, at least one | required |
| `VatBreakdown.taxable_amount` | BT-116 | VAT category taxable amount | required |
| `VatBreakdown.tax_amount` | BT-117 | VAT category tax amount | required |
| `VatBreakdown.category_code` | BT-118 | VAT category code | required |
| `VatBreakdown.rate` | BT-119 | VAT category rate |  |
| `VatBreakdown.exemption_reason` | BT-120 | VAT exemption reason text |  |
| `VatBreakdown.exemption_reason_code` | BT-121 | VAT exemption reason code |  |
| `Invoice.supporting_documents` | BG-24 | Additional supporting documents, any number: `reference` BT-122 (required in the group), `description` BT-123, `external_location` BT-124, but not the attached document |  |
| `Invoice.lines` | BG-25 | Invoice lines, at least one | required |
| `InvoiceLine.id` | BT-126 | Invoice line identifier | required |
| `InvoiceLine.note` | BT-127 | Invoice line note |  |
| `InvoiceLine.quantity` | BT-129 | Invoiced quantity | required |
| `InvoiceLine.unit_code` | BT-130 | Invoiced quantity unit of measure | required |
| `InvoiceLine.net_amount` | BT-131 | Invoice line net amount | required |
| `InvoiceLine.net_price` | BT-146 | Item net price | required |
| `InvoiceLine.price_discount` | BT-147 | Item price discount |  |
| `InvoiceLine.gross_price` | BT-148 | Item gross price |  |
| `InvoiceLine.base_quantity` | BT-149 | Item price base quantity |  |
| `InvoiceLine.base_quantity_unit_code` | BT-150 | Item price base quantity unit of measure code |  |
| `InvoiceLine.vat_category_code` | BT-151 | Invoiced item VAT category code | required |
| `InvoiceLine.vat_rate` | BT-152 | Invoiced item VAT rate |  |
| `InvoiceLine.item_name` | BT-153 | Item name | required |
| `InvoiceLine.item_description` | BT-154 | Item description |  |
| `InvoiceLine.seller_item_id` | BT-155 | Item Seller's identifier |  |
| `InvoiceLine.buyer_item_id` | BT-156 | Item Buyer's identifier |  |
| `InvoiceLine.standard_item_id` | BT-157 | Item standard identifier, an Identifier: `value` BT-157 (required in the group), `scheme` BT-157-1 (required in the group) |  |

**Related URS**: REQ-001-URS-F001, REQ-001-URS-F002

**Definition of Done**:

- The model's business-term fields match this table; `syntax` (REQ-001-PRS-F002) and `edition` (REQ-001-PRS-F003) are the only others (inspection).
- The KoSIT business case 01.01a reads to one exact expected model in both syntaxes (test, REQ-003).

#### REQ-001-PRS-F002: Equality and origin

**Description**: Two models SHALL compare equal when all their business terms are equal; numbers compare by value (`10.50` equals `10.5`). `Invoice.syntax` SHALL record the syntax an invoice was read from (`"cii"` or `"ubl"`), or `None` for a model built otherwise, and SHALL NOT take part in the comparison.

**Related URS**: REQ-001-URS-F001

**Definition of Done**: a test compares the CII and UBL models of one invoice as equal while their `syntax` differs; a model built in code has `syntax` `None`; two models that differ only in `10.50` and `10.5` compare equal (tests).

#### REQ-001-PRS-F003: Edition

**Description**: `Invoice.edition` SHALL give the edition BT-24 names, as the term Edition defines it, as a string (`"2017"`), or `None` when BT-24 names none. It SHALL follow from BT-24 alone and SHALL NOT be set on its own.

**Related URS**: REQ-001-URS-F003

**Definition of Done**: every file of the KoSIT test suite, and every identifier of REQ-002-PRS-F003 including the alternative spellings, gives `"2017"`; `urn:cen.eu:en16931:2026` gives `"2026"`; the Peppol BIS identifier gives `"2017"`; a model without BT-24 or with `urn:example:other` gives `None` (tests).

#### REQ-001-PRS-F004: Exact values

**Description**: Amounts, quantities, prices and rates SHALL be finite `decimal.Decimal` values with the digits as written, apart from the notation REQ-001-URS-NF001 excepts; dates SHALL be `datetime.date`. A number SHALL be taken from the XML only when it is written as the term Value as written defines.

**Related URS**: REQ-001-URS-NF001

**Definition of Done**: an amount written with more decimal places than its currency has reads with the same digits (compared as strings, not by equality) and is written back with them (tests, REQ-003 and REQ-004); `1_000`, `1E+2`, `١٢` and `1 000` aren't taken as numbers, and `+0336.90` reads as `336.90` (tests, REQ-003).

#### REQ-001-PRS-F005: Refusals and findings name their subject

**Description**: A refusal's reason SHALL name the business term or group (`BT-n`, `BG-n`) it concerns, where there is one; a finding SHALL carry the ID of its rule.

**Related URS**: REQ-001-URS-NF002

**Definition of Done**: a test reads an invoice with a malformed BT-9 and finds `BT-9` in the finding's text (REQ-003); a test writes a model with a float in BT-112 and finds `BT-112` in the refusal's reason (REQ-004); the findings tests of REQ-002 check the rule IDs.

## PRS — Non-Functional

#### REQ-001-PRS-NF001: Outside input

**Description**: XML that contains a document type declaration or an entity declaration SHALL be refused before any reader, stylesheet or rule processes it; XML embedded in a PDF SHALL be parsed by nothing else before this check. Nothing referenced in outside input, in XML or in a PDF (external file specifications, URLs, actions), SHALL be fetched, opened or run. Reading and validation SHALL write nothing to the file system; `haflinger.pdf.embed`, whose input is the caller's own PDF, hands it to `factur-x` through a private temporary directory that is removed afterwards. The library SHALL use no value from an input as a path, URL or command; values such as file names are handed back as data.

**Related URS**: REQ-001-URS-NF003

**Definition of Done**: tests with an internal DTD, an entity expansion and an external entity each get a refusal, from reading and from validation; a PDF whose embedded XML declares an external entity gets a refusal from reading; a PDF whose file specification points to a file outside it reads without that file being opened (tests); Saxon opens only local files, so that a stylesheet can't fetch a URL (test); no reference in an input is fetched, reading and validation write nothing to the file system, and no input value reaches a path, URL or command (inspection).

#### REQ-001-PRS-NF002: No Frappe

**Description**: Importing and using the library SHALL load no module of Frappe or ERPNext, the ERP system its first user runs on.

**Related URS**: REQ-001-URS-NF004

**Definition of Done**: the tests run in an environment without Frappe; a test asserts that no `frappe` or `erpnext` module is loaded after using the library.

#### REQ-001-PRS-NF003: Size limit

**Description**: Every entry point that takes outside input (`read_invoice`, `validate`, `haflinger.pdf.extract_xml`) SHALL take a keyword argument `max_size`, in bytes, by default 100 MiB (104,857,600 bytes), and SHALL refuse input larger than it before parsing it. XML embedded in a PDF SHALL count against the same limit, checked while it is decompressed.

**Related URS**: REQ-001-URS-NF003 | **Rationale**: The default lies above the largest real invoice seen, 61.1 MB in the ZUGFeRD corpus; a caller with less memory to spare passes a lower `max_size`. The memory reading takes is measured (REQ-003-PRS-NF002).

**Definition of Done**: for each entry point, a test with a `max_size` below the input's size gets a refusal naming the limit, and a test reads an input just below it; a PDF whose embedded file inflates beyond `max_size` is refused without inflating it completely (test, REQ-003).

## Acceptance Criteria

- The model holds the business terms of REQ-001-PRS-F001, with equality and edition as REQ-001-PRS-F002 and REQ-001-PRS-F003 say.
- No value is rounded, reformatted or invented on reading or writing.
- Outside XML with a DTD or entity is refused before anything processes it, also when embedded in a PDF; outside input beyond its size limit is refused before parsing.
- Every refusal names its business term where there is one, every finding its rule.
- The library loads no Frappe or ERPNext module.

## Assumptions

- The model grows by need, in the order [ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md) sets. Which editions Haflinger supports is REQ-002's ([REQ-002-PRS-F009](req-002-conformance.md#req-002-prs-f009-editions-supported)).

## Open Questions

None at present. How the model takes in the 2026 edition is [ITEM-001](../backlog/item-001-en16931-2026.md)'s.
