"""The seller and the buyer: the business term IDs of their fields, which reading, writing and
findings name (REQ-001-PRS-F001), and what reading them shares across the syntaxes
(REQ-003-PRS-F002)."""

from dataclasses import dataclass

from haflinger._xml import Node, first_of, none_if_empty
from haflinger.model import Contact, Identifier

# The seller's tax registration identifier; the buyer has no such term.
TAX_REGISTRATION = "BT-32"


@dataclass(frozen=True, kw_only=True)
class PartyTerms:
    """The IDs of one party's group and of the terms each `Party` field holds for it, and how
    the two parties differ: only the seller has a tax registration identifier and shares its
    identifiers' element with the bank assigned creditor identifier; the buyer has one
    identifier."""

    party: str
    name: str
    trading_name: str
    identifier: str
    legal_registration_id: str
    vat_id: str
    electronic_address: str
    address: str
    address_line_1: str
    address_line_2: str
    address_line_3: str
    city: str
    post_code: str
    country_subdivision: str
    country_code: str
    contact: str
    contact_point: str
    telephone: str
    email: str
    tax_registration: str | None
    creditor_identifier: str | None
    one_identifier: bool


SELLER = PartyTerms(
    party="BG-4",
    name="BT-27",
    trading_name="BT-28",
    identifier="BT-29",
    legal_registration_id="BT-30",
    vat_id="BT-31",
    electronic_address="BT-34",
    address="BG-5",
    address_line_1="BT-35",
    address_line_2="BT-36",
    address_line_3="BT-162",
    city="BT-37",
    post_code="BT-38",
    country_subdivision="BT-39",
    country_code="BT-40",
    contact="BG-6",
    contact_point="BT-41",
    telephone="BT-42",
    email="BT-43",
    tax_registration=TAX_REGISTRATION,
    creditor_identifier="BT-90",
    one_identifier=False,
)
BUYER = PartyTerms(
    party="BG-7",
    name="BT-44",
    trading_name="BT-45",
    identifier="BT-46",
    legal_registration_id="BT-47",
    vat_id="BT-48",
    electronic_address="BT-49",
    address="BG-8",
    address_line_1="BT-50",
    address_line_2="BT-51",
    address_line_3="BT-163",
    city="BT-52",
    post_code="BT-53",
    country_subdivision="BT-54",
    country_code="BT-55",
    contact="BG-9",
    contact_point="BT-56",
    telephone="BT-57",
    email="BT-58",
    tax_registration=None,
    creditor_identifier=None,
    one_identifier=True,
)


def identifiers(
    nodes: list[Node], terms: PartyTerms, scheme: str = "schemeID"
) -> tuple[Identifier, ...]:
    """The identifiers `nodes` hold, with their scheme in the attribute `scheme`, in the model's
    order: those without a scheme first, then those with one, each in document order. The
    buyer has one: the first with a scheme, or else the first without; the others are left out
    with a finding."""
    nodes = sorted(nodes, key=lambda node: node.attribute(scheme) is not None)
    if terms.one_identifier:
        first = first_of(
            sorted(nodes, key=lambda node: node.attribute(scheme) is None), terms.identifier
        )
        nodes = [] if first is None else [first]
    return tuple(Identifier(value=node.value, scheme=node.attribute(scheme)) for node in nodes)


def identifier(node: Node | None, scheme: str = "schemeID") -> Identifier | None:
    """The electronic address `node` holds, with its scheme in the attribute `scheme`."""
    return None if node is None else Identifier(value=node.value, scheme=node.attribute(scheme))


def contact(point: str | None, telephone: str | None, email: str | None) -> Contact | None:
    """The contact of these terms; None where it holds none of them."""
    return none_if_empty(Contact(point=point, telephone=telephone, email=email))
