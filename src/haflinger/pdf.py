"""ZUGFeRD PDFs: the invoice taken out of a PDF, and put into one (REQ-003-PRS-F007,
REQ-004-PRS-F007). Needs the extra `pdf`.

A PDF is outside input. pypdf parses it; any failure of pypdf on a malformed PDF becomes an
`InvoiceReadError`, and the embedded file is inflated here, against `max_size`, never by pypdf
(REQ-003-PRS-NF001, REQ-003-PRS-NF003). Looking for the invoice stops after `_TIME_LIMIT`.
"""

import dataclasses
import io
import sys
import tempfile
import time
import zlib
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Any, cast
from xml.etree.ElementTree import Element

try:
    import facturx
    from pypdf import Configuration, PdfReader, apply_configuration
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        IndirectObject,
        NullObject,
        NumberObject,
        StreamObject,
    )
except ImportError as error:
    raise ImportError("haflinger.pdf needs the extra 'pdf': install haflinger[pdf]") from error

from haflinger import _cii, _write
from haflinger._errors import InvoiceReadError, InvoiceWriteError
from haflinger._input import open_invoice
from haflinger._model import Invoice
from haflinger._write import EN16931
from haflinger._xml import MAX_SIZE, check_size, parse

__all__ = ["embed", "extract_xml"]

# The names of the embedded invoice (REQ-003-PRS-F007).
INVOICE_NAMES = frozenset(
    {"factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml", "ZUGFeRD-invoice.xml"}
)
# REQ-004-PRS-F007: the target profile embed writes, with its Factur-X level as `factur-x` takes
# it and as the XMP metadata names it.
_EMBED_LEVELS = {EN16931: ("en16931", "EN 16931")}
# The namespaces of XMP metadata: RDF's, PDF/A's identification and extension schemas', Factur-X's.
_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_PDFA_ID = "http://www.aiim.org/pdfa/ns/id/"
_PDFA_SCHEMA = "http://www.aiim.org/pdfa/ns/schema#"
_PDFA_PROPERTY = "http://www.aiim.org/pdfa/ns/property#"
_FACTUR_X = "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"
_PREFIXES = {_PDFA_ID: "pdfaid", _FACTUR_X: "fx"}
# The XMP properties of every PDF embed writes, by namespace and name, besides the level: PDF/A-3b,
# as `factur-x` declares it, and Factur-X's (REQ-004-PRS-F007).
_XMP_PROPERTIES = {
    (_PDFA_ID, "part"): "3",
    (_PDFA_ID, "conformance"): "B",
    (_FACTUR_X, "DocumentFileName"): "factur-x.xml",
    (_FACTUR_X, "DocumentType"): "INVOICE",
    (_FACTUR_X, "Version"): "1.0",
}
_MAX_DEPTH = 32  # of the name tree of embedded files
_MAX_ENTRIES = 100  # nodes and files of that tree read, at most (REQ-003-PRS-NF003)
# Bytes, for each stream pypdf decodes while the invoice is looked for: for every filter whose
# output pypdf's version limits (6.19.0, which Frappe v16 pins, has no BrotliDecode).
_PYPDF_LIMITS: dict[str, Any] = {
    field.name: 2_000_000
    for field in dataclasses.fields(Configuration)
    if field.name.endswith("_maximum_output_length")
}
# Seconds pypdf may spend while the invoice is looked for: no ZUGFeRD PDF needs a fraction of
# it, and no limit on sizes or counts bounds every shape that keeps pypdf busy (REQ-003-PRS-NF003).
_TIME_LIMIT = 3.0
# The names `factur-x` gives the type of document in the PDF's metadata.
_DOCUMENT_TYPES = {"380": "Invoice", "381": "Refund"}


class _OutOfTime(BaseException):
    """Raised inside pypdf when the time is up; a `BaseException`, so that pypdf's handlers of
    `Exception`, which recover from malformed input, don't take it for one."""


