'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import datetime
from dataclasses import dataclass
import logging
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, cast
from lxml import etree
from regex import Match, Pattern, compile as re_compile
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from arelle import UrlUtil, XbrlConst, XmlUtil, XmlValidateConst
from arelle.ModelValue import (qname, qnameFromNsmap, qnameClarkName, qnameHref,
                               dateTime, DATE, DATETIME, DATEUNION, time,
                               anyURI, INVALIDixVALUE, gYearMonth, gMonthDay, gYear, gMonth, gDay, isoDuration)
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.PythonUtil import strTruncate

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelDtsObject import ModelAnyAttribute
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelInstanceObject import ModelFact
    from arelle.typing import TypeGetText
    from arelle.ModelValue import TypeXValue, TypeSValue
    from arelle.ModelDtsObject import ModelType
    from arelle.ModelValue import QName

_: TypeGetText

# XSD Part 2 Appendix F name-character escapes (\i, \c) → Python character classes.
iNameChar = "[:_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"  # \i
iNameCharMinusColon = iNameChar.replace("[:", "[", 1)  # [\i-[:]]
cNameChar = r"[:_\-\."   "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]"  # \c
cNameCharMinusColon = cNameChar.replace("[:", "[", 1)  # [\c-[:]]

def _raiseOnNonXsdRegexSyntax(p: str) -> None:
    """
    Python regex supports extension groups (?:...) syntax (lookahead, non-capturing groups) that XSD patterns do not.
    Raise a ValueError if the pattern contains any such syntax.
    """
    i = 0
    while i < len(p) - 1:
        if p[i] == "\\":
            i += 2
        elif p[i] == "(" and p[i + 1] == "?":
            raise ValueError("XSD regular expressions do not support '(?' syntax")
        else:
            i += 1


@dataclass(frozen=True)
class XsdPattern:
    xsdPattern: str
    pyPattern: Pattern[str]

    # shim class for python wrapper of xsd pattern
    @classmethod
    def compile(cls, p: str) -> XsdPattern:
        """Expand XSD \\i and \\c escapes to Python character classes.

        Per XSD Part 2 Appendix F:
          \\i           → NameStartChar (Letter | '_' | ':')
          [\\i-[:]]     → NCName start (NameStartChar minus ':')
          \\c           → NameChar (includes ':')
          [\\c-[:]]     → NameChar minus ':'

        Subtract forms are replaced first so bare \\i/\\c inside them are not touched.
        """
        _raiseOnNonXsdRegexSyntax(p)
        if r"\i" in p or r"\c" in p:
            p = (p.replace(r"[\i-[:]]", iNameCharMinusColon)
                 .replace(r"\i", iNameChar)
                 .replace(r"[\c-[:]]", cNameCharMinusColon)
                 .replace(r"\c", cNameChar))
        pyPattern = re_compile(p + "$") # must match whole string
        return cls(p, pyPattern)

    def match(self, string: str) -> Match[str] | None:
        return self.pyPattern.match(string)

    @property
    def pattern(self) -> str:
        return self.xsdPattern

    def __repr__(self) -> str:
        return self.xsdPattern


@dataclass(frozen=True, slots=True)
class XmlValidationResult:
    sValue: TypeSValue
    xValue: TypeXValue
    xValid: int

    @property
    def isXValid(self) -> bool:
        return self.xValid >= XmlValidateConst.VALID


# support legacy direct imports from this module
UNVALIDATED      = XmlValidateConst.UNVALIDATED
UNKNOWN          = XmlValidateConst.UNKNOWN
INVALID          = XmlValidateConst.INVALID
NONE             = XmlValidateConst.NONE
VALID            = XmlValidateConst.VALID
VALID_ID         = XmlValidateConst.VALID_ID
VALID_NO_CONTENT = XmlValidateConst.VALID_NO_CONTENT


validateElementSequence: Callable[..., Any] | None = None  #dynamic import to break dependency loops
modelGroupCompositorTitle: Callable[[Any], str] | None = None
ModelInlineValueObject: type[Any] | None = None
ixMsgCode: Callable[..., str] | None = None

entirelyWhitespacePattern = re_compile(r"^[ \t\n\r]+$") # collapse multiple spaces, tabs, line feeds and returns to single space
languagePattern = re_compile("[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$")
NCNamePattern = re_compile("^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF]"
                            r"[_\-\."
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\u0300-\u036F\u203F-\u2040]*$")
QNamePattern = re_compile("^([_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF]"
                             r"[_\-\."
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\u0300-\u036F\u203F-\u2040]*:)?"
                          "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF]"
                            r"[_\-\."
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\u0300-\u036F\u203F-\u2040]*$")
namePattern = re_compile("^[:_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF]"
                            r"[_\-\.:"
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\u0300-\u036F\u203F-\u2040]*$")

