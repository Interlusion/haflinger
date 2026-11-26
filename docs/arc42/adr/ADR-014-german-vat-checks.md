# ADR-014: German VAT checks with KoSIT's German rules, on any invoice the caller names

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-26 |
| **Author** | loxy (drafted with Claude) |

## Context

An invoice that German invoicing law governs has to hold what §14(4) UStG lists; input VAT is deductible only from such an invoice (§15(1) no. 1 UStG). Which state's invoicing law governs an invoice follows the place of supply, and on reverse charge the state where the supplier is established (Article 219a of the EU VAT Directive): a German seller's tax-free intra-Community supply follows §14 with no German VAT on it, and a French supplier's reverse-charge invoice to a German buyer follows French law.

Much of §14(4) is mandatory in EN 16931 itself and checked by CEN's rules on every invoice of an EN 16931 profile: the invoice number (BT-1), the date of issue (BT-2), the seller's and buyer's names and countries, quantity and type of each item, the net amounts and the VAT per rate (BG-23), the seller's VAT identifier, tax number or tax representative's VAT identifier on any line of the categories S, Z, E, AE, K, G, L or M (`BR-S-02` and its siblings), and the reason for an exemption (`BR-E-10`, `BR-AE-10`, `BR-IC-10`). For §14a(1) and (3) UStG, CEN's rules ask for the buyer's VAT identifier on an intra-Community supply (`BR-IC-02`), and on reverse charge for it or the buyer's legal registration identifier (BT-47, `BR-AE-02`), where §14a(1) asks for the VAT identifier for a service in another member state; on domestic reverse charge (§13b(2)), §14a(5) asks only for the note, which `BR-AE-10` requires.

KoSIT's German rules of XRechnung check more, but `validate` runs them only where BT-24 names XRechnung, the profile for public buyers ([ITEM-010](../../backlog/archive/item-010-german-vat-checks.md)). Of them, these are §14(4)'s:

- `BR-DE-TMP-32`: the actual delivery date (BT-72), an invoicing period (BG-14) or a period on every line (BG-26), for the time of supply of no. 6, at the level `information`. An invoice without the time of supply isn't issued properly; it may be a calendar month (§31(4) UStDV), and it may follow from the invoice date where there is no doubt the supply was made in that month (UStAE 15.2a (1a), after BFH V R 18/17, by the BMF's letter of 2021-09-09), which no rule can tell. 36 of the 86 accepted files of KoSIT's test suite get this finding.
- `BR-DE-3`, `BR-DE-4`, `BR-DE-8`, `BR-DE-9`: the city and post code of seller and buyer (BT-37, BT-38, BT-52, BT-53), part of the full addresses of no. 1. A buyer in a country without post codes gets `BR-DE-9` too.

`BR-DE-16`, the seller's VAT identifier (BT-31), tax number (BT-32) or tax representative (BG-11), asks for what `BR-S-02` and its siblings already require; both accept a tax representative's VAT identifier alone. The others are XRechnung's own and not §14's: the payment instructions (`BR-DE-1`), the seller's contact (`BR-DE-2`), the buyer reference (`BR-DE-15`), BT-24 naming XRechnung (`BR-DE-21`), and Peppol's rules that XRechnung includes. No rule checks the street or post office box of no. 1 (BT-35, BT-50), the price reductions agreed in advance, such as a cash discount (no. 7), the date of an advance payment (no. 6), or the notes of nos. 9 and 10 for work on a private buyer's property and for self-billing.

What was found on 2026-11-21, with XRechnung 3.0.2's stylesheets as vendored:

- KoSIT's scenario file chooses the stylesheets by BT-24; the stylesheets themselves check any CII or UBL invoice in their syntax. Over the 86 files of KoSIT's test suite, the XRechnung stylesheets gave the same findings with BT-24 as written and with BT-24 set to plain EN 16931, but for `BR-DE-21`'s warning.
- On the corpus's two correct ZUGFeRD invoices of the EN 16931 profile, both from one producer (a third file is one of them with a byte order mark), none of the five rules above failed; `BR-DE-21`, `BR-DE-2` and Peppol's rules did.
- KoSIT's scenario sets no level for any of the five rules; their stylesheets' levels apply: `BR-DE-TMP-32` `information`, the others `fatal`.
- `BR-DE-TMP-32` reads the delivery date of the header only; Factur-X EXTENDED can give one on each line instead, which it doesn't see.

