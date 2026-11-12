# Haflinger

E-invoicing in Python: ZUGFeRD, XRechnung and Peppol, on one model of the EN 16931 business terms. Built for ERPNext first. *Das Zugpferd für ZUGFeRD und XRechnung.*

**Status:** built from its specs: reading CII, UBL and ZUGFeRD PDFs, validating with the official rules, writing CII and ZUGFeRD PDFs (EN 16931); the model holds the document's terms (references, parties, delivery, payment, allowances and charges, totals, VAT breakdown, supporting documents with their attachments) and a line's references, period, allowances and charges, price and item with its attributes: 82 of the 86 invoices of KoSIT's test suite, read and written again as XRechnung 3.0 with at most one preceding invoice, pass the official rules. Released on PyPI, an alpha: while Haflinger is at 0.x, a minor version may change the API ([changelog](https://github.com/Interlusion/haflinger/blob/main/CHANGELOG.md)), and the known limits below say what it doesn't do yet.

## What it is

- **A Python library.** One model of the EN 16931 business terms. It reads invoices in CII, UBL and from ZUGFeRD PDFs, validates them with the official rules, and writes CII and ZUGFeRD PDFs. Any Python software can use it; it needs no ERP system to run or to be tested.
- **Built on the official artefacts**: KoSIT's and CEN's rules run unchanged, and the official test files are the reference ([ADR-003](https://github.com/Interlusion/haflinger/blob/main/docs/arc42/adr/ADR-003-integrate-dont-implement.md)).
- **ERPNext first.** A slim ERPNext app, later and in its own repository, maps ERPNext's sales and purchase invoices to and from the model ([ADR-001](https://github.com/Interlusion/haflinger/blob/main/docs/arc42/adr/ADR-001-library-and-app.md)).

## What it is not

- Not a Peppol access point: Peppol goes through a certified provider.
- Not affiliated with or endorsed by Frappe Technologies. ERPNext and Frappe are their trademarks.

## Installation

From PyPI, with the extra `pdf` for ZUGFeRD PDFs; Python 3.14 (later versions should work, but aren't tested), tested on Linux on x86 and ARM and on macOS on Apple Silicon:

```sh
uv add "haflinger[pdf]"    # or: pip install "haflinger[pdf]"
```

## Example

Reading, validating and writing an invoice:

```python
from dataclasses import replace
from pathlib import Path

from haflinger import TARGET_PROFILES, is_valid, read_invoice, validate, write_cii

data = Path("invoice.xml").read_bytes()  # CII or UBL
result = read_invoice(data)  # the model, and what reading couldn't take in
findings = validate(data)  # the XML Schema's and the official rules' verdict, within 60 s
invoice = result.invoice
print(invoice.number, invoice.totals and invoice.totals.amount_due, is_valid(findings))

# CII, handed out only when it passes the XML Schema and the official rules
# of its target profile: plain EN 16931 or XRechnung 3.0
xml = write_cii(replace(invoice, specification_id=TARGET_PROFILES[0]))
```

`is_valid` judges the rules that ran: where BT-24 names no supported profile, or none, `validate` runs CEN's EN 16931 rules alone and adds a `HAFL-PROFILE` warning. Reading's findings are no verdict, and an `InvoiceWriteError` is a refusal whatever findings it holds.

The names `haflinger` and `haflinger.pdf` export are the API; every other module is internal ([ADR-012](https://github.com/Interlusion/haflinger/blob/main/docs/arc42/adr/ADR-012-public-api.md)).

The official rules run in a worker process that Haflinger starts, within a time limit: `timeout=` on `validate`, `write_cii` and `embed`, by default the environment variable `HAFLINGER_RULES_TIMEOUT` or 60 seconds.

A ZUGFeRD PDF, with the extra `pdf`: `read_invoice` reads it directly; validate the invoice embedded in it.

```python
from haflinger.pdf import embed, extract_xml

pdf = Path("invoice.pdf").read_bytes()
findings = validate(extract_xml(pdf))
zugferd = embed(Path("rendered-pdfa.pdf").read_bytes(), xml)  # PDF/A in, PDF/A-3 out; EN 16931 only
```

## Known limits

What Haflinger doesn't do yet ([backlog](https://github.com/Interlusion/haflinger/blob/main/docs/backlog/backlog.md)):

- **Writing** targets EN 16931 and XRechnung 3.0, as CII: not XRechnung's extension or CVD, the other Factur-X profiles, or UBL. `write_cii` refuses a model whose BT-24 names another profile before it writes, as it does 4 of KoSIT's 86 test invoices.
- **One preceding invoice**: CII D16B holds one (BG-3), so `write_cii` refuses a model with more, as UBL invoices can carry, before it writes.
- **ZUGFeRD PDFs**: `embed` writes the profile EN 16931 only, from a PDF that already is PDF/A; veraPDF checks its output where it is installed, not yet in CI.
- **Peppol**: the Peppol BIS rules don't run; a Peppol invoice gets CEN's EN 16931 rules and a `HAFL-PROFILE` warning.
- **The 2017 edition only**: the model holds the terms of EN 16931-1:2017, and reading, validation and writing refuse an invoice of another edition, such as 2026, naming it; extensions, such as XRechnung's, stay in the original invoice.
- **Nesting**: Saxon, which runs the official rules, refuses a document nested deeper than 100 elements, which reading accepts.
- **Platforms**: tested with Python 3.14 on Linux on x86 and ARM and on macOS on Apple Silicon, not on Intel Macs; the official rules run in a worker process that needs a POSIX system, so not Windows, and `saxonche` has no wheel for musl (Alpine).
- **Large outside input**: reading a hostile file near the default `max_size` takes a lot of memory; pass a smaller `max_size` for invoices from outside.

## Development

Python 3.14 and [uv](https://docs.astral.sh/uv/); details in the [development guide](https://github.com/Interlusion/haflinger/blob/main/docs/guides/development.md).

```sh
uv sync --all-extras
uv run pytest
```

Documentation: [docs/README.md](https://github.com/Interlusion/haflinger/blob/main/docs/README.md).

## Scope

Haflinger is maintained for our own use, first for ERPNext. Contributions are welcome ([contributing](https://github.com/Interlusion/haflinger/blob/main/CONTRIBUTING.md)); support isn't promised. Report vulnerabilities privately, as the [security policy](https://github.com/Interlusion/haflinger/blob/main/SECURITY.md) describes.

## Licence

Haflinger's code is Apache-2.0. The package also ships official files under their own terms, unchanged: CEN's EN 16931 rules under EUPL-1.2, SchXslt under MIT, the XML Schemas of UN/CEFACT, OASIS and W3C under the notices in their headers, and two schemas of ETSI's that carry none. [THIRD-PARTY-NOTICES](https://github.com/Interlusion/haflinger/blob/main/THIRD-PARTY-NOTICES) lists them with their terms ([ADR-009](https://github.com/Interlusion/haflinger/blob/main/docs/arc42/adr/ADR-009-licences-and-name.md)).

Validation runs the official rules with The Saxon XSLT and XQuery Processor from Saxonica Limited (https://www.saxonica.com/): SaxonC-HE, installed as the `saxonche` package under MPL-2.0. Haflinger requires it and ships none of its files.
