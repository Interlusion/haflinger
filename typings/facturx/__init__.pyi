# The part of factur-x's API Haflinger uses; the package ships no type information.

def generate_from_file(
    pdf_file: str,
    xml: bytes,
    *,
    flavor: str,
    level: str,
    check_xsd: bool,
    pdf_metadata: dict[str, str],
    output_pdf_file: str,
    afrelationship: str,
) -> bool: ...
