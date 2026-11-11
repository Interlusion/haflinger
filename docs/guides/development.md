# Development

| Meta | Value |
| :- | :- |
| **Date** | 2026-11-11 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Current |

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
typings/                  type stubs for saxonche and factur-x, which ship none
scripts/
  corpus_report.py        runs a corpus of invoices through Haflinger
  term_report.py          the business terms invoices carry that the model lacks
  benchmark.py            time and memory against the specs' limits
  check-links.sh          the Markdown link check
  check-workflows.sh      actionlint and zizmor
  check-secrets.sh        gitleaks over the commits
  prepare_release.py      a release's checks, and the links to its tag
docs/                     specs, architecture, ADRs, guides, backlog
AGENTS.md                 rules for coding agents; CLAUDE.md imports it
CONTRIBUTING.md           how a change is made; SECURITY.md: reporting a vulnerability
CHANGELOG.md              what each release changed, for callers (ADR-013)
pyproject.toml, uv.lock, .python-version
.gitattributes            keeps the vendored files byte for byte
lychee.toml               the link check: local links and #anchors only, the README's
                          absolute links as the local files
THIRD-PARTY-NOTICES       the vendored files in the package and their terms (ADR-009)
.github/                  CI checks and releases, Dependabot, the images of CI's tools,
                          issue and pull request templates, CODEOWNERS
