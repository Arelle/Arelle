'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any, Callable, Type, cast
from lxml import etree
from regex import Match, compile as re_compile
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from arelle import XbrlConst, XmlUtil
from arelle.ModelValue import (qname, qnameEltPfxName, qnameClarkName, qnameHref,
                               dateTime, DATE, DATETIME, DATEUNION, time,
                               anyURI, INVALIDixVALUE, gYearMonth, gMonthDay, gYear, gMonth, gDay, isoDuration)
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.PythonUtil import strTruncate
from arelle import UrlUtil

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelDtsObject import ModelAny
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelInstanceObject import ModelFact
    from arelle.typing import TypeGetText
    from arelle.ModelValue import TypeXValue, TypeSValue
    from arelle.ModelDtsObject import ModelType
    from arelle.ModelValue import QName

_: TypeGetText

validateElementSequence: Callable[..., Any] | None = None  #dynamic import to break dependency loops
modelGroupCompositorTitle: Callable[[Any], str] | None = None
ModelInlineValueObject: Type[Any] | None = None
ixMsgCode: Callable[..., str] | None = None

UNVALIDATED = 0 # note that these values may be used a constants in code for better efficiency
UNKNOWN = 1
INVALID = 2
NONE = 3
VALID = 4 # values >= VALID are valid
VALID_ID = 5
VALID_NO_CONTENT = 6 # may be a complex type with children, must be last (after VALID with content enums)

