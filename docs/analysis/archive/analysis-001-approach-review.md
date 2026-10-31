# Analysis 001: Approach review after the first spike

| Meta | Value |
| :- | :- |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Archived |
| **Audience** | Maintainer; input for the ADRs and specs |
| **Purpose** | Approaches, reuse and test material after the first reading spike |

> Archived on 2026-10-30. Its findings live in the ADRs, specs, architecture, guides and backlog; [analysis 005](../analysis-005-arc42-setup.md) lists where each one went.

After the first spike (REQ-001: reading CII and UBL into an own EN 16931 model, tested against the KoSIT test suite), this note reviews the approach: which alternatives exist, what can be reused, what test material is available, and what the spike missed. Background on the terms: [E-Invoicing 101](../../guides/e-invoicing-101.md).

## Summary

- The spike shows that one model for both syntaxes works and that the official test files make a usable oracle. It is the easy part: perhaps 5–10 % of a usable Haflinger.
- **EN 16931-1:2026** (ratified February 2026, 52 new business terms, new syntax versions) was missed. The model has to know about editions from the start.
- **KoSIT's visualisation** already maps CII and UBL to a neutral semantic model in XSLT. It is a serious alternative, or at least an independent oracle, to our hand-written mapping.
- Far more official test material exists than the spike used, including per-rule unit tests with passing and failing examples.
- Java tools (KoSIT validator, phax's CII-to-UBL converter) are worth using as oracles in CI, without a JVM at runtime.
- The hand-written XPath mapping won't scale; a declarative mapping table should replace it.

## Options for reading and writing

| Option | Idea | For | Against |
| :- | :- | :- | :- |
| **A. Own model and mapping** (the spike) | Python dataclasses for the business terms, a mapping per syntax | Full control, writing and reading on one model, light dependencies | We maintain about 280 mapping rows × 2 syntaxes × 2 editions ourselves |
| **B. KoSIT visualisation XSLT** | Run `cii-xr.xsl`, `ubl-invoice-xr.xsl`, `ubl-creditnote-xr.xsl` with saxonche, read the resulting semantic XML into the dataclasses | KoSIT maintains the mapping with every XRechnung release; covers about 200 terms and groups, credit notes included; Apache-2.0 | Reading only; XRechnung and EN 16931:2017 focus (no ZUGFeRD EXTENDED); Saxon at runtime |
| **C. Java sidecar** | phax (`ph-cii`, `ph-ubl`, `phive`) or Mustang as a service next to Frappe | The most mature implementations, also for 2026 | A JVM to run and secure; a second language |
| **D. Hybrid** | A for the model and writing; B and Java tools as independent oracles in tests | Our own model with checks we don't write ourselves | More moving parts in CI |
| E. Fork ALYF | Restructure European e-Invoice | ERPNext integration exists | GPL-3.0 for everything; CII-bound design to undo |

**Recommendation**: D, decided in an ADR. Check B early: if its coverage is good enough, it may also be the runtime reader, and A shrinks to the model and writing.

## Own model versus CII as the model

EN 16931 is the semantic model; UBL and CII are its two syntaxes. A model of business terms is general by definition: each syntax is one mapping, and the business rules (BR-…) are defined on the same terms. CII is not less expressive: as a full UN/CEFACT schema it holds more than EN 16931, which is why ZUGFeRD EXTENDED uses it.

ALYF's problem is building on CII *objects* (drafthorse): the code follows the XML's structure rather than business meaning, UBL means a mapping from UBL to CII, and rules can't be checked on terms.

Our approach has problems of its own:

- **Extensions get lost**: content beyond EN 16931 (ZUGFeRD EXTENDED, XRechnung extension) disappears in the core model.
- **Editions**: the model knows only EN 16931-1:2017.
- **Round trips** lose what the model doesn't hold.
- **Maintenance** of the mapping is ours.

Mitigation: the original XML stays the legal document and is archived unchanged; the model is a derived view, never the source for re-creating an incoming invoice.

## ALYF's European e-Invoice

### Its dependencies

| Library | Purpose | Licence | For Haflinger |
| :- | :- | :- | :- |
| `factur-x` (Akretion) | Extract XML from PDF; PDF/A-3 with embedded XML | BSD-3-Clause | Yes, for ZUGFeRD |
| `drafthorse` (pretix) | CII object model, read and write | Apache-2.0 | Only if we write CII through it; ties to CII structure |
| `saxonche` (Saxonica) | XSLT 3 for Schematron | open source (HE) | Yes, for validation, possibly option B |
| `lxml` | XML processing | BSD | Probably, once Saxon is in |

It also vendors Schematron XSLT (CEN EN 16931 CII, Factur-X 1.07.2 BASIC and EXTENDED, XRechnung CII) and the EU code lists (genericode, public domain). We take both from their sources. Its `main` targets Frappe/ERPNext 17-dev.

### What we can reuse

The app is **GPL-3.0**: nothing goes into the Apache-2.0 library. The future ERPNext app will be GPL-3.0 and may reuse code, with attribution.

- The ERPNext mapping: custom fields, tax rows, code lists mapped to tax categories, templates and accounts.
- The import doctype and its matching of suppliers and items.
- The Swiss specifics (`switzerland.py`).
- Its issue tracker, as a source of real user problems.
- Its known bugs as regression tests: Skonto never written, BT-114 never written, profile detection by exact string.

It has no official test files in its repository.

## Other libraries and frameworks

| Language | Project | Scope | Licence |
| :- | :- | :- | :- |
| Java | phax: `ph-cii`, `ph-ubl`, `en16931-cii2ubl`, `phive` and `phive-rules`, `phase4`, `phoss-smp` | Syntax libraries, CII-to-UBL for both editions, validation engine, Peppol AS4 and SMP | Apache-2.0 |
| Java | KoSIT validator and its XRechnung configuration | The reference validator for XRechnung | Apache-2.0 |
| Java | Mustangproject | ZUGFeRD read, write, validate | Apache-2.0 |
| XSLT | KoSIT `xrechnung-visualization` | CII and UBL to a semantic model, then HTML or PDF | Apache-2.0 |
| .NET | ZUGFeRD-csharp | ZUGFeRD read and write | Apache-2.0 |
| PHP | horstoeko/zugferd | ZUGFeRD read and write | MIT |
| Go | speedata/einvoice | ZUGFeRD / XRechnung read and write | (to check) |
| Python | `drafthorse`, `factur-x`, `pycheval` 0.3, `en16931` 0.2 | CII objects; PDF; a young reader/writer; an old, unmaintained one | Apache-2.0, BSD, (to check) |

Python has no mature library with a neutral model for both syntaxes: a gap Haflinger can fill. The Java ecosystem is the most complete and the closest to the standards bodies (phax maintains Peppol and CEN tooling); KoSIT's own tools are Java and XSLT.

**Recommendation**: Java tools as oracles in CI (the KoSIT validator checks everything we write; `en16931-cii2ubl` cross-checks our CII-to-UBL path), Python with saxonche at runtime.

## Test material

| Source | Content | Format | Licence |
| :- | :- | :- | :- |
| KoSIT `xrechnung-testsuite` | 33 standard business cases in CII and UBL (used by the spike); 6 extension cases; technical cases (comprehensive, minimal, CVD) | Complete invoices | Apache-2.0 |
| CEN `eInvoicing-EN16931` | 206 UBL invoice and 71 UBL credit note unit tests, a few CII; 19 UBL and 15 CII examples | Unit tests per business rule in VEFA `testSet` format: `<success>BR-20</success>` and `<error>BR-20</error>` examples | EUPL-1.2 |
| Peppol `peppol-bis-invoice-3` | `unit-UBL-PEPPOL` (63), `unit-CII-PEPPOL` (47), national rules (e.g. `unit-UBL-DE`, 28), examples and snippets | VEFA `testSet` | (to check) |
| KoSIT `validator-configuration-xrechnung` | CEN unit tests, instances, unexpected inputs | Mixed | Apache-2.0 |
| `ZUGFeRD/corpus` | 251 real, sample and test invoices, PDFs included, with `fail/` folders of deliberately broken ones | Files | Apache-2.0 |
| FeRD ZUGFeRD package | Official samples per profile | PDF and XML | (to check; download from FeRD) |

Limits: the unit tests are made for validators; they contain fragments, not complete invoices. For a reader they show robustness; they test Haflinger directly once it writes or checks rules. EUPL test files keep their own licence note in `tests/data/`.

Generated tests on top: round trips (read, write, read), differential tests against `en16931-cii2ubl` and option B, and the KoSIT validator over everything we write.

The KoSIT suite's CII and UBL pairs are not fully independent: KoSIT's build uses phax's CII-to-UBL converter, and the pairs were aligned by hand. A third mapping (option B) makes REQ-001-PRS-F004 a stronger check.

## What the spike missed

- **EN 16931-1:2026.** Ratified February 2026, English version since March 2026; 52 new business terms and 7 groups; syntax bindings and CEN validation artefacts pending (phax implements UBL 2.5 and CII D25A ahead of them). XRechnung 4.0 preview since September 2026, final expected 2027. Parallel run of both editions until March 2029 as planned. The edition is only recognisable from BT-24.
- **Hybrid PDFs first.** Most German SME invoices arrive as ZUGFeRD PDFs; extracting the XML with `factur-x` is cheap and valuable.
- **Legal original.** The XML is the invoice to archive (GoBD); a readable rendering is needed, and KoSIT's visualisation provides one.
- **Credit notes**: UBL has its own root, CII uses type code 381.
- **Security** beyond XML: untrusted PDFs, size limits.
- **Test data licences**: EUPL for the CEN files.

## Assessment of the current approach

**Keep:**

- Spec first, the official files as the oracle, tests without Frappe.
- A small model with `Decimal`, frozen dataclasses.
- Refusals that name the business term.
- The spike found real inconsistencies in the official files within half an hour: the feedback loop agents need.

**Change:**

- **Declarative mapping.** A table from business term to CII path and UBL path, per edition, ideally derived from the official binding tables; easier for agents to check and to diff when the standard changes.
- **Edition-aware model**, now while it is small.
- **Lenient reading, separate validation.** Refusing a missing required term while reading is too strict for incoming invoices; read what is there, then validate and report.
- **One XML stack.** If saxonche and lxml come for validation, reconsider ElementTree with defusedxml.
- **ADR-001** doesn't weigh option B or Java oracles; revise it once they are assessed.

## Next steps

1. Assess option B: run the KoSIT visualisation XSLT over the test suite with saxonche and compare its semantic XML with our model.
2. ADR: reading and writing approach (A, B, D), with the edition question.
3. Make the model edition-aware and the mapping declarative.
4. Add the technical and extension cases of the KoSIT suite; then the CEN and Peppol examples.
5. ZUGFeRD PDF extraction with `factur-x`.

## References

- [alyf-de/eu_einvoice](https://github.com/alyf-de/eu_einvoice)
- [itplr-kosit/xrechnung-visualization](https://github.com/itplr-kosit/xrechnung-visualization), [itplr-kosit/xrechnung-testsuite](https://github.com/itplr-kosit/xrechnung-testsuite), [itplr-kosit/validator-configuration-xrechnung](https://github.com/itplr-kosit/validator-configuration-xrechnung)
- [ConnectingEurope/eInvoicing-EN16931](https://github.com/ConnectingEurope/eInvoicing-EN16931), [OpenPEPPOL/peppol-bis-invoice-3](https://github.com/OpenPEPPOL/peppol-bis-invoice-3), [ZUGFeRD/corpus](https://github.com/ZUGFeRD/corpus)
- [phax/en16931-cii2ubl](https://github.com/phax/en16931-cii2ubl)
- KoSIT: [EN 16931 status and XRechnung 4.0](https://xeinkauf.de/aktuelles/xse/en-16931-aktueller-stand-und-ausblick-auf-die-einfuehrung-der-xrechnung-4-0/)
- Secondary sources on EN 16931-1:2026: [cosinex](https://blog.cosinex.de/2026/09/16/xrechnung-4-0-vorabversion-en-16931/), [eu-einvoicing.com](https://www.eu-einvoicing.com/news/en-16931-2026-update-xrechnung-4-zugferd-25-explained)
