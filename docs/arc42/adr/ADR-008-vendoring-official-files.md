# ADR-008: Official artefacts and test files vendored, pinned and byte for byte

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger runs official artefacts (KoSIT's reading stylesheets, the validation rules, XML Schemas) and tests against official test files ([ADR-003](ADR-003-integrate-dont-implement.md)). Their owners publish them in Git repositories and as release archives, several times a year.

What the spikes ran into:

- Rules and the unit tests that check them, taken from different releases (CEN 1.3.16 against tests of 1.3.17), gave 65 false misses.
- Git's `core.autocrlf=input` silently stored the CRLF line endings of the UN/CEFACT XML Schemas as LF, so the files in the repository were no longer the published ones.
- The runtime artefacts are small (2.9 MB at first, 6 MB with the Factur-X rules and the UBL schemas); test corpora can be large (the ZUGFeRD corpus is 152 MB).

## Decision

- **Vendored in the repository**: runtime artefacts under `src/haflinger/artefacts/<source>/`, test files under `tests/data/<source>/`. Only the files used, not whole repositories; a folder a release ships as one piece (a schema with its modules, SchXslt's pipeline) stays whole, and its README marks what isn't used.
- **Unchanged, byte for byte.** `.gitattributes` marks both directories `-text`. A file is never edited to make something work; a needed fix waits for the upstream release, or is carried as a separate, documented patch with a test.
- **Provenance per source**: a README naming the source repository, the release tag, the commit, the archive's SHA-256 when it came from a release asset, and the licence; the source's licence file next to it.
- **Pinned to a release, consistently**: rules and the tests that check them come from the same release.
- **Fetched at update time only**: nothing is downloaded when Haflinger is installed or runs.
- **One pull request per source and release.** New releases are found without `api.github.com` (`git ls-remote`, `releases.atom`, `raw.githubusercontent.com`); the tests show what changed. The procedure goes into the development guide.
- **Large corpora are not vendored.** A small, chosen selection may be, under the same rules.

## Alternatives Considered

### Alternative 1: Download at build or install time

**Rejected because**: network access at install, builds that differ by date, and an upstream outage or compromise reaching every install.

### Alternative 2: Git submodules

**Rejected because**: whole repositories, many release assets aren't in Git at all, and submodules don't end up in a wheel.

### Alternative 3: Take them from a package that bundles them (for example `factur-x`'s XSDs and Schematron)

**Rejected because**: another party's choice of version and of what to include, with no record of the source release. Allowed for tests only, with the package version pinned.

## Consequences

### Positive

- Reproducible and offline: the same commit runs the same rules everywhere.
- Every update is a reviewable diff of the official files, with the tests' verdict.

### Negative

- The repository grows with each source.
- Updates are pull requests to make and review, even when upstream changed little.
- Each source's licence is tracked by hand ([ADR-009](ADR-009-licences-and-name.md)).

## Reconsideration Triggers

1. The owners publish their artefacts as versioned packages.
2. The vendored files make the repository or the wheel too large to handle.

## Compliance

- Vendored files SHALL NOT be edited.
- Every vendored source SHALL have a README with source, release, commit and licence.
- Rules and the tests that check them SHALL come from the same release.

## References

- Affects: arc42 [§2](../README.md#2-constraints), [§4](../README.md#4-solution-strategy), [§8](../README.md#8-cross-cutting-concepts), [§10](../README.md#10-quality-requirements), [§11](../README.md#11-risks-and-technical-debt)
- [ADR-003](ADR-003-integrate-dont-implement.md), [ADR-006](ADR-006-validation-with-official-rules.md), [ADR-009](ADR-009-licences-and-name.md)
- [AGENTS.md](../../../AGENTS.md)
