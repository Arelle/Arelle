'''
Created on Feb 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
import xml.dom.minidom, os, re
from arelle import (XbrlConst, XmlUtil)
from arelle.ModelValue import (qname, dateTime, DATE, DATETIME, DATEUNION, anyURI)

UNKNOWN = 0
INVALID = 1
NONE = 2
VALID = 3 # values >= VALID are valid
VALID_ID = 4

normalizeWhitespacePattern = re.compile(r"\s+")

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
    if entryModelDocument.xmlRootElement.get(XbrlConst.xsi, "schemaLocation") is not None:
        ns = None
        for entry in entryModelDocument.xmlRootElement.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation").split():
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
            modelXbrl.error("xmlschema:error",
                    str(error),
                    modelDocument=instDoc)

def validate(modelXbrl, elt, recurse=True, attrQname=None):
    # attrQname can be provided for attributes that are global and LAX
    if not hasattr(elt,"xValid"):
        text = XmlUtil.text(elt)
        qnElt = qname(elt)
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        if modelConcept is not None:
            type = modelConcept.type
            baseXsdType = modelConcept.baseXsdType
            isNillable = modelConcept.isNillable
            if len(text) == 0 and modelConcept.default is not None:
                text = modelConcept.default
        elif qnElt == XbrlConst.qnXbrldiExplicitMember: # not in DTS
            baseXsdType = "QName"
            type = None
            isNillable = False
        else:
            baseXsdType = None
            type = None
            isNillable = False
        if attrQname is None:
            validateValue(modelXbrl, elt, None, baseXsdType, text, isNillable)
            if type is not None:
                definedAttributes = type.attributes
            presentAttributes = set()
        if not hasattr(elt, "xAttributes"):
            elt.xAttributes = {}
        # validate attributes
        # find missing attributes for default values
        for attrTag, attrValue in elt.items():
            qn = qname(attrTag)
            baseXsdAttrType = None
            if attrQname is not None: # validate all attributes and element
                if attrQname != qn:
                    continue
            elif type is not None:
                presentAttributes.add(qn)
                if qn in definedAttributes: # look for concept-type-specific attribute definition
                    baseXsdAttrType = definedAttributes[qn].baseXsdType
            if baseXsdAttrType is None: # look for global attribute definition
                attrObject = modelXbrl.qnameAttributes.get(qn)
                if attrObject is not None:
                    baseXsdAttrType = attrObject.baseXsdType
                elif attrTag == "{http://xbrl.org/2006/xbrldi}dimension": # some fallbacks?
                    baseXsdAttrType = "QName"
            validateValue(modelXbrl, elt, attrTag, baseXsdAttrType, attrValue)
        if type is not None and attrQname is None:
            missingAttributes = type.requiredAttributeQnames - presentAttributes
            if missingAttributes:
                modelXbrl.error("xmlSchema:attributesRequired",
                    _("Element %(element)s type %(typeName)s missing required attributes: %(attributes)s"),
                    modelObject=elt,
                    element=elt.elementQname,
                    typeName=baseXsdType,
                    attributes=','.join(str(a) for a in missingAttributes))
    if recurse:
        for child in elt.getchildren():
            validate(modelXbrl, child)

def validateValue(modelXbrl, elt, attrTag, baseXsdType, value, isNillable=False):
    if baseXsdType:
        try:
            if len(value) == 0 and not isNillable and baseXsdType not in ("anyType", "string", "normalizedString", "token", "NMTOKEN"):
                raise ValueError("missing value for not nillable element")
            xValid = VALID
            if baseXsdType == "string":
                xValue = sValue = value
            elif baseXsdType == "normalizedString":
                xValue = value.strip()
                sValue = value
            elif baseXsdType in ("token","language","NMTOKEN","Name","NCName","IDREF","ENTITY"):
                xValue = normalizeWhitespacePattern.sub(' ', value.strip())
                sValue = value
            elif baseXsdType == "ID":
                xValue = value.strip()
                sValue = value
                xValid = VALID_ID
            elif baseXsdType == "anyURI":
                xValue = anyURI(value.strip())
                sValue = value
            elif not value: # rest of types get None if nil/empty value
                xValue = sValue = None
            elif baseXsdType in ("decimal", "float", "double"):
                xValue = sValue = float(value)
            elif baseXsdType in ("integer",):
                xValue = sValue = int(value)
            elif baseXsdType == "boolean":
                if value in ("true", "1"):  
                    xValue = sValue = True
                elif value in ("false", "0"): 
                    xValue = sValue = False
                else: raise ValueError
            elif baseXsdType == "QName":
                xValue = qname(elt, value, castException=ValueError)
                sValue = value
            elif baseXsdType in ("XBRLI_DECIMALSUNION", "XBRLI_PRECISIONUNION"):
                xValue = value if value == "INF" else int(value)
                sValue = value
            elif baseXsdType == "XBRLI_DATEUNION":
                xValue = dateTime(value, type=DATEUNION, castException=ValueError)
                sValue = value
            elif baseXsdType == "dateTime":
                xValue = dateTime(value, type=DATETIME, castException=ValueError)
                sValue = value
            elif baseXsdType == "date":
                xValue = dateTime(value, type=DATE, castException=ValueError)
                sValue = value
            else:
                xValue = value
                sValue = value
        except ValueError:
            if attrTag:
                modelXbrl.error("xmlSchema:valueError",
                    _("Element %(element)s attribute %(attribute)s type %(typeName)s value error: %(value)s"),
                    modelObject=elt,
                    element=elt.elementQname,
                    attribute=XmlUtil.clarkNotationToPrefixedName(elt,attrTag,isAttribute=True),
                    typeName=baseXsdType,
                    value=value)
            else:
                modelXbrl.error("xmlSchema:valueError",
                    _("Element %(element)s type %(typeName)s value error: %(value)s"),
                    modelObject=elt,
                    element=elt.elementQname,
                    typeName=baseXsdType,
                    value=value)
            xValue = None
            sValue = value
            xValid = INVALID
    else:
        xValue = sValue = None
        xValid = UNKNOWN
    if attrTag:
        elt.xAttributes[attrTag] = (xValid, xValue, sValue)
    else:
        elt.xValid = xValid
        elt.xValue = xValue
        elt.sValue = sValue
