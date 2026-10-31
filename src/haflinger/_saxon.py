"""Running official stylesheets with Saxon, unchanged (ADR-006). `saxonche` is imported on first
use, so that importing Haflinger and reading invoices don't load it (ADR-005)."""

import tempfile
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from haflinger.errors import InvoiceReadError

if TYPE_CHECKING:
    from saxonche import PySaxonProcessor, PyXsltExecutable

ARTEFACTS = Path(__file__).parent / "artefacts"


@cache
def _processor() -> PySaxonProcessor:
    from saxonche import PySaxonProcessor

    return PySaxonProcessor(license=False)


@cache
def _executable(stylesheet: str) -> PyXsltExecutable:
    """A stylesheet by its path below `artefacts/`, compiled once per process."""
    compiler = _processor().new_xslt30_processor()
    return compiler.compile_stylesheet(stylesheet_file=str(ARTEFACTS / stylesheet))


def transform(data: bytes, *stylesheets: str) -> list[bytes]:
    """Apply each stylesheet to XML that `_xml.parse` has accepted, so that it holds no DTD and
    no entity. Saxon parses the original bytes once, from a file, in the encoding they declare: a
    tree written out again would have other namespace prefixes and no comments, and some rules
    see that (REQ-002-PRS-F006)."""
    from saxonche import PySaxonApiError

    executables = [_executable(stylesheet) for stylesheet in stylesheets]
    with tempfile.TemporaryDirectory(prefix="haflinger-") as directory:
        source = Path(directory) / "input.xml"
        source.write_bytes(data)
        try:
            node = _processor().parse_xml(xml_file_name=str(source))
            results = [executable.transform_to_string(xdm_node=node) for executable in executables]
        except PySaxonApiError as error:
            raise InvoiceReadError(f"Saxon can't process the input: {error}") from None
    return [(result or "").encode() for result in results]
