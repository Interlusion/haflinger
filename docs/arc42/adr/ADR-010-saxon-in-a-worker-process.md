# ADR-010: Saxon runs in a worker process, never in the caller's

| Meta | Value |
| :- | :- |
| **Status** | Proposed |
| **Date** | 2026-11-02 |
| **Author** | loxy (drafted with Claude) |

## Context

Haflinger runs the official rules with `saxonche` ([ADR-006](ADR-006-validation-with-official-rules.md)), today inside the process that calls `validate`, `write_cii` or `embed`. Three problems share that cause:

- **Licence.** Most of Saxon's files are marked "incompatible with secondary licenses" under MPL-2.0; Saxonica's SaxonC page says the code "cannot be combined with code issued under a GPL license". The ERPNext app is GPL-3.0 ([ADR-009](ADR-009-licences-and-name.md)). Asked on 2026-11-02, Saxonica declined to say whether a GPL-3.0 app that loads `saxonche` in its process through Haflinger is allowed ("We are not lawyers"), and offered no extra permission, only a paid licence for Saxon-PE or Saxon-EE, which suits a closed product, not a GPL-3.0 app given away ([ITEM-008](../../backlog/item-008-saxonche-licence.md)). The Free Software Foundation counts code loaded into one process and called with shared data as one program, and separate processes that exchange data over pipes as separate programs, depending on what they exchange.
- **Time.** On hostile input the official rules take minutes (87 s for a 2 MB UBL invoice with 64,000 `cbc:PaymentID`), Saxon holds Python's global interpreter lock meanwhile, and a running stylesheet can't be stopped from within the process; ADR-006 leaves the time limit to the caller ([ITEM-007](../../backlog/item-007-validation-time-limit.md)).
- **Crashes.** Saxon is native code built with GraalVM. `factur-x` dropped `saxonche` 13.0.0 in 2026 after it aborted the Odoo process with "Failed to enter the specified IsolateThread context"; a crash in Saxon ends the host's process with it. Saxon also prints stack traces to the process's stderr, which Python's logging can't capture.

Measured on 2026-11-02 (Linux aarch64, Python 3.14, `saxonche` 13.1.1): starting a Python process and importing Haflinger takes 0.05 s and 25 MB; starting Saxon in it 0.02 s; compiling a rule set 0.25 s (CII) to 0.4 s (UBL), up to 1.05 s for FeRD's EXTENDED rules; validating an invoice with compiled rules 3 ms. With Saxon and one rule set compiled, the process holds 160 to 190 MB.

Haflinger already passes Saxon nothing but text: `_saxon.transform` takes the decoded invoice and the names of vendored stylesheets, and returns each stylesheet's output, SVRL, as text that Haflinger parses with `defusedxml` ([ADR-006](ADR-006-validation-with-official-rules.md)).

## Decision

- **Saxon runs only in a worker process that Haflinger starts**; the calling process never imports `saxonche`. The boundary is `_saxon.transform`: the worker receives the invoice as text and the paths of stylesheets below `artefacts/`, and returns SVRL as text, or an error message. Everything else, reading, the XML Schema check with `lxml`, the choice of rule set, the parsing of SVRL into findings, stays in the caller's process.
- **The worker is a fresh Python interpreter**, `sys.executable -I -m haflinger._worker`, started with `subprocess`, not with `multiprocessing`: `spawn` would import the caller's `__main__` into the worker, which in a Frappe bench is the host itself, and `fork` would copy it. The worker imports Haflinger and `saxonche` and nothing of the caller's. `-I` keeps the working directory and `PYTHON*` variables out of its import path.
- **Plain data crosses the boundary**: length-prefixed UTF-8 frames over the worker's stdin and stdout, never `pickle`, so that a worker that fails or is fed a hostile invoice can't run code in the caller.
- **One worker per calling process, started on first use and kept**: it compiles each rule set once and reuses it, as the process does today. Calls from several threads take turns, as they do today, but wait on a pipe, so the caller's other threads keep running.
- **A time limit on every call.** When it passes, Haflinger kills the worker and raises `InvoiceReadError` from `validate`, `InvoiceWriteError` from `write_cii` and `embed`, saying that the rules took too long. The next call starts a new worker, which compiles its rule set again. The default and how to change it belong to REQ-002; the largest real invoice at hand, 25.7 MB from the Peppol corpus, validates in about 8 s.
- **A worker that dies**, by a crash, a kill or a missing `saxonche`, is reported the same way, with its stderr in the message, and replaced on the next call. Otherwise the worker's stderr goes to Python's logging.
- **A forked caller gets its own worker**: Haflinger remembers the process ID that started the worker, and a child process forked after that starts a new one instead of sharing the parent's pipes.
- `saxonche` stays a dependency of Haflinger: the worker needs it in the same environment.

