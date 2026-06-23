"""
:mod:`arelle.ModelInstanceObjuect`
~~~~~~~~~~~~~~~~~~~

.. module:: arelle.ModelInstanceObject
   :copyright: See COPYRIGHT.md for copyright information.
   :license: Apache-2.
   :synopsis: This module contains Instance-specialized ModelObject classes: ModelFact (xbrli:item
   and xbrli:tuple elements of an instance document), ModelInlineFact specializes ModelFact when
   in an inline XBRL document, ModelContext (xblrli:context element), ModelDimensionValue
   (xbrldi:explicitMember and xbrli:typedMember elements), and ModelUnit (xbrli:unit elements).

    Model facts represent XBRL instance facts (that are elements in the instance document).
    Model inline facts represent facts in a source xhtml document, but may accumulate text
    across multiple mixed-content elements in the instance document, according to the rendering
    transform in effect.  All inline facts are lxml proxy objects for the inline fact and have a
    cached value representing the transformed value content.  PSVI values for the inline fact's
    value and attributes are on the model inline fact object (not necessarily the element that
    held the mixed-content text).

    Model context objects are the lxml proxy object of the context XML element, but cache and
    interface context semantics that may either be internal to the context, or inferred from
    the DTS (such as default dimension values).   PSVI values for elements internal to the context,
    including segment and scenario elements, are on the individual model object lxml custom proxy
    elements.  For fast comparison of dimensions and segment/scenario, hash values are retained
    for each comparable item.

    Model dimension objects not only represent proxy objects for the XML elements, but have resolved
    model DTS concepts of the dimension and member, and access to the typed member contents.

    Model unit objects represent algebraically usable set objects for the numerator and denominator
    measure sets.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Callable, Iterator, TYPE_CHECKING, Sequence
from arelle import XmlUtil, XbrlConst, XbrlUtil, Locale, ModelValue
from arelle.Aspect import Aspect
from arelle.ModelDocumentType import ModelDocumentType
from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals, roundValue, rangeValue, ValidateCalcsMode
from arelle.XmlValidateConst import UNVALIDATED, INVALID, VALID
from arelle.XmlValidate import validate as xmlValidate
from arelle.XmlUtil import collapseWhitespace
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.ModelDtsObject import ModelResource
from arelle.typing import ModelFactBase
from math import isnan, isinf
from arelle.ModelObject import ModelObject
from decimal import Decimal, InvalidOperation
from hashlib import md5
from arelle.HashUtil import md5hash, Md5Sum

if TYPE_CHECKING:
    from datetime import date, datetime
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelDtsObject import ModelConcept, ModelType
    from arelle.ModelValue import QName
    from arelle.ValidateUtr import UtrEntry
    from arelle.ModelDtsObject import ModelLink
    from arelle.PrototypeDtsObject import LinkPrototype

utrEntries: Callable[..., Any] | None = None
utrSymbol: Callable[..., Any] | None = None
POSINF = float("inf")
NEGINF = float("-inf")
DECIMALONE = Decimal(1)


class NewFactItemOptions:
    """
    .. class:: NewFactItemOptions(savedOptions=None, xbrlInstance=None)

    NewFactItemOptions persists contextual parameters for interactive creation of new facts,
    such as when entering into empty table linkbase rendering pane cells.

    If savedOptions is provided (from configuration saved json file), then persisted last used
    values of item contextual options are used.  If no saved options, then the first fact in
    an existing instance (xbrlInstance) is used to glean prototype contextual parameters.

    Note that all attributes of this class must be compatible with json conversion, e.g., datetime
    must be persisted in string, not datetime object, form.

    Properties of this class (all str):

    - entityIdentScheme
    - entityIdentValue
    - startDate
    - endDate
    - monetaryUnit (str prefix:localName, e.g, iso4217:JPY)
    - monetaryDecimals (decimals attribute for numeric monetary facts)
    - nonMonetaryDecimals (decimals attribute for numeric non-monetary facts, e.g., shares)

    :param savedOptions: prior persisted dict of this class's attributes
    :param xbrlInstance: an open instance document from which to glean prototpye contextual parameters.
    """
    def __init__(self, savedOptions: dict[str, Any] | None = None, xbrlInstance: Any = None) -> None:
        self.entityIdentScheme = ""
        self.entityIdentValue = ""
        self.startDate = ""  # use string values so structure can be json-saved
        self.endDate = ""
        self.monetaryUnit = ""
        self.monetaryDecimals = ""
        self.nonMonetaryDecimals = ""
        if savedOptions is not None:
            self.__dict__.update(savedOptions)
        elif xbrlInstance is not None:
            for fact in xbrlInstance.facts:
                cntx = fact.context
                unit = fact.unit
                if fact.isItem and cntx is not None:
                    if not self.entityIdentScheme:
                        self.entityIdentScheme, self.entityIdentValue = cntx.entityIdentifier
                    if not self.startDate and cntx.isStartEndPeriod:
                        self.startDate = XmlUtil.dateunionValue(cntx.startDatetime)
                    if not self.startDate and (cntx.isStartEndPeriod or cntx.isInstantPeriod):
                        self.endDate = XmlUtil.dateunionValue(cntx.endDatetime, subtractOneDay=True)
                    if fact.isNumeric and unit is not None:
                        if fact.concept.isMonetary:
                            if not self.monetaryUnit and unit.measures[0] and unit.measures[0][0].namespaceURI == XbrlConst.iso4217:
                                self.monetaryUnit = unit.measures[0][0].localName
                            if not self.monetaryDecimals:
                                self.monetaryDecimals = fact.decimals
                        elif not self.nonMonetaryDecimals:
                            self.nonMonetaryDecimals = fact.decimals
                if self.entityIdentScheme and self.startDate and self.monetaryUnit and self.monetaryDecimals and self.nonMonetaryDecimals:
                    break

    @property
    def startDateDate(self) -> datetime | None:
        """(datetime) -- date-typed date value of startDate (which is persisted in str form)"""
        return XmlUtil.datetimeValue(self.startDate)

    @property
    def endDateDate(self) -> datetime | None:  # return a date-typed date
        """(datetime) -- date-typed date value of endDate (which is persisted in str form)"""
        return XmlUtil.datetimeValue(self.endDate, addOneDay=True)


class ModelFact(ModelObject, ModelFactBase):
    """
    .. class:: ModelFact(modelDocument)

    Model fact (both instance document facts and inline XBRL facts)

    :param modelDocument: owner document
    :type modelDocument: ModelDocument

        .. attribute:: modelTupleFacts

        ([ModelFact]) - List of child facts in source document order
    """
    modelTupleFacts: list["ModelFact"]
    uniqueUUID: uuid.UUID
    _context: ModelContext | None
    _conceptContextUnitHash: int
    _isItem: bool
    _isTuple: bool
    _isNumeric: bool
    _isInteger: bool
    _isFraction: bool
    _ancestorQnames: set[QName]
    _decimals: str | None
    _precision: str | None
    _fractionValue: tuple[str, str]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelFact, self).init(modelDocument)
        self.modelTupleFacts = []
        self.uniqueUUID = uuid.uuid4()

    @property
    def concept(self) -> ModelConcept | None:
        """(ModelConcept) -- concept of the fact."""
        return self.elementDeclaration()  # logical (fact) declaration in own modelXbrl, not physical element (if inline)

    @property
    def contextID(self) -> str | None:
        """(str) -- contextRef attribute"""
        return self.get("contextRef")

    @property
    def context(self) -> ModelContext | None:
        """(ModelContext) -- context of the fact if any else None (e.g., tuple)"""
        try:
            return self._context
        except AttributeError:
            if not self.modelXbrl.contexts: return None  # type: ignore[union-attr] # don't attempt before contexts are loaded
            self._context = self.modelXbrl.contexts.get(self.contextID)  # type: ignore[arg-type,union-attr]
            return self._context

    @property
    def unit(self) -> ModelUnit | None:
        """(ModelUnit) -- unit of the fact if any else None (e.g., non-numeric or tuple)"""
        return self.modelXbrl.units.get(self.unitID)  # type: ignore[arg-type,union-attr]

    @property
    def unitID(self) -> str | None:
        """(str) -- unitRef attribute"""
        return self.getStripped("unitRef")

    @unitID.setter
    def unitID(self, value: str) -> None:
        """(str) -- unitRef attribute"""
        self.set("unitRef", value)

    @property
    def utrEntries(self) -> set[UtrEntry | None] | None:
        """(set(UtrEntry)) -- set of UtrEntry objects that match this fact and unit"""
        if self.unit is not None and self.concept is not None:
            return self.unit.utrEntries(self.concept.type)  # type: ignore[arg-type]
        return None

    def unitSymbol(self) -> str:
        """(str) -- utr symbol for this fact and unit"""
        if self.unit is not None and self.concept is not None:
            return self.unit.utrSymbol(self.concept.type)  # type: ignore[arg-type]
        return ""

    @property
    def conceptContextUnitHash(self) -> int:
        """(int) -- Hash value of fact's concept QName, dimensions-aware
        context hash, unit hash, useful for fast comparison of facts for EFM 6.5.12"""
        try:
            return self._conceptContextUnitHash
        except AttributeError:
            context = self.context
            unit = self.unit
            self._conceptContextUnitHash = hash(
                (self.qname,
                 context.contextDimAwareHash if context is not None else None,
                 unit.hash if unit is not None else None)
            )
            return self._conceptContextUnitHash

    @property
    def isItem(self) -> bool:
        """(bool) -- concept.isItem"""
        try:
            return self._isItem
        except AttributeError:
            concept = self.concept
            self._isItem = concept is not None and concept.isItem
            return self._isItem

    @property
    def isTuple(self) -> bool:
        """(bool) -- concept.isTuple"""
        try:
            return self._isTuple
        except AttributeError:
            concept = self.concept
            self._isTuple = concept is not None and concept.isTuple
            return self._isTuple

    @property
    def isNumeric(self) -> bool:  # type: ignore[override]
        """(bool) -- concept.isNumeric (note this is false for fractions)"""
        try:
            return self._isNumeric
        except AttributeError:
            concept = self.concept
            self._isNumeric = concept is not None and concept.isNumeric
            return self._isNumeric

    @property
    def isInteger(self) -> bool:
        """(bool) -- concept.isInteger (note this is false for fractions)"""
        try:
            return self._isInteger
        except AttributeError:
            concept = self.concept
            self._isInteger = concept is not None and concept.isInteger
            return self._isInteger

    @property
    def isMultiLanguage(self) -> bool:
        """(bool) -- concept.type.isMultiLanguage (string or normalized string)"""
        concept = self.concept
        return concept is not None and concept.type is not None and concept.type.isMultiLanguage

    @property
    def isFraction(self) -> bool:
        """(bool) -- concept.isFraction"""
        try:
            return self._isFraction
        except AttributeError:
            concept = self.concept
            self._isFraction = concept is not None and concept.isFraction
            return self._isFraction

    @property
    def parentElement(self) -> ModelObject | None:
        """(ModelObject) -- parent element (tuple or xbrli:xbrl)"""
        return self.getparent()

    @property
    def ancestorQnames(self) -> set[QName]:
        """(set) -- Set of QNames of ancestor elements (tuple and xbrli:xbrl)"""
        try:
            return self._ancestorQnames
        except AttributeError:
            self._ancestorQnames = set(ModelValue.qname(ancestor) for ancestor in self.iterancestors())
            return self._ancestorQnames

    @property
    def decimals(self) -> str | None:
        """(str) -- Value of decimals attribute, or fixed or default value for decimals on concept type declaration"""
        try:
            return self._decimals
        except AttributeError:
            decimals = self.get("decimals")
            if decimals:
                self._decimals = decimals
            else:   #check for fixed decimals on type
                concept = self.concept
                if concept is not None:
                    type = concept.type
                    self._decimals = type.fixedOrDefaultAttrValue("decimals") if type is not None else None
                else:
                    self._decimals = None
            return  self._decimals

    @decimals.setter
    def decimals(self, value: str) -> None:
        self._decimals = value
        self.set("decimals", value)

    @property
    def precision(self) -> str | None:
        """(str) -- Value of precision attribute, or fixed or default value for precision on concept type declaration"""
        try:
            return self._precision
        except AttributeError:
            precision = self.get("precision")
            if precision:
                self._precision = precision
            else:   #check for fixed decimals on type
                concept = self.concept
                if concept is not None:
                    type = self.concept.type  # type: ignore[union-attr]
                    self._precision = type.fixedOrDefaultAttrValue("precision") if type is not None else None
                else:
                    self._precision = None
            return self._precision

    @property
    def xmlLang(self) -> str | None:  # type: ignore[override]
        """(str) -- xml:lang attribute, if none and non-numeric, disclosure-system specified default lang"""
        lang = self.get("{http://www.w3.org/XML/1998/namespace}lang")
        if lang is not None:
            return lang
        parentElt = self.parentElement
        if isinstance(parentElt, ModelFact):
            return parentElt.xmlLang
        elif isinstance(parentElt, ModelObject): # top-level fact is parented by xbrli:xbrl which isn't a fact
            lang = parentElt.get("{http://www.w3.org/XML/1998/namespace}lang")
            if lang is not None:
                return lang
        # if we got here there is no xml:lang on fact or ancestry
        if self.modelXbrl.modelManager.validateDisclosureSystem:  # type: ignore[union-attr] # use disclosureSystem's defaultXmlLang (if any)
            concept = self.concept
            if concept is not None and not concept.isNumeric:
                lang = self.modelXbrl.modelManager.disclosureSystem.defaultXmlLang  # type: ignore[union-attr]
        return lang

    @property
    def xsiNil(self) -> str:
        """(str) -- value of xsi:nil or 'false' if absent"""
        return self.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "false")

    @property
    def isNil(self) -> bool:
        """(bool) -- True if xsi:nil is 'true'"""
        return self.xsiNil in ("true", "1")

    @isNil.setter
    def isNil(self, value: bool) -> None:
        """:param value: if true, set xsi:nil to 'true', if false, remove xsi:nil attribute """
        if value:
            XmlUtil.setXmlns(self.modelDocument, "xsi", "http://www.w3.org/2001/XMLSchema-instance")
            self.set("{http://www.w3.org/2001/XMLSchema-instance}nil", "true")
            self.attrib.pop("decimals", "0")  # can't leave decimals or precision
            self.attrib.pop("precision", "0")
            del self._decimals
            del self._precision
        else: # also remove decimals and precision, if they were there
            self.attrib.pop("{http://www.w3.org/2001/XMLSchema-instance}nil", "false")

    @property
    def value(self) -> str:
        """(str) -- Text value of fact or default or fixed if any, otherwise None"""
        v = self.textValue
        if not v and self.concept is not None:
            if self.concept.default is not None:
                v = self.concept.default
            elif self.concept.fixed is not None:
                v = self.concept.fixed
        return v

    @property
    def fractionValue(self) -> tuple[str, str]:
        """( (str,str) ) -- (text value of numerator, text value of denominator)"""
        try:
            return self._fractionValue
        except AttributeError:
            self._fractionValue = (XmlUtil.text(XmlUtil.child(self, None, "numerator")),  # type: ignore[arg-type]
                                   XmlUtil.text(XmlUtil.child(self, None, "denominator")))  # type: ignore[arg-type]
            return self._fractionValue

    @property
    def effectiveValue(self) -> str | None:
        """(str) -- Effective value for views, (nil) if isNil, None if no value,
        locale-formatted string of decimal value (if decimals specified) , otherwise string value"""
        concept = self.concept
        if concept is None or concept.isTuple:
            return None
        if self.isNil:
            return "(nil)"
        try:
            if concept.isFraction:
                if self.xValid >= VALID:
                    return str(self.xValue)
                return "/".join(self.fractionValue)
            val = self.value
            if concept.isNumeric:
                try:
                    # num = float(val)
                    dec = self.decimals
                    num = roundValue(val, self.precision, dec) # round using reported decimals
                    if isinf(num):
                        return "-INF" if num < 0 else "INF"
                    elif isnan(num):
                        return "NaN"
                    else:
                        if dec is None or dec == "INF":  # show using decimals or reported format
                            dec = len(val.partition(".")[2])  # type: ignore[assignment]
                        else: # max decimals at 28
                            dec = max(min(int(dec), 28), -28)  # type: ignore[assignment]
                        # return Locale.format(self.modelXbrl.locale, "%.*f", (dec, num), True)
                        # switch to new formatting so long-precision decimal numbers are correct
                        if dec < 0:  # type: ignore[operator]
                            dec = 0  # type: ignore[assignment] # {} formatting doesn't accept negative dec
                        return Locale.format(self.modelXbrl.locale, "{:.{}f}", (num, dec), True)  # type: ignore[arg-type,union-attr]
                except ValueError:
                    return "(error)"
            # non-numeric fact at this point
            if len(val) == 0: # zero length string for HMRC fixed fact
                return "(reported)"
            if self.xValid >= VALID and isinstance(self.xValue, str):
                # Prefer the xs:whiteSpace normalized version of strings
                return self.xValue
            return val
        except Exception as ex:
            return str(ex)  # could be transform value of inline fact

    @property
    def vEqValue(self) -> float | str:
        """(float or str) -- v-equal value, float if numeric, otherwise string value"""
        if self.concept.isNumeric:  # type: ignore[union-attr]
            return float(self.value)
        return self.value

    def isVEqualTo(
            self,
            other: ModelFact,
            deemP0Equal: bool = False,
            deemP0inf: bool = False,
            normalizeSpace: bool = True,
            numericIntervalConsistency: bool = False
        ) -> bool:
        """(bool) -- v-equality of two facts

        Note that facts may be in different instances
        """
        if self.isTuple or other.isTuple:
            return False
        if self.context is None or self.concept is None:
            return False # need valid context and concept for v-Equality of nonTuple
        if self.isNil:
            return other.isNil
        if other.isNil:
            return False
        if not self.context.isEqualTo(other.context):
            return False
        if self.concept.isNumeric:
            if other.concept.isNumeric:  # type: ignore[union-attr]
                if self.unit is None or not self.unit.isEqualTo(other.unit):
                    return False

                if numericIntervalConsistency: # values consistent with being rounded from same number
                    (a1,b1,_ia1,_ib2) = rangeValue(self.value, inferredDecimals(self))
                    (a2,b2,_ia2,_ib2) = rangeValue(other.value, inferredDecimals(other))
                    return not (b1 < a2 or b2 < a1)

                if self.modelXbrl.modelManager.validateCalcs != ValidateCalcsMode.XBRL_v2_1_INFER_PRECISION:  # type: ignore[union-attr]
                    d = min((inferredDecimals(self), inferredDecimals(other)))
                    p = None
                    if isnan(d):
                        if deemP0Equal:
                            return True
                        elif deemP0inf: # for test cases deem P0 as INF comparison
                            return self.xValue == other.xValue
                else: # pre-2010 XBRL 2.1 inferred precision
                    d = None
                    p = min((inferredPrecision(self), inferredPrecision(other)))
                    if p == 0:
                        if deemP0Equal:
                            return True
                        elif deemP0inf: # for test cases deem P0 as INF comparison
                            return self.xValue == other.xValue
                return roundValue(self.value, precision=p, decimals=d) == roundValue(other.value, precision=p, decimals=d)
            else:
                return False
        elif self.concept.isFraction:
            return (other.concept.isFraction and  # type: ignore[union-attr]
                    self.unit is not None and
                    self.unit.isEqualTo(other.unit) and
                    self.xValue == other.xValue)
        selfValue = self.value
        otherValue = other.value
        if normalizeSpace and isinstance(selfValue, str) and isinstance(otherValue, str): # normalized space comparison
            return " ".join(selfValue.split()) == " ".join(otherValue.split())
        else:
            return selfValue == otherValue

    def isDuplicateOf(
            self,
            other: ModelFact,
            topLevel: bool = True,
            deemP0Equal: bool = False,
            unmatchedFactsStack: list[ModelFact] | None = None
        ) -> bool:
        """(bool) -- fact is duplicate of other fact

        Note that facts may be in different instances

        :param topLevel:  fact parent is xbrli:instance, otherwise nested in a tuple
        :type topLevel: bool
        :param deemPOEqual: True to deem any precision=0 facts equal ignoring value
        :type deepPOEqual: bool
        """
        if unmatchedFactsStack is not None:
            if topLevel: del unmatchedFactsStack[0:]
            entryDepth = len(unmatchedFactsStack)
            unmatchedFactsStack.append(self)
        if self.isItem:
            if (self == other or
                self.qname != other.qname or
                self.parentElement.qname != other.parentElement.qname):  # type: ignore[union-attr]
                return False    # can't be identical
            # parent test can only be done if in same instauce
            if self.modelXbrl == other.modelXbrl and self.parentElement != other.parentElement:
                return False
            if not (self.context is not None and self.context.isEqualTo(other.context,dimensionalAspectModel=False) and
                    (not self.isNumeric or (self.unit is not None and self.unit.isEqualTo(other.unit)))):
                return False
        elif self.isTuple:
            if (self == other or
                self.qname != other.qname or
                (topLevel and self.parentElement.qname != other.parentElement.qname)):  # type: ignore[union-attr]
                return False  # can't be identical
            if len(self.modelTupleFacts) != len(other.modelTupleFacts):
                return False
            for child1 in self.modelTupleFacts:
                if child1.isItem:
                    if not any(child1.isVEqualTo(child2, deemP0Equal) for child2 in other.modelTupleFacts if child1.qname == child2.qname):
                        return False
                elif child1.isTuple:
                    if not any(child1.isDuplicateOf( child2, False, deemP0Equal, unmatchedFactsStack)
                               for child2 in other.modelTupleFacts):
                        return False
        else:
            return False
        if unmatchedFactsStack is not None:
            del unmatchedFactsStack[entryDepth:]
        return True

    @property
    def md5sum(self) -> Md5Sum:  # note this must work in --skipDTS and streaming modes
        _toHash: list[str | QName | Md5Sum] = [self.qname]
        if self.context is not None: # not a tuple and has a valid unit
            # don't use self.xmlLang because its value may depend on disclosure system (assumption)
            _lang = XmlUtil.ancestorOrSelfAttr(self, "{http://www.w3.org/XML/1998/namespace}lang")
            if _lang:
                _toHash.append(XbrlConst.qnXmlLang)
                _toHash.append(_lang)
            if self.isNil:
                _toHash.append(XbrlConst.qnXsiNil)
                _toHash.append("true")
            elif self.value:
                _toHash.append(self.value)
            _toHash.append(self.context.md5sum)
            if self.unit is not None:
                _toHash.append(self.unit.md5sum)
        return md5hash(_toHash)

    @property
    def propertyView(self) -> tuple[tuple[str, str | QName | None], ...]:
        try:
            concept = self.concept
            lbl = (("label", concept.label(lang=self.modelXbrl.modelManager.defaultLang)),)  # type: ignore[union-attr]
        except (KeyError, AttributeError):
            lbl = ()  # type: ignore[assignment]
        if self.isNumeric and self.unit is not None:
            unitValue = self.unitID
            unitSymbol = self.unitSymbol()
            if unitSymbol:
                unitValue += " (" + unitSymbol + ")"  # type: ignore[operator]
        return lbl + (
               (("namespace", self.qname.namespaceURI),  # type: ignore[operator]
                ("name", self.qname.localName),
                ("QName", self.qname)) +
               (((("contextRef", self.contextID, self.context.propertyView) if self.context is not None else ()),
                 (("unitRef", unitValue, self.unit.propertyView) if self.isNumeric and self.unit is not None else ()),
                 ("decimals", self.decimals),
                 ("precision", self.precision),
                 ("xsi:nil", self.xsiNil),
                 ("value", self.effectiveValue))
                 if self.isItem else ()))

    def __repr__(self) -> str:
        return ("modelFact[{0}, qname: {1}, contextRef: {2}, unitRef: {3}, value: {4}, {5}, line {6}]"
                .format(self.objectIndex, self.qname, self.get("contextRef"), self.get("unitRef"),
                        self.effectiveValue.strip() if self.isItem else "(tuple)",  # type: ignore[union-attr]
                        self.modelDocument.basename, self.sourceline))

    @property
    def viewConcept(self) -> ModelConcept | None:
        return self.concept


class ModelInlineValueObject:

    xValue: Any
    xValid: int
    isNil: bool
    isInteger: bool
    localName: str
    elementQname: QName
    namespaceURI: str
    modelXbrl: Any
    _ixValue: str

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInlineValueObject, self).init(modelDocument)  # type: ignore[misc]

    @property
    def sign(self) -> str | None:
        """(str) -- sign attribute of inline element"""
        return self.get("sign")  # type: ignore[attr-defined,no-any-return]

    @property
    def format(self) -> QName | None:
        """(QName) -- format attribute of inline element"""
        return self.prefixedNameQname(self.getStripped("format"))  # type: ignore[attr-defined,no-any-return]

    @property
    def scale(self) -> str | None:
        """(str) -- scale attribute of inline element"""
        return self.getStripped("scale")  # type: ignore[attr-defined,no-any-return]

    @property
    def scaleInt(self) -> int | None:
        """(int) -- scale attribute of inline element"""
        try:
            _scale = self.get("scale")  # type: ignore[attr-defined]
            if _scale is None:
                return None
            return int(_scale)
        except ValueError:
            return None # should have rasied a validation error in XhtmlValidate.py

    def setInvalid(self) -> None:
        self._ixValue = ModelValue.INVALIDixVALUE
        self.xValid = INVALID
        self.xValue = None

    @property
    def rawValue(self) -> str:
        ixEscape = self.get("escape") in ("true", "1")  # type: ignore[attr-defined]
        raw = XmlUtil.innerText(
            self,  # type: ignore[arg-type]
            ixExclude="tuple" if self.elementQname == XbrlConst.qnIXbrl11Tuple else "html",  # type: ignore[arg-type]
            ixEscape=ixEscape,  # type: ignore[arg-type]
            ixContinuation=(self.elementQname == XbrlConst.qnIXbrl11NonNumeric),
            ixResolveUris=ixEscape,
            strip = False)
        if self.format is not None:
            # Most transforms are whitespace-collapse, so do that now.
            #
            # TODO: this collapsing should be moved to the individual
            # transformation functions in order to support non-collapsing
            # transformations
            raw = collapseWhitespace(raw)
        return raw

    @property
    def value(self) -> str:
        """(str) -- Overrides and corresponds to value property of ModelFact,
        for relevant inner text nodes aggregated and transformed as needed."""
        try:
            return self._ixValue
        except AttributeError:
            self.xValid = UNVALIDATED # may not be initialized otherwise
            self.xValue = None
            f = self.format
            v = self.rawValue
            if f is not None:
                if f.namespaceURI in FunctionIxt.ixtNamespaceFunctions:
                    try:
                        v = FunctionIxt.ixtNamespaceFunctions[f.namespaceURI][f.localName](v)
                    except Exception as err:
                        self.setInvalid()
                        raise err
                else:
                    try:
                        v = self.modelXbrl.modelManager.customTransforms[f](v)
                    except KeyError as err:
                        self.setInvalid()
                        raise FunctionIxt.ixtFunctionNotAvailable
                    except Exception as err:
                        self.setInvalid()
                        raise err
            if self.isNil:
                self._ixValue = v
            else:
                if self.localName == "nonNumeric":
                    if self.xValid >= VALID:
                        self._ixValue = str(self.xValue)
                    else:
                        self._ixValue = v
                elif self.localName == "tuple":
                    self._ixValue = ""
                elif self.localName == "fraction":
                    if self.xValid >= VALID:
                        self._ixValue = str(self.xValue)
                    else:
                        self._ixValue = "NaN"
                else:  # determine string value of transformed value
                    negate = -1 if self.sign else 1
                    try:
                        # concept may be unknown or invalid but transformation would still occur
                        # use decimal so all number forms work properly
                        num = Decimal(v)
                    except (ValueError, InvalidOperation):
                        self.setInvalid()
                        raise ValueError("Invalid value for {} number: '{}'".format(self.localName, v))
                    try:
                        scale = self.scale
                        if scale is not None:
                            num *= 10 ** Decimal(scale)
                        num *= negate
                        if isinf(num):
                            self._ixValue = "-INF" if num < 0 else "INF"
                        elif isnan(num):
                            self._ixValue = "NaN"
                        else:
                            if num == num.to_integral() and (".0" not in v or self.isInteger):
                                num = num.quantize(DECIMALONE) # drop any .0
                            self._ixValue = "{:f}".format(num)
                    except (ValueError, InvalidOperation):
                        self.setInvalid()
                        raise ValueError("Invalid value for {} scale '{}' for number '{}'".format(self.localName, scale, v))
            return self._ixValue

    @property
    def textValue(self) -> str:
        """(str) -- override xml-level textValue for transformed value text()
            will raise any value errors if transforming string or numeric has an error
        """
        return self.value

    @property
    def stringValue(self) -> str:
        """(str) -- override xml-level stringValue for transformed value descendants text
            will raise any value errors if transforming string or numeric has an error
        """
        return self.value


class ModelInlineFact(ModelInlineValueObject, ModelFact):
    """
    .. class:: ModelInlineFact(modelDocument)

    Model inline fact (inline XBRL facts)

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    modelTupleFacts: list["ModelInlineFact"]  # type: ignore[assignment]
    _factQname: QName | None
    _tupleId: str | None
    _tupleRef: str | None
    _order: Decimal | None  # type: ignore[assignment]
    _isEscaped: bool

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInlineFact, self).init(modelDocument)

    @property
    def qname(self) -> QName | None:  # type: ignore[override]
        """(QName) -- QName of concept from the name attribute, overrides and corresponds to the qname property of a ModelFact (inherited from ModelObject)"""
        try:
            return self._factQname
        except AttributeError:
            self._factQname = self.prefixedNameQname(self.get("name")) if self.get("name") else None
            return self._factQname

    @property
    def tupleID(self) -> str | None:
        """(str) -- tupleId attribute of inline element"""
        try:
            return self._tupleId
        except AttributeError:
            self._tupleId = self.get("tupleID")
            return self._tupleId

    @property
    def tupleRef(self) -> str | None:
        """(str) -- tupleRef attribute of inline element"""
        try:
            return self._tupleRef
        except AttributeError:
            self._tupleRef = self.get("tupleRef")
            return self._tupleRef

    @property
    def order(self) -> Decimal | None:
        """(Decimal) -- order attribute of inline element or None if absent or Decimal conversion error"""
        try:
            return self._order
        except AttributeError:
            try:
                orderAttr = self.get("order")
                self._order = Decimal(orderAttr)  # type: ignore[arg-type]
            except (ValueError, TypeError, InvalidOperation):
                self._order = None
            return self._order

    @property
    def parentElement(self) -> ModelObject | None:
        """(ModelObject) -- parent element (tuple or xbrli:xbrl) of the inline target instance document
            for inline root element, the xbrli:xbrl element is substituted for by the inline root element"""
        return getattr(self, "_ixFactParent")  # type: ignore[no-any-return] # set by ModelDocument locateFactInTuple for the inline target's root element

    @property
    def isEscaped(self) -> bool:
        """(bool) -- if true, the fact is escaped"""
        try:
            return self._isEscaped
        except AttributeError:
            self._isEscaped = self.get("escape") in ("true", "1")
            return self._isEscaped

    def ixIter(self, childOnly: bool = False) -> Iterator[ModelInlineFact]:
        """(ModelObject) -- child elements (tuple facts) of the inline target instance document"""
        for fact in self.modelTupleFacts:
            yield fact
            if not childOnly:
                fact.ixIter(childOnly)

    @property
    def fractionValue(self) -> tuple[str, str]:
        """( (str,str) ) -- (text value of numerator, text value of denominator)"""
        return (XmlUtil.text(XmlUtil.descendant(self, self.namespaceURI, "numerator")),  # type: ignore[arg-type]
                XmlUtil.text(XmlUtil.descendant(self, self.namespaceURI, "denominator")))  # type: ignore[arg-type]

    @property
    def footnoteRefs(self) -> list[str]:
        """([str]) -- list of footnoteRefs attribute contents of inline 1.0 element"""
        return self.get("footnoteRefs", "").split()

    def __iter__(self) -> Iterator[ModelObject]:  # type: ignore[override]
        if self.localName == "fraction":
            n = XmlUtil.descendant(self, self.namespaceURI, "numerator")
            d = XmlUtil.descendant(self, self.namespaceURI, "denominator")
            if n is not None and d is not None:
                yield n  # type: ignore[misc]
                yield d  # type: ignore[misc]
        for tupleFact in self.modelTupleFacts:
            yield tupleFact

    @property
    def propertyView(self) -> tuple[tuple[str, str | int | QName | None], ...]:  # type: ignore[override]
        if self.localName == "nonFraction" or self.localName == "fraction":
            numProperties = (("format", self.format),
                ("scale", self.scale),
                ("html value", XmlUtil.innerText(self)))
        else:
            numProperties = ()  # type: ignore[assignment]
        return (("file", self.modelDocument.basename),
                ("line", self.sourceline)) + \
               super(ModelInlineFact, self).propertyView + \
               numProperties

    def __repr__(self) -> str:
        return "modelInlineFact[{0}]{1})".format(self.objectId(), self.propertyView)


