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
- rendering the readable PDF of an outgoing invoice with ERPNext's print formats, as PDF/A, which the library then turns into a ZUGFeRD PDF; `embed` refuses a PDF that isn't PDF/A ([REQ-004-PRS-F007](../specs/req-004-outgoing-invoices.md#req-004-prs-f007-zugferd-pdf); [PDF/A from ERPNext](#pdfa-from-erpnext));
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

## PDF/A from ERPNext

Measured on 2026-11-20 with ERPNext 16.55.0 and Frappe 16.56.0 (the image `frappe/erpnext:v16.55.0`), on a sales invoice of `Example GmbH` in a throwaway site without network access:

- Frappe has no PDF/A setting. Its generators are wkhtmltopdf, Chromium (the default of a new site and of ERPNext's builder formats, such as "Sales Invoice Classic"; Frappe downloads `chrome-headless-shell` into the bench on first use), PlutoPrint (not installed), Typst and WeasyPrint. Neither wkhtmltopdf nor Chromium writes PDF/A; Typst refuses a builder format holding an HTML block or a letterhead with HTML, as "Sales Invoice Classic" does.
- Ghostscript 10.05.1 converted Chromium's PDFs of "Sales Invoice Classic" and "Standard", and wkhtmltopdf's of "Standard", to PDF/A-3b, with European e-Invoice's command (`gs -dPDFA=3 -dPDFACompatibilityPolicy=2 -sColorConversionStrategy=RGB … PDFA_def.ps`). veraPDF passed each, `embed` took each, and veraPDF passed the ZUGFeRD PDFs. A conversion took 60 ms; the text read from the PDF was unchanged, and under 0.1 % of the rendered page's pixels differed, at the edges of the glyphs.
- WeasyPrint, which Frappe 16 keeps as a legacy renderer, writes PDF/A-3b itself (`pdf_variant="pdf/a-3b"`) from the same HTML, and veraPDF passed it. But `embed` refused it: the `id` attributes of ERPNext's HTML become named destinations (`/Names /Dests`), which `factur-x` would drop. Its layout also differs from the browser's preview, which Chromium's matches.

So the app prints with ERPNext's own generator, converts the PDF with Ghostscript, as European e-Invoice does (at commit `797acf2`, 2026-11-16), and then calls `embed`. Where Ghostscript is missing or fails, European e-Invoice embeds the XML into the unconverted PDF and only logs an error; the app instead sends the invoice as XML, which is the e-invoice, and says why. The app may start with XML alone and add the ZUGFeRD PDF later.

What Ghostscript costs:

- Its licence is AGPL-3.0. The app calls it as a separate program and doesn't ship it: it names Ghostscript as a system requirement, and whoever distributes Ghostscript, for example in a Docker image, carries its obligations.
- It is a system package, missing from the image `frappe/erpnext`: a Docker setup builds its own image.
- Its interpreter has had many security holes. Here it reads only the company's own PDF, with `-dSAFER`, its default, kept on.
- Its output can change between versions: the app's tests check the result with veraPDF, and `embed` refuses a PDF that doesn't declare PDF/A.
- Not yet tried: invoices with a logo, images or several pages.

## Open Questions

- Where does it run (the ADR above)?
- The German checks beyond the official rules (§14(4) UStG content such as BT-32, BT-72 or BG-14): an optional rule set of Haflinger's own in the library, with findings of their own, for incoming and outgoing invoices and testable without ERPNext; or in the app, as listed above? Either way, each rule cites its paragraph and the date it was last checked, and a tax adviser reviews the set before it is relied on.
- Which of its needs are requirements on the library, for REQ-001 to REQ-004, and which are the app's own, for its specs ([ADR-004](../arc42/adr/ADR-004-specs-by-direction.md))?
- Which profile does an ERPNext invoice get by default: XRechnung for public buyers, ZUGFeRD EN 16931 otherwise?
- The delivery date (BT-72) when ERPNext has none: write the invoice date, as European e-Invoice does (§14(4) UStG allows a delivery date equal to the invoice date, but the invoice then states a date nobody entered), or require a real one?
- Can a hosted bench, such as Frappe Cloud, install Ghostscript ([PDF/A from ERPNext](#pdfa-from-erpnext))?
- May the GPL-3.0 app be published while Haflinger requires `saxonche`? To settle before publishing it ([ITEM-008](item-008-saxonche-licence.md)).
