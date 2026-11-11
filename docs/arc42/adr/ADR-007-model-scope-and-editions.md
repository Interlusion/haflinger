# ADR-007: A model that grows towards all of EN 16931, edition-aware from the start

| Meta | Value |
| :- | :- |
| **Status** | Accepted |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Context

EN 16931-1:2017 defines 196 business terms and groups. Haflinger's first model holds 51 of them: 45 terms in 6 groups (REQ-001-PRS-F001).

- **Reading a subset is harmless**: the original stays the invoice, and what the model lacks is still in it.
- **Writing a subset isn't.** Writing the 66 KoSIT files from the model broke 14 rules (16 over the 86 files of the suite as vendored), each for missing terms: allowances and charges (BG-20, BG-21), whose sums (BT-107, BT-108) the model holds without the items; and for XRechnung payment instructions (BG-16), seller contact (BG-6), city and post code (BT-37, BT-38, BT-52, BT-53), electronic addresses (BT-34, BT-49); the seller identifier (BT-29, `BR-CO-26`); and, in the extension's case, third party payments (BG-DEX-09, `BR-CO-16`), which XRechnung's extension adds beyond EN 16931. German VAT law needs more than any of those rules forced: the seller's tax number (BT-32) when no VAT identifier (BT-31) is given, and the delivery date (BT-72) or invoicing period (BG-14).
- **EN 16931-1:2026** was ratified in February 2026: 52 new business terms and 7 groups, bound to UBL 2.5 and CII D25A once the bindings are published. XRechnung 4.0 follows (final expected 2027); both editions run in parallel until March 2029. An invoice shows its edition only in BT-24.
- **Beyond EN 16931**, ZUGFeRD EXTENDED and XRechnung's extension carry content no edition defines.

## Decision

- **The model grows towards the complete EN 16931-1, by need, in this order**: first what writing a valid XRechnung and ZUGFeRD EN 16931 invoice requires (the rules the writer's tests still list as missed, plus BT-32, BT-72 and BG-14, which the app needs for German VAT law); then what incoming invoices commonly carry; then the rest. Every term enters through REQ-001, then its tests, then the code.
- **The model is edition-aware from the start.** It records the edition read from BT-24. Terms of the 2026 edition are added as optional fields once its bindings are published. An invoice of an edition Haflinger doesn't support is never read as another edition; REQ-002 says which editions are supported, and the others are refused.
- **One model for both editions**, as long as 2026 only adds terms or lets a term repeat. A term that becomes repeatable takes the wider form (a tuple) for both editions; a 2017 invoice then holds at most one entry.
- **Extensions beyond EN 16931 are not modelled.** They stay in the original, which is the invoice that is archived.
- **An invoice is handed out only when it passes the rules of its profile.** A profile may be a write target before the model holds every term its rules require (amended on 2026-11-01, for XRechnung 3.0): the rules then refuse each such invoice and their findings name what is missing. The writer's tests list the rules it can't yet meet, so that the list shrinks as the model grows.

## Alternatives Considered

### Alternative 1: All 196 terms and groups at once

**Rejected because**: the official material says what each term is (EN 16931-1) and where it sits in CII and UBL (the binding tables), but each term still needs its type in the model, reading from both syntaxes, writing to CII, the choices the binding leaves open, and tests. Done at once, that work would come before any need for it, while reading loses nothing without a term: the original keeps it. The writer's tests and a coverage report over the official test files make the order by need cheap to follow.

### Alternative 2: Only what ERPNext produces and consumes

**Rejected because**: incoming invoices carry more than ERPNext stores, and the operator needs to see it.

### Alternative 3: A model per edition

**Rejected because**: the 2026 edition mostly adds terms; two models would double the mapping for little gain.

## Consequences

### Positive

- Writing reaches valid XRechnung and ZUGFeRD with the fewest new terms, each tested.
- The 2026 edition finds a model that already knows editions exist.

### Negative

- Until the model is complete, an incoming invoice's model shows only part of the invoice; the original remains the reference.
- Each step adds work in REQ-001, both bindings, the writer and the tests.

## Reconsideration Triggers

1. The 2026 edition changes the meaning of existing terms: then edition-specific types.
2. Operators need EXTENDED content in the software built on Haflinger.
3. The 2026 bindings are published: schedule its terms.

## Compliance

- No business-term field SHALL enter the model without its entry, with its BT or BG ID, in REQ-001.
- A term's ID, name and meaning SHALL be taken from EN 16931-1 as published, not invented.
- Haflinger SHALL NOT hand out an invoice that fails the rules of its profile; a profile whose required terms the model doesn't hold is refused by those rules, naming the missing terms.

## References

- Affects: arc42 [§4](../README.md#4-solution-strategy), [§8](../README.md#8-cross-cutting-concepts), [§10](../README.md#10-quality-requirements), [§11](../README.md#11-risks-and-technical-debt)
- [ADR-005](ADR-005-own-mapping-kosit-as-check.md)
- KoSIT: [EN 16931 status and XRechnung 4.0](https://xeinkauf.de/aktuelles/xse/en-16931-aktueller-stand-und-ausblick-auf-die-einfuehrung-der-xrechnung-4-0/)
