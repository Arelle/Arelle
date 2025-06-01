'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

# initialize object from loaded linkbases
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from arelle import Locale, XbrlConst, ModelValue
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelRelationship, ModelResource
from arelle.PrototypeDtsObject import LocPrototype, PrototypeObject
from arelle.PythonUtil import OrderedSet
from arelle.XbrlConst import consecutiveArcrole
import sys

USING_EQUIVALENCE_KEY = sys.intern(str("using_equivalence_key")) # indicates hash entry replaced with keyed entry
NoneType = type(None)

def create(modelXbrl, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False) -> ModelRelationshipSet:
    return ModelRelationshipSet(modelXbrl, arcrole, linkrole, linkqname, arcqname, includeProhibits)

def ineffectiveArcs(baseSetModelLinks, arcrole, arcqname=None):
    hashEquivalentRels = defaultdict(list)
    for modelLink in baseSetModelLinks:
        for linkChild in modelLink:
            if (isinstance(linkChild,(ModelObject,PrototypeObject)) and
                linkChild.get("{http://www.w3.org/1999/xlink}type") == "arc" and
                arcrole == linkChild.get("{http://www.w3.org/1999/xlink}arcrole") and
                (arcqname is None or arcqname == linkChild)):
                fromLabel = linkChild.get("{http://www.w3.org/1999/xlink}from")
                toLabel = linkChild.get("{http://www.w3.org/1999/xlink}to")
                for fromResource in modelLink.labeledResources[fromLabel]:
                    for toResource in modelLink.labeledResources[toLabel]:
                        modelRel = ModelRelationship(modelLink.modelDocument, linkChild, fromResource.dereference(), toResource.dereference())
                        hashEquivalentRels[modelRel.equivalenceHash].append(modelRel)
    # determine ineffective relationships
    ineffectives = []
    keyEquivalentRels = defaultdict(list)
    for hashEquivRelList in hashEquivalentRels.values():
        # separate into relationships that are key-equivalent
        if len(hashEquivRelList) == 1:
            if hashEquivRelList[0].prohibitedUseSortKey == 2:
                ineffective = hashEquivRelList[0]
                ineffective.ineffectivity = _("prohibited arc (priority {0}) has no other arc to prohibit").format(
                                           ineffective.priority)
                ineffectives.append(ineffective) # this rel ineffective
        else:
            # index by equivalenceKey instead
            for modelRel in hashEquivRelList:
                keyEquivalentRels[modelRel.equivalenceKey].append(modelRel)
            for keyEquivRelList in keyEquivalentRels.values():
                #sort by priority, prohibited
                equivalentRels = [(modelRel.priority, modelRel.prohibitedUseSortKey, i)
                                  for i, modelRel in enumerate(keyEquivRelList)]
                priorRel = None
                for rel in sorted( equivalentRels ):
                    if rel[1] == 2: # this rel is prohibited
                        if priorRel is None:
                            ineffective = keyEquivRelList[rel[2]]
                            ineffective.ineffectivity = _("prohibited arc (priority {0}) has no other arc to prohibit").format(
                                                       ineffective.priority)
                            ineffectives.append(ineffective) # this rel ineffective
                        elif priorRel[1] == 2: # prior rel is prohibited
                            ineffective = keyEquivRelList[priorRel[2]]
                            effective = keyEquivRelList[rel[2]]
                            ineffective.ineffectivity = _("prohibited arc (priority {0}, {1} - {2}) has an equivalent prohibited arc (priority {3}, {4} - {5})\n").format(
                                                     ineffective.priority, ineffective.modelDocument.basename, ineffective.sourceline,
                                                     effective.priority, effective.modelDocument.basename, effective.sourceline)
                            ineffectives.append(ineffective)
                    else:
                        if priorRel is not None and priorRel[1] != 2:
                            ineffective = keyEquivRelList[priorRel[2]]
                            effective = keyEquivRelList[rel[2]]
                            ineffective.ineffectivity = _("arc (priority {0}, {1} - {2}) is ineffective due to equivalent arc (priority {3}, {4} - {5})\n").format(
                                                     ineffective.priority, ineffective.modelDocument.basename, ineffective.sourceline,
                                                     effective.priority, effective.modelDocument.basename, effective.sourceline)
                            ineffectives.append(ineffective) # prior ineffective
                    priorRel = rel
            keyEquivalentRels.clear()
    return ineffectives