class ModelInlineFraction(ModelInlineFact):
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInlineFraction, self).init(modelDocument)

    @property
    def textValue(self) -> str:
        return ""  # no text value for fraction


class ModelInlineFractionTerm(ModelInlineValueObject, ModelObject):
    modelTupleFacts: list["ModelInlineFractionTerm"]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInlineFractionTerm, self).init(modelDocument)
        self.isNil = False # required for inherited value property
        self.modelTupleFacts = [] # required for inherited XmlValudate of fraction term

    @property
    def qname(self) -> QName:
        if self.localName == "numerator":
            return XbrlConst.qnXbrliNumerator
        elif self.localName == "denominator":
            return XbrlConst.qnXbrliDenominator
        return self.elementQname

    @property
    def concept(self) -> ModelConcept | None:
        return self.modelXbrl.qnameConcepts.get(self.qname)  # type: ignore[no-any-return] # for fraction term type determination

    @property
    def isInteger(self) -> bool:  # type: ignore[override]
        return False # fraction terms are xs:decimal

    def __iter__(self) -> Iterator[Any]:
        if False:
            yield None # generator with nothing to generate


class ModelContext(ModelObject):
    """
    .. class:: ModelContext(modelDocument)

    Model context

    :param modelDocument: owner document
    :type modelDocument: ModelDocument

        .. attribute:: segDimValues

        (dict) - Dict by dimension ModelConcept of segment dimension ModelDimensionValues

        .. attribute:: scenDimValues

        (dict) - Dict by dimension ModelConcept of scenario dimension ModelDimensionValues

        .. attribute:: qnameDims

        (dict) - Dict by dimension concept QName of ModelDimensionValues (independent of whether segment or scenario)

        .. attribute:: errorDimValues

        (list) - List of ModelDimensionValues whose dimension concept could not be determined or which were duplicates

        .. attribute:: segNonDimValues

        (list) - List of segment child non-dimension ModelObjects

        .. attribute:: scenNonDimValues

        (list) - List of scenario child non-dimension ModelObjects
    """
    _inUse: bool
    _isStartEndPeriod: bool
    _isInstantPeriod: bool
    _isForeverPeriod: bool
    _startDatetime: datetime | None
    _endDate: date | None
    _endDatetime: datetime | None
    _instantDate: date | None
    _instantDatetime: datetime | None
    _period: ModelObject | None
    _periodHash: int
    _entity: ModelObject | None
    _entityIdentifierElement: ModelObject | None
    _entityIdentifier: tuple[str, str]
    _entityIdentifierHash: int
    _dimsHash: int
    _nonDimSegmentHash: int
    _nonDimScenarioHash: int
    _nonDimsHash: int
    _contextDimAwareHash: int
    _contextNonDimAwareHash: int
    _md5sum: Md5Sum

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelContext, self).init(modelDocument)
        self.segDimValues: dict[ModelConcept, ModelDimensionValue] = {}
        self.scenDimValues: dict[ModelConcept, ModelDimensionValue] = {}
        self.qnameDims: dict[QName, ModelDimensionValue] = {}
        self.errorDimValues: list[ModelDimensionValue] = []
        self.segNonDimValues: list[ModelObject] = []
        self.scenNonDimValues: list[ModelObject] = []
        self._isEqualTo: dict[tuple[ModelContext | None, bool], bool] = {}

    def clearCachedProperties(self) -> None:
        for key in [k for k in vars(self).keys() if k.startswith("_")]:
            delattr(self, key)

    @property
    def isStartEndPeriod(self) -> bool:
        """(bool) -- True for startDate/endDate period"""
        try:
            return self._isStartEndPeriod
        except AttributeError:
            self._isStartEndPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, ("startDate", "endDate"))  # type: ignore[arg-type]
            return self._isStartEndPeriod

    @property
    def isInstantPeriod(self) -> bool:
        """(bool) -- True for instant period"""
        try:
            return self._isInstantPeriod
        except AttributeError:
            self._isInstantPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "instant")  # type: ignore[arg-type]
            return self._isInstantPeriod

    @property
    def isForeverPeriod(self) -> bool:
        """(bool) -- True for forever period"""
        try:
            return self._isForeverPeriod
        except AttributeError:
            self._isForeverPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "forever")  # type: ignore[arg-type]
            return self._isForeverPeriod

    @property
    def startDatetime(self) -> datetime | None:
        """(datetime) -- startDate attribute"""
        try:
            return self._startDatetime
        except AttributeError:
            self._startDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "startDate"))  # type: ignore[arg-type]
            return self._startDatetime

    @startDatetime.setter
    def startDatetime(self, value: datetime | date) -> None:
        self.clearCachedProperties()
        elt = XmlUtil.child(self.period, XbrlConst.xbrli, "startDate")  # type: ignore[arg-type]
        if elt is not None:
            elt.text = XmlUtil.dateunionValue(value)
            xmlValidate(self.modelXbrl, elt)

    @property
    def endDate(self) -> date | None:
        """
        :return: endDate or instant attribute as date, *not* adjusted by a day for midnight values
        """
        try:
            return self._endDate
        except AttributeError:
            endDate = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, ("endDate", "instant")), subtractOneDay=True)  # type: ignore[arg-type]
            self._endDate = endDate.date() if endDate else None
            return self._endDate

    @property
    def endDatetime(self) -> datetime | None:
        """(datetime) -- endDate or instant attribute, with adjustment to end-of-day midnight as needed"""
        try:
            return self._endDatetime
        except AttributeError:
            self._endDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, ("endDate", "instant")), addOneDay=True)  # type: ignore[arg-type]
            return self._endDatetime

    @endDatetime.setter
    def endDatetime(self, value: datetime | date) -> None:
        self.clearCachedProperties()
        elt = XmlUtil.child(self.period, XbrlConst.xbrli, "endDate")  # type: ignore[arg-type]
        if elt is not None:
            elt.text = XmlUtil.dateunionValue(value, subtractOneDay=True)
            xmlValidate(self.modelXbrl, elt)

    @property
    def instantDate(self) -> date | None:
        """
        :return: instant attribute as date, *not* adjusted by a day for midnight values
        """
        try:
            return self._instantDate
        except AttributeError:
            instantDate = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "instant"), subtractOneDay=True)  # type: ignore[arg-type]
            self._instantDate = instantDate.date() if instantDate else None
            return self._instantDate

    @property
    def instantDatetime(self) -> datetime | None:
        """(datetime) -- instant attribute, with adjustment to end-of-day midnight as needed"""
        try:
            return self._instantDatetime
        except AttributeError:
            self._instantDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "instant"), addOneDay=True)  # type: ignore[arg-type]
            return self._instantDatetime

    @instantDatetime.setter
    def instantDatetime(self, value: datetime | date) -> None:
        self.clearCachedProperties()
        elt = XmlUtil.child(self.period, XbrlConst.xbrli, "instant")  # type: ignore[arg-type]
        if elt is not None:
            elt.text = XmlUtil.dateunionValue(value, subtractOneDay=True)
            xmlValidate(self.modelXbrl, elt)

    @property
    def period(self) -> ModelObject | None:
        """(ModelObject) -- period element"""
        try:
            return self._period
        except AttributeError:
            self._period = XmlUtil.child(self, XbrlConst.xbrli, "period")
            return self._period

    @property
    def periodHash(self) -> int:
        """(int) -- hash of period start and end datetimes"""
        try:
            return self._periodHash
        except AttributeError:
            self._periodHash = hash((self.startDatetime, self.endDatetime)) # instant hashes (None, inst), forever hashes (None,None)
            return self._periodHash

    @property
    def entity(self) -> ModelObject | None:
        """(ModelObject) -- entity element"""
        try:
            return self._entity
        except AttributeError:
            self._entity = XmlUtil.child(self, XbrlConst.xbrli, "entity")
            return self._entity

    @property
    def entityIdentifierElement(self) -> ModelObject | None:
        """(ModelObject) -- entity identifier element"""
        try:
            return self._entityIdentifierElement
        except AttributeError:
            self._entityIdentifierElement = XmlUtil.child(self.entity, XbrlConst.xbrli, "identifier")  # type: ignore[arg-type]
            return self._entityIdentifierElement

    @property
    def entityIdentifier(self) -> tuple[str, str]:
        """( (str,str) ) -- tuple of (scheme value, identifier value)"""
        try:
            return self._entityIdentifier
        except AttributeError:
            eiElt = self.entityIdentifierElement
            if eiElt is not None:
                self._entityIdentifier = (eiElt.get("scheme"), eiElt.xValue or eiElt.textValue)  # type: ignore[assignment] # no xValue if --skipDTS
            else:
                self._entityIdentifier = ("(Error)", "(Error)")
            return self._entityIdentifier

    @property
    def entityIdentifierHash(self) -> int:
        """(int) -- hash of entityIdentifier"""
        try:
            return self._entityIdentifierHash
        except AttributeError:
            self._entityIdentifierHash = hash(self.entityIdentifier)
            return self._entityIdentifierHash

    @property
    def hasSegment(self) -> bool:
        """(bool) -- True if a xbrli:segment element is present"""
        return XmlUtil.hasChild(self.entity, XbrlConst.xbrli, "segment")  # type: ignore[arg-type]

    @property
    def segment(self) -> ModelObject | None:
        """(ModelObject) -- xbrli:segment element"""
        return XmlUtil.child(self.entity, XbrlConst.xbrli, "segment")  # type: ignore[arg-type]

    @property
    def hasScenario(self) -> bool:
        """(bool) -- True if a xbrli:scenario element is present"""
        return XmlUtil.hasChild(self, XbrlConst.xbrli, "scenario")

    @property
    def scenario(self) -> ModelObject | None:
        """(ModelObject) -- xbrli:scenario element"""
        return XmlUtil.child(self, XbrlConst.xbrli, "scenario")

    def dimValues(self, contextElement: str) -> dict[ModelConcept, ModelDimensionValue]:
        """(dict) -- Indicated context element's dimension dict (indexed by ModelConcepts)

        :param contextElement: 'segment' or 'scenario'
        :returns: dict of ModelDimension objects indexed by ModelConcept dimension object, or empty dict
        """
        if contextElement == "segment":
            return self.segDimValues
        elif contextElement == "scenario":
            return self.scenDimValues
        return {}

    def hasDimension(self, dimQname: QName) -> bool:
        """(bool) -- True if dimension concept qname is reported by context (in either context element), not including defaulted dimensions."""
        return dimQname in self.qnameDims

    # returns ModelDimensionValue for instance dimensions, else QName for defaults
    def dimValue(self, dimQname: QName) -> ModelDimensionValue | QName | None:
        """(ModelDimension or QName) -- ModelDimension object if dimension is reported (in either context element), or QName of dimension default if there is a default, otherwise None"""
        dimValue = self.qnameDims.get(dimQname)
        if dimValue is None:
            dimValue = self.modelXbrl.qnameDimensionDefaults.get(dimQname)  # type: ignore[assignment,union-attr]
        return dimValue

    def dimMemberQname(self, dimQname: QName, includeDefaults: bool = False) -> QName | None:
        """(QName) -- QName of explicit dimension if reported (or defaulted if includeDefaults is True), else None"""
        dimValue = self.dimValue(dimQname)
        if isinstance(dimValue, (ModelDimensionValue, DimValuePrototype)) and dimValue.isExplicit:
            return dimValue.memberQname
        elif isinstance(dimValue, QName):
            return dimValue
        if dimValue is None and includeDefaults and dimQname in self.modelXbrl.qnameDimensionDefaults:  # type: ignore[union-attr]
            return self.modelXbrl.qnameDimensionDefaults[dimQname]  # type: ignore[union-attr]
        return None

    def dimAspects(self, defaultDimensionAspects: set[QName] | None = None) -> set[QName]:
        """(set) -- For formula and instance aspects processing, set of all dimensions reported or defaulted."""
        if defaultDimensionAspects:
            return self.qnameDims.keys() | defaultDimensionAspects
        return set(self.qnameDims.keys())

    @property
    def dimsHash(self) -> int:
        """(int) -- A hash of the set of reported dimension values."""
        try:
            return self._dimsHash
        except AttributeError:
            self._dimsHash = hash(frozenset(self.qnameDims.values()))
            return self._dimsHash

    def nonDimValues(self, contextElement: str | int) -> Sequence[ModelObject]:
        """([ModelObject]) -- ContextElement is either string or Aspect code for segment or scenario, returns nonXDT ModelObject children of context element.

        :param contextElement: one of 'segment', 'scenario', Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO, Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO
        :type contextElement: str or Aspect type
        :returns: list of ModelObjects
        """
        if contextElement in ("segment", Aspect.NON_XDT_SEGMENT):
            return self.segNonDimValues
        elif contextElement in ("scenario", Aspect.NON_XDT_SCENARIO):
            return self.scenNonDimValues
        elif contextElement == Aspect.COMPLETE_SEGMENT and self.hasSegment:
            return XmlUtil.children(self.segment, None, "*")  # type: ignore[arg-type]
        elif contextElement == Aspect.COMPLETE_SCENARIO and self.hasScenario:
            return XmlUtil.children(self.scenario, None, "*")  # type: ignore[arg-type]
        return []

    @property
    def segmentHash(self) -> int:
        """(int) -- Hash of the segment, based on s-equality values"""
        return XbrlUtil.equalityHash(self.segment)  # type: ignore[arg-type] # self-caching

    @property
    def scenarioHash(self) -> int:
        """(int) -- Hash of the scenario, based on s-equality values"""
        return XbrlUtil.equalityHash(self.scenario)  # type: ignore[arg-type] # self-caching

    @property
    def nonDimSegmentHash(self) -> int:
        """(int) -- Hash, of s-equality values, of non-XDT segment objects"""
        try:
            return self._nonDimSegmentHash
        except AttributeError:
            self._nonDimSegmentHash = XbrlUtil.equalityHash(self.nonDimValues("segment"))
            return self._nonDimSegmentHash

    @property
    def nonDimScenarioHash(self) -> int:
        """(int) -- Hash, of s-equality values, of non-XDT scenario objects"""
        try:
            return self._nonDimScenarioHash
        except AttributeError:
            self._nonDimScenarioHash = XbrlUtil.equalityHash(self.nonDimValues("scenario"))
            return self._nonDimScenarioHash

    @property
    def nonDimHash(self) -> int:
        """(int) -- Hash, of s-equality values, of non-XDT segment and scenario objects"""
        try:
            return self._nonDimsHash
        except AttributeError:
            self._nonDimsHash = hash((self.nonDimSegmentHash, self.nonDimScenarioHash))
            return self._nonDimsHash

    @property
    def contextDimAwareHash(self) -> int:
        """(int) -- Hash of period, entityIdentifier, dim, and nonDims"""
        try:
            return self._contextDimAwareHash
        except AttributeError:
            self._contextDimAwareHash = hash((self.periodHash, self.entityIdentifierHash, self.dimsHash, self.nonDimHash))
            return self._contextDimAwareHash

    @property
    def contextNonDimAwareHash(self) -> int:
        """(int) -- Hash of period, entityIdentifier, segment, and scenario (s-equal based)"""
        try:
            return self._contextNonDimAwareHash
        except AttributeError:
            self._contextNonDimAwareHash = hash((self.periodHash, self.entityIdentifierHash, self.segmentHash, self.scenarioHash))
            return self._contextNonDimAwareHash

    @property
    def md5sum(self) -> Md5Sum:
        try:
            return self._md5sum
        except AttributeError:
            _toHash: list[str | datetime | Md5Sum | None] = [self.entityIdentifier[0], self.entityIdentifier[1]]
            if self.isInstantPeriod:
                _toHash.append(self.instantDatetime)
            elif self.isStartEndPeriod:
                _toHash.append(self.startDatetime)
                _toHash.append(self.endDatetime)
            elif self.isForeverPeriod:
                _toHash.append("forever")
            if self.qnameDims:
                _toHash.extend([dim.md5sum for dim in self.qnameDims.values()])
            self._md5sum = md5hash(_toHash)  # type: ignore[arg-type]
            return self._md5sum

    def isPeriodEqualTo(self, cntx2: ModelContext) -> bool:
        """(bool) -- True if periods are datetime equal (based on 2.1 date offsets)"""
        if self.isForeverPeriod:
            return cntx2.isForeverPeriod
        elif self.isStartEndPeriod:
            if not cntx2.isStartEndPeriod:
                return False
            return self.startDatetime == cntx2.startDatetime and self.endDatetime == cntx2.endDatetime
        elif self.isInstantPeriod:
            if not cntx2.isInstantPeriod:
                return False
            return self.instantDatetime == cntx2.instantDatetime
        else:
            return False

    def isEntityIdentifierEqualTo(self, cntx2: ModelContext) -> bool:
        """(bool) -- True if entityIdentifier values are equal (scheme and text value)"""
        return self.entityIdentifier == cntx2.entityIdentifier

    def isEqualTo(self, cntx2: ModelContext | None, dimensionalAspectModel: bool | None = None) -> bool:
        if dimensionalAspectModel is None:
            dimensionalAspectModel = self.modelXbrl.hasXDT  # type: ignore[union-attr]
        try:
            return self._isEqualTo[(cntx2,dimensionalAspectModel)]
        except KeyError:
            result = self.isEqualTo_(cntx2, dimensionalAspectModel)
            self._isEqualTo[(cntx2,dimensionalAspectModel)] = result
            return result

    def isEqualTo_(self, cntx2: ModelContext | None, dimensionalAspectModel: bool) -> bool:
        """(bool) -- If dimensionalAspectModel is absent, True is assumed.
        False means comparing based on s-equality of segment, scenario, while
        True means based on dimensional values and nonDimensional values separately."""
        if cntx2 is None:
            return False
        if cntx2 == self:   # same context
            return True
        if (self.periodHash != cntx2.periodHash or
            self.entityIdentifierHash != cntx2.entityIdentifierHash):
            return False
        if dimensionalAspectModel:
            if (self.dimsHash != cntx2.dimsHash or
                self.nonDimHash != cntx2.nonDimHash):
                return False
        else:
            if (self.segmentHash != cntx2.segmentHash or
                self.scenarioHash != cntx2.scenarioHash):
                return False
        if self.periodHash != cntx2.periodHash or not self.isPeriodEqualTo(cntx2) or not self.isEntityIdentifierEqualTo(cntx2):
            return False
        if dimensionalAspectModel:
            if self.qnameDims.keys() != cntx2.qnameDims.keys():
                return False
            for dimQname, ctx1Dim in self.qnameDims.items():
                if not ctx1Dim.isEqualTo(cntx2.qnameDims[dimQname]):
                    return False
            for nonDimVals1, nonDimVals2 in ((self.segNonDimValues,cntx2.segNonDimValues),
                                             (self.scenNonDimValues,cntx2.scenNonDimValues)):
                if len(nonDimVals1) != len(nonDimVals2):
                    return False
                for i, nonDimVal1 in enumerate(nonDimVals1):
                    if not XbrlUtil.sEqual(self.modelXbrl, nonDimVal1, nonDimVals2[i]):  # type: ignore[arg-type]
                        return False
        else:
            if self.hasSegment:
                if not cntx2.hasSegment:
                    return False
                if not XbrlUtil.sEqual(self.modelXbrl, self.segment, cntx2.segment):  # type: ignore[arg-type]
                    return False
            elif cntx2.hasSegment:
                return False

            if self.hasScenario:
                if not cntx2.hasScenario:
                    return False
                if not XbrlUtil.sEqual(self.modelXbrl, self.scenario, cntx2.scenario):  # type: ignore[arg-type]
                    return False
            elif cntx2.hasScenario:
                return False

        return True

    @property
    def propertyView(self) -> tuple[tuple[str, str, tuple[tuple[str, str]]] | tuple[str, str], ...]:  # type: ignore[override]
        scheme, entityId = self.entityIdentifier
        return ((("entity", entityId, (("scheme", scheme),)),) +
                ((("forever", ""),) if self.isForeverPeriod else
                 (("instant", XmlUtil.dateunionValue(self.instantDatetime, subtractOneDay=True)),) if self.isInstantPeriod else
                 (("startDate", XmlUtil.dateunionValue(self.startDatetime)), ("endDate", XmlUtil.dateunionValue(self.endDatetime, subtractOneDay=True)))) +
                (("dimensions", "({0})".format(len(self.qnameDims)),
                  tuple(mem.propertyView for dim, mem in sorted(self.qnameDims.items())))  # type: ignore[operator]
                  if self.qnameDims else (),
                ))

    def __repr__(self) -> str:
        return ("modelContext[{0}, period: {1}, {2}{3} line {4}]"
                .format(self.id,
                        "forever" if self.isForeverPeriod else
                        "instant " + XmlUtil.dateunionValue(self.instantDatetime, subtractOneDay=True) if self.isInstantPeriod else
                        "duration " + XmlUtil.dateunionValue(self.startDatetime) + " - " + XmlUtil.dateunionValue(self.endDatetime, subtractOneDay=True),
                        "dimensions: ({0}) {1},".format(len(self.qnameDims),
                        tuple(mem.propertyView for dim, mem in sorted(self.qnameDims.items())))
                        if self.qnameDims else "",
                        self.modelDocument.basename, self.sourceline))


