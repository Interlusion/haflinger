"""The exceptions Haflinger raises instead of a result."""

from haflinger._findings import Finding


class InvoiceReadError(ValueError):
    """An input reading or validation refuses, with the reason (REQ-003-PRS-F006)."""


class InvoiceWriteError(ValueError):
    """An invoice writing refuses, with the reason (REQ-004-PRS-F001, REQ-004-PRS-F007). From
    `write_cii`: before writing without findings or document, after writing with the findings
    and the written CII. From `haflinger.pdf.embed`: where the given XML fails the XML Schema or
    the rules, or the rules can't check it, with the findings and that XML as `document`;
    otherwise, a written PDF that fails its checks included, without either."""

    def __init__(
        self, reason: str, *, findings: tuple[Finding, ...] = (), document: bytes | None = None
    ) -> None:
        super().__init__(reason)
        self.findings = findings
        self.document = document
