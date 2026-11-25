"""Validation with the official rules, run unchanged with Saxon (REQ-002, ADR-006).

The rule sets of EN 16931 and XRechnung, with their levels, are those of KoSIT's validator
configuration: its scenario file names the stylesheets for each profile and lowers or raises the
levels of some rules. The Factur-X profiles have FeRD's Schematron, compiled with SchXslt.
"""

import re
import time
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from xml.etree.ElementTree import Element

from haflinger import _cii, _read, _saxon, _ubl, _xsd
from haflinger._errors import InvoiceReadError
from haflinger._findings import Finding, Flag
from haflinger._input import Document, Opened, open_invoice
from haflinger._xml import MAX_SIZE, XML_WHITESPACE, decode, parse, quoted
from haflinger._xsd import _Element  # pyright: ignore[reportPrivateUsage]

_CONFIGURATION = "kosit-validator-xrechnung"
_SCENARIOS_NAMESPACE = "{http://www.xoev.de/de/validator/framework/1/scenarios}"
_SVRL = "{http://purl.oclc.org/dsdl/svrl}"

_EN16931 = "urn:cen.eu:en16931:2017"
_XRECHNUNG = f"{_EN16931}#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
_EXTENSION = f"{_XRECHNUNG}#conformant#urn:xeinkauf.de:kosit:extension:xrechnung_3.0"
_CVD = f"{_XRECHNUNG}#compliant#urn:xeinkauf.de:kosit:xrechnung:cvd_0.9"

