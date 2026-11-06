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

The spikes compared what KoSIT's reading stylesheet makes of the CII and UBL file of each business case, over every business term in them, in the KoSIT test suite `v2026-08-31`. Apart from differences in the files themselves, both agree. Those differences, with the technical cases' found by Haflinger's reading in the rebuild, and limits of KoSIT's reading stylesheet itself (the last six rows):

| Business term | Cases | Difference | Report? |
| :- | :- | :- | :- |
| BT-107, BT-108, BT-113, BT-114 | 6 | CII writes 0, UBL leaves the sum out | No: the standard allows both ([REQ-003-PRS-F004](../specs/req-003-incoming-invoices.md#req-003-prs-f004-cii-and-ubl-agree)) |
| BT-35, BT-37 | 01.20a | Different placeholder texts in the seller's address | No: placeholders |
| BT-37, BT-38, BT-52, BT-53 | 03.06a | The UBL file swaps city and post code | Yes |
| BT-13 | 7 | Only the UBL files have a purchase order reference (`Dummywert`) | Ask whether it is deliberate |
| BT-31, BT-82, BT-120 | 01.21a | Different values (BT-107 too, but as 0 against absent, which the standard allows) | Yes |
| BT-45 | 03.01a | Only in UBL | Yes |
| BT-29, BT-61, BT-122 | 03.07a | Only in one of the two files; BT-29 also in technical 01.01 and CVD 02.01a, three seller identifiers in CII and one in UBL | Yes |
| BT-41 | technical 01.03, 01.04 | The department name Testorganisation in CII, the person Tim Tester in UBL | Yes |
| BT-44, BT-45 | technical 01.01 to 01.04 | The UBL files swap the buyer's name and trading name placeholders | Yes |
| BT-149, BT-150 | technical 01.01 to 01.04 | Only the UBL files give the second line a base quantity (`1`, `XPP`) | Yes |
| BT-154 | CVD 02.01a | The first line's description: `Gruppe von Fahrzeugde XY der Klasse Z` in CII, `Gruppe von Fahrzeug XY der Klasse Z` in UBL | Yes |
| BT-110 | technical 01.05 | Absent in CII, 0 in UBL | No: the term is optional, and UBL's `cac:TaxTotal` needs an amount |
| BT-84 | ZUGFeRD corpus, `MustangGnuaccountingBeispielRE-20190610_507.pdf` | KoSIT's reading stylesheet gives a CII account with both `ram:IBANID` and `ram:ProprietaryID` as two BT-84, the proprietary one first, where EN 16931 allows one; Haflinger reads the IBAN (REQ-003-PRS-F002), and its tests' KoSIT reader prefers the one from `ram:IBANID` | Ask: the two elements give one account in two forms |
| BT-41, BT-56 | none in the suite | KoSIT's reading stylesheet gives two contact points for a CII contact with both a person and a department name, where EN 16931 allows one; Haflinger reads the person name (REQ-003-PRS-F002) | No: CEN's `CII-SR-465` and `CII-SR-466` already warn against such an input |
| BG-20, BG-21 | none in the suite | KoSIT's reading stylesheet takes an allowance or charge only where its charge indicator is the text `true` or `false`, so one written `1` or `0`, which `xs:boolean` and EN 16931's own rules allow, is neither; Haflinger reads all four (REQ-003-PRS-F002) | No: XRechnung, which the stylesheet is made for, forbids such values (`PEPPOL-EN16931-R043`) |
| BG-20, BG-21 | none in the suite | KoSIT's reading stylesheet compares the charge indicator with `true` and `false` as written, so one with whitespace around it, such as a line feed after `false`, is neither, although XRechnung allows it (`PEPPOL-EN16931-R043` compares after `normalize-space`); Haflinger removes the whitespace, as from any value (REQ-003-PRS-F002) | Yes |
| BT-147 | ZUGFeRD corpus, Mustang's `testout-ZF2PushItemChargesAllowances.xml` and `testout-ZF2PushRelativeChargesAllowances.xml` | KoSIT's reading stylesheet takes any CII `ram:AppliedTradeAllowanceCharge` of the gross price as the price discount, a charge too, which Factur-X EXTENDED allows; Haflinger leaves a charge out (REQ-003-PRS-F002) | No: EN 16931 has no charge on a price, and CEN's `CII-SR-119` warns of one |
| BT-149, BT-150 | none in the suite | KoSIT's reading stylesheet takes a CII line's base quantity and its unit from the gross price where both prices give one; Haflinger takes the net price's, to which the net price (BT-146) applies, and leaves a differing gross one out (REQ-003-PRS-F002) | No: XRechnung, which the stylesheet is made for, requires both to be the same (`BR-TMP-3`) |

## Open Questions

- Do the differences still exist in the release vendored with the rebuild ([ITEM-002](item-002-official-test-material.md))? Check against it before reporting, and search KoSIT's tracker for existing reports.
