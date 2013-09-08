'''
Created on Feb 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os, re
from decimal import Decimal
from arelle import XbrlConst, XmlUtil
from arelle.ModelValue import qname, dateTime, DATE, DATETIME, DATEUNION, anyURI, INVALIDixVALUE, gYearMonth, gMonthDay, gYear, gMonth, gDay
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle import UrlUtil
validateElementSequence = None  #dynamic import to break dependency loops
modelGroupCompositorTitle = None
ModelInlineValueObject = None

UNVALIDATED = 0
UNKNOWN = 1
INVALID = 2
NONE = 3
VALID = 4 # values >= VALID are valid
VALID_ID = 5
VALID_NO_CONTENT = 6 # may be a complex type with children

normalizeWhitespacePattern = re.compile(r"\s")
collapseWhitespacePattern = re.compile(r"\s+")
languagePattern = re.compile("[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$")
NCNamePattern = re.compile("^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                            r"[_\-\." 
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")
QNamePattern = re.compile("^([_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                             r"[_\-\." 
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*:)?"
                          "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
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

# patterns difficult to compile into python
xmlSchemaPatterns = {
    r"\c+": NMTOKENPattern,
    r"\i\c*": namePattern,
    r"[\i-[:]][\c-[:]]*": NCNamePattern,
    }

# patterns to replace \c and \i in names
iNameChar = "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
cNameChar = r"[_\-\.:"   "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]"

baseXsdTypePatterns = {
                "Name": namePattern,
                "language": languagePattern,
                "NMTOKEN": NMTOKENPattern,
                "NCName": NCNamePattern,
                "ID": NCNamePattern,
                "IDREF": NCNamePattern,
                "ENTITY": NCNamePattern, 
                "QName": QNamePattern,               
            }
predefinedAttributeTypes = {
    qname("{http://www.w3.org/XML/1998/namespace}xml:lang"):("language",None),
    qname("{http://www.w3.org/XML/1998/namespace}xml:space"):("NCName",{"enumeration":{"default","preserve"}})}

xAttributesSharedEmptyDict = {}

def validate(modelXbrl, elt, recurse=True, attrQname=None, ixFacts=False):
    global ModelInlineValueObject
    if ModelInlineValueObject is None:
        from arelle.ModelInstanceObject import ModelInlineValueObject
    isIxFact = isinstance(elt, ModelInlineValueObject)
    facets = None

    # attrQname can be provided for attributes that are global and LAX
    if (not hasattr(elt,"xValid") or elt.xValid == UNVALIDATED) and (not isIxFact or ixFacts):
        qnElt = elt.qname if ixFacts and isIxFact else elt.elementQname
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        if modelConcept is not None:
            isNillable = modelConcept.isNillable
            type = modelConcept.type
            if modelConcept.isAbstract:
                baseXsdType = "noContent"
            else:
                baseXsdType = modelConcept.baseXsdType
                facets = modelConcept.facets
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
            try:
                if baseXsdType == "noContent":
                    text = elt.textValue # no descendant text nodes
                else:
                    text = elt.stringValue # include descendant text nodes
                    if len(text) == 0 and modelConcept is not None:
                        if modelConcept.default is not None:
                            text = modelConcept.default
                        elif modelConcept.fixed is not None:
                            text = modelConcept.fixed
            except Exception as err:
                if isIxFact and err.__class__.__name__ == "FunctionArgType":
                    modelXbrl.error("ixTransform:valueError",
                        _("Inline element %(element)s fact %(fact)s type %(typeName)s transform %(transform)s value error: %(value)s"),
                        modelObject=elt, element=elt.elementQname, fact=elt.qname, transform=elt.format,
                        typeName=modelConcept.baseXsdType if modelConcept is not None else "unknown",
                        value=XmlUtil.innerText(elt, ixExclude=True))
                else:
                    modelXbrl.error("xmlValidation:valueError",
                        _("Element %(element)s error %(error)s value: %(value)s"),
                        modelObject=elt, element=elt.elementQname, error=str(err), value=elt.text)
                elt.sValue = elt.xValue = text = INVALIDixVALUE
                elt.xValid = INVALID
            if text is not INVALIDixVALUE:
                validateValue(modelXbrl, elt, None, baseXsdType, text, isNillable, isNil, facets)
                # note that elt.sValue and elt.xValue are not innerText but only text elements on specific element (or attribute)
            if type is not None:
                definedAttributes = type.attributes
            else:
                definedAttributes = {}
            presentAttributes = set()
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
        # if no attributes assigned above, there won't be an xAttributes, if so assign a shared dict to save memory
        try:
            elt.xAttributes
        except AttributeError:
            elt.xAttributes = xAttributesSharedEmptyDict
            
        if type is not None:
            if attrQname is None:
                missingAttributes = type.requiredAttributeQnames - presentAttributes - elt.slottedAttributesNames
                if missingAttributes:
                    modelXbrl.error("xmlSchema:attributesRequired",
                        _("Element %(element)s type %(typeName)s missing required attributes: %(attributes)s"),
                        modelObject=elt,
                        element=qnElt,
                        typeName=baseXsdType,
                        attributes=','.join(str(a) for a in missingAttributes))
                extraAttributes = presentAttributes - _DICT_SET(definedAttributes.keys()) - XbrlConst.builtinAttributes
                if extraAttributes:
                    attributeWildcards = type.attributeWildcards
                    extraAttributes -= set(a
                                           for a in extraAttributes
                                           if validateAnyWildcard(qnElt, a, attributeWildcards))
                    if isIxFact:
                        extraAttributes -= XbrlConst.ixAttributes
                    if extraAttributes:
                        modelXbrl.error("xmlSchema:attributesExtraneous",
                            _("Element %(element)s type %(typeName)s extraneous attributes: %(attributes)s"),
                            modelObject=elt,
                            element=qnElt,
                            typeName=baseXsdType,
                            attributes=','.join(str(a) for a in extraAttributes))
                # add default attribute values
                for attrQname in (type.defaultAttributeQnames - presentAttributes):
                    modelAttr = type.attributes[attrQname]
                    validateValue(modelXbrl, elt, attrQname.clarkNotation, modelAttr.baseXsdType, modelAttr.default, facets=modelAttr.facets)
            if recurse:
                global validateElementSequence, modelGroupCompositorTitle
                if validateElementSequence is None:
                    from arelle.XmlValidateParticles import validateElementSequence, modelGroupCompositorTitle
                try:
                    childElts = list(elt) # uses __iter__ for inline facts
                    if isNil:
                        if childElts and any(True for e in childElts if isinstance(e, ModelObject)) or elt.text:
                            modelXbrl.error("xmlSchema:nilElementHasContent",
                                _("Element %(element)s is nil but has contents"),
                                modelObject=elt,
                                element=qnElt)
                    else:
                        errResult = validateElementSequence(modelXbrl, type, childElts, ixFacts)
                        if errResult is not None and errResult[2]:
                            iElt, occured, errDesc, errArgs = errResult
                            errElt = childElts[iElt] if iElt < len(childElts) else elt
                            errArgs["modelObject"] = errElt
                            errArgs["element"] = errElt.qname
                            errArgs["parentElement"] = elt.qname
                            if "compositor" in errArgs:  # compositor is an object, provide friendly string
                                errArgs["compositor"] = modelGroupCompositorTitle(errArgs["compositor"])
                            modelXbrl.error(*errDesc,**errArgs)
                    recurse = False # cancel child element validation below, recursion was within validateElementSequence
                except AttributeError as ex:
                    pass
    if recurse: # if there is no complex or simple type (such as xbrli:measure) then this code is used
        for child in (elt.modelTupleFacts if ixFacts and isIxFact else elt):
            if isinstance(child, ModelObject):     
                validate(modelXbrl, child, recurse, attrQname, ixFacts)

def validateValue(modelXbrl, elt, attrTag, baseXsdType, value, isNillable=False, isNil=False, facets=None):
    if baseXsdType:
        try:
            '''
            if (len(value) == 0 and attrTag is None and not isNillable and 
                baseXsdType not in ("anyType", "string", "normalizedString", "token", "NMTOKEN", "anyURI", "noContent")):
                raise ValueError("missing value for not nillable element")
            '''
            xValid = VALID
            whitespaceReplace = (baseXsdType == "normalizedString")
            whitespaceCollapse = (not whitespaceReplace and baseXsdType != "string")
            isList = baseXsdType in {"IDREFS", "ENTITIES", "NMTOKENS"}
            if isList:
                baseXsdType = baseXsdType[:-1] # remove plural
            pattern = baseXsdTypePatterns.get(baseXsdType)
            if facets:
                if "pattern" in facets:
                    pattern = facets["pattern"]
                    # note multiple patterns are or'ed togetner, which isn't yet implemented!
                if "whiteSpace" in facets:
                    whitespaceReplace, whitespaceCollapse = {"preserve":(False,False), "replace":(True,False), "collapse":(False,True)}[facets["whiteSpace"]]
            if whitespaceReplace:
                value = normalizeWhitespacePattern.sub(' ', value)
            elif whitespaceCollapse:
                value = collapseWhitespacePattern.sub(' ', value.strip())
            if baseXsdType == "noContent":
                if len(value) > 0 and not value.isspace():
                    raise ValueError("value content not permitted")
                # note that sValue and xValue are not innerText but only text elements on specific element (or attribute)
                xValue = sValue = None
                xValid = VALID_NO_CONTENT # notify others that element may contain subelements (for stringValue needs)
            elif not value and isNil and isNillable: # rest of types get None if nil/empty value
                xValue = sValue = None
            else:
                if pattern is not None:
                    if ((isList and any(pattern.match(v) is None for v in value.split())) or
                        (not isList and pattern.match(value) is None)):
                        raise ValueError("pattern facet " + facets["pattern"].pattern if facets and "pattern" in facets else "pattern mismatch")
                if facets:
                    if "enumeration" in facets and value not in facets["enumeration"]:
                        raise ValueError("{0} is not in {1}".format(value, facets["enumeration"]))
                    if "length" in facets and len(value) != facets["length"]:
                        raise ValueError("length {0}, expected {1}".format(len(value), facets["length"]))
                    if "minLength" in facets and len(value) < facets["minLength"]:
                        raise ValueError("length {0}, minLength {1}".format(len(value), facets["minLength"]))
                    if "maxLength" in facets and len(value) > facets["maxLength"]:
                        raise ValueError("length {0}, maxLength {1}".format(len(value), facets["maxLength"]))
                if baseXsdType in {"string", "normalizedString", "language", "token", "NMTOKEN","Name","NCName","IDREF","ENTITY"}:
                    xValue = sValue = value
                elif baseXsdType == "ID":
                    xValue = sValue = value
                    xValid = VALID_ID
                elif baseXsdType == "anyURI":
                    if value:  # allow empty strings to be valid anyURIs
                        if UrlUtil.relativeUrlPattern.match(value) is None:
                            raise ValueError("IETF RFC 2396 4.3 syntax")
                    # encode PSVI xValue similarly to Xerces and other implementations
                    xValue = anyURI(UrlUtil.anyUriQuoteForPSVI(value))
                    sValue = value
                elif baseXsdType in ("decimal", "float", "double"):
                    sValue = float(value)
                    if baseXsdType == "decimal":
                        xValue = Decimal(value)
                    else:
                        xValue = sValue
                    if facets:
                        if "totalDigits" in facets and len(value.replace(".","")) > facets["totalDigits"]:
                            raise ValueError("totalDigits facet {0}".format(facets["totalDigits"]))
                        if "fractionDigits" in facets and ( '.' in value and
                            len(value[value.index('.') + 1:]) > facets["fractionDigits"]):
                            raise ValueError("fraction digits facet {0}".format(facets["fractionDigits"]))
                        if "maxInclusive" in facets and xValue > facets["maxInclusive"]:
                            raise ValueError(" > maxInclusive {0}".format(facets["maxInclusive"]))
                        if "maxExclusive" in facets and xValue >= facets["maxExclusive"]:
                            raise ValueError(" >= maxInclusive {0}".format(facets["maxExclusive"]))
                        if "minInclusive" in facets and xValue < facets["minInclusive"]:
                            raise ValueError(" < minInclusive {0}".format(facets["minInclusive"]))
                        if "minExclusive" in facets and xValue <= facets["minExclusive"]:
                            raise ValueError(" <= minExclusive {0}".format(facets["minExclusive"]))
                elif baseXsdType in {"integer",
                                     "nonPositiveInteger","negativeInteger","nonNegativeInteger","positiveInteger",
                                     "long","unsignedLong",
                                     "int","unsignedInt",
                                     "short","unsignedShort",
                                     "byte","unsignedByte"}:
                    xValue = sValue = _INT(value)
                    if ((baseXsdType in {"nonNegativeInteger","unsignedLong","unsignedInt"} 
                         and xValue < 0) or
                        (baseXsdType == "nonPositiveInteger" and xValue > 0) or
                        (baseXsdType == "positiveInteger" and xValue <= 0) or
                        (baseXsdType == "byte" and not -128 <= xValue < 127) or
                        (baseXsdType == "unsignedByte" and not 0 <= xValue < 255) or
                        (baseXsdType == "short" and not -32768 <= xValue < 32767) or
                        (baseXsdType == "unsignedShort" and not 0 <= xValue < 65535) or
                        (baseXsdType == "positiveInteger" and xValue <= 0)):
                        raise ValueError("{0} is not {1}".format(value, baseXsdType))
                    if facets:
                        if "totalDigits" in facets and len(value.replace(".","")) > facets["totalDigits"]:
                            raise ValueError("totalDigits facet {0}".format(facets["totalDigits"]))
                        if "fractionDigits" in facets and ( '.' in value and
                            len(value[value.index('.') + 1:]) > facets["fractionDigits"]):
                            raise ValueError("fraction digits facet {0}".format(facets["fractionDigits"]))
                        if "maxInclusive" in facets and xValue > facets["maxInclusive"]:
                            raise ValueError(" > maxInclusive {0}".format(facets["maxInclusive"]))
                        if "maxExclusive" in facets and xValue >= facets["maxExclusive"]:
                            raise ValueError(" >= maxInclusive {0}".format(facets["maxExclusive"]))
                        if "minInclusive" in facets and xValue < facets["minInclusive"]:
                            raise ValueError(" < minInclusive {0}".format(facets["minInclusive"]))
                        if "minExclusive" in facets and xValue <= facets["minExclusive"]:
                            raise ValueError(" <= minExclusive {0}".format(facets["minExclusive"]))
                elif baseXsdType == "boolean":
                    if value in ("true", "1"):  
                        xValue = sValue = True
                    elif value in ("false", "0"): 
                        xValue = sValue = False
                    else: raise ValueError
                elif baseXsdType == "QName":
                    xValue = qname(elt, value, castException=ValueError, prefixException=ValueError)
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
                    xValue = sValue = value if value == "INF" else _INT(value)
                elif baseXsdType in ("XBRLI_NONZERODECIMAL"):
                    xValue = sValue = _INT(value)
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
                        sValue = value
                        if value in xmlSchemaPatterns:
                            xValue = xmlSchemaPatterns[value]
                        else:
                            if r"\i" in value or r"\c" in value:
                                value = value.replace(r"\i", iNameChar).replace(r"\c", cNameChar)
                            xValue = re.compile(value + "$") # must match whole string
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
                            xValue = gMonthDay(month, day)
                        elif baseXsdType == "gYearMonth":
                            year, month, zSign, zHrMin, zHr, zMin = match.groups()
                            xValue = gYearMonth(year, month)
                        elif baseXsdType == "gYear":
                            year, zSign, zHrMin, zHr, zMin = match.groups()
                            xValue = gYear(year)
                        elif baseXsdType == "gMonth":
                            month, zSign, zHrMin, zHr, zMin = match.groups()
                            xValue = gMonth(month)
                        elif baseXsdType == "gDay":
                            day, zSign, zHrMin, zHr, zMin = match.groups()
                            xValue = gDay(day)
                        else:
                            xValue = value
                    else: # no lexical pattern, forget compiling value
                        xValue = value
                    sValue = value
        except ValueError as err:
            if ModelInlineValueObject is not None and isinstance(elt, ModelInlineValueObject):
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
        try:  # dynamically allocate attributes (otherwise given shared empty set)
            xAttributes = elt.xAttributes
        except AttributeError:
            elt.xAttributes = xAttributes = {}
        xAttributes[attrTag] = ModelAttribute(elt, attrTag, xValid, xValue, sValue, value)
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

def validateAnyWildcard(qnElt, qnAttr, attributeWildcards):
    # note wildcard is a set of possibly multiple values from inherited attribute groups
    for attributeWildcard in attributeWildcards:
        if attributeWildcard.allowsNamespace(qnAttr.namespaceURI):
            return True
    return False