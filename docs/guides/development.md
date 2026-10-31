# Development

| Meta | Value |
| :- | :- |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Draft: describes the layout the code is being rebuilt into, from the specs |

## Repository layout

The package's modules and what each is responsible for: [architecture, section 5](../arc42/README.md#5-building-block-view).

```
src/haflinger/            the package
  artefacts/<source>/     official stylesheets and rules, vendored (ADR-008)
tests/
  unit/                   per module, constructed inputs
  conformance/            against the official test files: both syntaxes,
                          both readers, round trip, XML Schema, rules
  data/<source>/          official test files, vendored (ADR-008)
scripts/
  corpus_report.py        runs a corpus of invoices through Haflinger (after the rebuild)
docs/                     specs, architecture, ADRs, guides, backlog
AGENTS.md                 rules for coding agents; CLAUDE.md imports it
pyproject.toml, uv.lock, .python-version
.gitattributes            keeps the vendored files byte for byte
.github/                  CI checks and Dependabot
```

Why this toolchain: [ADR-002](../arc42/adr/ADR-002-toolchain.md).

## Setup and checks

Requires [uv](https://docs.astral.sh/uv/). uv installs the Python version named in `.python-version`.

```sh
uv sync --locked --all-extras       # creates .venv from uv.lock, with dev tools and the pdf extra
uv run pytest                       # all tests; no network, no ERPNext
uv run ruff check && uv run ruff format --check
uv run basedpyright
uv run mdformat --check .           # Markdown; without --check it formats
```

CI runs the same checks on every pull request and on `main` (`.github/workflows/checks.yml`), with its Actions pinned to a commit; Dependabot proposes updates to them and to `uv.lock` weekly.

## Tests

- **Unit tests** check one module with inputs built in the test.
- **Conformance tests** check Haflinger against the official test files: CII and UBL give the same model ([REQ-003-PRS-F004](../specs/req-003-incoming-invoices.md#req-003-prs-f004-cii-and-ubl-agree)), KoSIT's reading stylesheet gives the same model as ours ([REQ-003-PRS-F005](../specs/req-003-incoming-invoices.md#req-003-prs-f005-two-readers-agree)), the official verdicts are reproduced ([REQ-002-PRS-F007](../specs/req-002-conformance.md#req-002-prs-f007-official-verdicts-reproduced)), and written invoices read back unchanged ([REQ-004-PRS-F006](../specs/req-004-outgoing-invoices.md#req-004-prs-f006-round-trip-over-the-kosit-suite)).

Tests come before code where a spec's Definition of Done describes the behaviour ([AGENTS.md](../../AGENTS.md)).

**When an official file looks wrong**, never edit it. Record the case in the test, with the business term and the reason, so that only that term is left out; the test that checks the recorded differences fails once a new release fixes it ([REQ-002-PRS-F008](../specs/req-002-conformance.md#req-002-prs-f008-differences-in-the-official-files)). Then tell upstream, the same for a rule that looks wrong:

1. Decide whether it is a defect. A difference the standard allows (zero or absent, [REQ-003-PRS-F004](../specs/req-003-incoming-invoices.md#req-003-prs-f004-cii-and-ubl-agree)) or a placeholder text is recorded with that reason, not reported.
2. Search the upstream issue tracker for an existing report.
3. An agent drafts the report: the release, the file names, the business case, the business term, both values. The maintainer files it; agents don't post to upstream trackers.
4. Link the issue in the record.

Where to report: the sources' trackers in [Upstream sources](#upstream-sources).

**When a written invoice fails a rule** because the model lacks a term, the writer's test lists the rule with the missing term ([REQ-004-PRS-F005](../specs/req-004-outgoing-invoices.md#req-004-prs-f005-official-rules)). When a new term makes a rule pass, its entry goes.

## Upstream sources

Where the official files come from, where their releases appear, and where to report a problem. A GitHub source takes reports in its issue tracker; the release feeds are what update checks read, never `api.github.com`.

| Source | What Haflinger takes | New releases | Licence |
| :- | :- | :- | :- |
| KoSIT [`validator-configuration-xrechnung`](https://github.com/itplr-kosit/validator-configuration-xrechnung) | The scenario file, KoSIT's XRechnung rules with CEN's EN 16931 rules, the CII D16B XML Schema | [releases.atom](https://github.com/itplr-kosit/validator-configuration-xrechnung/releases.atom) | Apache-2.0; CEN's rules EUPL-1.2; the schema © UN/CEFACT, unchanged with its notice |
| KoSIT [`xrechnung-visualization`](https://github.com/itplr-kosit/xrechnung-visualization) | The reading stylesheets | [releases.atom](https://github.com/itplr-kosit/xrechnung-visualization/releases.atom) | Apache-2.0 |
| KoSIT [`xrechnung-testsuite`](https://github.com/itplr-kosit/xrechnung-testsuite) | The business cases, CII and UBL | [releases.atom](https://github.com/itplr-kosit/xrechnung-testsuite/releases.atom) | Apache-2.0 |
| CEN [`eInvoicing-EN16931`](https://github.com/ConnectingEurope/eInvoicing-EN16931) | The unit tests of the EN 16931 rules (the rules themselves through KoSIT) | [releases.atom](https://github.com/ConnectingEurope/eInvoicing-EN16931/releases.atom) | EUPL-1.2 |
| FeRD's [ZUGFeRD package](https://www.ferd-net.de/en/downloads/publications) | The Factur-X rules and XML Schemas per profile, samples | FeRD's downloads page; the maintainer downloads through FeRD's form | Schemas and Schematron Apache-2.0 by FeRD's [rights of use](https://www.ferd-net.de/en/ueber-uns/ressourcen-1/veroeffentlichungen/disclaimer-and-rights-of-use-zugferd) |
| [`ZUGFeRD/corpus`](https://github.com/ZUGFeRD/corpus) | A selection of test files | No releases: pinned to a commit (`git ls-remote`) | Apache-2.0 |
| OpenPeppol [`peppol-bis-invoice-3`](https://github.com/OpenPEPPOL/peppol-bis-invoice-3) | Later: the Peppol BIS rules and unit tests | [releases.atom](https://github.com/OpenPEPPOL/peppol-bis-invoice-3/releases.atom) | To check |

FeRD takes reports through its website. Background on the bodies behind these sources: [E-Invoicing 101](e-invoicing-101.md).

## Updating official files

The rules are in [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md). One pull request per source and release:

1. Find the new release without `api.github.com`:

   ```sh
   git ls-remote --tags https://github.com/itplr-kosit/validator-configuration-xrechnung
   curl -s https://github.com/itplr-kosit/xrechnung-visualization/releases.atom
   ```

2. Download the release asset (or the files at the release's tag from `raw.githubusercontent.com`) into a new, empty directory outside the repository, and note its SHA-256:

   ```sh
   sha256sum xrechnung-3.0.2-validator-configuration-2026-08-31.zip
   ```

3. Replace the vendored files with the new ones, the same files as before unless the release adds or removes one the code uses. Don't edit them.

4. Update the source's README: release, commit, SHA-256, licence; and the licence file if it changed.

5. If the rules changed, take the tests that check them from the same release (CEN's unit tests with CEN's rules).

6. Run the tests. A failure is either a change Haflinger has to follow, or a new difference in the official files to record. The diff of the vendored files and the tests' verdict go into the pull request.

## Running the ZUGFeRD corpus

The script comes over from the spikes with the code rebuild; until then this section describes it as it will be. `scripts/corpus_report.py` runs every PDF and XML file below a directory through Haflinger: extraction from PDFs, both readers, their comparison, and validation. It prints a summary and writes one row per file as TSV. The corpus isn't vendored ([ITEM-002](../backlog/item-002-official-test-material.md)); clone it into a directory of its own:

```sh
git clone --filter=blob:none https://github.com/ZUGFeRD/corpus /path/to/zugferd-corpus
uv run python scripts/corpus_report.py /path/to/zugferd-corpus corpus.tsv
```

Files above 5 MB are read with Haflinger's mapping only; KoSIT's reading stylesheet takes minutes for them. The same clone serves the speed benchmarks of [REQ-002-PRS-NF002](../specs/req-002-conformance.md#req-002-prs-nf002-speed) and [REQ-003-PRS-NF002](../specs/req-003-incoming-invoices.md#req-003-prs-nf002-speed), which use its two large Peppol invoices (`PEPPOL/Valid/Qvalia/Large_Invoice_sample1.xml`, 25.7 MB, and `Large_Invoice_sample2.xml`, 61.1 MB).

## References

- [ADR-002](../arc42/adr/ADR-002-toolchain.md), [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md)
- [Specs index](../specs/README.md)
