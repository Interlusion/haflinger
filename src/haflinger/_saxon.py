"""Running official stylesheets with Saxon, unchanged (ADR-006). `saxonche` is imported on first
use, so that importing Haflinger and reading invoices don't load it (ADR-005)."""

import threading
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from haflinger._xml import decode
from haflinger.errors import InvoiceReadError

if TYPE_CHECKING:
    from saxonche import PySaxonProcessor, PyXsltExecutable

ARTEFACTS = Path(__file__).parent / "artefacts"
# One thread at a time compiles and runs stylesheets: a compiled stylesheet keeps state while it
# runs, and the caches below must not be filled twice.
_LOCK = threading.Lock()


@cache
def _processor() -> PySaxonProcessor:
    """Saxon, allowed to open local files only: the stylesheets read the vendored code lists and
    texts, and nothing else (REQ-001-PRS-NF001)."""
    from saxonche import PySaxonProcessor

    processor = PySaxonProcessor(license=False)
    processor.set_configuration_property("http://saxon.sf.net/feature/allowedProtocols", "file")
    return processor


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


class TransformError(InvoiceReadError):
    """Saxon failed on the document or in a stylesheet."""


def transform(data: bytes, *stylesheets: str) -> list[bytes]:
    """Apply each stylesheet to XML that `_xml.parse` has accepted, so that it holds no DTD and
    no entity. Saxon gets the document as received, decoded in memory by the encoding the XML
    parser accepted, and parses it once: a tree written out again would have other namespace
    prefixes and no comments, and some rules see that (REQ-002-PRS-F006); a file would put the
    input on disk (REQ-001-PRS-NF001)."""
    from saxonche import PySaxonApiError

    text = decode(data)
    with _LOCK:
        executables = [_executable(stylesheet) for stylesheet in stylesheets]
        try:
            node = _processor().parse_xml(xml_text=text)
            results = [executable.transform_to_string(xdm_node=node) for executable in executables]
        except PySaxonApiError as error:
            raise TransformError(f"Saxon can't process the input: {error}") from None
    return [(result or "").encode() for result in results]


def clear_caches() -> None:
    """Forget the compiled stylesheets, so that the next use compiles them again."""
    with _LOCK:
        _executable.cache_clear()
