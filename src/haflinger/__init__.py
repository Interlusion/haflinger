"""Haflinger: e-invoicing on one EN 16931 model.

An invoice is read into the model, validated with the official rules and written as CII:

- `read_invoice(data)` reads a CII or UBL invoice, or with the extra `pdf` a ZUGFeRD PDF, into a
  `ReadResult`: the `Invoice` and the findings of reading it, which are no verdict (REQ-003);
- `validate(data)` checks a CII or UBL invoice against its XML Schema and the official rules of
  its profile and returns their findings; `is_valid(findings)` says whether none of them is
  `fatal` or `error`. A `HAFL-PROFILE` warning says that the profile's own rules weren't run,
  only CEN's EN 16931 rules (REQ-002);
- `write_cii(invoice)` writes an `Invoice` whose BT-24 is one of `TARGET_PROFILES` as CII, when
  it passes the XML Schema and the official rules; otherwise it raises `InvoiceWriteError`, a
  refusal whatever findings it holds (REQ-004).

`haflinger.pdf`, with the extra `pdf`, takes the invoice out of a ZUGFeRD PDF with
`extract_xml(pdf)` and puts CII of the first target profile, EN 16931, into one with
`embed(pdf, xml)`. `InvoiceReadError` refuses input that can't be read, and from `validate` also
says that the rules gave no verdict, as when they took longer than their time limit. The names
in `__all__` here and in `haflinger.pdf` are the API; every other module is internal (ADR-012).
"""

from haflinger._errors import InvoiceReadError, InvoiceWriteError
from haflinger._findings import Finding, Flag, is_valid
from haflinger._model import (
    AllowanceCharge,
    Attachment,
    Contact,
    CreditTransfer,
    Delivery,
    DirectDebit,
    Identifier,
    Invoice,
    InvoiceLine,
    ItemAttribute,
    ItemClassification,
    Note,
    Party,
    Payee,
    PaymentCard,
    PaymentInstructions,
    Period,
    PrecedingInvoice,
    SupportingDocument,
    Syntax,
    TaxRepresentative,
    Totals,
    VatBreakdown,
)
from haflinger._read import ReadResult, read_invoice
from haflinger._validation import validate
from haflinger._write import TARGET_PROFILES, write_cii

__all__ = [
    "TARGET_PROFILES",
    "AllowanceCharge",
    "Attachment",
    "Contact",
    "CreditTransfer",
    "Delivery",
    "DirectDebit",
    "Finding",
    "Flag",
    "Identifier",
    "Invoice",
    "InvoiceLine",
    "InvoiceReadError",
    "InvoiceWriteError",
    "ItemAttribute",
    "ItemClassification",
    "Note",
    "Party",
    "Payee",
    "PaymentCard",
    "PaymentInstructions",
    "Period",
    "PrecedingInvoice",
    "ReadResult",
    "SupportingDocument",
    "Syntax",
    "TaxRepresentative",
    "Totals",
    "VatBreakdown",
    "is_valid",
    "read_invoice",
    "validate",
    "write_cii",
]
