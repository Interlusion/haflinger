# Releasing

| Meta | Value |
| :- | :- |
| **Date** | 2026-11-12 |
| **Author** | loxy (drafted with Claude) |
| **Status** | Current |

How a version of Haflinger gets to PyPI and onto GitHub's Releases page. Why it works this way: [ADR-013](../arc42/adr/ADR-013-releases.md).

In short: a pull request sets the version and the changelog's section; once it is merged, a dry run of `release.yml` checks, builds and tests the merged commit, and the maintainer tags that commit; `release.yml` does the same for the tag and, once the maintainer approves, uploads the package to PyPI through Trusted Publishing, without a token, and creates the GitHub Release.

## Once: the settings outside the repository

These live on PyPI and GitHub, where no check sees them; set them before the first release and look at them before each.

1. **The trusted publisher on PyPI**: in the project `haflinger`, Manage → Publishing → Add a new publisher → GitHub, with:

   | Field | Value |
   | :- | :- |
   | Owner | `Interlusion` |
   | Repository name | `haflinger` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

2. **The environment `pypi` on GitHub**: Settings → Environments → New environment `pypi`:

   - Required reviewers: the maintainer. Leave "Prevent self-review" off: the maintainer pushes the tag and approves.
   - Deployment branches and tags: selected branches and tags, one rule for tags matching `v*`.
   - No secrets: Trusted Publishing needs none.

3. **A ruleset for the tags**: Settings → Rules → Rulesets → New tag ruleset, enforced, targeting tags `v*`, with "Restrict creations", "Restrict updates" and "Restrict deletions"; in the bypass list only the maintainer's role, so that nobody else can push a release tag. The maintainer doesn't move or delete a tag of a published version either.

## Choosing the version

A version raises the part that the largest change since the last release calls for, by what changes for a caller ([ADR-013](../arc42/adr/ADR-013-releases.md)). The interface is what `haflinger` and `haflinger.pdf` export and what the specs describe ([ADR-012](../arc42/adr/ADR-012-public-api.md)).

| Version | For a caller | For example |
| :- | :- | :- |
| Patch, 0.1.0 → 0.1.1 | A defect fixed, the interface unchanged | A bug fixed; an official release that fixes rules of the same versions of the standards and profiles; a security fix, also one that an official release brings |
| Minor, 0.1.1 → 0.2.0 | Something added | A public name, a parameter or a profile added; a new version of a standard or profile, such as XRechnung 3.1 |
| Major, 1.x → 2.0.0 | A caller's working code or invoices may break | A public name removed or renamed; an entry point's call or result changed incompatibly; a promise of the specs changed; a profile dropped; a higher lower bound for Python or a dependency |

- **While Haflinger is at 0.x**, a breaking change is a minor version, not a major one.
- **The changelog names every official release** a version brings, a patch's too, so that a caller sees why verdicts changed.
- **From 1.0.0**, a name or a profile that a major version removes is listed under Deprecated at least one minor version before, with a `DeprecationWarning` where the code can give one. 1.0.0 comes once the ERPNext app runs on Haflinger in production and the interface has held for a few minor versions. From the merge of its release pull request on, ADRs and specs are no longer edited in place: an ADR changes through a new one, a spec with an entry in its history ([ADR index](../arc42/adr/README.md), [specs index](../specs/README.md#changes)).
- **A security fix** is a patch of the latest minor version, as the [security policy](../../SECURITY.md#supported-versions) promises.

## Releasing a version

1. **Check `main`.** All the checks of its latest commit passed, `platforms` on Linux on ARM and macOS included, required or not, and "Unreleased" in `CHANGELOG.md` lists every change a caller notices since the last release.

2. **The release's pull request**, on a branch `chore/release-X.Y.Z`:

   ```sh
   uv version X.Y.Z                    # pyproject.toml and uv.lock
   ```

   In `CHANGELOG.md`, move all the entries from "Unreleased" into a new section right below it, `## [X.Y.Z] - YYYY-MM-DD` with today's date, leave "Unreleased" empty, and update the links at the end: `[unreleased]` compares `vX.Y.Z...HEAD`, `[X.Y.Z]` compares the version before with `vX.Y.Z` (the first release links its tag). Then check what the workflow will check:

   ```sh
   uv run python scripts/prepare_release.py vX.Y.Z --check
   ```

   Commit as `chore: release X.Y.Z` and open the pull request.

   Merge the pull request once its checks pass. If you like, run the dry run below on its branch first; it's the merged commit that counts.

3. **The dry run**, on `main` right after the merge: in Actions, `Release` → Run workflow, the branch `main` and the version `X.Y.Z`. It runs the `build` job as the tag will, the checks of the tag aside, and publishes nothing. Its summary names the commit it built, `vX.Y.Z of <commit>`, and shows the GitHub Release's notes; its artefact `dist` holds the files. That commit should be the release pull request's merge commit: if another pull request was merged after it, its changes would ship in this release without their changelog entry, so they come into a new release pull request first.

4. **The tag**, annotated (`-a`), on the commit the dry run built:

   ```sh
   git switch main && git pull --ff-only
   git tag -a vX.Y.Z <the dry run's commit> -m "Haflinger X.Y.Z"
   git push origin vX.Y.Z
   ```

5. **The workflow.** In Actions, `Release` runs for the tag. Its `build` job refuses a tag that isn't annotated, names another commit than the run's, isn't on `main` or wasn't pushed to `Interlusion/haflinger`, that doesn't name `pyproject.toml`'s version, or a changelog without that version's section right below an empty "Unreleased"; it points the links to `main` in the README and in the project URLs at the tag, builds the sdist and the wheel and runs the tests against the wheel. Then `publish` waits for approval: review the deployment, approve it, and the files go to PyPI with their attestations. The built files are kept 30 days, as long as an approval can wait. Last, `github-release` creates the GitHub Release for the tag, with the changelog's section as its notes and the files attached.

6. **Check PyPI and GitHub.** GitHub's Releases page shows `vX.Y.Z` with its notes and both files. On [pypi.org/project/haflinger](https://pypi.org/project/haflinger/): the version, the README and the sidebar's links with the tag in them, and under "Download files" each file's provenance, naming `Interlusion/haflinger`, `release.yml` and the tag's commit.

## When a release goes wrong

- **Before the upload**, when `build` fails or the deployment is rejected, nothing has reached PyPI. Delete the tag (`git push origin :refs/tags/vX.Y.Z` and `git tag -d vX.Y.Z`), fix `main` with a pull request, and tag the fixed commit with the same version.
- **The GitHub Release failed**, after the upload: run `github-release` again, alone (Re-run failed jobs); it brings a release that was created halfway up to date.
- **A partial upload**, the sdist on PyPI and the wheel not, is finished by running `publish` again: it skips the files PyPI already has.
- **After the upload**, the version stays: PyPI refuses a file name once used, even after a deletion. Yank the release on PyPI (Manage → Releases → Options → Yank) with the reason, so that installs no longer choose it unless they pin it, mark its section in the changelog `## [X.Y.Z] - YYYY-MM-DD [YANKED]` and its GitHub Release (Edit: "Yanked:" and the reason at the top of its notes, and "Set as the latest release" off), and release the fix as the next patch, with the reason in its changelog entry.
- **A security fix** goes out as a patch, with an entry under Security and a GitHub security advisory ([security policy](../../SECURITY.md)).

## References

- [ADR-013](../arc42/adr/ADR-013-releases.md), [ADR-012](../arc42/adr/ADR-012-public-api.md)
- [Development guide, CI](development.md#ci)
- [PyPI: Trusted Publishers](https://docs.pypi.org/trusted-publishers/), [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
