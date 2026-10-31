"""Running official stylesheets with Saxon, unchanged (ADR-006)."""

import tempfile
from functools import cache
from pathlib import Path

from saxonche import PySaxonProcessor, PyXsltExecutable

ARTEFACTS = Path(__file__).parent / "artefacts"


@cache
def _processor() -> PySaxonProcessor:
    return PySaxonProcessor(license=False)


@cache
def _executable(stylesheet: str) -> PyXsltExecutable:
    """A stylesheet by its path below `artefacts/`, compiled once per process."""
    compiler = _processor().new_xslt30_processor()
    return compiler.compile_stylesheet(stylesheet_file=str(ARTEFACTS / stylesheet))


def transform(data: bytes, stylesheet: str) -> bytes:
    """Apply a stylesheet to XML that `_xml.parse` has accepted, so that it holds no DTD and no
    entity. Saxon reads the original bytes from a file, in the encoding they declare: a tree
    serialised again would drop comments and change what the stylesheet sees."""
    with tempfile.TemporaryDirectory(prefix="haflinger-") as directory:
        source = Path(directory) / "input.xml"
        source.write_bytes(data)
        result = _executable(stylesheet).transform_to_string(source_file=str(source))
    return (result or "").encode()
