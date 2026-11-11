"""The exceptions Haflinger raises instead of a result."""

from haflinger._findings import Finding


class InvoiceReadError(ValueError):
    """An input reading or validation refuses, with the reason (REQ-003-PRS-F006)."""


class InvoiceWriteError(ValueError):
    """An invoice writing refuses, with the reason (REQ-004-PRS-F001): before writing without
    findings or document, after writing with the findings and the written document."""

    def __init__(
        self, reason: str, *, findings: tuple[Finding, ...] = (), document: bytes | None = None
    ) -> None:
        super().__init__(reason)
        self.findings = findings
        self.document = document
