# Architecture Decision Records

Decisions about Haflinger. The architecture they shape is in the [arc42 overview](../README.md).

| ADR | Title | Status | Last changed |
| :- | :- | :- | :- |
| [ADR-001](ADR-001-library-and-app.md) | A standalone library on one EN 16931 model, and a slim ERPNext app in its own repository | Accepted | 2026-10-30 |
| [ADR-002](ADR-002-toolchain.md) | Toolchain and dependencies of a library that lives in its host's environment | Accepted | 2026-11-12 |
| [ADR-003](ADR-003-integrate-dont-implement.md) | Integrate, don't implement; receive everything, send one format | Accepted | 2026-11-01 |
| [ADR-004](ADR-004-specs-by-direction.md) | Requirement specs by direction, with one core spec | Accepted | 2026-10-30 |
| [ADR-005](ADR-005-own-mapping-kosit-as-check.md) | Our own mapping reads; KoSIT's reading stylesheet checks it | Accepted | 2026-11-01 |
| [ADR-006](ADR-006-validation-with-official-rules.md) | Validation with the official rules, run unchanged with Saxon | Accepted | 2026-11-12 |
| [ADR-007](ADR-007-model-scope-and-editions.md) | A model that grows towards all of EN 16931, edition-aware from the start | Accepted | 2026-11-01 |
| [ADR-008](ADR-008-vendoring-official-files.md) | Official artefacts and test files vendored, pinned and byte for byte | Accepted | 2026-11-01 |
| [ADR-009](ADR-009-licences-and-name.md) | Apache-2.0, the licences of what is vendored, and a name without ERPNext or Frappe | Accepted | 2026-11-12 |
| [ADR-010](ADR-010-saxon-in-a-worker-process.md) | Saxon runs in a worker process, never in the caller's | Accepted | 2026-11-02 |
| [ADR-011](ADR-011-attached-documents.md) | Attached documents in the model, as bytes, within the input's size limit | Accepted | 2026-11-08 |
| [ADR-012](ADR-012-public-api.md) | Two public modules, the rest private, the API what their `__all__` lists | Accepted | 2026-11-11 |
| [ADR-013](ADR-013-releases.md) | Releases: SemVer, a changelog, and PyPI from a tag through Trusted Publishing | Accepted | 2026-11-11 |

New ADRs take the highest number + 1 and start as Proposed. An ADR is Accepted when the maintainer accepts it; ADR-001 to ADR-013 were accepted on 2026-11-11. Until Haflinger 1.0.0, Proposed and Accepted ADRs alike are edited in place. From the merge of the 1.0.0 release pull request on ([ADR-013](ADR-013-releases.md)), an Accepted ADR is no longer rewritten, a typo or a link aside: a change is a new ADR that supersedes it. An ADR's `Date` is the date of its last change; an edit updates it in the ADR and in its row above, which a test checks. Agent-drafted ADRs say so under Author.