# REQ-002-PRS-F003: KoSIT's scenario for each document and BT-24. KoSIT has no scenario for the
# extension in a UBL credit note.
_RULE_SETS: dict[tuple[Document, str], str] = {
    ("cii", _EN16931): "EN16931 (CII)",
    ("cii", _XRECHNUNG): "EN16931 XRechnung (CII)",
    ("cii", _EXTENSION): "EN16931 XRechnung Extension (CII)",
    ("cii", _CVD): "EN16931 XRechnung CVD (CII)",
    ("ubl-invoice", _EN16931): "EN16931 (UBL Invoice)",
    ("ubl-invoice", _XRECHNUNG): "EN16931 XRechnung (UBL Invoice)",
    ("ubl-invoice", _EXTENSION): "EN16931 XRechnung Extension (UBL Invoice)",
    ("ubl-invoice", _CVD): "EN16931 XRechnung CVD (UBL Invoice)",
    ("ubl-credit-note", _EN16931): "EN16931 (UBL CreditNote)",
    ("ubl-credit-note", _XRECHNUNG): "EN16931 XRechnung (UBL CreditNote)",
    ("ubl-credit-note", _CVD): "EN16931 XRechnung CVD (UBL CreditNote)",
}
# REQ-002-PRS-F003: the Factur-X profiles, in CII only, by each BT-24 that names them (the
# alternative spellings included), with FeRD's Schematron for the profile.
_FERD = "ferd-zugferd/Schema"
_FACTUR_X: dict[str, tuple[str, tuple[str, ...]]] = {
    "Factur-X MINIMUM": (
        f"{_FERD}/0_Factur-X_1.09.2_MINIMUM/FACTUR-X_MINIMUM.sch",
        ("urn:factur-x.eu:1p0:minimum", "urn:zugferd.de:2p0:minimum"),
    ),
    "Factur-X BASIC WL": (
        f"{_FERD}/1_Factur-X_1.09.2_BASICWL/FACTUR-X_BASIC-WL.sch",
        ("urn:factur-x.eu:1p0:basicwl", "urn:zugferd.de:2p0:basicwl"),
    ),
    "Factur-X BASIC": (
        f"{_FERD}/2_Factur-X_1.09.2_BASIC/FACTUR-X_BASIC.sch",
        (
            f"{_EN16931}#compliant#urn:factur-x.eu:1p0:basic",
            f"{_EN16931}#compliant#urn:zugferd.de:2p0:basic",
            f"{_EN16931}:compliant:factur-x.eu:1p0:basic",
        ),
    ),
    "Factur-X EXTENDED": (
        f"{_FERD}/4_Factur-X_1.09.2_EXTENDED/FACTUR-X_EXTENDED.sch",
        (
            f"{_EN16931}#conformant#urn:factur-x.eu:1p0:extended",
            f"{_EN16931}#conformant#urn:zugferd.de:2p0:extended",
            f"{_EN16931}:compliant:factur-x.eu:1p0:extended",
        ),
    ),
}
# REQ-002-PRS-F011: FeRD's XML Schema of each Factur-X profile.
# REQ-004-PRS-F005: FeRD's rules of the EN 16931 profile, for a written invoice of that profile;
# an incoming one is judged by CEN's rules, as KoSIT's scenario does (REQ-002-PRS-F003).
FACTUR_X_EN16931 = "Factur-X EN 16931"
_FACTUR_X_EN16931 = (
    f"{_FERD}/3_Factur-X_1.09.2_EN16931/Factur-X_1.09.2_EN16931.xsd",
    f"{_FERD}/3_Factur-X_1.09.2_EN16931/FACTUR-X_EN16931.sch",
)
_FACTUR_X_SCHEMAS = {
    "Factur-X MINIMUM": f"{_FERD}/0_Factur-X_1.09.2_MINIMUM/Factur-X_1.09.2_MINIMUM.xsd",
    "Factur-X BASIC WL": f"{_FERD}/1_Factur-X_1.09.2_BASICWL/Factur-X_1.09.2_BASICWL.xsd",
    "Factur-X BASIC": f"{_FERD}/2_Factur-X_1.09.2_BASIC/Factur-X_1.09.2_BASIC.xsd",
    "Factur-X EXTENDED": f"{_FERD}/4_Factur-X_1.09.2_EXTENDED/Factur-X_1.09.2_EXTENDED.xsd",
}
_RULE_SETS.update(
    {
        ("cii", specification_id): name
        for name, (_, spellings) in _FACTUR_X.items()
        for specification_id in spellings
    }
)
# REQ-002-PRS-F003: the rows whose scenario compares BT-24's whole text, XPath's string value;
# the others' compare each of its text nodes, and so are the Factur-X rows compared, where no
# row of KoSIT's matches.
_BY_WHOLE_TEXT = frozenset(
    {("ubl-invoice", _XRECHNUNG), ("ubl-invoice", _EXTENSION), ("ubl-invoice", _CVD)}
)
_SPECIFICATIONS: dict[Document, str] = {
    "cii": _cii.SPECIFICATION,
    "ubl-invoice": _ubl.SPECIFICATION,
    "ubl-credit-note": _ubl.SPECIFICATION,
}
# The limits of an invoice that is validated (REQ-002-PRS-F001): empty elements and the characters
# of their locations, the digits of a number, the characters of a telephone number.
_MAX_EMPTY = 1000
_MAX_LOCATIONS = 10_000_000
_MAX_DIGITS = 1000
_MAX_TELEPHONE = 100
_MAX_PIECES = 5  # the values of each list in a `HAFL-PROFILE` text
_NUMBER = re.compile(r"[+-]?[0-9]*\.?[0-9]*")
_TELEPHONES = frozenset(
    {
        "{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}"
        "CompleteNumber",
        "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Telephone",
    }
)
_DOCUMENTS: dict[Document, str] = {
    "cii": "a CII invoice",
    "ubl-invoice": "a UBL invoice",
    "ubl-credit-note": "a UBL credit note",
}
# REQ-002-PRS-F013: the rules of KoSIT's XRechnung stylesheets that ask for what §14(4) UStG asks,
# run on any profile (ADR-014), with the scenario whose stylesheet is taken for each document.
GERMAN_VAT_RULES = frozenset({"BR-DE-TMP-32", "BR-DE-3", "BR-DE-4", "BR-DE-8", "BR-DE-9"})
_GERMAN_VAT_SCENARIOS: dict[Document, str] = {
    "cii": "EN16931 XRechnung (CII)",
    "ubl-invoice": "EN16931 XRechnung (UBL Invoice)",
    "ubl-credit-note": "EN16931 XRechnung (UBL CreditNote)",
}
# REQ-002-PRS-F012: the profiles that are no e-invoices under §14(1) UStG.
_NO_E_INVOICES = ("Factur-X MINIMUM", "Factur-X BASIC WL")
# REQ-002-PRS-F014: the small invoices of §33 UStDV, in EUR, and what they don't need; the
# categories of intra-Community supplies and reverse charge, to which §33 doesn't apply; the
# types of credit notes and advance payments, which need no time of supply.
_SMALL = Decimal(250)
_SMALL_NEEDS_NOT = frozenset({"BR-DE-TMP-32", "BR-DE-8", "BR-DE-9"})
_NOT_SMALL = frozenset({"K", "AE"})
_NO_TIME_OF_SUPPLY = frozenset({"381", "386"})
_FLAGS: dict[str, Flag] = {
    "fatal": "fatal",
    "error": "error",
    "warning": "warning",
    "information": "information",
}


