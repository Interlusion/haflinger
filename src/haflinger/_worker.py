"""The worker process that runs the official stylesheets with Saxon (ADR-010).

`_saxon` starts it with `python -E -P -c` and a few lines that set its import path to the caller's
and call `main`, with ARTEFACTS as the first argument. Each request on stdin is three frames
(`_frames`): its number, the names of stylesheets below ARTEFACTS, one per line, and the document
as text. Each reply on stdout repeats the number, then holds `ok` and one frame per stylesheet's
output, `error` and Saxon's message on the document, or `broken` and Saxon's message on a
stylesheet that doesn't compile. The worker ends when stdin ends.
"""

import os
import sys
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from haflinger._frames import frames, read_frame

if TYPE_CHECKING:
    from saxonche import PySaxonProcessor, PyXsltExecutable

# SchXslt's steps from a Schematron schema to a stylesheet that reports in SVRL.
_SCHXSLT = ("schxslt/2.0/include.xsl", "schxslt/2.0/expand.xsl", "schxslt/2.0/compile-for-svrl.xsl")


class _Saxon:
    """Saxon with the stylesheets below `artefacts`, each compiled once."""

    def __init__(self, artefacts: Path) -> None:
        from saxonche import PySaxonProcessor

        self.artefacts = artefacts
        # Local files only: the stylesheets read the vendored code lists and texts, and nothing
        # else (REQ-001-PRS-NF001).
        self.processor: PySaxonProcessor = PySaxonProcessor(license=False)
        self.processor.set_configuration_property(
            "http://saxon.sf.net/feature/allowedProtocols", "file"
        )
        self.executable = cache(self._compile)

    def _compile(self, stylesheet: str) -> PyXsltExecutable:
        """A stylesheet by its path below `artefacts`. A Schematron schema (`.sch`) is compiled
        with SchXslt first; the stylesheet it gives resolves relative paths, such as a code list
        read with `document()`, against the schema's folder."""
        path = self.artefacts / stylesheet
        compiler = self.processor.new_xslt30_processor()
        if path.suffix != ".sch":
            return compiler.compile_stylesheet(stylesheet_file=str(path))
        node = self.processor.parse_xml(xml_file_name=str(path))
        text = ""
        for step in _SCHXSLT:
            text = self.executable(step).transform_to_string(xdm_node=node) or ""
            node = self.processor.parse_xml(xml_text=text)
        compiler.set_cwd(path.parent.as_uri() + "/")
        return compiler.compile_stylesheet(stylesheet_text=text)

    def transform(self, text: str, executables: list[PyXsltExecutable]) -> list[bytes]:
        """Each compiled stylesheet's output for the document, parsed once."""
        node = self.processor.parse_xml(xml_text=text)
        return [
            (executable.transform_to_string(xdm_node=node) or "").encode()
            for executable in executables
        ]


def main() -> None:
    from saxonche import PySaxonApiError

    # Replies go to the original stdout alone, buffered so that each is written whole; whatever
    # else writes to stdout, Saxon included, goes to stderr, which the caller logs.
    replies = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    requests = sys.stdin.buffer
    saxon = _Saxon(Path(sys.argv[1]))
    while (number := read_frame(requests)) is not None:
        names, document = read_frame(requests), read_frame(requests)
        if names is None or document is None:
            raise EOFError("the stream ended within a request")
        try:
            executables = [saxon.executable(name) for name in names.decode().split("\n")]
        except PySaxonApiError as error:
            reply = (b"broken", _message(error))
        else:
            try:
                reply = (b"ok", *saxon.transform(document.decode(), executables))
            except PySaxonApiError as error:
                reply = (b"error", _message(error))
        replies.write(frames(number, *reply))
        replies.flush()


def _message(error: Exception) -> bytes:
    return str(error).encode(errors="replace")


if __name__ == "__main__":
    main()