NMTOKENPattern = re_compile(r"[_\-\.:"
                               "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\u0300-\u036F\u203F-\u2040]+$")

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
    "base64Binary": re_compile(r"((([A-Za-z0-9+/]\s?){4})*(([A-Za-z0-9+/]\s?){3}[A-Za-z0-9+/]|([A-Za-z0-9+/]\s?){2}[AEIMQUYcgkosw048]\s?=|[A-Za-z0-9+/]\s?[AQgw]\s?=\s?=))?$"),
    "hexBinary": re_compile(r"([0-9a-fA-F]{2})*$"),
    "language": re_compile(r"[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$"),
    "XBRLI_DATEUNION": re_compile(r"\s*-?[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?)?(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?\s*$"),
    "dateTime": re_compile(r"\s*-?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "date": re_compile(r"\s*-?[0-9]{4}-[0-9]{2}-[0-9]{2}(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    "time": re_compile(r"\s*-?[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$"),
    }

# patterns difficult to compile into python
xmlSchemaPatterns = {
    pattern: XsdPattern(xsdPattern=pattern, pyPattern=pyPattern)
    for pattern, pyPattern in (
        (r"\c+", NMTOKENPattern),
        (r"\i\c*", namePattern),
        (r"[\i-[:]][\c-[:]]*", NCNamePattern),
    )
}

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
_XSD_TYPE_INHERENT_INCLUSIVE_BOUNDS: dict[str, tuple[int | None, int | None]] = {
    "nonPositiveInteger": (None, 0),
    "negativeInteger": (None, -1),
    "long": (-9223372036854775808, 9223372036854775807),
    "int": (-2147483648, 2147483647),
    "short": (-32768, 32767),
    "byte": (-128, 127),
    "nonNegativeInteger": (0, None),
    "unsignedLong": (0, 18446744073709551615),
    "unsignedInt": (0, 4294967295),
    "unsignedShort": (0, 65535),
    "unsignedByte": (0, 255),
    "positiveInteger": (1, None),
}
_INTEGER_BASE_XSD_TYPES = frozenset(_XSD_TYPE_INHERENT_INCLUSIVE_BOUNDS.keys() | {"integer"})

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
    setTargetModelXbrl: bool = False, # when true also revalidate previously validated elements
    elementDeclarationType: ModelType | None = None,
)  -> None:
    global ModelInlineValueObject, ixMsgCode
    if ModelInlineValueObject is None:
        from arelle.ModelInstanceObject import ModelInlineValueObject
        from arelle.XhtmlInlineUtil import ixMsgCode
    assert ModelInlineValueObject is not None
    assert ixMsgCode is not None
    isIxFact = isinstance(elt, ModelInlineValueObject)
    facets = None

    # attrQname can be provided for attributes that are global and LAX
    if (getattr(elt,"xValid", UNVALIDATED) == UNVALIDATED or setTargetModelXbrl) and (not isIxFact or ixFacts):
        assert modelXbrl is not None
        if setTargetModelXbrl and modelXbrl != elt.modelXbrl: # change of element's targetModelXbrl
            elt.targetModelXbrl = modelXbrl
        qnElt = elt.qname if ixFacts and isIxFact else elt.elementQname
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        isAbstract = False
        if modelConcept is not None:
            isNillable = modelConcept.isNillable
            modelType = modelConcept.type
            if modelConcept.isAbstract:
                baseXsdType = "noContent"
                isAbstract = True
            elif modelConcept.isFraction:
                baseXsdType = "fraction"
            elif (
                elementDeclarationType is None
                or elementDeclarationType.qname == XbrlConst.qnXsdDefaultType
                or modelType.qname == elementDeclarationType.qname  # type: ignore[union-attr]
                or modelType.isDerivedFrom(elementDeclarationType.qname)  # type: ignore[arg-type,union-attr]
            ):
                baseXsdType = modelConcept.baseXsdType
                facets = modelConcept.facets
            else:
                baseXsdType = elementDeclarationType.baseXsdType
                facets = elementDeclarationType.facets
        elif qnElt == XbrlConst.qnXbrldiExplicitMember: # not in DTS
            baseXsdType = "QName"
            modelType = None
            isNillable = False
        elif qnElt == XbrlConst.qnXbrldiTypedMember: # not in DTS
            baseXsdType = "noContent"
            modelType = None
            isNillable = False
        else:
            baseXsdType = None
            modelType = None
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
                    if ixFacts: # still must validate format
                        text = elt.stringValue
                    else:
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
            if modelType is not None:
                definedAttributes = modelType.attributes
            else:
                definedAttributes = {}
            presentAttributes = set()
        # validate attributes
        # find missing attributes for default values
        for attrTag, attrValue in elt.items():
            qn = qnameClarkName(attrTag)
            #qn = qname(attrTag, noPrefixIsNoNamespace=True)
            baseXsdAttrType = None
            facets = None
            if attrQname is not None: # validate all attributes and element
                if attrQname != qn:
                    continue
            elif modelType is not None:
                presentAttributes.add(qn)
                if qn in definedAttributes: # look for concept-type-specific attribute definition
                    modelAttr = definedAttributes[qn]
                elif qn.namespaceURI:   # may be a globally defined attribute
                    modelAttr = modelXbrl.qnameAttributes.get(qn)  # type: ignore[assignment]
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

        if modelType is not None:
            if attrQname is None:
                missingAttributes = modelType.requiredAttributeQnames - presentAttributes - elt.slottedAttributesNames
                if missingAttributes:
                    modelXbrl.error("xmlSchema:attributesRequired",
                        _("Element %(element)s type %(typeName)s missing required attributes: %(attributes)s"),
                        modelObject=elt,
                        element=qnElt,
                        typeName=baseXsdType,
                        attributes=','.join(str(a) for a in missingAttributes))
                extraAttributes = presentAttributes - definedAttributes.keys() - XbrlConst.builtinAttributes
                if extraAttributes:
                    attributeWildcards = modelType.attributeWildcards
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
                for attrQname in (modelType.defaultAttributeQnames - presentAttributes):
                    modelAttr = modelType.attributes[attrQname]
                    validateValue(modelXbrl, elt, attrQname.clarkNotation, modelAttr.baseXsdType, modelAttr.default, facets=modelAttr.facets)  # type: ignore[arg-type]
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
                        errResult = validateElementSequence(modelXbrl, modelType, childElts, ixFacts, setTargetModelXbrl)
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
                                        validate(modelXbrl, childElt, ixFacts=ixFacts, setTargetModelXbrl=setTargetModelXbrl)
                    recurse = False # cancel child element validation below, recursion was within validateElementSequence
                except AttributeError as ex:
                    raise ex
                    #pass  # HF Why is this here????
    if recurse: # if there is no complex or simple type (such as xbrli:measure) then this code is used
        for child in (cast('ModelFact', elt).modelTupleFacts if ixFacts and isIxFact else elt):
            if isinstance(child, ModelObject):
                validate(modelXbrl, child, recurse, attrQname, ixFacts, setTargetModelXbrl)


