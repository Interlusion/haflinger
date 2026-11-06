# ITEM-006: Report the differences found in the official files

| Meta | Value |
| :- | :- |
| **Status** | CANDIDATE |
| **Type** | chore |
| **Origin** | KoSIT spike of 2026-10-30; [REQ-002-PRS-F008](../specs/req-002-conformance.md#req-002-prs-f008-differences-in-the-official-files) |
| **Created** | 2026-10-31 |
| **Author** | loxy (drafted with Claude) |

## Summary

Report upstream the differences between the CII and UBL files of the KoSIT test suite that the spikes found, as the [development guide](../guides/development.md#tests) describes, and link each report in the test's record of the difference.

## Context / Motivation

The spikes compared what KoSIT's reading stylesheet makes of the CII and UBL file of each business case, over every business term in them, in the KoSIT test suite `v2026-08-31`. Apart from differences in the files themselves, both agree. Those differences, with the technical cases' found by Haflinger's reading in the rebuild, and limits of KoSIT's reading stylesheet itself (the last ten rows):

| Business term | Cases | Difference | Report? |
| :- | :- | :- | :- |
| BT-107, BT-108, BT-113, BT-114 | 6 | CII writes 0, UBL leaves the sum out | No: the standard allows both ([REQ-003-PRS-F004](../specs/req-003-incoming-invoices.md#req-003-prs-f004-cii-and-ubl-agree)) |
| BT-35, BT-37 | 01.20a | Different placeholder texts in the seller's address | No: placeholders |
| BT-37, BT-38, BT-52, BT-53 | 03.06a | The UBL file swaps city and post code | Yes |
| BT-13 | 7 | Only the UBL files have a purchase order reference (`Dummywert`) | Ask whether it is deliberate |
| BT-31, BT-82, BT-120 | 01.21a | Different values (BT-107 too, but as 0 against absent, which the standard allows) | Yes |
| BT-45 | 03.01a | Only in UBL | Yes |
| BT-29, BT-61 | 03.07a | Only in one of the two files; BT-29 also in technical 01.01 and CVD 02.01a, three seller identifiers in CII and one in UBL; BT-61, the payee's legal registration identifier, only in CII, also in technical 01.01 to 01.04 and CVD 02.01a | Yes |
| BT-41 | technical 01.03, 01.04 | The department name Testorganisation in CII, the person Tim Tester in UBL | Yes |
| BT-44, BT-45 | technical 01.01 to 01.04 | The UBL files swap the buyer's name and trading name placeholders | Yes |
| BT-149, BT-150 | technical 01.01 to 01.04 | Only the UBL files give the second line a base quantity (`1`, `XPP`) | Yes |
| BT-154 | CVD 02.01a | The first line's description: `Gruppe von Fahrzeugde XY der Klasse Z` in CII, `Gruppe von Fahrzeug XY der Klasse Z` in UBL | Yes |
| BT-110 | technical 01.05 | Absent in CII, 0 in UBL | No: the term is optional, and UBL's `cac:TaxTotal` needs an amount |
| BT-84 | ZUGFeRD corpus, `MustangGnuaccountingBeispielRE-20190610_507.pdf` | KoSIT's reading stylesheet gives a CII account with both `ram:IBANID` and `ram:ProprietaryID` as two BT-84, the proprietary one first, where EN 16931 allows one; Haflinger reads the IBAN (REQ-003-PRS-F002), and its tests' KoSIT reader prefers the one from `ram:IBANID` | Ask: the two elements give one account in two forms |
| BT-41, BT-56 | none in the suite; ZUGFeRD corpus, the four XRechnung samples in `XML-Rechnung/`, as XML and as PDF, and four of symtrax's EN 16931 samples | KoSIT's reading stylesheet gives two contact points for a CII contact with both a person and a department name, where EN 16931 allows one; Haflinger reads the person name (REQ-003-PRS-F002) | No: CEN's `CII-SR-465` and `CII-SR-466` already warn against such an input |
| BG-20, BG-21 | none in the suite | KoSIT's reading stylesheet takes an allowance or charge only where its charge indicator is the text `true` or `false`, so one written `1` or `0`, which `xs:boolean` and EN 16931's own rules allow, is neither; Haflinger reads all four (REQ-003-PRS-F002) | No: XRechnung, which the stylesheet is made for, forbids such values (`PEPPOL-EN16931-R043`) |
| BG-20, BG-21 | none in the suite | KoSIT's reading stylesheet compares the charge indicator with `true` and `false` as written, so one with whitespace around it, such as a line feed after `false`, is neither, although XRechnung allows it (`PEPPOL-EN16931-R043` compares after `normalize-space`); Haflinger removes the whitespace, as from any value (REQ-003-PRS-F002) | Yes |
| BT-147 | ZUGFeRD corpus, Mustang's `testout-ZF2PushItemChargesAllowances.xml` and `testout-ZF2PushRelativeChargesAllowances.xml` | KoSIT's reading stylesheet takes any CII `ram:AppliedTradeAllowanceCharge` of the gross price as the price discount, a charge too, which Factur-X EXTENDED allows; Haflinger leaves a charge out (REQ-003-PRS-F002) | No: EN 16931 has no charge on a price, and CEN's `CII-SR-119` warns of one |
| BT-149, BT-150 | none in the suite | KoSIT's reading stylesheet takes a CII line's base quantity and its unit from the gross price where both prices give one; Haflinger takes the net price's, to which the net price (BT-146) applies, and leaves a differing gross one out (REQ-003-PRS-F002) | No: XRechnung, which the stylesheet is made for, requires both to be the same (`BR-TMP-3`) |
| BT-83 | ZUGFeRD corpus, seven of Mustang's `testout-ZF2Push*.xml` and FNFE-MPE's five `Avoir_FR_*` | KoSIT's reading stylesheet gives the payment instructions (BG-16) only within a CII `ram:SpecifiedTradeSettlementPaymentMeans`, so the remittance information (`ram:PaymentReference`) of an invoice without one is lost; Haflinger reads it (REQ-003-PRS-F002) | No: XRechnung, which the stylesheet is made for, requires a payment means (`BR-DE-1`) |
| BT-9, BT-20 | ZUGFeRD corpus, intarsys's and symtrax's `EXTENDED_Fremdwaehrung` | KoSIT's reading stylesheet joins a CII invoice's two due dates into one value and its two payment terms into one text, separated by `;`, where EN 16931 holds one of each; Haflinger reads the first and leaves the second out with a finding (REQ-003-PRS-F002) | No: only Factur-X EXTENDED allows more than one |
| BT-18-1 | ZUGFeRD corpus, `XML-Rechnung/CII/not_validating_full_invoice_based_onTest_EeISI_300_CENfullmodel.cii.xml` | KoSIT's reading stylesheet gives the scheme of a CII invoiced object identifier, `ram:ReferenceTypeCode`, only where its `ram:IssuerAssignedID` has a `schemeID` too (the template `identifier-with-scheme` in `common-xr.xsl` tests `@schemeID`), so the scheme is lost; Haflinger reads it (REQ-003-PRS-F002) | Yes: EN 16931 binds BT-18-1 to `ram:ReferenceTypeCode`, which XRechnung allows |
| BT-11, BT-18, BG-24 | none in the suite | KoSIT's reading stylesheets compare document type codes as written: a UBL credit note's with 50 as a number, so `050` or `50.0` gives the project reference, the others as text, so a UBL `130` or a CII `916` with whitespace around it isn't BT-18's or gives no BT-122; Haflinger compares a code as written without the whitespace around it, so a credit note's `050` is a supporting document (REQ-003-PRS-F002) | Yes, for the whitespace, which CEN's rules remove before comparing a type code (`normalize-space`, as in `CII-SR-475`); no for `050` and `50.0`, which are no codes of UNTDID 1001 |
| BT-63 | none in the suite | KoSIT's reading stylesheet takes every CII `ram:SpecifiedTaxRegistration/ram:ID` of the tax representative as BT-63, whatever its `schemeID`; Haflinger reads the one with `VA` or without a scheme and leaves one with another scheme out (REQ-003-PRS-F002) | No: CEN's `BR-56` counts only one with `VA`, so such an invoice isn't valid |
| BG-24 | 03.07a, technical 01.01 to 01.04, CVD 02.01a | KoSIT's stylesheets give BT-17's and BT-18's additional documents as supporting documents too: the UBL ones always, BT-18's (type code `130`) with its `cbc:ID` as BT-122, so the UBL file seems to hold a supporting document the CII file doesn't; the CII ones where they hold a description or location. Haflinger reads them as BT-17 and BT-18 alone and leaves a description or location in them out with a finding (REQ-003-PRS-F002); the tests' second reader leaves those supporting documents out | Yes: the stylesheets' own comment on the line's document reference says code `130` is not used for other additional documents |
| BG-24 | none in the suite | KoSIT's CII stylesheet gives every `ram:AdditionalReferencedDocument` as a supporting document, with BT-122 only where its type code is `916`, so one of another type code, or without one, holding a description, location or attachment is a supporting document without its reference; Haflinger leaves it out, with a finding where it holds a reference, description or location (REQ-003-PRS-F002) | No: EN 16931-3-3 binds BG-24 to the type code `916`, and `BR-52` requires BT-122 |
| BT-123 | 03.07a | CEN's rule `CII-SR-475` (a warning) allows one description (`ram:Name`) among all the supporting documents of a CII invoice, where EN 16931 gives each supporting document one (BT-123 in BG-24), so 03.07a's CII file, with two, and every invoice Haflinger writes with two descriptions get the warning; a test notices once a release counts them per document | Yes, to CEN |

## Open Questions

- Do the differences still exist in the release vendored with the rebuild ([ITEM-002](item-002-official-test-material.md))? Check against it before reporting, and search KoSIT's tracker for existing reports.
