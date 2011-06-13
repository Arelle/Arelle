'''
Created on Jun 10, 2011
Refactored on Jun 11, 2011 to ModelDtsObject, ModelInstanceObject, ModelTestcaseObject

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle.ModelObject import ModelObject

elementSubstitutionModelClass = {}

from lxml import etree
from arelle import XbrlConst
from arelle.ModelValue import qname
from arelle.ModelDtsObject import (ModelConcept, ModelAttribute, ModelType, ModelEnumeration,
                                   ModelRoleType, ModelLocator, ModelLink)
from arelle.ModelTestcaseObject import ModelTestcaseVariation

def parser(modelXbrl, baseUrl):
    parser = etree.XMLParser()
    parser.set_element_class_lookup(KnownNamespacesModelObjectClassLookup(modelXbrl,
                                    fallback=DiscoveringClassLookup(modelXbrl, baseUrl)))
    return parser

class KnownNamespacesModelObjectClassLookup(etree.CustomElementClassLookup):
    def __init__(self, modelXbrl, fallback=None):
        super().__init__(fallback)
        self.modelXbrl = modelXbrl
        
    def lookup(self, node_type, document, ns, ln):
        # node_type is "element", "comment", "PI", or "entity"
        if node_type == "element":
            if ns == XbrlConst.xsd:
                if ln == "element":
                    return ModelConcept
                elif ln == "attribute":
                    return ModelAttribute
                elif ln == "complexType" or ln == "simpleType":
                    return ModelType
                elif ln == "enumeration":
                    return ModelEnumeration
            elif ns == XbrlConst.link:
                if ln == "roleType" or ln == "arcroleType":
                    return ModelRoleType
            elif ln == "variation" and (
                ns is None or ns in ("http://edgar/2009/conformance",) or ns.startswith("http://xbrl.org/")):
                return ModelTestcaseVariation
            return self.modelXbrl.matchSubstitutionGroup(
                qname(ns, ln),
                elementSubstitutionModelClass)
        elif node_type == "comment":
            from arelle.ModelObject import ModelComment
            return ModelComment
        elif node_type == "PI":
            return etree.PIBase
        elif node_type == "entity":
            return etree.EntityBase

class DiscoveringClassLookup(etree.PythonElementClassLookup):
    def __init__(self, modelXbrl, baseUrl, fallback=None):
        super().__init__(fallback)
        self.modelXbrl = modelXbrl
        self.baseUrl = baseUrl
        self.discoveryAttempts = set()
        
    def lookup(self, document, proxyElement):
        # check if proxyElement's namespace is not known
        ns, sep, ln = proxyElement.tag.partition("}")
        if sep:
            ns = ns[1:]
        else:
            ln = ns
            ns = None
        if (ns and 
            ns not in self.discoveryAttempts and 
            ns not in self.modelXbrl.namespaceDocs):
            # is schema loadable?  requires a schemaLocation
            from arelle import XmlUtil, ModelDocument
            relativeUrl = XmlUtil.schemaLocation(proxyElement, ns)
            self.discoveryAttempts.add(ns)
            if relativeUrl:
                doc = ModelDocument.loadSchemalocatedSchema(self.modelXbrl, proxyElement, relativeUrl, ns, self.baseUrl)

        modelObjectClass = self.modelXbrl.matchSubstitutionGroup(
            qname(ns, ln),
            elementSubstitutionModelClass)
        
        if modelObjectClass is not None:
            return modelObjectClass
        else:
            return ModelObject
