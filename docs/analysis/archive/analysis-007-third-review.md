# Analysis 007: The third review, from six angles

| Meta | Value |
| :- | :- |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Done: its fixes merged with PR #22; its open items moved to the backlog; archived on 2026-11-04 |
| **Audience** | Maintainer |
| **Purpose** | What a third deep review found after the second review's fixes, how sure each finding is, and where each one went |
| **Branch** | `main` at `2c6dddf` (reviewed); `fix/review-3` (fixes) |

## Question

After the second review's fixes ([analysis 006](analysis-006-second-review.md)) and the change that lets Saxon open only local files, what is still wrong with the library, its tests and its documentation? Do the second review's fixes hold?

## Setup

Six reviewers worked in parallel on `main` at `2c6dddf`, each from one angle, read-only, with throwaway scripts outside the repository. Each had read analysis 006, was asked not to report its open items again, and was asked to check its fixes first.

| Angle | Scope | Method |
| :- | :- | :- |
| Reading | `read.py`, `_input.py`, `_xml.py`, `cii.py`, `ubl.py`, `model.py`, `kosit.py` against REQ-001 and REQ-003 | Both readers over the full ZUGFeRD corpus (240 files at `82e886f`) and CEN's 1,140 unit-test invoices; constructed edge cases; 23 planted bugs |
| Validation | `validation.py`, `_saxon.py`, `_xsd.py`, the vendored rules, against REQ-002 and ADR-006 | FeRD's 57 samples of profiles MINIMUM to EXTENDED; about 8,700 mutated copies (each element duplicated, each leaf replaced); shapes that grow with the square; KoSIT's report stylesheets read for parity; odd install paths; 16 threads |
| Writing and PDFs | `cii.py` (writing), `write.py`, `_xsd.py`, `pdf.py`, against REQ-004 and REQ-003-PRS-F007 | Round trips with tricky models; FeRD's EN 16931 Schematron on written output; `extract_xml` over 229 PDFs and `embed` into 211 PDF/A files, on pypdf 6.21.4 and 6.19.0; PDFs crafted just under the limits |
| Security | Every path that takes outside input, above all what changed since `107927c` | Hostile XML and PDFs with measured time and memory; `strace`; a local HTTP listener and `file://` probes against Saxon and lxml; 8 threads |
| Tests as evidence | `tests/`, CI, the Definitions of Done of REQ-001 to REQ-004 | 44 planted bugs, one at a time, with a full run each; every Definition of Done traced to a test; the vendored files' bytes |
| Docs against code | Specs, arc42, ADRs, guides, backlog, README, provenance READMEs, the public API | Every stated fact run or checked: the README example, the benchmark, the corpus report, the Frappe v16 installation, links, licences, versions |

The serious finding and the medium findings 2, 3, 4 and 9 were reproduced a second time, independently of the reviewers' scripts, before the fixes (marked "confirmed" below).

## Results

### Serious

| # | Finding | Evidence | Where it went |
| :- | :- | :- | :- |
| 1 | A PDF of 42 kB keeps `extract_xml` and `read_invoice` busy for 22 s; one of 208 kB for 118 s. The second review's limits (100 entries in the tree of embedded files, 2 MB decoded per stream) bound memory, not time: each node of the tree sits in its own object stream, decoded just under 2 MB, whose index lists one object 490,000 times; pypdf parses every object an object stream lists when it reads one | Confirmed: 20 object streams in 42 kB take 22.3 s; the reviewer measured 99 streams in 208 kB at 118 s on pypdf 6.21.4, and the same order on 6.19.0. The test of the limits uses streams of 20 MB, which fail at once | Fixed: looking for the invoice stops after 3 s, enforced within the thread by a profile function, which Python calls on every call while pypdf parses. A budget of objects wouldn't do: one object stream of 2 MB listing a dictionary followed by long whitespace kept pypdf busy for more than five minutes with only thousands of entries, as pypdf skips that whitespace byte by byte after each object (REQ-003-PRS-F007, REQ-003-PRS-NF003) |

### Medium