@dataclass(frozen=True, kw_only=True)
class _Scenario:
    schema: str  # the XML Schema checked first (REQ-002-PRS-F011)
    stylesheets: tuple[str, ...]
    levels: dict[str, Flag]  # KoSIT's level by rule ID, where it sets one


def validate(
    data: bytes, *, max_size: int = MAX_SIZE, timeout: float | None = None
) -> tuple[Finding, ...]:
    """Validate a CII invoice or a UBL invoice or credit note with the rule set its syntax and
    BT-24 call for. Raises `InvoiceReadError` for input that can't be read (REQ-002-PRS-F001),
    and where the rules don't end within `timeout` seconds, by default `HAFLINGER_RULES_TIMEOUT`
    or 60 (REQ-002-PRS-NF004)."""
    limit = _saxon.time_limit(timeout)
    opened, name, no_profile, schema = _schema_checked(data, max_size, "validate")
    findings = [] if no_profile is None else [no_profile]
    if schema:
        return (*findings, *schema)
    return (*findings, *_rules(data, name, opened, limit, time.monotonic()))


def check_german_vat(
    data: bytes, *, max_size: int = MAX_SIZE, timeout: float | None = None
) -> tuple[Finding, ...]:
    """Check a CII invoice or a UBL invoice or credit note for what §14(4) UStG asks of it
    beyond the rules of its profile, with KoSIT's German rules of XRechnung on any profile
    (REQ-002-PRS-F012 to REQ-002-PRS-F015, ADR-014); Factur-X MINIMUM and BASIC WL, no
    e-invoices under §14(1) UStG, get `HAFL-DE-PROFILE` instead. Refuses what `validate`
    refuses, with the same limits and time limit; the XML Schema check comes first.

    Call it where German invoicing law, §14 UStG, governs the invoice: that follows the place of
    supply, and on reverse charge the state where the supplier is established, which Haflinger
    doesn't decide. Every finding is meant to be shown, whatever its flag; `is_valid` is for
    `validate`'s findings, not these. The time of supply (`BR-DE-TMP-32`, `information`) is
    missing on many proper invoices, as the invoice date may give it (UStAE 15.2a (1a)).

    Not checked: the street or post office box (BT-35, BT-50); price reductions agreed in
    advance, such as a cash discount (§14(4) no. 7); the date of an advance payment (no. 6); the
    notes of nos. 9 and 10; the buyer's VAT identifier on a reverse charge for a service in
    another member state (§14a(1) UStG); the line delivery dates of Factur-X EXTENDED, which
    `BR-DE-TMP-32` doesn't see; distance sales among small invoices (§3c UStG); credit notes of
    other types than `381`, which keep `BR-DE-TMP-32`. A buyer in a country without post codes
    gets `BR-DE-9`. The check states what it checks, not that an invoice meets the law."""
    limit = _saxon.time_limit(timeout)
    opened, name, _, schema = _schema_checked(data, max_size, "check")
    if schema:
        return tuple(schema)
    if name in _NO_E_INVOICES:
        return (_no_e_invoice(opened, name),)
    stylesheet, levels = _german_vat_rules(opened.document)
    findings = _run(
        data, (stylesheet,), levels, "the German VAT check", opened, limit, time.monotonic()
    )
    found = {finding.rule for finding in findings}
    dropped = _needs_not(opened) if found & _SMALL_NEEDS_NOT else frozenset[str]()
    return tuple(
        finding
        for finding in findings
        if finding.rule == "HAFL-RULES"
        or (finding.rule in GERMAN_VAT_RULES and finding.rule not in dropped)
    )


def _schema_checked(
    data: bytes, max_size: int, verb: str
) -> tuple[Opened, str, Finding | None, list[Finding]]:
    """The steps before the rules that `validate` and `check_german_vat` share: the invoice
    opened, with what can't be read or would cost too much refused (REQ-002-PRS-F001), the name
    of the rule set its BT-24 calls for, the finding that BT-24 names no profile, and the
    findings of the rule set's XML Schema (REQ-002-PRS-F011); `verb` names the call in the
    message on a PDF."""
    opened = open_invoice(
        data,
        max_size,
        pdf=f"the input is a PDF; {verb} the XML that haflinger.pdf.extract_xml gives",
    )
    _refuse_costly(opened)
    text = decode(data)
    tree = _xsd.tree(text)
    name, no_profile = rule_set(opened, tree)
    return (
        opened,
        name,
        no_profile,
        _xsd.check(text if tree is None else tree, _scenarios()[name].schema),
    )


