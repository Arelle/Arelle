from dataclasses import dataclass

from arelle.ModelValue import QName


@dataclass(frozen=True)
class ExpectedErrorConstraint:
    qname: QName | None
    pattern: str | None
    min: int | None
    max: int | None
    warnings: bool
    errors: bool