class ModelDimensionValue(ModelObject):
    """
    .. class:: ModelDimensionValue(modelDocument)

    Model dimension value (both explicit and typed, non-default values)

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    _dimension: ModelConcept | None
    _memberQname: QName | None
    _member: ModelConcept | None

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelDimensionValue, self).init(modelDocument)

    def __hash__(self) -> int:
        if self.isExplicit:
            return hash((self.dimensionQname, self.memberQname))
        else: # need XPath equal so that QNames aren't lexically compared (for fact and context equality in comparing formula results)
            return hash((self.dimensionQname, XbrlUtil.equalityHash(XmlUtil.child(self), equalMode=XbrlUtil.XPATH_EQ)))  # type: ignore[arg-type]

    @property
    def md5sum(self) -> Md5Sum:
        if self.isExplicit:
            return md5hash([self.dimensionQname, self.memberQname])  # type: ignore[list-item]
        else:
            return md5hash([self.dimensionQname, self.typedMember])  # type: ignore[list-item]

    @property
    def dimensionQname(self) -> QName | None:
        """(QName) -- QName of the dimension concept"""
        dimAttr = self.xAttributes.get("dimension", None)
        if dimAttr is not None and dimAttr.xValid >= VALID:
            return dimAttr.xValue  # type: ignore[return-value]
        return None

    @property
    def dimension(self) -> ModelConcept | None:
        """(ModelConcept) -- Dimension concept"""
        try:
            return self._dimension
        except AttributeError:
            self._dimension = self.modelXbrl.qnameConcepts.get(self.dimensionQname)  # type: ignore[arg-type,union-attr]
            return  self._dimension

    @property
    def isExplicit(self) -> bool:
        """(bool) -- True if explicitMember element"""
        return self.localName == "explicitMember"

    @property
    def typedMember(self) -> ModelObject | None:
        """(ModelConcept) -- Child ModelObject that is the dimension member element

        (To get <typedMember> element use 'self').
        """
        for child in self.iterchildren():
            if isinstance(child, ModelObject):  # skip comment and processing nodes
                return child
        return None

    @property
    def isTyped(self) -> bool:
        """(bool) -- True if typedMember element"""
        return self.localName == "typedMember"

    @property
    def memberQname(self) -> QName | None:
        """(QName) -- QName of an explicit dimension member"""
        try:
            return self._memberQname
        except AttributeError:
            if self.isExplicit and self.xValid >= VALID:
                self._memberQname = self.xValue  # type: ignore[assignment]
            else:
                self._memberQname = None
            return self._memberQname

    @property
    def member(self) -> ModelConcept | None:
        """(ModelConcept) -- Concept of an explicit dimension member"""
        try:
            return self._member
        except AttributeError:
            self._member = self.modelXbrl.qnameConcepts.get(self.memberQname)  # type: ignore[arg-type,union-attr]
            return  self._member

    def isEqualTo(self, other: ModelDimensionValue | None, equalMode: int = XbrlUtil.XPATH_EQ) -> bool:
        """(bool) -- True if explicit member QNames equal or typed member nodes correspond, given equalMode (s-equal, s-equal2, or xpath-equal for formula)

        :param equalMode: XbrlUtil.S_EQUAL (ordinary S-equality from 2.1 spec), XbrlUtil.S_EQUAL2 (XDT definition of equality, adding QName comparisions), or XbrlUtil.XPATH_EQ (XPath EQ on all types)
        """
        if other is None:
            return False
        if self.isExplicit: # other is either ModelDimensionValue or the QName value of explicit dimension
            return self.memberQname == (other.memberQname if isinstance(other, (ModelDimensionValue, DimValuePrototype)) else other)
        else: # typed dimension compared to another ModelDimensionValue or other is the value nodes
            return XbrlUtil.nodesCorrespond(self.modelXbrl, self.typedMember,  # type: ignore[arg-type]
                                            other.typedMember if isinstance(other, (ModelDimensionValue, DimValuePrototype)) else other,
                                            equalMode=equalMode, excludeIDs=XbrlUtil.NO_IDs_EXCLUDED)

    @property
    def contextElement(self) -> str:
        """(str) -- 'segment' or 'scenario'"""
        return self.getparent().localName  # type: ignore[union-attr]

    @property
    def propertyView(self) -> tuple[str, str]:  # type: ignore[override]
        if self.isExplicit:
            return str(self.dimensionQname), str(self.memberQname)
        else:
            return str(self.dimensionQname), XmlUtil.xmlstring(XmlUtil.child(self), stripXmlns=True, prettyPrint=True)  # type: ignore[arg-type]

def measuresOf(parent: ModelObject) -> tuple[QName, ...]:
    if parent.xValid >= VALID: # has DTS and is validated
        return tuple(sorted([m.xValue  # type: ignore[misc]
                             for m in parent.iterchildren(tag="{http://www.xbrl.org/2003/instance}measure")
                             if isinstance(m, ModelObject) and m.xValue]))
    else:  # probably skipDTS
        return tuple(sorted([m.prefixedNameQname(m.textValue) or XbrlConst.qnInvalidMeasure
                             for m in parent.iterchildren(tag="{http://www.xbrl.org/2003/instance}measure")
                             if isinstance(m, ModelObject)]))

def measuresStr(m: QName) -> str:
    return m.localName if m.namespaceURI in (XbrlConst.xbrli, XbrlConst.iso4217) else str(m)


class ModelUnit(ModelObject):
    """
    .. class:: ModelUnit(modelDocument)

    Model unit

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    _measures: tuple[tuple[QName, ...], tuple[QName, ...]]
    _hash: int
    _inUse: bool
    _md5hash: str
    _md5sum: Md5Sum
    _utrEntries: dict[ModelType, set[UtrEntry | None]]
    _utrSymbols: dict[ModelType, str]

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelUnit, self).init(modelDocument)

    @property
    def measures(self) -> tuple[tuple[QName, ...], tuple[QName, ...]]:
        """([QName],[Qname]) -- Returns a tuple of multiply measures list and divide members list
        (empty if not a divide element).  Each list of QNames is in prefixed-name order."""
        try:
            return self._measures
        except AttributeError:
            if self.isDivide:
                self._measures = (measuresOf(XmlUtil.descendant(self, XbrlConst.xbrli, "unitNumerator")),  # type: ignore[arg-type]
                                  measuresOf(XmlUtil.descendant(self, XbrlConst.xbrli, "unitDenominator")))  # type: ignore[arg-type]
            else:
                self._measures = (measuresOf(self), ())
            return self._measures

    @property
    def hash(self) -> int:
        """(int) -- Hash of measures in both multiply and divide lists."""
        try:
            return self._hash
        except AttributeError:
            # should this use frozenSet of each measures element?
            self._hash = hash(self.measures) # measures must be immutable (tuple)
            return self._hash

    @property
    def md5hash(self) -> str:
        """(bool) -- md5 Hash of measures in both multiply and divide lists."""
        try:
            return self._md5hash
        except AttributeError:
            md5hash = md5()
            for i, measures in enumerate(self.measures):
                if i:
                    md5hash.update(b"divisor")
                for measure in measures:
                    if measure.namespaceURI:
                        md5hash.update(measure.namespaceURI.encode("utf-8", "replace"))
                    md5hash.update(measure.localName.encode("utf-8", "replace"))
            # should this use frozenSet of each measures element?
            self._md5hash = md5hash.hexdigest()
            return self._md5hash

    @property
    def md5sum(self) -> Md5Sum:
        try:
            return self._md5sum
        except AttributeError:
            if self.isDivide: # hash of mult and div hex strings of hashes of measures
                self._md5sum = md5hash([md5hash([md5hash(m) for m in md]).toHex()
                                        for md in self.measures])
            else: # sum of hash sums
                self._md5sum = md5hash([md5hash(m) for m in self.measures[0]])
            return self._md5sum

    @property
    def isDivide(self) -> bool:
        """(bool) -- True if unit has a divide element"""
        return XmlUtil.hasChild(self, XbrlConst.xbrli, "divide")

    @property
    def isSingleMeasure(self) -> bool:
        """(bool) -- True for a single multiply and no divide measures"""
        measures = self.measures
        return len(measures[0]) == 1 and len(measures[1]) == 0

    def isEqualTo(self, unit2: ModelUnit | None) -> bool:
        """(bool) -- True if measures are equal"""
        if unit2 is None or unit2.hash != self.hash:
            return False
        return unit2 is self or self.measures == unit2.measures

    @property
    def value(self) -> str:
        """(str) -- String value for view purposes, space separated list of string qnames
        of multiply measures, and if any divide, a '/' character and list of string qnames
        of divide measure qnames."""
        mul, div = self.measures
        return " ".join([measuresStr(m) for m in mul] + (["/"] + [measuresStr(d) for d in div] if div else []))

    def utrEntries(self, modelType: ModelType) -> set[UtrEntry | None]:
        try:
            return self._utrEntries[modelType]
        except AttributeError:
            self._utrEntries = {}
            return self.utrEntries(modelType)
        except KeyError:
            global utrEntries
            if utrEntries is None:
                from arelle.ValidateUtr import utrEntries
            self._utrEntries[modelType] = utrEntries(modelType, self)  # type: ignore[misc]
            return self._utrEntries[modelType]

    def utrSymbol(self, modelType: ModelType) -> str:
        try:
            return self._utrSymbols[modelType]
        except AttributeError:
            self._utrSymbols = {}
            return self.utrSymbol(modelType)
        except KeyError:
            global utrSymbol
            if utrSymbol is None:
                from arelle.ValidateUtr import utrSymbol
            self._utrSymbols[modelType] = utrSymbol(modelType, self.measures)  # type: ignore[misc]
            return self._utrSymbols[modelType]

    @property
    def propertyView(self) -> tuple[tuple[str, QName], ...]:
        measures = self.measures
        if measures[1]:
            return tuple(("mul", m) for m in measures[0]) + \
                   tuple(("div", d) for d in measures[1])
        else:
            return tuple(("measure", m) for m in measures[0])