def fractionValidateValue(value: str, fractionValue: tuple[str, str]) -> XmlValidationResult:
    sValue: TypeSValue
    xValue: TypeXValue
    numeratorStr, denominatorStr = fractionValue
    if numeratorStr == INVALIDixVALUE or denominatorStr == INVALIDixVALUE:
        sValue = xValue = INVALIDixVALUE
        xValid = INVALID
    else:
        sValue = value
        xValid = VALID
        numeratorNum = float(numeratorStr)
        denominatorNum = float(denominatorStr)
        if numeratorNum.is_integer() and denominatorNum.is_integer():
            xValue = Fraction(int(numeratorNum), int(denominatorNum))
        else:
            xValue = Fraction(numeratorNum / denominatorNum)
    return XmlValidationResult(sValue=sValue, xValue=xValue, xValid=xValid)


# XSD Datatypes 3.2.7.4: a date/time value with no timezone may stand for any
# timezone in the [-14:00, +14:00] range, so its instant is only known to within 14h.
_XSD_MAX_TIMEZONE_OFFSET = datetime.timedelta(hours=14)


def _comparableInstant(value: datetime.datetime | datetime.time) -> datetime.datetime:
    # Express an xs:dateTime/date/time value as a single datetime so values can be
    # ordered: timezone-aware values are normalized to (naive) UTC; an xs:time is
    # anchored to an arbitrary fixed date (XSD Datatypes 3.2.8).
    # Timezone-naive values are left as-is.
    if isinstance(value, datetime.datetime):
        dt = value
    else:  # datetime.time (xs:time)
        dt = datetime.datetime(2000, 1, 1, value.hour, value.minute, value.second, value.microsecond, value.tzinfo)
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def _hashableXValue(xValue: Any) -> Any:
    # xValue is normally hashable, but list-valued types (e.g. enumerationHrefs/
    # enumerationQNames, whose xValue is a list of QName) are not. Convert to a
    # tuple so such values can still be used as (or looked up against) dict keys.
    if isinstance(xValue, list):
        return tuple(xValue)
    return xValue


