# REQ-004: Haflinger Outgoing Invoices — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Draft |
| **Version** | 0.20 |
| **Date** | 2026-11-08 |
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

- **Before writing**, with no findings and no document, when the argument isn't an `Invoice`; the `timeout` isn't valid ([REQ-002-PRS-NF004](req-002-conformance.md#req-002-prs-nf004-time-limit)); the model's BT-24 is no supported target profile (REQ-004-PRS-F002); a value has the wrong type (an amount, quantity, price or rate that isn't a finite `Decimal`, a date that isn't a `date`, a text that isn't a `str`, a group that isn't of its class or a tuple of it); a number has more than 1,000 digits in plain notation; a text is empty, has surrounding whitespace, or holds a character XML 1.0 doesn't allow; a note (BG-1) holds neither subject code nor text, a contact (BG-6, BG-9) no term, an identifier (BT-18, BT-29, BT-30, BT-34, BT-46, BT-47, BT-49, BT-60, BT-61, BT-71, BT-128, BT-157) no value, an electronic address (BT-34, BT-49) no scheme, a card (BG-18) no account number (BT-87), which EN 16931 requires and no official rule checks in CII D16B, payment instructions (BG-16), a credit transfer (BG-17), a direct debit (BG-19), a preceding invoice (BG-3), the delivery information (BG-13), the invoicing period (BG-14), a line period (BG-26), an allowance (BG-20, BG-27), a charge (BG-21, BG-28), a payee (BG-10), a tax representative (BG-11) or a supporting document (BG-24) no term; the model holds more preceding invoices than CII D16B can, which is one; the buyer holds a tax registration identifier or additional legal information, which only the seller has (BT-32, BT-33), or more than one identifier (BT-46); a line's allowance or charge (BG-27, BG-28) holds a VAT category code or rate, which EN 16931 doesn't give it; or the model holds a term without one it needs to be written (BT-111 without BT-6, BT-130 without BT-129, BT-147 without BT-148, BT-150 without BT-149, BT-7 or BT-8 without a VAT breakdown, BG-23); or BT-8 holds CII's `5`, `29` or `72` instead of EN 16931's code.
- **After writing**, with the findings and the written document, when it fails REQ-004-PRS-F004 or REQ-004-PRS-F005, or can't be checked by them (for example, larger than the size limit validation accepts, or when the rules don't end within `timeout` or their worker dies, [REQ-002-PRS-NF004](req-002-conformance.md#req-002-prs-nf004-time-limit), [REQ-002-PRS-NF005](req-002-conformance.md#req-002-prs-nf005-rules-in-a-worker-process)).

**Related URS**: REQ-004-URS-F001, REQ-004-URS-F002

**Definition of Done**: a test writes a valid invoice and gets UTF-8 bytes with an XML declaration; a test writes an invoice whose BT-112 is off by one cent and gets `InvoiceWriteError` with `BR-CO-15` among its findings and the document, and so do tests with payment instructions without their means code (`BR-49`, and for EN 16931 Factur-X's XML Schema, which requires it), a credit transfer without its account (`BR-50`), a preceding invoice without its number (`BR-55`), a line period that ends before it starts (`BR-30`), a supporting document without its reference (`BR-52`), an allowance without its VAT category code (`BR-32`, for both target profiles) and a deliver to address without its country code (`BR-57`, and for EN 16931 Factur-X's XML Schema), which CII D16B can hold; a number of exactly 1,000 digits is written; one test per refusal before writing, each naming its business term (a float in BT-112, a string in BT-2, `" Example GmbH"` in BT-27, a control character in BT-153, BT-111 without BT-6, BT-147 without BT-148, BT-150 without BT-149, BT-7 and BT-8 without a VAT breakdown, a BT-7 that isn't a date without one, CII's code `29` in BT-8, an empty contact, an identifier without value, among them an invoiced object identifier (BT-18), a line object identifier (BT-128), a standard item identifier (BT-157) and an item classification identifier (BT-158), an electronic address without scheme, empty payment instructions, an empty credit transfer, a card without account number, an empty direct debit, two preceding invoices, an empty preceding invoice, delivery, invoicing period, line period, allowance or charge, document level or of a line, a line allowance holding a VAT category, an empty BT-77, a buyer with BT-32, BT-33 or two identifiers, an empty payee, tax representative or supporting document, a legal registration identifier without value, a line's item classifications not a tuple of ItemClassification, a classification's scheme that isn't a `str` (BT-158-1) and its scheme version with whitespace around it (BT-158-2)).

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
- **Parties**: an identifier (BT-29, BT-46) with a scheme as `ram:GlobalID` with that `schemeID`, one without as `ram:ID`; those without come first, as the XML Schema orders the two elements and as reading orders the model (REQ-003-PRS-F002); a model in another order reads back in that one. The seller's tax registration identifier (BT-32) as `ram:SpecifiedTaxRegistration/ram:ID` with `schemeID` `FC`, after the VAT identifier's; the contact point (BT-41, BT-56) as `ram:PersonName`. The legal registration identifier (BT-30, BT-47) with its scheme as `schemeID`; the seller's additional legal information (BT-33) as `ram:Description` after its name.
- **Payee and tax representative (BG-10, BG-11)**: the seller's tax representative as `ram:SellerTaxRepresentativeTradeParty` after the buyer, with its name, its postal address, written as a party's is, and its VAT identifier as `ram:SpecifiedTaxRegistration/ram:ID` with `schemeID` `VA`; the payee as `ram:PayeeTradeParty` in `ram:ApplicableHeaderTradeSettlement` after the invoice currency code, with its identifier, written as a party's is, its name and its legal registration identifier as `ram:SpecifiedLegalOrganization/ram:ID`, with their schemes as `schemeID`.
- **Payment instructions (BG-16)**: one `ram:SpecifiedTradeSettlementPaymentMeans` for each credit transfer (BG-17), or one where there is none, each with the means code (BT-81) and text (BT-82); the card (BG-18) and the debited account (BT-91, as `ram:PayerPartyDebtorFinancialAccount/ram:IBANID`) in the first. A credit transfer's account (BT-84) as `ram:IBANID` where it has an IBAN's form (two capital letters, two digits, then up to 30 letters and digits), else as `ram:ProprietaryID`; its provider (BT-86) as its payment means' `ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID`. The remittance information (BT-83) as `ram:PaymentReference`, the creditor identifier (BT-90) as `ram:CreditorReferenceID`. The payment terms (BT-20), the due date (BT-9) and the mandate reference (BT-89) in one `ram:SpecifiedTradePaymentTerms`. Payment terms that hold a line starting with `#`, as XRechnung's discount terms do, and end with a `#…#` run end with a line feed after it, which XRechnung's `BR-DE-18` requires and reading removes again as whitespace around the value.
- **Document references (BT-11 to BT-19)**: in `ram:ApplicableHeaderTradeAgreement` after the buyer, in the XML Schema's order: the sales order, purchase order and contract references (BT-14, BT-13, BT-12) as the `ram:IssuerAssignedID` of `ram:SellerOrderReferencedDocument`, `ram:BuyerOrderReferencedDocument` and `ram:ContractReferencedDocument`; the tender or lot reference (BT-17) and the invoiced object identifier (BT-18) each as a `ram:AdditionalReferencedDocument` with `ram:IssuerAssignedID` and the `ram:TypeCode` `50` or `130`, BT-18's scheme as `ram:ReferenceTypeCode`; then each supporting document (BG-24) as a `ram:AdditionalReferencedDocument` with its reference (BT-122) as `ram:IssuerAssignedID`, its external location (BT-124) as `ram:URIID`, the `ram:TypeCode` `916` and its description (BT-123) as `ram:Name`; the project reference (BT-11) as `ram:SpecifiedProcuringProject/ram:ID`, with the `ram:Name` the XML Schema requires as `Project reference`, as KoSIT's test files write it. The despatch and receiving advice references (BT-16, BT-15) as the `ram:IssuerAssignedID` of `ram:DespatchAdviceReferencedDocument` and `ram:ReceivingAdviceReferencedDocument` in `ram:ApplicableHeaderTradeDelivery`, after the delivery information; the buyer accounting reference (BT-19) as `ram:ReceivableSpecifiedTradeAccountingAccount/ram:ID`, last in `ram:ApplicableHeaderTradeSettlement`.
- **Preceding invoice, delivery and invoicing period**: the preceding invoice (BG-3) as `ram:InvoiceReferencedDocument` after the document totals, its date (BT-26) as `ram:FormattedIssueDateTime/qdt:DateTimeString` with `format="102"`; the delivery information (BG-13) in `ram:ApplicableHeaderTradeDelivery`, the deliver to party's name, location and address in `ram:ShipToTradeParty`, its location as a party's identifier is written, and the date (BT-72) in `ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime`; the invoicing period (BG-14) as `ram:BillingSpecifiedPeriod`.
- **Allowances and charges (BG-20, BG-21)**: each as a `ram:SpecifiedTradeAllowanceCharge` after the invoicing period, the allowances first, with the charge indicator `false` or `true` as `udt:Indicator`, and, where it holds either, its VAT category code and rate in `ram:CategoryTradeTax` with the type code `VAT`, so that a missing VAT category code reaches the official rules (`BR-32`, `BR-37`) rather than failing Factur-X's XML Schema.
- **Line allowances and charges (BG-27, BG-28)**: each as a `ram:SpecifiedTradeAllowanceCharge` in `ram:SpecifiedLineTradeSettlement`, after the line period and before the line's totals, the allowances first, written as the document's are but without VAT category, which EN 16931 doesn't give them. A line allowance or charge holding a VAT category code or rate, which the model's class can hold, is refused before writing.
- **Line references (BT-128, BT-132, BT-133)**: the referenced purchase order line reference (BT-132) as `ram:SpecifiedLineTradeAgreement/ram:BuyerOrderReferencedDocument/ram:LineID`, before the prices; in `ram:SpecifiedLineTradeSettlement` after the line totals, the line object identifier (BT-128) as a `ram:AdditionalReferencedDocument` with `ram:IssuerAssignedID`, the `ram:TypeCode` `130` and its scheme as `ram:ReferenceTypeCode`, as BT-18 is written, then the line's buyer accounting reference (BT-133) as `ram:ReceivableSpecifiedTradeAccountingAccount/ram:ID`.
- **Line details (BG-25, BG-26, BG-29, BG-31)**: the line note (BT-127) as `ram:IncludedNote/ram:Content` after the line identifier. The line period (BG-26) as `ram:BillingSpecifiedPeriod` in `ram:SpecifiedLineTradeSettlement`, after the line's VAT, written as the invoicing period is. The item in `ram:SpecifiedTradeProduct`, in the XML Schema's order: the standard identifier (BT-157) as `ram:GlobalID` with its scheme as `schemeID`, the seller's identifier (BT-155) as `ram:SellerAssignedID`, the buyer's (BT-156) as `ram:BuyerAssignedID`, the name (BT-153), the description (BT-154) as `ram:Description`, each classification identifier (BT-158) as a `ram:DesignatedProductClassification` holding a `ram:ClassCode` with its scheme (BT-158-1) as `listID` and the scheme's version (BT-158-2) as `listVersionID`, then the country of origin (BT-159) as `ram:OriginTradeCountry/ram:ID`. A classification without a scheme is written without one, and CEN's rules report it (`BR-65`). The gross price (BT-148) as `ram:GrossPriceProductTradePrice/ram:ChargeAmount`, with the price discount (BT-147) as its `ram:AppliedTradeAllowanceCharge` with the charge indicator `false` and `ram:ActualAmount`; the base quantity (BT-149), with its unit (BT-150) as `unitCode`, as `ram:BasisQuantity` of the net price and, where it is written, of the gross price, so that both prices are for the same quantity. A price discount without a gross price, which UBL can hold, can't be written: CII holds the discount only within the gross price, and writing computes no value the model doesn't hold ([REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)).
- **VAT point date (BT-7, BT-8)**: in the first VAT breakdown's `ram:ApplicableTradeTax`, after the exemption reason code: BT-7 as `ram:TaxPointDate/udt:DateString` with `format="102"`, BT-8 as `ram:DueDateTypeCode`, EN 16931's `3`, `35` and `432` as CII's `5`, `29` and `72` and any other code as it is; a model holding CII's own codes is refused before writing, naming EN 16931's ([REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)). An invoice with both is written, and CEN's rules report it (`BR-CO-03`). Without a VAT breakdown (BG-23), which EN 16931 requires, neither can be written.
- **VAT totals**: BT-110 as `ram:TaxTotalAmount` with `currencyID` BT-5; BT-111 as a second `ram:TaxTotalAmount` with `currencyID` BT-6.
- **Numbers** in plain notation with the digits the model holds: `Decimal("10.50")` stays `10.50`; `Decimal("1E+2")` is written `100` (the exception of [REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)).
- The elements the XML Schema requires and that need no content (`ram:ApplicableHeaderTradeAgreement`, `ram:ApplicableHeaderTradeDelivery` and `ram:ApplicableHeaderTradeSettlement`; in a line, `ram:AssociatedDocumentLineDocument` and `ram:SpecifiedLineTradeSettlement`) are written even when empty.

**Related URS**: REQ-004-URS-F001

**Definition of Done**: a test writes numbers with trailing zeros and reads them back with the same digits, and writes `Decimal("1E+2")` as `100`; a test writes a model without optional terms and finds none of their elements; a test writes identifiers with and without scheme, BT-32, address lines 2 and 3, the subdivision and a contact, finds them where this requirement puts them, and reads them back; so does a test with payment terms and instructions holding two credit transfers, one IBAN and one other account, a card and a direct debit, and ones with XRechnung's discount terms, last and before a closing note; so does a test with a preceding invoice, delivery information and an invoicing period; so does a test with two allowances and a charge, with every term; so does a test with every document reference (BT-11 to BT-19), and one with two supporting documents beside them; so does a test with a payee and a tax representative, with every term, and the seller's additional legal information and legal registration scheme; so does a test with a VAT point date, and with each VAT point date code of EN 16931, written as CII's, and another code as it is, a CII file with EN 16931's code written with CII's, and one with both, refused after writing with `BR-CO-03`; so does a test with a line's two allowances and a charge, with every term, after its period; so does a test with a line holding every term of BT-127 to BT-133 and BG-26 to BG-31 the model holds, and one with a base quantity but no gross price; the rest is covered by REQ-004-PRS-F004 to REQ-004-PRS-F006.

#### REQ-004-PRS-F004: XML Schema

**Description**: A written invoice SHALL be valid against the CII D16B XML Schema and, for the target profile `urn:cen.eu:en16931:2017`, against Factur-X's XML Schema of the EN 16931 profile. A schema violation is a `HAFL-XSD` finding ([REQ-002-PRS-F010](req-002-conformance.md#req-002-prs-f010-haflingers-own-findings)).

**Related URS**: REQ-004-URS-F002

**Definition of Done**: every invoice written in the round trip of REQ-004-PRS-F006 is schema-valid; a deliberately broken document gets a `HAFL-XSD` finding (tests).

#### REQ-004-PRS-F005: Official rules

**Description**: A written invoice SHALL be validated with the rule set of its target profile ([REQ-002-PRS-F003](req-002-conformance.md#req-002-prs-f003-rule-sets)) and, for the target profile `urn:cen.eu:en16931:2017`, which a ZUGFeRD PDF labels Factur-X EN 16931 (REQ-004-PRS-F007), also with FeRD's Factur-X rules of the EN 16931 profile. It SHALL be handed out only when it is valid as [REQ-002-PRS-F002](req-002-conformance.md#req-002-prs-f002-findings) defines.

**Related URS**: REQ-004-URS-F002 | **Rationale**: A recipient may check a ZUGFeRD PDF with FeRD's rules rather than CEN's; FeRD's rules of the profile also reject what the profile doesn't use, such as a line's VAT exemption reason.

**Definition of Done**: in the round trip of REQ-004-PRS-F006, every `fatal` or `error` finding of a written KoSIT file is a rule that needs a business term the model doesn't hold yet, or that a code only the file's own profile allows fails, as the round trip writes XRechnung's extension and CVD as XRechnung 3.0; the test lists those rules in two lists, with the missing terms and with the codes, and a further test fails once a listed rule no longer fires on any file, so that the first list shrinks as the model grows; every invoice handed out passes FeRD's EN 16931 rules without `fatal` or `error`.

#### REQ-004-PRS-F006: Round trip over the KoSIT suite

**Description**: For every file of the KoSIT test suite, CII and UBL, the document written from its model (handed out, or carried by the refusal) SHALL read back to that model, its BT-24 written as XRechnung 3.0 where it names XRechnung's extension or CVD, which aren't target profiles (REQ-004-PRS-F002), and its preceding invoices (BG-3) reduced to the first where it holds more than CII D16B can, with `haflinger.read_invoice`, without findings, and with KoSIT's reading stylesheet.

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

- With the terms of [ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)'s first step in the model, `write_cii` hands out 82 of the 86 KoSIT models as either target profile. Two of the others use XRechnung's extension (third party payments, `BR-CO-16`; schemes for digital health apps, `BR-CL-10`), whose terms are outside the model; the two files of the CVD case classify a vehicle by the scheme `CVD` (BT-158-1), which only XRechnung's CVD allows beside UNTDID 7143 (`BR-CL-13`), and CVD is no target profile (REQ-004-PRS-F002). The rules refuse all four with findings naming the rule each fails.
- Factur-X's XML Schemas are vendored under [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md) ([ITEM-002](../backlog/item-002-official-test-material.md)).
- `factur-x` produces PDF/A-3 when its input is PDF/A, as its changelog states (tested there with veraPDF); it doesn't convert other PDFs to PDF/A.

## Open Questions

- More target profiles (EXTENDED, BASIC) when a customer needs them?
- XRechnung as a ZUGFeRD PDF (profile XRECHNUNG, `xrechnung.xml`), which `factur-x` doesn't write: needed by any recipient?
