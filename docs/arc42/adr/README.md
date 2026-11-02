# Architecture Decision Records

Decisions about Haflinger. The architecture they shape is in the [arc42 overview](../README.md).

| ADR | Title | Status | Date |
| :- | :- | :- | :- |
| [ADR-001](ADR-001-library-and-app.md) | A standalone library on one EN 16931 model, and a slim ERPNext app in its own repository | Proposed | 2026-10-30 |
| [ADR-002](ADR-002-toolchain.md) | Toolchain and dependencies of a library that lives in its host's environment | Proposed | 2026-11-01 |
| [ADR-003](ADR-003-integrate-dont-implement.md) | Integrate, don't implement; receive everything, send one format | Proposed | 2026-11-01 |
| [ADR-004](ADR-004-specs-by-direction.md) | Requirement specs by direction, with one core spec | Proposed | 2026-10-30 |
| [ADR-005](ADR-005-own-mapping-kosit-as-check.md) | Our own mapping reads; KoSIT's reading stylesheet checks it | Proposed | 2026-11-01 |
| [ADR-006](ADR-006-validation-with-official-rules.md) | Validation with the official rules, run unchanged with Saxon | Proposed | 2026-11-01 |
| [ADR-007](ADR-007-model-scope-and-editions.md) | A model that grows towards all of EN 16931, edition-aware from the start | Proposed | 2026-11-01 |
| [ADR-008](ADR-008-vendoring-official-files.md) | Official artefacts and test files vendored, pinned and byte for byte | Proposed | 2026-11-01 |
| [ADR-009](ADR-009-licences-and-name.md) | Apache-2.0, the licences of what is vendored, and a name without ERPNext or Frappe | Proposed | 2026-11-01 |
| [ADR-010](ADR-010-saxon-in-a-worker-process.md) | Saxon runs in a worker process, never in the caller's | Proposed | 2026-11-02 |

New ADRs take the highest number + 1 and start as Proposed. An ADR is Accepted when the maintainer accepts it. While it is Proposed, it is edited in place; once Accepted, a change is a new ADR that supersedes it. Agent-drafted ADRs say so under Author.
