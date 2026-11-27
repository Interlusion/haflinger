# Changelog

What changed in each release of Haflinger, for its callers. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html): while Haflinger is at 0.x, a minor version may break the interface ([ADR-013](https://github.com/Interlusion/haflinger/blob/main/docs/arc42/adr/ADR-013-releases.md)).

## [Unreleased]

### Fixed

- `read_invoice` leaves out a UBL seller's, buyer's or tax representative's `cac:PartyTaxScheme` whose `cac:TaxScheme` has no `cbc:ID` with a `HAFL-DROPPED` finding naming its `cbc:CompanyID`, as it does a CII tax registration without `schemeID`. Before, it dropped the VAT identifier (BT-31, BT-48, BT-63) or the seller's tax registration identifier (BT-32) without a finding; CEN's rules count such a tax scheme for neither.
- `haflinger.pdf.embed` replaces the PDF's document information with the invoice's, as its docstring says. Before, the input's other entries, such as `/Producer` and keys of its own, stayed in the result beside the invoice's title, subject, author and keywords.
- `read_invoice` reads a UBL VAT total (BT-110, BT-111) from the `cbc:TaxAmount` its `cac:TaxTotal` was chosen by. Before, where a first `cbc:TaxAmount` held an element and a second one a value, it read the first, which its `HAFL-VALUE` finding calls missing, and lost the second without a finding.
- `haflinger.pdf.extract_xml`, and `read_invoice` with a PDF, refuse an embedded invoice stored with FlateDecode and decode parameters other than none or a `/Predictor` of 1 with a reason naming the parameters. Before, the reason said that FlateDecode isn't decoded.

## [0.3.0] - 2026-11-26

### Added

- `check_german_vat(data)` checks a CII invoice or a UBL invoice or credit note that German invoicing law (§14 UStG) governs, which the caller decides, for what §14(4) UStG asks beyond the rules of its profile: KoSIT's German rules of XRechnung run on any profile and give `BR-DE-TMP-32` (the time of supply, `information`), `BR-DE-3`, `BR-DE-4`, `BR-DE-8` and `BR-DE-9` (city and post code of seller and buyer). Factur-X MINIMUM and BASIC WL get `HAFL-DE-PROFILE`, as they are no e-invoices under §14(1) UStG; small invoices of at most 250 EUR (§33 UStDV) drop the time of supply and the buyer's address, credit notes (`381`) and advance payments (`386`) the time of supply. It refuses what `validate` refuses, checks the XML Schema first and takes `max_size` and `timeout`. Every finding is meant to be shown, whatever its flag; `is_valid` isn't for them ([ADR-014](https://github.com/Interlusion/haflinger/blob/main/docs/arc42/adr/ADR-014-german-vat-checks.md)).

## [0.2.1] - 2026-11-20

### Fixed

- `read_invoice` leaves out a UBL VAT breakdown entry (`cac:TaxSubtotal`) or line tax category (`cac:ClassifiedTaxCategory`) of a tax other than VAT, such as `GST`, with a `HAFL-DROPPED` finding naming its tax scheme, as it does in CII, and a `cac:TaxTotal` holding only such entries gives no VAT total (BT-110, BT-111). Before, it read them as VAT without a finding; CEN's rules reject such an invoice. Of two `cac:TaxTotal` in one currency, the one holding the VAT breakdown gives BT-110, also where one without subtotals comes first, which before took BT-110 and left the breakdown out.
- `haflinger.pdf.embed` checks the PDF it writes and refuses, with `InvoiceWriteError` naming what differs, one that doesn't relate the invoice as `/Alternative`, or whose XMP metadata doesn't declare PDF/A-3b, an extension schema of Factur-X's namespace and, in that namespace, exactly one profile `EN 16931`, file name `factur-x.xml`, version `1.0` and document type `INVOICE`. Before, it handed out whatever `factur-x` wrote: the tests check the release they run with, and the extra `pdf` allows any from 7.9 on.

## [0.2.0] - 2026-11-18

An alpha. A finding's `location` is written anew, so code that reads it may need to change.

### Changed

- A finding's `location` is written as the official rules write theirs, an XPath whose every step is `Q{namespace}name[position]`, for Haflinger's own findings and the XML Schema check's too: it selects its element with no prefixes declared. Before, those gave paths with prefixes that nothing declared, and a UBL root without one. Where the XML Schema check names no element, or one that can't be told from its siblings, its finding still gives the line, `line n`.
- A refusal of `write_cii` for a term within an invoice line names the line: its position and its identifier (BT-126). A refusal for an entry of a group names its position among them.
- `validate` refuses an invoice whose empty elements' locations total more than 10,000,000 characters, with `InvoiceReadError`: each empty element fails `PEPPOL-EN16931-R008`, and a few hundred nested deep in a long namespace gave findings that took gigabytes.
- Tested on Linux on ARM and on macOS on Apple Silicon too, besides Linux on x86; the package names macOS among its operating systems.
- veraPDF, the reference PDF/A validator, checks in CI that the PDFs `haflinger.pdf.embed` writes are PDF/A-3.
- KoSIT's validator, the official tool, checks in CI that it gives the same verdict and the same findings as `validate` over KoSIT's test suite and the invoices `write_cii` writes from it.
- phax's converter `en16931-cii2ubl` checks in CI that the UBL copies it makes of the invoices `write_cii` writes from KoSIT's test suite, and of the ZUGFeRD corpus's CII invoices, read to the same model as the CII invoices.

### Fixed

- `validate`, `read_invoice` and `haflinger.pdf.embed` refuse an invoice any of whose BT-24 elements names another edition than 2017 anywhere in its whole text. Before, they checked only the start of the BT-24 that reading takes, the first that holds a value: an invoice whose second BT-24 names another edition, whose BT-24 holds an element, or whose BT-24 names another edition after a comment, was read with a `HAFL-DROPPED` or `HAFL-VALUE` finding or none; `embed` now refuses it with the edition as its reason. The reason quotes BT-24 shortened.
- `validate` runs the rules on a UBL invoice whose extension (`ext:ExtensionContent`) is nested more than 96 levels deep, or holds an element of more than 200 attributes, as KoSIT's validator does. Before, Saxon refused it at SaxonC's strict limits, 100 levels and 200 attributes, and `validate` gave a `HAFL-RULES` finding that made the invoice invalid. Saxon now parses up to 2,048 levels, where the XML Schema check stops with a `HAFL-XSD` finding, and up to 10,000 attributes, the limit of KoSIT's validator.
- `validate` compares BT-24 as KoSIT's validator does where a comment or a processing instruction splits it: by its whole text for XRechnung in a UBL invoice, by each piece of text otherwise, every BT-24 element counted, a Factur-X profile only where no profile of KoSIT's matches. Before, it compared the text with comments left out, and could run another profile's rules than KoSIT's validator, or a profile's rules where KoSIT's validator chooses none. A BT-24 that matches more than one profile names none, as in KoSIT's validator: CEN's rules run, with a `HAFL-PROFILE` warning.
- `read_invoice` reports a CII seller's or buyer's tax registration it leaves out, one with another `schemeID` than `VA` or, for the seller, `FC`, or none, with a `HAFL-DROPPED` finding; before, it left it out without one. Among them is `schemeID` `VAT`, which some producers write for `VA`; the official rules don't count it as a VAT identifier either. A CII tax representative's registration without `schemeID` is no longer read as its VAT identifier (BT-63), as CEN's `BR-56` counts only `VA`; it is left out with a finding too.
- `read_invoice` reads a UBL party's tax scheme `VAT` in any case, as CEN's rules do: a seller's `vat` gives its VAT identifier (BT-31), not its tax registration identifier (BT-32), a buyer's its VAT identifier (BT-48), which was left out, and a tax representative's its VAT identifier (BT-63), which was left out too.
- `validate` no longer raises `UnicodeDecodeError` for an invoice with an element whose prefixed name is longer than 98 bytes and holds characters outside ASCII; the XML Schema check's finding gives its line.

## [0.1.0] - 2026-11-11

The first release, an alpha; the README lists its known limits.

### Added

- One model of the EN 16931 business terms, frozen dataclasses with amounts as `Decimal` exactly as written.
- `read_invoice`: invoices in CII and UBL, and ZUGFeRD and Factur-X PDFs with the extra `pdf`, read into the model, with findings for what reading couldn't take in; outside input parsed without DTDs, entities or network access, within a size limit.
- `validate` and `is_valid`: the XML Schema, then the official rules chosen by BT-24: CEN's EN 16931 rules, KoSIT's XRechnung 3.0 rules and FeRD's Factur-X rules per profile, run unchanged in a worker process within a time limit.
- `write_cii` and `TARGET_PROFILES`: CII for EN 16931 and XRechnung 3.0, handed out only when it passes the XML Schema and the official rules of its target profile.
- `haflinger.pdf.extract_xml` and `haflinger.pdf.embed`, with the extra `pdf`: the invoice taken out of a ZUGFeRD PDF, and embedded into a PDF/A as a ZUGFeRD PDF of the profile EN 16931.
- The official files: KoSIT's validator configuration for XRechnung 3.0.2 (`v2026-08-31`, with CEN's rules 1.3.16), KoSIT's visualisation (`v2026-10-13`), FeRD's ZUGFeRD 2.5.2 (Factur-X 1.09.2) and SchXslt 1.10.1.

[0.1.0]: https://github.com/Interlusion/haflinger/tree/v0.1.0
[0.2.0]: https://github.com/Interlusion/haflinger/compare/v0.1.0...v0.2.0
[0.2.1]: https://github.com/Interlusion/haflinger/compare/v0.2.0...v0.2.1
[0.3.0]: https://github.com/Interlusion/haflinger/compare/v0.2.1...v0.3.0
[unreleased]: https://github.com/Interlusion/haflinger/compare/v0.3.0...HEAD
