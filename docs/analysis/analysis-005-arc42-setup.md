# Analysis 005: arc42 setup and harvest of the spikes

| Meta | Value |
| :- | :- |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Draft |
| **Audience** | Maintainer; review before the arc42 layout, the ADRs and the specs are written |
| **Purpose** | Phase A of setting up arc42 for Haflinger (assessment before writing), and the list of everything the spikes found, with where it goes |

## 1. Executive Summary

Haflinger has no arc42 yet, three Proposed ADRs and two Draft specs. The spikes left the evidence on four branches and in four analysis files. This analysis proposes a compact arc42 in one file, with Mermaid diagrams. It lists six contradictions between the carried-over docs and what the spikes found. It names six decisions that deserve ADRs (ADR-004 to ADR-009) and ten open questions for the maintainer. The harvest list in section 9 is the checklist for archiving the analysis files and deleting the spike branches: every finding has a destination.

## 2. Context / Motivation

After four spikes on 2026-10-30, the maintainer chose to start fresh from `main`: docs first (arc42 layout, ADRs, specs), then the code rebuilt from the specs, with the spike branches as a quarry. This file is the only output of phase A. The arc42 sections are written in phase B, after review.

**Evidence base.** `main` holds only the project setup. The code these findings rest on is on `spike/cii-writer` (`864fd6e`, plus `c36f7a8` with the spikes' scratch scripts). Paths below refer to that branch. The arc42 layout will cite the same module names, which the rebuild keeps unless a spec changes them.

## 3. Evidence Map

| Aspect | Detected |
| :- | :- |
| Language / framework | Python ≥ 3.14 library, `uv_build`, no Frappe (`pyproject.toml`) |
| Model | `src/haflinger/model.py`: frozen dataclasses, 43 business terms and groups, `Decimal` and `date` |
| Entry points | `read_invoice` (`read.py`, syntax detected from the root element), `write_cii` (`write.py`) |
| Syntax bindings | `cii.py` (read and write, 301 lines), `ubl.py` (read, 147 lines) |
| XML safety | `_xml.py`: `defusedxml` with DTDs forbidden; `Node` access by business term; refusals as `InvoiceReadError` (`errors.py`) |
| Official artefacts | `src/haflinger/artefacts/`: KoSIT visualisation `v2026-10-13` (reading XSLT), KoSIT validator configuration `v2026-08-31` (CEN Schematron 1.3.16, XRechnung 3.0.2), each with a provenance README, 2.9 MB |
| KoSIT reading path | `kosit.py` (spike), via `_saxon.py` |
| Validation | `validate.py` (spike): EN 16931 rules, plus XRechnung rules when BT-24 names XRechnung; SVRL into findings |
| Runtime dependencies | `defusedxml`; `saxonche` (about 105 MB, licence unconfirmed); `factur-x` (used only by `scripts/corpus_report.py` and a test, not by the library) |
| Test dependencies | `pytest`, `lxml` (XSD checks); dev: ruff, basedpyright strict, coverage, mdformat |
| Tests | 603 tests: `tests/unit/`, `tests/conformance/` (KoSIT suite, KoSIT XSLT, writer round trip) |
| Test data | `tests/data/kosit/` (66 files, `v2026-08-31`), `tests/data/cii-d16b/` (UN/CEFACT XSD), both with provenance READMEs; `.gitattributes` keeps them byte for byte |
| Tools | `scripts/corpus_report.py` (ZUGFeRD corpus report); `spike-scratch/` (CEN unit test runner and comparisons, harvest material only) |
| Deployment | None: a package, not published, no container |
| CI/CD | None; the GitHub repository is empty |
| Existing arc42 sections | 0 of 12; 3 ADRs, all Proposed |
| Prior analysis | Analyses 001 to 004 (approach review, KoSIT XSLT, ZUGFeRD corpus, CII writer); harvested in section 9 |

## 4. Section-by-Section Assessment

All twelve sections are missing. Proposed content and its evidence:

| Section | Status | Proposed content | Evidence | Contradictions |
| :- | :- | :- | :- | :- |
| 01 Introduction & Goals | missing | Why Haflinger exists (ERPNext has no complete e-invoicing; ALYF's app is CII-only; Python has no maintained library with a syntax-neutral model); quality goals; stakeholders | Analysis 001, ADR-001, REQ-001 personas | — |
| 02 Constraints | missing | No Frappe in the library; Apache-2.0 library, GPL app; official artefacts unchanged; no network at runtime; installs into a Frappe bench (Python lower bound, few dependencies); German law (accept all EN 16931 formats; sender chooses) | ADR-001 to ADR-003, AGENTS.md | ADR-002's "few dependencies" against saxonche and factur-x (C2) |
| 03 Context & Scope | missing | Library, ERPNext app (later), ERPNext; suppliers and customers, public authorities' portals, Peppol (later); upstream: CEN, KoSIT, OpenPeppol, FeRD, EU code lists (vendored, not called) | ADR-003, guide §11 | — |
| 04 Solution Strategy | missing | One model; integrate, don't implement; receive everything, send CII; library and app; reading path; validation engine; model scope | ADR-001 to ADR-003, ADR-004 to ADR-009 (to write) | ADR-003 names KoSIT's XSLT as the reader (C3) |
| 05 Building Block View | missing | Model; entry points; syntax bindings; KoSIT reading path; validation; XML safety; Saxon runner; artefacts; later PDF and the app | `src/haflinger/` | — |
| 06 Runtime View | missing | Incoming: bytes, PDF extraction, safe parse, syntax detection, read, validate, model with findings, original archived. Outgoing: model, write CII, XSD and rules, PDF/A-3 | Analyses 002 to 004, guide §11 | — |
| 07 Deployment View | missing | A wheel installed into the bench's Python; saxonche native wheels per platform; the app later | `pyproject.toml` | — |
| 08 Cross-cutting Concepts | missing | Hostile input (defusedxml, original bytes to Saxon, size limits, rendering); exact amounts; refusals and findings naming business terms; official files as the reference; vendoring and provenance; editions by BT-24; the original XML is the legal document, the model a derived view | AGENTS.md, analyses 001 to 004 | — |
| 09 Architecture Decisions | missing | One line linking the ADR index | `docs/arc42/adr/README.md` | — |
| 10 Quality Requirements | missing | Quality scenarios with their evidence: KoSIT suite in both syntaxes; round trip; XSD; rules; CEN unit tests; speed figures | Tests, analyses 002 to 004 | — |
| 11 Risks & Technical Debt | missing | Saxon (licence, 105 MB, platform wheels); large invoices (11 min through KoSIT's XSLT for 26 MB); EN 16931-1:2026 and XRechnung 4.0; model completeness for writing; upstream timing; KoSIT's custom rule levels not applied; rendering XSS; rules and tests out of step; single-maintainer libraries | Analyses 001 to 004 | — |
| 12 Glossary | missing | A link to the 101 guide's glossary (domain) and REQ-001's terms (requirements); nothing restated | `docs/guides/e-invoicing-101.md` | — |

**Layout.** One file, `docs/arc42/README.md`, all twelve sections, until a section outgrows it. Twelve files are meant for larger services.

## 5. ADR Hygiene Report

- **ADR index:** three files, three rows, statuses match. The index has no Date column and no link to the arc42 overview.
- **Format consistency:** all three follow the ADR template (Context to References). None has arc42 cross-links ("Affects: §4"); added once arc42 exists.
- **Contradictions with the spikes** (all ADRs are still Proposed, so they are edited in place):
  - **C1.** ADR-001 says the library writes both syntaxes; ADR-003 says outgoing is CII only. ADR-001 also defers `drafthorse` for writing to the writing spec; analysis 004 wrote CII with the standard library in about 140 lines.
  - **C2.** ADR-002 rejects lxml and promises few runtime dependencies; the spikes added `saxonche` (runtime), `factur-x` (runtime, pulling in `lxml`, `pypdf`, `requests`) and `lxml` (tests). Its reconsideration trigger 1 ("Schematron validation needs lxml or Saxon anyway") has fired.
  - **C3.** ADR-003 makes KoSIT's XSLT the reader. Analysis 003 measured 11 minutes for a 26 MB invoice (our mapping: 0.8 s), and analysis 004 showed the value of two independent readers. The reading path needs its own decision (ADR-005).
  - **C4.** ADR-002 holds the rule for vendoring test data, ADR-003 the one for artefacts, and both point at REQ-001 requirements that the hygiene gates will move out of the specs (gate 3). One vendoring ADR should hold it (ADR-008).
  - **C5.** ADR-003 lists `factur-x` for PDFs; nothing in the library uses it yet. Whether PDF extraction is in the library is a REQ-003 question.
  - **C6.** README says "not yet a validator"; the spikes validate. Fixed when README is rewritten after the code.
- **Implicit decisions deserving ADRs** (numbering as proposed earlier):

| ADR | Decision | Evidence |
| :- | :- | :- |
| ADR-004 | How the specs are cut: base spec REQ-001, REQ-002 conformance, REQ-003 incoming, REQ-004 outgoing; no split by syntax or profile | Conversation of 2026-10-30; split criteria for specs |
| ADR-005 | Reading path: our mapping or KoSIT's XSLT as the reader, the other as an independent check | Analyses 002 to 004 |
| ADR-006 | Validation: official Schematron unchanged via Saxon; rule set chosen by syntax, profile and version (BT-24); XSD check and its library; KoSIT's custom rule levels | Analyses 002 to 004 |
| ADR-007 | Model scope and editions: all of EN 16931-1:2017 or as needed; edition-aware by BT-24; extensions | Analyses 001 and 004 |
| ADR-008 | Vendoring official artefacts and test files: pinned, byte for byte, provenance README, update procedure | Analyses 002 and 004, `.gitattributes` |
| ADR-009 | Licences and name: Apache-2.0 library, GPL-3.0 app, licences of vendored material (EUPL-1.2 for CEN, UN/CEFACT, KoSIT), Saxon; the trademark rule from AGENTS.md | ADR-001, analysis 001, the provenance READMEs |

Possibly also: one XML stack (ElementTree with defusedxml, plus Saxon and lxml) as part of ADR-002's revision or ADR-006.

## 6. Diagram Inventory

| Diagram | Location | Format | View type | Covers section |
| :- | :- | :- | :- | :- |
| Eight domain diagrams (layers, bodies, model, syntaxes, CIUS, transport, validation) | `docs/guides/e-invoicing-101.md` | Mermaid | Domain, not architecture | Linked from 01 and 03 |
| Where Haflinger fits (incoming and outgoing flows) | 101 guide §11 | Mermaid | Behavioural | Basis for 06; the guide then links to arc42 |
| Reading through KoSIT's XSLT next to our mapping | Analysis 002 | Mermaid | Behavioural | Basis for 06 (incoming) |

**Missing:** context (03), building blocks (05), runtime incoming and outgoing (06). PlantUML C4 with rendered SVGs would need tooling the repository doesn't have. Proposal: Mermaid flowcharts for all, rendered by GitHub. Mermaid can't be render-checked here (mermaid-cli was blocked earlier); the diagrams are checked by hand.

## 7. Open Questions

| # | Question | Where to confirm | Affects |
| -- | :- | :- | :- |
| 1 | The quality goals and their order. Proposal: 1 correctness (no value lost, changed or guessed), 2 conformance (official artefacts and tests as the reference), 3 safety with hostile input, 4 keeping current with the standards by agents, 5 fitting into a Frappe bench | Maintainer | 01, 10 |
| 2 | Reading path: our mapping as the reader with KoSIT's XSLT as the check (large invoices, two independent readers), or KoSIT's XSLT as the reader with our mapping as the fallback (about 160 terms for free)? | Maintainer, ADR-005 | 04, 05, 06 |
| 3 | Mermaid instead of PlantUML C4, and one arc42 file instead of twelve? | Maintainer | All |
| 4 | Is PDF extraction (`factur-x`) part of the library, with its dependencies (`lxml`, `pypdf`, `requests`), or of the app? | Maintainer, REQ-003, ADR-002 | 02, 05 |
| 5 | Is 105 MB of Saxon acceptable in a Frappe bench, and on which platforms are there wheels? | Check PyPI; maintainer | 02, 07, 11 |
| 6 | The Saxon licence: confirm before relying on it | Saxonica's licence terms for SaxonC-HE | 11, ADR-006, ADR-009 |
| 7 | The XSD check at runtime: lxml (already pulled in by `factur-x`) or `xmlschema` (pure Python)? | ADR-006 | 05 |
| 8 | Outdated versions (XRechnung before 3.0) and code lists that moved on: validate with the rules of their time, or reject with a reason? | Maintainer, REQ-002 | 08 |
| 9 | Where the ERPNext app's requirements go: into REQ-003 and REQ-004 by placement, or a spec of its own (different code base and licence)? | Maintainer, ADR-004 | Specs |
| 10 | The Python version of Frappe/ERPNext v16 benches against `requires-python >= 3.14` | Frappe's docs or a bench | 02 |

**Answered by the maintainer on 2026-10-30:**

- **1:** the quality goals as proposed, correctness first.
- **2:** our own mapping is the reader; KoSIT's XSLT is the independent check in the tests (ADR-005).
- **3:** Mermaid, and one arc42 file.
- **4:** PDF handling is in the library, as an optional extra (`haflinger[pdf]`) that the app requires. Incoming: extracting the XML. Outgoing: the app renders the readable PDF; the library embeds the XML and makes it Factur-X conformant (PDF/A-3, XMP). Reasons: it is format knowledge, which ADR-001 keeps in the library; the main input of German invoices can then be tested without ERPNext; hostile PDFs are handled where hostile XML is; other software can use it under Apache-2.0.

Questions 5 to 10 stay open and move to arc42 §11.

## 8. Proposed Changes (phase B)

### High priority

1. `docs/arc42/README.md` (new): compact arc42, twelve sections in one file, Mermaid diagrams for 03, 05 and 06. Sections 01 to 05, 08 and 11 with content; 06, 07, 10 and 12 short with links; 09 one line to the ADR index. Decisions not yet made (section 7) are marked as open, not stated as fact.
2. `docs/README.md`: an Architecture row in the quick navigation; `arc42/` no longer "comes later"; directories listed.
3. `docs/arc42/adr/README.md`: link to the arc42 overview; add a Date column.

### Medium priority (the ADR step, after phase B)

1. ADR-001: outgoing CII only (C1), the writer with the standard library, the app's licence boundary moved to ADR-009.
2. ADR-002: the dependencies as they are (C2), vendoring moved to ADR-008 (C4).
3. ADR-003: the reader moved to ADR-005 (C3); provenance moved to ADR-008 (C4).
4. ADR-004 to ADR-009 as Proposed.
5. Each ADR gets the arc42 sections it affects under References.

### Low priority

1. 101 guide §11: link to arc42 06 instead of keeping its own status markers ("planned", "done as a draft"), which age.
2. An open-questions list in arc42 §11 or a separate page, once section 7 is answered in part.

## 9. Harvest list

Every finding of the spikes, with its destination. When a row is done it is ticked; when all rows of an analysis are ticked, the analysis moves to `archive/`; when all rows are ticked, the spike branches can go.

### Analysis 001: approach review

- [x] One model for both syntaxes works; the spike is perhaps 5–10 % of Haflinger → arc42 01 (the percentage was a snapshot and is not kept)
- [x] Python has no maintained library with a syntax-neutral model; the Java ecosystem is the most complete → arc42 01, ADR-001 alternatives
- [x] EN 16931-1:2026 (52 new terms, 7 groups, UBL 2.5 and CII D25A, XRechnung 4.0 preview, parallel run until March 2029, edition only in BT-24) → ADR-007, arc42 11, backlog item
- [x] Options A to E for reading and writing → ADR-005 alternatives (E, forking ALYF, is ADR-001 alternative 1)
- [x] Own model versus CII objects as the model; extensions and round trips lose content → ADR-007
- [x] The original XML is the legal document (GoBD), the model a derived view; a readable rendering is needed → arc42 08, REQ-003
- [x] ALYF's dependencies and what the future app may reuse (GPL-3.0: ERPNext mapping, import doctype, Swiss specifics, issues, its bugs as regression tests) → backlog item (ERPNext app), ADR-009
- [x] Test material and licences (KoSIT, CEN, Peppol, ZUGFeRD corpus, FeRD) → REQ-002, ADR-008, ADR-009, backlog item
- [x] KoSIT's CII and UBL pairs aren't independent (built with phax's converter, aligned by hand) → REQ-003-URS-NF001 rationale, ITEM-002
- [x] Java tools as oracles in CI (KoSIT validator, `en16931-cii2ubl`) → ADR-003 (exists), backlog
- [x] Declarative mapping table → ADR-005
- [x] Hybrid PDFs first; credit notes; security beyond XML (PDFs, size limits) → REQ-003
- [x] Keep: spec first, official files as the oracle, small model, refusals naming the term → AGENTS.md (exists), REQ-001
- [x] Change: edition-aware model → ADR-007; lenient reading → REQ-003; one XML stack → ADR-002 or ADR-006

### Analysis 002: KoSIT XSLT spike

- [x] KoSIT's XSLT reads 66/66 files to the same model; about 160 terms and groups; CII and UBL consistent apart from the files' own differences → ADR-005 evidence
- [x] XRechnung's `#XXX#` note convention in UBL is real; KoSIT doesn't decode it → REQ-003 mapping choices
- [x] Differences in the official files (BT-13, sums, addresses, 01.21a, 03.01a, 03.07a) → REQ-002 (how official files are treated), tests, ITEM-006 (upstream reports)
- [x] The rules accept 66/66 files and catch a one-cent error (BR-CO-15, BR-CO-16) → REQ-002 DoD, ADR-006 evidence
- [x] CEN unit tests: 1,131/1,131 with matching rules, 1,066 with KoSIT's bundled 1.3.16 (BR-IG, BR-IP) → ADR-006 evidence; REQ-002 (rules and tests from the same release); backlog item (ITEM-002: vendor CEN unit tests; the runner's location named there). Rechecked in the review: CEN 1.3.16's own tests, 1,131/1,131 against KoSIT's bundled rules
- [x] Speed: compile 0.5 s once, validate 7 ms → ADR-006; read 6 ms per KoSIT file → REQ-003-PRS-NF002 sets 20 ms (the 6 ms figure itself not carried over)
- [x] Saxon: 105 MB, licence unconfirmed → ADR-006, ADR-009, arc42 11
- [x] Give Saxon the original bytes (re-serialising caused 18 false R008 findings) → arc42 08, ADR-006 compliance
- [x] KoSIT's custom rule levels from its scenario file → REQ-002, ADR-006
- [x] Rendering is a security surface (XSS through attachment names, fixed in the latest release) → arc42 8, ITEM-005
- [x] Not covered: EXTENDED, credit notes untested, KoSIT's semantic model is the 2017 one → ADR-005, ADR-007, backlog

### Analysis 003: ZUGFeRD corpus spike

- [x] 176/176 agree where both readers read; every refusal has a cause → ADR-005 evidence
- [x] Read leniently: MINIMUM and BASIC WL arrive without lines → REQ-003
- [x] Recognise ZUGFeRD 1.0 and FatturaPA and say so → REQ-003
- [x] Extraction cases: PDFs without XML, UBL embedded, broken encoding → REQ-003
- [x] Validation by syntax, profile and version; Factur-X Schematron per profile; outdated XRechnung; moved code lists (`EM`) → REQ-002, ADR-006, open question 8
- [x] Large invoices: 26 MB in 0.8 s (ours), 677 s (KoSIT XSLT), 6.7 s (rules); a 61 MB file exists → ADR-005, REQ-003 (limits), arc42 11
- [x] EXTENDED content joined in KoSIT's output (BT-9) → ADR-005
- [x] PDF checks (PDF/A-3, embedded file name, XMP) → ITEM-004, linked from REQ-004
- [ ] The corpus report → development guide (described); `scripts/corpus_report.py` carried over with the code, see below
- [x] A vendored selection of corpus files as regression tests → backlog, ADR-008

### Analysis 004: CII writer spike

- [x] Round trip 66/66 with both readers; XSD 66/66 (CII D16B, Factur-X EN 16931) → REQ-004 DoD; corpus 180/180 (own reader and CII XSD only) → arc42 10 (QS-03)
- [x] Two readers cover each other's blind spots → ADR-005
- [x] The fourteen rules a written invoice breaks, by missing term → REQ-001 (model), REQ-004 DoD
- [x] Reading a subset is fine, writing one is not → ADR-007, REQ-004
- [x] German VAT law needs BT-32 and BT-72 or BG-14 → REQ-001
- [x] The writer with the standard library, about 140 lines → ADR-001 (C1)
- [x] Speed: 66 files in 7 ms, 61 MB in 1.5 s → REQ-004-PRS-NF001 sets 10 ms per file and 5 s for 25.7 MB (the figures themselves not carried over)
- [x] Vendored files need `-text` → ADR-008
- [x] REQ-002 draft's open questions (refuse or validate, validate before returning, default profile) → REQ-004

### Carried-over docs

- [x] REQ-001 draft → REQ-001 core (model, terms, personas, shared rules) and REQ-003 (reading); hygiene gates 3 and 4
- [x] REQ-002 draft (writing CII) → REQ-004
- [x] Backlog → quick items and `item-NNN` files; spec and ADR items removed once written
- [ ] README → rewritten after the code (C6)
- [x] AGENTS.md → docs structure, vendoring rules (ADR-008)
- [x] 101 guide → stays; §11 links to arc42

### Code and data on the spike branches

- [ ] `model.py` → REQ-001
- [ ] `read.py`, `_xml.py`, `errors.py`, `cii.py` and `ubl.py` (reading) → REQ-003
- [ ] `cii.py` (writing), `write.py` → REQ-004
- [ ] `kosit.py` → ADR-005; reader or test oracle
- [ ] `validate.py`, `_saxon.py`, `typings/saxonche.pyi`, `artefacts/` → REQ-002, ADR-006, ADR-008
- [ ] `tests/data/kosit/`, `tests/data/cii-d16b/`, `.gitattributes` → ADR-008
- [ ] Tests: `test_kosit.py` (with `KNOWN_DIFFERENCES`, `ZERO_OR_ABSENT`), `test_kosit_xslt.py`, `test_cii_write.py` (with `MISSING_TERMS`), `test_read.py`, `test_write.py` → the specs' DoD
- [ ] `scripts/corpus_report.py` → development guide
- [ ] `spike-scratch/`: the CEN unit test runner (`cen_units.py`, `cen_units_kosit.py`) → carried over with the code (ITEM-002 names it); the rest is reference only
- [x] `pyproject.toml` dependencies → ADR-002
