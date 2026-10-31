# Haflinger

E-invoicing in Python: ZUGFeRD, XRechnung and Peppol, on one model of the EN 16931 business terms. Built for ERPNext first. *Das Zugpferd für ZUGFeRD und XRechnung.*

**Status:** specs and architecture written; the library is being built from them, after spikes that proved the approach. Nothing is released.

## What it is

- **A Python library.** One model of the EN 16931 business terms. It reads invoices in CII, UBL and from ZUGFeRD PDFs, validates them with the official rules, and writes CII and ZUGFeRD PDFs. Any Python software can use it; it needs no ERP system to run or to be tested.
- **Built on the official artefacts**: KoSIT's and CEN's rules run unchanged, and the official test files are the reference ([ADR-003](docs/arc42/adr/ADR-003-integrate-dont-implement.md)).
- **ERPNext first.** A slim ERPNext app, later and in its own repository, maps ERPNext's sales and purchase invoices to and from the model ([ADR-001](docs/arc42/adr/ADR-001-library-and-app.md)).

## What it is not

- Not a Peppol access point: Peppol goes through a certified provider.
- Not affiliated with or endorsed by Frappe Technologies. ERPNext and Frappe are their trademarks.

## Example

The intended use, as the specs define it:

```python
from pathlib import Path

from haflinger import read_invoice, validate

data = Path("invoice.xml").read_bytes()
result = read_invoice(data)  # the model, and what reading couldn't take in
findings = validate(data)  # the official rules' verdict
invoice = result.invoice
print(invoice.number, invoice.seller.name, invoice.totals.amount_due, len(findings))
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
