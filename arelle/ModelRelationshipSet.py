'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''

# initialize object from loaded linkbases
from collections import defaultdict
from arelle import ModelDtsObject, XbrlConst, XmlUtil, ModelValue
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelResource
import os

def create(modelXbrl, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
    return ModelRelationshipSet(modelXbrl, arcrole, linkrole, linkqname, arcqname, includeProhibits)

def ineffectiveArcs(baseSetModelLinks, arcrole, arcqname=None):
    relationships = defaultdict(list)
    for modelLink in baseSetModelLinks:
        for linkChild in modelLink:
            if (isinstance(linkChild,ModelObject) and 
                linkChild.get("{http://www.w3.org/1999/xlink}type") == "arc" and 
                arcrole == linkChild.get("{http://www.w3.org/1999/xlink}arcrole") and
                (arcqname is None or arcqname == linkChild)):
                fromLabel = linkChild.get("{http://www.w3.org/1999/xlink}from")
                toLabel = linkChild.get("{http://www.w3.org/1999/xlink}to")
                for fromResource in modelLink.labeledResources[fromLabel]:
                    for toResource in modelLink.labeledResources[toLabel]:
                        modelRel = ModelDtsObject.ModelRelationship(modelLink.modelDocument, linkChild, fromResource.dereference(), toResource.dereference())
                        relationships[modelRel.equivalenceKey].append(modelRel)
    # determine ineffective relationships
    ineffectives = []
    for equivalenceKey, relationship in relationships.items():
        #sort by priority, prohibited
        equivalentRels = [(modelRel.priority, modelRel.prohibitedUseSortKey, i)
                          for i, modelRel in enumerate(relationship)]
        priorRel = None
        for rel in sorted( equivalentRels ):
            if rel[1] == 2: # this rel is prohibited
                if priorRel is None:
                    ineffective = relationship[rel[2]]
                    ineffective.ineffectivity = _("prohibited arc (priority {0}) has no other arc to prohibit").format(
                                               ineffective.priority)
                    ineffectives.append(ineffective) # this rel ineffective
                elif priorRel[1] == 2: # prior rel is prohibited
                    ineffective = relationship[priorRel[2]]
                    effective = relationship[rel[2]]
                    ineffective.ineffectivity = _("prohibited arc (priority {0}, {1} - {2}) has an equivalent prohibited arc (priority {3}, {4} - {5})\n").format(
                                             ineffective.priority, ineffective.modelDocument.basename, ineffective.sourceline,
                                             effective.priority, effective.modelDocument.basename, effective.sourceline)
                    ineffectives.append(ineffective)
            else:
                if priorRel is not None and priorRel[1] != 2:
                    ineffective = relationship[priorRel[2]]
                    effective = relationship[rel[2]]
                    ineffective.ineffectivity = _("arc (priority {0}, {1} - {2}) is ineffective due to equivalent arc (priority {3}, {4} - {5})\n").format(
                                             ineffective.priority, ineffective.modelDocument.basename, ineffective.sourceline,
                                             effective.priority, effective.modelDocument.basename, effective.sourceline)
                    ineffectives.append(ineffective) # prior ineffective
            priorRel = rel
    return ineffectives

def baseSetArcroles(modelXbrl):
    # returns sorted list of tuples of arcrole basename and uri
    return sorted(set((XbrlConst.baseSetArcroleLabel(b[0]),b[0]) for b in modelXbrl.baseSets.keys()))
    
def labelroles(modelXbrl, includeConceptName=False):
    # returns sorted list of tuples of arcrole basename and uri
    return sorted(set((XbrlConst.labelroleLabel(r),r) 
                        for r in (modelXbrl.labelroles | ({XbrlConst.conceptNameLabelRole} if includeConceptName else set()))
                        if r is not None))
    
class ModelRelationshipSet:
    __slots__ = ("isChanged", "modelXbrl", "arcrole", "linkrole", "linkqname", "arcqname",
                 "modelRelationshipsFrom", "modelRelationshipsTo", "modelConceptRoots", "modellinkRoleUris",
                 "modelRelationships", "_testHintedLabelLinkrole")
    
    # arcrole can either be a single string or a tuple or frozenset of strings
    def __init__(self, modelXbrl, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
        self.isChanged = False
        self.modelXbrl = modelXbrl
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname

        relationshipSetKey = (arcrole, linkrole, linkqname, arcqname, includeProhibits) 
            
        # base sets does not care about the #includeProhibits
        if not isinstance(arcrole,(tuple,frozenset)):
            modelLinks = self.modelXbrl.baseSets.get((arcrole, linkrole, linkqname, arcqname), [])
        else: # arcrole is a set of arcroles
            modelLinks = []
            for ar in arcrole:
                modelLinks.extend(self.modelXbrl.baseSets.get((ar, linkrole, linkqname, arcqname), []))
            
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
                    linkChildQname = linkChild
                    if isFootnoteRel:
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
                          (arcqname is None or arcqname == linkChildQname) and 
                          (linkqname is None or linkqname == linkEltQname)):
                        arcs.append(linkChild)
                        
            # build network
            for arcElement in arcs:
                fromLabel = arcElement.get("{http://www.w3.org/1999/xlink}from")
                toLabel = arcElement.get("{http://www.w3.org/1999/xlink}to")
                for fromResource in modelLink.labeledResources[fromLabel]:
                    for toResource in modelLink.labeledResources[toLabel]:
                        if isinstance(fromResource,ModelResource) and isinstance(toResource,ModelResource):
                            modelRel = ModelDtsObject.ModelRelationship(modelLink.modelDocument, arcElement, fromResource.dereference(), toResource.dereference())
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
            if includeProhibits or not modelRel.isProhibited:
                orderRels[modelRel.order].append(modelRel)
        self.modelRelationships = [modelRel
                                   for order in sorted(orderRels.keys())
                                   for modelRel in orderRels[order]]
        modelXbrl.relationshipSets[relationshipSetKey] = self
        
    def clear(self):
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
        if self.modellinkRoleUris is None:
            self.modellinkRoleUris = set(modelRel.linkrole for modelRel in self.modelRelationships)
        return self.modellinkRoleUris
    
    def loadModelRelationshipsFrom(self):
        if self.modelRelationshipsFrom is None:
            self.modelRelationshipsFrom = defaultdict(list)
            for modelRel in self.modelRelationships:
                fromModelObject = modelRel.fromModelObject
                if fromModelObject is not None: # none if concepts failed to load
                    self.modelRelationshipsFrom[fromModelObject].append(modelRel)
    
    def loadModelRelationshipsTo(self):
        if self.modelRelationshipsTo is None:
            self.modelRelationshipsTo = defaultdict(list)
            for modelRel in self.modelRelationships:
                toModelObject = modelRel.toModelObject
                if toModelObject is not None:   # none if concepts failed to load
                    self.modelRelationshipsTo[toModelObject].append(modelRel)
                
    def fromModelObjects(self):
        self.loadModelRelationshipsFrom()
        return self.modelRelationshipsFrom

    def fromModelObject(self, modelFrom):
        if self.modelRelationshipsFrom is None:
            self.loadModelRelationshipsFrom()
        return self.modelRelationshipsFrom.get(modelFrom, [])
    
    def toModelObjects(self):
        self.loadModelRelationshipsTo()
        return self.modelRelationshipsTo

    def toModelObject(self, modelTo):
        if self.modelRelationshipsTo is None:
            self.loadModelRelationshipsTo()
        return self.modelRelationshipsTo.get(modelTo, [])
        
    def fromToModelObjects(self, modelFrom, modelTo):
        self.loadModelRelationshipsFrom()
        return [rel for rel in self.fromModelObject(modelFrom) if rel.toModelObject is modelTo]

    @property
    def rootConcepts(self):
        if self.modelConceptRoots is None:
            self.loadModelRelationshipsFrom()
            self.loadModelRelationshipsTo()
            self.modelConceptRoots = [modelRelFrom
                                      for modelRelFrom in self.modelRelationshipsFrom.keys()
                                      if modelRelFrom not in self.modelRelationshipsTo]
        return self.modelConceptRoots
    
    # if modelFrom and modelTo are provided determine that they have specified relationship
    # if only modelFrom, determine that there are relationships present of specified axis
    def isRelated(self, modelFrom, axis, modelTo=None, visited=None): # either model concept or qname
        if isinstance(modelFrom,ModelValue.QName): modelFrom = self.modelXbrl.qnameConcepts[modelFrom]
        if isinstance(modelTo,ModelValue.QName): modelTo = self.modelXbrl.qnameConcepts[modelTo]
        if axis.endswith("self") and (modelTo is None or modelFrom == modelTo):
            return True
        isDescendantAxis = "descendant" in axis
        if axis.startswith("sibling"):  # allow sibling-or-self or sibling-or-descendant
            for modelRel in self.toModelObject(modelFrom):
                modelFrom = modelRel.fromModelObject # assumes only one parent
                break
            axis = axis[7:] # remove sibling, else recursion will loop
        for modelRel in self.fromModelObject(modelFrom):
            toConcept = modelRel.toModelObject
            if modelTo is None or modelTo == toConcept:
                return True
            if isDescendantAxis:
                if visited is None: visited = set()
                if toConcept not in visited:
                    visited.add(toConcept)
                    if self.isRelated(toConcept, axis, modelTo, visited):
                        return True
                    visited.discard(toConcept)
        return False
    
    def label(self, modelFrom, role, lang, returnMultiple=False, returnText=True, linkroleHint=None):
        shorterLangInLabel = longerLangInLabel = None
        shorterLangLabels = longerLangLabels = None
        langLabels = []
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
                    if role == label.role:
                        linkrole = modelLabelRel.linkrole
                        if linkrole == linkroleHint:
                            labelsHintedLink.append(modelLabelRel)
                        elif linkrole == XbrlConst.defaultLinkRole:
                            labelsDefaultLink.append(modelLabelRel)
                        else:
                            labelsOtherLinks.append(modelLabelRel)
                labels = (labelsHintedLink or labelsDefaultLink or labelsOtherLinks)
        if len(labels) > 1: # order by priority (ignoring equivalence of relationships)
            labels.sort(key=lambda rel: rel.priority, reverse=True)
        for modelLabelRel in labels:
            label = modelLabelRel.toModelObject
            if role == label.role:
                labelLang = label.xmlLang
                text = label.text if returnText else label
                if lang is None or len(lang) == 0 or lang == labelLang:
                    langLabels.append(text)
                    if not returnMultiple:
                        break
                elif labelLang.startswith(lang):
                    if not longerLangInLabel or len(longerLangInLabel) > len(labelLang):
                        longerLangInLabel = labelLang
                        longerLangLabels = [text,]
                    else:
                        longerLangLabels.append(text)
                elif lang.startswith(labelLang):
                    if not shorterLangInLabel or len(shorterLangInLabel) < len(labelLang):
                        shorterLangInLabel = labelLang
                        shorterLangLabels = [text,]
                    else:
                        shorterLangLabels.append(text)
        if langLabels:
            if returnMultiple: return langLabels
            else: return langLabels[0]
        if shorterLangLabels:  # more general has preference
            if returnMultiple: return shorterLangLabels
            else: return shorterLangLabels[0]
        if longerLangLabels:
            if returnMultiple: return longerLangLabels
            else: return longerLangLabels[0]
        return None
