'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''

# initialize object from loaded linkbases
from collections import defaultdict
from arelle import (ModelDtsObject, XbrlConst, XmlUtil, ModelValue)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelResource
import os

def create(modelXbrl, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
    return ModelRelationshipSet(modelXbrl, arcrole, linkrole, linkqname, arcqname, includeProhibits)

def ineffectiveArcs(baseSetModelLinks, arcrole, arcqname=None):
    relationships = defaultdict(list)
    for modelLink in baseSetModelLinks:
        for linkChild in modelLink.getchildren():
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
        equivalentRels = []
        i = 0
        for modelRel in relationship:
            equivalentRels.append((modelRel.priority,modelRel.prohibitedUseSortKey,i))
            i += 1
        equivalentRels.sort()
        priorRel = None
        for rel in equivalentRels:
            if rel[1] == 2: # this rel is prohibited
                if priorRel is None:
                    ineffectives.append(relationship[rel[2]]) # this rel ineffective
                elif priorRel[1] == 2: # prior rel is prohibited
                    ineffectives.append(priorRel[2])
            else:
                if priorRel is not None and \
                   priorRel[1] != 2:
                    ineffectives.append(relationship[priorRel[2]]) # prior ineffective
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
    def __init__(self, modelXbrl, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
        self.isChanged = False
        self.modelXbrl = modelXbrl
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname

        baseSetKey = (arcrole, linkrole, linkqname, arcqname) 
        relationshipSetKey = (arcrole, linkrole, linkqname, arcqname, includeProhibits) 
            
        # base sets does not care about the #includeProhibits
        if baseSetKey in self.modelXbrl.baseSets:
            modelLinks = self.modelXbrl.baseSets[baseSetKey]
        else:
            modelLinks = []
        
        # gather arcs
        relationships = {}
        isDimensionRel =  self.arcrole == "XBRL-dimensions" # all dimensional relationship arcroles
        isFormulaRel =  self.arcrole == "XBRL-formulae" # all formula relationship arcroles
        isTableRenderingRel = self.arcrole == "Table-rendering"
        isFootnoteRel =  self.arcrole == "XBRL-footnotes" # all footnote relationship arcroles
        
        for modelLink in modelLinks:
            arcs = []
            linkEltQname = modelLink.qname
            for linkChild in modelLink.getchildren():
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
                    elif arcrole == linkChildArcrole and \
                         (arcqname is None or arcqname == linkChildQname) and \
                         (linkqname is None or linkqname == linkEltQname):
                        arcs.append(linkChild)
                        
            # build network
            for arcElement in arcs:
                arcrole = arcElement.get("{http://www.w3.org/1999/xlink}arcrole")
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
        self.modelRelationships = []
        self.modelRelationshipsFrom = None
        self.modelRelationshipsTo = None
        self.modelConceptRoots = None
        self.modellinkRoleUris = None
        orderRels = defaultdict(list)
        for modelRel in relationships.values():
            if includeProhibits or not modelRel.isProhibited:
                orderRels[modelRel.order].append(modelRel)
        for order in sorted(orderRels.keys()):
            for modelRel in orderRels[order]:
                self.modelRelationships.append(modelRel)
        modelXbrl.relationshipSets[relationshipSetKey] = self
        
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
        self.loadModelRelationshipsFrom()
        return self.modelRelationshipsFrom.get(modelFrom, [])
    
    def toModelObjects(self):
        self.loadModelRelationshipsTo()
        return self.modelRelationshipsTo

    def toModelObject(self, modelTo):
        self.loadModelRelationshipsTo()
        return self.modelRelationshipsTo.get(modelTo, [])
        
    @property
    def rootConcepts(self):
        if self.modelConceptRoots is None:
            self.loadModelRelationshipsFrom()
            self.loadModelRelationshipsTo()
            self.modelConceptRoots = []
            for modelRelFrom in self.modelRelationshipsFrom.keys():
                if self.modelRelationshipsTo.get(modelRelFrom) == None and \
                    modelRelFrom not in self.modelConceptRoots:
                    self.modelConceptRoots.append(modelRelFrom)
        return self.modelConceptRoots
    
    # if modelFrom and modelTo are provided determine that they have specified relationship
    # if only modelFrom, determine that there are relationships present of specified axis
    def isRelated(self, modelFrom, axis, modelTo=None, visited=None): # either model concept or qname
        if visited is None: visited = set()
        if isinstance(modelFrom,ModelValue.QName): modelFrom = self.modelXbrl.qnameConcepts[modelFrom]
        if isinstance(modelTo,ModelValue.QName): modelTo = self.modelXbrl.qnameConcepts[modelTo]
        if axis.endswith("self") and (modelTo is None or modelFrom == modelTo):
            return True
        for modelRel in self.fromModelObject(modelFrom):
            toConcept = modelRel.toModelObject
            if modelTo is None or modelTo == toConcept:
                return True
            if axis.startswith("descendant") and toConcept not in visited:
                visited.add(toConcept)
                if self.isRelated(toConcept, axis, modelTo, visited):
                    return True
                visited.discard(toConcept)
        return False
    
    def label(self, modelFrom, role, lang, returnMultiple=False, returnText=True):
        shorterLangInLabel = longerLangInLabel = None
        shorterLangLabels = longerLangLabels = None
        langLabels = []
        for modelLabelRel in self.fromModelObject(modelFrom):
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
