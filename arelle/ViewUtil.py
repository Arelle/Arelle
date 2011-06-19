'''
Created on Mar 21, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ModelObject, XmlUtil, XbrlConst)

# clean references for viewability
def viewReferences(concept):
    references = []
    for refrel in concept.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(concept):
        ref = refrel.toModelObject
        if ref is not None:
            references.append(ref.viewText())
    return ", ".join(references)