Factur-X MINIMUM and BASIC WL have no invoice lines and are no e-invoices under §14(1) UStG, by the BMF; their XML lacks what §14(4) asks for. On them, `BR-DE-TMP-32` never fails, as its condition on the lines holds when there are none, and the buyer's address may be missing altogether.

An invoice of at most €250 including VAT needs less (§33 UStDV): the seller's name and address, the date of issue, quantity and type, the amount with the VAT in one sum, and the rate or a note on an exemption; so neither the tax number, the time of supply nor the buyer. This doesn't hold for distance sales (§3c UStG), intra-Community supplies (§6a) or reverse charge (§13b). KoSIT's rules don't know the limit.

A credit note (BT-3 `381`) corrects an invoice it refers to, and an invoice for an advance payment (`386`) before the supply states the date of the payment, where known, not the time of supply (§14(4) no. 6); `BR-DE-TMP-32` asks both for a time of supply.

Which invoicing law governs an invoice doesn't follow from the invoice: the seller's country, a VAT identifier starting with `DE` and the rate of 19%, which other states have too, all mislead in the cases above. The caller knows, from the company and the tax template its invoice was booked with.

## Decision

- **A function of its own, `haflinger.check_german_vat(data, *, max_size, timeout)`**, which takes the XML of a CII invoice or a UBL invoice or credit note and returns findings, with the same limits, refusals and time limit as `validate`, in the same worker process ([ADR-010](ADR-010-saxon-in-a-worker-process.md)). It is not a mode or a profile: reading, writing and `validate` stay as they are. "German VAT" in its name means German VAT law, of which §14 UStG is part.
- **The caller decides that German invoicing law, §14 UStG, governs the invoice** and calls the check only then; Haflinger doesn't guess from the seller's country, VAT identifier or rates. Outgoing, the caller checks the CII that `write_cii` wrote; incoming, the invoice it received, beside `validate`.
- **The XML Schema check first**, the one `validate` runs for the invoice; where it fails, its `HAFL-XSD` findings are the result, as the rules assume a schema-valid document.
- **KoSIT's XRechnung stylesheet for the invoice's syntax, unchanged, on any invoice**, whatever its BT-24 names, Factur-X MINIMUM and BASIC WL aside. Only the findings of `BR-DE-TMP-32`, `BR-DE-3`, `BR-DE-4`, `BR-DE-8` and `BR-DE-9` are kept, with KoSIT's rule IDs, texts, levels and XPath locations, as `validate`'s findings carry them; `HAFL-RULES`, where the stylesheet fails on the invoice, is kept too, naming the check's rules rather than an XRechnung rule set. The list of rule IDs is REQ-002's.
- **Every finding of the check is meant to be shown, whatever its flag**: the time of supply comes at KoSIT's level `information`, which Haflinger doesn't raise ([ADR-006](ADR-006-validation-with-official-rules.md)). `is_valid` is for `validate`'s findings, not the check's. A caller that holds an invoice back on a finding chooses by flag and rule knowingly: the missing time of supply is common on proper invoices, whose date may give it.
- **Three rules of Haflinger's own**, with the law they follow:
  - Factur-X MINIMUM and BASIC WL get one finding of Haflinger's own instead of the rules: no e-invoice under §14(1) UStG, its XML lacks what §14(4) asks for. Its ID and text are REQ-002's.
  - Small invoices: where the invoice total with VAT (BT-112) is at most 250 in absolute value, as a corrective invoice (`384`) may be negative, the currency (BT-5) is EUR, the invoice has a VAT breakdown and no VAT category of the breakdown (BT-118) or of a line (BT-151) is K or AE, the findings of `BR-DE-TMP-32`, `BR-DE-8` and `BR-DE-9` are dropped. The values are those `read_invoice` reads; where one of them isn't read, nothing is dropped. A distance sale can't be told from the invoice; that limit is stated, not guessed.
  - Credit notes (`381`) and invoices for advance payments (`386`): the finding of `BR-DE-TMP-32` is dropped.
- **What no rule checks is stated as not checked**, with the gaps above: the street or post office box and no. 7's price reductions, no. 6's advance payments, nos. 9 and 10, the buyer's VAT identifier on a cross-border reverse charge, and the line delivery dates of Factur-X EXTENDED, which `BR-DE-TMP-32` doesn't see.
- **`validate` stays as it is.** It judges an invoice by the rules its BT-24 claims ([ADR-006](ADR-006-validation-with-official-rules.md)); the check answers the caller's other question, what §14 UStG asks of the invoice. On an XRechnung invoice both report the five rules, and on a small one `validate` keeps what XRechnung requires and the check drops: the caller shows the two lists apart.
- **Haflinger states what the check covers, not that an invoice meets the law.** What a finding means, holding an outgoing invoice back or showing it to the person reviewing an incoming one, is the caller's.
- **Germany first.** Another member state, if needed, gets a function of its own, with its own exceptions.