def extract_xml(data: bytes, *, max_size: int = MAX_SIZE) -> bytes:
    """The invoice embedded in a ZUGFeRD PDF, byte for byte and not parsed. Raises
    `InvoiceReadError` when the PDF itself exceeds `max_size` or isn't readable, holds no
    invoice or more than one under the names of `INVOICE_NAMES`, encodes it otherwise than with
    FlateDecode, without decode parameters or with a predictor of 1, or the invoice exceeds
    `max_size`; and when looking for the invoice passes the limits of REQ-003-PRS-F007: a tree
    of embedded files of more than 100 entries or nested deeper than 32 levels, a stream on the
    way that decodes to more than 2 MB, or more than 3 s."""
    if not isinstance(cast(object, data), bytes):
        raise InvoiceReadError(f"the input is not bytes but {type(data).__name__}")
    check_size(data, max_size)
    try:
        # pypdf's own decoding (object and cross-reference streams) stays small: none of what
        # leads to the invoice needs more, and the decoded data is kept while the PDF is read.
        with apply_configuration(**_PYPDF_LIMITS), _deadline(_TIME_LIMIT):
            return _extract(PdfReader(io.BytesIO(data)), max_size)
    except _OutOfTime:
        raise InvoiceReadError(
            f"the PDF takes more than {_TIME_LIMIT:g} s to look for the invoice in; a ZUGFeRD PDF"
            " takes milliseconds"
        ) from None
    except InvoiceReadError:
        raise
    except Exception as error:  # noqa: BLE001 - pypdf raises many kinds on malformed input
        raise InvoiceReadError(f"the input isn't a readable PDF: {error!r}") from None


@contextmanager
def _deadline(seconds: float) -> Generator[None]:
    """Raise `_OutOfTime` in this thread's Python code once `seconds` have passed, by a profile
    function, which Python calls on every call and return, of C functions too. It raises again a
    quarter of a second later if the first was caught, so that cleanup on the way out runs. A
    profiler the caller had set is paused meanwhile."""
    end = time.monotonic() + seconds
    raised = 0.0

    def check(frame: FrameType, event: str, arg: object) -> None:
        nonlocal raised
        now = time.monotonic()
        if now > end and now > raised + 0.25:
            raised = now
            raise _OutOfTime

    previous = sys.getprofile()
    sys.setprofile(check)
    try:
        yield
    finally:
        sys.setprofile(previous)


def embed(pdf: bytes, xml: bytes, *, timeout: float | None = None) -> bytes:
    """`pdf`, a PDF/A-1, -2 or -3 file by its XMP metadata, as a PDF/A-3 ZUGFeRD PDF with `xml`
    embedded as `factur-x.xml`, its XMP metadata and document information replaced by the
    invoice's, when `pdf` holds no name tree (`/Names`: embedded files, named destinations and
    the others) and no associated files (`/AF`), which embedding would drop, and `xml` is a CII
    invoice of the target profile embed writes and passes the XML Schema and the official rules,
    which end within `timeout` seconds, by default `HAFLINGER_RULES_TIMEOUT` or 60
    (REQ-002-PRS-NF004). Raises `InvoiceWriteError` otherwise (REQ-004-PRS-F007)."""
    for argument, value in (("PDF", cast(object, pdf)), ("XML", cast(object, xml))):
        if not isinstance(value, bytes):
            raise InvoiceWriteError(f"the {argument} is not bytes but {type(value).__name__}")
    limit = _write.rules_timeout(timeout)
    try:
        opened = open_invoice(xml, MAX_SIZE, pdf="the XML is a PDF")
    except InvoiceReadError as error:
        raise InvoiceWriteError(f"the XML can't be read: {error}") from None
    # BT-24 exactly as written, as a recipient's validator matches it (REQ-004-PRS-F007).
    specification_id = None if opened.specification is None else opened.specification.element.text
    profile = _EMBED_LEVELS.get(specification_id or "")
    if opened.document != "cii" or profile is None:
        raise InvoiceWriteError(
            f"embed writes only CII invoices with BT-24 {', '.join(_EMBED_LEVELS)};"
            f" this is {opened.document} with BT-24 {specification_id!r}"
        )
    _check_pdf(pdf)
    _write.refuse_if_invalid(_write.check_written(xml, specification_id, limit), xml)
    invoice = _cii.read(opened.reading.root, specification_id)
    level, conformance_level = profile
    result = _embed(pdf, xml, level, _metadata(invoice))
    # What `factur-x` writes, read back: the tests check the release they run with, and a caller
    # may run another (REQ-004-PRS-F007).
    try:
        reader = PdfReader(io.BytesIO(result), strict=True)
        embedded = list(reader.attachments)
        extracted = extract_xml(result)
        related = _relates_as_alternative(reader)
        xmp = _xmp(_dictionary(reader.trailer.get("/Root")))
    except Exception as error:  # noqa: BLE001 - checking factur-x's result
        raise InvoiceWriteError(f"the written PDF can't be read back: {error!r}") from None
    if not result.startswith(b"%PDF-") or embedded != ["factur-x.xml"] or extracted != xml:
        raise InvoiceWriteError("the written PDF doesn't carry the invoice as given")
    if not related:
        raise InvoiceWriteError(
            "the written PDF doesn't relate the invoice as /Alternative, in its embedded file and"
            " in the catalogue's /AF"
        )
    _check_xmp(xmp, conformance_level)
    return result