def _orderedComparison(value: Any, bound: Any) -> int | None:
    """Order ``value`` against an ordering-facet ``bound``.

    ``value`` and ``bound`` must be the same type: they are expected to be the
    already-validated value and facet bound for the same ``baseXsdType``, e.g. both
    ``DateTime`` or both ``Time``. Raises ``TypeError`` if they aren't, since a type
    mismatch indicates a caller bug (a facet compiled against the wrong base type)
    rather than an ordering that can be resolved here.

    Returns ``-1``/``0``/``1`` when ``value`` is less than/equal to/greater than
    ``bound``, or ``None`` when the order is indeterminate. Callers should treat
    ``None`` as failing whichever relation the facet requires (Datatypes 3.2.6.3:
    "indeterminate comparisons should be considered as 'false'").

    Ordinarily the operands' own comparison operators are used. For an xs:date/time
    value where exactly one operand carries a timezone, Python raises ``TypeError``
    rather than ordering offset-naive against offset-aware values; in that case apply
    the XSD timezone-straddling rule (Datatypes 3.2.7.4) on the underlying instants,
    yielding ``None`` when the timezone uncertainty leaves the order undetermined.
    """
    if type(value) is not type(bound):
        raise TypeError("Value type ({}) is not comparable with bound type ({}).".format(type(value), type (bound)))
    try:
        if value < bound:
            return -1
        if value > bound:
            return 1
        return 0
    except TypeError:
        if not isinstance(value, (datetime.datetime, datetime.time)) or \
                not isinstance(bound, (datetime.datetime, datetime.time)):
            raise
        valueInstant = _comparableInstant(value)
        boundInstant = _comparableInstant(bound)
        if value.tzinfo is not None:  # bound is the timezone-naive operand
            if valueInstant < boundInstant - _XSD_MAX_TIMEZONE_OFFSET:
                return -1
            if valueInstant > boundInstant + _XSD_MAX_TIMEZONE_OFFSET:
                return 1
        else:  # value is the timezone-naive operand
            if valueInstant + _XSD_MAX_TIMEZONE_OFFSET < boundInstant:
                return -1
            if valueInstant - _XSD_MAX_TIMEZONE_OFFSET > boundInstant:
                return 1
        return None


def validateValueString(
    baseXsdType: str,
    value: str,
    isNillable: bool = False,
    isNil: bool = False,
    facets: Mapping[str, Any] | None = None,
    nsmap: Mapping[str | None, str] | None = None,
) -> XmlValidationResult:
    try:
        return _validateValueStringOrRaise(baseXsdType, value, isNillable, isNil, facets, nsmap)
    except (InvalidOperation, ValueError):
        return XmlValidationResult(sValue=value, xValue=None, xValid=INVALID)


