'''
Created on January 5, 2020

Filer Guidelines: ESMA_ESEF Manula 2019.pdf

@author: Mark V Systems Limited
(c) Copyright 2020 Mark V Systems Limited, All rights reserved.
'''
from .Const import standardTaxonomyURIs, esefTaxonomyNamespaceURIs

# check if a modelDocument URI is an extension URI (document URI)
# also works on a uri passed in as well as modelObject
def isExtension(val, modelObject):
    if modelObject is None:
        return False
    if isinstance(modelObject, str):
        uri = modelObject
    else:
        uri = modelObject.modelDocument.uri
    return (uri.startswith(val.modelXbrl.uriDir) or
            not any(uri.startswith(standardTaxonomyURI) for standardTaxonomyURI in standardTaxonomyURIs))

# check if in core esef taxonomy (based on namespace URI)
def isInEsefTaxonomy(val, modelObject):
    if modelObject is None:
        return False
    ns = modelObject.qname.namespaceURI
    return (any(ns.startswith(esefNsPrefix) for esefNsPrefix in esefTaxonomyNamespaceURIs))
    
