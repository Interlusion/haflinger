# AGENTS.md

Instructions for coding agents working on Haflinger. `CLAUDE.md` imports this file; edit the rules here.

## Project

Haflinger: e-invoicing in Python (ZUGFeRD, XRechnung, Peppol). A library with one model of the EN 16931 business terms, read from CII, UBL and ZUGFeRD PDFs, validated with the official rules, written as CII and ZUGFeRD PDFs. Its first user is an ERPNext app, later and in its own repository. See `README.md` and the [architecture](docs/arc42/README.md).

## Rules

- **This repository is the library.** Anything about ERPNext (mapping its documents, print formats, the review flow) belongs to the app, in its own repository; the library imports no Frappe or ERPNext code ([ADR-001](docs/arc42/adr/ADR-001-library-and-app.md)).
- **Incoming invoices are outside input.** XML is parsed with `defusedxml`: no DTDs, no entities, no network access.
- **Amounts are `Decimal`, exactly as written.** No floats, no rounding on reading or writing.
- **Integrate, don't implement.** No business rule is reimplemented where an official Schematron covers it; official artefacts run unchanged ([ADR-003](docs/arc42/adr/ADR-003-integrate-dont-implement.md)).
- **Vendored files stay byte for byte.** Official artefacts and test files are pinned to a release, with a provenance README, and never edited ([ADR-008](docs/arc42/adr/ADR-008-vendoring-official-files.md)); updating them: [development guide](docs/guides/development.md#updating-official-files).
- **Official test files are the reference.** Behaviour against them is tested; a file is never edited to make a test pass. Where an official file looks wrong, the test records the exception with a reason.
- The project is **Haflinger** in prose, `haflinger` as an identifier (package, repository), `HAFLINGER_` for variables.
- The names "ERPNext" and "Frappe" don't go into the project or package name (Frappe's trademark policy); descriptions may say "for ERPNext".
- Nothing specific to one company goes into this repository: examples use placeholders such as `Example GmbH`.

## Docs

Start at `docs/README.md`. The specs in `docs/specs/` are the contract: a new business term or a changed behaviour starts there, then tests, then code. Read REQ-001 first, then the spec the placement map in the [specs index](docs/specs/README.md) names. Decisions are ADRs in `docs/arc42/adr/`; a decision that changes one is a new ADR or, while it is Proposed, an edit.

- **Tests first** where a spec's Definition of Done describes the behaviour: write the failing test from it, run it red, then write the code. Commit the tests before the code (`test:` then `feat:`).
- Write requirement IDs in full (`REQ-003-PRS-F004`, not `PRS-F004`), and business terms by their EN 16931 ID (`BT-110`, `BG-23`).
- **Analyses are temporary.** `docs/analysis/analysis-NNN-*.md` hold explorations and spike results; once their findings are carried into ADRs, specs, guides or the backlog, they move to `docs/analysis/archive/`. ADRs, specs and guides never link to an analysis: they state the facts they rely on.

## Conventions

- Conventional Commits: `feat`, `fix`, `docs`, `ci`, `chore`, `refactor`, `test`.
- Keep scripts and agents off `api.github.com`: use `git ls-remote`, `raw.githubusercontent.com`, `releases.atom`.
- Markdown: one line per paragraph, no hard wrapping. `mdformat` formats it (config in `.mdformat.toml`).
- Checks: `uv run ruff check`, `uv run ruff format --check`, `uv run mdformat --check .`, `uv run basedpyright`, `uv run pytest` ([development guide](docs/guides/development.md)).
- Commit or push only when the maintainer asks.