def _validateValueStringOrRaise(
    baseXsdType: str,
    value: str,
    isNillable: bool = False,
    isNil: bool = False,
    facets: Mapping[str, Any] | None = None,
    nsmap: Mapping[str | None, str] | None = None,
) -> XmlValidationResult:
    if nsmap is None:
        nsmap = {}
    sValue: TypeSValue
    xValue: TypeXValue
    xValid = VALID
    whitespaceReplace = (baseXsdType == "normalizedString")
    whitespaceCollapse = (not whitespaceReplace and baseXsdType != "string")
    isList = baseXsdType in {"IDREFS", "ENTITIES", "NMTOKENS"}
    if isList:
        baseXsdType = baseXsdType[:-1] # remove plural
        if facets:
            if "minLength" not in facets:
                facets = {
                    **facets,
                    "minLength": 1,
                }
        else:
            facets = {"minLength": 1}
    pattern = baseXsdTypePatterns.get(baseXsdType)
    if facets:
        if "pattern" in facets:
            pattern = facets["pattern"]
            # note multiple patterns are or'ed togetner, which isn't yet implemented!
        if "whiteSpace" in facets:
            whitespaceReplace, whitespaceCollapse = {"preserve": (False, False), "replace": (True, False), "collapse": (False, True)}[facets["whiteSpace"]]
    if whitespaceReplace:
        value = XmlUtil.replaceWhitespace(value)
    elif whitespaceCollapse:
        value = XmlUtil.collapseWhitespace(value)
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
            # length/minLength/maxLength are meaningless for QName and NOTATION; per
            # XSD Datatypes 3.2.18/3.2.19 every value is facet-valid with respect to them.
            if baseXsdType not in ("QName", "NOTATION"):
                # length facets count octets of binary data for hexBinary/base64Binary,
                # characters otherwise (XSD Datatypes 4.3.1); compute the units once.
                if baseXsdType == "hexBinary":
                    valueLength = len(value) // 2
                elif baseXsdType == "base64Binary":
                    # ignore lexical spaces before counting octets (whitespace already collapsed to spaces)
                    data = value.replace(" ", "")
                    valueLength = len(data) * 3 // 4 - data.count("=")
                else:
                    valueLength = len(value)
                if "length" in facets and valueLength != facets["length"]:
                    raise ValueError("length {0}, expected {1}".format(valueLength, facets["length"]))
                if "minLength" in facets and valueLength < facets["minLength"]:
                    raise ValueError("length {0}, minLength {1}".format(valueLength, facets["minLength"]))
                if "maxLength" in facets and valueLength > facets["maxLength"]:
                    raise ValueError("length {0}, maxLength {1}".format(valueLength, facets["maxLength"]))
        if baseXsdType in {"string", "normalizedString", "language", "languageOrEmpty", "token", "NMTOKEN", "Name", "NCName", "IDREF", "ENTITY"}:
            xValue = sValue = value
        elif baseXsdType == "ID":
            xValue = sValue = value
            xValid = VALID_ID
        elif baseXsdType == "anyURI":
            if not UrlUtil.isValidUriReference(value):
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
                # totalDigits isn't a valid constraining facet for float/double (XSD Datatypes 3.2.4/3.2.5),
                # so it's only checked here. Digits are counted from the parsed (normalized) value, excluding
                # the sign and any insignificant zeros, per XSD Datatypes 4.3.11.
                if facets and "totalDigits" in facets:
                    _sign, digits, exp = xValue.normalize().as_tuple()
                    assert isinstance(exp, int) # decimalPattern rules out NaN/Infinity, whose exponents aren't ints
                    digitCount = len(digits) + max(0, exp)
                    if digitCount > facets["totalDigits"]:
                        raise ValueError("totalDigits facet {0}".format(facets["totalDigits"]))
            else:
                if floatPattern.match(value) is None:
                    raise ValueError("lexical pattern mismatch")
                xValue = sValue = float(value)
            if facets:
                if "fractionDigits" in facets and ("." in value and
                    len(value[value.index(".") + 1:]) > facets["fractionDigits"]):
                    raise ValueError("fraction digits facet {0}".format(facets["fractionDigits"]))
                if "maxInclusive" in facets and xValue > facets["maxInclusive"]:
                    raise ValueError(" > maxInclusive {0}".format(facets["maxInclusive"]))
                if "maxExclusive" in facets and xValue >= facets["maxExclusive"]:
                    raise ValueError(" >= maxExclusive {0}".format(facets["maxExclusive"]))
                if "minInclusive" in facets and xValue < facets["minInclusive"]:
                    raise ValueError(" < minInclusive {0}".format(facets["minInclusive"]))
                if "minExclusive" in facets and xValue <= facets["minExclusive"]:
                    raise ValueError(" <= minExclusive {0}".format(facets["minExclusive"]))
        elif baseXsdType in _INTEGER_BASE_XSD_TYPES:
            xValue = sValue = int(value)
            if inclusiveBounds := _XSD_TYPE_INHERENT_INCLUSIVE_BOUNDS.get(baseXsdType):
                lowerLimit, upperLimit = inclusiveBounds
                if (lowerLimit is not None and xValue < lowerLimit) or (upperLimit is not None and xValue > upperLimit):
                    raise ValueError(f"{value} is not {baseXsdType}")
            if facets:
                if "totalDigits" in facets and len(str(abs(xValue))) > facets["totalDigits"]:
                    raise ValueError("totalDigits facet {0}".format(facets["totalDigits"]))
                if "fractionDigits" in facets and ("." in value and
                    len(value[value.index(".") + 1:]) > facets["fractionDigits"]):
                    raise ValueError("fraction digits facet {0}".format(facets["fractionDigits"]))
                if "maxInclusive" in facets and xValue > facets["maxInclusive"]:
                    raise ValueError(" > maxInclusive {0}".format(facets["maxInclusive"]))
                if "maxExclusive" in facets and xValue >= facets["maxExclusive"]:
                    raise ValueError(" >= maxExclusive {0}".format(facets["maxExclusive"]))
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
            xValue = qnameFromNsmap(nsmap, value, prefixException=ValueError)
            sValue = value
        elif baseXsdType == "enumerationHrefs":
            xValue = [qnameHref(href) for href in value.split()]
            sValue = value
        elif baseXsdType == "enumerationQNames":
            xValue = [qnameFromNsmap(nsmap, qn, prefixException=ValueError) for qn in value.split()]
            sValue = value
        elif baseXsdType in ("XBRLI_DECIMALSUNION", "XBRLI_PRECISIONUNION"):
            xValue = sValue = value if value == "INF" else int(value)
        elif baseXsdType == "xsd-pattern":
            # for facet compiling
            try:
                sValue = value
                if value in xmlSchemaPatterns:
                    xValue = xmlSchemaPatterns[value]
                else:
                    xValue = XsdPattern.compile(value)
            except Exception as err:
                raise ValueError(err)
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
                    if int(year) == 0:
                        raise ValueError("year zero is not permitted per XSD 1.0")
                    xValue = gYearMonth(year, month)
                elif baseXsdType == "gYear":
                    year, zSign, zHrMin, zHr, zMin = match.groups()
                    if int(year) == 0:
                        raise ValueError("year zero is not permitted per XSD 1.0")
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
            if facets: # ordering facets on date/time/gYear/... (xValue is a comparable type)
                # _orderedComparison tolerates xs:date/time values that mix timezoned and
                # untimezoned operands (which Python won't order); per XSD Datatypes 3.2.6.3
                # ("indeterminate comparisons should be considered as 'false'") an
                # indeterminate order fails the facet test, so the value is rejected rather
                # than accepted or crashing.
                if "maxInclusive" in facets and _orderedComparison(xValue, facets["maxInclusive"]) not in (-1, 0):
                    raise ValueError(" > maxInclusive {0}".format(facets["maxInclusive"]))
                if "maxExclusive" in facets and _orderedComparison(xValue, facets["maxExclusive"]) != -1:
                    raise ValueError(" >= maxExclusive {0}".format(facets["maxExclusive"]))
                if "minInclusive" in facets and _orderedComparison(xValue, facets["minInclusive"]) not in (0, 1):
                    raise ValueError(" < minInclusive {0}".format(facets["minInclusive"]))
                if "minExclusive" in facets and _orderedComparison(xValue, facets["minExclusive"]) != 1:
                    raise ValueError(" <= minExclusive {0}".format(facets["minExclusive"]))
        if facets and "enumeration" in facets and value not in facets["enumeration"]:
            # XSD 1.0 Datatypes 4.3.5: the enumeration facet constrains the value space, so
            # a value is facet-valid when it equals a member in the value space even if its
            # lexical form differs (e.g. dateTime 12:01:01+00:00 vs -00:00, decimal 1.0 vs 1).
            enumeration = facets["enumeration"]
            # Only a schema-derived enumeration facet (a dict of lexical value -> facetElt,
            # possibly an _EnumerationFacet) supports the lazily-populated valueSpace cache;
            # synthetic enumerations built in this module (e.g. for whiteSpace) are plain
            # sets/dicts without facetElts and always fall through to a fresh parse below.
            valueSpace = getattr(enumeration, "valueSpace", None)
            if valueSpace is None:
                valueSpace = {}
                members = (
                    enumeration.items()
                    if isinstance(enumeration, dict)
                    else ((m, None) for m in enumeration)
                )
                for member, facetElt in members:
                    try:
                        # Use the enumeration facet's own schema-document nsmap (not the
                        # validated instance's) since a QName-lexical enumeration member's
                        # namespace bindings are fixed at the schema, per XSD Part 2 §3.2.18.
                        memberNsmap = facetElt.nsmap if facetElt is not None else nsmap
                        parsedMember = _validateValueStringOrRaise(baseXsdType, member, nsmap=memberNsmap)
                        valueSpace[_hashableXValue(parsedMember.xValue)] = member
                    except (ValueError, InvalidOperation, TypeError):
                        pass
                try: # only an _EnumerationFacet (schema-derived enumeration) supports this
                    enumeration.valueSpace = valueSpace
                except AttributeError:
                    pass
            found = _hashableXValue(xValue) in valueSpace
            if not found:
                raise ValueError("{0} is not in {1}".format(value, (
                    facets["enumeration"].keys()
                    if isinstance(facets["enumeration"], dict)
                    else facets["enumeration"])))
    return XmlValidationResult(sValue=sValue, xValue=xValue, xValid=xValid)


