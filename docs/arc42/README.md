# Haflinger architecture

Compact [arc42](https://arc42.org/): all twelve sections in this file, until one of them outgrows it. It describes the design that the requirement specifications ([index](../specs/README.md)) and the [ADRs](adr/README.md) set out. Where the code disagrees, the code wins and this file is fixed.

**State:** the modules named here are built on `main`, rebuilt from the specs after the spikes that proved the approach; section 5 says where a block is still incomplete.

Diagrams are Mermaid, rendered by GitHub. Background on the standards, formats and bodies: [E-Invoicing 101](../guides/e-invoicing-101.md).

## 1. Introduction and goals

Haflinger is a Python library for e-invoicing (ZUGFeRD, XRechnung, Peppol), `haflinger`, that holds one model of the EN 16931 business terms. It reads invoices in CII and UBL and from ZUGFeRD PDFs, validates them with the official rules, and writes CII and ZUGFeRD PDFs. Any Python software can build on it. The first is a slim ERPNext app, later and in its own repository, that maps ERPNext's sales and purchase invoices to and from the model; this document describes the library.

Why it exists: ERPNext, its first user, has no complete e-invoicing. ALYF's European e-Invoice app is bound to CII, without UBL or Peppol ([ADR-001](adr/ADR-001-library-and-app.md)). Python has no mature library with a syntax-neutral model; the mature tools are Java.

### Quality goals

| # | Goal | Meaning |
| :- | :- | :- |
| 1 | **Correctness** | No value of an invoice is lost, changed or guessed, on the way in or out. Amounts stay exactly as written. What can't be read is refused or reported, never filled in. |
| 2 | **Conformance** | The official rules and test files decide what is right, not our reading of the standard. Haflinger runs them unchanged. |
| 3 | **Safety with hostile input** | Incoming invoices come from anyone. Neither XML nor PDF can make Haflinger fetch, expand or execute anything. |
| 4 | **Keeping current** | New releases of the standards, rules and test files are adopted mostly by agents, as a version bump and a test run. |
| 5 | **Fit into other software** | The library installs into its host's Python environment next to the versions the host pins, with few dependencies. The first host is a Frappe bench. |

### Stakeholders

| Who | Expects |
| :- | :- |
| Operator (runs the books in software built on Haflinger, ERPNext first) | Invoices in any format handled the same way; nothing wrong reaching the books unnoticed |
| Maintainer (keeps Haflinger current, usually an agent with a person reviewing) | Official test files as the reference; behaviour checkable without an ERP system |
| Integrator (the ERPNext app, other software built on the library) | One typed model independent of the syntax; refusals and findings that say what is wrong |
| Suppliers and customers | Their invoices accepted in the format they chose; Haflinger's invoices accepted by their software |
| Public authorities | XRechnung that passes their portals' validation (BT-10 Leitweg-ID, XRechnung rules) |
| Tax auditor | The original invoice archived unchanged, the booking traceable to it |
| Standards bodies (CEN, KoSIT, OpenPeppol, FeRD) | Not stakeholders who expect anything of Haflinger, but its upstream: their release cycles set its pace |

The first three are the personas of [REQ-001](../specs/req-001-core.md#personas).

## 2. Constraints

| Constraint | Source |
| :- | :- |
| Syntax and format knowledge lives only in the library; knowledge of one ERP system (the ERPNext mapping) lives in the software that uses it, outside this repository | [ADR-001](adr/ADR-001-library-and-app.md) |
| Python at runtime, no JVM; Java tools at most as oracles in CI | [ADR-001](adr/ADR-001-library-and-app.md), [ADR-003](adr/ADR-003-integrate-dont-implement.md) |
| Official artefacts (rules, mappings, code lists) and test files are used unchanged, pinned to a release, with their provenance | [ADR-003](adr/ADR-003-integrate-dont-implement.md); [ADR-008](adr/ADR-008-vendoring-official-files.md) |
| German law: a business must accept every EN 16931 invoice, in CII, UBL or as ZUGFeRD; the sender chooses the format | [101 guide §10](../guides/e-invoicing-101.md#10-the-law-briefly), [ADR-003](adr/ADR-003-integrate-dont-implement.md) |
| Installs next to the versions its host pins, a Frappe bench first: a lower bound on Python, few runtime dependencies, PDF support as an optional extra | [ADR-002](adr/ADR-002-toolchain.md) |
| Reading XML and PDFs needs no network and resolves nothing external; outside input has a size limit | [REQ-001](../specs/req-001-core.md) |
| Apache-2.0 for the library; the ERPNext app is GPL-3.0 in its own repository; "ERPNext" and "Frappe" not in the project or package name | [ADR-009](adr/ADR-009-licences-and-name.md), [AGENTS.md](../../AGENTS.md) |
| Nothing specific to one company in the repository | [AGENTS.md](../../AGENTS.md) |

## 3. Context and scope

```mermaid
flowchart LR
    supplier(["Suppliers"])
    customer(["Customers,<br/>public authorities"])
    caller["Calling software:<br/>the ERPNext app (later),<br/>other software"]
    lib["haflinger<br/>library"]
    upstream["CEN, KoSIT, OpenPeppol, FeRD,<br/>EU code lists"]

    supplier -- "XML or PDF:<br/>e-mail, upload, Peppol" --> caller
    caller -- "bytes in, model and findings out" --> lib
    caller -- "model in, CII or PDF out" --> lib
    caller -- "XML or PDF:<br/>e-mail, portal, Peppol" --> customer
    upstream -. "releases, vendored<br/>at update time" .-> lib
```

| Interface | Direction | What |
| :- | :- | :- |
| Library API | caller → library | Python calls: read an invoice from bytes, write the model as CII, validate; PDF in and out with the `pdf` extra. Defined by [REQ-001](../specs/req-001-core.md), [REQ-002](../specs/req-002-conformance.md), [REQ-003](../specs/req-003-incoming-invoices.md) and [REQ-004](../specs/req-004-outgoing-invoices.md) |
| Official artefacts | upstream → repository | Rules, reading stylesheets and test files, taken from upstream releases at update time and vendored; nothing is fetched at runtime |
| Transport | caller ↔ suppliers and customers | Not the library's: e-mail, portals, and Peppol through a certified provider; no AS4 of Haflinger's own ([ADR-003](adr/ADR-003-integrate-dont-implement.md)) |

**Out of scope:** sending and receiving e-mail and Peppol messages (the caller, providers); archiving storage (the caller; Haflinger hands back the original bytes); bookkeeping decisions (a person, in the caller's system); the ERPNext app and its context, described in its own repository ([ITEM-003](../backlog/item-003-erpnext-app.md) until it exists); rendering invoices for people (later, with KoSIT's visualisation stylesheets, [ITEM-005](../backlog/item-005-rendering.md)).

## 4. Solution strategy

| Goal | Approach | Decision or requirement |
| :- | :- | :- |
| Correctness | One model of the EN 16931 business terms for every syntax; `Decimal` exactly as written; refuse or report instead of guessing | [ADR-001](adr/ADR-001-library-and-app.md), [REQ-001](../specs/req-001-core.md) |
| Correctness | Our own mapping reads; KoSIT's reading stylesheet reads the same files independently in the tests, so a mistake made the same way in our reader and writer still shows | [ADR-005](adr/ADR-005-own-mapping-kosit-as-check.md) |
| Conformance | The official Schematron runs unchanged with Saxon; the rule set is chosen by syntax, profile and version from BT-24 | [ADR-003](adr/ADR-003-integrate-dont-implement.md); [ADR-006](adr/ADR-006-validation-with-official-rules.md) |
| Conformance | The official test suites are the oracle, unchanged; where an official file looks wrong, the test records the exception with a reason | [AGENTS.md](../../AGENTS.md); [REQ-002](../specs/req-002-conformance.md) |
| Safety | XML parsed without DTDs and entities before anything else sees it, also when embedded in a PDF; every input limited in size | [REQ-001](../specs/req-001-core.md); [REQ-003](../specs/req-003-incoming-invoices.md); [§8](#8-cross-cutting-concepts) |
| Keeping current | Integrate, don't implement: what the standards bodies maintain is used, not rewritten; artefacts vendored per release | [ADR-003](adr/ADR-003-integrate-dont-implement.md); [ADR-008](adr/ADR-008-vendoring-official-files.md) |
| Keeping current | The model knows editions (EN 16931-1:2017 and :2026) by BT-24; its scope grows by what the specs need | [ADR-007](adr/ADR-007-model-scope-and-editions.md) |
| Fit into other software | No ERP code, few dependencies, PDF as an extra | [ADR-001](adr/ADR-001-library-and-app.md), [ADR-002](adr/ADR-002-toolchain.md) |
| All | Receive everything EN 16931 allows; send CII only, as ZUGFeRD EN 16931 or XRechnung 3.0 | [ADR-003](adr/ADR-003-integrate-dont-implement.md), [REQ-004](../specs/req-004-outgoing-invoices.md) |

How the requirements are cut into specs: [ADR-004](adr/ADR-004-specs-by-direction.md).

## 5. Building block view

```mermaid
flowchart TB
    subgraph lib["haflinger"]
        api["read / write / validate<br/>entry points"]
        model["model<br/>EN 16931 business terms"]
        safe["_xml<br/>safe parsing, access by business term"]
        cii["cii<br/>read and write"]
        ubl["ubl<br/>read"]
        validate["validate<br/>rules into findings"]
        xsd["XSD check<br/>(lxml)"]
        kosit["kosit<br/>KoSIT reading path"]
        saxon["_saxon<br/>talks to the worker, time limit"]
        worker["_worker (own process)<br/>runs official XSLT with Saxon"]
        artefacts[("artefacts<br/>vendored rules and stylesheets")]
        pdf["pdf (extra)<br/>extract and embed XML"]
    end
    caller["calling software"]
    tests["tests: official suites,<br/>round trip, XSD"]

    caller --> api
    api --> safe
    api --> cii & ubl
    api --> validate
    api --> xsd
    api -.-> pdf
    validate --> safe
    validate --> xsd
    cii & ubl --> model
    cii & ubl --> safe
    validate --> saxon
    kosit --> saxon
    saxon -- "text over pipes" --> worker
    worker --> artefacts
    tests -. "check our readers against" .-> kosit
```

| Block | Responsibility | State |
| :- | :- | :- |
| entry points (`read_invoice`, `write_cii`, `validate`) | Check size and safety, detect the syntax from the root element, dispatch, hand back a model with findings, a document, findings, or a refusal | Built |
| `model` | The business terms as frozen dataclasses with `Decimal` and `date`, each field mapped to its BT or BG ID by REQ-001; equal invoices compare equal whatever their syntax | Built: the terms REQ-001-PRS-F001 lists, growing by ADR-007 |
| `_xml` | Parse outside XML with `defusedxml`; read elements by path, with `HAFL-VALUE` and `HAFL-DROPPED` findings that name the business term | Built |
| `cii`, `ubl` | The syntax bindings: each business term read from the element EN 16931-3-3 (CII) or -3-2 (UBL) assigns it, CII also written | Built |
| `validate` | Choose the rule set, check the invoice against the rule set's XML Schema, run the rules on a schema-valid invoice, turn the SVRL report into findings (rule, flag, location, text) | Built: KoSIT's scenarios with their levels (EN 16931, XRechnung 3.0, its extension, CVD); FeRD's Factur-X rules (MINIMUM, BASIC WL, BASIC, EXTENDED, and EN 16931 for written invoices), compiled with SchXslt on first use |
| XSD check | Check an incoming invoice against the XML Schema of its rule set before the rules, and a written invoice against the CII and Factur-X XML Schemas | Built, with lxml ([ADR-006](adr/ADR-006-validation-with-official-rules.md)): on `validate`, on the text as decoded for Saxon, CII D16B, UBL 2.1 Invoice and CreditNote, and FeRD's schema of each Factur-X profile (MINIMUM, BASIC WL, BASIC, EXTENDED); on writing, on the bytes as a recipient parses them, CII D16B and Factur-X's EN 16931 profile for that target |
| `kosit` | Read through KoSIT's stylesheet into the same model; the tests' independent second reader | Built; agrees with `read_invoice` on the KoSIT suite, CEN's UBL credit note and the vendored corpus PDFs |
| `_saxon` | Start the worker process on first use and keep it; a helper thread alone talks to it, taking the calls' requests in turn, so that a signal in a caller never interrupts an exchange; send it the document, decoded once in Python, and the stylesheets' names; enforce the time limit, killing the worker when it passes; replace a worker that died; log its stderr | Built ([ADR-010](adr/ADR-010-saxon-in-a-worker-process.md)); never imports `saxonche` |
| `_worker` | A process of its own: compile each stylesheet once, run it on the document, reply with each output as text | Built; the only module that imports `saxonche`; Saxon opens only local files |
| `artefacts` | KoSIT's visualisation stylesheets (the reading stylesheet) and validator stylesheets, unchanged, with provenance READMEs | Vendored: KoSIT's visualisation and validator configuration, FeRD's Factur-X Schematron and XML Schemas, SchXslt |
| `pdf` | Extract the XML from a ZUGFeRD PDF without parsing it; embed checked XML into a PDF/A file the caller rendered (PDF/A-3, XMP), via `factur-x` | Built, extra `pdf`: `extract_xml` inflates against the size limit itself, within limits on the tree of embedded files, on the streams it decodes and on its time (3 s); `embed` writes the EN 16931 profile, with the relationship `Alternative` |

Which spec owns which block: the placement map in the [specs index](../specs/README.md).

## 6. Runtime view

### Receiving an invoice

```mermaid
sequenceDiagram
    participant A as Caller
    participant H as haflinger
    participant S as Worker: Saxon with official rules
    A->>H: read_invoice(bytes: XML or PDF)
    H->>H: check the size limit
    opt PDF, with the pdf extra
        H->>H: extract the embedded XML, within the size limit
    end
    H->>H: parse safely (no DTD, no entities), detect syntax and edition
    H->>H: read into the model with our mapping
    H-->>A: model and reading findings, or a refusal naming the problem
    A->>H: validate(XML bytes)
    H->>H: check the size limit, parse safely, choose the rule set by syntax, profile and version
    H->>H: XML Schema of the rule set (lxml, ADR-006)
    opt schema-valid
        H->>S: the decoded text, the rule set's stylesheets
        S-->>H: report of failed rules, within the time limit
    end
    H-->>A: findings
    A->>A: archive the original unchanged, show to a person
```

When the rules don't end within the time limit, the worker is killed and the call refused; the next call starts a new worker (REQ-002-PRS-NF004). An incomplete invoice is read with what it holds, and the rules report the rest. Reading reports what it couldn't take into the model; it doesn't validate, and no finding stops an invoice from being read ([REQ-003-PRS-F008](../specs/req-003-incoming-invoices.md#req-003-prs-f008-findings-on-incoming-invoices)). What is refused is listed in [REQ-003-PRS-F006](../specs/req-003-incoming-invoices.md#req-003-prs-f006-refusals).

### Sending an invoice

```mermaid
sequenceDiagram
    participant A as Caller
    participant H as haflinger
    participant S as Worker: Saxon with official rules
    A->>H: write_cii(model)
    H->>H: check the target profile and the values
    H->>H: write CII
    H->>H: XML Schema check (lxml, ADR-006)
    H->>S: written bytes, rules for the target profile
    S-->>H: findings
    alt fatal or error findings
        H-->>A: InvoiceWriteError: findings and the written document
    else valid
        opt ZUGFeRD
            A->>H: embed(PDF/A the caller rendered, XML)
            H->>H: check the XML again, embed it, PDF/A-3, XMP metadata
        end
        H-->>A: CII or ZUGFeRD PDF
        A->>A: send by e-mail, portal or Peppol
    end
```

An invalid invoice is refused with its findings and the written document; a model that can't be written at all (an unsupported profile, a value of the wrong type) is refused before writing ([REQ-004-PRS-F001](../specs/req-004-outgoing-invoices.md#req-004-prs-f001-one-entry-point)). Rendering the readable PDF as PDF/A is the caller's job (for ERPNext: [ITEM-003](../backlog/item-003-erpnext-app.md)).

## 7. Deployment view

The library is a Python package installed into the caller's Python environment. No service, no container, no network at runtime. Validation starts one worker process per calling process, from the same environment, and keeps it: about 160 MB with a rule set compiled, while the caller holds no Saxon ([ADR-010](adr/ADR-010-saxon-in-a-worker-process.md)). The worker's pipes need a POSIX system (Linux, macOS). The first host is a Frappe bench, where the ERPNext app and the library share one environment, so the library's dependencies have to fit the versions the bench pins ([ADR-002](adr/ADR-002-toolchain.md)).

```mermaid
flowchart LR
    subgraph env["The caller's Python environment<br/>(first: a Frappe bench)"]
        subgraph proc["calling process"]
            caller["calling software"]
            lib["haflinger[pdf]"]
            lxml["lxml<br/>(native wheel)"]
            facturx["factur-x, pypdf<br/>(extra pdf)"]
        end
        subgraph wproc["worker process"]
            worker["haflinger._worker"]
            saxon["saxonche<br/>(native wheel)"]
        end
    end
    caller --> lib
    lib --> lxml
    lib -.-> facturx
    lib -- "starts, pipes" --> worker --> saxon
```

Nothing is released yet; the name is reserved on PyPI ([backlog](../backlog/backlog.md)). `saxonche` is a native wheel per platform; which platforms it covers, and its size, are in [ADR-006](adr/ADR-006-validation-with-official-rules.md).

## 8. Cross-cutting concepts

- **Hostile input:** XML is parsed with `defusedxml`, DTDs forbidden, before any other component sees it, also XML embedded in a PDF. Saxon, in its worker process, and lxml's check of an incoming invoice then get the document as received, decoded once in Python and held as text in memory, never a re-serialised tree or a file; Saxon opens only local files ([ADR-006](adr/ADR-006-validation-with-official-rules.md)). Every input, and every file unpacked from a PDF, has a size limit (REQ-001); looking for the invoice in a PDF is bounded too, in the entries of its tree of embedded files, in the bytes of the streams it decodes on the way, and in time: it stops after 3 s, which no ZUGFeRD PDF comes near (REQ-003). The official rules run within a time limit, in a worker process that is killed when it passes, so that neither a slow invoice nor a crash in Saxon holds or ends the caller's process (REQ-002-PRS-NF004, REQ-002-PRS-NF005). Rendering for people, later, needs the current KoSIT release, which fixed script injection through attachment names.

- **Exact values:** amounts, quantities, prices and rates are `Decimal` exactly as written, in XML Schema's decimal form; dates are `date`. Nothing is rounded on reading or on writing; the writer writes the digits the model holds. REQ-001 names the only three exceptions (whitespace and the notation of numbers on reading, exponent notation on writing).

- **Business terms as names:** each model field maps to its BT or BG ID; refusals name the business term, findings the rule ID (`BR-CO-15`). Haflinger's own findings have IDs starting `HAFL-`, all defined in REQ-002: `HAFL-PROFILE`, `HAFL-XSD`, `HAFL-RULES` (the official rules failed on a schema-valid invoice), `HAFL-VALUE` and `HAFL-DROPPED`.

- **The original is the invoice:** the bytes received are the legal document to archive (GoBD). The model is a derived view, never the source for re-creating an incoming invoice. Content beyond the model (extensions, terms not modelled yet) stays in the original.

- **Official files as the reference:** behaviour is tested against the official suites and never adjusted by editing a file. A difference in the official files themselves is recorded in the test with the business term and the reason, and a further test fails once a new release removes it.

- **Vendoring:** official artefacts and test files are kept byte for byte (`.gitattributes`), pinned to a release, each with a README naming source, release, commit and licence. Rules and the tests that check them come from the same release; otherwise version drift looks like defects ([ADR-008](adr/ADR-008-vendoring-official-files.md)).

- **Editions, profiles, versions:** BT-24 tells which EN 16931 edition, which profile and which version an invoice follows; reading and validation choose by it ([ADR-006](adr/ADR-006-validation-with-official-rules.md), [ADR-007](adr/ADR-007-model-scope-and-editions.md)).

- **Testing:** unit tests per block; conformance tests over the official suites: CII and UBL agree, our reader and KoSIT's agree, written invoices read back unchanged and pass the XML Schema and the rules. Details per scenario in §10.

## 9. Architecture decisions

See the [ADR index](adr/README.md).

## 10. Quality requirements

The quality goals of section 1, made testable. The requirement column names the requirement that holds the test; the figures were measured on 2026-11-01 (Apple aarch64, Python 3.14.10) by the tests and `scripts/benchmark.py` ([development guide](../guides/development.md#running-the-zugferd-corpus)).

### Correctness

| ID | Scenario | Response and measure | Requirement |
| :- | :- | :- | :- |
| QS-01 | The same invoice arrives in CII and in UBL | The same model, for every business case of the KoSIT suite; differences in the official files listed with their reason | [REQ-003-PRS-F004](../specs/req-003-incoming-invoices.md#req-003-prs-f004-cii-and-ubl-agree) |
| QS-02 | An amount has more decimal places than its currency | Read and written back unchanged | [REQ-001-PRS-F004](../specs/req-001-core.md#req-001-prs-f004-exact-values) |
| QS-03 | Haflinger writes an invoice read from an official file | Our reader and KoSIT's both read it back to the same model; valid against the XML Schemas; measured: 86 of 86 KoSIT files with both readers, the CII D16B XML Schema and Factur-X's EN 16931 XML Schema | [REQ-004-PRS-F006](../specs/req-004-outgoing-invoices.md#req-004-prs-f006-round-trip-over-the-kosit-suite) |
| QS-04 | An invoice total is off by one cent | Validation reports `BR-CO-15` and `BR-CO-16` as fatal | [REQ-002-PRS-F002](../specs/req-002-conformance.md#req-002-prs-f002-findings) |
| QS-11 | An invoice repeats a value the model holds once (two due dates) | The first is read, the second reported with `HAFL-DROPPED`; no value of a term the model holds is left out without a finding | [REQ-003-PRS-F002](../specs/req-003-incoming-invoices.md#req-003-prs-f002-reading-choices) |

### Conformance

| ID | Scenario | Response and measure | Requirement |
| :- | :- | :- | :- |
| QS-05 | CEN's per-rule unit tests run against the rules of the same release | Every expected pass and failure met; measured: all 1,140 tests of CEN 1.3.16 (1,131 UBL, 9 CII), the release of the rules in KoSIT's configuration, with those rules | [REQ-002-PRS-F007](../specs/req-002-conformance.md#req-002-prs-f007-official-verdicts-reproduced) |
| QS-06 | KoSIT, CEN or FeRD publishes a new release | One pull request updates the vendored files; the tests show what changed | [REQ-002-PRS-NF003](../specs/req-002-conformance.md#req-002-prs-nf003-traceable-to-a-release), [ADR-008](adr/ADR-008-vendoring-official-files.md) |

### Safety with hostile input

| ID | Scenario | Response and measure | Requirement |
| :- | :- | :- | :- |
| QS-07 | An XML file declares a DTD or an entity, also inside a PDF | Refused before any stylesheet or reader sees it | [REQ-001-PRS-NF001](../specs/req-001-core.md#req-001-prs-nf001-outside-input) |
| QS-12 | A small PDF carries an embedded file that inflates to gigabytes | Refused once the unpacked XML passes the size limit | [REQ-003-PRS-NF001](../specs/req-003-incoming-invoices.md#req-003-prs-nf001-embedded-files-within-the-limit) |
| QS-13 | A crafted invoice makes the official rules run for minutes | Refused when the time limit passes, the worker killed and replaced, the caller's process unaffected; measured: 16,000 distinct `cbc:PaymentID` (about 5 s of rules) refused within 1.5 s at a limit of 0.5 s | [REQ-002-PRS-NF004](../specs/req-002-conformance.md#req-002-prs-nf004-time-limit) |

### Speed

Speed serves conformance: every invoice, received or sent, is validated.

| ID | Scenario | Response and measure | Requirement |
| :- | :- | :- | :- |
| QS-08 | A 25.7 MB invoice with 26,813 lines arrives or is sent | Measured: reading 1.0 s with our mapping (KoSIT's stylesheet: 11 minutes in the spikes, which is why it is not the reader), validating 7.6–8.2 s with the XML Schema check first, writing 0.8 s; the 61.1 MB invoice read in 2.5 s (2026-10-31) and validated in 18.5–18.6 s, of which the XML Schema check takes 0.5 s (1.75–1.92 GiB peak memory); the first validation in a process, compiling its rules included, 0.17–0.29 s for KoSIT's scenarios, 0.09 s for Factur-X MINIMUM and 1.05 s for Factur-X EXTENDED; with the worker process (2026-11-02), the first validation of KoSIT's CII case 01.01a 0.31 s, starting the worker included, and each after it 5 ms | [REQ-002-PRS-NF002](../specs/req-002-conformance.md#req-002-prs-nf002-speed), [REQ-003-PRS-NF002](../specs/req-003-incoming-invoices.md#req-003-prs-nf002-speed), [REQ-004-PRS-NF001](../specs/req-004-outgoing-invoices.md#req-004-prs-nf001-speed) |

### Keeping current

| ID | Scenario | Response and measure | Requirement |
| :- | :- | :- | :- |
| QS-09 | An invoice of EN 16931-1:2026 arrives | Recognised by its edition from BT-24 and refused, naming the edition, until Haflinger supports it; never read as a 2017 invoice | [REQ-001-PRS-F003](../specs/req-001-core.md#req-001-prs-f003-edition), [REQ-002-PRS-F009](../specs/req-002-conformance.md#req-002-prs-f009-editions-supported), [ADR-007](adr/ADR-007-model-scope-and-editions.md) |

### Fit into other software

| ID | Scenario | Response and measure | Requirement |
| :- | :- | :- | :- |
| QS-10 | `haflinger` is installed into a Frappe bench, its first host | No Frappe import; without the `pdf` extra, no PDF dependencies | [REQ-001-PRS-NF002](../specs/req-001-core.md#req-001-prs-nf002-no-frappe), [ADR-002](adr/ADR-002-toolchain.md) |

## 11. Risks and technical debt

| Risk | Mitigation |
| :- | :- |
| Saxon: large, native, licence not yet confirmed ([ADR-006](adr/ADR-006-validation-with-official-rules.md)) | [ADR-010](adr/ADR-010-saxon-in-a-worker-process.md) runs it in a worker process, out of the caller's; the platforms and the licence are open questions 1 and 2; without Saxon at runtime, incoming invoices couldn't be validated, so there is no fallback short of a new ADR |
| EN 16931-1:2026 and XRechnung 4.0, in parallel with 2017 for years ([ITEM-001](../backlog/item-001-en16931-2026.md)) | Edition-aware model from the start ([ADR-007](adr/ADR-007-model-scope-and-editions.md)); follow KoSIT's and CEN's releases |
| The model doesn't yet hold every term an invoice may hold (a supporting document's attachment, XRechnung's extension): harmless when reading, but a model read and written again loses them | Grow the model in slices ([ADR-007](adr/ADR-007-model-scope-and-editions.md)); the writer's tests list the rules still missed (REQ-004) |
| Very large invoices | Our own mapping reads them; KoSIT's stylesheet only in tests; a size limit on every input (REQ-001) |
| On hostile input the official rules take minutes (REQ-002's assumptions), and Saxon can't be stopped from within the process ([ADR-010](adr/ADR-010-saxon-in-a-worker-process.md)) | `validate` refuses the cheapest shapes before the rules (REQ-002-PRS-F001); a time limit on every call kills the worker when it passes ([ADR-010](adr/ADR-010-saxon-in-a-worker-process.md), REQ-002-PRS-NF004) |
| Upstream timing: a fix in an official artefact waits for its release | Documented patch with a test, or wait; never a silent edit |
| Rules and their unit tests from different releases look like defects | Vendor both from the same release ([ADR-008](adr/ADR-008-vendoring-official-files.md)) |
| Libraries with a single maintainer (`factur-x`) | Kept behind Haflinger's own interface, replaceable |
| The official test files differ between CII and UBL in places | Recorded per case in the tests, rechecked with every release |
| An outgoing ZUGFeRD PDF is only PDF/A-3 if the rendered PDF was PDF/A | `embed` refuses other PDFs; veraPDF checks the results in the tests (REQ-004); producing PDF/A is the caller's (for ERPNext: [ITEM-003](../backlog/item-003-erpnext-app.md)) |
| One maintainer | Small own code, official tests as the reference, behaviour checkable without an ERP system |

### Open questions

| # | Question | Where to confirm | Affects |
| -- | :- | :- | :- |
| 1 | Is Saxon's size acceptable in a bench, and does any target lack a wheel ([ADR-006](adr/ADR-006-validation-with-official-rules.md))? | Maintainer, [backlog](../backlog/backlog.md) | §2, §7 |
| 2 | Saxon's licence for SaxonC-HE, to confirm before a release, also beside the GPL-3.0 ERPNext app; Saxonica answered on 2026-11-02 without a verdict, [ADR-010](adr/ADR-010-saxon-in-a-worker-process.md) keeps Saxon out of the app's process | Saxonica's licence terms, [ITEM-008](../backlog/item-008-saxonche-licence.md), [backlog](../backlog/backlog.md) | [ADR-009](adr/ADR-009-licences-and-name.md) |

## 12. Glossary

Domain terms (EN 16931, CII, UBL, CIUS, profile, Leitweg-ID, Peppol …): the [101 guide's glossary](../guides/e-invoicing-101.md#glossary). Terms of the requirements: [REQ-001's Terms](../specs/req-001-core.md#terms). In addition:

| Term | Meaning |
| :- | :- |
| Official artefact | A file a standards body publishes and maintains: Schematron rules, reading stylesheets, XML Schemas, code lists, test files |
| Binding | The assignment of each business term to an element of one syntax (EN 16931-3-2 for UBL, -3-3 for CII) |
| KoSIT's reading stylesheet | KoSIT's visualisation stylesheets (`xrechnung-visualization`), used as the second reader: they turn CII and UBL into XML in which every element carries its business term ID |
| Finding | [REQ-002-PRS-F002](../specs/req-002-conformance.md#req-002-prs-f002-findings); Haflinger's own: [REQ-002-PRS-F010](../specs/req-002-conformance.md#req-002-prs-f010-haflingers-own-findings) |
| Round trip | [REQ-004's Terms](../specs/req-004-outgoing-invoices.md#terms) |
