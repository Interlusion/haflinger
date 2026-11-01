"""ZUGFeRD PDFs: the invoice taken out of a PDF, and put into one (REQ-003-PRS-F007,
REQ-004-PRS-F007). Needs the extra `pdf`.

A PDF is outside input. pypdf parses it; any failure of pypdf on a malformed PDF becomes an
`InvoiceReadError`, and the embedded file is inflated here, against `max_size`, never by pypdf
(REQ-003-PRS-NF001, REQ-003-PRS-NF003).
"""

import io
import re
import tempfile
import zlib
from pathlib import Path
from typing import cast

try:
    import facturx
    from pypdf import PdfReader, apply_configuration
    from pypdf.generic import ArrayObject, DictionaryObject, NullObject, StreamObject
except ImportError as error:
    raise ImportError("haflinger.pdf needs the extra 'pdf': install haflinger[pdf]") from error

from haflinger import write
from haflinger._input import open_invoice
from haflinger._xml import MAX_SIZE, check_size
from haflinger.errors import InvoiceReadError, InvoiceWriteError

# The names of the embedded invoice (REQ-003-PRS-F007).
INVOICE_NAMES = frozenset(
    {"factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml", "ZUGFeRD-invoice.xml"}
)
# REQ-004-PRS-F007: the target profile embed writes, with its Factur-X level.
_EMBED_LEVELS = {"urn:cen.eu:en16931:2017": "en16931"}
_PDFA_PART = re.compile(rb"pdfaid:part(?:>|=[\"'])\s*[1-3](?![0-9])")
_MAX_DEPTH = 32  # of the name tree of embedded files
_MAX_ENTRIES = 100  # nodes and files of that tree read, at most (REQ-003-PRS-NF003)
_PYPDF_LIMIT = 2_000_000  # bytes, for each stream pypdf decodes while the invoice is looked for


def extract_xml(data: bytes, *, max_size: int = MAX_SIZE) -> bytes:
    """The invoice embedded in a ZUGFeRD PDF, byte for byte and not parsed. Raises
    `InvoiceReadError` when the input isn't a readable PDF, holds no invoice or more than one
    under the names of `INVOICE_NAMES`, or the invoice exceeds `max_size`."""
    if not isinstance(cast(object, data), bytes):
        raise InvoiceReadError(f"the input is not bytes but {type(data).__name__}")
    check_size(data, max_size)
    try:
        # pypdf's own decoding (object and cross-reference streams) stays small: none of what
        # leads to the invoice needs more, and the decoded data is kept while the PDF is read.
        with apply_configuration(
            zlib_maximum_output_length=_PYPDF_LIMIT,
            lzw_maximum_output_length=_PYPDF_LIMIT,
            run_length_maximum_output_length=_PYPDF_LIMIT,
            brotli_maximum_output_length=_PYPDF_LIMIT,
        ):
            return _extract(PdfReader(io.BytesIO(data)), max_size)
    except InvoiceReadError:
        raise
    except Exception as error:  # noqa: BLE001 - pypdf raises many kinds on malformed input
        raise InvoiceReadError(f"the input isn't a readable PDF: {error!r}") from None


def embed(pdf: bytes, xml: bytes) -> bytes:
    """`pdf`, a PDF/A file, as a PDF/A-3 ZUGFeRD PDF with `xml` embedded, when `xml` is a CII
    invoice of the target profile embed writes and passes the XML Schema and the official rules.
    Raises `InvoiceWriteError` otherwise (REQ-004-PRS-F007)."""
    for argument, value in (("PDF", cast(object, pdf)), ("XML", cast(object, xml))):
        if not isinstance(value, bytes):
            raise InvoiceWriteError(f"the {argument} is not bytes but {type(value).__name__}")
    try:
        opened = open_invoice(xml, MAX_SIZE, pdf="the XML is a PDF")
    except InvoiceReadError as error:
        raise InvoiceWriteError(f"the XML can't be read: {error}") from None
    level = _EMBED_LEVELS.get(opened.specification_id or "")
    if opened.document != "cii" or level is None:
        raise InvoiceWriteError(
            f"embed writes only CII invoices with BT-24 {', '.join(_EMBED_LEVELS)};"
            f" this is {opened.document} with BT-24 {opened.specification_id!r}"
        )
    _check_pdf(pdf)
    write.refuse_if_invalid(write.check_written(xml, opened.specification_id), xml)
    result = _embed(pdf, xml, level)
    try:
        reader = PdfReader(io.BytesIO(result), strict=True)
        embedded = list(reader.attachments)
        extracted = extract_xml(result)
    except Exception as error:  # noqa: BLE001 - checking factur-x's result
        raise InvoiceWriteError(f"the written PDF can't be read back: {error!r}") from None
    if result.count(b"%PDF-") != 1 or embedded != ["factur-x.xml"] or extracted != xml:
        raise InvoiceWriteError("the written PDF doesn't carry the invoice as given")
    return result


def _embed(pdf: bytes, xml: bytes, level: str) -> bytes:
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
                output_pdf_file=str(target),
            )
            return target.read_bytes()
    except Exception as error:  # noqa: BLE001 - factur-x and pypdf raise many kinds
        raise InvoiceWriteError(f"the PDF can't be written: {error!r}") from None


def _check_pdf(pdf: bytes) -> None:
    """A PDF/A-1, -2 or -3 file holding nothing that embedding would drop."""
    try:
        root = _dictionary(PdfReader(io.BytesIO(pdf)).trailer.get("/Root"))
        metadata = None if root is None else root.get("/Metadata")
        stream = None if metadata is None else metadata.get_object()
        xmp = stream.get_data() if isinstance(stream, StreamObject) else b""
        names = None if root is None else _dictionary(root.get("/Names"))
        dropped = [
            key
            for key, value in (
                ("/Names /EmbeddedFiles", None if names is None else names.get("/EmbeddedFiles")),
                ("/Names /Dests", None if names is None else names.get("/Dests")),
                ("/Dests", None if root is None else root.get("/Dests")),
                ("/AF", None if root is None else root.get("/AF")),
            )
            if value is not None
        ]
    except Exception as error:  # noqa: BLE001 - pypdf raises many kinds on malformed input
        raise InvoiceWriteError(f"the PDF isn't readable: {error!r}") from None
    if _PDFA_PART.search(xmp) is None:
        raise InvoiceWriteError(
            "the PDF declares no conformance to PDF/A-1, -2 or -3 in its XMP metadata; the input"
            " must be PDF/A"
        )
    if dropped:
        raise InvoiceWriteError(
            f"the PDF holds embedded files or named destinations ({', '.join(dropped)}), which"
            " embedding would drop"
        )


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
    """No decode parameters: none, null, or an empty dictionary."""
    resolved = _dictionary(value)
    return value is None or isinstance(value, NullObject) or (resolved is not None and not resolved)


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
    else:
        raise InvoiceReadError(
            f"the PDF's {name} is encoded with {', '.join(names)}, which Haflinger doesn't"
            " decode; only FlateDecode without parameters"
        )
    if len(data) > max_size:
        raise InvoiceReadError(f"the PDF's {name} is larger than max_size ({max_size:,} bytes)")
    return data
