# ADR-009: Apache-2.0, the licences of what is vendored, and a name without ERPNext or Frappe

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger's library is meant to be used by the ERPNext app and by other software. ERPNext is licensed under GPL-3.0; code that imports it is bound by it. ALYF's European e-Invoice app, the nearest prior work, is GPL-3.0 too.

Haflinger also ships files it didn't write, each under its own licence:

| Material | Licence |
| :- | :- |
| KoSIT's visualisation, validator configuration and test suite | Apache-2.0 |
| CEN's EN 16931 rules (inside KoSIT's configuration) and unit tests | EUPL-1.2 |
| UN/CEFACT's CII XML Schemas | © UN/CEFACT; may be copied and distributed unchanged with the notice |
| ZUGFeRD corpus (the Mustang project's PDFs) | Apache-2.0 |
| SchXslt (runtime, compiles FeRD's Schematron) | MIT |
| The PDF/A file of veraPDF's test corpus (tests only) | CC BY 4.0 |
| FeRD's Factur-X XML Schemas and Schematron | Apache-2.0, by FeRD's rights of use; its XSLT and samples are not named there |
| `saxonche` (runtime) | Not named in its package metadata; Saxonica publishes the Home Edition as open source; to be confirmed |
| `defusedxml`, `lxml` (runtime); `factur-x`, `pypdf` (`pdf` extra) | PSF, BSD-3-Clause; BSD, BSD-3-Clause |

Frappe's trademark policy doesn't allow "ERPNext" or "Frappe" in the name of a third-party product; a description may say "for ERPNext".

## Decision

- **The library is Apache-2.0**: permissive, with a patent grant, usable by the app and by other software.
- **The ERPNext app is GPL-3.0**, in its own repository, because it imports ERPNext. Code from GPL projects such as ALYF's goes only into the app, with attribution.
- **Vendored files keep their own licence**, stated in their provenance README with the licence file next to them ([ADR-008](ADR-008-vendoring-official-files.md)), and listed among the package's licence files. Copyleft material (EUPL-1.2) is shipped only as unchanged files.
- **New runtime dependencies** need a licence that allows distributing them with an Apache-2.0 library; copyleft beyond unchanged files needs an ADR.
- **Saxon's licence is confirmed before the first release**, and recorded here.
- **The name**: Haflinger in prose, `haflinger` as an identifier, `HAFLINGER_` for variables; the project code `HAFL`. "ERPNext" and "Frappe" are not in the project or package name; descriptions may say "for ERPNext", and the README says Haflinger is not affiliated with Frappe Technologies.

## Alternatives Considered

### Alternative 1: GPL-3.0 for the library too

**Rejected because**: it would bind every user of the library, including software outside ERPNext, while the library imports nothing of ERPNext.

### Alternative 2: MIT

**Rejected because**: no patent grant.

### Alternative 3: A name with ERPNext in it

**Rejected because**: Frappe's trademark policy.

## Consequences

### Positive

- The library can serve any software; the app's GPL stays where ERPNext requires it.
- Every vendored file's terms are visible next to it.

### Negative

- Two repositories with two licences once the app exists.
- Licences to track per source and dependency, by hand.
- Shipping EUPL-1.2 files in an Apache-2.0 package needs a check before the first release.

## Reconsideration Triggers

1. Saxon's licence turns out not to allow distribution with Haflinger.
2. A review before the first release finds a conflict with a vendored licence.
3. Frappe changes its trademark policy.

## Compliance

- The library SHALL NOT contain code copied from GPL projects.
- Every vendored source SHALL state its licence and ship its licence file.
- The project and package names SHALL NOT contain "ERPNext" or "Frappe".

## References

- Affects: arc42 [§2](../README.md#2-constraints), [§11](../README.md#11-risks-and-technical-debt)
- [ADR-001](ADR-001-library-and-app.md), [ADR-008](ADR-008-vendoring-official-files.md), [AGENTS.md](../../../AGENTS.md)
