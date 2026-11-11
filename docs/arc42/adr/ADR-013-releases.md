# ADR-013: Releases: SemVer, a changelog, and PyPI from a tag through Trusted Publishing

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-11 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger isn't released. The name is reserved on PyPI with a placeholder 0.0.0 without code, yanked; `pyproject.toml` says 0.0.0 too. The API the first release fixes is what `haflinger` and `haflinger.pdf` export ([ADR-012](ADR-012-public-api.md)). The security policy already promises fixes for the latest minor version only, and warns that while Haflinger is at 0.x a minor version may break the interface.

Its first caller, the ERPNext app, installs it into a bench ([ITEM-003](../../backlog/item-003-erpnext-app.md)), and so does anyone else: from PyPI, by version. A caller needs to know from a version number whether an update may break their code, and from a list in their words what changed; the commits say what changed for the maintainers, tests and docs included. An update of the official files changes verdicts without touching the code ([ADR-008](ADR-008-vendoring-official-files.md)).

Uploading from a maintainer's machine needs a PyPI API token: a secret that lasts until it is revoked, and nothing ties the uploaded files to a commit. PyPI's Trusted Publishing lets a workflow of a named repository upload instead: GitHub gives the run a signed identity (OpenID Connect), PyPI checks it against the publisher configured for the project and hands out a token that expires within minutes. Uploaded this way, pypa's publish action also signs an attestation for each file (PEP 740): which repository, workflow and commit built it, which PyPI shows and anyone can verify.

The README's links are absolute and point at `main`, so that they work on PyPI; PyPI keeps each release's README, so a release's page would show the files as they are on `main` later, not as they were released ([backlog](../../backlog/backlog.md)). `uv_build`, the build backend ([ADR-002](ADR-002-toolchain.md)), reads a static version from `pyproject.toml`; it has no dynamic versions from Git tags.

## Decision

- **Versions follow Semantic Versioning, from 0.1.0**, raised by what changes for a caller, as the table below gives. The interface is ADR-012's: the names the two `__all__` list and the behaviour the specs describe. Haflinger promises the official verdict of the official files it ships, not a frozen one: a new release of them that fixes rules is a fix, whether or not Haflinger's code changes. While Haflinger is at 0.x, a minor version takes the place of a major one: 0.2.0 may break what 0.1.x offers. Versions have the form `X.Y.Z`, without leading zeros, the same in SemVer and in Python's versions (PEP 440).
- **1.0.0** comes once the ERPNext app runs on Haflinger in production and the interface has gone a few minor versions without a breaking change.
- **Deprecated before removed**: from 1.0.0, a name or a profile that a major version removes is listed under Deprecated in the changelog, with a `DeprecationWarning` where the code can give one, at least one minor version before.
- **One version, in `pyproject.toml`**, set with `uv version X.Y.Z`, which updates `uv.lock` too. Haflinger has no `__version__`, a name ADR-012 doesn't export; a caller asks `importlib.metadata.version("haflinger")`.
- **`CHANGELOG.md`, in the format of Keep a Changelog 1.1.0**: a change a caller notices adds its entry under "Unreleased" in the same pull request, under Added, Changed, Deprecated, Removed, Fixed or Security; a new release of official files names that release. Tests, docs, CI and refactoring get no entry. A release moves the entries into a section of its own, `## [X.Y.Z] - YYYY-MM-DD`.
- **A release is a tag** `vX.Y.Z` on the merge commit of the pull request that sets the version and the changelog's section, pushed by the maintainer. A version on PyPI is never replaced (PyPI refuses a file name once used), and its tag is never moved or deleted; a broken release is yanked and followed by a patch.
- **`release.yml` runs on the tag**, in two jobs, with no token or password stored and no call to `api.github.com`:
  - `build`, with `contents: read`: `scripts/prepare_release.py` refuses unless the tag is `v` and `pyproject.toml`'s version, and `CHANGELOG.md` has that version's section with a date and entries right below an empty "Unreleased", then points the links to `main` in the README and in `pyproject.toml`'s project URLs at the tag; the workflow refuses a commit that isn't on `main`; `uv build` builds the sdist and the wheel; the tests run against the wheel, installed with the extra `pdf` into an environment of its own; the files are kept as an artefact of the run.
  - `publish`, with `id-token: write` alone: in the environment `pypi`, which waits for the maintainer's approval and admits only tags `v*`, pypa's publish action uploads the files through Trusted Publishing, with their attestations; run again, it skips the files PyPI already has.
- **No GitHub Release**: the tag and `CHANGELOG.md` are the record on GitHub. A release there would be a second call to `api.github.com`, and a copy of the changelog.
- **Builds with the backend uv bundles**: the uv version `pyproject.toml` requires lies within the range of `uv_build` it names, so `uv build` downloads no backend; a test checks it.
- **Settings outside the repository**, which the [releasing guide](../../guides/releasing.md) lists: the trusted publisher on PyPI (`Interlusion/haflinger`, `release.yml`, environment `pypi`), the environment `pypi` with the maintainer as required reviewer, and a ruleset for tags `v*` that restricts creating, updating and deleting them, with only the maintainer past it.

Which part of the version a change raises:

