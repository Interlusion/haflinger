# The part of factur-x's API Haflinger uses; the package ships no type information.

def generate_from_binary(
    pdf_file: bytes, xml: bytes, *, flavor: str, level: str, check_xsd: bool
) -> bytes: ...
