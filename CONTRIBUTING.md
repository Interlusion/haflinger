# Contributing

Haflinger is maintained for our own use, first for ERPNext. Contributions are welcome; support isn't promised, and we may decline a change that doesn't fit what Haflinger is for ([README](README.md)).

## Before you start

- **A vulnerability** goes through [SECURITY.md](SECURITY.md), never an issue.
- **A bug:** open an issue with the bug report form.
- **A new business term, profile or behaviour:** open an issue with the feature form first.
- **Never attach a real invoice**, to an issue, a pull request or a test: invoices hold names, addresses, bank details and amounts. Name the official test file that shows the problem, with its release, or build an invoice with placeholders such as `Example GmbH`.

What Haflinger is not for:

- **Reimplementing the official rules.** Haflinger runs KoSIT's, CEN's and FeRD's rules unchanged and never rewrites what they check; a rule they lack goes to their projects first. A check of Haflinger's own, such as a German requirement beyond the official rules, needs a spec and an ADR before code ([ADR-003](docs/arc42/adr/ADR-003-integrate-dont-implement.md)).
- **Editing the official files.** Vendored artefacts and test files stay byte for byte as their source ships them, and an update replaces them from it ([development guide](docs/guides/development.md#updating-official-files)). A file that looks wrong is recorded in a test with its reason, and a defect in it is reported upstream ([ADR-008](docs/arc42/adr/ADR-008-vendoring-official-files.md), [development guide](docs/guides/development.md#tests)).
- **ERPNext itself.** Mapping ERPNext's documents, print formats and the review of incoming invoices belong to the ERPNext app, in its own repository; the library imports no Frappe or ERPNext code ([ADR-001](docs/arc42/adr/ADR-001-library-and-app.md)).

## How a change is made

1. **Spec first:** a new business term or a changed behaviour starts in the spec the [specs index](docs/specs/README.md) names, after REQ-001.
2. **Tests first,** where a spec's Definition of Done describes the behaviour: the failing test is committed before the code.
3. **The code,** with the checks of the [development guide](docs/guides/development.md#setup-and-checks) passing locally.

[AGENTS.md](AGENTS.md), the rules for coding agents, holds the rules every change follows, such as exact amounts, safe parsing of outside XML and placeholders instead of company data.

## Commits and pull requests

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) with the types `feat`, `fix`, `docs`, `ci`, `chore`, `refactor` and `test`, one topic per commit, and name requirement IDs in full (`REQ-003-PRS-F004`) and business terms by their EN 16931 ID (`BT-110`). The pull request template lists what review looks for.

## Licence

Haflinger is licensed under [Apache-2.0](LICENSE). Unless you state otherwise, a contribution you submit for inclusion is licensed under Apache-2.0 without additional terms (section 5 of the licence); there is no separate agreement and no sign-off line. Vendored official files keep their own licences ([ADR-009](docs/arc42/adr/ADR-009-licences-and-name.md)) and come from their upstream sources, pinned to a release or a commit ([ADR-008](docs/arc42/adr/ADR-008-vendoring-official-files.md)).
