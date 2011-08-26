'''
Created on Feb 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
import xml.dom.minidom, os, re
from arelle import XbrlConst, XmlUtil
from arelle.ModelValue import qname, dateTime, DATE, DATETIME, DATEUNION, anyURI
from arelle.ModelObject import ModelAttribute
from arelle import UrlUtil

UNKNOWN = 0
INVALID = 1
NONE = 2
VALID = 3 # values >= VALID are valid
VALID_ID = 4

normalizeWhitespacePattern = re.compile(r"\s+")

def schemaValidate(modelXbrl):
    class schemaResolver(etree.Resolver):
        def resolve(self, url, id, context): 
            if url.startswith("file:///__"):
                url = importedFilepaths[int(url[10:])]
            filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(url)
            return self.resolve_filename(filepath, context)
          
    entryDocument = modelXbrl.modelDocument
    # test of schema validation using lxml (trial experiment, commented out for production use)
    from arelle import ModelDocument
    imports = []
    importedNamespaces = set()
    importedFilepaths = []
    for mdlSchemaDoc in entryDocument.referencesDocument.keys():
        if (mdlSchemaDoc.type == ModelDocument.Type.SCHEMA and 
            mdlSchemaDoc.targetNamespace not in importedNamespaces):
            # actual file won't pass through properly, fake with table reference
            imports.append('<xsd:import namespace="{0}" schemaLocation="file:///__{1}"/>'.format(
                mdlSchemaDoc.targetNamespace, len(importedFilepaths)))
            importedNamespaces.add(mdlSchemaDoc.targetNamespace)
            importedFilepaths.append(mdlSchemaDoc.filepath)
    # add schemas used in xml validation but not DTS discovered
    for mdlDoc in modelXbrl.urlDocs.values():
        if mdlDoc.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.LINKBASE):
            schemaLocation = mdlDoc.xmlRootElement.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
            if schemaLocation:
                ns = None
                for entry in schemaLocation.split():
                    if ns is None:
                        ns = entry
                    else:
                        if ns not in importedNamespaces:
                            imports.append('<xsd:import namespace="{0}" schemaLocation="file:///__{1}"/>'.format(
                                ns, len(importedFilepaths)))
                            importedNamespaces.add(ns)
                            importedFilepaths.append(entry)
                        ns = None
    schemaXml = '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">{0}</xsd:schema>'.format(
                   ''.join(imports))
    modelXbrl.modelManager.showStatus(_("lxml validator loading xml schema"))
    schema_root = etree.XML(schemaXml)
    import time
    startedAt = time.time()
    parser = etree.XMLParser()
    parser.resolvers.add(schemaResolver())
    schemaDoc = etree.fromstring(schemaXml, parser=parser, base_url=entryDocument.filepath+"-dummy-import.xsd")
    schema = etree.XMLSchema(schemaDoc)
    from arelle.Locale import format_string
    modelXbrl.info("info:lxmlSchemaValidator", format_string(modelXbrl.modelManager.locale, 
                                 _("schema loaded in %.2f secs"), 
                                        time.time() - startedAt))
    modelXbrl.modelManager.showStatus(_("lxml schema validating"))
    # check instance documents and linkbases (sort for inst doc before linkbases, and in file name order)
    for mdlDoc in sorted(modelXbrl.urlDocs.values(), key=lambda mdlDoc: (-mdlDoc.type, mdlDoc.filepath)):
        if mdlDoc.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.LINKBASE):
            startedAt = time.time()
            docXmlTree = etree.parse(mdlDoc.filepath)
            modelXbrl.info("info:lxmlSchemaValidator", format_string(modelXbrl.modelManager.locale, 
                                                _("schema validated in %.3f secs"), 
                                                time.time() - startedAt),
                                                modelDocument=mdlDoc)
            if not schema.validate(docXmlTree):
                for error in schema.error_log:
                    modelXbrl.error("lxmlSchema:{0}".format(error.type_name.lower()),
                            error.message,
                            modelDocument=mdlDoc,
                            sourceLine=error.line)
    modelXbrl.modelManager.showStatus(_("lxml validation done"), clearAfter=3000)

def validate(modelXbrl, elt, recurse=True, attrQname=None):
    # attrQname can be provided for attributes that are global and LAX
    if not hasattr(elt,"xValid"):
        text = XmlUtil.textNotStripped(elt)
        qnElt = qname(elt)
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        if modelConcept is not None:
            if modelConcept.isAbstract:
                baseXsdType = "noContent"
            else:
                type = modelConcept.type
                baseXsdType = modelConcept.baseXsdType
                isNillable = modelConcept.isNillable
                if len(text) == 0 and modelConcept.default is not None:
                    text = modelConcept.default
        elif qnElt == XbrlConst.qnXbrldiExplicitMember: # not in DTS
            baseXsdType = "QName"
            type = None
            isNillable = False
        elif qnElt == XbrlConst.qnXbrldiTypedMember: # not in DTS
            baseXsdType = "noContent"
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
                elif attrTag == "id":
                    baseXsdAttrType = "ID"
                elif elt.namespaceURI == "http://www.w3.org/2001/XMLSchema":
                    if attrTag in ("type", "ref", "base", "refer", "itemType"):
                        baseXsdAttrType = "QName"
                    elif attrTag in ("name"):
                        baseXsdAttrType = "NCName"
                    elif attrTag in ("default", "fixed", "form"):
                        baseXsdAttrType = "string"
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
            if len(value) == 0 and not isNillable and baseXsdType not in ("anyType", "string", "normalizedString", "token", "NMTOKEN", "noContent"):
                raise ValueError("missing value for not nillable element")
            xValid = VALID
            if baseXsdType == "noContent":
                if len(value) > 0 and not value.isspace():
                    raise ValueError("value content not permitted")
                xValue = sValue = None
            elif baseXsdType == "string":
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
                if not UrlUtil.isValid(xValue):
                    raise ValueError("invalid anyURI value")
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
                xValue = sValue = value if value == "INF" else int(value)
            elif baseXsdType in ("XBRLI_NONZERODECIMAL"):
                xValue = sValue = int(value)
                if xValue == 0:
                    raise ValueError("invalid value")
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
        elt.xAttributes[attrTag] = ModelAttribute(elt, attrTag, xValid, xValue, sValue, value)
    else:
        elt.xValid = xValid
        elt.xValue = xValue
        elt.sValue = sValue
