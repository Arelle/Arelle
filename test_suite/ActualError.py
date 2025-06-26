from dataclasses import dataclass

from arelle.ModelValue import QName


@dataclass(frozen=True)
class ActualError:
    qname: QName | None
    code: str
