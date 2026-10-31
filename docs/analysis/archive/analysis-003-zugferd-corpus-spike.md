# Analysis 003: The ZUGFeRD corpus through Haflinger (spike)

| Meta | Value |
| :- | :- |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Archived |
| **Audience** | Maintainer; input for the ADRs and specs |
| **Purpose** | How robust are reading and validation on real invoices from many producers? |
| **Branch** | `spike/zugferd-corpus` |

> Archived on 2026-10-30. Its findings live in the ADRs, specs, architecture, guides and backlog; [analysis 005](../analysis-005-arc42-setup.md) lists where each one went.

## Question

The [KoSIT XSLT spike](analysis-002-kosit-xslt-spike.md) worked on KoSIT's clean test suite. How robust are reading and validation on real and sample invoices from many producers, including PDFs, old formats and deliberately broken files?

## Setup

- **Corpus**: [`ZUGFeRD/corpus`](https://github.com/ZUGFeRD/corpus) at commit `82e886fb21369e3e83c1e97170a4ff406deceee7` (2026-10-13), Apache-2.0. 240 files (151 PDF, 89 XML, 152 MB), not vendored. Folders: ZUGFeRD 1 and 2 (`correct/` and `fail/`), XRechnung samples in CII, UBL and as PDF, Peppol, Italian FatturaPA, one unstructured PDF.
- **Pipeline per file**: XML out of a PDF with `factur-x` 7.9 (`get_xml_from_pdf`, no XSD check); read with Haflinger's own mapping and through KoSIT's XSLT; compare; validate with EN 16931 rules (and XRechnung rules when BT-24 names XRechnung), as in the previous spike.
- **Script**: `scripts/corpus_report.py <corpus> [<out.tsv>]`, one row per file.

## Results

### Extraction

| Outcome | Files |
| :- | :- |
| XML found | 236 |
| PDF without embedded XML | 3 (an unstructured invoice; two `fail/` files: a PDF with UBL embedded, and one with an invalid encoding attribute) |
| Not well-formed XML | 1 (a FatturaPA sample) |

### Reading

| Outcome | Files | Cause |
| :- | :- | :- |
| Read by both, **identical** | **176** | — |
| Read by both, different | **0** | — |
| Not CII or UBL invoice | 25 | ZUGFeRD 1.0 (`CrossIndustryDocument`) |
| Not CII or UBL invoice | 14 | Italian FatturaPA |
| Refused, no lines (BG-25) | 14 | MINIMUM and BASIC WL profiles: header data only, by design |
| Refused, BT-40 missing | 2 | No seller country code |
| Own mapping refuses, KoSIT reads | 1 | UBL credit note (not in REQ-001's scope) |
| KoSIT path refuses, own mapping reads | 2 | EXTENDED with two due dates: KoSIT's XSLT joins them into one value (`2018-11-20;2018-11-14`), our glue can't read it as a date |

Where both read a file, the two readers agree on every one of REQ-001's terms, across producers (Mustang, intarsys, symtrax, FNFE, Qvalia, others).

### Validation

By profile (BT-24) and by whether the corpus files the invoice under `correct/` or `fail/`:

| Profile | Under `correct/` or `valid/`: valid / invalid | Under `fail/`: valid / invalid |
| :- | :- | :- |
| EN 16931 | 90 / 10 | 4 / 7 |
| XRechnung | 8 / 11 | 0 / 1 |
| Peppol BIS | 20 / 3 (2 skipped, see below) | — |
| BASIC | 6 / 1 | 0 / 5 |
| EXTENDED | 5 / 8 | 0 / 1 |
| BASIC WL | 0 / 5 | 0 / 1 |
| MINIMUM | 0 / 6 | 0 / 2 |

The invalid results under `correct/` are almost all **version and profile effects**, not wrong rules:

- **Outdated XRechnung**: the XRechnung 1.2 and 2.1 samples fail the XRechnung 3.0 rules (Peppol rules `PEPPOL-EN16931-R001`, `-R010`, `-R020` that XRechnung 3.0 includes). KoSIT's validator would not even pick a scenario for them.
- **Code lists moved on**: `BR-CL-25` on samples that use the electronic address scheme `EM` (e-mail), since removed from the EAS code list; `BR-CL-11` likewise.
- **Profiles with their own rules**: MINIMUM and BASIC WL are not EN 16931 invoices, and EXTENDED goes beyond it; checking them with the EN 16931 rules can only fail. They need the Factur-X Schematron of their profile.
- Two deliberate test files with the EICAR test string (`other/eicar.*`), and one named "not validating".

Under `fail/`, 4 files pass the XML rules: their faults are in the PDF (wrong embedded file name, PDF/A or metadata problems), which this pipeline doesn't check.

### Speed and size

- The 238 files of normal size took **6.3 s** together, PDFs included.
- **Two Peppol invoices of 26 MB and 61 MB** (26,813 lines in the first): our own mapping reads the 26 MB file in 0.8 s; KoSIT's XSLT did not finish within 2 minutes in the first run. Measured separately: KoSIT's XSLT needs **677 s** (11 minutes) for the 26 MB file, while the official rules validate it in **6.7 s**. The reading stylesheet grows much faster than linearly with the number of lines; the rules don't. The report skips the Saxon steps above 5 MB.

## Lessons

- **Reading holds on real files.** No disagreement in 176 files from many producers; the refusals have clear causes.
- **Read leniently.** MINIMUM and BASIC WL invoices are not e-invoices under German law, but they arrive, and a person should see them. Refusing them for missing lines is wrong for incoming invoices; that confirms REQ-001's open question in favour of reading what is there and reporting what is missing.
- **Validation must choose its rules**, as KoSIT's validator does with scenarios: by syntax, profile and version from BT-24. Profiles need the Factur-X Schematron (MINIMUM, BASIC WL, BASIC, EN 16931, EXTENDED). Outdated versions (XRechnung before 3.0) need a decision: reject with a clear reason, or validate with the rules of their time.
- **Very large invoices** (11 minutes through KoSIT's XSLT for 26 MB, against 0.8 s with our mapping and 6.7 s for validation) need our own reading path or a different strategy for the XSLT (for example only the header through KoSIT, the lines through our mapping), and a size limit. A 26 MB invoice is not exotic for utilities and telecoms.
- **EXTENDED content** shows up in KoSIT's output as joined values (several due dates in BT-9). The glue has to handle repeated values, or EXTENDED gets its own mapping.
- **PDF checks are a separate job**: PDF/A-3 conformance, embedded file name, XMP metadata. Nothing in the pipeline covers them yet.
- **Legacy formats**: ZUGFeRD 1.0 and FatturaPA arrive too. Haflinger should recognise them and say what they are, not just "unknown root".

## Not covered

- PDF-level validation (PDF/A, XMP).
- The Factur-X Schematron per profile.
- Writing.

## Recommended next steps

1. Lenient reading for incoming invoices (REQ-001 next version): read what is there, report missing required terms as findings.
2. Profile- and version-aware validation: Factur-X Schematron per profile, a scenario table keyed by BT-24, and a policy for outdated versions.
3. Large invoices: a size or line limit above which reading uses our own mapping (or KoSIT's XSLT for the header only); validation can stay as it is.
4. Recognise ZUGFeRD 1.0 and FatturaPA and say so in the refusal.
5. Vendor a small, representative selection of corpus files as regression tests (Apache-2.0).
