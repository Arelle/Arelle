"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import os
from collections import Counter
from operator import attrgetter
from typing import TYPE_CHECKING

from arelle import XbrlConst, XmlUtil
from arelle.ModelObject import ModelObject
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText

ARCROLE_GROUP_DETECT_STR = "*detect*"


def titleFromUri(arcrole: str) -> str:
    return os.path.basename(arcrole).title()


def baseSetArcroleLabel(arcrole: str) -> str:  # with sort char in first position
    match arcrole:
        case "XBRL-dimensions":
            return _("1Dimension")
        case "XBRL-formulae":
            return _("1Formula")
        case "Table-rendering":
            return _("1Rendering")
        case XbrlConst.parentChild:
            return _("1Presentation")
        case XbrlConst.summationItem | XbrlConst.summationItem11:
            return _("1Calculation")
        case XbrlConst.widerNarrower:
            return "1Anchoring"
        case _:
            return "2" + titleFromUri(arcrole)


def labelroleLabel(role: str) -> str:  # with sort char in first position
    match role:
        case XbrlConst.standardLabel:
            return _("1Standard Label")
        case XbrlConst.conceptNameLabelRole:
            return _("0Name")
        case _:
            return "3" + titleFromUri(role)


def baseSetArcroles(modelXbrl: ModelXbrl):
    # returns sorted list of tuples of arcrole basename and uri
    return sorted(
        set((baseSetArcroleLabel(b[0]), b[0]) for b in modelXbrl.baseSets.keys())
    )


def labelroles(modelXbrl: ModelXbrl, includeConceptName=False) -> list[tuple[str, str]]:
    # returns sorted list of tuples of arcrole basename and uri
    allRoles: set[str] = (
        (modelXbrl.labelroles | {XbrlConst.conceptNameLabelRole})
        if includeConceptName
        else modelXbrl.labelroles
    )
    return sorted((labelroleLabel(r), r) for r in allRoles if r is not None)


# clean references for viewability
def viewReferences(concept):
    return ", ".join(
        ref.viewText()
        for refrel in concept.modelXbrl.relationshipSet(
            XbrlConst.conceptReference
        ).fromModelObject(concept)
        if (ref := refrel.toModelObject) is not None
    )


def referenceURI(concept):
    return next(
        (
            XmlUtil.text(resourceElt)
            for refrel in concept.modelXbrl.relationshipSet(
                XbrlConst.conceptReference
            ).fromModelObject(concept)
            if (ref := refrel.toModelObject) is not None
            for resourceElt in ref.iter()
            if isinstance(resourceElt, ModelObject) and resourceElt.localName == "URI"
        ),
        None,
    )


def groupRelationshipSet(modelXbrl, arcrole, linkrole, linkqname, arcqname):
    if isinstance(arcrole, (list, tuple)):  # (group-name, [arcroles])
        arcroles = arcrole[1]
        relationshipSet = ModelRelationshipSet(
            modelXbrl, arcroles[0], linkrole, linkqname, arcqname
        )
        relationshipSet.modelRelationships.extend(
            rel
            for arc in arcroles[1:]
            if arc != ARCROLE_GROUP_DETECT_STR
            if (rels := modelXbrl.relationshipSet(arc, linkrole, linkqname, arcqname))
            for rel in rels.modelRelationships
        )
        relationshipSet.modelRelationships.sort(key=attrgetter("order"))
    else:
        relationshipSet = modelXbrl.relationshipSet(
            arcrole, linkrole, linkqname, arcqname
        )
    return relationshipSet


def groupRelationshipLabel(arcrole):
    if isinstance(arcrole, (list, tuple)):  # (group-name, [arcroles])
        arcroleName = arcrole[0]
    else:
        arcroleName = baseSetArcroleLabel(arcrole)[1:]
    return arcroleName


def sortCountExpected(expected):
    if isinstance(expected, list):
        return [
            s if qty == 1 else f"{s} ({qty})"
            for s, qty in sorted((str(e), qty) for e, qty in Counter(expected).items())
        ]
    return expected