def baseSetArcroles(modelXbrl):
    # returns sorted list of tuples of arcrole basename and uri
    return sorted(set((XbrlConst.baseSetArcroleLabel(b[0]),b[0]) for b in modelXbrl.baseSets.keys()))

def labelroles(modelXbrl, includeConceptName=False):
    # returns sorted list of tuples of arcrole basename and uri
    return sorted(set((XbrlConst.labelroleLabel(r),r)
                        for r in (modelXbrl.labelroles | ({XbrlConst.conceptNameLabelRole} if includeConceptName else set()))
                        if r is not None))

def baseSetRelationship(arcElement):
    modelXbrl = arcElement.modelXbrl
    arcrole = arcElement.get("{http://www.w3.org/1999/xlink}arcrole")
    ELR = arcElement.getparent().get("{http://www.w3.org/1999/xlink}role")
    for rel in modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
        if rel.arcElement == arcElement:
            return rel
    return None

# For internal use by ModelRelationshipSet.label.
@dataclass
class _LangLabels:
    lang: str
    labels: list[ModelObject] | list[str] # list[str] if returnText

class ModelRelationshipSet:
    __slots__ = ("isChanged", "modelXbrl", "arcrole", "linkrole", "linkqname", "arcqname",
                 "modelRelationshipsFrom", "modelRelationshipsTo", "modelConceptRoots", "modellinkRoleUris",
                 "modelRelationships", "_testHintedLabelLinkrole")

    modelRelationshipsFrom: dict[Any, list[ModelRelationship]] | None
    modelRelationshipsTo: dict[Any, list[ModelRelationship]] | None

    # arcrole can either be a single string or a tuple or frozenset of strings
    def __init__(self, modelXbrl, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
        self.isChanged = False
        self.modelXbrl = modelXbrl
        self.arcrole = arcrole # may be str, None, tuple or frozenset
        self.linkrole = linkrole # may be str, None, tuple or frozenset
        self.linkqname = linkqname
        self.arcqname = arcqname

        relationshipSetKey = (arcrole, linkrole, linkqname, arcqname, includeProhibits)

        # base sets does not care about the #includeProhibits
        if isinstance(arcrole, (str, NoneType)) and isinstance(linkrole, (str, NoneType)):
            modelLinks = self.modelXbrl.baseSets.get((arcrole, linkrole, linkqname, arcqname), [])
        else: # arcrole is a set of arcroles
            modelLinks = []
            for ar in (arcrole,) if isinstance(arcrole, (str, NoneType)) else arcrole:
                for lr in (linkrole,) if isinstance(linkrole, (str, NoneType)) else linkrole:
                    modelLinks.extend(self.modelXbrl.baseSets.get((ar, lr, linkqname, arcqname), []))

        # gather arcs
        relationships = {}
        isDimensionRel =  self.arcrole == "XBRL-dimensions" # all dimensional relationship arcroles
        isFormulaRel =  self.arcrole == "XBRL-formulae" # all formula relationship arcroles
        isTableRenderingRel = self.arcrole == "Table-rendering"
        isFootnoteRel =  self.arcrole == "XBRL-footnotes" # all footnote relationship arcroles
        if not isinstance(arcrole,(tuple,frozenset)):
            arcrole = (arcrole,)

        for modelLink in modelLinks:
            arcs = []
            linkEltQname = modelLink.qname
            for linkChild in modelLink:
                linkChildArcrole = linkChild.get("{http://www.w3.org/1999/xlink}arcrole")
                if linkChild.get("{http://www.w3.org/1999/xlink}type") == "arc" and linkChildArcrole:
                    if isFootnoteRel: # arcrole is fact-footnote or other custom footnote relationship
                        arcs.append(linkChild)
                    elif isDimensionRel:
                        if XbrlConst.isDimensionArcrole(linkChildArcrole):
                            arcs.append(linkChild)
                    elif isFormulaRel:
                        if XbrlConst.isFormulaArcrole(linkChildArcrole):
                            arcs.append(linkChild)
                    elif isTableRenderingRel:
                        if XbrlConst.isTableRenderingArcrole(linkChildArcrole):
                            arcs.append(linkChild)
                    elif (linkChildArcrole in arcrole and
                          (arcqname is None or arcqname == linkChild.qname) and
                          (linkqname is None or linkqname == linkEltQname)):
                        arcs.append(linkChild)

            # build network
            for arcElement in arcs:
                fromLabel = arcElement.get("{http://www.w3.org/1999/xlink}from")
                toLabel = arcElement.get("{http://www.w3.org/1999/xlink}to")
                for fromResource in modelLink.labeledResources[fromLabel]:
                    for toResource in modelLink.labeledResources[toLabel]:
                        if isinstance(fromResource,(ModelResource,LocPrototype)) and isinstance(toResource,(ModelResource,LocPrototype)):
                            modelRel = ModelRelationship(modelLink.modelDocument, arcElement, fromResource.dereference(), toResource.dereference())
                            modelRelEquivalenceHash = modelRel.equivalenceHash
                            if modelRelEquivalenceHash not in relationships:
                                relationships[modelRelEquivalenceHash] = modelRel
                            else: # use equivalenceKey instead of hash
                                otherRel = relationships[modelRelEquivalenceHash]
                                if otherRel is not USING_EQUIVALENCE_KEY: # move equivalentRel to use key instead of hasn
                                    if modelRel.isIdenticalTo(otherRel):
                                        continue # skip identical arc
                                    relationships[otherRel.equivalenceKey] = otherRel
                                    relationships[modelRelEquivalenceHash] = USING_EQUIVALENCE_KEY
                                modelRelEquivalenceKey = modelRel.equivalenceKey    # this is a complex tuple to compute, get once for below
                                if modelRelEquivalenceKey not in relationships or \
                                   modelRel.priorityOver(relationships[modelRelEquivalenceKey]):
                                    relationships[modelRelEquivalenceKey] = modelRel

        #reduce effective arcs and order relationships...
        self.modelRelationshipsFrom = None
        self.modelRelationshipsTo = None
        self.modelConceptRoots = None
        self.modellinkRoleUris = None
        orderRels = defaultdict(list)
        for modelRel in relationships.values():
            if (modelRel is not USING_EQUIVALENCE_KEY and
                (includeProhibits or not modelRel.isProhibited)):
                orderRels[modelRel.order].append(modelRel)
        self.modelRelationships = [modelRel
                                   for order in sorted(orderRels.keys())
                                   for modelRel in orderRels[order]]
        modelXbrl.relationshipSets[relationshipSetKey] = self

    def clear(self) -> None:
        # this object is slotted, clear slotted variables
        self.modelXbrl = None
        del self.modelRelationships[:]
        if self.modelRelationshipsTo is not None:
            self.modelRelationshipsTo.clear()
        if self.modelRelationshipsFrom is not None:
            self.modelRelationshipsFrom.clear()
        if self.modelConceptRoots is not None:
            del self.modelConceptRoots[:]
        self.linkqname = self.arcqname = None

    def __bool__(self):  # some modelRelationships exist
        return len(self.modelRelationships) > 0

    @property
    def linkRoleUris(self):
        # order by document appearance of linkrole, required for Table Linkbase testcase 3220 v03
        if self.modellinkRoleUris is None:
            linkroleObjSeqs = set((modelRel.linkrole, getattr(modelRel.arcElement.getparent(), "objectIndex", sys.maxsize)) for modelRel in self.modelRelationships)
            self.modellinkRoleUris = OrderedSet([lr[0] for lr in sorted(linkroleObjSeqs, key=lambda l: l[1])])
        return self.modellinkRoleUris

    def loadModelRelationshipsFrom(self) -> dict[Any, list[ModelRelationship]]:
        modelRelationshipsFrom = self.modelRelationshipsFrom
        if modelRelationshipsFrom is None:
            modelRelationshipsFrom = defaultdict(list)
            for modelRel in self.modelRelationships:
                fromModelObject = modelRel.fromModelObject
                if fromModelObject is not None: # none if concepts failed to load
                    modelRelationshipsFrom[fromModelObject].append(modelRel)
            self.modelRelationshipsFrom = modelRelationshipsFrom
        return modelRelationshipsFrom

    def loadModelRelationshipsTo(self) -> dict[Any, list[ModelRelationship]]:
        modelRelationshipsTo = self.modelRelationshipsTo
        if modelRelationshipsTo is None:
            modelRelationshipsTo = defaultdict(list)
            for modelRel in self.modelRelationships:
                toModelObject = modelRel.toModelObject
                if toModelObject is not None:   # none if concepts failed to load
                    modelRelationshipsTo[toModelObject].append(modelRel)
            self.modelRelationshipsTo = modelRelationshipsTo
        return modelRelationshipsTo

    def fromModelObjects(self) -> dict[Any, list[ModelRelationship]]:
        return self.loadModelRelationshipsFrom()

    def fromModelObject(self, modelFrom) -> list[ModelRelationship]:
        if getattr(self.modelXbrl, "isSupplementalIxdsTarget", False) and modelFrom is not None and modelFrom.modelXbrl != self.modelXbrl:
            modelFrom = self.modelXbrl.qnameConcepts.get(modelFrom.qname, None)
        return self.loadModelRelationshipsFrom().get(modelFrom, [])

    def toModelObjects(self) -> dict[Any, list[ModelRelationship]]:
        return self.loadModelRelationshipsTo()

    def toModelObject(self, modelTo) -> list[ModelRelationship]:
        if getattr(self.modelXbrl, "isSupplementalIxdsTarget", False) and modelTo is not None and modelTo.modelXbrl != self.modelXbrl:
            modelFrom = self.modelXbrl.qnameConcepts.get(modelTo.qname, None)
        return self.loadModelRelationshipsTo().get(modelTo, [])

    def fromToModelObjects(self, modelFrom, modelTo, checkBothDirections=False) -> list[ModelRelationship]:
        rels = [rel for rel in self.fromModelObject(modelFrom) if rel.toModelObject is modelTo]
        if checkBothDirections:
            rels += [rel for rel in self.fromModelObject(modelTo) if rel.toModelObject is modelFrom]
        return rels

    @property
    def rootConcepts(self):
        if self.modelConceptRoots is None:
            modelRelationshipsFrom = self.loadModelRelationshipsFrom()
            modelRelationshipsTo = self.loadModelRelationshipsTo()
            self.modelConceptRoots = [modelRelFrom
                                      for modelRelFrom, relFrom in modelRelationshipsFrom.items()
                                      if modelRelFrom not in modelRelationshipsTo or
                                      (len(relFrom) == 1 and # root-level self-looping arc
                                       len(modelRelationshipsTo[modelRelFrom]) == 1 and
                                       relFrom[0].fromModelObject == relFrom[0].toModelObject)]
        return self.modelConceptRoots

    # if modelFrom and modelTo are provided determine that they have specified relationship
    # if only modelFrom, determine that there are relationships present of specified axis
    def isRelated(self, modelFrom, axis, modelTo=None, visited=None, isDRS=False, consecutiveLinkrole=False): # either model concept or qname
        assert self.modelXbrl is not None
        if getattr(self.modelXbrl, "isSupplementalIxdsTarget", False):
            if modelFrom is not None and modelFrom.modelXbrl != self.modelXbrl:
                modelFrom = modelFrom.qname
            if modelTo is not None and modelTo.modelXbrl != self.modelXbrl:
                modelTo = modelTo.qname
        if isinstance(modelFrom,ModelValue.QName):
            modelFrom = self.modelXbrl.qnameConcepts.get(modelFrom) # fails if None
        if isinstance(modelTo,ModelValue.QName):
            modelTo = self.modelXbrl.qnameConcepts.get(modelTo)
            if modelTo is None: # note that modelTo None (not a bad QName) means to check for any relationship
                return False # if a QName and not existent then fails
        if axis.endswith("self") and (modelTo is None or modelFrom == modelTo):
            return True
        if axis.startswith("ancestor"): # could be ancestor-or-self
            assert isDRS == False # DRS is not possible
            for modelRel in self.toModelObject(modelFrom):
                toConcept = modelRel.fromModelObject
                if modelTo is None or modelTo == toConcept:
                    return True
                if visited is None: visited = set()
                if toConcept not in visited:
                    visited.add(toConcept)
                    if self.isRelated(toConcept, axis, modelTo, visited, isDRS):
                        return True
                    visited.discard(toConcept)
            return False
        isDescendantAxis = "descendant" in axis
        if axis.startswith("ancestral-"): # allow ancestral-sibling...
            if self.isRelated(modelFrom, axis[10:], modelTo): # any current-level sibling?
                return True
            if visited is None: visited = set()
            if modelFrom in visited:
                return False # prevent looping
            visited.add(modelFrom)
            isRel = any(self.isRelated(modelRel.fromModelObject, axis, modelTo, visited) # any ancestral sibling?
                        for modelRel in self.toModelObject(modelFrom))
            visited.discard(modelFrom)
            return isRel
        if axis.startswith("sibling"):  # allow sibling-or-self or sibling-or-descendant
            axis = axis[7:] # remove sibling, else recursion will loop
            return any(self.isRelated(modelRel.fromModelObject, axis, modelTo)
                       for modelRel in self.toModelObject(modelFrom))
        for modelRel in self.fromModelObject(modelFrom):
            toConcept = modelRel.toModelObject
            if modelTo is None or modelTo == toConcept:
                return True
            if isDescendantAxis:
                if visited is None: visited = set()
                if toConcept not in visited:
                    visited.add(toConcept)
                    if isDRS:
                        if (self.modelXbrl.relationshipSet(consecutiveArcrole[modelRel.arcrole],
                                                           modelRel.consecutiveLinkrole, self.linkqname, self.arcqname)
                            .isRelated(toConcept, axis, modelTo, visited, isDRS)):
                            return True
                    elif consecutiveLinkrole: # allows starting at relationship set with ELR None
                        if (self.modelXbrl.relationshipSet(modelRel.arcrole,
                                                           modelRel.consecutiveLinkrole, self.linkqname, self.arcqname)
                            .isRelated(toConcept, axis, modelTo, visited, isDRS, consecutiveLinkrole)):
                            return True
                    else:
                        if self.isRelated(toConcept, axis, modelTo, visited, isDRS):
                            return True
                    visited.discard(toConcept)
        return False

    def label(self, modelFrom, role, lang, returnMultiple=False, returnText=True, linkroleHint=None) -> str | ModelObject | list[str] | list[ModelObject] | None:
        _lang = lang.lower() if lang else lang # lang processing is case insensitive
        langLabels = []
        wildRole = role == '*'
        labels = self.fromModelObject(modelFrom)
        if linkroleHint:  # order of preference of linkroles to find label
            try:
                testHintedLinkrole = self._testHintedLabelLinkrole
            except AttributeError:
                self._testHintedLabelLinkrole = testHintedLinkrole = (len(self.linkRoleUris) > 1)
            if testHintedLinkrole:
                labelsHintedLink = []
                labelsDefaultLink = []
                labelsOtherLinks = []
                for modelLabelRel in labels:
                    label = modelLabelRel.toModelObject
                    if wildRole or role == label.role:
                        linkrole = modelLabelRel.linkrole
                        if linkrole == linkroleHint:
                            labelsHintedLink.append(modelLabelRel)
                        elif linkrole == XbrlConst.defaultLinkRole:
                            labelsDefaultLink.append(modelLabelRel)
                        else:
                            labelsOtherLinks.append(modelLabelRel)
                labels = (labelsHintedLink or labelsDefaultLink or labelsOtherLinks)
        if len(labels) > 1: # order by priority (ignoring equivalence of relationships)
            labels = sorted(labels, key=lambda rel: rel.priority, reverse=True)
        shorter: _LangLabels | None = None
        longer: _LangLabels | None = None
        regionalVariant: _LangLabels | None = None
        baseLang = _lang.partition(Locale.BCP47_LANGUAGE_REGION_SEPARATOR)[0] if _lang else None
        for modelLabelRel in labels:
            label = modelLabelRel.toModelObject
            if wildRole or role == label.role:
                labelLang = label.xmlLang # None if absent or un-declared by empty string (see xml schema)
                if labelLang:
                    labelLang = labelLang.lower() # must be case insensitive for processiing
                text = label.textValue if returnText else label
                if _lang is None or len(_lang) == 0 or _lang == labelLang:
                    langLabels.append(text)
                    if not returnMultiple:
                        break
                elif labelLang is not None:
                    if labelLang.startswith(_lang):
                        if not longer or len(longer.lang) > len(labelLang):
                            longer = _LangLabels(labelLang, [text])
                        else:
                            longer.labels.append(text)
                    elif lang.startswith(labelLang):
                        if not shorter or len(shorter.lang) < len(labelLang):
                            shorter = _LangLabels(labelLang, [text])
                        else:
                            shorter.labels.append(text)
                    elif baseLang and labelLang.startswith(baseLang):
                        if not regionalVariant:
                            regionalVariant = _LangLabels(labelLang, [text])
                        else:
                            regionalVariant.labels.append(text)
        if langLabels:
            if returnMultiple: return langLabels
            else: return langLabels[0]
        if shorter:  # more general has preference
            if returnMultiple: return shorter.labels
            else: return shorter.labels[0]
        if longer:
            if returnMultiple: return longer.labels
            else: return longer.labels[0]
        if regionalVariant:
            if returnMultiple: return regionalVariant.labels
            else: return regionalVariant.labels[0]
        return None
