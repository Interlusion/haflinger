# ADR-002: Toolchain and dependencies of a library that lives in its host's environment

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-10-30 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger is maintained mostly by agents with a person reviewing; they need fast, strict checks that run the same everywhere. It is a library, installed into its host's Python environment next to other packages, not an application with its own environment; the first host is a Frappe bench. It parses XML and PDFs from outside the company.

Every runtime dependency has to coexist with the versions its host pins; in a Frappe bench, those of Frappe and ERPNext. The spikes showed which ones Haflinger can't do without: Saxon for the official rules ([ADR-006](ADR-006-validation-with-official-rules.md)), and `factur-x` for ZUGFeRD PDFs, which brings `lxml`, `pypdf`, `requests`, `iso4217` and `python-stdnum` with it.

## Decision

- **Toolchain**: uv with `uv_build` and a locked `uv.lock`; development tools as dependency groups; ruff for linting and formatting; mdformat with `mdformat-gfm` (`.mdformat.toml`); basedpyright strict; pytest; coverage with branch coverage. CI with Dependabot and pinned Actions once the repository is on GitHub.
- **A lower bound on Python, not one exact version**: `requires-python = ">=3.14"`, developed and tested on 3.14 (`.python-version`). A library must install next to whatever its host runs.
- **Runtime dependencies, each for one job**:
  - `defusedxml` with the standard library's `ElementTree`, for parsing outside XML and for writing CII;
  - `saxonche`, for the official stylesheets ([ADR-006](ADR-006-validation-with-official-rules.md));
  - `lxml`, only for checking written invoices against their XML Schema ([ADR-006](ADR-006-validation-with-official-rules.md)); outside XML stays with `defusedxml`;
  - in the optional extra `pdf`: `factur-x`, for ZUGFeRD PDFs ([ADR-001](ADR-001-library-and-app.md)).
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

**Rejected because**: callers that handle only XML would carry `lxml`, `pypdf`, `requests` and the rest of `factur-x`'s dependencies.

## Consequences

### Positive

- One set of commands and checks, for people, agents and CI.
- The plain library has three runtime dependencies.

### Negative

- Saxon is large and native ([ADR-006](ADR-006-validation-with-official-rules.md)).
- Hand-written XML access instead of generated bindings.
- Two XML stacks: lxml checks written invoices against the XML Schema, beside ElementTree for everything else. Weighed when lxml arrived (2026-10-31): kept, because lxml there only reads documents Haflinger wrote itself.

## Reconsideration Triggers

1. A dependency's version range clashes with what Frappe/ERPNext v16 pins.
2. The Python version of Frappe/ERPNext v16 benches is below the lower bound.
3. lxml is needed for more than the XML Schema check of written invoices; then weigh one XML stack.

## Compliance

- A new runtime dependency SHALL come with a change to this ADR or a new ADR.
- Outside XML SHALL be parsed with `defusedxml`, DTDs and entities forbidden, before any other component sees it.

## References

- Affects: arc42 [§2](../README.md#2-constraints), [§4](../README.md#4-solution-strategy), [§7](../README.md#7-deployment-view), [§10](../README.md#10-quality-requirements)
- [ADR-006](ADR-006-validation-with-official-rules.md), [ADR-008](ADR-008-vendoring-official-files.md)
