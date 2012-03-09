'''
Created on Feb 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
import os, re
from arelle import XbrlConst, XmlUtil
from arelle.ModelValue import qname, dateTime, DATE, DATETIME, DATEUNION, anyURI
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle import UrlUtil
validateElementSequence = None  #dynamic import to break dependency loops
modelGroupCompositorTitle = None
ModelInlineFact = None

UNKNOWN = 0
INVALID = 1
NONE = 2
VALID = 3 # values >= VALID are valid
VALID_ID = 4

normalizeWhitespacePattern = re.compile(r"\s")
collapseWhitespacePattern = re.compile(r"\s+")
languagePattern = re.compile("[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$")
NCNamePattern = re.compile("^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                            r"[_\-\." 
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")
namePattern = re.compile("^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                            r"[_\-\.:" 
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")
NMTOKENPattern = re.compile(r"[_\-\.:" 
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]+$")
lexicalPatterns = {
    "duration": re.compile("-?P((([0-9]+Y([0-9]+M)?([0-9]+D)?|([0-9]+M)([0-9]+D)?|([0-9]+D))(T(([0-9]+H)([0-9]+M)?([0-9]+(\.[0-9]+)?S)?|([0-9]+M)([0-9]+(\.[0-9]+)?S)?|([0-9]+(\.[0-9]+)?S)))?)|(T(([0-9]+H)([0-9]+M)?([0-9]+(\.[0-9]+)?S)?|([0-9]+M)([0-9]+(\.[0-9]+)?S)?|([0-9]+(\.[0-9]+)?S))))$"),
    "gYearMonth": re.compile(r"-?([1-9][0-9]{3,}|0[0-9]{3})-(0[1-9]|1[0-2])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gYear": re.compile(r"-?([1-9][0-9]{3,}|0[0-9]{3})(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gMonthDay": re.compile(r"--(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gDay": re.compile(r"---(0[1-9]|[12][0-9]|3[01])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gMonth": re.compile(r"--(0[1-9]|1[0-2])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"), 
    "language": re.compile(r"[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$"),   
    }

baseXsdTypePatterns = {
                "Name": namePattern,
                "language": languagePattern,
                "NMTOKEN": NMTOKENPattern,
                "NCName": NCNamePattern,
                "ID": NCNamePattern,
                "IDREF": NCNamePattern,
                "ENTITY": NCNamePattern,                
            }
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

    '''    
    for mdlSchemaDoc in entryDocument.referencesDocument.keys():
        if (mdlSchemaDoc.type == ModelDocument.Type.SCHEMA and 
            mdlSchemaDoc.targetNamespace not in importedNamespaces):
            # actual file won't pass through properly, fake with table reference
            imports.append('<xsd:import namespace="{0}" schemaLocation="file:///__{1}"/>'.format(
                mdlSchemaDoc.targetNamespace, len(importedFilepaths)))
            importedNamespaces.add(mdlSchemaDoc.targetNamespace)
            importedFilepaths.append(mdlSchemaDoc.filepath)
    '''    

    def importReferences(referencingDocument):
        for mdlSchemaDoc in referencingDocument.referencesDocument.keys():
            if (mdlSchemaDoc.type == ModelDocument.Type.SCHEMA and 
                mdlSchemaDoc.targetNamespace not in importedNamespaces):
                importedNamespaces.add(mdlSchemaDoc.targetNamespace)
                importReferences(mdlSchemaDoc)  # do dependencies first
                # actual file won't pass through properly, fake with table reference
                imports.append('<xsd:import namespace="{0}" schemaLocation="file:///__{1}"/>'.format(
                    mdlSchemaDoc.targetNamespace, len(importedFilepaths)))
                importedFilepaths.append(mdlSchemaDoc.filepath)
    importReferences(entryDocument)
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
    schemaXml = '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n{0}</xsd:schema>\n'.format(
                   '\n'.join(imports))
    # trace schema files referenced
    with open("c:\\temp\\test.xml", "w") as fh:
        fh.write(schemaXml)
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
    
predefinedAttributeTypes = {
    qname("{http://www.w3.org/XML/1998/namespace}xml:lang"):("language",None),
    qname("{http://www.w3.org/XML/1998/namespace}xml:space"):("NCName",{"enumeration":{"default","preserve"}})}

def xhtmlValidate(modelXbrl, elt):
    from lxml.etree import DTD, XMLSyntaxError
    # copy xhtml elements to fresh tree
    with open(os.path.join(modelXbrl.modelManager.cntlr.configDir, "xhtml1-strict-ix.dtd")) as fh:
        dtd = DTD(fh)
    try:
        if not dtd.validate( XmlUtil.ixToXhtml(elt) ):
            modelXbrl.error("xmlDTD:error",
                _("%(element)s error %(error)s"),
                modelObject=elt, element=elt.localName.title(),
                error=', '.join(e.message for e in dtd.error_log.filter_from_errors()))
    except XMLSyntaxError as err:
        modelXbrl.error("xmlDTD:error",
            _("%(element)s error %(error)s"),
            modelObject=elt, element=elt.localName.title(), error=dtd.error_log.filter_from_errors())

def validate(modelXbrl, elt, recurse=True, attrQname=None, ixFacts=False):
    global ModelInlineFact
    if ModelInlineFact is None:
        from arelle.ModelInstanceObject import ModelInlineFact
    isIxFact = isinstance(elt, ModelInlineFact)

    # attrQname can be provided for attributes that are global and LAX
    if not hasattr(elt,"xValid") and (not isIxFact or ixFacts):
        text = elt.elementText
        qnElt = elt.qname if ixFacts and isIxFact else qname(elt)
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        facets = None
        if modelConcept is not None:
            isNillable = modelConcept.isNillable
            type = modelConcept.type
            if modelConcept.isAbstract:
                baseXsdType = "noContent"
            else:
                baseXsdType = modelConcept.baseXsdType
                facets = modelConcept.facets
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
        isNil = isNillable and elt.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true"
        if attrQname is None:
            validateValue(modelXbrl, elt, None, baseXsdType, text, isNillable, facets)
            if type is not None:
                definedAttributes = type.attributes
            else:
                definedAttributes = {}
            presentAttributes = set()
        if not hasattr(elt, "xAttributes"):
            elt.xAttributes = {}
        # validate attributes
        # find missing attributes for default values
        for attrTag, attrValue in elt.items():
            qn = qname(attrTag, noPrefixIsNoNamespace=True)
            baseXsdAttrType = None
            facets = None
            if attrQname is not None: # validate all attributes and element
                if attrQname != qn:
                    continue
            elif type is not None:
                presentAttributes.add(qn)
                if qn in definedAttributes: # look for concept-type-specific attribute definition
                    modelAttr = definedAttributes[qn]
                elif qn.namespaceURI:   # may be a globally defined attribute
                    modelAttr = modelXbrl.qnameAttributes.get(qn)
                else:
                    modelAttr = None
                if modelAttr is not None:
                    baseXsdAttrType = modelAttr.baseXsdType
                    facets = modelAttr.facets
            if baseXsdAttrType is None: # look for global attribute definition
                attrObject = modelXbrl.qnameAttributes.get(qn)
                if attrObject is not None:
                    baseXsdAttrType = attrObject.baseXsdType
                    facets = attrObject.facets
                elif attrTag == "{http://xbrl.org/2006/xbrldi}dimension": # some fallbacks?
                    baseXsdAttrType = "QName"
                elif attrTag == "id":
                    baseXsdAttrType = "ID"
                elif elt.namespaceURI == "http://www.w3.org/2001/XMLSchema":
                    if attrTag in {"type", "ref", "base", "refer", "itemType"}:
                        baseXsdAttrType = "QName"
                    elif attrTag in {"name"}:
                        baseXsdAttrType = "NCName"
                    elif attrTag in {"default", "fixed", "form"}:
                        baseXsdAttrType = "string"
                elif qn in predefinedAttributeTypes:
                    baseXsdAttrType, facets = predefinedAttributeTypes[qn]
            validateValue(modelXbrl, elt, attrTag, baseXsdAttrType, attrValue, facets=facets)
        if type is not None:
            if attrQname is None:
                missingAttributes = type.requiredAttributeQnames - presentAttributes
                if missingAttributes:
                    modelXbrl.error("xmlSchema:attributesRequired",
                        _("Element %(element)s type %(typeName)s missing required attributes: %(attributes)s"),
                        modelObject=elt,
                        element=qnElt,
                        typeName=baseXsdType,
                        attributes=','.join(str(a) for a in missingAttributes))
                # add default attribute values
                for attrQname in (type.defaultAttributeQnames - presentAttributes):
                    modelAttr = type.attributes[attrQname]
                    validateValue(modelXbrl, elt, attrQname.clarkNotation, modelAttr.baseXsdType, modelAttr.default, facets=modelAttr.facets)
            if recurse:
                global validateElementSequence, modelGroupCompositorTitle
                if validateElementSequence is None:
                    from arelle.XmlValidateParticles import validateElementSequence, modelGroupCompositorTitle
                try:
                    childElts = elt.modelTupleFacts if ixFacts and isIxFact else list(elt)
                    if isNil:
                        if childElts and any(True for e in childElts if isinstance(e, ModelObject)) or elt.text:
                            modelXbrl.error("xmlSchema:nilElementHasContent",
                                _("Element %(element)s is nil but has contents"),
                                modelObject=elt,
                                element=qnElt)
                    else:
                        errResult = validateElementSequence(modelXbrl, type, childElts)
                        if errResult is not None and errResult[2]:
                            iElt, occured, errDesc, errArgs = errResult
                            errElt = childElts[iElt] if iElt < len(childElts) else elt
                            errArgs["modelObject"] = errElt
                            errArgs["element"] = errElt.qname
                            errArgs["parentElement"] = elt.qname
                            if "compositor" in errArgs:  # compositor is an object, provide friendly string
                                errArgs["compositor"] = modelGroupCompositorTitle(errArgs["compositor"])
                            modelXbrl.error(*errDesc,**errArgs)
                    recurse = False # cancel child element validation below
                except AttributeError as ex:
                    pass
    if recurse: # if there is no complex or simple type (such as xbrli:measure) then this code is used
        for child in (elt.modelTupleFacts if ixFacts and isIxFact else elt):
            if isinstance(child, ModelObject):
                validate(modelXbrl, child, recurse, attrQname, ixFacts)

def validateValue(modelXbrl, elt, attrTag, baseXsdType, value, isNillable=False, facets=None):
    if baseXsdType:
        try:
            if (len(value) == 0 and
                not attrTag is None and 
                not isNillable and 
                baseXsdType not in ("anyType", "string", "normalizedString", "token", "NMTOKEN", "anyURI", "noContent")):
                raise ValueError("missing value for not nillable element")
            xValid = VALID
            whitespaceReplace = (baseXsdType == "normalizedString")
            whitespaceCollapse = (not whitespaceReplace and baseXsdType != "string")
            pattern = baseXsdTypePatterns.get(baseXsdType)
            if facets:
                if "pattern" in facets:
                    pattern = facets["pattern"]
                    # note multiple patterns are or'ed togetner, which isn't yet implemented!
                if "whiteSpace" in facets:
                    whitespaceReplace, whitespaceCollapse = {"preserve":(False,False), "replace":(True,False), "collapse":(False,True)}
            if whitespaceReplace:
                value = normalizeWhitespacePattern.sub(' ', value)
            elif whitespaceCollapse:
                value = collapseWhitespacePattern.sub(' ', value.strip())
            if pattern is not None and pattern.match(value) is None:
                    raise ValueError("pattern facet " + facets["pattern"].pattern if facets and "pattern" in facets else "pattern mismatch")
            if facets:
                if "enumeration" in facets and value not in facets["enumeration"]:
                    raise ValueError("is not in {1}".format(value, facets["enumeration"]))
                if "length" in facets and len(value) != facets["length"]:
                    raise ValueError("length {0}, expected {1}".format(len(value), facets["length"]))
                if "minLength" in facets and len(value) < facets["minLength"]:
                    raise ValueError("length {0}, minLength {1}".format(len(value), facets["minLength"]))
                if "maxLength" in facets and len(value) > facets["maxLength"]:
                    raise ValueError("length {0}, maxLength {1}".format(len(value), facets["maxLength"]))
            if baseXsdType == "noContent":
                if len(value) > 0 and not value.isspace():
                    raise ValueError("value content not permitted")
                xValue = sValue = None
            elif baseXsdType in {"string", "normalizedString", "language", "token", "NMTOKEN","Name","NCName","IDREF","ENTITY"}:
                xValue = sValue = value
            elif baseXsdType == "ID":
                xValue = sValue = value
                xValid = VALID_ID
            elif baseXsdType == "anyURI":
                xValue = anyURI(value)
                sValue = value
                if xValue and not UrlUtil.isValid(xValue):  # allow empty strings to be valid anyURIs
                    raise ValueError("invalid anyURI value")
            elif not value: # rest of types get None if nil/empty value
                xValue = sValue = None
            elif baseXsdType in ("decimal", "float", "double"):
                xValue = sValue = float(value)
                if facets:
                    if "totalDigits" in facets and len(value.replace(".","")) > facets["totalDigits"]:
                        raise ValueError("totalDigits facet {0}".format(facets["totalDigits"]))
                    if "fractionDigits" in facets and ( '.' in value and
                        len(value[value.index('.') + 1:]) > facets["fractionDigits"]):
                        raise ValueError("fraction digits facet {0}".format(facets["fractionDigits"]))
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
                ''' not sure here, how are explicitDimensions validated, but bad units not?
                if xValue.namespaceURI in modelXbrl.namespaceDocs:
                    if (xValue not in modelXbrl.qnameConcepts and 
                        xValue not in modelXbrl.qnameTypes and
                        xValue not in modelXbrl.qnameAttributes and
                        xValue not in modelXbrl.qnameAttributeGroups):
                        raise ValueError("qname not defined " + str(xValue))
                '''
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
            elif baseXsdType == "regex-pattern":
                # for facet compiling
                try:
                    xValue = re.compile(value + "$") # must match whole string
                    sValue = value
                except Exception as err:
                    raise ValueError(err)
            else:
                if baseXsdType in lexicalPatterns:
                    match = lexicalPatterns[baseXsdType].match(value)
                    if match is None:
                        raise ValueError("lexical pattern mismatch")
                    if baseXsdType == "gMonthDay":
                        month, day, zSign, zHrMin, zHr, zMin = match.groups()
                        if int(day) > {2:29, 4:30, 6:30, 9:30, 11:30, 1:31, 3:31, 5:31, 7:31, 8:31, 10:31, 12:31}[int(month)]:
                            raise ValueError("invalid day {0} for month {1}".format(day, month))
                xValue = value
                sValue = value
        except ValueError as err:
            if ModelInlineFact is not None and isinstance(elt, ModelInlineFact):
                errElt = "{0} fact {1}".format(elt.elementQname, elt.qname)
            else:
                errElt = elt.elementQname
            if attrTag:
                modelXbrl.error("xmlSchema:valueError",
                    _("Element %(element)s attribute %(attribute)s type %(typeName)s value error: %(value)s, %(error)s"),
                    modelObject=elt,
                    element=errElt,
                    attribute=XmlUtil.clarkNotationToPrefixedName(elt,attrTag,isAttribute=True),
                    typeName=baseXsdType,
                    value=value,
                    error=err)
            else:
                modelXbrl.error("xmlSchema:valueError",
                    _("Element %(element)s type %(typeName)s value error: %(value)s, %(error)s"),
                    modelObject=elt,
                    element=errElt,
                    typeName=baseXsdType,
                    value=value,
                    error=err)
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

def validateFacet(typeElt, facetElt):
    facetName = facetElt.localName
    value = facetElt.get("value")
    if facetName in ("length", "minLength", "maxLength", "totalDigits", "fractionDigits"):
        baseXsdType = "integer"
        facets = None
    elif facetName in ("maxInclusive", "maxExclusive", "minExclusive"):
        baseXsdType = typeElt.baseXsdType
        facets = None
    elif facetName == "whiteSpace":
        baseXsdType = "string"
        facets = {"enumeration": {"replace","preserve","collapse"}}
    elif facetName == "pattern":
        baseXsdType = "regex-pattern"
        facets = None
    else:
        baseXsdType = "string"
        facets = None
    validateValue(typeElt.modelXbrl, facetElt, None, baseXsdType, value, facets=facets)
    if facetElt.xValid == VALID:
        return facetElt.xValue
    return None
