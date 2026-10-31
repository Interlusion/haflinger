# Analysis 004: Writing CII, checked by the read side (spike)

| Meta | Value |
| :- | :- |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Archived |
| **Audience** | Maintainer; input for the ADRs and specs |
| **Purpose** | Can writing rely on the read side, and how far does the model get towards a valid outgoing invoice? |
| **Branch** | `spike/cii-writer` |

> Archived on 2026-10-30. Its findings live in the ADRs, specs, architecture, guides and backlog; [analysis 005](analysis-005-arc42-setup.md) lists where each one went.

## Question

Can writing rely on what the read side already has, instead of hand-written expected XML? That is: Haflinger's reader, KoSIT's reading stylesheet, the XML Schema of CII and the official rules. And how far does the current model (43 business terms, REQ-001-PRS-F002) get towards a valid outgoing invoice?

## Setup

- **Writer**: `haflinger.write_cii(invoice) -> bytes` ([REQ-002](../../specs/req-004-outgoing-invoices.md)), about 140 lines in `cii.py` next to the reader. It writes each business term to the path the reader reads it from, in the order of the CII D16B XSD, using only the standard library's ElementTree.
- **Checks per file**, over all 66 files of the KoSIT suite, CII and UBL:
  1. Read the file, write CII, read the result with Haflinger's reader: same model?
  2. The same with KoSIT's reading stylesheet, which is independent of our mapping.
  3. XML Schema: the full CII D16B XSD (unchanged from KoSIT's validator configuration) and the stricter Factur-X 1.09 EN 16931 XSD (shipped with `factur-x`), checked with `lxml`, in the test group only.
  4. Official rules: EN 16931 and XRechnung, as `haflinger.validate` runs them. Every error must be explained by a business term the model doesn't hold; the test lists those rules.
- **Also run**: the same round trip and XSD check over the ZUGFeRD corpus of the [previous spike](analysis-003-zugferd-corpus-spike.md).

## Results

### Round trip and XML Schema

| Check | Result |
| :- | :- |
| Written file reads back to the same model (Haflinger) | 66 / 66 |
| Written file reads back to the same model (KoSIT stylesheet) | 66 / 66 |
| Valid against the CII D16B XSD | 66 / 66 |
| Valid against the Factur-X EN 16931 XSD | 66 / 66 |
| ZUGFeRD corpus: every invoice Haflinger reads (180) round-trips and is XSD-valid | 180 / 180 |

All passed on the first run. A deliberately swapped element order is rejected by the XSD, so the check bites.

### Official rules

No rule about the values themselves fails: no wrong sums (`BR-CO-10` to `BR-CO-16`), dates, codes or VAT arithmetic for what the model holds. Fourteen rules fail, all because of business terms the model doesn't hold yet:

| Rules | Files | Missing |
| :- | :- | :- |
| `BR-CO-11`, `BR-CO-12` | 6 | BG-20, BG-21: document-level allowances and charges. The model holds their sums (BT-107, BT-108), not the allowances and charges themselves |
| `BR-S-08`, `BR-E-08`, `BR-AE-08` | 2 each | The same: the VAT taxable amount (BT-116) counts allowances and charges |
| `BR-E-01` | 8 | The same: the exempt VAT breakdown exists only for an allowance or charge |
| `BR-DE-1` | 66 | BG-16 payment instructions (XRechnung) |
| `BR-DE-2` | 66 | BG-6 seller contact (XRechnung) |
| `BR-DE-3`, `BR-DE-4`, `BR-DE-8`, `BR-DE-9` | 66 | BT-37, BT-38, BT-52, BT-53: seller and buyer city and post code (XRechnung) |
| `PEPPOL-EN16931-R010`, `-R020` | 66 | BT-49, BT-34: buyer and seller electronic address (Peppol rules in XRechnung 3.0) |

The test lists exactly these, and a second test fails once one no longer fires, so the list shrinks as the model grows.

### Speed

Writing the 66 KoSIT files takes 7 ms together. The large Peppol invoices of the corpus: 25 MB (26,813 lines) in 0.5 s, 61 MB (63,404 lines) in 1.5 s.

## Lessons

- **Yes, writing can rely on the read side.** Round trip, the independent KoSIT reader, the XSD and the rules together found every gap without one line of hand-written expected XML. The test suite tells exactly which business terms are missing and why.
- **The two readers cover each other's blind spots.** A mistake made the same way in our reader and our writer (the same wrong path both ways) passes our own round trip, but not KoSIT's reader. A term that neither the model nor the writer knows passes both round trips; only the rules catch it, and only where a rule requires the term.
- **Reading a subset is fine, writing a subset is not.** The model holds BT-107 and BT-108 but not the allowances and charges they sum up. Reading that is harmless; written, it gives an invoice whose arithmetic the rules reject. The model must be complete for a profile before Haflinger writes that profile.
- **The gap to a valid XRechnung is small and known.** Payment instructions (BG-16), seller contact (BG-6), city and post code (BT-37, BT-38, BT-52, BT-53), electronic addresses (BT-34, BT-49), allowances and charges (BG-20, BG-21). On top of these, the German VAT Act needs more than any rule here forced, because every test file has a VAT ID: the tax number (BT-32) and the delivery date (BT-72) or the invoicing period (BG-14).
- **The writer is the easy part.** About 140 lines, fast, and straightforward because the reader already fixed each path. The work is in the model and, later, in mapping ERPNext's Sales Invoice to it.
- **Vendored files need `-text`.** With `core.autocrlf=input`, Git stored the CRLF XSDs with LF. `.gitattributes` now keeps `tests/data/` and `src/haflinger/artefacts/` byte for byte.

## Not covered

- Writing UBL (not planned, [ADR-003](../../arc42/adr/ADR-003-integrate-dont-implement.md)).
- Validating before returning, and the XSD check outside the tests (`lxml` or `xmlschema` as a runtime dependency; a decision for the validation spec).
- Embedding the XML in a PDF/A-3 (`factur-x` can do it).
- Any ERPNext data.

## Recommended next steps

1. Complete the model for writing XRechnung and ZUGFeRD EN 16931: the terms in the table above, plus BT-32, BT-72 and BG-14, with REQ-001's next version. The excepted rules in the writer test are the checklist.
2. Before writing, check that the model is complete for the target profile (the rules do this anyway; the question is whether `write_cii` refuses or returns findings).
3. Then the ERPNext side: Sales Invoice to the model, which needs its own decision on where it runs ([ADR-001](../../arc42/adr/ADR-001-library-and-app.md)).
