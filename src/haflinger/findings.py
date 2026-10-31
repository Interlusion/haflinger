"""Findings: failed rules of a validation, and the problems Haflinger itself reports (REQ-002)."""

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
