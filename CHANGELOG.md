# Changelog

What changed in each release of Haflinger, for its callers. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html): while Haflinger is at 0.x, a minor version may break the interface ([ADR-013](https://github.com/Interlusion/haflinger/blob/main/docs/arc42/adr/ADR-013-releases.md)).

## [Unreleased]

### Changed

- Tested on Linux on ARM and on macOS on Apple Silicon too, besides Linux on x86; the package names macOS among its operating systems.
- veraPDF, the reference PDF/A validator, checks in CI that the PDFs `haflinger.pdf.embed` writes are PDF/A-3.

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
[unreleased]: https://github.com/Interlusion/haflinger/compare/v0.1.0...HEAD
