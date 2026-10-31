# ITEM-004: Checks of the PDF itself

| Meta | Value |
| :- | :- |
| **Status** | IDEA |
| **Type** | feature |
| **Origin** | ZUGFeRD corpus spike of 2026-10-30; review of the specs of 2026-10-30 |
| **Created** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Summary

Check an incoming ZUGFeRD PDF beyond its XML: PDF/A-3 conformance, the embedded file's name and relationship, and the XMP metadata naming profile and version, to report a faulty container to the operator. Outgoing PDFs are settled: `embed` takes only PDF/A input, and veraPDF checks its results in the tests ([REQ-004-PRS-F007](../specs/req-004-outgoing-invoices.md#req-004-prs-f007-zugferd-pdf)).

## Context / Motivation

Four files in the ZUGFeRD corpus's `fail/` folders passed every XML check: their faults were in the PDF (a wrong embedded file name, PDF/A or metadata problems). Nothing in Haflinger checks these. `factur-x` writes conformant metadata when it embeds, and produces PDF/A-3 only from PDF/A input; it doesn't verify a PDF. veraPDF is the reference validator for PDF/A; it is Java, so it can only be an oracle in the tests, not a runtime check.

## Open Questions

- Is a container check of incoming PDFs possible in Python without veraPDF, to the degree that matters (embedded file name, relationship, XMP)?
- Are findings about an incoming PDF's container worth showing to the operator, given that the law asks for the XML?