class ModelInlineFootnote(ModelResource):
    """
    .. class:: ModelInlineFootnote(modelDocument)

    Model inline footnote (inline XBRL facts)

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    _ixValue: str

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInlineFootnote, self).init(modelDocument)

    @property
    def qname(self) -> QName:
        """(QName) -- QName of generated object"""
        return XbrlConst.qnLinkFootnote

    @property
    def footnoteID(self) -> str | None:  # type: ignore[override]
        if self.namespaceURI == XbrlConst.ixbrl:
            return self.get("footnoteID")
        else:
            return self.id

    @property
    def value(self) -> str:
        """(str) -- Overrides and corresponds to value property of ModelFact,
        for relevant inner text nodes aggregated and transformed as needed."""
        try:
            return self._ixValue
        except AttributeError:
            self._ixValue = XmlUtil.innerText(self,
                                  ixExclude=True,
                                  ixEscape="html",
                                  ixContinuation=(self.namespaceURI != XbrlConst.ixbrl),
                                  ixResolveUris=True,
                                  strip=True) # include HTML constructs

            return self._ixValue

    @property
    def textValue(self) -> str:
        """(str) -- override xml-level stringValue for transformed value descendants text"""
        return self.value

    @property
    def stringValue(self) -> str:
        """(str) -- override xml-level stringValue for transformed value descendants text"""
        return self.value

    @property
    def htmlValue(self) -> str:
        return XmlUtil.innerText(self, ixExclude=True, ixContinuation=True, strip=False)

    @property
    def role(self) -> str:  # type: ignore[override]
        """(str) -- xlink:role attribute"""
        return self.get("footnoteRole") or XbrlConst.footnote

    @property
    def xlinkLabel(self) -> str | None:  # type: ignore[override]
        """(str) -- xlink:label attribute"""
        return self.footnoteID

    @property
    def xmlLang(self) -> str | None:  # type: ignore[override]
        """(str) -- xml:lang attribute"""
        return XmlUtil.ancestorOrSelfAttr(self, "{http://www.w3.org/XML/1998/namespace}lang")

    @property
    def attributes(self) -> dict[str, str | None]:
        # for output of derived instance, includes all output-applicable attributes
        attributes = {"{http://www.w3.org/1999/xlink}type": "resource",
                      "{http://www.w3.org/1999/xlink}label": self.xlinkLabel,
                      "{http://www.w3.org/1999/xlink}role": self.role}
        if self.id:
            attributes["id"] = self.footnoteID
        lang = self.xmlLang
        if lang:
            attributes["{http://www.w3.org/XML/1998/namespace}lang"] = lang
        return attributes

    def viewText(self, labelrole: str | None = None, lang: str | None = None) -> str:
        return self.value

    @property
    def propertyView(self) -> tuple[tuple[str, str | int | None], ...]:
        return (("file", self.modelDocument.basename),
                ("line", self.sourceline)) + \
               super(ModelInlineFootnote, self).propertyView + \
               (("html value", self.htmlValue),)

    def __repr__(self) -> str:
        return "modelInlineFootnote[{0}]{1})".format(self.objectId(), self.propertyView)


class ModelInlineXbrliXbrl(ModelObject):
    """
    .. class:: ModelInlineXbrliXbrl(modelDocument)

    Model inline xbrli:xbrl element for root of derived/extracted instance

    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelInlineXbrliXbrl, self).init(modelDocument)

    @property
    def qname(self) -> QName:
        """(QName) -- QName of generated object"""
        return XbrlConst.qnXbrliXbrl

    @property
    def parentElement(self) -> None:
        """(ModelObject) -- inline root element has no parent element"""
        return None

    def ixIter(self, childOnly: bool = False) -> Iterator[Any]:
        """(ModelObject) -- generator of child elements of the inline target instance document"""
        modelXbrl = self.modelXbrl
        # roleRef and arcroleRef (of each inline document)
        for sourceRefs in (modelXbrl.targetRoleRefs, modelXbrl.targetArcroleRefs):  # type: ignore[union-attr]
            for roleRefElt in sourceRefs.values():
                yield roleRefElt
        # contexts
        if not hasattr(self, "_orderedContenxts"): # contexts may come from multiple IXDS files
            self._orderedContenxts = sorted(modelXbrl.contexts.values(), key=lambda c: c.objectIndex)  # type: ignore[union-attr]
        for context in self._orderedContenxts:
            yield context
            if not childOnly:
                for e in context.iterdescendants():
                    yield e
        if not hasattr(self, "_orderedUnits"): # units may come from multiple IXDS files
            self._orderedUnits = sorted(modelXbrl.units.values(), key=lambda u: u.objectIndex)  # type: ignore[union-attr]
        for unit in self._orderedUnits:
            yield unit
            if not childOnly:
                for e in unit.iterdescendants():
                    yield e
        for fact in modelXbrl.facts:  # type: ignore[union-attr]
            yield fact
            if not childOnly:
                for e in fact.ixIter(childOnly):  # type: ignore[union-attr]
                    yield e
        if not hasattr(self, "_orderedFootnoteLinks"):
            _ftLinks: defaultdict[str | None, list[ModelLink | LinkPrototype]] = defaultdict(list)
            for linkKey, linkPrototypes in modelXbrl.baseSets.items():  # type: ignore[union-attr]
                arcrole, linkrole, linkqname, arcqname = linkKey
                if (linkrole and linkqname and arcqname and  # fully specified roles
                    arcrole != "XBRL-footnotes" and
                    any(lP.modelDocument.type == ModelDocumentType.INLINEXBRL for lP in linkPrototypes)):
                    for linkPrototype in linkPrototypes:
                        if linkPrototype not in _ftLinks[linkrole]:
                            _ftLinks[linkrole].append(linkPrototype)
            self._orderedFootnoteLinks = [l for r in sorted(_ftLinks.keys()) for l in _ftLinks[r]]  # type: ignore[type-var]
        for linkPrototype in self._orderedFootnoteLinks:
            yield linkPrototype
            if not childOnly:
                for e in linkPrototype.iterdescendants():
                    yield e

