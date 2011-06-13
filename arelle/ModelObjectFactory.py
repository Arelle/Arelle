'''
Created on Jun 10, 2011
Refactored on Jun 11, 2011 to ModelDtsObject, ModelInstanceObject, ModelTestcaseObject

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle.ModelObject import ModelObject

elementSubstitutionModelClass = {
    None: ModelObject}

from lxml import etree
from arelle import XbrlConst
from arelle.ModelValue import qname
from arelle.ModelDtsObject import (ModelConcept, ModelAttribute, ModelType, ModelEnumeration,
                                   ModelRoleType, ModelLocator, ModelLink)
from arelle.ModelTestcaseObject import ModelTestcaseVariation

def parser(modelXbrl):
    parser = etree.XMLParser()
    parser.set_element_class_lookup(ModelObjectClassLookup(modelXbrl))
    return parser

class ModelObjectClassLookup(etree.CustomElementClassLookup):
    def __init__(self, modelXbrl):
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

