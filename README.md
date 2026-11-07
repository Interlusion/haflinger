# Haflinger

E-invoicing in Python: ZUGFeRD, XRechnung and Peppol, on one model of the EN 16931 business terms. Built for ERPNext first. *Das Zugpferd für ZUGFeRD und XRechnung.*

**Status:** built from its specs: reading CII, UBL and ZUGFeRD PDFs, validating with the official rules, writing CII and ZUGFeRD PDFs (EN 16931); the model holds the document's terms (references, parties, delivery, payment, allowances and charges, totals, VAT breakdown, supporting documents without their attachments) and a line's references, period, price and item: 82 of the 86 invoices of KoSIT's test suite, read and written again, pass the official rules; a line's allowances and charges, and the item's attributes come next. Nothing is released.

## What it is

- **A Python library.** One model of the EN 16931 business terms. It reads invoices in CII, UBL and from ZUGFeRD PDFs, validates them with the official rules, and writes CII and ZUGFeRD PDFs. Any Python software can use it; it needs no ERP system to run or to be tested.
- **Built on the official artefacts**: KoSIT's and CEN's rules run unchanged, and the official test files are the reference ([ADR-003](docs/arc42/adr/ADR-003-integrate-dont-implement.md)).
- **ERPNext first.** A slim ERPNext app, later and in its own repository, maps ERPNext's sales and purchase invoices to and from the model ([ADR-001](docs/arc42/adr/ADR-001-library-and-app.md)).

## What it is not

- Not a Peppol access point: Peppol goes through a certified provider.
- Not affiliated with or endorsed by Frappe Technologies. ERPNext and Frappe are their trademarks.

## Example

Reading, validating and writing an invoice:

```python
from dataclasses import replace
from pathlib import Path

from haflinger import read_invoice, validate, write_cii

data = Path("invoice.xml").read_bytes()  # CII or UBL
result = read_invoice(data)  # the model, and what reading couldn't take in
findings = validate(data)  # the XML Schema's and the official rules' verdict, within 60 s
invoice = result.invoice
print(invoice.number, invoice.totals and invoice.totals.amount_due, len(findings))

# CII, handed out only when it passes the XML Schema and the official rules
xml = write_cii(replace(invoice, specification_id="urn:cen.eu:en16931:2017"))
```

The official rules run in a worker process that Haflinger starts, within a time limit: `timeout=` on `validate`, `write_cii` and `embed`, by default the environment variable `HAFLINGER_RULES_TIMEOUT` or 60 seconds.

A ZUGFeRD PDF, with the extra `pdf`: `read_invoice` reads it directly; validate the invoice embedded in it.

```python
from haflinger.pdf import embed, extract_xml

pdf = Path("invoice.pdf").read_bytes()
findings = validate(extract_xml(pdf))
zugferd = embed(Path("rendered-pdfa.pdf").read_bytes(), xml)  # PDF/A in, PDF/A-3 out
```

## Development

Python 3.14 and [uv](https://docs.astral.sh/uv/); details in the [development guide](docs/guides/development.md).

```sh
uv sync --all-extras
uv run pytest
```

Documentation: [docs/README.md](docs/README.md).

## Licence

Apache-2.0. Vendored official files keep their own licences, named next to them ([ADR-009](docs/arc42/adr/ADR-009-licences-and-name.md)).

Validation runs the official rules with The Saxon XSLT and XQuery Processor from Saxonica Limited (https://www.saxonica.com/): SaxonC-HE, installed as the `saxonche` package under MPL-2.0. Haflinger requires it and ships none of its files.
