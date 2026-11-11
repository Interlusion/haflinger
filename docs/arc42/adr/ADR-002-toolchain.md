# ADR-002: Toolchain and dependencies of a library that lives in its host's environment

| Meta | Value |
| :- | :- |
| **Status** | Accepted |
| **Date** | 2026-11-11 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger is maintained mostly by agents with a person reviewing; they need fast, strict checks that run the same everywhere. It is a library, installed into its host's Python environment next to other packages, not an application with its own environment; the first host is a Frappe bench. It parses XML and PDFs from outside the company.

Every runtime dependency has to coexist with the versions its host pins; in a Frappe bench, those of Frappe and ERPNext. The spikes showed which ones Haflinger can't do without: Saxon for the official rules ([ADR-006](ADR-006-validation-with-official-rules.md)), and `factur-x` for ZUGFeRD PDFs, which brings `lxml`, `pypdf`, `requests`, `iso4217` and `python-stdnum` with it.

## Decision

- **Toolchain**: uv with `uv_build` and a locked `uv.lock`; development tools as dependency groups; ruff for linting and formatting; mdformat with `mdformat-gfm` (`.mdformat.toml`); basedpyright strict; pytest; coverage with branch coverage, the rules' worker process included. CI on GitHub with pinned Actions, on a pinned runner image and the uv version `pyproject.toml` requires; a workflow grants no more than `contents: read` by default, and a job that needs more gets it alone and runs no code of the pull request. Besides the checks above, CI runs: a Markdown link check (lychee, offline: every relative link and `#anchor` resolves, and no wiki-links, which GitHub shows as text); branch coverage, reported in the run's summary and, for pull requests from this repository's branches, as one comment on the pull request, not a gate; a vulnerability audit of the lock with `uv audit` (OSV), in a job of its own, so that a known vulnerability stops a pull request before Dependabot's alert after the merge; actionlint, with shellcheck for the workflows' `run:` scripts, and zizmor for the workflows and Dependabot's configuration; and gitleaks over the pushed commits. The coverage comment and the release's GitHub Release ([ADR-013](ADR-013-releases.md)) are the two calls to `api.github.com`, authenticated with the workflow's token; scripts and agents otherwise stay off it, as its limit binds requests without a token. actionlint, gitleaks and lychee run from their images, pinned by digest in a Dockerfile each, so that Dependabot keeps them current: none ships a locked Python package with its binary for every platform. Dependabot proposes updates after a cooldown (14 days for Actions and images, 7 for Python packages), minor and patch updates as one pull request per ecosystem, security updates at once.
- **A lower bound on Python, not one exact version**: `requires-python = ">=3.14"`, developed and tested on 3.14 (`.python-version`). A library must install next to whatever its host runs.
- **Runtime dependencies, each for one job**:
  - `defusedxml` with the standard library's `ElementTree`, for parsing outside XML and for writing CII;
  - `saxonche`, for the official stylesheets ([ADR-006](ADR-006-validation-with-official-rules.md));
  - `lxml`, only for XML Schema checks ([ADR-006](ADR-006-validation-with-official-rules.md)), of written invoices and of incoming ones after `defusedxml` has checked them;
  - in the optional extra `pdf`: `factur-x`, for embedding invoices into PDFs, and `pypdf`, which `factur-x` brings anyway and Haflinger uses directly to take the invoice out of a PDF ([ADR-001](ADR-001-library-and-app.md)).
- **The model as frozen dataclasses** with `Decimal` and `date`, not pydantic.
- **Test-only tools stay in the test group**.
- **No container image**: the library is published as a package.
- Official artefacts and test files: [ADR-008](ADR-008-vendoring-official-files.md).

## Alternatives Considered

### Alternative 1: lxml for all XML

**Rejected because**: a compiled library with its own parser settings to get right for hostile input, where `defusedxml` gives safe defaults. lxml came for the XSD check, and comes with the `pdf` extra too; outside XML is still parsed with `defusedxml`.

### Alternative 2: pydantic models

**Rejected because**: the model needs no parsing from JSON yet, and Frappe benches pin their own pydantic version. Revisit when the model is exchanged as JSON.

### Alternative 3: Exactly one Python version

**Rejected because**: right for an application with its own image, wrong for a library installed into someone else's environment.

### Alternative 4: PDF support in the plain library

**Rejected because**: callers that handle only XML would carry `pypdf`, `requests` and the rest of `factur-x`'s dependencies. `lxml`, which `factur-x` needs too, is a dependency of the plain library anyway, for the XML Schema checks.

## Consequences

### Positive

- One set of commands and checks, for people, agents and CI.
- A broken link, a vulnerable dependency, a workflow that grants more than it needs and a committed secret stop a pull request before review.
- The plain library has three runtime dependencies.

### Negative

- Saxon is large and native ([ADR-006](ADR-006-validation-with-official-rules.md)).
- Three of CI's checks need Docker locally (`scripts/check-links.sh`, `scripts/check-workflows.sh`, `scripts/check-secrets.sh`); measuring the worker process makes the tests with coverage about a third slower.
- Hand-written XML access instead of generated bindings.
- Two XML stacks: lxml checks invoices against their XML Schema, beside ElementTree for everything else. Weighed when lxml arrived (2026-10-31), and again when the schema check came to incoming invoices (2026-11-01, trigger 3): kept, because `defusedxml` stays the gate for outside input, and lxml only reads what has passed it, with entities, DTDs and the network off.

## Reconsideration Triggers

1. A dependency's version range clashes with what Frappe/ERPNext v16 pins. Fired on 2026-11-01: Frappe v16 pins `pypdf==6.19.0`, while the `pdf` extra asked for 6.21.4 or later, so `haflinger[pdf]` couldn't be installed into a v16 bench; the extra's lower bound came down to 6.19.0, and CI tests with the versions Frappe v16 pins (see Compliance): `pypdf==6.19.0`, and `requests~=2.33.0`, which `factur-x` imports.
2. The Python version of Frappe/ERPNext v16 benches is below the lower bound. Checked on 2026-11-01: Frappe's `version-16` requires `>=3.14,<3.15`, ERPNext `>=3.14`; Haflinger's `>=3.14` fits.
3. lxml is needed for more than XML Schema checks; then weigh one XML stack.

## Compliance

- A new runtime dependency SHALL come with a change to this ADR or a new ADR.
- Outside XML SHALL be parsed with `defusedxml`, DTDs and entities forbidden, before any other component sees it.
- The lower bounds of the dependencies SHALL admit the versions Frappe/ERPNext v16 pin, and CI SHALL run the tests with those versions as well as with the locked ones.

## References

- Affects: arc42 [§2](../README.md#2-constraints), [§4](../README.md#4-solution-strategy), [§7](../README.md#7-deployment-view), [§10](../README.md#10-quality-requirements)
- [ADR-006](ADR-006-validation-with-official-rules.md), [ADR-008](ADR-008-vendoring-official-files.md)
