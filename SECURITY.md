# Security policy

Haflinger reads invoices from outside the company: XML and PDFs that anyone can send. What it reads, and what it says about an invoice, ends up in accounting, so we take reports about it seriously.

## Reporting a vulnerability

Report it privately through GitHub's private vulnerability reporting: [report a vulnerability](https://github.com/interlusion/haflinger/security/advisories/new) (the repository's Security tab). Please don't open a public issue, pull request or discussion for it.

A useful report says:

- the commit of Haflinger, or its version once it is released, the Python version and the platform;
- what an invoice, or a caller's input, makes Haflinger do that it shouldn't, and how;
- the input that shows it: the name and release of an official test file, or an invoice built from scratch with placeholders such as `Example GmbH`, never a real invoice: invoices hold names, addresses, bank details and amounts.

## Scope

In scope is anything that breaks what Haflinger promises in its [specifications](docs/specs/README.md) for its public API ([ADR-012](docs/arc42/adr/ADR-012-public-api.md)): the entry points `read_invoice`, `validate`, `write_cii`, `haflinger.pdf.extract_xml` and `haflinger.pdf.embed`, and the other names `haflinger` exports, such as `is_valid`, for example:

- **Outside input** ([REQ-001-PRS-NF001](docs/specs/req-001-core.md#req-001-prs-nf001-outside-input)): XML with a document type or entity declaration that a reader, stylesheet or rule processes; anything an invoice references, in its XML or its PDF (files, URLs, actions), fetched, opened or run; reading or validation creating a file, or writing anything from an input to the file system; a value from an invoice, such as an attachment's file name, used as a path, URL or command; an attachment's content opened or rendered, or shown in a model's `repr`, a refusal or a finding beyond the shortened quotes the specs describe.
- **The limits**: an input above `max_size` parsed, or XML embedded in a PDF inflated beyond it ([REQ-001-PRS-NF003](docs/specs/req-001-core.md#req-001-prs-nf003-size-limit)); the official rules of a call running past its time limit ([REQ-002-PRS-NF004](docs/specs/req-002-conformance.md#req-002-prs-nf004-time-limit)), or a worker that has died leaving the caller waiting ([REQ-002-PRS-NF005](docs/specs/req-002-conformance.md#req-002-prs-nf005-rules-in-a-worker-process)); an exception other than Haflinger's own errors from reading or validating an invoice.
- **The verdict**: an invoice crafted so that the XML Schema check, the rules and the reader see different text of it ([REQ-002-PRS-F011](docs/specs/req-002-conformance.md#req-002-prs-f011-xml-schema-first)); `write_cii` or `embed` handing out a document that fails its XML Schema or the official rules of its target profile ([REQ-004-URS-F002](docs/specs/req-004-outgoing-invoices.md#req-004-urs-f002-only-valid-invoices-leave)); `is_valid` calling `validate`'s findings valid where one of them is `fatal` or `error` ([REQ-002-PRS-F002](docs/specs/req-002-conformance.md#req-002-prs-f002-findings)).
- **The worker process** that runs the official rules ([REQ-002-PRS-NF005](docs/specs/req-002-conformance.md#req-002-prs-nf005-rules-in-a-worker-process)): an input that makes it run anything but Haflinger's code and the vendored stylesheets, or reach the caller's process other than through the text it sends back and what it writes to stderr.

Out of scope:

- Haflinger's other modules, which are internal; what they do matters where it reaches an entry point.
- The official artefacts and the libraries Haflinger builds on: KoSIT's, CEN's and FeRD's rules and stylesheets, SchXslt, Saxon, lxml and libxml2, `defusedxml`, `pypdf`, `factur-x`. Report those to their projects; tell us too where Haflinger should guard against it.
- What a caller does with what Haflinger hands back: showing an attachment or a PDF to a person, storing files, booking an invoice. The ERPNext app is its own project.
- The known costs of large input within `max_size`, the memory reading takes and the number of findings a hostile file can produce ([backlog](docs/backlog/backlog.md)): a caller reading outside input passes a smaller `max_size`.
- A business rule the official rules don't check: Haflinger runs them unchanged and doesn't reimplement them ([ADR-003](docs/arc42/adr/ADR-003-integrate-dont-implement.md)); a rule they lack is a feature request, or goes to their projects.

## Supported versions

Haflinger isn't released yet; until then, reports concern `main`. Once it is, only the latest minor version gets security fixes, released as a patch of it as soon as it is ready, with a GitHub security advisory and an entry under Security in the [changelog](CHANGELOG.md). While Haflinger is at 0.x, a minor version may break the interface, so taking a fix can mean taking those changes too.

## What to expect

Haflinger is maintained on a best-effort basis: we answer and fix as soon as we can, without a promised time. There is no bounty. With your consent, the advisory credits you.
