# ADR-001: A standalone library on one EN 16931 model, and a slim ERPNext app in its own repository

| Meta | Value |
| :- | :- |
| **Status** | Accepted |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Context

ERPNext has no complete e-invoicing. ALYF's European e-Invoice app (`alyf-de/eu_einvoice`) is bound to CII: it translates ERPNext documents directly into the CII objects of the `drafthorse` library and back, with no model of the EN 16931 business terms in between. Its README calls UBL out of scope, its import rejects UBL files, and Peppol is missing. UBL and Peppol matter for customers in Belgium or France, and EU-wide once ViDA requires EN 16931 invoices for cross-border trade from 2030, in either syntax.

Haflinger is to be maintained largely by agents. They need behaviour they can check quickly and on their own: against official test files, without a running ERPNext.

## Decision

- **A standalone Python library, `haflinger`.** It holds one model of the EN 16931 business terms. It reads CII, UBL and ZUGFeRD PDFs into the model, validates with the official rules ([ADR-006](ADR-006-validation-with-official-rules.md)) and writes CII and ZUGFeRD PDFs ([ADR-003](ADR-003-integrate-dont-implement.md)). It imports no Frappe or ERPNext code and is tested against the official test files.
- **All syntax and format knowledge is in the library**: the elements of CII and UBL, and how XML is embedded in a ZUGFeRD PDF (PDF/A-3, XMP). PDF support is an optional extra, `haflinger[pdf]`, so that the plain library stays small.
- **A slim ERPNext app later, in its own repository**, which maps ERPNext documents to and from the model, renders the readable PDF of an outgoing invoice with ERPNext's print formats, and holds no syntax knowledge of its own. It is the library's first user, not part of it: its name, its requirements, and whether parts of it run elsewhere (as tools of another system, or as a separate service) are decided there, per feature. Licences of the library and the app: [ADR-009](ADR-009-licences-and-name.md).
- **Peppol later**, through an access point; not part of the library.

## Alternatives Considered

### Alternative 1: Contribute UBL and Peppol to European e-Invoice

**Rejected because**: UBL is out of scope there by the maintainers' decision, UBL files are deliberately rejected (#323), and the app has no syntax-neutral model to extend; UBL would be a rewrite inside someone else's roadmap.

### Alternative 2: Map ERPNext directly to each syntax

**Rejected because**: every syntax would need its own mapping from ERPNext, and the ERPNext side couldn't be tested without ERPNext. A model in between makes each syntax one mapping, tested against official files.

### Alternative 3: Build on existing libraries per syntax (`drafthorse` for CII, a UBL library)

**Rejected because**: two object models to translate between, and the mapping to EN 16931, which is the actual work, would remain. For writing neither is needed: a CII writer on the standard library took about 140 lines, and its output reads back unchanged and passes the XML Schema and the official rules for every term the model holds.

### Alternative 4: Mustangproject (Java)

**Rejected because**: covers both syntaxes, but brings a JVM next to the host application and a second language for the maintainers.

## Consequences

### Positive

- CII, UBL and later formats are each one mapping to one model, tested without ERPNext.
- The library can serve other software than ERPNext.

### Negative

- The model has to be built and kept complete against EN 16931, rather than borrowed.
- Two repositories once the app exists.

## Reconsideration Triggers

1. European e-Invoice gains a syntax-neutral model and UBL.
2. ERPNext adds e-invoicing to its core.

## Compliance

- The library SHALL NOT import Frappe or ERPNext.
- Syntax and format knowledge (CII and UBL elements, ZUGFeRD PDF embedding) SHALL live in the library only.

## References

- Affects: arc42 [§1](../README.md#1-introduction-and-goals), [§2](../README.md#2-constraints), [§3](../README.md#3-context-and-scope), [§4](../README.md#4-solution-strategy), [§5](../README.md#5-building-block-view)
- [ADR-003](ADR-003-integrate-dont-implement.md), [ADR-009](ADR-009-licences-and-name.md)
- [REQ-001](../../specs/req-001-core.md)
- [alyf-de/eu_einvoice](https://github.com/alyf-de/eu_einvoice)
