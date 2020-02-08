'''
Created on January 5, 2020

Filer Guidelines: ESMA_ESEF Manula 2019.pdf

@author: Mark V Systems Limited
(c) Copyright 2020 Mark V Systems Limited, All rights reserved.
'''
from .Const import standardTaxonomyURIs

# check if a modelDocument URI is an extension URI
def isExtension(val, modelObject):
    uri = modelObject.modelDocument.uri
    return (uri.startswith(val.modelXbrl.uriDir) or
            not any(uri.startswith(standardTaxonomyURI) for standardTaxonomyURI in standardTaxonomyURIs))

    