def _relates_as_alternative(reader: PdfReader) -> bool:
    """Whether the embedded invoice's file specification and one in the catalogue's associated
    files (`/AF`) relate it as `/Alternative`."""

    def alternative(spec: DictionaryObject | None) -> bool:
        return (
            spec is not None
            and spec.get("/UF", spec.get("/F")) == "factur-x.xml"
            and spec.get("/AFRelationship") == "/Alternative"
        )

    root = _dictionary(reader.trailer.get("/Root"))
    associated = None if root is None else root.get("/AF")
    if isinstance(associated, IndirectObject):
        associated = associated.get_object()
    files: list[object] = list(associated) if isinstance(associated, ArrayObject) else []
    return all(alternative(spec) for _, spec in _embedded_files(reader)) and any(
        alternative(_dictionary(spec)) for spec in files
    )


def _check_xmp(xmp: bytes, conformance_level: str) -> None:
    """Refuse XMP metadata that doesn't declare PDF/A-3b, an extension schema of Factur-X's
    namespace naming its properties, and in that namespace exactly one of each of them, the level
    `conformance_level`, all as written (REQ-004-PRS-F007)."""
    try:
        root = parse(xmp)
    except InvoiceReadError as error:
        raise InvoiceWriteError(f"the written PDF's XMP metadata isn't readable: {error}") from None
    expected = {**_XMP_PROPERTIES, (_FACTUR_X, "ConformanceLevel"): conformance_level}
    found = _xmp_properties(root)
    differences = [
        f"{_PREFIXES[namespace]}:{name} {values} instead of {value!r}"
        for (namespace, name), value in expected.items()
        if (values := found.get(f"{{{namespace}}}{name}", [])) != [value]
    ]
    names = sorted(name for namespace, name in expected if namespace == _FACTUR_X)
    if not _declares_schema(root, _FACTUR_X, names):
        differences.append(f"no PDF/A extension schema of {_FACTUR_X} naming {', '.join(names)}")
    if differences:
        raise InvoiceWriteError(
            "the written PDF's XMP metadata doesn't declare what ZUGFeRD requires: "
            + "; ".join(differences)
        )


def _declares_schema(root: Element, namespace: str, names: list[str]) -> bool:
    """Whether a PDF/A extension schema in XMP metadata declares `namespace` with properties of
    all of `names`, as PDF/A requires of the properties of a namespace it doesn't know."""
    for schema in root.iter():
        if schema.findtext(f"{{{_PDFA_SCHEMA}}}namespaceURI") == namespace:
            declared = {e.text for e in schema.iter(f"{{{_PDFA_PROPERTY}}}name")}
            if declared.issuperset(names):
                return True
    return False


def _xmp_properties(root: Element) -> dict[str, list[str]]:
    """The properties of XMP metadata by Clark name (`{namespace}name`), each with every value it
    has, as an element or an attribute of an `rdf:Description`, whatever its prefix."""
    properties: dict[str, list[str]] = {}
    for description in root.iter(f"{{{_RDF}}}Description"):
        for name, value in [*description.attrib.items(), *((e.tag, e.text) for e in description)]:
            properties.setdefault(name, []).append(value or "")
    return properties


