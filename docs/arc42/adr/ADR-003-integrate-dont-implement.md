# ADR-003: Integrate, don't implement; receive everything, send one format

| Meta | Value |
| :- | :- |
| **Status** | Accepted |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Context

E-invoicing has many layers, each with its own owners and release cycles ([E-Invoicing 101](../../guides/e-invoicing-101.md)): EN 16931 in two editions, two syntaxes in two versions each, CIUS and profiles (XRechnung, Peppol BIS, ZUGFeRD), validation rules released several times a year, code lists, Peppol. The standards bodies already publish most of the hard parts, maintained with every release: business rules as Schematron, test suites, code lists, and with KoSIT's visualisation even a mapping of CII and UBL to a semantic model.

Haflinger is maintained mostly by agents with a person reviewing. Its own code has to stay small enough for that, and every piece of it is a piece we keep current against moving standards.

German law requires a business to accept every EN 16931 invoice, in CII, UBL or as ZUGFeRD; it lets the sender choose the format.

## Decision

### Integrate what the standards bodies maintain

Haflinger uses official artefacts and maintained libraries unchanged, and implements nothing they cover:

| Area | Use | Maintained by |
| :- | :- | :- |
| Business rules, validation | The official Schematron (CEN EN 16931, XRechnung with the Peppol rules it includes, ZUGFeRD), run unchanged with Saxon ([ADR-006](ADR-006-validation-with-official-rules.md)); Peppol BIS's own rules later | CEN, KoSIT, FeRD; OpenPeppol |
| Checking how CII and UBL are read | KoSIT's visualisation XSLT as the independent second reader in the tests; our own mapping reads ([ADR-005](ADR-005-own-mapping-kosit-as-check.md)) | KoSIT |
| Rendering for people | KoSIT's visualisation XSLT (HTML, PDF) | KoSIT |
| ZUGFeRD / Factur-X PDF | `factur-x` | Akretion |
| Code lists | As the official rules carry them, unchanged; the EU registry behind them | European Commission |
| Tests | The official test suites, unchanged | KoSIT, CEN, OpenPeppol, community |
| Peppol transport | A certified access point provider; no AS4 of our own | Providers |

Official artefacts are vendored per release, pinned and unchanged ([ADR-008](ADR-008-vendoring-official-files.md)). Libraries with a single maintainer stay behind Haflinger's model, so that each can be replaced.

### Receive everything, send one format

- **Incoming**: CII, UBL (invoice and credit note), and ZUGFeRD / Factur-X PDFs, of both EN 16931 editions once the 2026 bindings exist.
- **Outgoing**: CII only, in two profiles: ZUGFeRD EN 16931 (as XML, or as PDF/A-3 with the XML embedded) for businesses, XRechnung 3.0 for public authorities. The profiles and their identifiers are listed in REQ-004; more profiles (EXTENDED, BASIC) only when a customer needs them. UBL output only when Peppol needs it and the access point doesn't convert.

### Our own code

What no one else maintains, and where Haflinger's value is:

- the bindings of the business terms to CII and UBL: a fixed table of paths per syntax, checked against KoSIT's ([ADR-005](ADR-005-own-mapping-kosit-as-check.md));
- in the ERPNext app, outside this repository: the mapping between ERPNext documents and the model (taxes, Skonto, rounding), matching incoming invoices to suppliers, items and accounts, and the review flow;
- German specifics beyond the official rules (for example the tax number or VAT ID and the delivery date that §14(4) UStG requires, or the planned note on cash-basis taxation); where they live, in the library as an optional rule set of Haflinger's own or in the app, is open ([ITEM-003](../../backlog/item-003-erpnext-app.md));
- glue: running the artefacts, turning their output into the model and into refusals or warnings;
- **following upstream**: new releases of the artefacts and code lists open agent pull requests, checked against the official tests.

## Alternatives Considered

### Alternative 1: Implement the standard ourselves

Own mapping, own business rules in Python, own writers for both syntaxes.

**Rejected because**: duplicates what CEN and KoSIT publish with every release, multiplies what agents must keep current, and every divergence from the official rules is a defect we would find late. The bindings are the exception, for speed and independence ([ADR-005](ADR-005-own-mapping-kosit-as-check.md)); the rules are not.

### Alternative 2: Send both CII and UBL

**Rejected because**: the law lets the sender choose, German receivers must accept CII, and a second writer doubles the output tests. Revisit for Peppol.

### Alternative 3: Java tools at runtime (KoSIT validator, phax, Mustang)

**Rejected because**: a JVM next to the host application to run and secure. They remain welcome as oracles in CI.

## Consequences

### Positive

- Haflinger's own code shrinks to the bindings, glue and tests in the library, and the ERPNext mapping in the app.
- Behaviour follows the official artefacts by construction; an update is mostly a version bump and a test run.
- The public story is one agents can keep: official building blocks integrated reliably.

### Negative

- Saxon becomes a large native runtime dependency, with its licence to be confirmed ([ADR-006](ADR-006-validation-with-official-rules.md), [ADR-009](ADR-009-licences-and-name.md)).
- We depend on upstream release timing; a fix in an official artefact waits for its release, or is carried as a documented patch.
- Licences to respect per artefact ([ADR-009](ADR-009-licences-and-name.md)).

## Reconsideration Triggers

1. An artefact we rely on is no longer maintained.
2. Saxon's licence or packaging changes.
3. Customers need UBL output outside Peppol.

## Compliance

- Business rules SHALL NOT be reimplemented in Python where an official Schematron covers them.
- Official artefacts SHALL be used unchanged, pinned to a release, with their provenance recorded.

## References

- Affects: arc42 [§2](../README.md#2-constraints), [§3](../README.md#3-context-and-scope), [§4](../README.md#4-solution-strategy)
- [ADR-001](ADR-001-library-and-app.md), [ADR-002](ADR-002-toolchain.md), [ADR-005](ADR-005-own-mapping-kosit-as-check.md), [ADR-006](ADR-006-validation-with-official-rules.md), [ADR-008](ADR-008-vendoring-official-files.md)