def validateValue(
    modelXbrl: ModelXbrl | None,
    elt: ModelObject,
    attrTag: str | None,
    baseXsdType: str | None,
    value: str,
    isNillable: bool = False,
    isNil: bool = False,
    facets: Mapping[str, Any] | None = None,
) -> None:
    sValue: TypeSValue
    xValue: TypeXValue
    if baseXsdType:
        try:
            isNilValue = not value and isNil and isNillable
            if baseXsdType == "fraction" and not isNilValue:
                # Fraction reads numerator/denominator from child elements, not from the value string
                result = fractionValidateValue(value, elt.fractionValue)  # type: ignore[attr-defined]
            else:
                result = _validateValueStringOrRaise(baseXsdType, value, isNillable, isNil, facets, elt.nsmap)
            sValue, xValue, xValid = result.sValue, result.xValue, result.xValid
        except (ValueError, InvalidOperation) as err:
            elt.xValueError = err
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


def _facetTypeAndFacets(facetName: str, baseXsdType: str) -> tuple[str, dict[str, int | set[str]] | None]:
    facets: dict[str, int | set[str]] | None
    if facetName in ("length", "minLength", "maxLength"):
        baseXsdType = "nonNegativeInteger"
        facets = None
    elif facetName == "fractionDigits":
        # Integer and its derived types have fractionDigits fixed at 0 while xs:decimal allows any non-negative value.
        facets = {"maxInclusive": 0} if baseXsdType in _INTEGER_BASE_XSD_TYPES else None
        baseXsdType = "nonNegativeInteger"
    elif facetName == "totalDigits":
        baseXsdType = "positiveInteger"
        facets = None
    elif facetName in ("minInclusive", "maxInclusive"):
        baseXsdType = baseXsdType
        facets = None
    elif facetName in ("minExclusive", "maxExclusive"):
        # Reject values at or outside of the type's bounds, e.g. minExclusive="127" for byte.
        # The facet value itself is valid as a byte but it creates an empty range (nothing > 127)
        # for the value space of the type it restricts. Inclusive bounds don't need this because they
        # overshoot the range by one (minInclusive="128" for byte), which type parsing already rejects.
        facets = None
        if inherentBounds := _XSD_TYPE_INHERENT_INCLUSIVE_BOUNDS.get(baseXsdType):
            lowerLimit, upperLimit = inherentBounds
            if facetName == "minExclusive" and upperLimit is not None:
                facets = {"maxExclusive": upperLimit}
            elif facetName == "maxExclusive" and lowerLimit is not None:
                facets = {"minExclusive": lowerLimit}
    elif facetName == "whiteSpace":
        baseXsdType = "string"
        facets = {"enumeration": {"replace", "preserve", "collapse"}}
    elif facetName == "pattern":
        baseXsdType = "xsd-pattern"
        facets = None
    else:
        baseXsdType = "string"
        facets = None
    return baseXsdType, facets