def _metadata(invoice: Invoice) -> dict[str, str]:
    """The PDF's metadata as `factur-x` would take it from the XML, which it then doesn't parse:
    its parser stops at texts over 10 MB, such as a large attachment (BG-24)."""
    kind = _DOCUMENT_TYPES.get(invoice.type_code or "", "Invoice")
    number = invoice.number or ""
    seller = "" if invoice.seller is None else invoice.seller.name or ""
    issued = "" if invoice.issue_date is None else f" dated {invoice.issue_date.isoformat()}"
    return {
        "author": seller,
        "keywords": f"{kind}, Factur-X",
        "title": f"{seller}: {kind} {number}",
        "subject": f"{kind} {number}{issued} issued by {seller}",
    }


def _embed(pdf: bytes, xml: bytes, level: str, metadata: dict[str, str]) -> bytes:
    """`factur-x`'s embedding, into a new file: writing back into its input leaves the end of a
    longer input in place. The input is the caller's own PDF (REQ-001-PRS-NF001)."""
    try:
        with tempfile.TemporaryDirectory(prefix="haflinger-") as directory:
            source, target = Path(directory, "input.pdf"), Path(directory, "output.pdf")
            source.write_bytes(pdf)
            facturx.generate_from_file(
                str(source),
                xml,
                flavor="factur-x",
                level=level,
                check_xsd=False,
                check_schematron=False,  # never a request to a Saxon server (REQ-001-PRS-NF001)
                pdf_metadata=metadata,
                output_pdf_file=str(target),
                afrelationship="alternative",  # REQ-004-PRS-F007
            )
            return target.read_bytes()
    except Exception as error:  # noqa: BLE001 - factur-x and pypdf raise many kinds
        raise InvoiceWriteError(f"the PDF can't be written: {error!r}") from None


def _check_pdf(pdf: bytes) -> None:
    """A PDF/A-1, -2 or -3 file holding nothing that embedding would drop: `factur-x` writes a
    `/Names` of its own, holding only the invoice, and an `/AF` of its own."""
    try:
        root = _dictionary(PdfReader(io.BytesIO(pdf)).trailer.get("/Root"))
        xmp = _xmp(root)
        names = None if root is None else _dictionary(root.get("/Names"))
        dropped = [f"/Names {key}" for key in cast(dict[str, object], names or {})]
        if root is not None and root.get("/AF") is not None:
            dropped.append("/AF")
    except Exception as error:  # noqa: BLE001 - pypdf raises many kinds on malformed input
        raise InvoiceWriteError(f"the PDF isn't readable: {error!r}") from None
    if _pdfa_part(xmp) not in ("1", "2", "3"):
        raise InvoiceWriteError(
            "the PDF declares no conformance to PDF/A-1, -2 or -3 in its XMP metadata; the input"
            " must be PDF/A"
        )
    if dropped:
        raise InvoiceWriteError(f"the PDF holds {', '.join(dropped)}, which embedding would drop")


def _xmp(root: DictionaryObject | None) -> bytes:
    """The XMP metadata of the PDF whose catalogue is `root`, or nothing."""
    metadata = None if root is None else root.get("/Metadata")
    stream = None if metadata is None else metadata.get_object()
    return stream.get_data() if isinstance(stream, StreamObject) else b""


def _pdfa_part(xmp: bytes) -> str | None:
    """The part of PDF/A the XMP metadata declares, as an element or an attribute in PDF/A's
    identification namespace, whatever its prefix."""
    try:
        root = parse(xmp)
    except InvoiceReadError:
        return None
    parts = _xmp_properties(root).get(f"{{{_PDFA_ID}}}part")
    return parts[0].strip() if parts else None


def _extract(reader: PdfReader, max_size: int) -> bytes:
    files = _embedded_files(reader)
    invoices = [(name, spec) for name, spec in files if name in INVOICE_NAMES]
    if not invoices:
        found = ", ".join(sorted(name for name, _ in files)) or "none"
        raise InvoiceReadError(
            f"the PDF holds no invoice under the names {', '.join(sorted(INVOICE_NAMES))};"
            f" its embedded files: {found}"
        )
    if len(invoices) > 1:
        raise InvoiceReadError(
            f"the PDF holds more than one invoice: {', '.join(sorted(n for n, _ in invoices))}"
        )
    ((name, spec),) = invoices
    return _inflate(name, _stream(name, spec), max_size)


def _dictionary(value: object) -> DictionaryObject | None:
    """`value`, resolved if it is a reference, when it is a dictionary."""
    get_object = getattr(value, "get_object", None)
    resolved: object = get_object() if callable(get_object) else value
    return resolved if isinstance(resolved, DictionaryObject) else None


