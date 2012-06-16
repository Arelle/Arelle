'''
Created on Mar 21, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XmlUtil, XbrlConst)
from arelle.ModelObject import ModelObject
from arelle.ModelRelationshipSet import ModelRelationshipSet

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
            if arcrole != XbrlConst.arcroleGroupDetect:
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
        arcroleName = XbrlConst.baseSetArcroleLabel(arcrole)[1:]
    return arcroleName