def validateFacet(typeElt: ModelType, facetElt: ModelObject) -> TypeXValue | None:
    facetName = facetElt.localName
    value = facetElt.get("value")
    facetType, facets = _facetTypeAndFacets(facetName, typeElt.baseXsdType)
    assert value is not None
    validateValue(typeElt.modelXbrl, facetElt, None, facetType, value, facets=facets)
    if facetElt.xValid == VALID:
        return facetElt.xValue
    return None


def validateFacetValueString(facetName: str, facetValue: str, baseXsdType: str) -> XmlValidationResult:
    facetType, facets = _facetTypeAndFacets(facetName, baseXsdType)
    return validateValueString(facetType, facetValue, facets=facets)


def validateAnyWildcard(qnElt: QName, qnAttr: QName, attributeWildcards: list[ModelAnyAttribute]) -> bool:
    # note wildcard is a set of possibly multiple values from inherited attribute groups
    for attributeWildcard in attributeWildcards:
        if attributeWildcard.allowsNamespace(qnAttr.namespaceURI):
            return True
    return False

class lxmlSchemaResolver(etree.Resolver):
    def __init__(self, cntlr: Cntlr, modelXbrl: ModelXbrl | None = None) -> None:
        super(lxmlSchemaResolver, self).__init__()
        self.cntlr = cntlr
        self.modelXbrl = modelXbrl

    def resolve(self, url: str | None, id: str, context: Any) -> Any: #  type: ignore[override]
        _url = url
        if self.modelXbrl is None or not self.modelXbrl.fileSource.isInArchive(url):
            url = self.cntlr.webCache.getfilename(url)
        if url: # may be None if file doesn't exist
            if self.modelXbrl is not None: # use fileSource
                #fh = self.modelXbrl.fileSource.file(url,binary=True)[0]
                #return self.resolve_file(fh, context, base_url=_url, close=True)
                with self.modelXbrl.fileSource.file(url)[0] as fh:
                    xml = fh.read()
                if xml:
                    return self.resolve_string(xml, context, base_url=_url)
            else: # probably no active modelXbrl yet, such as when loading packages, use url
                return self.resolve_filename(url, context)
        return self.resolve_empty(context)

