# ADR-006: Validation with the official rules, run unchanged with Saxon

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Context

The business rules of EN 16931 and of each CIUS and profile are published as Schematron, compiled to XSLT 2 and 3: CEN's EN 16931 rules for CII and UBL, KoSIT's XRechnung rules (which include Peppol rules), the Factur-X rules per profile, Peppol BIS. KoSIT's validator configuration bundles CEN's and KoSIT's, with a scenario file that picks the rules for an invoice and lowers some rule levels (for example `CII-SR-475` and `CII-SR-476`, whose context is wrong in CEN 1.3.16).

In Python, only Saxon runs XSLT 3: `saxonche`, the C build of Saxon's Home Edition. Its Home Edition can't check XML Schemas. What was measured on 2026-10-30:

- All 66 files of the KoSIT test suite pass the EN 16931 and XRechnung rules; a total changed by one cent fails `BR-CO-15` and `BR-CO-16`.
- CEN's per-rule unit tests: 1,131 of 1,131 met with the rules of their own release, both for 1.3.17 and for 1.3.16, the release KoSIT bundles; 1.3.17's tests against 1.3.16's rules met only 1,066, all 65 misses in rules that changed between the two.
- Compiling the stylesheets takes 0.5 s once per process; validating an invoice 7 ms; the 25.7 MB Peppol invoice 6.7 s.
- Passing Saxon a tree re-serialised by ElementTree made 18 valid files fail `PEPPOL-EN16931-R008`: re-serialising drops comments, and an element holding only a comment became empty.
- Over the ZUGFeRD corpus, most failures of files filed as correct were the wrong rules for the file: XRechnung 1.2 and 2.1 checked with 3.0 rules, MINIMUM, BASIC WL and EXTENDED checked with EN 16931 rules, code-list values since removed.
- `saxonche` 13.1.1: wheels of about 38 MB (about 105 MB installed) for Linux with glibc ≥ 2.24 (x86_64, aarch64), macOS and Windows; none for musl (Alpine), no source distribution; the package metadata names no licence.

Written invoices also need their XML Schema checked; the rules assume a schema-valid document.

## Decision

- **The official Schematron stylesheets run unchanged with `saxonche`**, at runtime, for incoming and outgoing invoices. Haflinger reimplements no rule ([ADR-003](ADR-003-integrate-dont-implement.md)).
- **The rule set is chosen per invoice**, like the scenarios of KoSIT's validator: by syntax from the root element, then by profile and version from BT-24; for ZUGFeRD the Factur-X rules of its profile. The table of supported profiles and versions belongs to REQ-002. An invoice whose profile has no rule set of its own is checked with CEN's EN 16931 rules for its syntax and gets a Haflinger warning that says so (REQ-002); it is never silently checked with rules it doesn't claim.
- **KoSIT's rule levels apply**: the levels its scenario file sets override the stylesheets' own.
- **Saxon gets the original bytes**, after `defusedxml` has rejected DTDs and entities in them; never a re-serialised tree.
- **Findings** carry rule ID, flag, location and text; `fatal` and `error` make an invoice invalid.
- **Each stylesheet is compiled once per process** and reused.
- **The XML Schema check** runs before the rules for invoices Haflinger writes. This ADR owns the choice of its library, still open: `lxml` (a compiled library, already a dependency of the `pdf` extra) or `xmlschema` (pure Python). The tests use `lxml`; the choice is made when REQ-004-PRS-F004 is built, and recorded here.

## Alternatives Considered

### Alternative 1: KoSIT's validator (Java) at runtime

**Rejected because**: a JVM next to the host application. It remains a candidate for an oracle in CI.

### Alternative 2: The rules reimplemented in Python

**Rejected because**: hundreds of rules, changed several times a year by their owners; every divergence would be a defect found late ([ADR-003](ADR-003-integrate-dont-implement.md)).

### Alternative 3: lxml's ISO Schematron

**Rejected because**: XSLT 1 only; the official rules need XSLT 2 or 3.

### Alternative 4: Validation in CI only

**Rejected because**: incoming invoices are validated when they arrive, not when Haflinger is built.

## Consequences

### Positive

- Validation is the official rules' verdict, by construction; adopting a release is a version bump and a test run.
- Fast enough for every invoice, large ones included.

### Negative

- About 105 MB of native code in the host's environment, and no wheels for musl-based images.
- The licence of `saxonche` is to be confirmed before a release ([ADR-009](ADR-009-licences-and-name.md)).
- Haflinger has to maintain the choice of rule set and KoSIT's rule levels as glue.

## Reconsideration Triggers

1. Saxon's licence or packaging changes, or a platform Haflinger must support has no wheel.
2. A Python engine runs the official stylesheets without Saxon.
3. KoSIT's or FeRD's validator becomes available without a JVM.

## Compliance

- The official stylesheets SHALL run unchanged; a change SHALL come from a new upstream release ([ADR-008](ADR-008-vendoring-official-files.md)).
- Saxon SHALL receive the original bytes, after the `defusedxml` check.
- An invoice SHALL be validated with the rule set its syntax, profile and version call for; only an invoice whose profile has none gets CEN's EN 16931 rules, with the warning that says so.

## References

- Affects: arc42 [§4](../README.md#4-solution-strategy), [§5](../README.md#5-building-block-view), [§6](../README.md#6-runtime-view), [§7](../README.md#7-deployment-view), [§8](../README.md#8-cross-cutting-concepts), [§10](../README.md#10-quality-requirements), [§11](../README.md#11-risks-and-technical-debt)
- [ADR-003](ADR-003-integrate-dont-implement.md), [ADR-008](ADR-008-vendoring-official-files.md), [ADR-009](ADR-009-licences-and-name.md)
- [itplr-kosit/validator-configuration-xrechnung](https://github.com/itplr-kosit/validator-configuration-xrechnung), [ConnectingEurope/eInvoicing-EN16931](https://github.com/ConnectingEurope/eInvoicing-EN16931)
