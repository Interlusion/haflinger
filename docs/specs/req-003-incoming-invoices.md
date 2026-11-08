# REQ-003: Haflinger Incoming Invoices — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Draft |
| **Version** | 0.19 |
| **Date** | 2026-11-08 |
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
- **VAT point date (BT-7, BT-8)**: in CII, the VAT point date (BT-7) is the `ram:TaxPointDate/udt:DateString` with `format="102"` of the VAT breakdown's `ram:ApplicableTradeTax` (BG-23), which CEN's `CII-SR-461` allows in one of them; a further one is left out with a `HAFL-DROPPED` finding. Its code (BT-8) is their `ram:DueDateTypeCode`, which `CII-SR-462` allows in each of them with the same value: a repeat of the first one's code is the same term, one with another code is left out with a `HAFL-DROPPED` finding; `5`, `29` and `72` read as EN 16931's `3`, `35` and `432`, and EN 16931's codes as they are ([REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)). In UBL, BT-7 is `cbc:TaxPointDate` and BT-8 is `cac:InvoicePeriod/cbc:DescriptionCode`, which doesn't make a `cac:InvoicePeriod` the invoicing period (BG-14) and which `UBL-SR-49` allows once: a further one is left out with a `HAFL-DROPPED` finding, whatever its code. Both are read beside each other; CEN's rules report an invoice with both (`BR-CO-03`).
- **Parties**: the identifiers (BT-29, BT-46) are, in CII, every `ram:ID` and every `ram:GlobalID` with a `schemeID` of the party, in UBL every `cac:PartyIdentification/cbc:ID`, except the seller's with scheme `SEPA`, which is the bank assigned creditor identifier (BT-90); a `ram:GlobalID` without `schemeID` identifies nothing (CEN's rules too take a `ram:GlobalID` with its scheme) and is left out with a `HAFL-DROPPED` finding. Each identifier's, legal registration identifier's and electronic address's scheme (BT-29-1, BT-30-1, BT-34-1, BT-46-1, BT-47-1, BT-49-1, BT-60-1, BT-61-1) is its element's `schemeID`. The seller's additional legal information (BT-33) is CII's `ram:Description` of the seller and UBL's `cac:PartyLegalEntity/cbc:CompanyLegalForm`, read from the legal entity the seller's name comes from. The model holds identifiers in one order whatever the syntax, those without a scheme first, then those with one, each in document order, as CII's XML Schema orders `ram:ID` before `ram:GlobalID`, so that the CII and UBL forms of one invoice read to equal models. The buyer has one identifier: the first with a scheme, or else the first without, is read, and each further one is left out with a `HAFL-DROPPED` finding (CEN's `CII-SR-450` warns where a CII buyer has both). The contact (BG-6, BG-9) is the first contact element holding one of its terms; an element holding only what the model doesn't hold, such as an EXTENDED invoice's fax number, isn't the contact, and each further element holding one of its terms is left out with a `HAFL-DROPPED` finding. The seller's tax registration identifier (BT-32) is, in CII, the `ram:SpecifiedTaxRegistration/ram:ID` with `schemeID` `FC`, in UBL the `cbc:CompanyID` of a `cac:PartyTaxScheme` whose `cac:TaxScheme/cbc:ID` holds another value than `VAT`. In CII, the contact point (BT-41, BT-56) is `ram:PersonName`, or `ram:DepartmentName` where the contact holds no person name (EN 16931-3-3 assigns either; CEN's rules warn where both are given, `CII-SR-465` and `CII-SR-466`); a department name beside a person name is left out with a `HAFL-DROPPED` finding. In UBL, address line 3 (BT-162, BT-163) is the first `cac:AddressLine/cbc:Line`.
- **Supporting documents (BG-24)**: an additional document's type code decides what it is. In CII, a supporting document is each `ram:ApplicableHeaderTradeAgreement/ram:AdditionalReferencedDocument` with the type code `916`, to which EN 16931-3-3 binds the group, with its reference (BT-122) `ram:IssuerAssignedID`, its description (BT-123) `ram:Name` and its external location (BT-124) `ram:URIID`; one of another type code than `50` and `130`, or without one, that holds a reference, description or location is left out with a `HAFL-DROPPED` finding. In UBL, it is each `cac:AdditionalDocumentReference` other than those of BT-18's type code `130` and, in a credit note, of BT-11's `50`, whatever its type code, with `cbc:ID`, `cbc:DocumentDescription` and `cac:Attachment/cac:ExternalReference/cbc:URI`. An additional document of BT-11's, BT-17's or BT-18's type code holds only that reference's identifier: a description or location in it is left out with a `HAFL-DROPPED` finding, and it is no supporting document, even without an identifier. Supporting documents are read in document order; one holding none of the three terms, such as one holding only an attached document (BT-125), which the model doesn't hold, is neither read nor reported. KoSIT's stylesheets also give BT-17's and BT-18's additional documents as supporting documents ([ITEM-006](../backlog/item-006-upstream-reports.md)).
- **Payee and tax representative (BG-10, BG-11)**: the payee (BG-10) is CII's `ram:ApplicableHeaderTradeSettlement/ram:PayeeTradeParty` and UBL's `cac:PayeeParty`: its name (BT-59) is `ram:Name` and `cac:PartyName/cbc:Name`; its identifier (BT-60) is chosen as the buyer's is, from CII's `ram:ID` and `ram:GlobalID` and from UBL's `cac:PartyIdentification/cbc:ID` other than the one with scheme `SEPA`, which is the bank assigned creditor identifier (BT-90); its legal registration identifier (BT-61) is `ram:SpecifiedLegalOrganization/ram:ID` and `cac:PartyLegalEntity/cbc:CompanyID`. The seller's tax representative (BG-11) is CII's `ram:ApplicableHeaderTradeAgreement/ram:SellerTaxRepresentativeTradeParty` and UBL's `cac:TaxRepresentativeParty`: its name (BT-62) is `ram:Name` and `cac:PartyName/cbc:Name`, its VAT identifier (BT-63) is, in CII, the `ram:SpecifiedTaxRegistration/ram:ID` with `schemeID` `VA` or, since the tax representative has no other tax term, without one (one with another scheme is left out with a `HAFL-DROPPED` finding), in UBL read as the seller's is, and its postal address (BG-12) as a party's is. Each of the two, and the elements within it that hold several of its terms, is read from one element.
- **Document references (BT-11 to BT-19)**: in CII, the project reference (BT-11) is `ram:ApplicableHeaderTradeAgreement/ram:SpecifiedProcuringProject/ram:ID`; the contract, purchase order and sales order references (BT-12, BT-13, BT-14) are the `ram:IssuerAssignedID` of the agreement's `ram:ContractReferencedDocument`, `ram:BuyerOrderReferencedDocument` and `ram:SellerOrderReferencedDocument`; the receiving and despatch advice references (BT-15, BT-16) that of `ram:ApplicableHeaderTradeDelivery`'s `ram:ReceivingAdviceReferencedDocument` and `ram:DespatchAdviceReferencedDocument`; the tender or lot reference (BT-17) and the invoiced object identifier (BT-18) that of the agreement's `ram:AdditionalReferencedDocument` with the type code `50` and `130`, BT-18's scheme (BT-18-1) its `ram:ReferenceTypeCode` or else the `schemeID` of its `ram:IssuerAssignedID`; a differing `schemeID` beside a `ram:ReferenceTypeCode`, and a `ram:ReferenceTypeCode` in a document without an identifier, are left out with a `HAFL-DROPPED` finding; and the buyer accounting reference (BT-19) `ram:ApplicableHeaderTradeSettlement/ram:ReceivableSpecifiedTradeAccountingAccount/ram:ID`. In UBL they are `cac:ProjectReference/cbc:ID`, in a credit note, which has no project reference element, the `cbc:ID` of the `cac:AdditionalDocumentReference` with the document type code `50`; `cac:ContractDocumentReference/cbc:ID`; `cac:OrderReference/cbc:ID` and `cac:OrderReference/cbc:SalesOrderID`; `cac:ReceiptDocumentReference/cbc:ID` and `cac:DespatchDocumentReference/cbc:ID`; `cac:OriginatorDocumentReference/cbc:ID`; the `cbc:ID` of the `cac:AdditionalDocumentReference` with the document type code `130`, its scheme the `schemeID`; and `cbc:AccountingCost`. These are the elements KoSIT's reading stylesheet reads them from; where Haflinger reads one differently, [ITEM-006](../backlog/item-006-upstream-reports.md) records it. A type code counts with the whitespace around it removed; an additional document of another type code, or without one, is a supporting document (BG-24) or is left out as one, and a line's (BT-128) isn't the invoice's. Each reference is a term the model holds once (Repeated values); an order reference of `NA`, which Peppol writes where there is only a sales order reference, is read as written.
- **Preceding invoices, delivery and invoicing period**: each preceding invoice reference (BG-3) is CII's `ram:ApplicableHeaderTradeSettlement/ram:InvoiceReferencedDocument`, which CII D16B allows once, with `ram:IssuerAssignedID` and the date `ram:FormattedIssueDateTime/qdt:DateTimeString`, or UBL's `cac:BillingReference/cac:InvoiceDocumentReference`, with `cbc:ID` and `cbc:IssueDate`; a reference holding neither is left out. The delivery information (BG-13) comes from CII's `ram:ApplicableHeaderTradeDelivery`: the deliver to party's name (BT-70), location identifier (BT-71) and address (BG-15) from `ram:ShipToTradeParty`, its identifier chosen as the buyer's is, and the delivery date (BT-72) from `ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime`; in UBL from the first `cac:Delivery` holding one of its terms: `cac:DeliveryParty/cac:PartyName/cbc:Name`, `cac:DeliveryLocation/cbc:ID`, `cbc:ActualDeliveryDate` and `cac:DeliveryLocation/cac:Address`, read as a party's postal address is. The invoicing period (BG-14) is CII's `ram:BillingSpecifiedPeriod` with `ram:StartDateTime` and `ram:EndDateTime`, UBL's first `cac:InvoicePeriod` holding `cbc:StartDate` or `cbc:EndDate`.
- **Payment instructions (BG-16)**: EN 16931 gives an invoice one payment means, which the syntaxes repeat once for each account it is paid to. In CII, each `ram:SpecifiedTradeSettlementPaymentMeans` holding a value is a payment means, in UBL each `cac:PaymentMeans`. The means code (BT-81, `ram:TypeCode`, `cbc:PaymentMeansCode`) is the first one given; a payment means with another code is left out with the accounts, card and mandate it holds, with a `HAFL-DROPPED` finding, as KoSIT's stylesheet tells payment means apart by their code alone. Of the payment means kept, the text (BT-82, `ram:Information`, the `name` of `cbc:PaymentMeansCode`) and, in UBL, the remittance information (BT-83, `cbc:PaymentID`) are the first given; another value of either is left out with a `HAFL-DROPPED` finding, the payment means with it. Each account of the payment means kept is a credit transfer (BG-17): in CII `ram:PayeePartyCreditorFinancialAccount`, with the account (BT-84) its `ram:IBANID` or else its `ram:ProprietaryID` (a `ram:ProprietaryID` beside a `ram:IBANID` is left out with a `HAFL-DROPPED` finding), the name (BT-85) its `ram:AccountName` and the provider (BT-86) the payment means' `ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID`, which, in a payment means without an account, is left out with a `HAFL-DROPPED` finding; in UBL `cac:PayeeFinancialAccount`, with `cbc:ID`, `cbc:Name` and `cac:FinancialInstitutionBranch/cbc:ID`. The card (BG-18: CII `ram:ApplicableTradeSettlementFinancialCard` with `ram:ID` and `ram:CardholderName`, UBL `cac:CardAccount` with `cbc:PrimaryAccountNumberID` and `cbc:HolderName`) comes from the first payment means holding one, and so do, for the direct debit (BG-19), the UBL `cac:PaymentMandate` (BT-89 `cbc:ID`, BT-91 `cac:PayerFinancialAccount/cbc:ID`) and the CII debited account (BT-91, `ram:PayerPartyDebtorFinancialAccount/ram:IBANID`). Outside the payment means: in CII the remittance information (BT-83) is `ram:PaymentReference`, the mandate reference (BT-89) `ram:SpecifiedTradePaymentTerms/ram:DirectDebitMandateID` and the creditor identifier (BT-90) `ram:CreditorReferenceID`; in UBL the creditor identifier is the `cac:PartyIdentification/cbc:ID` with scheme `SEPA` of the payee read, or else of the seller (a further `cac:PayeeParty`, left out, gives none), and only beside a `cac:PaymentMandate`: without one there is no direct debit, and such an identifier is left out with a `HAFL-DROPPED` finding, as is the seller's beside the payee's. A scheme counts with the whitespace around it removed, like any value. The payment terms (BT-20) are CII's `ram:SpecifiedTradePaymentTerms/ram:Description` and UBL's `cac:PaymentTerms/cbc:Note`.
- **Allowances and charges (BG-20, BG-21)**: in CII each `ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeAllowanceCharge` holding a value, in UBL each `cac:AllowanceCharge` of the invoice itself, not of a line; its charge indicator (`ram:ChargeIndicator/udt:Indicator`, `cbc:ChargeIndicator`) makes it a charge where it is `true` or `1`, an allowance where it is `false` or `0`, the values of `xs:boolean`; one without either is left out with a `HAFL-DROPPED` finding, since it is neither. The charge indicator is read like a term: a further one is left out with a `HAFL-DROPPED` finding, and one holding elements with a `HAFL-VALUE` finding. The VAT category code and rate (BT-95, BT-96, BT-102, BT-103) come from the first `ram:CategoryTradeTax` or `cac:TaxCategory` of VAT holding a value; a further one of VAT is left out with a `HAFL-DROPPED` finding.
- **Line allowances and charges (BG-27, BG-28)**: read as the document's are (BG-20, BG-21), from each CII `ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeAllowanceCharge` and each UBL `cac:AllowanceCharge` of the line itself, not of its price, which gives the price discount (BT-147): the amount (BT-136, BT-141) `ram:ActualAmount` and `cbc:Amount`, the base amount (BT-137, BT-142) `ram:BasisAmount` and `cbc:BaseAmount`, the percentage (BT-138, BT-143) `ram:CalculationPercent` and `cbc:MultiplierFactorNumeric`, the reason (BT-139, BT-144) `ram:Reason` and `cbc:AllowanceChargeReason`, and its code (BT-140, BT-145) `ram:ReasonCode` and `cbc:AllowanceChargeReasonCode`, in document order, told apart by the charge indicator. EN 16931 gives a line's allowance or charge no VAT category, which is the line's (BG-30): a `ram:CategoryTradeTax` or `cac:TaxCategory` in one is not read, as an element outside EN 16931 isn't.
- **Line references (BT-128, BT-132, BT-133)**: the invoice line object identifier (BT-128) and its scheme are read as the invoice's BT-18 and BT-18-1 are, from the line's additional document of the type code `130`: in CII the `ram:IssuerAssignedID` of `ram:SpecifiedLineTradeSettlement/ram:AdditionalReferencedDocument`, its scheme (BT-128-1) the `ram:ReferenceTypeCode` or else the `schemeID` of its `ram:IssuerAssignedID`, a differing `schemeID` beside a `ram:ReferenceTypeCode`, and a `ram:ReferenceTypeCode` in a document without an identifier, left out with a `HAFL-DROPPED` finding; in UBL the `cbc:ID` of the line's `cac:DocumentReference`, its scheme the `schemeID`. A line's additional document of another type code, or without one, that holds an identifier is left out with a `HAFL-DROPPED` finding, as EN 16931 binds a line's additional document to BT-128 alone; a description or location in it, or in BT-128's (`ram:Name`, `ram:URIID`; `cbc:DocumentDescription`, `cac:Attachment`), is no term of the model, and no supporting document (BG-24), which EN 16931 has only for the invoice: it is ignored without a finding, as an element outside EN 16931 is. The referenced purchase order line reference (BT-132) is CII's `ram:SpecifiedLineTradeAgreement/ram:BuyerOrderReferencedDocument/ram:LineID` and UBL's `cac:OrderLineReference/cbc:LineID`; the line's buyer accounting reference (BT-133) CII's `ram:SpecifiedLineTradeSettlement/ram:ReceivableSpecifiedTradeAccountingAccount/ram:ID` and UBL's `cbc:AccountingCost`. Each is a term the model holds once (Repeated values).
- **Line details (BG-25, BG-26, BG-29, BG-31, BG-32)**: the line note (BT-127) is CII's `ram:AssociatedDocumentLineDocument/ram:IncludedNote/ram:Content` and UBL's `cbc:Note`. The line period (BG-26) is read as the invoicing period is: CII's `ram:SpecifiedLineTradeSettlement/ram:BillingSpecifiedPeriod` with its start (BT-134) `ram:StartDateTime` and its end (BT-135) `ram:EndDateTime`, UBL's first `cac:InvoicePeriod` of the line holding `cbc:StartDate` or `cbc:EndDate`; a further one holding either is left out with a `HAFL-DROPPED` finding. The price details (BG-29) come from CII's `ram:SpecifiedLineTradeAgreement` and UBL's `cac:Price`. In CII the gross price (BT-148) is `ram:GrossPriceProductTradePrice/ram:ChargeAmount` and the price discount (BT-147) its `ram:AppliedTradeAllowanceCharge/ram:ActualAmount`; in UBL both come from the price's `cac:AllowanceCharge`, the discount its `cbc:Amount` and the gross price its `cbc:BaseAmount`. Only an allowance holding one of these amounts gives them: one whose charge indicator is `false` or `0`, or that has no charge indicator, since EN 16931 has no charge on a price (CEN's `CII-SR-119` warns of a CII one without its indicator). A charge on the price, which Factur-X EXTENDED allows, one whose indicator is neither, an empty one included, and a further allowance are left out with a `HAFL-DROPPED` finding. The base quantity (BT-149) is UBL's `cbc:BaseQuantity` and, in CII, the `ram:BasisQuantity` of the net price, to which the net price (BT-146) applies, or else of the gross price; its unit (BT-150) is the `unitCode` of the same element, or of the other where only that one gives a unit. A gross price's base quantity or unit that differs from the net price's is left out with a `HAFL-DROPPED` finding. The item (BG-31) is CII's `ram:SpecifiedTradeProduct` and UBL's `cac:Item`: the description (BT-154) `ram:Description` and `cbc:Description`, the seller's and the buyer's identifiers (BT-155, BT-156) `ram:SellerAssignedID` and `ram:BuyerAssignedID`, `cac:SellersItemIdentification/cbc:ID` and `cac:BuyersItemIdentification/cbc:ID`, and the standard identifier (BT-157) `ram:GlobalID` and `cac:StandardItemIdentification/cbc:ID`, with its scheme (BT-157-1) the element's `schemeID`; one without a scheme is read without one, which CEN's rules report (`BR-64`). Each classification identifier (BT-158) is a `ram:DesignatedProductClassification/ram:ClassCode` and a `cac:CommodityClassification/cbc:ItemClassificationCode` holding a value, in document order, with its scheme (BT-158-1) the element's `listID` and the scheme's version (BT-158-2) its `listVersionID`, which KoSIT's reading stylesheet reads too; one without a scheme is read without one, which CEN's rules report (`BR-65`), and an element holding only these attributes is not read, as a standard identifier (BT-157) holding only its `schemeID` isn't. The country of origin (BT-159) is `ram:OriginTradeCountry/ram:ID` and `cac:OriginCountry/cbc:IdentificationCode`. Each item attribute (BG-32) is a `ram:ApplicableProductCharacteristic` or `cac:AdditionalItemProperty` holding its name (BT-160), `ram:Description` or `cbc:Name`, or its value (BT-161), `ram:Value` or `cbc:Value`, in document order; one holding only one of them is read with it, which CEN's rules report (`BR-54`), or, for a UBL one without its name, UBL's XML Schema, and one holding neither is not read. An attribute holds its name and its value once: a further one is left out with a `HAFL-DROPPED` finding. A CII attribute's `ram:TypeCode` or `ram:ValueMeasure`, the forms of a name and a value that only Factur-X EXTENDED allows, is left out with a `HAFL-DROPPED` finding.
- **Taxes other than VAT**: in CII, only an `ram:ApplicableTradeTax` whose `ram:TypeCode` is `VAT`, or that has no type code, gives the VAT breakdown (BG-23) and a line's VAT information (BG-30), and only such a `ram:CategoryTradeTax` an allowance's or a charge's VAT category; in UBL, only a `cac:TaxCategory` whose `cac:TaxScheme/cbc:ID` is `VAT`, or that has none, gives an allowance's or a charge's VAT category. Another tax, which Factur-X EXTENDED allows, is left out with a `HAFL-DROPPED` finding. The type code and the tax scheme are read like a term, the first one holding a value, and count as `VAT` in any case (`vat`), as CEN's rules compare them.
- **Repeated values**: where the invoice holds a term more often than the model does (two due dates, BT-9, in an EXTENDED invoice; two VAT totals in one currency), the first that holds a value is read and each further one that holds a value is left out with a `HAFL-DROPPED` finding. The same holds for the groups the model holds once and for the elements within a party or a line that hold several of its terms (the postal address, the legal organisation or entity, the line's VAT information BG-30, its price BG-29, its item BG-31): the first element that holds any value is read, all of its terms from it, and each further one holding a value is left out with a `HAFL-DROPPED` finding, so that no group mixes the terms of two. The VAT totals (BT-110, BT-111) are read also where the document totals (BG-22) are missing, and the units of measure (BT-130, BT-150) also where their quantity element is empty.
- **Whitespace**: XML whitespace (space, tab, carriage return, line feed) around a value is removed, and an element empty after that counts as missing (the exception of [REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)); other whitespace, such as a no-break space, is kept. An invoice line (BG-25) or a VAT breakdown (BG-23) whose element holds no value counts as missing too.
- **Malformed values**: a number not written as `xs:decimal` (REQ-001's term Value as written), a CII date not written as `YYYYMMDD` with `format="102"`, or a UBL date not written as `YYYY-MM-DD`, and a value whose element holds elements instead of only text, whichever term it gives, is read as missing, with a `HAFL-VALUE` finding. A number keeps its value and decimal places, not its notation (the exception of [REQ-001-URS-NF001](req-001-core.md#req-001-urs-nf001-values-exactly-as-they-are)).

The findings are those of [REQ-002-PRS-F010](req-002-conformance.md#req-002-prs-f010-haflingers-own-findings).

**Related URS**: REQ-003-URS-F001, REQ-003-URS-F006

**Definition of Done**: one test per choice: a UBL note with `#AAI#`; a KoSIT case with BT-6 for both VAT totals; a CII `TaxTotalAmount` without `currencyID`; a VAT total in a third currency; an invoice with two due dates (first read, one `HAFL-DROPPED`; constructed, and FeRD's EXTENDED sample X07 where the maintainer's copy of the package is present); an element holding only whitespace, and a no-break space kept; `1E+2` as BT-112 and `2026-10-30` as a CII date (missing, one `HAFL-VALUE` each), and `+0336.90` as BT-112 (`336.90`); a constructed EXTENDED line with another tax before its VAT; a payee and a tax representative with every term, and the seller's additional legal information and legal registration scheme, in both syntaxes; a UBL payee's identifier with scheme `SEPA` read as BT-90 only, and a dropped second UBL payee's not read as BT-90; a second payee and a second tax representative dropped, in both syntaxes; a CII tax representative's VAT identifier without a scheme read, and one with another scheme dropped; every document reference (BT-11 to BT-19) in both syntaxes, and the project reference of a UBL credit note; supporting documents with every term in both syntaxes, and in a UBL credit note beside its project reference; a CII additional document with another type code and one without a type code dropped, and a UBL one with another type code than `130` read as a supporting document; a supporting document holding only an attached document not read, in both syntaxes, and a CII one not reported, with the type code `916` and with another; a description or location in BT-17's and BT-18's additional documents dropped in CII, and in BT-18's in UBL, with and without an identifier; a second contract reference and a second invoiced object identifier dropped, each finding naming its value; a CII invoiced object identifier's scheme as `schemeID`, beside a differing `ram:ReferenceTypeCode`, and a `ram:ReferenceTypeCode` without an identifier; a tender or lot reference holding elements reported once; a supporting document's repeated type code reported as BG-24's; a CII line's additional document with type code `130` read as the line's BT-128, not the invoice's BT-18, and an additional document of another type code read as neither BT-17 nor BT-18; the line references (BT-128, BT-132, BT-133) in both syntaxes, and in a UBL credit note; a CII line object identifier's scheme as `schemeID`, beside a differing `ram:ReferenceTypeCode`, and a `ram:ReferenceTypeCode` without an identifier; a line's additional document of another type code and one without a type code dropped, in both syntaxes, each finding naming BT-128, not an element, and a second one of the type code `130` dropped; a description and location in BT-128's document ignored without a finding, in both syntaxes; a VAT point date (BT-7) in both syntaxes and in a UBL credit note, a CII one in the second VAT breakdown, a second one dropped, and one not written as `YYYYMMDD` with `format="102"` (missing, one `HAFL-VALUE`); each CII VAT point date code read as EN 16931's, EN 16931's own in CII and another one read as they are, and KoSIT's technical case 01.02 to the same code in both syntaxes; a CII code repeated in a second VAT breakdown read without a finding, and a differing one dropped; a UBL `cac:InvoicePeriod` holding only BT-8 read as BT-8, not as the invoicing period, and a second BT-8 dropped; a line with every term of BT-127 and BG-26 to BG-31 the model holds in both syntaxes, and a credit note's in UBL; a line's allowances and charges with every term in both syntaxes, and in a UBL credit note, in document order, with indicators `1`, `0` and one that is neither (left out, one `HAFL-DROPPED`), a VAT category in one not read, and the allowance of a UBL line's price read as the price discount, not as a line allowance; KoSIT case 01.01a's item classification in both syntaxes; two item classifications, one with a scheme version and one without, and a country of origin, in both syntaxes; a classification without a scheme read without one, and one holding only its scheme not read, in both syntaxes; a second country of origin dropped, and a classification and a country of origin holding an element (missing, one `HAFL-VALUE` each), in both syntaxes; a UBL credit note's classification and country of origin; two item attributes in both syntaxes, in document order, and a UBL credit note's; an attribute with only a name, one with only a value, and one holding neither, in both syntaxes, the official rules or UBL's XML Schema reporting the first two; a CII attribute's `ram:TypeCode` and `ram:ValueMeasure` dropped; an attribute's second value dropped, in both syntaxes; a line period with only a start and with only an end, in both syntaxes; a UBL line's `cac:InvoicePeriod` holding only a term the model doesn't read before the one holding its terms, and a second one holding a start dropped; a CII base quantity in the gross price alone, in the net price alone, and in both, the same, differing in value or in unit (the gross price's dropped), with a unit on one of them only, and the gross price's not an `xs:decimal`; a charge on the price, a price allowance whose indicator is neither, and a second price allowance, dropped in both syntaxes, a CII price allowance without an indicator read, and one with an empty indicator dropped; a price allowance without an amount before one with an amount, in both syntaxes; a CII gross price without a discount; a standard identifier without a scheme; a CII type code and a UBL tax scheme `vat` read as VAT, and a UBL tax scheme of another tax after an empty one left out; BT-110, BT-31 and a UBL note whose element holds an element (missing, one `HAFL-VALUE` each); a multi-line UBL note with `#AAI#`; for each group read from one element (postal address, contact, legal organisation or entity, BG-29, BG-30, BG-31) and for the VAT identifier, the tax registration identifier, the electronic address and the buyer identifier, in both syntaxes, a second one dropped with a finding naming its term; seller identifiers with and without scheme, in both syntaxes, and a UBL seller identifier with scheme `SEPA` left out; a CII contact with a department name alone, and with a department name beside a person name; the identifiers in the model's order from UBL and CII, a buyer's identifier with a scheme read before one without, and a CII `ram:GlobalID` without `schemeID` left out; a contact element holding only a fax number before the contact; a payment means repeated for a second account, with its text repeated, read as one with two credit transfers, and one with another means code dropped with what it holds, in both syntaxes; a CII account as `ram:ProprietaryID`, and as `ram:IBANID` beside a `ram:ProprietaryID`; a card, a direct debit and the creditor identifier in both syntaxes, the UBL payee's before the seller's, which is dropped, and a UBL creditor identifier without a mandate dropped; an invoice without payment means; two preceding invoices in UBL, with and without a date, and a reference holding neither term in both syntaxes; delivery information and invoicing period in both syntaxes, a deliver to location with and without scheme; allowances and charges in both syntaxes, with every term, and indicators `1`, `0` and one that is neither (left out, one `HAFL-DROPPED`), and a UBL line's `cac:AllowanceCharge` not read as the invoice's; a UBL `cac:Delivery` and `cac:InvoicePeriod` holding none of their group's terms before the ones that hold them; a second UBL `cac:Delivery` dropped; a repeated payment means with another text or remittance information keeping its account; a CII BIC without an account dropped; a UBL `cac:TaxTotal` in the VAT accounting currency before the one in the invoice currency; an empty invoice line.

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
- The library bounds the time of looking for the invoice in a PDF, not the time of reading the XML, which grows with its size (REQ-003-PRS-NF002). The bound on PDFs works within the thread: pypdf is pure Python, and a profile function that Python calls on every function call raises once the time is up. A caller that reads outside input still runs it where a time limit applies, such as a background job with a timeout ([ITEM-003](../backlog/item-003-erpnext-app.md)); validation has its own time limit ([REQ-002-PRS-NF004](req-002-conformance.md#req-002-prs-nf004-time-limit)).

## Open Questions

None at present.