| Version | For a caller | For example |
| :- | :- | :- |
| Patch, 0.1.0 → 0.1.1 | A defect fixed, the interface unchanged | A bug in reading, validating or writing fixed; an official release that fixes rules of the same versions of the standards and profiles, such as CEN's rules 1.3.16 → 1.3.17; a security fix, also one that an official release brings |
| Minor, 0.1.1 → 0.2.0 | Something added | A public name, a parameter or a profile added; a new version of a standard or profile, such as XRechnung 3.1, with its BT-24 among the `TARGET_PROFILES` |
| Major, 1.x → 2.0.0 (at 0.x: minor) | A caller's working code or invoices may break | A public name removed or renamed; an entry point's call or result changed incompatibly; a promise of the specs changed, such as a default limit lowered; a profile dropped; a higher lower bound for Python, or for a dependency beyond what Frappe benches pin |

## Alternatives Considered

### Alternative 1: The version from the Git tag

A plugin such as `hatch-vcs` or `setuptools-scm` derives the version from the latest tag, so no commit sets it.

Its advantage: one step fewer per release, and no tag that can disagree with the file.

**Rejected because** `uv_build` doesn't support it, so the build backend would change ([ADR-002](ADR-002-toolchain.md)); a checkout without its tags, or an archive of it, gets a wrong version; and a version in `pyproject.toml` is reviewed in the release's pull request like any other change. The workflow refuses a tag that disagrees.

### Alternative 2: Uploading with an API token

The maintainer uploads with `uv publish` and a token, from their machine or from a secret of the repository.

Its advantage: no settings on PyPI or GitHub beyond the token.

**Rejected because** the token is a long-lived secret that can leak, from a machine or a workflow, and an upload with it carries no attestation tying the files to a commit.

### Alternative 3: Calendar versions

Versions by date, such as `2026.11.0`, as KoSIT names its releases.

Its advantage: a version says how current the official files are.

**Rejected because** a date doesn't tell a caller whether an update breaks their code; the changelog names the official releases each version brings.

### Alternative 4: A changelog generated from the commits

A tool writes `CHANGELOG.md` from the Conventional Commits since the last tag.

Its advantage: no entry to write by hand.

**Rejected because** the commits are written for the maintainers: tests, docs and CI changes, with requirement IDs. A caller needs what changed for them, which a commit message doesn't say; and the tool would be another dependency.

### Alternative 5: The checks workflow called again by the release

`release.yml` calls `checks.yml` (`workflow_call`) before building.

Its advantage: every check runs once more on the released commit.

**Rejected because** the commit is on `main`, whose checks ran when it was merged, and `checks.yml`'s coverage comment asks for `pull-requests: write`, which the release workflow would have to grant. What the checks don't cover is the built package, and the release tests that.

### Alternative 6: A trial upload to TestPyPI

Each release goes to TestPyPI first, then to PyPI.

Its advantage: the upload itself is tried before it counts.

**Rejected because** it is a second trusted publisher, environment and project to keep, for the one step the `build` job can't check; a failed upload changes nothing, and a broken one is yanked.

## Consequences

### Positive

- A version says whether an update may break a caller's code, and the changelog says what changed in their words.
- No secret for publishing exists; PyPI shows for each file which commit and workflow built it.
- What PyPI receives is the tagged commit, built and tested in CI, after the maintainer's approval.
- A release's page on PyPI links the files of that release.
- A caller who pins a minor version (`~=0.1.0`) still gets fixes of the official rules and security fixes, and nothing that breaks them.

### Negative

- Each change a caller notices needs its changelog entry, by hand.
- A release takes a pull request before the tag.
- The `publish` job runs for the first time with the first release; until then only its configuration is checked (actionlint, zizmor).
- The settings on PyPI and GitHub live outside the repository, where no check sees them.

## Reconsideration Triggers

1. The ERPNext app runs on Haflinger in production, and the interface has held for a few minor versions: 1.0.0, after which a breaking change needs a major version and a deprecation before it.
2. A caller needs pre-releases (`0.2.0rc1`): `prepare_release.py` and this ADR admit `X.Y.Z` only.
3. Callers ask to be notified of releases on GitHub: a GitHub Release from the workflow, with the token's write right in a job of its own.
4. PyPI or GitHub change Trusted Publishing or attestations.
5. A second maintainer: who approves a release.

## Compliance

- A release SHALL be published only by `release.yml`, from a tag `vX.Y.Z` on a commit of `main` that names `pyproject.toml`'s version.
- `CHANGELOG.md` SHALL have a section for each released version, and "Unreleased" SHALL list every change a caller notices since the last release; in a release's commit, it SHALL be empty.
- A version SHALL raise the part the table above gives for the largest change it brings.
- No PyPI token SHALL be stored, in the repository or its secrets.
- A version on PyPI SHALL NOT be replaced, and its tag SHALL NOT be moved or deleted.

## References

- Affects: the [releasing guide](../../guides/releasing.md), the [development guide](../../guides/development.md#ci), `CHANGELOG.md`, the [security policy](../../../SECURITY.md) (supported versions), arc42 [§7](../README.md#7-deployment-view)
- [ADR-002](ADR-002-toolchain.md), [ADR-008](ADR-008-vendoring-official-files.md), [ADR-012](ADR-012-public-api.md)
- [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html), [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- [PyPI: Trusted Publishers](https://docs.pypi.org/trusted-publishers/), [PEP 740](https://peps.python.org/pep-0740/), [pypa/gh-action-pypi-publish](https://github.com/pypa/gh-action-pypi-publish)
