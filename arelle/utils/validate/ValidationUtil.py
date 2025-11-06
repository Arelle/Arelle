"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Generator, Iterable

from lxml.etree import _Element

from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText

_: TypeGetText


def etreeIterWithDepth(
        node: ModelObject | _Element,
        depth: int = 0,
) -> Generator[tuple[ModelObject | _Element, int], None, None]:
    yield node, depth
    for child in node.iterchildren():
        yield from etreeIterWithDepth(child, depth + 1)


def hasPresentationalConceptsWithFacts(
        modelXbrl: ModelXbrl,
        roleUris: Iterable[str],
        memberQnameFilter: set[QName] | None = None,
) -> bool:
    """
    Returns True if any concepts used in the presentation network of the role URIs have been tagged with facts.
    This DOES NOT check if the facts are dimensionally valid against hypercubes defined in the roles.
    """
    roleRelSet = modelXbrl.relationshipSet(XbrlConst.parentChild, tuple(roleUris))
    concepts = set(roleRelSet.fromModelObjects().keys()) | set(roleRelSet.toModelObjects().keys())
    for concept in concepts:
        if not isinstance(concept, ModelConcept):
            continue
        if concept.qname is None:
            continue
        if concept.isAbstract:
            continue
        for fact in modelXbrl.factsByQname.get(concept.qname, set()):
            if memberQnameFilter is None:
                return True
            if fact.context is not None:
                for dimValue in fact.context.qnameDims.values():
                    if dimValue.memberQname in memberQnameFilter:
                        return True
    return False
