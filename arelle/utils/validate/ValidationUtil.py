"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Generator

from lxml.etree import _Element

from arelle.ModelObject import ModelObject
from arelle.typing import TypeGetText

_: TypeGetText


def etreeIterWithDepth(
        node: ModelObject | _Element,
        depth: int = 0,
) -> Generator[tuple[ModelObject | _Element, int], None, None]:
    yield node, depth
    for child in node.iterchildren():
        for n_d in etreeIterWithDepth(child, depth + 1):
            yield n_d
