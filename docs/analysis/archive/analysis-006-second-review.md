# Analysis 006: The second review, from six angles

| Meta | Value |
| :- | :- |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Done: its fixes merged with PR #18; its open items moved to the backlog; archived on 2026-11-01 |
| **Audience** | Maintainer |
| **Purpose** | What a deep review of the rebuilt library found, how sure each finding is, and where each one went |
| **Branch** | `main` at `107927c` (reviewed); `fix/review-2` (fixes) |

## Question

After the rebuild (steps a to h), the first review's fixes and the Factur-X rules, what is still wrong with the library, its tests and its documentation, seen from every angle at once?

## Setup

Six reviewers worked in parallel on `main` at `107927c`, each from one angle, read-only, with throwaway scripts outside the repository. None was told what the first review had found.

| Angle | Scope | Method |
| :- | :- | :- |
| Reading | `read.py`, `_input.py`, `_xml.py`, `cii.py`, `ubl.py`, `model.py`, `kosit.py` against REQ-001 and REQ-003 | Both readers over the full ZUGFeRD corpus (195 readable files) and CEN's 1,140 unit-test invoices; every Python codec as declared encoding; nesting to 10⁶ levels; constructed edge cases |
| Validation | `validation.py`, `_saxon.py`, the vendored rules, against REQ-002 and ADR-006 | Haflinger's verdict against FeRD's own XSLT on FeRD's 29 samples, about 690 mutated copies and the 40 Factur-X files of the corpus; scenario matching; odd install paths |
| Writing and PDFs | `cii.py` (writing), `write.py`, `_xsd.py`, `pdf.py`, against REQ-004 and REQ-003-PRS-F007 | Round trips with tricky models; constructed and incrementally updated PDFs; strict re-reading of results |
| Security | Every path that takes outside input | Hostile XML and PDFs (entities, bombs, deep and wide structures, encodings), measured time and memory, 33,000 fuzzed inputs, threads, killed workers |
| Tests as evidence | `tests/`, CI, the Definitions of Done of REQ-001 to REQ-004 | 16 deliberate bugs planted in a copy of the repository, to see which tests catch them; checks of every recorded exception and of the vendored files' bytes |
| Docs against code | Specs, arc42, ADRs, guides, backlog, README, provenance READMEs | Every stated fact checked against code, data and runs; the README example and the guide's commands run; links and conventions |

The main claims were reproduced a second time before the fixes (marked "confirmed" below).

## Results

### Serious

