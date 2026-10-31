# ITEM-005: Rendering invoices for people

| Meta | Value |
| :- | :- |
| **Status** | IDEA |
| **Type** | feature |
| **Origin** | Approach review and KoSIT XSLT spike of 2026-10-30 |
| **Created** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Summary

Show an incoming XML invoice to a person as HTML or PDF with KoSIT's visualisation stylesheets, which Haflinger will vendor for its second reader ([ADR-005](../arc42/adr/ADR-005-own-mapping-kosit-as-check.md)).

## Context / Motivation

An XML invoice is the legal document, but people need a readable view to check and book it, and archiving rules (GoBD) expect it to be readable. KoSIT publishes the reference rendering, maintained with every XRechnung release ([ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md)).

Rendering outside input is a security surface: KoSIT's release of 2026-10-13 fixed script injection through attachment file names (BT-122, BT-125). Rendering needs the current release, and HTML output needs to be shown without running scripts.

## Open Questions

- In the library or in the app: the stylesheets are format knowledge ([ADR-001](../arc42/adr/ADR-001-library-and-app.md)), the display is the caller's.
- HTML only, or also PDF (KoSIT's PDF route needs an XSL-FO processor)?
- Does it cover ZUGFeRD profiles beyond EN 16931, such as EXTENDED?