```

Why this toolchain: [ADR-002](../arc42/adr/ADR-002-toolchain.md).

## Setup and checks

Requires [uv](https://docs.astral.sh/uv/). uv installs the Python version named in `.python-version`; `pyproject.toml` names the uv version (`required-version`), which CI uses too.

```sh
uv sync --locked --all-extras       # creates .venv from uv.lock, with dev tools and the pdf extra
uv run pytest                       # all tests; no network, no ERPNext
uv run ruff check && uv run ruff format --check
uv run basedpyright
uv run mdformat --check .           # Markdown; without --check it formats
scripts/check-links.sh              # no wiki-links; local links and #anchors resolve (Docker)
scripts/check-workflows.sh          # actionlint with shellcheck (Docker), zizmor
scripts/check-secrets.sh            # gitleaks over all of HEAD's commits, or those after a base (Docker)
uv run coverage erase && uv run coverage run -m pytest && uv run coverage combine && uv run coverage report
```

## CI

`checks.yml` runs on pull requests and pushes to `main`, without secrets ([ADR-002](../arc42/adr/ADR-002-toolchain.md)):

- **`checks`**: the lock, ruff, mdformat, the Markdown link check (the README's links absolute, as PyPI shows it, and checked as the local files), basedpyright, pytest with branch coverage, the rules' worker process included (the table in the run's summary and, for pull requests from this repository's branches, as one comment on the pull request that each push updates; not a gate), and the workflows and Dependabot's configuration (actionlint, zizmor);
- **`coverage-comment`**: posts that comment with `gh pr comment`, authenticated with the workflow's token: the one exception to keeping scripts off `api.github.com`, whose limit binds requests without a token; the only job that may write, and it runs no code of the pull request;
- **`audit`**: the vulnerability audit of the lock (`uv audit --locked`), a job of its own, so that a new advisory or the advisory database out of reach fails it alone;
- **`secrets`**: gitleaks over the pushed commits (`scripts/check-secrets.sh`), over all of HEAD's where the base before the push isn't in the clone, as after a force push;
- **`frappe-v16-pins`**: the tests once more with the versions of shared dependencies that Frappe/ERPNext v16 pin (for now `pypdf==6.19.0` and `requests~=2.33.0`, which `factur-x` imports), so that Haflinger stays installable into a bench.

`release.yml` runs on a tag `vX.Y.Z` and publishes that version to PyPI, after the maintainer's approval ([releasing guide](releasing.md), [ADR-013](../arc42/adr/ADR-013-releases.md)): `build` checks the tag against `pyproject.toml` and `CHANGELOG.md` and that its commit is on `main`, points the links to `main` in the README and the project URLs at the tag, builds the package with the backend uv bundles and runs the tests against the wheel; `publish`, in the environment `pypi`, uploads it through Trusted Publishing, its only right `id-token: write`.

A newer push to a pull request's branch cancels the run before it; on `main`, each commit keeps its run. Actions are pinned to a commit, the runner image to `ubuntu-24.04` and uv to a version (`required-version` in `pyproject.toml`), which lies within the range of `uv_build` that `[build-system]` names, so that `uv build` uses the backend uv bundles instead of downloading one (`tests/unit/test_release.py` checks it: an update of `uv_build` raises `required-version` with it); the images of actionlint, gitleaks and lychee are pinned by digest in `.github/<tool>/Dockerfile`. Dependabot proposes updates to Actions and images weekly once a new version is 14 days old, to `uv.lock` once it is 7 days old, minor and patch updates as one pull request per ecosystem; security updates come at once (`.github/dependabot.yml`).

## Tests

- **Unit tests** check one module with inputs built in the test.
- **Conformance tests** check Haflinger against the official test files: CII and UBL give the same model ([REQ-003-PRS-F004](../specs/req-003-incoming-invoices.md#req-003-prs-f004-cii-and-ubl-agree)), KoSIT's reading stylesheet gives the same model as ours ([REQ-003-PRS-F005](../specs/req-003-incoming-invoices.md#req-003-prs-f005-two-readers-agree)), the official verdicts are reproduced ([REQ-002-PRS-F007](../specs/req-002-conformance.md#req-002-prs-f007-official-verdicts-reproduced)), and written invoices read back unchanged ([REQ-004-PRS-F006](../specs/req-004-outgoing-invoices.md#req-004-prs-f006-round-trip-over-the-kosit-suite)).

Tests come before code where a spec's Definition of Done describes the behaviour ([AGENTS.md](../../AGENTS.md)).

**FeRD's samples** aren't vendored, as no terms name them ([ITEM-002](../backlog/item-002-official-test-material.md)). Their tests (`tests/conformance/test_ferd_samples.py`) read the unpacked ZUGFeRD package from the path in `HAFLINGER_FERD_PACKAGE`, and are skipped without it. The package's XRechnung samples (`Examples/5. XRECHNUNG`) aren't among them: each fails `CII-SR-465`, which KoSIT's scenarios raise to error, so by the official verdict they are invalid.

**veraPDF**, the reference PDF/A validator, checks the PDFs `embed` writes where it is installed ([REQ-004-PRS-F007](../specs/req-004-outgoing-invoices.md#req-004-prs-f007-zugferd-pdf)); otherwise its test is skipped. Install it from [verapdf.org](https://verapdf.org/software/) (it needs Java) and put `verapdf` on the `PATH`, or name the program in `HAFLINGER_VERAPDF`.

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
| KoSIT [`validator-configuration-xrechnung`](https://github.com/itplr-kosit/validator-configuration-xrechnung) | The scenario file, KoSIT's XRechnung rules with CEN's EN 16931 rules, the CII D16B and UBL 2.1 XML Schemas | [releases.atom](https://github.com/itplr-kosit/validator-configuration-xrechnung/releases.atom) | Apache-2.0; CEN's rules EUPL-1.2; the CII schema © UN/CEFACT, unchanged with its notice; the UBL schemas © OASIS, W3C and UN/CEFACT, unchanged with their notices, two XAdES schemas without one ([README](../../src/haflinger/artefacts/kosit-validator-xrechnung/README.md)) |
| KoSIT [`xrechnung-visualization`](https://github.com/itplr-kosit/xrechnung-visualization) | The reading stylesheets | [releases.atom](https://github.com/itplr-kosit/xrechnung-visualization/releases.atom) | Apache-2.0 |
| KoSIT [`xrechnung-testsuite`](https://github.com/itplr-kosit/xrechnung-testsuite) | The business cases, CII and UBL | [releases.atom](https://github.com/itplr-kosit/xrechnung-testsuite/releases.atom) | Apache-2.0 |
| CEN [`eInvoicing-EN16931`](https://github.com/ConnectingEurope/eInvoicing-EN16931) | The unit tests of the EN 16931 rules (the rules themselves through KoSIT) | [releases.atom](https://github.com/ConnectingEurope/eInvoicing-EN16931/releases.atom) | EUPL-1.2 |
| FeRD's [ZUGFeRD package](https://www.ferd-net.de/en/downloads/publications) | The Factur-X Schematron and XML Schemas per profile | FeRD's downloads page; the maintainer downloads through FeRD's form | Schemas and Schematron Apache-2.0 by FeRD's [rights of use](https://www.ferd-net.de/en/ueber-uns/ressourcen-1/veroeffentlichungen/disclaimer-and-rights-of-use-zugferd) |
| [`ZUGFeRD/corpus`](https://github.com/ZUGFeRD/corpus) | A selection of test files | No releases: pinned to a commit (`git ls-remote`) | Apache-2.0 |
| [SchXslt](https://codeberg.org/SchXslt/schxslt) | The Schematron compiler for FeRD's Factur-X rules | Codeberg releases (`git ls-remote --tags`) | MIT |
| veraPDF [`veraPDF-corpus`](https://github.com/veraPDF/veraPDF-corpus) | One PDF/A file, the input for embedding invoices | Tags (`git ls-remote --tags`) | CC BY 4.0 |
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

4. Update the source's README: release, commit, SHA-256, licence; and the licence file if it changed. For a runtime source, also its block in `THIRD-PARTY-NOTICES`, with its `Licence` line, and the licence expression in `pyproject.toml` where a licence was added or dropped; `tests/unit/test_vendoring.py` checks that they agree.

5. If the rules changed, take the tests that check them from the same release (CEN's unit tests with CEN's rules).

6. Run the tests. A failure is either a change Haflinger has to follow, or a new difference in the official files to record. The diff of the vendored files and the tests' verdict go into the pull request.

## Running the ZUGFeRD corpus

`scripts/corpus_report.py` runs every PDF and XML file below a directory through Haflinger: the invoice taken out of a PDF, both readers, the business terms on which they differ (after KoSIT's known limits that `_kosit.comparable` evens out: the UBL notes' subject codes, and a CII object identifier's scheme), and validation. It prints a summary, with any crash (an exception other than `InvoiceReadError`), and writes one row per file as TSV. A file below a `fail` folder is marked as filed as failing. Only a few of its files are vendored, in `tests/data/zugferd-corpus/` ([ITEM-002](../backlog/item-002-official-test-material.md)); clone it into a directory of its own:

```sh
git clone --filter=blob:none https://github.com/ZUGFeRD/corpus /path/to/zugferd-corpus
uv run python scripts/corpus_report.py /path/to/zugferd-corpus corpus.tsv
```

Files above 5 MB are read with Haflinger's mapping only; KoSIT's reading stylesheet takes minutes for them. At the corpus's commit `82e886f`, run on 2026-11-07 with the line references: 240 files, no crash; 3 PDFs refused when their invoice is taken out, 197 read, 40 refused (22 ZUGFeRD 1.0, 14 FatturaPA, the rest broken or another format). The readers agree on all but 26 files, each a limit of KoSIT's reading stylesheet that [ITEM-006](../backlog/item-006-upstream-reports.md) records: 12 CII invoices with remittance information (BT-83) but no payment means, which the stylesheet loses, two of them also with a charge on a line's price, which it takes as the discount (BT-147); 12 whose seller contact gives both a person and a department name, which it gives as two contact points (BT-41); and the two EXTENDED invoices with two due dates and two payment terms, which it joins into one value each (BT-9, BT-20).

The same clone serves the benchmark of [REQ-002-PRS-NF002](../specs/req-002-conformance.md#req-002-prs-nf002-speed), [REQ-003-PRS-NF002](../specs/req-003-incoming-invoices.md#req-003-prs-nf002-speed) and [REQ-004-PRS-NF001](../specs/req-004-outgoing-invoices.md#req-004-prs-nf001-speed), which uses its two large Peppol invoices (`PEPPOL/Valid/Qvalia/Large_Invoice_sample1.xml`, 25.7 MB, and `Large_Invoice_sample2.xml`, 61.1 MB). It prints a Markdown table with the machine it ran on, to record with a release; without the clone, the large invoices' rows are skipped:

```sh
uv run python scripts/benchmark.py /path/to/zugferd-corpus
```

## The terms the model doesn't hold yet

`scripts/term_report.py` orders the model's growth by what invoices commonly carry ([ADR-007](../arc42/adr/ADR-007-model-scope-and-editions.md)). It runs every PDF and XML file of the KoSIT test suite, and of each directory given, through KoSIT's reading stylesheet, which names every business term it finds, and prints a Markdown table of the terms of EN 16931 that the model doesn't hold (those REQ-001-PRS-F001's table doesn't name), with each one's group and how many files of each directory carry it. XRechnung's extension is left out, the terms within its groups too (such as a sub-invoice line's), and so are files above 5 MB, as in the corpus report; a file KoSIT's stylesheet fails on, by its time limit or a crash, is counted apart from those refused. The KoSIT suite is made to cover every term, so its counts show what the tests exercise; a clone of the ZUGFeRD corpus shows what invoices carry:

```sh
uv run python scripts/term_report.py /path/to/zugferd-corpus
```

## References

- [ADR-002](../arc42/adr/ADR-002-toolchain.md), [ADR-008](../arc42/adr/ADR-008-vendoring-official-files.md)
- [Specs index](../specs/README.md)