| # | Finding | Evidence | Where it went |
| :- | :- | :- | :- |
| 1 | `embed` can return a broken PDF: `factur-x` writes its result back into the input's temporary file without rewinding, so the output starts with a fragment of the input and a second `%PDF-` header; on an incrementally updated PDF/A the result no longer carries the invoice. `embed` also drops the caller's other attachments and named destinations, and replaces the whole XMP | Confirmed: the repository's own test output has headers at offsets 0 and 5811; an updated PDF/A gives a result whose embedded files are "none" | Fixed: `embed` writes into a new file, checks its result strictly, and refuses PDFs whose embedded files or destinations it would drop (REQ-004-PRS-F007) |
| 2 | `validate` can take minutes on a small invoice: the official rules compute each finding's location with `xsl:number`, which grows with the square of the number of sibling elements; Saxon holds Python's global interpreter lock meanwhile | Confirmed: 3,200, 6,400 and 12,800 empty elements take 0.5, 0.9 and 3.1 s; the reviewer measured 13 s for 100 kB and 197 s for 400 kB; a thread sleeping 0.1 s at a time stalled for 12.4 s | Documented, as the maintainer decided: REQ-002's assumptions, ADR-006, arc42 §11 (callers validate outside input where a time limit applies). Later the same day: the cheapest shapes are refused before the rules (REQ-002-PRS-F001): thousands of empty elements (at most 8 in any corpus file), numbers of more than 1,000 digits, and telephone numbers of more than 100 characters, which XRechnung's `BR-DE-27` checks with a pattern taking 36 s for 8,000 characters; a time limit in a child process is ITEM-007 |
| 3 | A PDF of 3 MB can use 3 GB while the embedded invoice is looked for: the tree of embedded files is walked without a limit on its breadth, and pypdf's cap on decompression applies to each stream, not to the whole | Reproduced by the reviewer: 10 object streams of 74 MB behind 721 kB take 30 s and 838 MB; 40 take 119 s and 2.96 GB | Fixed: at most 100 entries, and pypdf's decoding capped at 2 MB per stream for that call (REQ-003-PRS-NF003) |
| 4 | Incoming invoices get no XML Schema check, though KoSIT's scenarios run one before the rules: an amount written `1,00` makes the rules crash and `validate` refuse the invoice; an unknown element or a date like 30 February comes out valid | Confirmed: `1,00` refused with a Saxon stack trace on stderr; `ram:Bogus` gives no error | Fixed, as the maintainer decided: XML Schema first (REQ-002-PRS-F011), UBL 2.1 schemas vendored, ADR-002 and ADR-006 amended |
| 5 | Every Saxon run writes the invoice to a temporary file, which REQ-001-PRS-NF001 forbids; the file stays when a worker is killed, and a full disk raises `OSError`. Reading and validation also decoded four Mac encodings differently | Reproduced by the reviewer: `input.xml` left after SIGKILL and SIGTERM; `OSError` under a file-size limit | Fixed, as the maintainer decided: Saxon gets the decoded text in memory; REQ-001-PRS-NF001 scoped to reading and validation (embed hands the caller's own PDF to `factur-x` through a temporary directory) |

### Medium

| # | Finding | Evidence | Where it went |
| :- | :- | :- | :- |
| 6 | Values from two copies of a group mix: a line reads as "exempt at 19 %" when its first VAT category is E and the second S at 19 %; with two legal entities, the name comes from one and the registration from the other | Confirmed | Fixed: groups and their sub-groups are read from one element, further ones dropped with a finding (REQ-003-PRS-F002) |
| 7 | UBL loses BT-110 and BT-111 without a finding when `cac:LegalMonetaryTotal` is missing | Reproduced by the reviewer | Fixed (REQ-003-PRS-F002) |
| 8 | BT-130 is lost when the quantity element is empty; one of CEN's own files does this | Reproduced on `BR-CL-23.xml` | Fixed (REQ-003-PRS-F002) |
| 9 | Factur-X validation fails when the install path contains `#` or `%`: the compiled Schematron's base was a raw path, not a URI | Reproduced by the reviewer | Fixed: a file URI |
| 10 | The XRechnung write target contradicts ADR-007 ("a profile is written only when the model holds every term its rules require"); no KoSIT file can be written as XRechnung | Measured: 0 of 86 | ADR-007 amended, as the maintainer decided: a profile may be a target; an invoice is handed out only when its rules pass |
| 11 | Several Definitions of Done need Factur-X files that aren't vendored (MINIMUM, BASIC WL, BASIC, the corpus's two-due-date invoice), and REQ-003 assumed they were; the README example failed for PDFs | Checked against `tests/data` | Definitions of Done, the assumption and the README corrected; FeRD's samples tested from the maintainer's copy |

### Gaps in the tests

Of 16 planted bugs, 3 were caught. The gaps, each now covered by a test:

