"""The attached document of a supporting document (BT-125): what reading it shares across the
syntaxes and with the tests' second reader (REQ-003-PRS-F002, REQ-003-PRS-F005, ADR-011).

Haflinger decodes an attachment's Base64 and hands back its bytes; it never opens them.
"""

import binascii

from haflinger._model import Attachment
from haflinger._xml import XML_WHITESPACE, Node

_NO_WHITESPACE = str.maketrans("", "", XML_WHITESPACE)


def attachment(
    node: Node | None, mime_code: str = "mimeCode", filename: str = "filename"
) -> Attachment | None:
    """The attached document whose Base64 text `node` holds, with its media type (BT-125-1) and
    file name (BT-125-2) in the attributes `mime_code` and `filename`: by default `mimeCode` and
    `filename`, which CII and UBL share. The text is decoded without the XML whitespace that
    `xs:base64Binary` allows within it (REQ-001-URS-NF001); text that isn't Base64 as
    `xs:base64Binary` defines it is missing, with a finding."""
    if node is None or (text := node.value) is None:
        return None
    try:
        content = _decoded(text)
    except ValueError:  # binascii.Error, and text that isn't ASCII
        node.malformed("BT-125", "Base64", text)
        return None
    return Attachment(
        content=content, mime_code=node.attribute(mime_code), filename=node.attribute(filename)
    )


def _decoded(text: str) -> bytes:
    """The bytes of Base64 `text`, copied once more only where it holds whitespace, which none
    of the official files does (ADR-011). Python's decoder ignores bits of the last characters
    beyond the bytes, as in `QR==` for `A`, which `xs:base64Binary` refuses: the last four
    characters are written again from their bytes and compared."""
    if any(character in text for character in XML_WHITESPACE):
        text = text.translate(_NO_WHITESPACE)
    content = binascii.a2b_base64(text, strict_mode=True)
    if padding := (tail := text[-4:]).count("="):  # strict mode allows it only at the end
        last = binascii.b2a_base64(content[padding - 3 :], newline=False)
        if last != tail.encode("ascii"):
            raise binascii.Error("bits beyond the bytes")
    return content