def _german_vat_rules(document: Document) -> tuple[str, dict[str, Flag]]:
    """The XRechnung stylesheet of the document's scenario, which holds KoSIT's German rules,
    with KoSIT's levels; a KoSIT release that moves or splits it fails here rather than leaving
    the check without rules."""
    scenario = _scenarios()[_GERMAN_VAT_SCENARIOS[document]]
    found = [path for path in scenario.stylesheets if "/xrechnung/" in path]
    if len(found) != 1:
        raise RuntimeError(
            f"the scenario {_GERMAN_VAT_SCENARIOS[document]} holds {len(found)} XRechnung"
            f" stylesheets, not one: {', '.join(scenario.stylesheets)}"
        )
    return found[0], scenario.levels


def _no_e_invoice(opened: Opened, name: str) -> Finding:
    """`HAFL-DE-PROFILE` (REQ-002-PRS-F010), at the BT-24 that names the profile."""
    return Finding(
        rule="HAFL-DE-PROFILE",
        flag="error",
        location=(opened.specification or opened.reading.root).path,
        text=f"{name} is no e-invoice under §14(1) UStG: its XML lacks what §14(4) UStG asks"
        " for, such as the invoice lines; the German VAT check's rules weren't run",
    )


def _needs_not(opened: Opened) -> frozenset[str]:
    """The rules whose findings the law doesn't support for the invoice, by the values reading
    gives (REQ-002-PRS-F014), the VAT categories of the breakdown and of the lines; a value that
    isn't read, or a breakdown that isn't, shows no exception."""
    invoice = _read.model(opened)
    needs_not = set[str]()
    if invoice.type_code in _NO_TIME_OF_SUPPLY:
        needs_not.add("BR-DE-TMP-32")
    total = None if invoice.totals is None else invoice.totals.total_with_vat
    categories = {breakdown.category_code for breakdown in invoice.vat_breakdown}
    categories |= {line.vat_category_code for line in invoice.lines}
    if (
        total is not None
        and invoice.vat_breakdown
        and abs(total) <= _SMALL
        and invoice.currency_code == "EUR"
        and None not in categories
        and not categories & _NOT_SMALL
    ):
        needs_not |= _SMALL_NEEDS_NOT
    return frozenset(needs_not)


def _refuse_costly(opened: Opened) -> None:
    """Refuse the shapes on which the rules would take minutes or gigabytes (REQ-002-PRS-F001):
    more than `_MAX_EMPTY` empty elements, each failing PEPPOL-EN16931-R008 and located by counting
    its preceding siblings, or fewer whose locations, each step `Q{namespace}name[position]`, total
    more than `_MAX_LOCATIONS` characters; a number of more than `_MAX_DIGITS` digits, whose
    arithmetic grows with the square of its length; a telephone number of more than
    `_MAX_TELEPHONE` characters, which XRechnung's BR-DE-27 checks with a pattern growing with the
    square of the length."""
    empty = locations = 0
    root = opened.reading.root.element
    located = {root: _step(root.tag, 1)}  # each element's location's length, until it is reached
    for element in root.iter():
        location = located.pop(element)
        text = (element.text or "").strip(XML_WHITESPACE)
        if len(element) == 0 and not text:
            empty += 1
            locations += location
        elif element.tag in _TELEPHONES and len(text) > _MAX_TELEPHONE:
            raise InvoiceReadError(
                f"the invoice holds a telephone number of {len(text):,} characters, more than"
                f" {_MAX_TELEPHONE}; Haflinger doesn't run the official rules on it, which would"
                " take minutes"
            )
        elif len(text) > _MAX_DIGITS and _NUMBER.fullmatch(text):
            digits = sum(character.isdigit() for character in text)
            if digits > _MAX_DIGITS:
                raise InvoiceReadError(
                    f"the invoice holds a number of {digits:,} digits, more than {_MAX_DIGITS:,};"
                    " Haflinger doesn't run the official rules on it, which would take minutes"
                )
        if len(element):
            positions = dict[str, int]()
            for child in element:
                positions[child.tag] = position = positions.get(child.tag, 0) + 1
                located[child] = location + _step(child.tag, position)
    if empty > _MAX_EMPTY:
        raise InvoiceReadError(
            f"the invoice holds {empty:,} empty elements, more than {_MAX_EMPTY:,}; Haflinger"
            " doesn't run the official rules on it, which would take minutes"
        )
    if locations > _MAX_LOCATIONS:
        raise InvoiceReadError(
            f"the locations of the invoice's empty elements total {locations:,} characters, more"
            f" than {_MAX_LOCATIONS:,}; Haflinger doesn't run the official rules on it, whose"
            " findings would take gigabytes"
        )


