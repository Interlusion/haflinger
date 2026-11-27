# REQ-002: Haflinger Conformance — Requirement Specification

| Meta | Value |
| :- | :- |
| **Status** | Baselined |
| **Version** | 0.18 |
| **Date** | 2026-11-27 |
| **Author** | loxy (drafted with Claude) |

## Intended Use

Which official rules an invoice is checked against, and how Haflinger shows that it follows them. This spec holds validation (choosing and running the official rule set for an invoice, and the findings, Haflinger's own included), the profiles, versions and editions Haflinger supports, and how the official test files are used. It also holds the German VAT check: what §14(4) UStG asks of an invoice that German invoicing law governs, checked with KoSIT's German rules on any profile ([ADR-014](../arc42/adr/ADR-014-german-vat-checks.md)). Incoming invoices (REQ-003) and outgoing invoices (REQ-004) say what a finding means for them.

Out of scope: Peppol BIS rules beyond those XRechnung includes; PDF/A conformance of a PDF itself; the invoicing law of other member states, and deciding which state's law governs an invoice (the caller).

Read [REQ-001](req-001-core.md) first: it holds the personas, stories and terms, and the rules every spec follows.

Key constraints: the official rules run unchanged, with Saxon ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md)), in a worker process ([ADR-010](../arc42/adr/ADR-010-saxon-in-a-worker-process.md)); the German VAT check runs KoSIT's German rules on any invoice, with three rules of Haflinger's own ([ADR-014](../arc42/adr/ADR-014-german-vat-checks.md)); official artefacts and test files are vendored, pinned and unchanged ([ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md)).

## User Stories

