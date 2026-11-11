"""Findings: failed rules of a validation, and the problems Haflinger itself reports (REQ-002)."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

type Flag = Literal["fatal", "error", "warning", "information"]


@dataclass(frozen=True, kw_only=True)
class Finding:
    """One finding (REQ-002-PRS-F002). Haflinger's own rules start with `HAFL-`
    (REQ-002-PRS-F010)."""

    rule: str
    flag: Flag
    location: str
    text: str


# The flags that make an invoice invalid (REQ-002-PRS-F002).
INVALID: frozenset[Flag] = frozenset({"fatal", "error"})


def is_valid(findings: Iterable[Finding]) -> bool:
    """Whether `validate`'s findings leave their invoice valid: none has the flag `fatal` or
    `error` (REQ-002-PRS-F002)."""
    return not any(finding.flag in INVALID for finding in findings)
