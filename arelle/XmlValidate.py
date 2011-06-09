'''
Created on Feb 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
import xml.dom.minidom, os
from arelle import (XbrlConst, XmlUtil)
from arelle.ModelValue import (qname, dateTime, DATE, DATETIME)

UNKNOWN = 0
INVALID = 1
NONE = 2
VALID = 3

def xmlValidate(entryModelDocument):
    # test of schema validation using lxml (trial experiment, commented out for production use)
    modelXbrl = entryModelDocument.modelXbrl
    from arelle import ModelDocument
    imports = []
    importedNamespaces = set()
    for modelDocument in modelXbrl.urlDocs.values():
        if (modelDocument.type == ModelDocument.Type.SCHEMA and 
            modelDocument.targetNamespace not in importedNamespaces):
            imports.append('<xsd:import namespace="{0}" schemaLocation="{1}"/>'.format(
                modelDocument.targetNamespace, modelDocument.filepath.replace("\\","/")))
            importedNamespaces.add(modelDocument.targetNamespace)
    if entryModelDocument.xmlRootElement.hasAttributeNS(XbrlConst.xsi, "schemaLocation"):
        ns = None
        for entry in entryModelDocument.xmlRootElement.getAttributeNS(XbrlConst.xsi, "schemaLocation").split():
            if ns is None:
                ns = entry
            else:
                if ns not in importedNamespaces:
                    imports.append('<xsd:import namespace="{0}" schemaLocation="{1}"/>'.format(
                        ns, entry))
                    importedNamespaces.add(ns)
                ns = None
    schema_root = etree.XML(
        '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">{0}</xsd:schema>'.format(
        ''.join(imports))
        )
    import time
    startedAt = time.time()
    schema = etree.XMLSchema(schema_root)
    from arelle.Locale import format_string
    modelXbrl.modelManager.addToLog(format_string(modelXbrl.modelManager.locale, 
                                        _("schema loaded in %.2f secs"), 
                                        time.time() - startedAt))
    startedAt = time.time()
    instDoc = etree.parse(entryModelDocument.filepath)
    modelXbrl.modelManager.addToLog(format_string(modelXbrl.modelManager.locale, 
                                        _("instance parsed in %.2f secs"), 
                                        time.time() - startedAt))
    if not schema.validate(instDoc):
        for error in schema.error_log:
            modelXbrl.error(
                    str(error),
                    "err", "xmlschema:error")

def validate(modelXbrl, elt, recurse=True, attrQname=None):
    if not hasattr(elt,"xValid"):
        text = XmlUtil.text(elt)
        qnElt = qname(elt)
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        if modelConcept:
            baseXsdType = modelConcept.baseXsdType
            if len(text) == 0 and modelConcept.default is not None:
                text = modelConcept.default
        elif qnElt == XbrlConst.qnXbrldiExplicitMember: # not in DTS
            baseXsdType = "QName"
        else:
            baseXsdType = None
        if attrQname is None:
            validateNode(modelXbrl, elt, elt, baseXsdType, text)
        # validate attributes
        # find missing attributes for default values
        for i in range(len(elt.attributes)):
            attr = elt.attributes.item(i)
            attrNsURI = attr.namespaceURI
            if (attr.name not in ("xmlns") and attr.prefix != "xmlns"):
                if attrNsURI:
                    qn = qname(attrNsURI, attr.localName)
                else:
                    qn = qname(attr.localName)
                if attrQname and attrQname != qn:
                    continue
                baseXsdAttrType = None
                if modelConcept:
                    baseXsdAttrType = modelConcept.baseXsdAttrType(qn) if modelConcept else None
                if baseXsdAttrType is None:
                    attrObject = modelXbrl.qnameAttributes.get(qn)
                    if attrObject:
                        baseXsdAttrType = attrObject.baseXsdType
                    elif attr.localName == "dimension" and elt.namespaceURI == XbrlConst.xbrldi:
                        baseXsdAttrType = "QName"
                validateNode(modelXbrl, elt, attr, baseXsdAttrType, attr.value)
    if recurse:
        for child in elt.childNodes:
            if child.nodeType == 1:
                validate(modelXbrl, child)

def validateNode(modelXbrl, elt, node, baseXsdType, value):
    if baseXsdType:
        try:
            if baseXsdType in ("decimal", "float", "double"):
                node.xValue = float(value)
            elif baseXsdType in ("integer",):
                node.xValue = int(value)
            elif baseXsdType == "boolean":
                if value in ("true", "1"): node.xValue = True
                elif value in ("false", "0"): node.xValue = False
                else: raise ValueError
            elif baseXsdType == "QName":
                node.xValue = qname(elt, value, castException=ValueError)
            elif baseXsdType in ("normalizedString","token","language","NMTOKEN","Name","NCName","ID","IDREF","ENTITY"):
                node.xValue = value.strip()
            elif baseXsdType == "dateTime":
                node.xValue = dateTime(value, type=DATETIME, castException=ValueError)
            elif baseXsdType == "date":
                node.xValue = dateTime(value, type=DATE, castException=ValueError)
            else:
                node.xValue = value
            node.xValid = VALID
        except ValueError:
            if node.nodeType == 1:
                modelXbrl.error(
                    _("Element {0} type {1} value error: {2}").format(
                    elt.tagName,
                    baseXsdType,
                    value),
                    "err", "xmlSchema:valueError")
            else:
                modelXbrl.error(
                    _("Element {0} attribute {1} type {2} value error: {3}").format(
                    elt.tagName,
                    node.name,
                    baseXsdType,
                    value),
                    "err", "xmlSchema:valueError")
            node.xValue = None
            node.xValid = INVALID
    else:
        node.xValue = None
        node.xValid = UNKNOWN
