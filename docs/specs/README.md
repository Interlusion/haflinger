# Requirement Specifications

REQ-001 is the base spec: the personas, stories and terms, the model of the EN 16931 business terms, and the rules every other spec follows. REQ-002 holds conformance: the official artefacts and test files, the profiles, versions and editions, and validation. REQ-003 and REQ-004 hold the two directions an invoice travels. Every spec has an intended use, user stories, its requirement rules, user requirements (URS, what is needed), product requirements (PRS, what is built, each with a Definition of Done), acceptance criteria, assumptions and open questions (kept when empty), and always shows the current state.

| Spec | Area | Status |
| :- | :- | :- |
| [REQ-001](req-001-core.md) | Core: personas, stories and terms, the model, the rules every spec follows | Draft |
| [REQ-002](req-002-conformance.md) | Conformance: official artefacts and test files, profiles and versions, validation | Draft |
| [REQ-003](req-003-incoming-invoices.md) | Incoming invoices: reading CII, UBL and ZUGFeRD PDFs into the model | Draft |
| [REQ-004](req-004-outgoing-invoices.md) | Outgoing invoices: writing CII and ZUGFeRD PDFs from the model | Draft |

Why the specs are cut this way: [ADR-004](../arc42/adr/ADR-004-specs-by-direction.md).

## Reading and writing

- **For any task, read REQ-001 first**, then the spec the map below names.
- **Adopting a new release of KoSIT, CEN or FeRD, or adding a profile:** REQ-002.
- **A new business term:** REQ-001 for the model, then REQ-003 for reading it and REQ-004 for writing it.
- **The map below decides** where a requirement goes, by its main subject. For a subject not yet in it: if one spec uses it, that spec; if several do, the spec where it is maintained; otherwise REQ-001. Add the new entry to the map first.

| Spec | Main subjects |
| :- | :- |
| REQ-001 Core | Business terms and the model; exact values and their only exceptions; outside input in general, its size limit included; refusals and findings as concepts |
| REQ-002 Conformance | Official artefacts; official test files and differences found in them; profiles, versions and editions supported; choosing and running the rule set; findings, Haflinger's own included |
| REQ-003 Incoming invoices | An invoice received: CII, UBL and PDF input, the choices made in reading, what is read, reported and refused, embedded files |
| REQ-004 Outgoing invoices | An invoice Haflinger produces: target profiles, the choices made in writing, the XML Schema check, ZUGFeRD PDFs, what is handed out and what is refused |

Validation splits along the map: choosing and running the rule set is REQ-002's; what a finding means for an incoming invoice is REQ-003's, for an outgoing one REQ-004's.

## IDs

Requirement, user story and persona IDs always carry the spec's ID: `REQ-003-PRS-F004`, `REQ-001-P1-2`, `REQ-001-P1`, never a bare `PRS-F004`. This holds in the specs, the other docs, code comments, tests and commit messages. EN 16931 business terms keep their own IDs (`BT-1`, `BG-23`).

The project code is **HAFL**. Outside this repository, IDs carry it: `HAFL-REQ-003-PRS-F004`, or `HAFL-REQ-003` for a whole spec. The code never changes, since other repositories cite it.

## Changes

A spec is Draft until the maintainer baselines it, and edited in place until then. After baseline:

- **A substantive change** (a requirement added, removed or reworded, or a term changed so that a requirement covers other cases) is folded into the body, and a sibling `req-NNN-name.history.md` records the dated reason, most recent first. The spec's `Version` goes up with each entry.
- **A change that keeps the meaning** (a typo, a link, formatting, clearer wording) is made in the body only.
