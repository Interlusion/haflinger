# ADR-009: Apache-2.0, the licences of what is vendored, and a name without ERPNext or Frappe

| Meta | Value |
| :- | :- |
| **Status** | Accepted |
| **Date** | 2026-11-12 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger's library is meant to be used by the ERPNext app and by other software. ERPNext is licensed under GPL-3.0; code that imports it is bound by it. ALYF's European e-Invoice app, the nearest prior work, is GPL-3.0 too.

Haflinger also ships files it didn't write, each under its own licence:

| Material | Licence |
| :- | :- |
| KoSIT's visualisation, validator configuration and test suite | Apache-2.0 |
| CEN's EN 16931 rules (inside KoSIT's configuration) and unit tests | EUPL-1.2 |
| UN/CEFACT's CII XML Schemas | © UN/CEFACT; may be copied and distributed unchanged with the notice |
| OASIS's UBL 2.1 XML Schemas of invoice and credit note (inside KoSIT's configuration) | No licence named. The twelve UBL modules: © OASIS Open 2013, with OASIS's copyright notice, which allows copying and distributing them unchanged with the notice. Among their imports: the XML Signature schema © The Internet Society and W3C (2001), under the W3C Software License; UN/CEFACT's CCTS module © UN/CEFACT (2006), with a notice like OASIS's; two XAdES schemas, copies of ETSI's, without any notice; ETSI publishes the current edition of these namespaces' schemas (EN 319 132-1 V1.3.1, on its forge) under BSD-3-Clause, © 2024 ETSI, but these copies are of earlier versions, which differ |
| ZUGFeRD corpus (tests only): the Mustang project's PDFs, and broken invoices of FeRD and FNFE-MPE it passes on | Apache-2.0, the corpus's; FeRD's and FNFE-MPE's files name no licence of their own |
| SchXslt (runtime, compiles FeRD's Schematron) | MIT |
| The PDF/A file of veraPDF's test corpus (tests only) | CC BY 4.0 |
| FeRD's Factur-X XML Schemas and Schematron | Apache-2.0, by FeRD's rights of use; its XSLT and samples are not named there |
| `saxonche` (runtime) | Not named in its package metadata; per Saxonica, MPL-2.0 for the most part, its files marked "Incompatible With Secondary Licenses", shipping GraalVM Community Edition; beside the GPL-3.0 app an open question ([ITEM-008](../../backlog/item-008-saxonche-licence.md)) |
| `defusedxml`, `lxml` (runtime); `factur-x`, `pypdf` (`pdf` extra) | PSF, BSD-3-Clause; BSD, BSD-3-Clause |

Frappe's trademark policy doesn't allow "ERPNext" or "Frappe" in the name of a third-party product; a description may say "for ERPNext".

## Decision

- **The library is Apache-2.0**: permissive, with a patent grant, usable by the app and by other software.
- **The ERPNext app is GPL-3.0**, in its own repository, because it imports ERPNext. Code from GPL projects such as ALYF's goes only into the app, with attribution.
- **Vendored files keep their own licence**, stated in their provenance README with the licence file next to them ([ADR-008](ADR-008-vendoring-official-files.md)), and listed among the package's licence files. Copyleft material (EUPL-1.2) is shipped only as unchanged files, with where its source code is: CEN's rules are XSLT that KoSIT compiled from CEN's Schematron, the form EUPL-1.2 calls source code, and `THIRD-PARTY-NOTICES` names its repository and tag, as the licence's article 5 asks.
- **Test files that name no licence of their own**, passed on by a collection under its licence, are taken on that licence: the ZUGFeRD corpus has passed on FeRD's and FNFE-MPE's invoices under Apache-2.0 since 2019, and their makers publish such samples for testing; they stay out of the package, which holds no tests. A test file whose identifiers may be real, such as VAT identifiers or an IBAN passing their check digits, isn't vendored, scrambled names or not.
- **New runtime dependencies** need a licence that allows distributing them with an Apache-2.0 library; copyleft beyond unchanged files needs an ADR.
- **The package says what it ships**: `THIRD-PARTY-NOTICES` lists the vendored files of the wheel with their terms, a `Licence` line of SPDX identifiers per directory, and holds the notices of UN/CEFACT and OASIS and W3C's licence, which have no licence file of their own; `pyproject.toml`'s licence expression is Apache-2.0 and those lines together. The licence files and `THIRD-PARTY-NOTICES` are among the package's licence files (PEP 639). It isn't named `NOTICE`, which Apache-2.0 section 4(d) would have every redistributor reproduce. The wheel holds only the runtime artefacts; the test files and veraPDF's PDF are in the repository only.
- **ETSI's XAdES schemas**, which OASIS's UBL 2.1 schemas import, carry no notice, in ETSI's originals or in OASIS's copies, and no licence of them is known. They are shipped as OASIS's UBL 2.1 and KoSIT's configuration ship them, and `THIRD-PARTY-NOTICES` says so. ETSI publishes the current edition of these namespaces' schemas under BSD-3-Clause; whether that covers the earlier versions OASIS copied was asked of ETSI on 2026-11-11 ([backlog](../../backlog/backlog.md)). Without them, the UBL schemas still load, but the XML Schema check would no longer be KoSIT's.
- **Saxon doesn't block Haflinger's releases**: Haflinger ships none of Saxon's files and only requires `saxonche`, and Apache-2.0 beside Saxon's MPL-2.0 isn't in question. Whether the GPL-3.0 app may use it is the app's question, to settle before the app is published ([ITEM-008](../../backlog/item-008-saxonche-licence.md)); [ADR-010](ADR-010-saxon-in-a-worker-process.md) keeps Saxon out of the caller's process.
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
- A licence expression and `THIRD-PARTY-NOTICES` to keep in step with the vendored files, by hand, on each update ([development guide](../../guides/development.md#updating-official-files)); a test checks that they agree.
- EUPL-1.2 files in an Apache-2.0 package: shipped unchanged and run as data by Saxon, as KoSIT's Apache-2.0 validator configuration ships them; the package isn't a derivative of them, as the EU's guidance on the EUPL doesn't count linking programs, for interoperability too, as making one. The obligations of its article 5 for unchanged copies are met: the licence ships with them, their notices are kept (they carry none), they stay under EUPL-1.2, and `THIRD-PARTY-NOTICES` says where their source code is. This is a reading, not legal advice.

## Reconsideration Triggers

1. Saxon's licence turns out not to allow requiring it from an Apache-2.0 library, or a lawyer's answer for the app (ITEM-008) changes how Haflinger runs it.
2. A review before the first release finds a conflict with a vendored licence.
3. Frappe changes its trademark policy.

## Compliance

- The library SHALL NOT contain code copied from GPL projects.
- Every vendored source SHALL state its licence and ship its licence file.
- `THIRD-PARTY-NOTICES` SHALL list every vendored directory the wheel ships with the licences of its files, and the package's licence expression SHALL be Apache-2.0 and those licences.
- The project and package names SHALL NOT contain "ERPNext" or "Frappe".

## References

- Affects: arc42 [§2](../README.md#2-constraints), [§11](../README.md#11-risks-and-technical-debt)
- [ADR-001](ADR-001-library-and-app.md), [ADR-008](ADR-008-vendoring-official-files.md), [AGENTS.md](../../../AGENTS.md)
- [EUPL: licence compatibility, permissivity, reciprocity and interoperability](https://interoperable-europe.ec.europa.eu/collection/eupl/licence-compatibility-permissivity-reciprocity-and-interoperability), the EU's guidance on linking
- [ETSI EN 319 132-1 V1.3.1](https://www.etsi.org/deliver/etsi_en/319100_319199/31913201/01.03.01_60/en_31913201v010301p.pdf), annex C: where its XAdES schemas are