## Alternatives Considered

### Alternative 1: Saxon in the caller's process, as today

No second process, no IPC.

**Rejected because** it leaves all three problems: the GPL-3.0 app would load Saxon into its own process on a reading of the GPL nobody would confirm, validation can't be stopped, and a crash takes ERPNext's worker down with it.

### Alternative 2: A worker process only on request

The caller picks in-process or worker.

**Rejected because** the licence boundary holds only if the app's process never loads Saxon, and a default that loads it is one forgotten setting away; two paths would also need testing twice.

### Alternative 3: A `multiprocessing` pool

Ready-made pools, timeouts and restarts.

**Rejected because** its start methods bring the caller into the worker: `spawn` and `forkserver` import the caller's `__main__`, `fork` copies the whole process, and results come back pickled.

### Alternative 4: A new process per call

Nothing kept between calls; a fresh worker every time.

**Rejected because** every invoice would pay start-up and the compiling of its rule set, 0.3 to 1.1 s, where a kept worker takes 3 ms.

### Alternative 5: A validation service over HTTP

As `factur-x` does since release 6.0, with a separate Saxon server.

**Rejected because** every user of the library would have to deploy and run a service. A host that wants one can still run Haflinger's worker behind its own service; the library's boundary doesn't change.

## Consequences

### Positive

- The process that calls Haflinger never contains Saxon: the GPL-3.0 app and Saxon exchange text over a pipe instead of sharing a process.
- Validation has a time limit, and hostile input no longer holds the caller for minutes ([ITEM-007](../../backlog/item-007-validation-time-limit.md)).
- A crash in Saxon ends the worker, not the caller; Saxon's stderr reaches logging.
- The caller's other threads run while the rules do.

### Negative

- A second process per calling process, holding 160 to 190 MB per compiled rule set where Saxon in the caller's process holds the same; a caller that never validates starts none.
- A worker killed after a time limit costs the next call a compile of 0.25 to 1.05 s.
- IPC, a worker's lifecycle and a fork check are new code that can fail; errors cross a process boundary.
- Whether a process boundary suffices legally is a reading too, if a stronger one; a lawyer should confirm it before the app is published ([ITEM-008](../../backlog/item-008-saxonche-licence.md)).

## Reconsideration Triggers

1. Saxonica or a lawyer confirms that Saxon in the caller's process is fine beside GPL-3.0 code, and the time limit and crash isolation are no longer wanted.
2. An engine without Saxon's licence runs the official rules in the caller's process ([ADR-006](ADR-006-validation-with-official-rules.md), trigger 2).
3. The worker's memory or start-up proves too costly in a bench, for example with many gunicorn workers that each validate.

## Compliance

- The calling process SHALL NOT import `saxonche`; a test SHALL check `sys.modules` after `validate`, `write_cii` and `embed`.
- Only text SHALL cross the boundary; no `pickle`.
- Every call into the worker SHALL have a time limit, and a worker that passes it SHALL be killed.

## References

- Affects: arc42 [§5](../README.md#5-building-block-view), [§6](../README.md#6-runtime-view), [§7](../README.md#7-deployment-view), [§8](../README.md#8-cross-cutting-concepts), [§11](../README.md#11-risks-and-technical-debt); REQ-002's time limit and assumptions
- [ADR-006](ADR-006-validation-with-official-rules.md), [ADR-009](ADR-009-licences-and-name.md), [ITEM-007](../../backlog/item-007-validation-time-limit.md), [ITEM-008](../../backlog/item-008-saxonche-licence.md)
- [GNU GPL FAQ: separate programs or one program](https://www.gnu.org/licenses/gpl-faq.html#MereAggregation)
