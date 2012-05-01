'''
Created on Mar 21, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XmlUtil, XbrlConst)
from arelle.ModelObject import ModelObject

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
            