normalizeWhitespacePattern = re_compile(r"[\t\n\r]") # replace tab, line feed, return with space (XML Schema Rules, note: does not include NBSP)
collapseWhitespacePattern = re_compile(r"[ \t\n\r]+") # collapse multiple spaces, tabs, line feeds and returns to single space
entirelyWhitespacePattern = re_compile(r"^[ \t\n\r]+$") # collapse multiple spaces, tabs, line feeds and returns to single space
languagePattern = re_compile("[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$")
NCNamePattern = re_compile("^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                            r"[_\-\."
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")
QNamePattern = re_compile("^([_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                             r"[_\-\."
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*:)?"
                          "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                            r"[_\-\."
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")
namePattern = re_compile("^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                            r"[_\-\.:"
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")

NMTOKENPattern = re_compile(r"[_\-\.:"
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]+$")

decimalPattern = re_compile(r"^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)$")
integerPattern = re_compile(r"^[+-]?([0-9]+)$")
floatPattern = re_compile(r"^(\+|-)?([0-9]+(\.[0-9]*)?|\.[0-9]+)([Ee](\+|-)?[0-9]+)?$|^(\+|-)?INF$|^NaN$")

lexicalPatterns = {
    "duration": re_compile(r"-?P((([0-9]+Y([0-9]+M)?([0-9]+D)?|([0-9]+M)([0-9]+D)?|([0-9]+D))(T(([0-9]+H)([0-9]+M)?([0-9]+(\.[0-9]+)?S)?|([0-9]+M)([0-9]+(\.[0-9]+)?S)?|([0-9]+(\.[0-9]+)?S)))?)|(T(([0-9]+H)([0-9]+M)?([0-9]+(\.[0-9]+)?S)?|([0-9]+M)([0-9]+(\.[0-9]+)?S)?|([0-9]+(\.[0-9]+)?S))))$"),
    "gYearMonth": re_compile(r"-?([1-9][0-9]{3,}|0[0-9]{3})-(0[1-9]|1[0-2])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gYear": re_compile(r"-?([1-9][0-9]{3,}|0[0-9]{3})(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gMonthDay": re_compile(r"--(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gDay": re_compile(r"---(0[1-9]|[12][0-9]|3[01])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "gMonth": re_compile(r"--(0[1-9]|1[0-2])(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "language": re_compile(r"[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$"),
    "XBRLI_DATEUNION": re_compile(r"\s*-?[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?)?(Z|[+-][0-9]{2}:[0-9]{2})?\s*$"),
    "dateTime": re_compile(r"\s*-?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?\s*$"),
    "date": re_compile(r"\s*-?[0-9]{4}-[0-9]{2}-[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})?\s*$"),
    "time": re_compile(r"\s*-?[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?\s*$"),
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
cMinusCNameChar = r"[_\-\."   "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]"

baseXsdTypePatterns = {
                "Name": namePattern,
                "language": languagePattern,
                "languageOrEmpty": re_compile(r"[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$|$"),
                "NMTOKEN": NMTOKENPattern,
                "NCName": NCNamePattern,
                "ID": NCNamePattern,
                "IDREF": NCNamePattern,
                "ENTITY": NCNamePattern,
                "QName": QNamePattern,
            }
predefinedAttributeTypes = {
    qname("{http://www.w3.org/XML/1998/namespace}xml:lang"):("languageOrEmpty",None),
    qname("{http://www.w3.org/XML/1998/namespace}xml:space"):("NCName",{"enumeration":{"default","preserve"}})}
xAttributesSharedEmptyDict: dict[str, ModelAttribute] = {}

def validate(
    modelXbrl: ModelXbrl | None,
    elt: ModelObject,
    recurse: bool = True,
    attrQname: QName | None = None,
    ixFacts: bool = False,
) -> None:
    global ModelInlineValueObject, ixMsgCode
    if ModelInlineValueObject is None:
        from arelle.ModelInstanceObject import ModelInlineValueObject
        from arelle.XhtmlValidate import ixMsgCode
    assert ModelInlineValueObject is not None
    assert ixMsgCode is not None
    isIxFact = isinstance(elt, ModelInlineValueObject)
    facets = None

    # attrQname can be provided for attributes that are global and LAX
    if (getattr(elt,"xValid", UNVALIDATED) == UNVALIDATED) and (not isIxFact or ixFacts):
        assert modelXbrl is not None
        qnElt = elt.qname if ixFacts and isIxFact else elt.elementQname
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        isAbstract = False
        if modelConcept is not None:
            isNillable = modelConcept.isNillable
            type = modelConcept.type
            if modelConcept.isAbstract:
                baseXsdType = "noContent"
                isAbstract = True
            elif modelConcept.isFraction:
                baseXsdType = "fraction"
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
            isNillable = True # allow nil if no schema definition
        isNil = elt.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1")
        if attrQname is None:
            if isNil and not isNillable:
                errElt: str | QName
                if ModelInlineValueObject is not None and isinstance(elt, ModelInlineValueObject):
                    errElt = "{0} fact {1}".format(elt.elementQname, elt.qname)
                else:
                    errElt = elt.elementQname
                modelXbrl.error("xmlSchema:nilNonNillableElement",
                    _("Element %(element)s fact %(fact)s type %(typeName)s is nil but element has not been defined nillable"),
                    modelObject=elt, element=errElt, fact=elt.qname,
                    typeName=modelConcept.baseXsdType if modelConcept is not None else "unknown")
            try:
                if isAbstract:
                    raise ValueError("element is abstract")
                if isNil:
                    text = ""
                elif baseXsdType == "noContent":
                    text = elt.textValue # no descendant text nodes
                else:
                    text = elt.stringValue # include descendant text nodes
                    if modelConcept is not None:
                        if len(text) == 0:
                            if modelConcept.default is not None:
                                text = modelConcept.default
                            elif modelConcept.fixed is not None:
                                text = modelConcept.fixed
                        if baseXsdType == "token" and modelConcept.isEnumeration:
                            if modelConcept.instanceOfType(XbrlConst.qnEnumeration2ItemTypes):
                                baseXsdType = "enumerationHrefs"
                            else:
                                baseXsdType = "enumerationQNames"
            except Exception as err:
                if ModelInlineValueObject is not None and isinstance(elt, ModelInlineValueObject):
                    errElt = "{0} fact {1}".format(elt.elementQname, elt.qname)
                else:
                    errElt = elt.elementQname
                if isIxFact and err.__class__.__name__ == "FunctionArgType":
                    assert isinstance(elt, ModelInlineValueObject)
                    modelXbrl.error(ixMsgCode("transformValueError", elt),
                        _("Inline element %(element)s fact %(fact)s type %(typeName)s transform %(transform)s value error: %(value)s"),
                        modelObject=elt, element=errElt, fact=elt.qname, transform=elt.format,
                        typeName=modelConcept.baseXsdType if modelConcept is not None else "unknown",
                        value=XmlUtil.innerText(elt, ixExclude=True, ixContinuation=elt.namespaceURI==XbrlConst.ixbrl11))
                elif isIxFact and err.__class__.__name__ == "ixtFunctionNotAvailable":
                    assert isinstance(elt, ModelInlineValueObject)
                    modelXbrl.error(ixMsgCode("invalidTransformation", elt, sect="validation"),
                        _("Fact %(fact)s has unrecognized transformation %(transform)s, value: %(value)s"),
                        modelObject=elt, element=errElt, fact=elt.qname, transform=elt.format,
                        typeName=modelConcept.baseXsdType if modelConcept is not None else "unknown",
                        value=XmlUtil.innerText(elt, ixExclude=True, ixContinuation=elt.namespaceURI==XbrlConst.ixbrl11))
                elif isAbstract:
                    modelXbrl.error("xmlSchema:abstractElement",
                        _("Element %(element)s has abstract declaration, value: %(value)s"),
                        modelObject=elt, element=errElt, error=str(err), value=elt.text)
                else:
                    modelXbrl.error("xmlSchema:valueError",
                        _("Element %(element)s error %(error)s value: %(value)s"),
                        modelObject=elt, element=errElt, error=str(err), value=elt.text)
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
        for attrTag_, attrValue_ in elt.items():
            attrTag: str = cast(str, attrTag_)
            attrValue: str = cast(str, attrValue_)
            qn = qnameClarkName(attrTag)
            #qn = qname(attrTag, noPrefixIsNoNamespace=True)
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
                elif elt.namespaceURI == "http://xbrl.org/2006/xbrldi":
                    if attrTag == "dimension":
                        baseXsdAttrType = "QName"
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
                extraAttributes = presentAttributes - definedAttributes.keys() - XbrlConst.builtinAttributes
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
                assert validateElementSequence is not None
                assert modelGroupCompositorTitle is not None
                try:
                    #childElts = list(elt) # uses __iter__ for inline facts
                    childElts = [e for e in elt if isinstance(e, ModelObject)]
                    if isNil:
                        if childElts or elt.text:
                            modelXbrl.error("xmlSchema:nilElementHasContent",
                                _("Element %(element)s is nil but has contents"),
                                modelObject=elt,
                                element=qnElt)
                    else:
                        errResult = validateElementSequence(modelXbrl, type, childElts, ixFacts)
                        if errResult is not None and errResult[2]:
                            iElt, occured, errDesc, errArgs = errResult
                            errElt1 = childElts[iElt] if iElt < len(childElts) else elt
                            errArgs["modelObject"] = errElt1
                            errArgs["element"] = errElt1.qname
                            errArgs["parentElement"] = elt.qname
                            if "compositor" in errArgs:  # compositor is an object, provide friendly string
                                errArgs["compositor"] = modelGroupCompositorTitle(errArgs["compositor"])
                            modelXbrl.error(*errDesc,**errArgs)

                            # when error is in an xbrli element, check any further unvalidated children
                            if qnElt.namespaceURI == XbrlConst.xbrli and iElt < len(childElts):
                                for childElt in childElts[iElt:]:
                                    if (getattr(childElt,"xValid", UNVALIDATED) == UNVALIDATED):
                                        validate(modelXbrl, childElt, ixFacts=ixFacts)
                    recurse = False # cancel child element validation below, recursion was within validateElementSequence
                except AttributeError as ex:
                    raise ex
                    #pass  # HF Why is this here????
    if recurse: # if there is no complex or simple type (such as xbrli:measure) then this code is used
        for child in (cast('ModelFact', elt).modelTupleFacts if ixFacts and isIxFact else elt):
            if isinstance(child, ModelObject):
                validate(modelXbrl, child, recurse, attrQname, ixFacts)

def validateValue(
    modelXbrl: ModelXbrl | None,
    elt: ModelObject,
    attrTag: str | None,
    baseXsdType: str | None,
    value: str,
    isNillable: bool = False,
    isNil: bool = False,
    facets: dict[str, Any] | None = None,
) -> None:
    sValue: TypeSValue
    xValue: TypeXValue

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
                if facets:
                    if "minLength" not in facets:
                        facets = facets.copy()
                        facets["minLength"] = 1
                else:
                    facets = {"minLength": 1}
            pattern = baseXsdTypePatterns.get(baseXsdType)
            if facets:
                if "pattern" in facets:
                    pattern = facets["pattern"]
                    # note multiple patterns are or'ed togetner, which isn't yet implemented!
                if "whiteSpace" in facets:
                    whitespaceReplace, whitespaceCollapse = {"preserve":(False,False), "replace":(True,False), "collapse":(False,True)}[facets["whiteSpace"]]
            if whitespaceReplace:
                value = normalizeWhitespacePattern.sub(' ', value) # replace tab, line feed, return with space
            elif whitespaceCollapse:
                value = collapseWhitespacePattern.sub(' ', value).strip(' ') # collapse multiple spaces, tabs, line feeds and returns to single space
            if baseXsdType == "noContent":
                if len(value) > 0 and not entirelyWhitespacePattern.match(value): # only xml schema pattern whitespaces removed
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
                        raise ValueError("{0} is not in {1}".format(value, facets["enumeration"].keys()))
                    if "length" in facets and len(value) != facets["length"]:
                        raise ValueError("length {0}, expected {1}".format(len(value), facets["length"]))
                    if "minLength" in facets and len(value) < facets["minLength"]:
                        raise ValueError("length {0}, minLength {1}".format(len(value), facets["minLength"]))
                    if "maxLength" in facets and len(value) > facets["maxLength"]:
                        raise ValueError("length {0}, maxLength {1}".format(len(value), facets["maxLength"]))
                if baseXsdType in {"string", "normalizedString", "language", "languageOrEmpty", "token", "NMTOKEN","Name","NCName","IDREF","ENTITY"}:
                    xValue = sValue = value
                elif baseXsdType == "ID":
                    xValue = sValue = value
                    xValid = VALID_ID
                elif baseXsdType == "anyURI":
                    if value:  # allow empty strings to be valid anyURIs
                        if UrlUtil.isValidUriReference(value) is None:
                            raise ValueError("IETF RFC 2396 4.3 syntax")
                    # encode PSVI xValue similarly to Xerces and other implementations
                    xValue = anyURI(UrlUtil.anyUriQuoteForPSVI(value))
                    sValue = value
                elif baseXsdType in ("decimal", "float", "double", "XBRLI_NONZERODECIMAL"):
                    if baseXsdType in ("decimal", "XBRLI_NONZERODECIMAL"):
                        if decimalPattern.match(value) is None:
                            raise ValueError("lexical pattern mismatch")
                        xValue = Decimal(value)
                        sValue = float(value) # s-value uses Number (float) representation
                        if sValue == 0 and baseXsdType == "XBRLI_NONZERODECIMAL":
                            raise ValueError("zero is not allowed")
                    else:
                        if floatPattern.match(value) is None:
                            raise ValueError("lexical pattern mismatch")
                        xValue = sValue = float(value)
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
                    xValue = sValue = int(value)
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
                    xValue = qnameEltPfxName(elt, value, prefixException=ValueError)
                    #xValue = qname(elt, value, castException=ValueError, prefixException=ValueError)
                    sValue = value
                    ''' not sure here, how are explicitDimensions validated, but bad units not?
                    if xValue.namespaceURI in modelXbrl.namespaceDocs:
                        if (xValue not in modelXbrl.qnameConcepts and
                            xValue not in modelXbrl.qnameTypes and
                            xValue not in modelXbrl.qnameAttributes and
                            xValue not in modelXbrl.qnameAttributeGroups):
                            raise ValueError("qname not defined " + str(xValue))
                    '''
                elif baseXsdType == "enumerationHrefs":
                    xValue = [qnameHref(href) for href in value.split()]
                    sValue = value
                elif baseXsdType == "enumerationQNames":
                    xValue = [qnameEltPfxName(elt, qn, prefixException=ValueError) for qn in value.split()]
                    sValue = value
                elif baseXsdType in ("XBRLI_DECIMALSUNION", "XBRLI_PRECISIONUNION"):
                    xValue = sValue = value if value == "INF" else int(value)
                elif baseXsdType in ("XBRLI_NONZERODECIMAL"):
                    xValue = sValue = int(value)
                    if xValue == 0:
                        raise ValueError("invalid value")
                elif baseXsdType == "xsd-pattern":
                    # for facet compiling
                    try:
                        sValue = value
                        if value in xmlSchemaPatterns:
                            xValue = xmlSchemaPatterns[value]
                        else:
                            xValue = XsdPattern().compile(value)
                    except Exception as err:
                        raise ValueError(err)
                elif baseXsdType == "fraction":
                    numeratorStr, denominatorStr = elt.fractionValue  # type: ignore[attr-defined]
                    if numeratorStr == INVALIDixVALUE or denominatorStr == INVALIDixVALUE:
                        sValue = xValue = INVALIDixVALUE
                        xValid = INVALID
                    else:
                        sValue = value
                        numeratorNum = float(numeratorStr)
                        denominatorNum = float(denominatorStr)
                        if numeratorNum.is_integer() and denominatorNum.is_integer():
                            xValue = Fraction(int(numeratorNum), int(denominatorNum))
                        else:
                            xValue = Fraction(numeratorNum / denominatorNum)
                else:
                    if baseXsdType in lexicalPatterns:
                        match = lexicalPatterns[baseXsdType].match(value)
                        if match is None:
                            raise ValueError("lexical pattern mismatch")
                        if baseXsdType == "XBRLI_DATEUNION":
                            xValue = dateTime(value, type=DATEUNION, castException=ValueError)
                            sValue = value
                        elif baseXsdType == "dateTime":
                            xValue = dateTime(value, type=DATETIME, castException=ValueError)
                            sValue = value
                        elif baseXsdType == "date":
                            xValue = dateTime(value, type=DATE, castException=ValueError)
                            sValue = value
                        elif baseXsdType == "time":
                            xValue = time(value, castException=ValueError)
                            sValue = value
                        elif baseXsdType == "gMonthDay":
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
                        elif baseXsdType == "duration":
                            xValue = isoDuration(value)
                        else:
                            xValue = value
                    else: # no lexical pattern, forget compiling value
                        xValue = value
                    sValue = value
        except (ValueError, InvalidOperation) as err:
            errElt: str | QName
            if ModelInlineValueObject is not None and isinstance(elt, ModelInlineValueObject):
                errElt = "{0} fact {1}".format(elt.elementQname, elt.qname)
            else:
                errElt = elt.elementQname
            assert modelXbrl is not None
            if attrTag:
                modelXbrl.error("xmlSchema:valueError",
                    _("Element %(element)s attribute %(attribute)s type %(typeName)s value error: %(value)s, %(error)s"),
                    modelObject=elt,
                    element=errElt,
                    attribute=XmlUtil.clarkNotationToPrefixedName(elt,attrTag,isAttribute=True),
                    typeName=baseXsdType,
                    value=strTruncate(value, 30),
                    error=err)
            else:
                modelXbrl.error("xmlSchema:valueError",
                    _("Element %(element)s type %(typeName)s value error: %(value)s, %(error)s"),
                    modelObject=elt,
                    element=errElt,
                    typeName=baseXsdType,
                    value=strTruncate(value, 30),
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

def validateFacet(typeElt: ModelType, facetElt: ModelObject) -> TypeXValue | None:
    facetName = facetElt.localName
    value = facetElt.get("value")
    if facetName in ("length", "minLength", "maxLength", "totalDigits", "fractionDigits"):
        baseXsdType = "integer"
        facets = None
    elif facetName in ("minInclusive", "maxInclusive", "minExclusive", "maxExclusive"):
        baseXsdType = typeElt.baseXsdType
        facets = None
    elif facetName == "whiteSpace":
        baseXsdType = "string"
        facets = {"enumeration": {"replace","preserve","collapse"}}
    elif facetName == "pattern":
        baseXsdType = "xsd-pattern"
        facets = None
    else:
        baseXsdType = "string"
        facets = None
    assert value is not None
    validateValue(typeElt.modelXbrl, facetElt, None, baseXsdType, value, facets=facets)
    if facetElt.xValid == VALID:
        return facetElt.xValue
    return None

def validateAnyWildcard(qnElt: QName, qnAttr: QName, attributeWildcards: list[ModelAny]) -> bool:
    # note wildcard is a set of possibly multiple values from inherited attribute groups
    for attributeWildcard in attributeWildcards:
        if attributeWildcard.allowsNamespace(qnAttr.namespaceURI):  # type: ignore[no-untyped-call]
            return True
    return False

class lxmlSchemaResolver(etree.Resolver):
    def __init__(self, cntlr: Cntlr, modelXbrl: ModelXbrl | None = None) -> None:
        super(lxmlSchemaResolver, self).__init__()
        self.cntlr = cntlr
        self.modelXbrl = modelXbrl

    def resolve(self, url: str | None, id: str, context: Any) -> Any: #  type: ignore[override]
        if self.modelXbrl is None or not self.modelXbrl.fileSource.isInArchive(url):
            url = self.cntlr.webCache.getfilename(url)
        if url: # may be None if file doesn't exist
            if self.modelXbrl is not None: # use fileSource
                fh = self.modelXbrl.fileSource.file(url,binary=True)[0]
                return self.resolve_file(fh, context, base_url=None, close=True)
            else: # probably no active modelXbrl yet, such as when loading packages, use url
                return self.resolve_filename(url, context)  # type: ignore[attr-defined]
        return self.resolve_empty(context)  # type: ignore[attr-defined]

def lxmlResolvingParser(cntlr: Cntlr, modelXbrl: ModelXbrl | None = None) -> etree.XMLParser:
    parser = etree.XMLParser()
    parser.resolvers.add(lxmlSchemaResolver(cntlr, modelXbrl))
    return parser

def lxmlSchemaValidate(modelDocument: ModelDocument) -> None:
    # lxml schema-validate modelDocument
    if modelDocument is None:
        return
    modelXbrl = modelDocument.modelXbrl
    cntlr = modelXbrl.modelManager.cntlr
    ns = modelDocument.xmlRootElement.qname.namespaceURI
    if ns:
        try:
            if ns in modelXbrl.namespaceDocs:
                xsdTree = modelXbrl.namespaceDocs[ns][0].xmlRootElement.getroottree()
            else:
                xsdTree = None
                for slElt in modelDocument.schemaLocationElements:
                    _sl = (slElt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation") or "").split()
                    for i in range(0, len(_sl), 2):
                        if _sl[i] == ns and i+1 < len(_sl):
                            url = cntlr.webCache.normalizeUrl(_sl[i+1], modelDocument.baseForElement(slElt))  # type: ignore[no-untyped-call]
                            try:
                                xsdTree = etree.parse(url,parser=lxmlResolvingParser(cntlr, modelXbrl))
                                break
                            except (EnvironmentError, KeyError, UnicodeDecodeError) as err:
                                msgCode = "arelle.schemaFileError"
                                cntlr.addToLog(_("XML schema validation error: %(error)s"),
                                               messageArgs={"error": str(err)},
                                               messageCode=msgCode,
                                               file=(modelDocument.basename, _sl[i+1]),
                                               level=logging.INFO) # schemaLocation is just a hint
                                modelDocument.modelXbrl.errors.append(msgCode)
                    if xsdTree is not None:
                        break
            if xsdTree is None:
                return # no schema to validate
            docTree = modelDocument.xmlRootElement.getroottree()
            etreeXMLSchema = etree.XMLSchema(xsdTree)
            etreeXMLSchema.assertValid(docTree)
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as err:
            msgCode = "lxml.schemaError"
            cntlr.addToLog(_("XML file syntax error %(error)s"),
                           messageArgs={"error": str(err)},
                           messageCode=msgCode,
                           file=modelDocument.basename,
                           level=logging.ERROR)
            modelDocument.modelXbrl.errors.append(msgCode)

class XsdPattern():
    # shim class for python wrapper of xsd pattern
    def compile(self, p: str) -> XsdPattern:
        self.xsdPattern = p
        if r"\i" in p or r"\c" in p:
            p = p.replace(r"[\i-[:]]", iNameChar).replace(r"\i", iNameChar) \
                 .replace(r"[\c-[:]]", cMinusCNameChar).replace(r"\c", cNameChar)
        self.pyPattern = re_compile(p + "$") # must match whole string
        return self

    def match(self, string: str) -> Match[str] | None:
        return self.pyPattern.match(string)

    @property
    def pattern(self) -> str:
        return self.xsdPattern

    def __repr__(self) -> str:
        return self.xsdPattern