The personas are [REQ-001's](req-001-core.md#personas).

- REQ-002-P1-1. As the operator, I need an invoice judged with the official rules, as the official validators judge it, and told where Haflinger couldn't run a profile's own rules, so that what Haflinger accepts the authorities and my customers accept too.
- REQ-002-P1-2. As the operator, I need to know where an invoice that German invoicing law governs lacks what §14(4) UStG asks for, also when it isn't an XRechnung invoice, so that I neither send one nor deduct input VAT from one that the tax office wouldn't accept.
- REQ-002-P2-1. As the maintainer, I need to adopt a new release of the rules or test files in one step and see from the tests what changed.
- REQ-002-P3-1. As the integrator, I need each failed rule reported with its ID and text, so that I can show it to a person or act on it.
- REQ-002-P3-2. As the integrator, I need validation to end within a time I set and to leave my process alone, so that a hostile invoice can't hold or crash the host that validates it.

## Requirement Rules

- SHALL = mandatory · SHOULD = recommended · MAY = optional
- Every SHALL verifiable (test / benchmark / inspection / analysis)
- One requirement = one idea

## URS — Functional

#### REQ-002-URS-F001: The official verdict

**Description**: Validation SHALL report the rules the official rule set finds failed for an invoice, at the levels the official configuration sets, and besides them only the Haflinger findings this spec defines.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: [ADR-003](../arc42/adr/ADR-003-integrate-dont-implement.md). Haflinger's own findings say what the official rules can't: that a profile's rules weren't run, or that a value couldn't be read or written.

#### REQ-002-URS-F002: The rules the invoice claims

**Description**: Validation SHALL check each invoice against the rule set of its syntax and profile.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: Checking a ZUGFeRD MINIMUM invoice with the EN 16931 rules, or an XRechnung 2.1 invoice with the 3.0 rules, reports failures that aren't there. The German VAT check (REQ-002-URS-F005) is apart from validation: it answers what German law asks, not what the profile does.

#### REQ-002-URS-F003: Findings that can be acted on

**Description**: Each failed rule SHALL be reported with its ID, its seriousness, where in the invoice it failed, and the rule's text.

**Related User Stories**: REQ-002-P3-1

#### REQ-002-URS-F004: One edition at a time

**Description**: An invoice SHALL be handled only under the EN 16931 edition it follows, never as another one.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: Both editions are in use until March 2029 ([ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)).

#### REQ-002-URS-F005: What German invoicing law asks

**Description**: On the caller's request, Haflinger SHALL check an invoice that German invoicing law governs for what §14(4) UStG asks of it beyond the rules of its profile, with the official rules that check it, and SHALL state what the check doesn't cover.

**Related User Stories**: REQ-002-P1-2 | **Rationale**: [ADR-014](../arc42/adr/ADR-014-german-vat-checks.md). KoSIT's German rules run in validation only where BT-24 names XRechnung, so an invoice between businesses gets none; input VAT is deductible only from an invoice that holds what §14 UStG asks (§15(1) no. 1 UStG). Which state's invoicing law governs an invoice follows the place of supply, which the invoice doesn't show; the caller knows.

## URS — Non-Functional

#### REQ-002-URS-NF001: Checked against the official test files

**Description**: Haflinger's behaviour SHALL be tested against the official test files, unchanged. Test files published with a set of rules (KoSIT's test suite with KoSIT's configuration, CEN's unit tests with CEN's rules) SHALL come from the release of the rules in use.

**Related User Stories**: REQ-002-P2-1 | **Rationale**: Rules and tests from different releases look like defects ([ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md)). The ZUGFeRD corpus belongs to no release of rules.

#### REQ-002-URS-NF002: Offline

**Description**: Validation and the German VAT check SHALL need no network access and SHALL fetch no artefact at install or run time.

**Related User Stories**: REQ-002-P1-1

#### REQ-002-URS-NF003: Fast enough for every invoice

**Description**: Validation and the German VAT check SHALL be fast enough that a caller can check every invoice it receives or sends: well under a second for a usual invoice, under a minute for one of tens of megabytes.

**Related User Stories**: REQ-002-P1-1 | **Rationale**: If validation were slow, callers would skip it, and an invoice nobody checked could reach the books or a customer. Whether a caller validates large invoices in a background job is its own choice.

#### REQ-002-URS-NF004: Bounded time

**Description**: Validation and the German VAT check SHALL end within a time limit the caller can set, on any input.

**Related User Stories**: REQ-002-P3-2 | **Rationale**: On hostile input the official rules take minutes, and no list of refusals can catch every such input (see the assumptions).

#### REQ-002-URS-NF005: The caller's process kept apart

**Description**: The engine that runs the official rules SHALL NOT run in the caller's process: a crash of it or a time limit passed SHALL NOT end or hold the caller's process.

**Related User Stories**: REQ-002-P3-2 | **Rationale**: Saxon is native code, and a crash in it ends the process it runs in, and Saxonica leaves open whether the GPL-3.0 ERPNext app may load it into its own process ([ADR-010](../arc42/adr/ADR-010-saxon-in-a-worker-process.md)).

## PRS — Functional

#### REQ-002-PRS-F001: One entry point

**Description**: `haflinger.validate(data: bytes, *, max_size: int = …, timeout: float = …) -> tuple[Finding, ...]` SHALL validate a CII or UBL invoice with the rule set of REQ-002-PRS-F003 and return its findings. It SHALL raise `haflinger.InvoiceReadError`, and no other exception, with a reason that names the problem, when the input:

- isn't `bytes` (the reason names its type);
- is not well-formed XML, which includes a byte order mark that contradicts the encoding declaration; for a PDF the reason says to extract its XML first (REQ-003-PRS-F007);
- contains a document type or entity declaration (REQ-001-PRS-NF001);
- has a root element that is neither a CII invoice nor a UBL invoice or credit note;
- follows an edition other than 2017 (REQ-002-PRS-F009);
- is larger than `max_size` (REQ-001-PRS-NF003);
- holds more than 1,000 empty elements (no child element, no text but whitespace): every one fails `PEPPOL-EN16931-R008`, and the rules would take minutes over thousands of them (see the assumptions); real invoices hold none or a few;
- holds empty elements whose locations (REQ-002-PRS-F002) total more than 10,000,000 characters: each step of a location names its element's namespace, so that a few hundred empty elements nested deep in a long namespace give findings that take gigabytes in the worker and the caller (229 million characters of locations, 1.7 GB in the worker, for an invoice of 35 kB, measured on 2026-11-17); the locations of a real invoice's empty elements total a few thousand characters at most;
- holds a number of more than 1,000 digits, whose arithmetic in the rules grows with the square of its length (minutes for one of a megabyte); real amounts have fewer than 20;
- holds a telephone number (`ram:CompleteNumber`, `cbc:Telephone`) of more than 100 characters: XRechnung's `BR-DE-27` checks it with a pattern whose time grows with the square of the length (36 s for 8,000 characters); real numbers have fewer than 40.

A value the rules find wrong is a finding, not a refusal, and so is a failure of the rules themselves on an invoice that passed the XML Schema (`HAFL-RULES`, REQ-002-PRS-F010). Rules that don't end within `timeout`, a worker that dies and a `timeout` that isn't valid raise `InvoiceReadError` too (REQ-002-PRS-NF004, REQ-002-PRS-NF005).

**Related URS**: REQ-002-URS-F001

**Definition of Done**: a test validates a CII and a UBL file of the KoSIT suite; one test per refusal (a `str` and a `memoryview` for the type, a UTF-8 byte order mark with `encoding="ISO-8859-1"`), those for empty elements, their locations, digits and telephone numbers also showing that the limit itself is validated and that far beyond it is refused within a second; the rest is covered by REQ-002-PRS-F006.

#### REQ-002-PRS-F002: Findings

**Description**: A `Finding` SHALL carry `rule` (the rule's ID, e.g. `BR-CO-15`; empty where the rule set gives none, as FeRD's reports of elements a profile doesn't use), `flag` (`fatal`, `error`, `warning` or `information`; `error` where the rule set gives none or another), `location` (where in the invoice: an XPath from the document's root that selects the element, each step written as XPath 3.0's `Q{namespace}name[position]`, as the official rules give it, so that it needs no prefixes declared; `line n` where the XML Schema check names no element, or one Haflinger can't tell from its siblings) and `text` (the rule's text); `haflinger.Flag` SHALL be the type of `flag`. An invoice SHALL count as valid when no finding has the flag `fatal` or `error`, and `haflinger.is_valid(findings: Iterable[Finding]) -> bool` SHALL apply this rule to the findings of `validate`. It judges the rules that ran: a `HAFL-PROFILE` warning (REQ-002-PRS-F004) says the profile's own rules didn't, and the invoice counts as valid against CEN's EN 16931 rules alone. Reading's findings are no verdict (REQ-003-PRS-F008), and an `InvoiceWriteError` is a refusal whatever findings it holds (REQ-004-PRS-F001).

**Related URS**: REQ-002-URS-F003 | **Rationale**: Each caller would otherwise write the rule again ([ADR-012](../arc42/adr/ADR-012-public-api.md)).

**Definition of Done**: a test changes BT-112 of KoSIT case 01.01a by one cent and gets findings `BR-CO-15` and `BR-CO-16` with flag `fatal`, a location and the rules' texts, which `is_valid` calls invalid; in a CII and a UBL invoice, the location of a rule's finding and of each of Haflinger's own (REQ-002-PRS-F010) selects the element it names, and only that one; `is_valid` calls findings valid that hold only warnings and information, or none, and invalid that hold one `fatal` or `error`, given as a tuple, a list or a generator (tests).

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

A comment or a processing instruction inside BT-24, or an element, splits its text into pieces, and KoSIT's scenarios compare it in one of two ways; the identifiers of each row SHALL be compared as its scenario compares them. For XRechnung 3.0, its extension and CVD in a UBL invoice, the scenarios compare BT-24's whole text, comments and processing instructions left out (XPath's string value); for every other row, they compare each piece on its own (each text node), so that `urn:cen.eu:en16931:2017<!-- a comment -->` in a CII invoice names EN 16931, and `urn:cen.eu:<!-- a comment -->en16931:2017` names no profile. KoSIT's scenarios have no Factur-X rows: theirs are compared as KoSIT compares the other CII rows, and count only where no other row matches, so that a BT-24 naming XRechnung 3.0 and a Factur-X profile gets XRechnung's rules, as in KoSIT's validator. Every BT-24 element of the invoice counts, a second one too. A BT-24 whose pieces or whole text match the identifiers of no row, or of more than one, names no profile (REQ-002-PRS-F004), as KoSIT's validator then chooses no scenario.

**Related URS**: REQ-002-URS-F002 | **Rationale**: ZUGFeRD 2.0's spellings get today's Factur-X rules, because Factur-X 1.0 continues the same profiles. The Factur-X rules are FeRD's, from its ZUGFeRD package, which is technically identical to FNFE-MPE's Factur-X package. A comment inside BT-24 is rare, but compared any other way, it can make Haflinger run another profile's rules than KoSIT's validator does, which can turn its verdict.

**Definition of Done**: a test per row checks that its rule set ran (by the rule IDs in its findings, or by a deliberately broken copy failing a rule of that set), with an official test file of that profile where one is vendored, otherwise with a copy of a KoSIT file with BT-24 changed; a test per alternative spelling, with a test file that uses it where the vendored files have one, otherwise with such a copy; a test checks that each row other than Factur-X's is compared as its scenario's match expression compares it (tests). Copies of KoSIT case 01.01a in CII and UBL and of CEN's UBL credit note, with a comment or a processing instruction at the start, in the middle or at the end of BT-24, with an element inside it, and with two BT-24 elements, and a copy of the CII case with the identifiers of XRechnung 3.0 and Factur-X MINIMUM, get the rule set this rule names, or a `HAFL-PROFILE` finding, with the text of REQ-002-PRS-F010, which names BT-24 with all its text inside an element, and a BT-24 of 1,000 pieces by its first five (tests); KoSIT's validator chooses the same scenario for each, and none where Haflinger gives `HAFL-PROFILE` (conformance test, where `HAFLINGER_KOSIT_VALIDATOR` names it).

#### REQ-002-PRS-F004: Profiles not supported

**Description**: An invoice whose BT-24 names no profile of REQ-002-PRS-F003 for its syntax, or more than one, or that has no BT-24, SHALL be validated with CEN's EN 16931 rules for its syntax, and SHALL get one `HAFL-PROFILE` finding (REQ-002-PRS-F010).

**Related URS**: REQ-002-URS-F002, REQ-002-URS-F003 | **Rationale**: Rule sets of outdated versions (XRechnung before 3.0) aren't kept: they would have to be vendored and tested next to the current ones for a shrinking number of invoices, and such an invoice is still read and validated. The same holds for code lists: a code that has since left its list shows as a finding, and the invoice date shows that it was valid then. Peppol BIS rules come with sending through Peppol; the sending access point checks them for incoming Peppol invoices.

**Definition of Done**: tests with a Peppol BIS invoice, an XRechnung 2.1 invoice, a UBL invoice that claims Factur-X BASIC, a UBL invoice whose BT-24 a comment splits into the identifiers of EN 16931 and XRechnung 3.0, and an invoice without BT-24 get the EN 16931 findings and one `HAFL-PROFILE` finding each.

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
- Every sample of FeRD's ZUGFeRD package for the Factur-X profiles of REQ-002-PRS-F003 is valid. The package's samples aren't vendored, as its rights of use don't name them ([ITEM-002](../backlog/item-002-official-test-material.md)): the test reads the maintainer's copy of the package and is skipped where it isn't present.
- KoSIT's validator, the official tool, run with the same release of KoSIT's configuration, gives the same verdict and the same findings for every file of the KoSIT test suite and every invoice written from it as each target profile (REQ-004-PRS-F006): each rule with its level after the configuration's levels (REQ-002-PRS-F005), `fatal` as `error`, which KoSIT's reports name it, and its location. It is Java, so it runs as an oracle in CI and where `HAFLINGER_KOSIT_VALIDATOR` names it, never at runtime; the test is skipped elsewhere.
- KoSIT's validator gives the same verdict and the same findings for invoices that fail too: copies of the KoSIT test suite's files, made when the test runs, each with one error (an amount due that doesn't add up, an unknown invoice type code, an unknown VAT category, the buyer reference left out, an amount with three decimals, an element the XML Schema doesn't know), every copy failing; copies of KoSIT's case 01.01a with a tax other than VAT (`GST`) in the VAT breakdown, alone and beside VAT, as a line's category, or in a UBL `cac:TaxTotal` of its own, which CEN's rules reject (REQ-003-PRS-F002); and the broken invoices of the ZUGFeRD corpus selection kept with the tests whose profile KoSIT's configuration covers. Where the XML Schema fails, both stop there, and their parsers word and count its errors differently: the verdicts are compared, and that both report XML Schema errors alone.

#### REQ-002-PRS-F008: Differences in the official files

**Description**: Where official test files disagree with each other (the CII and UBL files of one KoSIT business case giving different values), the test SHALL record the case, the business term and the reason, and leave out only that term. Each record SHALL link the upstream issue that reports the difference, say why there is none (for example, a difference the standard allows), or, until the report is filed, name the backlog item that tracks it. A further test SHALL fail once a new release of the files removes a recorded difference.

**Related URS**: REQ-002-URS-NF001 | **Rationale**: Haflinger never fixes an official file, so a fix can only come from upstream; the failing test then shows when it has arrived.

**Definition of Done**: the recorded differences are tested both ways (test); inspection of each recorded reason and upstream link.

#### REQ-002-PRS-F009: Editions supported

**Description**: Haflinger SHALL support EN 16931-1:2017 only. An invoice that follows another edition (REQ-001-PRS-F003) SHALL be refused by validation (REQ-002-PRS-F001), reading (REQ-003-PRS-F006) and writing (REQ-004-PRS-F002), with a reason naming the edition. An invoice read from XML SHALL count as following another edition where the whole text of any of its BT-24 elements, the text of elements within it included, holds another edition's identifier (`urn:cen.eu:en16931:` and a year other than 2017) anywhere: at its start, as the term Edition reads it, and also after another identifier, which a comment, a processing instruction or an element may split off; also in a BT-24 that reading leaves out, a second one (`HAFL-DROPPED`) or one that holds an element (`HAFL-VALUE`, REQ-003-PRS-F002). The reason SHALL quote that text shortened, as findings quote values. An invoice that names no edition SHALL be handled as 2017.

**Related URS**: REQ-002-URS-F004 | **Rationale**: Reading takes the first BT-24 that holds a value, and the choice of the rule set counts every BT-24 (REQ-002-PRS-F003); checked on the first alone, a CII invoice whose second BT-24 names 2026 was read as 2017, with a `HAFL-DROPPED` warning. Haflinger can't check an invoice of another edition, so a BT-24 that names one anywhere is refused, not read as 2017. KoSIT's validator, which has no edition check, accepts one of these invoices: a CII BT-24 whose XRechnung identifier a comment splits from `urn:cen.eu:en16931:2026`, as XRechnung, the scenario its first piece matches; there Haflinger is stricter. It accepts none of the others: a second BT-24 makes CEN's CII rules fail, and a second one in UBL, an element within BT-24, or in UBL the same comment fails the XML Schema or matches no scenario (measured on 2026-11-17).

**Definition of Done**: a CII and a UBL file with BT-24 `urn:cen.eu:en16931:2026` are refused by `validate`, naming 2026; so are a CII and a UBL file with a second BT-24 `urn:cen.eu:en16931:2026` after their own, with a BT-24 that holds `urn:cen.eu:en16931:2026` and an element, with a BT-24 `urn:cen.eu:en16931:` whose year `2026` lies within an element, and with a BT-24 that names XRechnung 3.0, a comment, and `urn:cen.eu:en16931:2026`, by `validate` and `read_invoice`; the reason for a BT-24 of 2 MB is under 1,000 characters (tests); the refusals of reading and writing are tested in REQ-003 and REQ-004.

#### REQ-002-PRS-F010: Haflinger's own findings

**Description**: Besides the findings of the official rules, Haflinger SHALL report only these findings of its own, each a `Finding` (REQ-002-PRS-F002) whose rule ID starts with `HAFL-`:

| Rule | Flag | Reported by | When | Location and text |
| :- | :- | :- | :- | :- |
| `HAFL-PROFILE` | `warning` | `validate` | BT-24 names no profile for the invoice's syntax, or more than one, or is missing (REQ-002-PRS-F004) | BT-24's element, or the root; the text names BT-24's text, of each BT-24 element, and its pieces where a comment, a processing instruction or an element splits it (REQ-002-PRS-F003), each shortened to its start and its end and at most five, with how many more, and the rule sets it names where it names more than one, and says that the profile's own rules weren't run |
| `HAFL-XSD` | `fatal` | `validate`, `check_german_vat`, `write_cii`, `haflinger.pdf.embed` | the document violates an XML Schema it must pass, or can't be parsed for the check (REQ-002-PRS-F011, REQ-004-PRS-F004) | the element the schema check names, or the line where it names none or one Haflinger can't tell from its siblings; a text of more than 500 characters shortened to its start and its end; the text names the schema |
| `HAFL-RULES` | `fatal` | `validate`, `check_german_vat`, `write_cii`, `haflinger.pdf.embed` | the official rules fail on an invoice that passed the XML Schema, as when a value a stylesheet expects once occurs twice; KoSIT's validator reports this as a processing error and rejects the invoice (REQ-002-PRS-F001, REQ-002-PRS-F013) | the root element; the text names the rule set, for `check_german_vat` the German VAT check's rules, and the processor's message |
| `HAFL-DE-PROFILE` | `error` | `check_german_vat` | REQ-002-PRS-F003 chooses the rules of Factur-X MINIMUM or BASIC WL (REQ-002-PRS-F012) | the BT-24 element that names the profile; the text names the profile and says that it is no e-invoice under §14(1) UStG, that its XML lacks what §14(4) UStG asks for, such as the invoice lines, and that the check's rules weren't run |
| `HAFL-VALUE` | `error` | `read_invoice` | a value isn't written as its business term requires, and is read as missing (REQ-003-PRS-F002) | the element; the text names the business term and the value |
| `HAFL-DROPPED` | `warning` | `read_invoice` | a value the model has no place for: a repeat of a term the model holds once, a VAT total in a third currency (REQ-003-PRS-F002) | the element left out; the text names the business term |

**Related URS**: REQ-002-URS-F001, REQ-002-URS-F003

**Definition of Done**: each finding is tested in the requirement the table names; inspection that no other `HAFL-` rule exists.

#### REQ-002-PRS-F011: XML Schema first

**Description**: `validate` SHALL check the invoice against the XML Schema of its rule set before the rules, as KoSIT's validator does: for KoSIT's scenarios the schema the scenario names (CII D16B, UBL 2.1 Invoice or CreditNote), for a Factur-X profile FeRD's XML Schema of the profile. The check SHALL read the text Saxon gets, decoded once by the byte order mark or the declared encoding, so that the schema, the rules and the reader see the same characters. Each violation SHALL be a `HAFL-XSD` finding (REQ-002-PRS-F010), its text shortened where the schema check quotes a long value, such as an attached document's Base64, and the rules SHALL run only on an invoice that passes the schema. Saxon SHALL parse such an invoice as KoSIT's validator does, within the limits of the check: SaxonC parses with the JDK's strict limits, 100 levels (`jdk.xml.maxElementDepth`) and 200 attributes an element, namespace declarations counted (`jdk.xml.elementAttributeLimit`), which a UBL invoice can pass the schema beyond, since UBL's extensions (`ext:ExtensionContent`) take any foreign elements; KoSIT's validator has Java's defaults, no depth limit and 10,000 attributes. Haflinger SHALL set 2,048 levels, where the check itself stops: it runs with libxml2, which parses no deeper, so that a deeper invoice is a `HAFL-XSD` finding, where KoSIT's validator checks it. It SHALL set 10,000 attributes, beyond which both reject the invoice, Haflinger with `HAFL-RULES`, KoSIT's validator with a processing error.

**Related URS**: REQ-002-URS-F001 | **Rationale**: The rules assume a schema-valid document: on one that isn't, a stylesheet can fail (an amount written `1,00`) or miss what the schema would report (an unknown element, a date that doesn't exist). SaxonC's limits made a schema-valid invoice with an extension 97 levels deep, or with an element of 201 attributes, a `HAFL-RULES` finding, rejected where KoSIT's validator accepts it. Saxon keeps a depth limit, as the rules also run without the check, on CEN's unit tests, which are fragments rather than whole invoices; an invoice Haflinger writes passes the check first. Beyond 32,767 levels Saxon builds a wrong tree without an error, and a copy of 01.01a 50,000 levels deep failed CEN's `BR-CO-10`, in KoSIT's validator too (measured on 2026-11-17). libxml2's limit, which lxml can't raise, leaves the same difference beyond 2,048 levels, far beyond real content: a XAdES signature in an extension, as UBL's schemas define it, reaches 15.

**Definition of Done**: a CII and a UBL file of the KoSIT suite with an unknown element, and one with an amount written `1,00`, each get `HAFL-XSD` findings and no finding of a rule; a Factur-X copy that violates its profile's schema gets `HAFL-XSD`; a copy of a KoSIT file declaring an encoding that Python knows and libxml2 doesn't (`mac-roman`) gets no `HAFL-XSD`; a copy nested 50,000 elements deep gets `HAFL-XSD`, not a crash; a copy of KoSIT's 01.01a UBL file with an extension whose deepest element lies at level 2,048 gets the rules' findings and no `HAFL-` finding, and one at level 2,049 gets `HAFL-XSD`, and `HAFL-RULES` from the rules without the check; one with an element of 10,000 attributes in its extension gets the rules' findings and no `HAFL-` finding, and one of 10,001 gets `HAFL-RULES` (tests); KoSIT's validator gives the same findings as `validate` for the copies at level 2,048 and of 10,000 attributes, accepts the copy at level 2,049 and rejects the one of 10,001 attributes with a processing error (conformance test, where `HAFLINGER_KOSIT_VALIDATOR` names it); a copy with an unknown element whose prefixed name is longer than the 98 bytes libxml2's paths keep gets a `HAFL-XSD` finding located at it, or at its line where the cut splits a character, not a crash; a copy with an attached document of 400,000 characters the schema refuses gets a `HAFL-XSD` finding under 1,000 characters (tests).

#### REQ-002-PRS-F012: The German VAT check

**Description**: `haflinger.check_german_vat(data: bytes, *, max_size: int = …, timeout: float = …) -> tuple[Finding, ...]` SHALL check a CII invoice or a UBL invoice or credit note for what §14(4) UStG asks of it beyond the rules of its profile, and return its findings. It SHALL refuse what `validate` refuses (REQ-002-PRS-F001), with `InvoiceReadError` and the same reasons, a PDF's saying to check the XML that `haflinger.pdf.extract_xml` gives. It SHALL then check the invoice against the XML Schema `validate` checks it against (REQ-002-PRS-F011), and where the schema fails, return its `HAFL-XSD` findings and nothing else. Where REQ-002-PRS-F003 chooses the rules of Factur-X MINIMUM or BASIC WL for the invoice, it SHALL return one `HAFL-DE-PROFILE` finding (REQ-002-PRS-F010) and run no rules; otherwise the rules of REQ-002-PRS-F013, with the exceptions of REQ-002-PRS-F014. Its time limit and worker SHALL be `validate`'s (REQ-002-PRS-NF004, REQ-002-PRS-NF005). It SHALL check any invoice it is given: whether German invoicing law governs the invoice is the caller's to decide.

**Related URS**: REQ-002-URS-F005 | **Rationale**: [ADR-014](../arc42/adr/ADR-014-german-vat-checks.md). The check runs the same stylesheets on the same outside input as `validate`, so it needs the same limits; the rules assume a schema-valid document. MINIMUM and BASIC WL have no invoice lines and are no e-invoices under §14(1) UStG, by the BMF; on them, `BR-DE-TMP-32`'s condition on the lines holds when there are none, so that the rules would miss the time of supply and report the addresses alone. Which state's invoicing law governs an invoice follows the place of supply, and on reverse charge the state where the supplier is established (Article 219a of the EU VAT Directive); the seller's country, a VAT identifier or the rate don't tell it.

**Definition of Done**: a CII and a UBL file of the KoSIT suite are checked; each refusal of REQ-002-PRS-F001 tested against the check as against `validate`; a copy with an unknown element gets `HAFL-XSD` findings and nothing else; invoices of Factur-X MINIMUM and BASIC WL that pass their XML Schema, under each spelling of REQ-002-PRS-F003, get one `HAFL-DE-PROFILE` finding each, located at BT-24, and nothing else, and one that fails its profile's XML Schema gets `HAFL-XSD` and no `HAFL-DE-PROFILE`; a copy of KoSIT case 01.01a in CII whose BT-24 names XRechnung 3.0 and Factur-X MINIMUM gets the check's rules, as REQ-002-PRS-F003 chooses XRechnung's; a copy of KoSIT case 01.01a in CII whose BT-24 names no profile is checked like one that names EN 16931 (tests).

#### REQ-002-PRS-F013: The check's rules

**Description**: The check SHALL run KoSIT's XRechnung 3.0 stylesheet for the invoice's syntax, as vendored (`XRechnung-CII-validation.xsl`, `XRechnung-UBL-validation.xsl` for invoices and credit notes), unchanged, whatever BT-24 names, and SHALL return of its findings only those of these rules, with their IDs, flags, locations and texts as REQ-002-PRS-F002 gives them; KoSIT's scenario sets no level for them (REQ-002-PRS-F005):

| Rule | Flag | What it asks for | §14(4) UStG |
| :- | :- | :- | :- |
| `BR-DE-TMP-32` | `information` | the actual delivery date (BT-72), an invoicing period (BG-14) or a period on every line (BG-26) | no. 6, the time of supply |
| `BR-DE-3` | `fatal` | the seller's city (BT-37) | no. 1, the seller's full address |
| `BR-DE-4` | `fatal` | the seller's post code (BT-38) | no. 1 |
| `BR-DE-8` | `fatal` | the buyer's city (BT-52) | no. 1, the buyer's full address |
| `BR-DE-9` | `fatal` | the buyer's post code (BT-53) | no. 1 |

Where the stylesheet fails on the invoice, the check SHALL return the `HAFL-RULES` finding (REQ-002-PRS-F010), naming the German VAT check's rules.

**Related URS**: REQ-002-URS-F005 | **Rationale**: [ADR-014](../arc42/adr/ADR-014-german-vat-checks.md). Of KoSIT's German rules, these ask for what §14(4) UStG asks; the others are XRechnung's own (the payment instructions `BR-DE-1`, the seller's contact `BR-DE-2`, the buyer reference `BR-DE-15`, BT-24 naming XRechnung `BR-DE-21`), and `BR-DE-16`, the seller's VAT identifier or tax number, asks for what CEN's `BR-S-02` and its siblings already require, which `validate` runs. CEN's rules aren't run again: they are `validate`'s. The four address rules check an address the invoice gives; that it gives one, which EN 16931 requires of seller and buyer, CEN's `BR-08` and `BR-10` check in `validate`.

**Definition of Done**: copies of KoSIT case 01.01a in CII and UBL, BT-24 set to `urn:cen.eu:en16931:2017`, without BT-72, BG-14 and BG-26 get `BR-DE-TMP-32` with flag `information`, without the seller's city and post code `BR-DE-3` and `BR-DE-4`, without the buyer's `BR-DE-8` and `BR-DE-9`, each located as the rule locates it; a copy of CEN's UBL credit note with BT-112 above 250, without the seller's and the buyer's city and post code, gets the four address findings; the XML of the three files under `ZUGFeRDv2/correct/Mustangproject/` of the ZUGFeRD corpus, of the EN 16931 profile, gets no finding, though the stylesheet finds `BR-DE-21`, `BR-DE-2` and Peppol's rules among them; KoSIT's 01.01a UBL file with an element of 10,001 attributes in its extension (REQ-002-PRS-F011), on which the stylesheet fails, gets `HAFL-RULES` naming the check's rules; a test fails when one of the five IDs no longer occurs in the vendored stylesheets (tests).

#### REQ-002-PRS-F014: Exceptions under German law

**Description**: The check SHALL drop findings of REQ-002-PRS-F013 that the law doesn't support, judged by the values `read_invoice` reads from the invoice (REQ-003-PRS-F001):

- a small invoice, whose invoice total with VAT (BT-112) is at most 250 in absolute value, in the currency (BT-5) `EUR`, with a VAT breakdown (BG-23), and with no VAT category of the breakdown (BT-118) or of a line (BT-151) that is `K` or `AE`: the findings of `BR-DE-TMP-32`, `BR-DE-8` and `BR-DE-9`;
- a credit note or an invoice for an advance payment, whose type (BT-3) is `381` or `386`: the finding of `BR-DE-TMP-32`.

Where a value an exception judges by isn't read (BT-3; for small invoices BT-112, BT-5, the VAT breakdown, or the category of any VAT breakdown or line), that exception SHALL NOT apply.

**Related URS**: REQ-002-URS-F005 | **Rationale**: [ADR-014](../arc42/adr/ADR-014-german-vat-checks.md). An invoice of at most €250 including VAT needs neither the time of supply nor the buyer (§33 UStDV), except for distance sales (§3c UStG), which the invoice doesn't show, intra-Community supplies (§6a, category `K`) and reverse charge (§13b, `AE`), on any line; a corrective invoice (`384`) may be negative. A credit note corrects an invoice it refers to; an invoice for an advance payment states the date of the payment, where known, not the time of supply (§14(4) no. 6). A value that isn't read can't show that an exception holds.

**Definition of Done**: copies of KoSIT case 01.01a in CII and UBL without the time of supply and the buyer's city and post code: with BT-112 at 250.00 and at -250.00 `EUR` get none of the three findings, at 250.01 and at -250.01 all three; at 100.00 `USD` all three; at 100.00 `EUR` with a breakdown of category `K`, and one of `AE`, all three, as do copies with a line of category `K`, one of `AE`, and one whose category isn't read; a UBL copy without a VAT breakdown, which UBL's XML Schema allows, all three; with BT-3 `381` or `386` and BT-112 above 250, `BR-DE-8` and `BR-DE-9` and no `BR-DE-TMP-32`; without BT-112, which the XML Schema allows, all three; a copy of CEN's UBL credit note (BT-3 `381` in `cbc:CreditNoteTypeCode`) with BT-112 above 250, without BG-14 and the buyer's city and post code, gets `BR-DE-8` and `BR-DE-9` and no `BR-DE-TMP-32` (tests).

#### REQ-002-PRS-F015: What the check states

**Description**: The docstring of `check_german_vat` SHALL state:

- that the caller calls it where German invoicing law (§14 UStG) governs the invoice, which Haflinger doesn't decide;
- that every finding is meant to be shown, whatever its flag, and that `is_valid` is for `validate`'s findings, not the check's;
- that the time of supply is missing on many proper invoices, as the invoice date may give it (UStAE 15.2a (1a));
- what it doesn't check: the street or post office box (BT-35, BT-50); price reductions agreed in advance, such as a cash discount (no. 7); the date of an advance payment (no. 6); the notes of nos. 9 and 10; the buyer's VAT identifier on a reverse charge for a service in another member state (§14a(1) UStG); the line delivery dates of Factur-X EXTENDED, which `BR-DE-TMP-32` doesn't see; distance sales among small invoices (§3c UStG); credit notes of other types than `381`, which keep `BR-DE-TMP-32`; and that a buyer in a country without post codes gets `BR-DE-9`;
- that it states what it checks, not that an invoice meets the law.

**Related URS**: REQ-002-URS-F005 | **Rationale**: [ADR-014](../arc42/adr/ADR-014-german-vat-checks.md). `BR-DE-TMP-32` fails on 36 of the 86 accepted files of KoSIT's test suite; a caller that holds an invoice back on any finding, or on none that `is_valid` counts, would hold back proper invoices or miss the time of supply.

**Definition of Done**: inspection of the docstring against this list.

## PRS — Non-Functional

#### REQ-002-PRS-NF001: No network

**Description**: Validation and the German VAT check SHALL work without network access, and installing Haflinger SHALL download nothing beyond its packages.

**Related URS**: REQ-002-URS-NF002

**Definition of Done**: no artefact or setting makes Saxon or lxml fetch anything beyond the vendored files, and the package contains every artefact it uses (inspection). A test that blocks the network can't reach Saxon, which runs native code; the tests and the corpus report run without network access.

#### REQ-002-PRS-NF002: Speed

**Description**: The first validation of a KoSIT test file with a rule set in a process, compiling that rule set included, SHALL take at most 2 s. After that, validating a file of the KoSIT test suite SHALL take at most 50 ms, and the 25.7 MB Peppol invoice of the ZUGFeRD corpus (`PEPPOL/Valid/Qvalia/Large_Invoice_sample1.xml`, 26,813 lines, at corpus commit `82e886f`) at most 30 s, on the reference machine. Validating the 61.1 MB Peppol invoice (`PEPPOL/Valid/Qvalia/Large_Invoice_sample2.xml`) SHALL take at most 60 s, and its peak memory SHALL be measured. The German VAT check of a file of the KoSIT test suite SHALL take at most 50 ms after its first call in a process.

**Related URS**: REQ-002-URS-NF003

**Definition of Done**: a benchmark run against the KoSIT suite and the ZUGFeRD corpus, the first validation measured in a fresh process per rule set, its figures and the 61.1 MB invoice's time and peak memory recorded with the release, together with the machine they ran on (processor, Python version).

#### REQ-002-PRS-NF003: Traceable to a release

**Description**: Every official artefact and set of official test files Haflinger ships or tests with SHALL carry the provenance [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md) requires.

**Related URS**: REQ-002-URS-NF001

**Definition of Done**: inspection of the provenance of each source.

#### REQ-002-PRS-NF004: Time limit

**Description**: `validate`, `check_german_vat`, `write_cii` and `haflinger.pdf.embed` SHALL take a keyword argument `timeout`, in seconds, an `int` or `float` greater than 0 and at most a year (31,536,000 s). Its default SHALL be the environment variable `HAFLINGER_RULES_TIMEOUT`, read on each call, or 60 s where it isn't set. The official rules of one call, waiting for another thread's call, starting the worker and compiling the rule set included, SHALL end within `timeout`. When it passes while the call's own rules run, the worker SHALL be killed; when it passes while the call still waits for its turn, the worker SHALL be left to the other call. Either way, `validate` and `check_german_vat` SHALL raise `InvoiceReadError`, `write_cii` and `embed` `InvoiceWriteError` (REQ-004-PRS-F001, REQ-004-PRS-F007), with a reason that says the rules took longer than the limit and names it. A `timeout` (a `bool` included) that isn't such a number of seconds, or, where no `timeout` is given, a `HAFLINGER_RULES_TIMEOUT` that isn't one, SHALL be refused the same way, with a reason that names it, before the rules run.

**Related URS**: REQ-002-URS-NF004 | **Rationale**: The default lies well above the largest real invoice's time (the 61.1 MB invoice of REQ-002-PRS-NF002 validated in 18.5 s on the development machine; a usual invoice takes milliseconds) and below what hostile input takes. A caller that validates invoices of tens of megabytes on a slower machine passes a higher one. A limit must leave room for starting the worker and compiling a rule set, up to about 1 s, which it includes; a year is longer than any validation, and the platform's own limits on waiting lie beyond it. The variable lets a host set the limit without code.

**Definition of Done**: a crafted UBL invoice of 16,000 distinct `cbc:PaymentID` (about 5 s) with `timeout=0.5` is refused within 1.5 s, naming the limit, and the next call validates a KoSIT file; the same holds for `write_cii` and `embed` with a `timeout` too short for their rules, and for `check_german_vat` with one too short for its stylesheet's first compile in a fresh worker; `HAFLINGER_RULES_TIMEOUT` sets the default, and an explicit `timeout` overrides it, an invalid variable included; a call that waits behind another thread's slow call past its own `timeout` is refused while the other call goes on; `0`, `-1`, `nan`, `inf`, `1e10`, `10**400`, `True` and `"60"` as `timeout`, and `abc`, `0` and `1e10` as the variable, are refused, and a year is accepted (tests).

#### REQ-002-PRS-NF005: Rules in a worker process

**Description**: The official rules SHALL run in a worker process that Haflinger starts as a new Python interpreter, which imports nothing of the caller's; the calling process SHALL NOT import `saxonche`. Between them SHALL pass only text, the invoice and the names of vendored stylesheets one way and their output or an error message the other, never pickled objects. Each calling process SHALL have one worker, started on its first validation and kept with its compiled rule sets; threads that start it at the same moment, on a first call or after the helper thread that talks to it ended, may each start one, and each one not kept SHALL end, with its worker, once it has had no request for a second. Calls on one worker SHALL take turns, and calls from several threads SHALL each get the findings of its own invoice. A call that ends early, by any exception, a signal handler's included, SHALL reach the caller as it is and leave the worker in step and no lock held; where its rules run, the worker SHALL be killed within a second: no later call SHALL take its reply for its own, wait for it, or fail because of it. The worker SHALL import the same Haflinger and `saxonche` as the caller, found on the caller's import path, and SHALL write Python's bytecode cache as the caller does: none where the caller writes none, and below the caller's cache prefix where it has one. A worker that dies during a call SHALL be reported as REQ-002-PRS-NF004 reports a time limit passed, with the reason saying that the worker died and holding what it wrote to stderr during that call, and SHALL be replaced on the next call. A worker that can't be started, and a vendored stylesheet that can't be compiled, SHALL be reported the same way, saying so; neither is a finding about the invoice. Calls SHALL work however many files the caller has open. What the worker writes to stderr otherwise SHALL go to Python's logging, logger `haflinger`. A process forked from the caller after its worker started SHALL start a worker of its own, also when another thread of the caller was in a call at the fork, and SHALL hold no pipe of the caller's workers, also of one being started at the fork.

**Related URS**: REQ-002-URS-NF005 | **Rationale**: [ADR-010](../arc42/adr/ADR-010-saxon-in-a-worker-process.md). Background jobs end with a signal handler's exception (RQ's job timeout), which Python raises between any two steps of the calling thread. Rules left running for a call that ended early would hold up the next job for up to its time limit; killing the worker costs that job a compile instead, about 1 s at most. A worker shared across a fork would get the requests of two processes on one pipe, and a child forked during another thread's call inherits a lock that no thread of its own will release; a child that holds a worker's stdin keeps it from ending with the caller. A broken installation reported as `HAFL-RULES` would make every invoice look invalid. A lock that let only one thread start the worker could be left held, by a signal handler's exception between taking and releasing it or in a child forked while another thread holds it; a second worker for a moment costs its memory and a compile instead.

**Definition of Done**: in a fresh interpreter, `saxonche` isn't in `sys.modules` after `validate`, `check_german_vat`, `write_cii` and `embed`; a worker killed between calls is replaced, and the next call validates; a worker killed during a call gives the refusal saying that it died; a child forked after a validation validates with the same findings and with a worker of its own, and so does a child forked while another thread waits on the worker; a child forked while the worker starts holds none of its pipes; 8 threads validating different KoSIT files at once each get their own file's findings; an invoice that makes Saxon print to stderr leaves the text in the `haflinger` log; a call interrupted by a signal handler's exception, at any moment of hundreds tried, in the XML Schema check (REQ-002-PRS-F011) too, leaves the next call its own findings within its time limit; so does an exception at any step of a process's first call, threading's own code included, which reaches the caller as it is; a slow call interrupted after 1 s leaves the next call its findings within 2 s; a call whose helper thread ended before taking its request gets its findings; a helper started beside the one kept ends with its worker within two seconds of its last request; a worker killed while it takes a request is reported as having died; a helper thread that can't be started is refused; a stylesheet that doesn't compile and a worker that can't be started are refused, not findings; a call whose deadline has passed before it sends anything leaves the worker running; validation works with more than 1,024 files open; a caller that finds Haflinger on an import path of its own has a worker that uses the same; the worker of a caller that writes no bytecode writes none, and that of a caller with a cache prefix writes its bytecode below it (tests); inspection that no `pickle` crosses the boundary.

## Acceptance Criteria

- Every KoSIT test file is valid; a one-cent error fails `BR-CO-15` and `BR-CO-16`.
- Every expectation of CEN's unit tests from the rules' release is met.
- Each profile of the rule-set table runs its own rules, under each of its spellings; other profiles get the EN 16931 rules and a `HAFL-PROFILE` warning. BT-24 is compared as KoSIT's scenarios compare it, a comment inside it too.
- KoSIT's rule levels apply; the rules judge the document as received.
- Only EN 16931-1:2017 is handled; other editions are refused.
- Haflinger's own findings are the six of REQ-002-PRS-F010.
- The German VAT check returns only the findings of its five rules and Haflinger's, with the exceptions of German law, on any profile but Factur-X MINIMUM and BASIC WL, which get `HAFL-DE-PROFILE`.
- Validation works offline and within the speed limits.
- Validation ends within its time limit, and the rules run in a worker process, never in the caller's.
- Every artefact and test file set carries its provenance.

## Assumptions

- KoSIT's XRechnung stylesheets check any CII or UBL invoice in their syntax, and BT-24 only chooses KoSIT's scenario: over the 86 files of KoSIT's test suite, they gave the same findings with BT-24 set to `urn:cen.eu:en16931:2017`, but for `BR-DE-21` (measured on 2026-11-21). `BR-DE-TMP-32` fails on 36 of those accepted files.
- XRechnung 3.0 is the only XRechnung version the authorities accept today; earlier versions need no rules of their own.
- The Factur-X rules and XML Schemas for MINIMUM, BASIC WL, BASIC, EN 16931 and EXTENDED come from FeRD's ZUGFeRD package, whose rights of use put the schemas and Schematron under Apache-2.0, so that Haflinger can vendor them under [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md) ([ITEM-002](../backlog/item-002-official-test-material.md)). The rights of use don't name the XSLT the package also holds; Haflinger compiles the Schematron itself ([ADR-006](../arc42/adr/ADR-006-validation-with-official-rules.md)).
- KoSIT's scenario file, which sets the rule levels of REQ-002-PRS-F005, is vendored with KoSIT's stylesheets.
- On hostile input the official rules take minutes. Some of them grow with the square of what they count: the location of each finding is computed by counting its preceding siblings, and CEN's `UBL-SR-44` compares every `cbc:PaymentID` with every one before it. Such invoices needn't look like real ones. Measured on 2026-11-01: 16,000, 32,000 and 64,000 distinct `cbc:PaymentID` (0.5, 1 and 2 MB) take 5.1, 20.4 and 87.0 s; 32,000 notes that each fail `BR-CL-08` in 2 MB take 22.5 s; 10,000 invoice lines that each fail a rule in 3.2 MB take 15 s. No list of refusals can be complete, so the time limit (REQ-002-PRS-NF004) bounds every case; `validate` still refuses the cheapest shapes before the rules (REQ-002-PRS-F001), within milliseconds instead of after the limit.
- The worker costs a process per calling process: 0.07 s to start, 0.25 s (CII) to 1.05 s (Factur-X EXTENDED) to compile a rule set the first time, 160 to 190 MB with a rule set compiled (measured on 2026-11-02).
- Haflinger's hosts run Python as a program (gunicorn and RQ workers in a Frappe bench, a script), so `sys.executable` starts an interpreter of the caller's environment. Where Python is embedded in another program (uWSGI, mod_wsgi), `sys.executable` may name that program; such hosts would need a setting for the interpreter, which Haflinger doesn't have yet. The worker's pipes need a POSIX system (Linux, macOS); elsewhere Haflinger imports and reads invoices, and validation is refused.

## Open Questions

None at present.