def _embedded_files(reader: PdfReader) -> list[tuple[str, DictionaryObject]]:
    """The document's embedded files, each with its name; a name can occur more than once."""
    root = _dictionary(reader.trailer.get("/Root"))
    names = None if root is None else _dictionary(root.get("/Names"))
    files: list[tuple[str, DictionaryObject]] = []
    seen: set[int] = set()
    pending = [] if names is None else [(names.get("/EmbeddedFiles"), 0)]
    while pending:
        value, depth = pending.pop()
        node = _dictionary(value)
        if node is None or id(node) in seen:
            continue
        if depth > _MAX_DEPTH:
            raise InvoiceReadError("the PDF's tree of embedded files is nested too deeply")
        seen.add(id(node))
        if len(seen) > _MAX_ENTRIES:
            raise InvoiceReadError(
                f"the PDF's tree of embedded files has more than {_MAX_ENTRIES} entries"
            )
        kids = node.get("/Kids")
        if isinstance(kids, ArrayObject):
            pending.extend((kid, depth + 1) for kid in kids)
        entries = node.get("/Names")
        if isinstance(entries, ArrayObject):
            for key, value in zip(entries[::2], entries[1::2], strict=False):
                spec = _dictionary(value)
                if spec is not None and id(spec) not in seen:
                    seen.add(id(spec))
                    if len(seen) > _MAX_ENTRIES:
                        raise InvoiceReadError(
                            f"the PDF's tree of embedded files has more than {_MAX_ENTRIES} entries"
                        )
                    files.append((str(spec.get("/UF") or spec.get("/F") or key), spec))
    return files


def _stream(name: str, spec: DictionaryObject) -> StreamObject:
    ef = _dictionary(spec.get("/EF"))
    value = None if ef is None else ef.get("/UF") or ef.get("/F")
    stream: object = None if value is None else value.get_object()
    if not isinstance(stream, StreamObject):
        raise InvoiceReadError(f"the PDF's {name} has no embedded file stream")
    return stream


def _no_parameters(value: object) -> bool:
    """The decode parameters Haflinger takes: none, null, an empty dictionary, a predictor of 1
    (none), or an array of one of these, as for a filter given as an array; any other is
    refused, also one that changes nothing, such as /Columns without a predictor
    (REQ-003-PRS-F007)."""
    if isinstance(value, ArrayObject):
        return len(value) == 1 and _no_parameters(value[0])
    resolved = _dictionary(value)
    if value is None or isinstance(value, NullObject):
        return True
    if resolved is None:
        return False
    return all(
        key == "/Predictor" and isinstance(entry, NumberObject) and int(entry) == 1
        for key, entry in resolved.items()
    )


def _inflate(name: str, stream: StreamObject, max_size: int) -> bytes:
    """The stream's data, decoded; inflating stops once it exceeds `max_size`."""
    raw = StreamObject.get_data(stream)  # the data as stored, before any filter
    filters: object = stream.get("/Filter")
    listed: list[object] = list(filters) if isinstance(filters, ArrayObject) else [filters]
    names = [str(f) for f in listed]
    if filters is None:
        data = raw
    elif names == ["/FlateDecode"] and _no_parameters(stream.get("/DecodeParms")):
        inflater = zlib.decompressobj()
        try:
            data = inflater.decompress(raw, max_size + 1)
        except zlib.error as error:
            raise InvoiceReadError(f"the PDF's {name} can't be inflated: {error}") from None
        if len(data) <= max_size and not inflater.eof:
            raise InvoiceReadError(f"the PDF's {name} is cut off")
    elif names == ["/FlateDecode"]:
        raise InvoiceReadError(
            f"the PDF's {name} is encoded with FlateDecode with decode parameters, which"
            " Haflinger doesn't take; only none or a /Predictor of 1"
        )
    else:
        raise InvoiceReadError(
            f"the PDF's {name} is encoded with {', '.join(names)}, which Haflinger doesn't"
            " decode; only FlateDecode"
        )
    if len(data) > max_size:
        raise InvoiceReadError(f"the PDF's {name} is larger than max_size ({max_size:,} bytes)")
    return data
