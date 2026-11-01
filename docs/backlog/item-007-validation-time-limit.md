# ITEM-007: A time limit on validation, in a child process

| Meta | Value |
| :- | :- |
| **Status** | CANDIDATE |
| **Type** | feature |
| **Origin** | Second review of 2026-11-01 ([REQ-002](../specs/req-002-conformance.md)'s assumptions); third review of 2026-11-01 |
| **Created** | 2026-11-01 |
| **Author** | loxy (drafted with Claude) |

## Summary

Let `validate` (and the rule check of `write_cii` and `embed`) give up after a time limit, with an `InvoiceReadError` or `InvoiceWriteError` that says so, by running Saxon in a child process that is stopped when the limit passes. Today the library doesn't bound the time of validation; its callers must ([REQ-002](../specs/req-002-conformance.md#assumptions)).

## Context / Motivation

The official rules compute the location of every finding with `xsl:number`, which counts the preceding siblings again for each finding: the time grows with the square of the number of findings among sibling elements. CEN's `UBL-SR-44` compares every `cbc:PaymentID` with every one before it, so its time grows with the square of their number even without findings. Long numbers and XRechnung's pattern for telephone numbers grow with the square of their length too. Saxon holds Python's global interpreter lock while it runs, so every thread of the process waits, and it can't be interrupted from within the process. Measured on 2026-11-01 (KoSIT case 01.01a with additions):

| Crafted invoice | Size | `validate` |
| :- | :- | :- |
| 25,600 empty notes | 484 kB | 12.8 s; refused within milliseconds since the limit on empty elements ([REQ-002-PRS-F001](../specs/req-002-conformance.md#req-002-prs-f001-one-entry-point)) |
| 10,000 invoice lines that each fail rules, no empty element | 3.2 MB | 15.2 s (5,000 lines: 4.5 s) |
| One amount with 200,000 digits | 204 kB | 4.4 s (100,000 digits: 1.2 s); refused within milliseconds since the limit of 1,000 digits |
| A telephone number of 8,000 characters (XRechnung's `BR-DE-27` pattern) | 17 kB | 35.8 s (4,000 characters: 8.9 s); refused within milliseconds since the limit of 100 characters |
| 64,000 distinct `cbc:PaymentID` in a UBL invoice (CEN's `UBL-SR-44`), 3 findings | 2 MB | 87.0 s (16,000 in 0.5 MB: 5.1 s; 32,000 in 1 MB: 20.4 s) |
| 32,000 notes that each fail `BR-CL-08` | 2 MB | 22.5 s |

The last three rows are not refused, and no list of refusals can be complete: the invoice lines can't be told apart from a legitimate invoice by counting (the 25.7 MB Peppol invoice of the corpus has 26,813 lines and validates in about 8 s, because it has few findings), and the other two needn't look like a real invoice at all. Only a limit on time bounds every case. Until there is one, callers validate outside input where a time limit applies ([REQ-002](../specs/req-002-conformance.md#assumptions)).

## Options

- **A child process per call**: simple, but every call pays process start-up and the compiling of its rule set (about 0.1 s to 1.1 s).
- **A pool of child processes** that keep their compiled rule sets; a call that passes the limit stops its process, and the pool starts a new one. Fast after the first call; costs memory per process (Saxon and the compiled rules, a few hundred MB) and care in hosts that fork (Frappe's workers): start the children with `spawn`, not `fork`.
- **Cheap refusals of further shapes**, beside or instead of the above, as for empty elements, long numbers and long telephone numbers: each covers one shape only. Decided against on 2026-11-01, after the third review found two more shapes: no further refusals.

## Open Questions

- The default limit, and whether the time limit is a parameter of `validate` or a setting of the process.
- Does the ERPNext app need it, given that it validates in background jobs with their own timeout ([ITEM-003](item-003-erpnext-app.md))?
- How saxonche behaves in child processes started with `spawn`, and what a pool costs in memory in a Frappe bench.
