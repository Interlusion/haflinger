"""The exceptions Haflinger raises instead of a result."""


class InvoiceReadError(ValueError):
    """An input reading or validation refuses, with the reason (REQ-003-PRS-F006)."""