def lxmlResolvingParser(cntlr: Cntlr, modelXbrl: ModelXbrl | None = None) -> etree.XMLParser:
    parser = etree.XMLParser(resolve_entities=False)
    resolver = lxmlSchemaResolver(cntlr, modelXbrl)
    parser.resolvers.add(resolver)
    return parser

def lxmlSchemaValidate(modelDocument: ModelDocument, extraSchema : str | None = None) -> None:
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
                xsdTree = url = None  # type: ignore[assignment]

                if extraSchema:
                    url = extraSchema
                else:
                    for slElt in modelDocument.schemaLocationElements:
                        _sl = (slElt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation") or "").split()
                        for i in range(0, len(_sl), 2):
                            if _sl[i] == ns and i+1 < len(_sl):
                                url = cntlr.webCache.normalizeUrl(_sl[i+1], modelDocument.baseForElement(slElt))
                                break
                if url:
                    try:
                        xsdTree = etree.parse(url, parser=lxmlResolvingParser(cntlr, modelXbrl))  # type: ignore[arg-type]
                    except (EnvironmentError, KeyError, UnicodeDecodeError) as err:
                        msgCode = "arelle.schemaFileError"
                        cntlr.addToLog(_("XML schema validation error: %(error)s"),
                                       messageArgs={"error": str(err)},
                                       messageCode=msgCode,
                                       file=modelDocument.basename,
                                       level=logging.INFO) # schemaLocation is just a hint
                        modelDocument.modelXbrl.errors.append(msgCode)
            if xsdTree is None:
                return # no schema to validate
            docTree = modelDocument.xmlRootElement.getroottree()
            etreeXMLSchema = etree.XMLSchema(xsdTree)
            etreeXMLSchema.assertValid(docTree)
        except etree.DocumentInvalid as err:
            nsmap = {
                key: val
                for key, val in docTree.getroot().nsmap.items()
                if key
            }
            for e in err.error_log:
                if not any(s in e.message for s in (": The QName value", "is not a valid value of the atomic type 'xs:QName'")):
                    # do newer lxml validations have QName whitespace collapsing issue?
                    userFriendlyElementPath = ''
                    errorElements = docTree.xpath(e.path, namespaces=nsmap)  # type: ignore[arg-type]
                    if len(errorElements) == 1:
                        userFriendlyElementPath = docTree.getelementpath(errorElements[0])
                        for prefix, namespace in docTree.getroot().nsmap.items():
                            replacementText = f"{prefix}:" if prefix else ''
                            userFriendlyElementPath = userFriendlyElementPath.replace(f"{{{namespace}}}", replacementText)
                    msgCode = f"lxml.{e.type_name}"
                    cntlr.addToLog(_("XML file syntax error %(error)s, line %(sourceLine)s, path '%(path)s', xpath '%(xpath)s'"),
                                   messageArgs={"error": e.message,
                                                "path": userFriendlyElementPath,
                                                "xpath": e.path,
                                                "sourceLine": e.line},
                                   messageCode=msgCode,
                                   file=modelDocument.basename,
                                   level=logging.ERROR)
                    modelDocument.modelXbrl.errors.append(msgCode)
        except (etree.XMLSyntaxError, etree.XMLSchemaError) as err:
            msgCode = "lxml.schemaError"
            cntlr.addToLog(_("XML file syntax error %(error)s"),
                           messageArgs={"error": str(err)},
                           messageCode=msgCode,
                           file=modelDocument.basename,
                           level=logging.ERROR)
            modelDocument.modelXbrl.errors.append(msgCode)