## Alternatives Considered

### Alternative 1: Rules of Haflinger's own on the model

A function that takes the model, before `write_cii` and after `read_invoice`, with rules of Haflinger's own for all of it.

**Rejected because**: it reimplements rules KoSIT maintains ([ADR-003](ADR-003-integrate-dont-implement.md)), needs IDs of its own and locations by business term, as a model has no XPath, and would drift from KoSIT's rules with each release.

### Alternative 2: KoSIT's rules alone, without rules of Haflinger's own

**Rejected because**: small invoices, credit notes and advance payments would get findings the law doesn't support, and a MINIMUM invoice none, though its XML lacks what §14(4) asks for.

### Alternative 3: XRechnung's rules in full for every German invoice

**Rejected because**: XRechnung asks for more than the law, such as the payment instructions and the buyer reference, the Leitweg-ID for public buyers; an invoice between businesses would fail rules that don't concern it.

### Alternative 4: Haflinger decides which invoicing law governs the invoice

From the seller's country (BT-40), a VAT identifier starting with `DE`, or the rates.

**Rejected because**: it follows the place of supply, not the addresses; a wrong guess either misses a gap or reports one that doesn't concern the invoice. The caller has the facts.

### Alternative 5: The checks in the ERPNext app

**Rejected because**: one list of findings beside the official rules', tested in seconds without ERPNext, kept current with KoSIT's releases in one place, and of use to every caller.

## Consequences

### Positive

- An invoice between businesses gets the German checks KoSIT maintains, with the same IDs and texts an XRechnung invoice gets.
- What KoSIT maintains isn't reimplemented; adopting a KoSIT release updates the check too.

### Negative

- A second run of XRechnung's stylesheet beside `validate`'s, of a few milliseconds for a common invoice, and bounded like `validate`'s for a hostile one.
- Three rules of Haflinger's own that follow the law, not KoSIT's releases (trigger 4).
- The five rule IDs, and what their rules check, are reviewed with each KoSIT release: a rule renamed, split, changed or added for §14 needs a change of REQ-002.
- The check doesn't cover all of §14(4) UStG, and its time of supply is often missing on proper invoices; a tax adviser's review decides whether and how a caller relies on it.

## Reconsideration Triggers

1. A KoSIT release removes, renames, splits or changes one of the five rules, or adds one for §14(4) UStG.
2. XRechnung 4.0 for EN 16931:2026 ([ADR-007](ADR-007-model-scope-and-editions.md)).
3. A caller needs another member state, or a check that KoSIT's rules don't hold.
4. §14 or §14a UStG, or §31 or §33 UStDV, changes.

## Compliance

- The check SHALL run KoSIT's stylesheets unchanged and SHALL keep only the findings of the rule IDs REQ-002 lists, and `HAFL-RULES`.
- A test SHALL fail when a listed rule ID no longer occurs in the vendored stylesheets; updating KoSIT's configuration SHALL review the changes to its `BR-DE` rules.
- Each rule of Haflinger's own SHALL have tests, the small invoices' at 250.00, 250.01 and -250.00 EUR.
- Haflinger SHALL NOT decide which invoicing law governs an invoice.

## References

- Affects: arc42 [§4](../README.md#4-solution-strategy), [§5](../README.md#5-building-block-view); REQ-001-PRS-F006 and [ADR-012](ADR-012-public-api.md), which list the public names; [REQ-002](../../specs/req-002-conformance.md), which lists the rule IDs and Haflinger's own findings (REQ-002-PRS-F010); [REQ-004](../../specs/req-004-outgoing-invoices.md), whose scope leaves this to the caller until then; the [security policy](../../../SECURITY.md), which names the entry points
- Updates [ADR-003](ADR-003-integrate-dont-implement.md#our-own-code)'s open point on German specifics; beside [ADR-006](ADR-006-validation-with-official-rules.md)'s choice of the rule set
- [ITEM-010](../../backlog/archive/item-010-german-vat-checks.md)
- §14, §14a, §15 UStG, §31 and §33 UStDV; UStAE 15.2a (1a); BMF, letter of 2021-09-09 on the time of supply (BFH V R 18/17); Article 219a of Directive 2006/112/EC
