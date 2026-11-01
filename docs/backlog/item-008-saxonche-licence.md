# ITEM-008: saxonche's licence beside the GPL-3.0 ERPNext app

| Meta | Value |
| :- | :- |
| **Status** | CANDIDATE |
| **Type** | question |
| **Origin** | Check of what blocks the ERPNext app, 2026-11-01 |
| **Created** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Summary

Find out whether the ERPNext app, GPL-3.0 because it imports ERPNext ([ADR-009](../arc42/adr/ADR-009-licences-and-name.md)), may use Haflinger while Haflinger depends on `saxonche`, whose files are mostly marked "Incompatible With Secondary Licenses" under MPL-2.0. Settle it before the app is written ([ITEM-003](item-003-erpnext-app.md)), and before Haflinger's first release, which ADR-009 already asks for the licence of `saxonche`.

## Context / Motivation

What is known (2026-11-01):

- Saxonica: "The product SaxonC-HE is open-source. The primary license is the Mozilla Public License version 2.0." Some components are Apache-2.0 or BSD-style; "All SaxonC editions currently ship with GraalVM Community Edition."
- Saxonica: "In most cases, the source files are marked as being 'incompatible with secondary licenses'", which, in Saxonica's words, means the code can't be combined with GPL-licensed code.
- The `saxonche` wheel (13.1.1) holds no licence file, and its metadata names no licence.
- MPL-2.0 is file-based: it doesn't extend to code that merely uses the MPL files. A file marked "Incompatible With Secondary Licenses" can't be relicensed under the GPL as part of a larger work.
- Haflinger is Apache-2.0 and only declares `saxonche` as a dependency; it ships none of its files. The app would import Haflinger, which loads `saxonche` at run time; the user installs all of them separately into a bench.
- Without `saxonche`, incoming invoices can't be validated with the official rules ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md)); KoSIT's validator (Java) would bring the JVM the ADRs avoid.

## Open Questions

- Does a GPL-3.0 app that imports, at run time, an independently installed MPL-2.0 package marked "Incompatible With Secondary Licenses" form a combined work the GPL governs, and is that combination allowed? To ask Saxonica, and if needed a lawyer.
- Which notices does redistributing `saxonche` require, for example in a Docker image of a bench, and what are GraalVM Community Edition's terms inside it?
- If the combination isn't allowed: validation in a separate process or service that the app talks to over a boundary the GPL doesn't cross, or another XSLT 3 engine ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md), trigger 2).