from arelle import FunctionIxt

from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
     (XbrlConst.qnXbrliItem, ModelFact),
     (XbrlConst.qnXbrliTuple, ModelFact),
     (XbrlConst.qnIXbrlTuple, ModelInlineFact),
     (XbrlConst.qnIXbrl11Tuple, ModelInlineFact),
     (XbrlConst.qnIXbrlNonNumeric, ModelInlineFact),
     (XbrlConst.qnIXbrl11NonNumeric, ModelInlineFact),
     (XbrlConst.qnIXbrlNonFraction, ModelInlineFact),
     (XbrlConst.qnIXbrl11NonFraction, ModelInlineFact),
     (XbrlConst.qnIXbrlFraction, ModelInlineFraction),
     (XbrlConst.qnIXbrl11Fraction, ModelInlineFraction),
     (XbrlConst.qnIXbrlNumerator, ModelInlineFractionTerm),
     (XbrlConst.qnIXbrl11Numerator, ModelInlineFractionTerm),
     (XbrlConst.qnIXbrlDenominator, ModelInlineFractionTerm),
     (XbrlConst.qnIXbrl11Denominator, ModelInlineFractionTerm),
     (XbrlConst.qnIXbrlFootnote, ModelInlineFootnote),
     (XbrlConst.qnIXbrl11Footnote, ModelInlineFootnote),
     (XbrlConst.qnPrototypeXbrliXbrl, ModelInlineXbrliXbrl),
     (XbrlConst.qnXbrliContext, ModelContext),
     (XbrlConst.qnXbrldiExplicitMember, ModelDimensionValue),
     (XbrlConst.qnXbrldiTypedMember, ModelDimensionValue),
     (XbrlConst.qnXbrliUnit, ModelUnit),
    ))
