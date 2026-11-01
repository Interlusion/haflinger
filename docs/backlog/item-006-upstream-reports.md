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

The spikes compared what KoSIT's reading stylesheet makes of the CII and UBL file of each business case, over every business term in them, in the KoSIT test suite `v2026-08-31`. Apart from differences in the files themselves, both agree. Those differences, with the technical cases' found by Haflinger's reading in the rebuild:

| Business term | Cases | Difference | Report? |
| :- | :- | :- | :- |
| BT-107, BT-108, BT-113, BT-114 | 6 | CII writes 0, UBL leaves the sum out | No: the standard allows both ([REQ-003-PRS-F004](../specs/req-003-incoming-invoices.md#req-003-prs-f004-cii-and-ubl-agree)) |
| BT-35, BT-37, BT-38, BT-52, BT-53 | 2 | Different placeholder texts in addresses | No: placeholders |
| BT-13 | 7 | Only the UBL files have a purchase order reference (`Dummywert`) | Ask whether it is deliberate |
| BT-31, BT-82, BT-120 | 01.21a | Different values (BT-107 too, but as 0 against absent, which the standard allows) | Yes |
| BT-45 | 03.01a | Only in UBL | Yes |
| BT-29, BT-61, BT-122 | 03.07a | Only in one of the two files | Yes |
| BT-44, BT-45 | technical 01.01 to 01.04 | The UBL files swap the buyer's name and trading name placeholders | Yes |
| BT-110 | technical 01.05 | Absent in CII, 0 in UBL | No: the term is optional, and UBL's `cac:TaxTotal` needs an amount |

## Open Questions

- Do the differences still exist in the release vendored with the rebuild ([ITEM-002](item-002-official-test-material.md))? Check against it before reporting, and search KoSIT's tracker for existing reports.