| # | Finding | Evidence | Where it went |
| :- | :- | :- | :- |
| 2 | In Factur-X EXTENDED, which allows other taxes beside VAT (`ram:TypeCode` other than `VAT`), a line whose first `ram:ApplicableTradeTax` is another tax reads that tax's category and rate as BT-151 and BT-152; the VAT entry is dropped as a repeat of BG-30. The invoice is valid, and KoSIT's reading stylesheet has the same blind spot | Confirmed: a 2 % tax `AAA` before the 19 % VAT reads as `S 2.00`, with `HAFL-DROPPED` "BG-30 appears more than once" on the VAT entry | Fixed: only a `ram:ApplicableTradeTax` of `VAT` (or without a type code) gives BG-23 and BG-30; another tax is left out with a finding (REQ-003-PRS-F002) |
| 3 | The second review's fix for a value whose element holds elements covers only the values read through `Node.first`: BT-110, BT-111, BT-31, BT-48 and UBL's BT-22 are read from the text before the first child, without a finding | Confirmed: `1<X/>22.04` as BT-110 reads as `1`, no finding; the reviewer showed the same for UBL, for the VAT identifiers and for a UBL note | Fixed: every value goes through the same check (REQ-003-PRS-F002) |
| 4 | Schema-valid invoices make the official rules fail inside Saxon (a second BT-106, a second `GuidelineSpecifiedDocumentContextParameter`, two `cac:PartyLegalEntity` in a UBL seller, a second `TaxTotalAmount` in EXTENDED), and `validate` raises `InvoiceReadError` with Saxon's message. REQ-002-PRS-F001 lists no such refusal; KoSIT's validator records the failure as a processing error at level `error` and rejects the invoice | Confirmed for BT-106; the reviewer's sweep failed 15 of 2,182 mutations of KoSIT case 01.01a and 3 of 6,560 of FeRD's samples this way | Decided by the maintainer: a `HAFL-RULES` finding with flag `fatal` (REQ-002-PRS-F010) |
| 5 | The refusals before the rules don't cover every shape that takes minutes. CEN's `UBL-SR-44` counts distinct `cbc:PaymentID` with a test that grows with the square of their number; many notes that each fail `BR-CL-08` cost as much as empty elements. REQ-002's assumptions and ADR-006 put what remains at "thousands of invoice lines that each fail a rule … which looks like a large real invoice" | Reproduced by the reviewer: 16,000, 32,000 and 64,000 `cbc:PaymentID` (0.5, 1 and 2 MB) take 5.1, 20.4 and 87.0 s with 3 findings; 32,000 notes (2 MB) take 22.5 s | Decided by the maintainer: no further refusals, as no list of them can be complete; REQ-002's assumptions, ADR-006 and arc42 §11 say plainly that `validate` has no time bound on hostile input and that callers validate outside input where a time limit applies; a limit inside the library stays [ITEM-007](../../backlog/archive/item-007-validation-time-limit.md) |
| 6 | `embed` writes `/AFRelationship /Data`, `factur-x`'s default. ZUGFeRD 2.5.2 allows only `Alternative` for the EN 16931 profile in Germany; France allows `Alternative`, `Source` or `Data`; FeRD's `BR-HYBRID-11` checks it | `/AFRelationship /Data` in every PDF `embed` writes; no test checks the relationship | Decided by the maintainer: `Alternative`; that the PDF shows the same invoice as the XML is up to the caller, who renders it (REQ-004-PRS-F007) |
| 7 | `embed` labels its PDF Factur-X EN 16931 but runs only CEN's EN 16931 rules on the XML; FeRD's Schematron for that profile is vendored but never run. It rejects two invoices `embed` accepts: a BT-24 with whitespace around it (FeRD's `FX-SCH-A-000556`; `embed` compared BT-24 without the whitespace), and KoSIT case 01.21a with BT-24 set to EN 16931 (a line's `ram:ExemptionReason`, which the profile doesn't use) | Reproduced by the reviewer with the vendored Schematron; all 60 invoices `write_cii` hands out pass it without error | Decided by the maintainer: for the target profile EN 16931, `write_cii` and `embed` run FeRD's rules of the profile as well as CEN's; `embed` takes BT-24 exactly as written (REQ-004-PRS-F005, REQ-004-PRS-F007) |
| 8 | `embed` refuses a valid invoice with an attachment (BG-24) of about 8 MB: `factur-x` parses the XML for the PDF's metadata with libxml2's default limit on a text | Reproduced by the reviewer: "Resource limit exceeded: Text node too long"; `validate` accepts the same XML | Fixed: `embed` gives `factur-x` the metadata, so that it doesn't parse the XML (REQ-004-PRS-F007) |
| 9 | `read_invoice` and `validate` raise `TypeError` or `AttributeError` for input that isn't `bytes` (a `str`, a `memoryview`, `None`), though REQ-002-PRS-F001 and REQ-003-PRS-F006 allow no exception but `InvoiceReadError`; `extract_xml`, `embed` and `write_cii` already check their arguments. Frappe can return a file's content as `str` | Confirmed for `str` | Fixed: refused with `InvoiceReadError` naming the type (REQ-002-PRS-F001, REQ-003-PRS-F006) |
| 10 | The documentation doesn't keep up with the second review's changes: the vendored UBL 2.1 XML Schemas (OASIS, W3C/IETF, UN/CEFACT) have no licence statement anywhere, against ADR-009's compliance rule; FeRD's provenance README says only the EN 16931 schema is used, and its EN 16931 Schematron is unused without being marked so; ADR-006 says lxml reads only documents Haflinger wrote, and arc42 shows no schema check of incoming invoices and still says Saxon gets "the original bytes" | Confirmed for the licence by searching every provenance README, ADR-009 and the guide | Corrected |

### Gaps in the tests

Of 44 planted bugs, 25 were caught (the second review: 3 of 16). Of the 19 survivors, three break no requirement (an unbounded depth of the name tree, writing that refuses only `fatal`, a PDF inside a PDF); the others are gaps, each now covered by a test:

| # | Gap |
| :- | :- |
| 11 | Which UBL `cac:TaxTotal` gives the VAT breakdown, when one in the VAT accounting currency comes first |
| 12 | `embed`'s refusals of named destinations and of a catalogue `/AF`, and its check against Factur-X's EN 16931 XML Schema: "one test per refusal" (REQ-004-PRS-F007) covered only embedded files |
| 13 | Texts over 10 MB in the schema check (`huge_tree`): the test wrapped its call in `suppress(InvoiceWriteError)` and passed either way |
| 14 | `BR-16` for an invoice without lines (REQ-003-PRS-F003): no test asserted it; analysis 006 counted it as covered |
| 15 | The groups read from one element other than those tested (CII and UBL postal address, CII legal organisation, UBL item BG-31), the repeated UBL VAT identifier, and the business term a buyer's finding names |
| 16 | A multi-line UBL note with `#XXX#`, and Unicode whitespace that isn't XML whitespace kept around a value |
| 17 | `HAFL-PROFILE` when the XML Schema fails too |
| 18 | `max_size` at the limit for `validate` and `extract_xml`, and a number of exactly 1,000 digits on writing |
| 19 | An internal DTD and an external entity refused by `validate`; Saxon refusing `https:` as well as `http:` |
| 20 | Deeply nested XML in the schema check, which only libxml2's own depth limit of 2,048 stops |
| 21 | Rules that fail on a schema-valid invoice (finding 4), and a byte order mark that contradicts the encoding declaration (finding 25) |
| 22 | The relationship of the embedded file, BT-24 with whitespace in `embed`, the PDF limits just under their caps |

### Low

| # | Finding | Where it went |
| :- | :- | :- |
| 23 | UBL reads only the first `cbc:TaxAmount` of a `cac:TaxTotal`, the first `cbc:CompanyID` and `cac:TaxScheme/cbc:ID` of a `cac:PartyTaxScheme`; a further one vanishes without a finding, and an empty first one hides a later value | Fixed (REQ-003-PRS-F002) |
| 24 | An empty `cac:InvoiceLine`, `ram:IncludedSupplyChainTradeLineItem` or VAT breakdown element reads as a group whose terms are all missing; the groups held once skip empty elements | Fixed: a repeated group whose element holds no value counts as missing (REQ-003-PRS-F002) |
| 25 | A UTF-8 byte order mark with `encoding="ISO-8859-1"`: the reader decodes by the declaration, Saxon and lxml by the mark, so non-ASCII text differs (`MÃ¼ller` against `Müller`); XML 1.0 makes this a fatal error | Fixed: refused (REQ-002-PRS-F001, REQ-003-PRS-F006) |
| 26 | The schema check parses the raw bytes a third time; encodings that Python's XML parser accepts and libxml2 doesn't (`utf_8`, `mac-roman`, `cp437`) make a readable invoice fail with `HAFL-XSD` | Fixed: the schema check of an incoming invoice gets the text as decoded for Saxon; a written invoice is still checked as bytes, as a recipient parses it |
| 27 | Numbers keep their value and decimal places, not their characters: `+336.90` and `0336.90` read as `336.90`, `.5` as `0.5`, against the letter of REQ-001-URS-NF001 | Decided by the maintainer: a third exception in REQ-001-URS-NF001 |
| 28 | `embed` refuses a PDF whose page content holds the text `%PDF-`, as "doesn't carry the invoice as given" | Fixed: the check looks at the header, not at every occurrence |
| 29 | `embed` refuses a catalogue `/Dests`, which `factur-x` keeps, and silently drops the other name trees (`/AP`, `/IDS`, `/Pages`, …); it replaces the PDF's XMP and document information and sets `/PageMode` | Fixed: the refusal names exactly what `factur-x` drops; the replaced metadata is stated (REQ-004-PRS-F007) |
| 30 | PDF/A is detected with a byte pattern: a valid PDF/A with another namespace prefix or UTF-16 XMP is refused, a PDF whose description mentions `pdfaid:part='2'` accepted | Fixed: the XMP is parsed (with `defusedxml`) |
| 31 | The PDF limits refuse well-formed PDFs (99 supporting attachments; a cross-reference stream of about 300,000 objects), and the specs don't say so | The limits stated in REQ-003-PRS-F007 |
| 32 | Some FlateDecode streams with decode parameters that change nothing (`[null]`, `[<< >>]`, `<< /Predictor 1 >>`) are refused | Fixed |
| 33 | `Decimal("0E+2000")` is refused as "more than 1,000 digits in plain notation", though it is written `0` | Fixed |
| 34 | An issue date of 30 February passes `validate` (CII's `DateTimeString` is a string in the XML Schema) and made `factur-x` fail inside `embed` | Fixed with finding 8: `factur-x` no longer reads the XML |
| 35 | FeRD's EN 16931 rules warn `PEPPOL-EN16931-R008` on every invoice `write_cii` writes, for the empty `ram:ApplicableHeaderTradeDelivery` the CII schema requires | No change: a warning, and the element is required (REQ-004-PRS-F003) |
| 36 | `factur-x` imports `requests`, which Frappe v16 pins (`requests~=2.33.0`); neither CI job tests that version | CI's Frappe job pins it too |
| 37 | The public API is wider than documented (`kosit.read_invoice`, `validation.check_rules`, `cii.write`, `write.check_written`; no `__all__` in submodules); `Flag` and the target profiles aren't exported; no helper says whether findings make an invoice invalid | [ITEM-009](../../backlog/archive/item-009-public-api.md) |
| 38 | Stale or inconsistent documentation: Frappe v16's Python version (3.14) still an open question; QS-05 claims tests of CEN's rules 1.3.17, which aren't vendored; speed figures from before the schema check; compile times in three versions; ADR dates; ITEM-008 not referenced where its question lives; ADR-002, ADR-005, ADR-007 details; an unused visualization schema; REQ-002-PRS-F011 before F010; analysis 006's open items not in the backlog | Corrected; analysis 006 archived, its open items in the backlog |

## What held up

- **The second review's fixes**, checked by run: BT-110 and BT-111 without BG-22; BT-130 on an empty quantity; VAT totals without `currencyID`; the edition check of BT-24; no group mixing for the UBL tax category, the line's BG-30 and the party's legal entity; `embed` writing into a new file and checking its result strictly; very large Decimals; `embed(pdf, None)`.
- **No path to the network or the file system**: no input reaches lxml or Saxon before `defusedxml`; lxml runs without entities, DTDs or network; with a live listener and `file://` probes (`xsi:schemaLocation`, `xml:base`, XInclude, a stylesheet processing instruction), neither Saxon nor lxml opened anything; Saxon refuses `http`, `https`, `ftp`, `jar:`, `classpath:` and `data:`; `strace` shows reading and validation write nothing.
- **Bindings**: every term of the model is read from the element EN 16931-3-3 and EN 16931-3-2 assign; every swap of two terms planted in reading or writing was caught.
- **Two readers**: they agree on the 195 readable corpus files apart from KoSIT's known limit, and on CEN's examples and Peppol BIS test files. Of CEN's 1,140 unit-test invoices, 30 now differ, each at a known limit of KoSIT's stylesheet (VAT totals without `currencyID` or without BG-22, one total where BT-6 equals BT-5), where Haflinger follows REQ-003-PRS-F002; analysis 006's "both readers agree on CEN's 1,140 invoices" no longer holds literally.
- **Validation**: XML Schema first, for the right schema of each rule set; FeRD's 57 samples of profiles MINIMUM to EXTENDED valid, as XML and from their PDFs; the verdict and the flags match KoSIT's report stylesheets; odd install paths (`#`, `%`, quotes, non-ASCII, a backslash) work; 1,500 validations on 16 threads, with the caches cleared every 50 ms, gave the sequential results.
- **The refusals before the rules** reject no realistic invoice; long IBANs, e-mail addresses, notes and buyer references are linear.
- **Writing and PDFs**: round trips of credit notes, negative amounts, JPY and BHD, notes with special characters, 5,000 lines; `extract_xml` over 229 PDFs with every refusal correct; `embed` into 211 PDF/A files with one header, the XML byte for byte and the pages unchanged; encrypted and damaged PDFs handled; the same on pypdf 6.19.0, which Frappe v16 pins.
- **Process and records**: every recorded exception carries a reason and is tested both ways, with counts that guard against empty globs; the 25 vendored KoSIT files, the 16 UBL schemas among them, are byte-identical to the release's ZIP; every requirement ID cited exists; no broken relative link; all checks green (2,181 tests).

## Lessons

- **A fix needs its own review.** Three of the medium findings and the serious one sit in the second review's fixes: a check added to one of several paths, limits on memory that don't bound time, a list of refusals that can't be complete.
- **Limits on sizes and counts don't bound time.** The PDF limits counted entries and bytes per stream; the cost was in objects parsed, and then in whitespace skipped after each one. Only a limit on time bounds every shape, and for pure-Python parsing it can be enforced within the thread.
- **Two readers with the same blind spot agree on the wrong value.** KoSIT's stylesheet, like Haflinger, takes the first tax of a line; only reading the binding found it.
- **Planted bugs now find gaps, not a lack of tests.** 25 of 44 caught; the survivors cluster in paths that official files never exercise (a second address, a tax total in the second currency first, a refusal of `embed`).
- **Oracles that never run prove nothing.** veraPDF is skipped in CI and wasn't available to the reviewers; KoSIT's own validator couldn't be fetched. The PDF/A-3 claim and the parity with KoSIT rest on inspection.

## Left open

- `validate` has no time bound on hostile input (finding 5): callers validate where a time limit applies; a limit inside the library is [ITEM-007](../../backlog/archive/item-007-validation-time-limit.md).
- KoSIT's reading stylesheet shares the blind spot of finding 2, so the second reader can't check a line's VAT information in EXTENDED invoices with other taxes; Haflinger's own test covers it.
- PDF/A-3 conformance of `embed`'s output has never been checked by veraPDF, and parity with KoSIT's validator rests on its report stylesheets: both are the backlog's Java oracles in CI.
- An error of `embed` can name its private temporary directory; the input is the caller's own PDF, and the directory is gone when the error is raised.
