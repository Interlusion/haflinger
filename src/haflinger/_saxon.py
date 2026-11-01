"""Running official stylesheets with Saxon, unchanged (ADR-006). `saxonche` is imported on first
use, so that importing Haflinger and reading invoices don't load it (ADR-005)."""

import codecs
import re
import threading
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from haflinger.errors import InvoiceReadError

if TYPE_CHECKING:
    from saxonche import PySaxonProcessor, PyXsltExecutable

ARTEFACTS = Path(__file__).parent / "artefacts"
# One thread at a time compiles and runs stylesheets: a compiled stylesheet keeps state while it
# runs, and the caches below must not be filled twice.
_LOCK = threading.Lock()


@cache
def _processor() -> PySaxonProcessor:
    from saxonche import PySaxonProcessor

    return PySaxonProcessor(license=False)


# SchXslt's steps from a Schematron schema to a stylesheet that reports in SVRL.
_SCHXSLT = ("schxslt/2.0/include.xsl", "schxslt/2.0/expand.xsl", "schxslt/2.0/compile-for-svrl.xsl")


@cache
def _executable(stylesheet: str) -> PyXsltExecutable:
    """A stylesheet by its path below `artefacts/`, compiled once per process. A Schematron
    schema (`.sch`) is compiled with SchXslt first; the stylesheet it gives resolves relative
    paths, such as a code list read with `document()`, against the schema's folder."""
    path = ARTEFACTS / stylesheet
    compiler = _processor().new_xslt30_processor()
    if path.suffix != ".sch":
        return compiler.compile_stylesheet(stylesheet_file=str(path))
    node = _processor().parse_xml(xml_file_name=str(path))
    text = ""
    for step in _SCHXSLT:
        text = _executable(step).transform_to_string(xdm_node=node) or ""
        node = _processor().parse_xml(xml_text=text)
    compiler.set_cwd(path.parent.as_uri() + "/")
    return compiler.compile_stylesheet(stylesheet_text=text)


def transform(data: bytes, *stylesheets: str) -> list[bytes]:
    """Apply each stylesheet to XML that `_xml.parse` has accepted, so that it holds no DTD and
    no entity. Saxon gets the document as received, decoded in memory by the encoding the XML
    parser accepted, and parses it once: a tree written out again would have other namespace
    prefixes and no comments, and some rules see that (REQ-002-PRS-F006); a file would put the
    input on disk (REQ-001-PRS-NF001)."""
    from saxonche import PySaxonApiError

    text = decoded(data)
    with _LOCK:
        executables = [_executable(stylesheet) for stylesheet in stylesheets]
        try:
            node = _processor().parse_xml(xml_text=text)
            results = [executable.transform_to_string(xdm_node=node) for executable in executables]
        except PySaxonApiError as error:
            raise InvoiceReadError(f"Saxon can't process the input: {error}") from None
    return [(result or "").encode() for result in results]


def clear_caches() -> None:
    """Forget the compiled stylesheets, so that the next use compiles them again."""
    with _LOCK:
        _executable.cache_clear()


_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)
_DECLARED = re.compile(rb"""<\?xml[^>]*?encoding\s*=\s*["']([A-Za-z][A-Za-z0-9._-]*)["']""")


def decoded(data: bytes) -> str:
    """The text of an XML document, as the XML parser reads it: by its byte order mark, else by
    the encoding its declaration names, else UTF-8 (UTF-16 recognised by its first bytes)."""
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            return _decode(data[len(bom) :], encoding)
    if data.startswith(b"<\x00?\x00"):
        return _decode(data, "utf-16-le")
    if data.startswith(b"\x00<\x00?"):
        return _decode(data, "utf-16-be")
    declared = _DECLARED.match(data)
    return _decode(data, declared[1].decode("ascii") if declared else "utf-8")


def _decode(data: bytes, encoding: str) -> str:
    try:
        return data.decode(encoding)
    except (LookupError, UnicodeDecodeError) as error:
        raise InvoiceReadError(f"the input can't be decoded as {encoding}: {error}") from None
