# REQ-002: Haflinger Conformance — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Draft |
| **Version** | 0.2 |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Intended Use

Which official rules an invoice is checked against, and how Haflinger shows that it follows them. This spec holds validation (choosing and running the official rule set for an invoice, and the findings, Haflinger's own included), the profiles, versions and editions Haflinger supports, and how the official test files are used. Incoming invoices (REQ-003) and outgoing invoices (REQ-004) say what a finding means for them.

Out of scope: Peppol BIS rules beyond those XRechnung includes; PDF/A conformance of a PDF itself.

Read [REQ-001](req-001-core.md) first: it holds the personas, stories and terms, and the rules every spec follows.

Key constraints: the official rules run unchanged, with Saxon ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md)); official artefacts and test files are vendored, pinned and unchanged ([ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md)).

## User Stories

The personas are [REQ-001's](req-001-core.md#personas).

- REQ-002-P1-1. As the operator, I need an invoice judged with the official rules, as the official validators judge it, and told where Haflinger couldn't run a profile's own rules, so that what Haflinger accepts the authorities and my customers accept too.
- REQ-002-P2-1. As the maintainer, I need to adopt a new release of the rules or test files in one step and see from the tests what changed.
- REQ-002-P3-1. As the integrator, I need each failed rule reported with its ID and text, so that I can show it to a person or act on it.

## Requirement Rules

- SHALL = mandatory · SHOULD = recommended · MAY = optional
- Every SHALL verifiable (test / benchmark / inspection / analysis)
- One requirement = one idea

## URS — Functional

#### REQ-002-URS-F001: The official verdict

**Description**: Validation SHALL report the rules the official rule set finds failed for an invoice, at the levels the official configuration sets, and besides them only the Haflinger findings this spec defines.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: [ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md). Haflinger's own findings say what the official rules can't: that a profile's rules weren't run, or that a value couldn't be read or written.

#### REQ-002-URS-F002: The rules the invoice claims

**Description**: Each invoice SHALL be checked against the rule set of its syntax and profile.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: Checking a ZUGFeRD MINIMUM invoice with the EN 16931 rules, or an XRechnung 2.1 invoice with the 3.0 rules, reports failures that aren't there.

#### REQ-002-URS-F003: Findings that can be acted on

**Description**: Each failed rule SHALL be reported with its ID, its seriousness, where in the invoice it failed, and the rule's text.

**Related User Stories**: REQ-002-P3-1

#### REQ-002-URS-F004: One edition at a time

**Description**: An invoice SHALL be handled only under the EN 16931 edition it follows, never as another one.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: Both editions are in use until March 2029 ([ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)).

## URS — Non-Functional

#### REQ-002-URS-NF001: Checked against the official test files

**Description**: Haflinger's behaviour SHALL be tested against the official test files, unchanged. Test files published with a set of rules (KoSIT's test suite with KoSIT's configuration, CEN's unit tests with CEN's rules) SHALL come from the release of the rules in use.

**Related User Stories**: REQ-002-P2-1 | **Rationale**: Rules and tests from different releases look like defects ([ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md)). The ZUGFeRD corpus belongs to no release of rules.

#### REQ-002-URS-NF002: Offline

**Description**: Validation SHALL need no network access and SHALL fetch no artefact at install or run time.

**Related User Stories**: REQ-002-P1-1

#### REQ-002-URS-NF003: Fast enough for every invoice

**Description**: Validation SHALL be fast enough that a caller can validate every invoice it receives or sends: well under a second for a usual invoice, under a minute for one of tens of megabytes.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: If validation were slow, callers would skip it, and an invoice nobody checked could reach the books or a customer. Whether a caller validates large invoices in a background job is its own choice.

## PRS — Functional

#### REQ-002-PRS-F001: One entry point

**Description**: `haflinger.validate(data: bytes, *, max_size: int = …) -> list[Finding]` SHALL validate a CII or UBL invoice with the rule set of REQ-002-PRS-F003 and return its findings. It SHALL raise `haflinger.InvoiceReadError`, and no other exception, with a reason that names the problem, when the input:

- is not well-formed XML; for a PDF the reason says to extract its XML first (REQ-003-PRS-F007);
- contains a document type or entity declaration (REQ-001-PRS-NF001);
- has a root element that is neither a CII invoice nor a UBL invoice or credit note;
- follows an edition other than 2017 (REQ-002-PRS-F009);
- is larger than `max_size` (REQ-001-PRS-NF003).

A value the rules find wrong is a finding, not a refusal.

**Related URS**: REQ-002-URS-F001

**Definition of Done**: a test validates a CII and a UBL file of the KoSIT suite; one test per refusal; the rest is covered by REQ-002-PRS-F006.

#### REQ-002-PRS-F002: Findings

**Description**: A `Finding` SHALL carry `rule` (the rule's ID, e.g. `BR-CO-15`), `flag` (`fatal`, `error`, `warning` or `information`), `location` (where in the invoice) and `text` (the rule's text). An invoice SHALL count as valid when no finding has the flag `fatal` or `error`.

**Related URS**: REQ-002-URS-F003

**Definition of Done**: a test changes BT-112 of KoSIT case 01.01a by one cent and gets findings `BR-CO-15` and `BR-CO-16` with flag `fatal`, a location and the rules' texts.

#### REQ-002-PRS-F003: Rule sets

**Description**: The rule set SHALL be chosen by the invoice's syntax and its specification identifier (BT-24) exactly as written, whitespace included, as KoSIT's scenarios match it, from this table. The alternative spellings, used by ZUGFeRD 2.0 and by some producers, SHALL select the same rule set as the row's identifier; no other identifier SHALL.

| Profile | BT-24 | Alternative spellings | Syntax | Rule set |
| :- | :- | :- | :- | :- |
| EN 16931, also Factur-X / ZUGFeRD EN 16931 | `urn:cen.eu:en16931:2017` |  | CII, UBL | CEN's EN 16931 rules for the syntax |
| XRechnung 3.0 | `urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0` |  | CII, UBL | CEN's EN 16931 rules and KoSIT's XRechnung 3.0 rules for the syntax |
| XRechnung 3.0 extension | `urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0#conformant#urn:xeinkauf.de:kosit:extension:xrechnung_3.0` |  | CII, UBL invoice | The rules KoSIT's scenario for the extension names; KoSIT has none for a UBL credit note |
| XRechnung 3.0 CVD (Clean Vehicles Directive) | `urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0#compliant#urn:xeinkauf.de:kosit:xrechnung:cvd_0.9` |  | CII, UBL | The rules KoSIT's scenario for CVD names |
| Factur-X / ZUGFeRD MINIMUM | `urn:factur-x.eu:1p0:minimum` | `urn:zugferd.de:2p0:minimum` | CII | The Factur-X rules of the profile |
| Factur-X / ZUGFeRD BASIC WL | `urn:factur-x.eu:1p0:basicwl` | `urn:zugferd.de:2p0:basicwl` | CII | The Factur-X rules of the profile |
| Factur-X / ZUGFeRD BASIC | `urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic` | `urn:cen.eu:en16931:2017#compliant#urn:zugferd.de:2p0:basic`, `urn:cen.eu:en16931:2017:compliant:factur-x.eu:1p0:basic` | CII | The Factur-X rules of the profile |
| Factur-X / ZUGFeRD EXTENDED | `urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended` | `urn:cen.eu:en16931:2017#conformant#urn:zugferd.de:2p0:extended`, `urn:cen.eu:en16931:2017:compliant:factur-x.eu:1p0:extended` | CII | The Factur-X rules of the profile |

**Related URS**: REQ-002-URS-F002 | **Rationale**: ZUGFeRD 2.0's spellings get today's Factur-X rules, because Factur-X 1.0 continues the same profiles. The Factur-X rules are FeRD's, from its ZUGFeRD package, which is technically identical to FNFE-MPE's Factur-X package.

**Definition of Done**: a test per row with an official test file of that profile checks that its rule set ran (by the rule IDs in its findings, or by a deliberately broken copy failing a rule of that set); a test per alternative spelling, with a test file that uses it where the official files have one, otherwise with a copy of the row's file with only BT-24 changed.

#### REQ-002-PRS-F004: Profiles not supported

**Description**: An invoice whose BT-24 names no profile of REQ-002-PRS-F003 for its syntax, or that has no BT-24, SHALL be validated with CEN's EN 16931 rules for its syntax, and SHALL get one `HAFL-PROFILE` finding (REQ-002-PRS-F010).

**Related URS**: REQ-002-URS-F002, REQ-002-URS-F003 | **Rationale**: Rule sets of outdated versions (XRechnung before 3.0) aren't kept: they would have to be vendored and tested next to the current ones for a shrinking number of invoices, and such an invoice is still read and validated. The same holds for code lists: a code that has since left its list shows as a finding, and the invoice date shows that it was valid then. Peppol BIS rules come with sending through Peppol; the sending access point checks them for incoming Peppol invoices.

**Definition of Done**: tests with a Peppol BIS invoice, an XRechnung 2.1 invoice, a UBL invoice that claims Factur-X BASIC and an invoice without BT-24 get the EN 16931 findings and one `HAFL-PROFILE` finding each.

#### REQ-002-PRS-F005: KoSIT's rule levels

**Description**: For a rule set that KoSIT's validator configuration has a scenario for, where the configuration sets a rule's level differently from the stylesheet, the finding SHALL carry the configuration's level.

**Related URS**: REQ-002-URS-F001

**Definition of Done**: a test with an XRechnung file that fails `CII-SR-475` gets the finding with flag `information`, as KoSIT's configuration sets it.

#### REQ-002-PRS-F006: The document as received

**Description**: The rules SHALL judge the invoice exactly as received, its namespace prefixes, comments and whitespace included, not a copy written out again.

**Related URS**: REQ-002-URS-F001 | **Rationale**: Some rules test an element's prefixed name: `PEPPOL-EN16931-R008`, "no empty elements", exempts the empty `ram:ApplicableHeaderTradeDelivery` by name, so a copy written out with other prefixes fails it.

**Definition of Done**: a test validates KoSIT case 01.01a in CII, whose `ram:ApplicableHeaderTradeDelivery` is empty, and gets no `PEPPOL-EN16931-R008` finding, while the same file written out again by ElementTree gets one.

#### REQ-002-PRS-F007: Official verdicts reproduced

**Description**: Validation SHALL reproduce the official test files' verdicts.

**Related URS**: REQ-002-URS-F001, REQ-002-URS-NF001

**Definition of Done**:

- Every file of the KoSIT test suite is valid (no `fatal` or `error` finding).
- Every expectation of CEN's per-rule unit tests, from the release of the EN 16931 rules in use, is met: each listed rule fails where the test expects an error and doesn't where it expects success.
- One file per Factur-X profile of REQ-002-PRS-F003, chosen from the ZUGFeRD corpus's `correct` folders among files made for the Factur-X version of the rules in use, is valid.

#### REQ-002-PRS-F008: Differences in the official files

**Description**: Where official test files disagree with each other (the CII and UBL files of one KoSIT business case giving different values), the test SHALL record the case, the business term and the reason, and leave out only that term. Each record SHALL link the upstream issue that reports the difference, or say why there is none (for example, a difference the standard allows). A further test SHALL fail once a new release of the files removes a recorded difference.

**Related URS**: REQ-002-URS-NF001 | **Rationale**: Haflinger never fixes an official file, so a fix can only come from upstream; the failing test then shows when it has arrived.

**Definition of Done**: the recorded differences are tested both ways (test); inspection of each recorded reason and upstream link.

#### REQ-002-PRS-F009: Editions supported

**Description**: Haflinger SHALL support EN 16931-1:2017 only. An invoice that follows another edition (REQ-001-PRS-F003) SHALL be refused by validation (REQ-002-PRS-F001), reading (REQ-003-PRS-F006) and writing (REQ-004-PRS-F002), with a reason naming the edition. An invoice that names no edition SHALL be handled as 2017.

**Related URS**: REQ-002-URS-F004

**Definition of Done**: a CII and a UBL file with BT-24 `urn:cen.eu:en16931:2026` are refused by `validate`, naming 2026; the refusals of reading and writing are tested in REQ-003 and REQ-004.

#### REQ-002-PRS-F010: Haflinger's own findings

**Description**: Besides the findings of the official rules, Haflinger SHALL report only these findings of its own, each a `Finding` (REQ-002-PRS-F002) whose rule ID starts with `HAFL-`:

| Rule | Flag | Reported by | When | Location and text |
| :- | :- | :- | :- | :- |
| `HAFL-PROFILE` | `warning` | `validate` | BT-24 names no profile for the invoice's syntax, or is missing (REQ-002-PRS-F004) | BT-24's element, or the root; the text names the BT-24 value and says that the profile's own rules weren't run |
| `HAFL-XSD` | `fatal` | `write_cii`, `haflinger.pdf.embed` | the document violates an XML Schema it must pass (REQ-004-PRS-F004) | as the schema check reports it; the text names the schema |
| `HAFL-VALUE` | `error` | `read_invoice` | a value isn't written as its business term requires, and is read as missing (REQ-003-PRS-F002) | the element; the text names the business term and the value |
| `HAFL-DROPPED` | `warning` | `read_invoice` | a value the model has no place for: a repeat of a term the model holds once, a VAT total in a third currency (REQ-003-PRS-F002) | the element left out; the text names the business term |

**Related URS**: REQ-002-URS-F001, REQ-002-URS-F003

**Definition of Done**: each finding is tested in the requirement the table names; inspection that no other `HAFL-` rule exists.

## PRS — Non-Functional

#### REQ-002-PRS-NF001: No network

**Description**: Validation SHALL work without network access, and installing Haflinger SHALL download nothing beyond its packages.

**Related URS**: REQ-002-URS-NF002

**Definition of Done**: the validation tests pass with network access blocked (test); the package contains every artefact it uses (inspection).

#### REQ-002-PRS-NF002: Speed

**Description**: The first validation of a KoSIT test file with a rule set in a process, compiling that rule set included, SHALL take at most 2 s. After that, validating a file of the KoSIT test suite SHALL take at most 50 ms, and the 25.7 MB Peppol invoice of the ZUGFeRD corpus (`PEPPOL/Valid/Qvalia/Large_Invoice_sample1.xml`, 26,813 lines, at corpus commit `82e886f`) at most 30 s, on the reference machine. The time and peak memory of validating the 61.1 MB Peppol invoice (`PEPPOL/Valid/Qvalia/Large_Invoice_sample2.xml`) SHALL be measured; its limit is set once they are known.

**Related URS**: REQ-002-URS-NF003

**Definition of Done**: a benchmark run against the KoSIT suite and the ZUGFeRD corpus, the first validation measured in a fresh process per rule set, its figures and the 61.1 MB invoice's time and peak memory recorded with the release, together with the machine they ran on (processor, Python version).

#### REQ-002-PRS-NF003: Traceable to a release

**Description**: Every official artefact and set of official test files Haflinger ships or tests with SHALL carry the provenance [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md) requires.

**Related URS**: REQ-002-URS-NF001

**Definition of Done**: inspection of the provenance of each source.

## Acceptance Criteria

- Every KoSIT test file is valid; a one-cent error fails `BR-CO-15` and `BR-CO-16`.
- Every expectation of CEN's unit tests from the rules' release is met.
- Each profile of the rule-set table runs its own rules, under each of its spellings; other profiles get the EN 16931 rules and a `HAFL-PROFILE` warning.
- KoSIT's rule levels apply; the rules judge the document as received.
- Only EN 16931-1:2017 is handled; other editions are refused.
- Haflinger's own findings are the four of REQ-002-PRS-F010.
- Validation works offline and within the speed limits.
- Every artefact and test file set carries its provenance.

## Assumptions

- XRechnung 3.0 is the only XRechnung version the authorities accept today; earlier versions need no rules of their own.
- The Factur-X rules and XML Schemas for MINIMUM, BASIC WL, BASIC, EN 16931 and EXTENDED come from FeRD's ZUGFeRD package, whose rights of use put the schemas and Schematron under Apache-2.0, so that Haflinger can vendor them under [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md) ([ITEM-002](../backlog/item-002-official-test-material.md)).
- KoSIT's scenario file, which sets the rule levels of REQ-002-PRS-F005, is vendored with KoSIT's stylesheets.

## Open Questions

- FeRD's rights of use name the schemas and Schematron as Apache-2.0, not the XSLT its package also holds: does the licence cover the XSLT (to ask FeRD), or is the Schematron compiled to XSLT at vendoring time? Until this is settled, the Factur-X profiles get CEN's rules and `HAFL-PROFILE`, as REQ-002-PRS-F004 says.
