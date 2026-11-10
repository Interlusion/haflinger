# ITEM-003: The ERPNext side

| Meta | Value |
| :- | :- |
| **Status** | IDEA |
| **Type** | feature |
| **Origin** | [ADR-001](../arc42/adr/ADR-001-library-and-app.md); approach review of 2026-10-30 |
| **Created** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Summary

Bring the library into ERPNext: outgoing sales invoices written as XRechnung or ZUGFeRD, incoming invoices read and turned into purchase invoice drafts a person reviews. First an ADR on where this runs: a Frappe app, tools of another system, or a separate service, per feature. The app is GPL-3.0 in its own repository ([ADR-009](../arc42/adr/ADR-009-licences-and-name.md)).

## Context / Motivation

What only the ERPNext side can do, and no standards body maintains ([ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md)):

- the mapping between ERPNext documents and the model: taxes, Skonto, rounding;
- matching incoming invoices to suppliers, items and accounts, and the review flow;
- rendering the readable PDF of an outgoing invoice with ERPNext's print formats, as PDF/A, which the library then turns into a ZUGFeRD PDF; `embed` refuses a PDF that isn't PDF/A ([REQ-004-PRS-F007](../specs/req-004-outgoing-invoices.md#req-004-prs-f007-zugferd-pdf));
- completeness under German VAT law beyond the official rules: the seller's tax number (BT-32) when no VAT identifier is given and the delivery date (BT-72) or invoicing period (BG-14), §14(4) UStG; no official rule enforces them, so `write_cii` hands out an invoice without them ([REQ-004](../specs/req-004-outgoing-invoices.md));
- further German specifics, for example a note on cash-basis taxation, if it becomes required;
- archiving the original invoice unchanged (GoBD);
- safety with incoming files, where a person or a viewer meets them: virus scanning at intake (mail, upload), in the app or the infrastructure (for example ClamAV); PDFs offered as a download rather than rendered inline, or the invoice shown through KoSIT's visualisation of the XML ([ITEM-005](item-005-rendering.md)); attachments inside the XML (BT-125, which the library hands over as bytes) treated as untrusted, scanned, with their names cleaned before saving; reading incoming invoices in a background job with a timeout, because the library doesn't bound the time of reading ([REQ-003](../specs/req-003-incoming-invoices.md#assumptions)); validation has its own time limit ([REQ-002-PRS-NF004](../specs/req-002-conformance.md#req-002-prs-nf004-time-limit)), and with a `max_size` well below the default of 100 MB, for example 20 MB, because a crafted file takes many times its size in memory when it is read and validated.

ALYF's European e-Invoice app (`alyf-de/eu_einvoice`, GPL-3.0) is prior work the app may reuse, with attribution; nothing of it goes into the Apache-2.0 library:

- its ERPNext mapping: custom fields, tax rows, code lists mapped to tax categories, templates and accounts;
- its import doctype and the matching of suppliers and items;
- its Swiss specifics;
- its issue tracker, as a source of real user problems;
- its known bugs as regression tests for the app: Skonto never written, BT-114 never written, profile detection by exact string.

Its `main` branch targets Frappe/ERPNext 17-dev.

How it handles German content beyond the official rules (at commit `1385900`, 2026-10-31): by mapping, not by checks. The company's Tax ID is written as a VAT identifier (BT-31) when it is one, otherwise as a tax number (BT-32, `schemeID="FC"`); nothing checks that either is present. A delivery date (BT-72) is always written: the latest delivery date of the lines, else the end of the billing period, else the invoice date. The billing period (BG-14) comes from the invoice's from and to dates. Validation runs only the official rules, on outgoing invoices before submission and on imported ones; nothing checks German content in incoming invoices, and there is nothing on cash-basis taxation.

## Open Questions

- Where does it run (the ADR above)?
- The German checks beyond the official rules (§14(4) UStG content such as BT-32, BT-72 or BG-14): an optional rule set of Haflinger's own in the library, with findings of their own, for incoming and outgoing invoices and testable without ERPNext; or in the app, as listed above? Either way, each rule cites its paragraph and the date it was last checked, and a tax adviser reviews the set before it is relied on.
- Which of its needs are requirements on the library, for REQ-001 to REQ-004, and which are the app's own, for its specs ([ADR-004](../arc42/adr/ADR-004-specs-by-direction.md))?
- Which profile does an ERPNext invoice get by default: XRechnung for public buyers, ZUGFeRD EN 16931 otherwise?
- The delivery date (BT-72) when ERPNext has none: write the invoice date, as European e-Invoice does (§14(4) UStG allows a delivery date equal to the invoice date, but the invoice then states a date nobody entered), or require a real one?
- How does ERPNext produce PDF/A: a print-format setting, a different PDF generator, or a conversion step in the app?
