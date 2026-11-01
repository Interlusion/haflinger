# Documentation

## Quick navigation

| I want to … | Read |
| :- | :- |
| Understand e-invoicing: standards, formats, who is in charge | [E-Invoicing 101](guides/e-invoicing-101.md) |
| Know what Haflinger must do | [Specs](specs/README.md): REQ-001 core, REQ-002 conformance, REQ-003 incoming and REQ-004 outgoing invoices |
| Understand how it fits together | [Architecture](arc42/README.md) |
| Know why it is built this way | [ADRs](arc42/adr/README.md) |
| Work on it: setup, checks, tests, updating official files | [Development](guides/development.md) |
| See the analysis in progress | [Analysis 006](analysis/analysis-006-second-review.md): the second review, from six angles; older analyses in the [archive](analysis/archive/) |
| See open work | [Backlog](backlog/backlog.md): quick items, and the `item-NNN` files in the same [folder](backlog/) |

## Directories

- **`specs/`**: requirement specifications. They are the contract: a new business term or a changed behaviour starts there.
- **`arc42/`**: the architecture, all sections in one file for now; `arc42/adr/` holds the decisions.
- **`guides/`**: introductions and how-tos, kept current.
- **`analysis/`**: reviews and research that feed ADRs and specs, numbered `analysis-NNN-*.md`; not updated afterwards. Once their findings are carried into ADRs, specs, guides or the backlog, they move to `analysis/archive/`.
- **`backlog/`**: `backlog.md` for quick items, `item-NNN-*.md` for items with detail, `archive/` for done or rejected ones.

## Document status

| Document | Status |
| :- | :- |
| Specs | Draft until baselined |
| ADRs | Proposed until accepted, edited in place until then; once Accepted, superseded by new ADRs rather than rewritten |
| Architecture, guides | Kept current with every change they describe |
| Analyses | Temporary; archived once their findings are carried over |
| Backlog | Living |

## Conventions

- **Generic only.** Placeholders such as `Example GmbH`, never a real company's data.
- **Plain Markdown links**, so they work on GitHub.
- **Source of truth:** the specs for what Haflinger must do; the code for what it does. When docs and code disagree, fix one of them in the same change.
- Agent-drafted documents say so under Author.
