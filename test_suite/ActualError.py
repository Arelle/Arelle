'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from dataclasses import dataclass

from arelle.ModelValue import QName


@dataclass(frozen=True)
class ActualError:
    assertions: dict[str, tuple[int, ...]]
    code: str
    qname: QName | None
