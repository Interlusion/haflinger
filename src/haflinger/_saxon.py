"""Running official stylesheets with Saxon, unchanged (ADR-006). `saxonche` is imported on first
use, so that importing Haflinger and reading invoices don't load it (ADR-005)."""

import tempfile
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
    compiler.set_cwd(str(path.parent))
    return compiler.compile_stylesheet(stylesheet_text=text)


def transform(data: bytes, *stylesheets: str) -> list[bytes]:
    """Apply each stylesheet to XML that `_xml.parse` has accepted, so that it holds no DTD and
    no entity. Saxon parses the original bytes once, from a file, in the encoding they declare: a
    tree written out again would have other namespace prefixes and no comments, and some rules
    see that (REQ-002-PRS-F006)."""
    from saxonche import PySaxonApiError

    with tempfile.TemporaryDirectory(prefix="haflinger-") as directory, _LOCK:
        executables = [_executable(stylesheet) for stylesheet in stylesheets]
        source = Path(directory) / "input.xml"
        source.write_bytes(data)
        try:
            node = _processor().parse_xml(xml_file_name=str(source))
            results = [executable.transform_to_string(xdm_node=node) for executable in executables]
        except PySaxonApiError as error:
            raise InvoiceReadError(f"Saxon can't process the input: {error}") from None
    return [(result or "").encode() for result in results]
