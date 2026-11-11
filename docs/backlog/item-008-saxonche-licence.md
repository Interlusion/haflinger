# ITEM-008: saxonche's licence beside the GPL-3.0 ERPNext app

| Meta | Value |
| :- | :- |
| **Status** | CANDIDATE |
| **Type** | question |
| **Origin** | Check of what blocks the ERPNext app, 2026-11-01 |
| **Created** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Summary

Find out whether the ERPNext app, GPL-3.0 because it imports ERPNext ([ADR-009](../arc42/adr/ADR-009-licences-and-name.md)), may use Haflinger while Haflinger depends on `saxonche`, whose files are mostly marked "Incompatible With Secondary Licenses" under MPL-2.0. Settle it before the app is published ([ITEM-003](item-003-erpnext-app.md)). It doesn't block Haflinger's releases, which ship none of Saxon's files ([ADR-009](../arc42/adr/ADR-009-licences-and-name.md)).

## Context / Motivation

What is known (2026-11-01):

- Saxonica, on its SaxonC page: "The product SaxonC-HE is open-source. The primary license is the Mozilla Public License version 2.0." Some components are Apache-2.0 or BSD-style; SaxonC 13 is "built from GraalVM Community Edition."
- Saxonica, on the same page: "In most cases, the source files are marked as being "incompatible with secondary licenses", which means that the code cannot be combined with code issued under a GPL license (the reason for this is the difficulty of contacting all past contributors to gain their assent)." An extra permission for GPL code may therefore not be Saxonica's alone to give.
- Saxonica, in the licensing section of the Saxon 13 documentation, which covers SaxonC unless it says otherwise: "Saxon code, in general, is NOT compatible with secondary licenses. This means it is not possible to redistribute the source code under a different license." That reads narrower than the SaxonC page. The same section, on redistribution: "you are not required to publish the source of your own application code if it is in separate modules"; and it asks a product that "includes or requires" Saxon to name it "The Saxon XSLT and XQuery Processor from Saxonica Limited", with `https://www.saxonica.com/`, which Haflinger's README does.
- MPL-2.0 is file-based: it doesn't extend to code that merely uses the MPL files. Its compatibility with the GPL comes from section 3.3, the "secondary licenses", which the marking switches off. The SPDX identifier of such files is `MPL-2.0-no-copyleft-exception`, not `MPL-2.0`.
- The `saxonche` wheel (13.1.1) holds no licence file and no notices, only the extension, two shared libraries and `saxonc.cpp`, and its metadata names no licence, so tools that scan licences (SBOMs, compliance checks) see nothing. Saxonica's documentation says the notices that third-party components require are "in the notices directory of the Saxon product as distributed", which the wheel lacks.
- Haflinger is Apache-2.0 and only declares `saxonche` as a dependency; it ships none of its files. KoSIT's validator, Apache-2.0, ships Saxon-HE likewise and names it in its notices. Apache-2.0 beside MPL-2.0 is not in question.
- The app would import Haflinger, which loads `saxonche` at run time in the same process; the user installs all of them separately into a bench. The Free Software Foundation counts libraries loaded into one process and called with shared data as one combined program; separate processes that talk over pipes, sockets or command lines usually as separate programs, depending on what they exchange.
- GPL-3.0 governs conveying, not running: "You are not required to accept this License in order to receive or run a copy of the Program" (section 9). A company that runs ERPNext, the app and `saxonche` on its own servers conveys nothing. The question arises when the app is published, for example on the Frappe Marketplace, and when someone conveys an image or installer that holds all of them.
- A precedent in the same field: `factur-x`, which Haflinger uses to embed XML into PDFs, added `saxonche` in release 4.0 (2026-03-18) and dropped it in 6.0 (2026-07-08) for an HTTP call to a separate Saxon server, citing its bug #77: with `saxonche` 13.0.0 inside Odoo, the process aborted with "Failed to enter the specified IsolateThread context". That was about stability, not the licence, but it shows Saxon moved out of the ERP's process. Haflinger calls `factur-x` with its Schematron check off, so no such request is made.
- Without `saxonche`, incoming invoices can't be validated with the official rules ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md)). KoSIT's validator (Java) would bring the JVM the ADRs avoid. No other engine runs the official rules today: Xee (MIT) has, by its own account, partial XSLT and no Python binding, while KoSIT's compiled rules rely throughout on `xsl:next-match` (598 uses), template parameters (about 600 `xsl:with-param`), modes and `xsl:function`, and SchXslt adds `xsl:import`, `xsl:include`, `xsl:for-each-group` and `xsl:sort` (counted on 2026-11-01); pyschematron is GPL-3.0 and interprets Schematron instead of running the official stylesheets ([ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md)).

## Options

- **Saxon in the app's process**, as today: allowed only if a lawyer says that importing an independently installed `saxonche` doesn't form a combined work. Saxonica gives no extra permission (see below).
- **Validation in a separate process** that the app starts or calls, with invoice bytes in and findings out: an Apache-2.0 Haflinger worker that loads `saxonche`, while the app's process never does. It is the same boundary [ITEM-007](archive/item-007-validation-time-limit.md) needs for a time limit, and a crash of Saxon wouldn't take the app's process down. Saxonica left open whether it suffices legally.
- **Another engine** ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md), trigger 2): Xee, once it runs the official rules with the same findings as Saxon, Saxon serving as the oracle in CI.
- **A commercial licence** for Saxon-PE or Saxon-EE, which Saxonica offers for redistribution: it fits a closed product, not a GPL-3.0 app given away, whose users would each need a licence and whose combination with proprietary code the GPL doesn't allow either.

## Saxonica's answer

Asked on Saxonica's SaxonC tracker; Michael Kay answered on 2026-11-02:

- On the in-process case: "We can't give you an answer to that question. We are not lawyers." In his personal view, "the language of the GPL makes no technical sense", and he has "no idea how the courts would interpret it".
- On notices: the open-source components of SaxonJ and their licences are listed in the licensing section of the Saxon 13 documentation, and "most of these components are also used in SaxonC". That section sorts Saxon's code into Saxon's own (MPL-2.0), code taken in from other products under MPL-, Apache- or BSD-style licences, and components redistributed unchanged in binary form, whose notices it lists. "Many of the licenses require you to include a copy of the license with your distribution."
- On an extra permission: none; Saxonica offers "a license that you may find more suitable to your needs, but it costs money", a redistribution licence for Saxon-PE or Saxon-EE. "If you want to use the open source product and license, then I'm afraid you have to take it as it comes."
- The case of a separate process wasn't answered.

So Saxonica neither allows nor forbids the in-process combination, and won't widen the licence. Running ERPNext, the app and `saxonche` on one's own servers stays unaffected (GPL-3.0 section 9); publishing the app with Saxon in its process would rest on an untested reading of the GPL.

## Open Questions

- [ADR-010](../arc42/adr/ADR-010-saxon-in-a-worker-process.md) puts Saxon into a worker process that Haflinger starts, so that no caller's process, the app's included, loads `saxonche`; built on 2026-11-02 (REQ-002-PRS-NF005). A lawyer should still confirm that the boundary suffices before the app is published.
- Which licence texts and notices an image or installer that holds `saxonche` must carry, since the wheel brings none: the lists in the Saxon 13 documentation, checked against the components in the wheel, GraalVM Community Edition's among them.

Also open: whether the app must be GPL-3.0 at all, if it used only the Frappe Framework (MIT) and none of ERPNext's code; the app works on ERPNext's sales and purchase invoices ([ITEM-003](item-003-erpnext-app.md)), so it would import ERPNext.