| # | Gap |
| :- | :- |
| 12 | A profile without rules of its own could be validated with no rules at all: the tests checked only for `HAFL-PROFILE` |
| 13 | BT-110 and BT-111 could be swapped in CII: every official file gives both the same number |
| 14 | Nothing tested that `read_invoice` hands `max_size` on to a PDF's embedded file |
| 15 | Digits as written: only CII reading and two terms on writing were tested; amounts on writing and UBL reading weren't |
| 16 | UBL's repeated groups and the document order of its findings were untested |
| 17 | BT-9 of a UBL credit note was never exercised |
| 18 | FeRD's sample tests could pass vacuously (no count, a loop over a possibly empty glob) and are always skipped in CI |
| 19 | The records of differences between KoSIT's CII and UBL files lacked the reason or link REQ-002-PRS-F008 requires (REQ-002-PRS-F008 now allows naming the backlog item until the report is filed) |
| 20 | No test at all for an external entity inside a PDF, a file specification pointing outside, BR-16 for an invoice without lines, FatturaPA inside a PDF; a network-blocking test can't reach Saxon's native code (REQ-002-PRS-NF001's Definition of Done changed to inspection) |

### Low

| # | Finding | Where it went |
| :- | :- | :- |
| 21 | A value whose element holds elements was cut at the first child; a BT-24 like `…:2026-01` escaped the edition check; a `TaxTotalAmount` without `currencyID` was dropped when BT-5 was missing; very large Decimals raised `MemoryError` when writing; `embed(pdf, None)` raised `TypeError`; Flate streams with empty decode parameters were refused | Fixed |
| 22 | ADR-006 gave the Factur-X compile time as under 0.2 s (EXTENDED takes 1.1–1.5 s); the benchmark covered 7 of 15 rule sets and didn't produce QS-08's reading figure | Corrected; the benchmark covers all 15 rule sets and reading the 25.7 MB invoice |
| 23 | Stale or missing documentation: arc42 still called the XSD library open; ADR-009's licence list and the package's licence files lacked SchXslt, lxml, pypdf and the vendored licences; ADR-002 omitted pypdf; ADR-008's "only the files used" and size; dates, counts and wording in several documents | Corrected |

## What held up

- **Reading**: every one of the model's 45 terms is read from the element EN 16931-3-3 or EN 16931-3-2 assigns; both readers agree on the 195 readable corpus files and CEN's 1,140 invoices, apart from KoSIT's known limit (two EXTENDED due dates joined).
- **The Factur-X rules**: compiled with SchXslt, they gave exactly FeRD's findings, rule by rule and with the same counts, on the samples, about 690 mutated copies and the corpus's Factur-X files.
- **No XXE, file or network path**: `defusedxml` is the only barrier, and it holds; Saxon itself would resolve an external entity, so it must stay in front. No stylesheet `document()` call takes an input value.
- **Robustness**: 33,000 fuzzed inputs raised only `InvoiceReadError`; `_inflate` is correct; the schema check and Saxon were thread-safe.
- **Vendored files**: all 451 are byte-identical to their recorded sources; every Commit row matches its tag.
- **Process**: every feature's history has `test:` before `feat:`; the rule-set table is tied to the spec and to KoSIT's scenario file.

## Lessons

- **A second reader and a round trip don't find what nobody built.** The missing XML Schema step and the group mixing passed every agreement test, because both readers and the writer shared the same blind spot or the official files never exercised it.
- **Planted bugs measure tests better than their number.** 2,041 passing tests caught 3 of 16 deliberate bugs; official files with identical values in two terms hide swaps.
- **Dependencies need the same scrutiny as own code.** Two of the five serious findings were in how Haflinger called `factur-x` and `pypdf`, and one in how the official rules scale.
- **Statements of fact in the docs drift within days**; a reviewer who runs the claims finds them.

## Left open

All low; candidates for the backlog when this analysis is archived:

- UBL finding locations aren't valid XPaths (the root step has no prefix, and no location declares its prefixes).
- A comment inside BT-24 can pick a different rule set than KoSIT, which compares each text node separately.
- Saxon prints stack traces to stderr when it refuses an input; Python's logging can't capture them.
- Saxon refuses documents nested deeper than 100 elements, which reading accepts.
- Reading a hostile file of 100 MB takes about 35 times its size in memory and can return millions of `HAFL-DROPPED` findings; the caller's `max_size` is the remedy.
- The KoSIT reader shares Haflinger's number, date and whitespace parsing (`_xml.Node`), so a defect there would pass the second reader.
- CI prints no list of skipped tests, has no timeout plugin, and doesn't run coverage; `test_no_frappe_is_loaded` proves little while Frappe isn't installed.
