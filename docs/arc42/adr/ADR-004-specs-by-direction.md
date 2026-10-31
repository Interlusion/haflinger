# ADR-004: Requirement specs by direction, with one core spec

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger's first spec, REQ-001, holds the model and reading CII and UBL. The spikes added writing CII, validating with the official rules, ZUGFeRD PDFs and the handling of official artefacts and test files. One spec for all of it would mix requirements that change for different reasons and are read for different tasks.

Specs are split where parts change at different rates, are read for different tasks, are decided by different people or carry different risk; never for length alone, and before IDs are baselined.

Haflinger's parts differ in exactly those ways:

- **Incoming invoices** are outside input: hostile until checked, in every format the law allows, read leniently so that a person sees what arrived. In the caller's system, ERPNext first, they become purchase invoices.
- **Outgoing invoices** are Haflinger's own legal duty: one format, complete for their profile, valid before they leave. In the caller's system they come from sales invoices.
- **Conformance** (which official artefacts, editions, profiles and rule sets, which test files) changes with every release of KoSIT, CEN or FeRD, several times a year, independent of either direction. It is the maintainer's part.

## Decision

- **REQ-001 Core** is the base spec. It holds the intended use and the shared personas, user stories and terms; the model of the EN 16931 business terms; and the rules every spec follows: exact values and their only exceptions, safety with outside input and its size limit, refusals and findings that name business terms and rules.
- **REQ-002 Conformance** holds the official artefacts and test files Haflinger relies on, the editions, profiles and versions it supports, and how the rule set for an invoice is chosen.
- **REQ-003 Incoming invoices** holds receiving: reading CII, UBL and ZUGFeRD PDFs into the model, what is refused and what is reported, legacy formats and limits.
- **REQ-004 Outgoing invoices** holds sending: writing CII and ZUGFeRD PDFs from the model, and validating them before they are handed out.
- **Not split by syntax or profile.** CII and UBL change together with the EN 16931 edition and are read for the same tasks; the model is independent of both. A syntax or profile shows up as requirements inside REQ-003 and REQ-004 and as rule sets in REQ-002. Which element holds which business term is the binding's (EN 16931-3) and lives in the code; the specs state only the choices the binding leaves open.
- **Other specs may tighten REQ-001's rules, never loosen them.** A rule is loosened only in REQ-001, by naming the exception.
- **Placement follows a map** in the [specs index](../../specs/README.md), by a requirement's main subject: business terms and the model to REQ-001; artefacts, test files, editions, profiles and rule sets to REQ-002; an incoming invoice to REQ-003; an outgoing invoice to REQ-004. Validation splits along the same line: choosing and running the rule set is REQ-002's; what a finding means for an incoming invoice is REQ-003's, for an outgoing one REQ-004's.
- **IDs are written in full** (`REQ-003-PRS-F002`), with the project code outside the repository (`HAFL-REQ-003-PRS-F002`).
- **The ERPNext app's requirements** belong to the app, in its own repository ([ADR-001](ADR-001-library-and-app.md), [ADR-009](ADR-009-licences-and-name.md)); until it exists, [ITEM-003](../../backlog/item-003-erpnext-app.md) collects them. What the app needs from the library goes into REQ-001 to REQ-004 by the map, like any caller's needs.

## Alternatives Considered

### Alternative 1: One spec

**Rejected because**: its history would mix every upstream release with every change to reading and writing, and an agent working on one direction would load the other.

### Alternative 2: Specs by capability (reading, writing, validation, PDF)

**Rejected because**: validation and PDFs would each mix both directions with their opposite risks (lenient on the way in, strict on the way out), and a caller, who works in one direction at a time, would have to read all of them.

### Alternative 3: Specs by syntax or profile

**Rejected because**: CII and UBL, and the profiles, change together and are read together; the split would only add cross-references and copies.

### Alternative 4: A spec for the ERPNext app in this repository

**Rejected because**: the app is a separate product with its own repository and licence ([ADR-009](ADR-009-licences-and-name.md)); its specs belong next to its code.

## Consequences

### Positive

- An agent working on incoming invoices reads REQ-001 and REQ-003; one adopting a KoSIT release reads REQ-001 and REQ-002.
- Each direction's risk is stated once, in its own spec.
- The cut matches how callers use the library: purchase and sales invoices (procure to pay, order to cash).

### Negative

- Validation and PDFs appear in three specs, held together by the placement map.
- REQ-001 grows with every business term the model gains.

## Reconsideration Triggers

1. Peppol transmission is added: network, an access point and contracts are a different risk and may need their own spec.
2. REQ-001's model section is read for tasks that need none of its rules, or the reverse.

## Compliance

- A new requirement SHALL go into the spec the placement map names; a subject not yet in the map SHALL be added to it first.
- Requirement IDs SHALL carry their spec's ID everywhere, and the project code `HAFL` outside the repository.

## References

- Affects: arc42 [§4](../README.md#4-solution-strategy)
- [Specs index](../../specs/README.md)