def _step(tag: str, position: int) -> int:
    """The length of a location's step `/Q{namespace}name[position]` for an element's tag."""
    return len(tag) + len(str(position)) + (4 if tag.startswith("{") else 6)


def check_rules(data: bytes, *also: str, timeout: float | None = None) -> tuple[Finding, ...]:
    """Like `validate`, without the XML Schema check: for fragments that aren't whole invoices,
    as in CEN's per-rule unit tests, and for written invoices, whose schemas `write` checks.
    `also` names further rule sets to run, such as `FACTUR_X_EN16931`; `timeout` bounds them
    together."""
    limit = _saxon.time_limit(timeout)
    started = time.monotonic()
    opened = open_invoice(data, MAX_SIZE, pdf="the input is a PDF")
    name, no_profile = rule_set(opened, _xsd.tree(decode(data)))
    findings = [] if no_profile is None else [no_profile]
    for each in (name, *also):
        findings.extend(_rules(data, each, opened, limit, started))
    return tuple(findings)


def _rules(data: bytes, name: str, opened: Opened, timeout: float, started: float) -> list[Finding]:
    """The findings of a rule set; where the rules themselves fail on the invoice, `HAFL-RULES`,
    as KoSIT's validator reports a processing error (REQ-002-PRS-F010). Rules that don't end
    within `timeout` from `started`, and a worker that dies, raise `_saxon.WorkerError`."""
    scenario = _scenarios()[name]
    return _run(data, scenario.stylesheets, scenario.levels, name, opened, timeout, started)


def _run(
    data: bytes,
    stylesheets: tuple[str, ...],
    levels: dict[str, Flag],
    name: str,
    opened: Opened,
    timeout: float,
    started: float,
) -> list[Finding]:
    """The findings of `stylesheets`, with KoSIT's `levels`; where they fail on the invoice,
    `HAFL-RULES`, which names the rules as `name`."""
    try:
        reports = _saxon.transform(data, *stylesheets, timeout=timeout, started=started)
    except _saxon.TransformError as error:
        return [
            Finding(
                rule="HAFL-RULES",
                flag="fatal",
                location=opened.reading.root.path,
                text=f"the rules of {name} fail on this invoice: {error}",
            )
        ]
    findings: list[Finding] = []
    for report in reports:
        findings.extend(_findings(parse(report), levels))
    return findings


def rule_set(opened: Opened, tree: _Element | None) -> tuple[str, Finding | None]:
    """The name of KoSIT's scenario for the invoice, as KoSIT's validator chooses it
    (REQ-002-PRS-F003), and, where its BT-24 names no profile or more than one, CEN's rules with
    the `HAFL-PROFILE` finding (REQ-002-PRS-F004). `tree` is the invoice's from `_xsd.tree`."""
    pieces, wholes = _as_written(opened, tree)
    names = list(
        dict.fromkeys(
            name
            for (document, identifier), name in _RULE_SETS.items()
            if document == opened.document
            and identifier in (wholes if (document, identifier) in _BY_WHOLE_TEXT else pieces)
        )
    )
    names = [name for name in names if name not in _FACTUR_X] or names
    if len(names) == 1:
        return names[0], None
    return _RULE_SETS[opened.document, _EN16931], _no_profile(opened, pieces, wholes, names)


def _as_written(opened: Opened, tree: _Element | None) -> tuple[list[str], list[str]]:
    """The text nodes of every BT-24 element, exactly as written, in order, and the whole text of
    each, as KoSIT's scenarios compare them (REQ-002-PRS-F003). lxml's tree keeps the comments and
    processing instructions that split a text node; ElementTree's, which serves where libxml2
    can't parse the invoice, leaves them out."""
    root = opened.reading.root.element if tree is None else tree
    elements = root.findall(_SPECIFICATIONS[opened.document], opened.reading.namespaces)
    pieces = [
        text
        for element in elements
        for text in (element.text, *(child.tail for child in element))
        if text
    ]
    return pieces, ["".join(element.itertext()) for element in elements]


