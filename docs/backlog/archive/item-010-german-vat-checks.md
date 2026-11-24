# ITEM-010: Checks of an invoice's content under German VAT law

| Meta | Value |
| :- | :- |
| **Status** | DONE on 2026-11-24: [ADR-014](../../arc42/adr/ADR-014-german-vat-checks.md) (Proposed), [REQ-002-PRS-F012](../../specs/req-002-conformance.md#req-002-prs-f012-the-german-vat-check) to REQ-002-PRS-F015: `check_german_vat`, KoSIT's German rules on any profile, with three rules of Haflinger's own |
| **Type** | feature |
| **Origin** | Requested by Haflinger Saddle (SADL-ITEM-001), 2026-11-20 |
| **Created** | 2026-11-20 |
| **Author** | loxy (drafted with Claude) |

## Summary

An optional check that a caller runs on an invoice under German VAT, incoming or outgoing, and that reports what §14(4) UStG requires and the rules `validate` runs don't check for that invoice: first the time of supply (§14(4) no. 6). It settles the open point of [ADR-003](../../arc42/adr/ADR-003-integrate-dont-implement.md#our-own-code), where these specifics live, for the library; the ERPNext app keeps filling the values from its documents.

## Context / Motivation

- **What the official rules check already.** CEN's EN 16931 rules run on every invoice and require the seller's VAT identifier (BT-31), tax number (BT-32) or tax representative's VAT identifier (BT-63) as soon as a line has one of the VAT categories S, Z, E, AE, K, G, L or M (`BR-S-02` and its siblings), which covers §14(4) no. 2 UStG but for an invoice that names the tax representative alone. KoSIT's German rules of XRechnung hold more: `BR-DE-16`, the VAT identifier or tax number; `BR-DE-TMP-32`, a warning where the invoice states neither the actual delivery date (BT-72), an invoicing period (BG-14) nor a period on every line (BG-26), the time of supply of no. 6; and `BR-DE-3`, `BR-DE-4`, `BR-DE-8` and `BR-DE-9`, city and post code of seller and buyer, part of no. 1 (all in XRechnung 3.0.2).
- **The gap.** KoSIT's German rules run only where BT-24 names XRechnung, which is the profile for public buyers. An invoice between businesses, ZUGFeRD's EN 16931 profile, gets CEN's rules alone, so `write_cii` hands it out without a time of supply ([REQ-004](../../specs/req-004-outgoing-invoices.md), Out of scope), and `validate` accepts an incoming one without it.
- **Incoming invoices need it most.** Input VAT is deductible only from an invoice issued under §§14 and 14a UStG (§15(1) no. 1). Whoever reviews a supplier's invoice needs to know that the time of supply is missing.
- **Why in the library, not the app.** One list of findings beside the official rules'; tested in seconds without ERPNext; maintained in one place as the law and KoSIT's rules change; and of use to every caller, not only Haflinger Saddle.
- **Not a profile, and not a mode.** §14 UStG applies to every invoice under German VAT, ZUGFeRD between businesses included. Reading, writing and `validate` stay as they are; the caller runs the check where German VAT applies and decides what a finding means. Haflinger Saddle plans to hold back an outgoing invoice with such a finding and to show it on an incoming one to the reviewer.
- **Small invoices.** An invoice of at most €250 including VAT needs less (§33 UStDV): neither the tax number nor the time of supply, nor the buyer; the rule doesn't apply to some supplies, such as intra-Community ones. KoSIT's rules don't know this limit.
- **Germany first, others later.** §14(4) UStG implements Article 226 of the EU VAT Directive, which every member state implements with its own details, such as the limit for small invoices. Only Germany is needed now; the design should take a second country as an addition.
- **Reviewed before relied on.** A tax adviser reviews what the check covers; Haflinger states what it checks, not that an invoice meets the law.

## Options

- **KoSIT's German rules on any invoice under German VAT**, as ADR-003 prefers: run XRechnung's stylesheet of the invoice's syntax on the XML, and keep the findings of the rules that §14(4) UStG asks for (`BR-DE-16`, `BR-DE-TMP-32`, `BR-DE-3`, `BR-DE-4`, `BR-DE-8`, `BR-DE-9`), leaving out those that only XRechnung asks for, such as the payment instructions (`BR-DE-1`), the seller's contact (`BR-DE-2`) and the buyer reference (`BR-DE-15`). The findings keep KoSIT's rule IDs and XPath locations, as `validate`'s do. KoSIT's rules don't know the limit for small invoices, so Haflinger would drop the findings of `BR-DE-16`, `BR-DE-TMP-32`, `BR-DE-8` and `BR-DE-9` itself for an invoice of at most €250 including VAT where §33 UStDV applies: a rule of its own, which makes this option the third. Open: whether running a stylesheet meant for XRechnung on another profile's invoice gives only these rules' findings, and how a selection of rule IDs is kept current with KoSIT's releases.
- **Rules of Haflinger's own on the model**: a function that takes the model and returns findings, before `write_cii` and after `read_invoice` alike. It needs rule IDs of its own (`HAFL-DE-…`?), listed in [REQ-002-PRS-F010](../../specs/req-002-conformance.md#req-002-prs-f010-haflingers-own-findings), and locations by business term, as a model has no XPath ([REQ-002-PRS-F002](../../specs/req-002-conformance.md#req-002-prs-f002-findings)); and it reimplements what KoSIT maintains.
- **Both**: KoSIT's rules for what they cover, and rules of Haflinger's own only for what they don't: the limit for small invoices, and whatever else is left.

## Open Questions

- Which of the options, decided in an ADR that updates ADR-003's open point; the requirements then go into REQ-002 (or a spec of their own, by the placement map).
- Which other items of §14(4) UStG neither rule set checks: for example the street of both parties (no. 1), where KoSIT asks for city and post code.
- How the check learns that German VAT applies: from the caller only, or also from the seller's country (BT-40) or VAT identifier?
