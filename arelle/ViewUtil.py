'''
See COPYRIGHT.md for copyright information.
'''
from arelle import (XmlUtil, XbrlConst)
from __future__ import annotations

import os
from arelle.typing import TypeGetText
from typing import TYPE_CHECKING

from arelle import XbrlConst, XmlUtil
from arelle.ModelObject import ModelObject
from arelle.ModelRelationshipSet import ModelRelationshipSet

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText

ARCROLE_GROUP_DETECT_STR = "*detect*"


def titleFromUri(arcrole: str) -> str:
    return os.path.basename(arcrole).title()


def baseSetArcroleLabel(arcrole: str) -> str:  # with sort char in first position
    if arcrole == "XBRL-dimensions":
        return _("1Dimension")
    elif arcrole == "XBRL-formulae":
        return _("1Formula")
    elif arcrole == "Table-rendering":
        return _("1Rendering")
    elif arcrole == XbrlConst.parentChild:
        return _("1Presentation")
    elif arcrole in (XbrlConst.summationItem, XbrlConst.summationItem11):
        return _("1Calculation")
    elif arcrole == XbrlConst.widerNarrower:
        return "1Anchoring"
    else:
        return "2" + titleFromUri(arcrole)


def labelroleLabel(role: str) -> str:  # with sort char in first position
    if role == XbrlConst.standardLabel:
        return _("1Standard Label")
    elif role == XbrlConst.conceptNameLabelRole:
        return _("0Name")
    return "3" + titleFromUri(role)


def baseSetArcroles(modelXbrl: ModelXbrl):
    # returns sorted list of tuples of arcrole basename and uri
    return sorted(
        set((baseSetArcroleLabel(b[0]), b[0]) for b in modelXbrl.baseSets.keys())
    )


def labelroles(modelXbrl, includeConceptName=False):
    # returns sorted list of tuples of arcrole basename and uri
    return sorted(set((XbrlConst.labelroleLabel(r),r)
                        for r in (modelXbrl.labelroles | ({XbrlConst.conceptNameLabelRole} if includeConceptName else set()))
                        if r is not None))


# clean references for viewability
def viewReferences(concept):
    references = []
    for refrel in concept.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(concept):
        ref = refrel.toModelObject
        if ref is not None:
            references.append(ref.viewText())
    return ", ".join(references)

def referenceURI(concept):
    for refrel in concept.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(concept):
        ref = refrel.toModelObject
        if ref is not None:
            for resourceElt in ref.iter():
                if isinstance(resourceElt,ModelObject) and resourceElt.localName == "URI":
                    return XmlUtil.text(resourceElt)
    return None

def groupRelationshipSet(modelXbrl, arcrole, linkrole, linkqname, arcqname):
    if isinstance(arcrole, (list,tuple)): # (group-name, [arcroles])
        arcroles = arcrole[1]
        relationshipSet = ModelRelationshipSet(modelXbrl, arcroles[0], linkrole, linkqname, arcqname)
        for arcrole in arcroles[1:]:
            if arcrole != ARCROLE_GROUP_DETECT_STR:
                rels = modelXbrl.relationshipSet(arcrole, linkrole, linkqname, arcqname)
                if rels:
                    relationshipSet.modelRelationships.extend(rels.modelRelationships)
        relationshipSet.modelRelationships.sort(key=lambda rel: rel.order)
    else:
        relationshipSet = modelXbrl.relationshipSet(arcrole, linkrole, linkqname, arcqname)
    return relationshipSet

def groupRelationshipLabel(arcrole):
    if isinstance(arcrole, (list,tuple)): # (group-name, [arcroles])
        arcroleName = arcrole[0]
    else:
        arcroleName = baseSetArcroleLabel(arcrole)[1:]
    return arcroleName

def sortCountExpected(expected):
    if isinstance(expected, list):
        _expected = {}
        for e in expected:
            _expected[e] = _expected.get(e, 0) + 1
        return [str(e) if qty == 1 else "{} ({})".format(e,qty)
                for e, qty in sorted(_expected.items(), key=lambda i:str(i[0]))]
    return expected
