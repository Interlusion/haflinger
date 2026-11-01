# ADR-005: Our own mapping reads; KoSIT's reading stylesheet checks it

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Context

An invoice is read into the model through a binding: for each business term, the element of CII or UBL that holds it (EN 16931-3-3 and EN 16931-3-2). Two bindings were tried on 2026-10-30:

- **Haflinger's own mapping**, per syntax, for the business terms of the first model (REQ-001-PRS-F001).
- **KoSIT's visualisation stylesheets** (`xrechnung-visualization`), run with Saxon. They turn CII and UBL into a semantic XML in which every element carries its business term ID; Haflinger reads the model from that by ID.

What was measured:

|  | Own mapping | KoSIT's stylesheet |
| :- | :- | :- |
| KoSIT test suite (66 files, CII and UBL) | the same model as KoSIT's for all 66 | the same model as ours for all 66 |
| ZUGFeRD corpus, invoices both read (176) | the same model as KoSIT's | the same model as ours |
| Business terms and groups covered | those of the model, growing with it | all 196 in its semantic model, about 160 of them seen in the KoSIT suite; maintained by KoSIT with each XRechnung release |
| 25.7 MB Peppol invoice, 26,813 lines | 0.8 s | 677 s |
| Two due dates in a ZUGFeRD EXTENDED invoice (BT-9) | the first read; the second, beyond EN 16931, silently dropped (now reported, REQ-003) | joined into one value, unreadable as a date |
| UBL credit note | not yet | read |
| EN 16931 editions | ours to add | the 2017 semantic model; 2026 expected with XRechnung 4.0 |

Invoices of tens of MB are normal for utilities and telecoms; the corpus holds one of 61 MB. KoSIT's stylesheet grows much faster than linearly with the number of lines; the official rules don't (6.7 s for the same file).

The writer spike showed what the second reader is worth: a mistake made the same way in Haflinger's reader and writer (the same wrong element both ways) passes a round trip through Haflinger alone, but not through KoSIT's reader.

[ADR-003](ADR-003-integrate-dont-implement.md) prefers official artefacts to own implementations. A binding, though, is a fixed table of paths published in EN 16931-3; the hard, moving parts are the business rules, which Haflinger doesn't reimplement.

## Decision

- **Haflinger's own mapping is the reader.** `read_invoice` reads CII and UBL into the model through Haflinger's bindings, at every size, with no Saxon in the reading path.
- **KoSIT's stylesheet is the independent check.** In the tests, every official test file that is a whole invoice Haflinger reads, and every written invoice, is read by both; the two models must be equal. CEN's unit tests are fragments, not whole invoices, and files `read_invoice` refuses have no model to compare (REQ-003-PRS-F005). A difference is a defect in Haflinger, or a limit of KoSIT's stylesheet recorded in the test with its reason.
- **KoSIT's coverage guides the mapping.** For a business term the model gains, KoSIT's semantic XML shows its element in both syntaxes, and its test files exercise it.
- The stylesheets stay vendored unchanged ([ADR-008](ADR-008-vendoring-official-files.md)), for the tests now and for rendering invoices for people later.

## Alternatives Considered

### Alternative 1: KoSIT's stylesheet as the reader

The model read from KoSIT's semantic XML, all its terms without mapping work of our own.

**Rejected because**: 11 minutes for a 25.7 MB invoice; the 2017 semantic model only, with XRechnung in focus; repeated EXTENDED values joined; Saxon in the reading path of every invoice. And the tests would lose their independent second reader.

### Alternative 2: KoSIT's stylesheet as the reader, our mapping above a size limit

**Rejected because**: two runtime paths with different coverage: the same invoice would give a different model depending on its size.

### Alternative 3: A Java library (phax, Mustang) as the reader

**Rejected because**: a JVM at runtime ([ADR-003](ADR-003-integrate-dont-implement.md), alternative 3). Both remain candidates for further oracles in CI.

## Consequences

### Positive

- Reading is fast at any size and needs no Saxon.
- Every reading and writing defect has to slip past an independent implementation maintained by KoSIT.
- Editions, profiles and terms beyond XRechnung are in Haflinger's hands, not waiting for KoSIT.

### Negative

- Haflinger maintains its bindings: up to about 200 business terms and groups, in two syntaxes, in two editions.
- The check covers only what KoSIT's stylesheet covers: the 2017 edition, XRechnung's view of CII and UBL.
- A term KoSIT's stylesheet doesn't know has no second reader; its tests rely on the official files and the rules.

## Reconsideration Triggers

1. KoSIT's stylesheet reads large invoices in seconds; then alternative 1 is worth weighing again for coverage.
2. Maintaining the bindings costs more than the model's growth justifies, for example once the 2026 edition arrives; then consider a declarative table of business term to CII and UBL path, per edition, ideally derived from the official binding tables.
3. KoSIT stops maintaining the visualisation.

## Compliance

- Every official test file that is a whole invoice `read_invoice` reads SHALL be read by Haflinger's mapping and by KoSIT's stylesheet in the tests, and the models SHALL be equal, except for differences recorded with their reason.
- KoSIT's stylesheet SHALL NOT be on the runtime reading path.

## References

- Affects: arc42 [§4](../README.md#4-solution-strategy), [§5](../README.md#5-building-block-view), [§10](../README.md#10-quality-requirements)
- [ADR-003](ADR-003-integrate-dont-implement.md), [ADR-007](ADR-007-model-scope-and-editions.md)
- [itplr-kosit/xrechnung-visualization](https://github.com/itplr-kosit/xrechnung-visualization)
