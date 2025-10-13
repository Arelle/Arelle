'''
See COPYRIGHT.md for copyright information.

Saves OIM Taxonomy Model into json, cbor and Excel

'''
import os
from .XbrlTaxonomyModule import XbrlTaxonomyModule

def saveModel(cntlr, txmyMdl, filename):
    # nested sheet for each OrderedSet of XbrlTaxonomyModule object
    modelComponentObjects = [
        propName
        for propName, propType in objClass.propertyNameTypes()
        if isinstance(propType, GenericAlias) and propType.__origin__ == OrderedSet]
    
    
    