def _no_profile(opened: Opened, pieces: list[str], wholes: list[str], names: list[str]) -> Finding:
    """`HAFL-PROFILE` (REQ-002-PRS-F004, REQ-002-PRS-F010): BT-24's whole text, of each element,
    and its pieces where they differ, and the rule sets it names where it names more than one.
    Located at the BT-24 that reading takes, or else at the first, which reading leaves out where
    it holds an element."""
    document = _DOCUMENTS[opened.document]
    if not "".join(wholes).strip(XML_WHITESPACE):
        location = opened.reading.root.path
        text = f"BT-24 is missing, so {document} names no profile"
    else:
        first = (
            opened.specification or opened.reading.root.findall(_SPECIFICATIONS[opened.document])[0]
        )
        location = first.path
        if len(wholes) == 1:
            written = f"BT-24 {quoted(wholes[0])}"
        else:
            written = f"BT-24, given {len(wholes):,} times, as {_listed(wholes)}"
        if not pieces:
            written += ", all of it inside an element,"
        elif pieces != wholes:
            written += f", in pieces {_listed(pieces)},"
        elif len(wholes) > 1:
            written += ","
        if names:
            text = (
                f"{written} names more than one profile Haflinger has rules for in {document},"
                f" with the rule sets {_listed(names)}"
            )
        else:
            text = f"{written} names no profile Haflinger has rules for in {document}"
    return Finding(
        rule="HAFL-PROFILE",
        flag="warning",
        location=location,
        text=f"{text}; checked with CEN's EN 16931 rules only, not the profile's own rules",
    )


def _listed(values: list[str]) -> str:
    """`'a'`, `'a' and 'b'`, `'a', 'b' and 'c'`, each shortened as `quoted` does, and of more
    than `_MAX_PIECES`, the first and how many more."""
    shown = [quoted(value) for value in values[:_MAX_PIECES]]
    if len(values) > _MAX_PIECES:
        shown.append(f"{len(values) - _MAX_PIECES:,} more")
    return " and ".join([", ".join(shown[:-1]), shown[-1]] if len(shown) > 1 else shown)


def _findings(report: Element, levels: dict[str, Flag]) -> list[Finding]:
    """The failed assertions and successful reports of an SVRL report. KoSIT's level replaces a
    rule's flag; a flag Haflinger doesn't know counts as `error`, so that it still makes the
    invoice invalid."""
    findings: list[Finding] = []
    for element in report.iter():
        if element.tag not in (f"{_SVRL}failed-assert", f"{_SVRL}successful-report"):
            continue
        rule = element.get("id", "")
        findings.append(
            Finding(
                rule=rule,
                flag=levels.get(rule) or _FLAGS.get(element.get("flag", ""), "error"),
                location=element.get("location", ""),
                text=" ".join("".join(element.itertext()).split()),
            )
        )
    return findings


@cache
def _scenarios() -> dict[str, _Scenario]:
    """The rule sets by name: KoSIT's scenarios with their XML Schema, stylesheets and levels, and
    the Factur-X profiles with FeRD's XML Schema and Schematron."""
    n = _SCENARIOS_NAMESPACE
    root = parse((_saxon.ARTEFACTS / _CONFIGURATION / "scenarios.xml").read_bytes())
    factur_x = {
        name: _Scenario(schema=_FACTUR_X_SCHEMAS[name], stylesheets=(schematron,), levels={})
        for name, (schematron, _) in _FACTUR_X.items()
    }
    schema, schematron = _FACTUR_X_EN16931
    factur_x[FACTUR_X_EN16931] = _Scenario(schema=schema, stylesheets=(schematron,), levels={})
    return factur_x | {
        scenario.findtext(f"{n}name", ""): _Scenario(
            schema=f"{_CONFIGURATION}/"
            + scenario.findtext(f"{n}validateWithXmlSchema/{n}resource/{n}location", ""),
            stylesheets=tuple(
                f"{_CONFIGURATION}/{location.text}"
                for location in scenario.findall(
                    f"{n}validateWithSchematron/{n}resource/{n}location"
                )
            ),
            levels={
                rule: _FLAGS[level.get("level", "")]
                for level in scenario.iter(f"{n}customLevel")
                for rule in (level.text or "").split()
            },
        )
        for scenario in root.findall(f"{n}scenario")
    }
