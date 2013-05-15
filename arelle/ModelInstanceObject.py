"""
:mod:`arelle.ModelInstanceObjuect`
~~~~~~~~~~~~~~~~~~~

.. module:: arelle.ModelInstanceObject
   :copyright: Copyright 2010-2012 Mark V Systems Limited, All rights reserved.
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
from collections import defaultdict
from lxml import etree
from arelle import XmlUtil, XbrlConst, XbrlUtil, UrlUtil, Locale, ModelValue
from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals, roundValue
from arelle.PrototypeInstanceObject import DimValuePrototype
from math import isnan
from arelle.ModelObject import ModelObject
Aspect = None
POSINF = float("inf")
NEGINF = float("-inf")

class NewFactItemOptions():
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
    def __init__(self, savedOptions=None, xbrlInstance=None):
        self.entityIdentScheme = ""
        self.entityIdentValue = ""
        self.startDate = ""  # use string  values so structure can be json-saved
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
    def startDateDate(self):
        """(datetime) -- date-typed date value of startDate (which is persisted in str form)"""
        return XmlUtil.datetimeValue(self.startDate)

    @property
    def endDateDate(self):  # return a date-typed date
        """(datetime) -- date-typed date value of endDate (which is persisted in str form)"""
        return XmlUtil.datetimeValue(self.endDate, addOneDay=True)
                
    
class ModelFact(ModelObject):
    """
    .. class:: ModelFact(modelDocument)
    
    Model fact (both instance document facts and inline XBRL facts)
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument

        .. attribute:: modelTupleFacts
        
        ([ModelFact]) - List of child facts in source document order
    """
    def init(self, modelDocument):
        super(ModelFact, self).init(modelDocument)
        self.modelTupleFacts = []
        
    @property
    def concept(self):
        """(ModelConcept) -- concept of the fact."""
        return self.elementDeclaration()  # logical (fact) declaration in own modelXbrl, not physical element (if inline)
        
    @property
    def contextID(self):
        """(str) -- contextRef attribute"""
        return self.get("contextRef")

    @property
    def context(self):
        """(ModelContext) -- context of the fact if any else None (e.g., tuple)"""
        try:
            return self._context
        except AttributeError:
            self._context = self.modelXbrl.contexts.get(self.contextID)
            return self._context
    
    @property
    def unit(self):
        """(ModelUnit) -- unit of the fact if any else None (e.g., non-numeric or tuple)"""
        return self.modelXbrl.units.get(self.unitID)
    
    @property
    def unitID(self):
        """(str) -- unitRef attribute"""
        return self.get("unitRef")

    @property
    def conceptContextUnitLangHash(self):
        """(int) -- Hash value of fact's concept QName, dimensions-aware 
        context hash, unit hash, and xml:lang hash, useful for fast comparison of facts for EFM 6.5.12"""
        try:
            return self._conceptContextUnitLangHash
        except AttributeError:
            context = self.context
            unit = self.unit
            self._conceptContextUnitLangHash = hash( 
                (self.qname,
                 context.contextDimAwareHash if context is not None else None,
                 unit.hash if unit is not None else None,
                 self.xmlLang) )
            return self._conceptContextUnitLangHash

    @property
    def isItem(self):
        """(bool) -- concept.isItem"""
        try:
            return self._isItem
        except AttributeError:
            concept = self.concept
            self._isItem = (concept is not None) and concept.isItem
            return self._isItem

    @property
    def isTuple(self):
        """(bool) -- concept.isTuple"""
        try:
            return self._isTuple
        except AttributeError:
            concept = self.concept
            self._isTuple = (concept is not None) and concept.isTuple
            return self._isTuple

    @property
    def isNumeric(self):
        """(bool) -- concept.isNumeric (note this is false for fractions)"""
        try:
            return self._isNumeric
        except AttributeError:
            concept = self.concept
            self._isNumeric = (concept is not None) and concept.isNumeric
            return self._isNumeric

    @property
    def isFraction(self):
        """(bool) -- concept.isFraction"""
        try:
            return self._isFraction
        except AttributeError:
            concept = self.concept
            self._isFraction = (concept is not None) and concept.isFraction
            return self._isFraction
        
    @property
    def parentElement(self):
        """(ModelObject) -- parent element (tuple or xbrli:xbrl)"""
        return self.getparent()

    @property
    def ancestorQnames(self):
        """(set) -- Set of QNames of ancestor elements (tuple and xbrli:xbrl)"""
        try:
            return self._ancestorQnames
        except AttributeError:
            self._ancestorQnames = set( ModelValue.qname(ancestor) for ancestor in self.iterancestors() )
            return self._ancestorQnames

    @property
    def decimals(self):
        """(str) -- Value of decimals attribute, or fixed or default value for decimals on concept type declaration"""
        try:
            return self._decimals
        except AttributeError:
            decimals = self.get("decimals")
            if decimals:
                self._decimals = decimals
            else:   #check for fixed decimals on type
                type = self.concept.type
                self._decimals = type.fixedOrDefaultAttrValue("decimals") if type is not None else None
            return  self._decimals

    @property
    def precision(self):
        """(str) -- Value of precision attribute, or fixed or default value for precision on concept type declaration"""
        try:
            return self._precision
        except AttributeError:
            precision = self.get("precision")
            if precision:
                self._precision = precision
            else:   #check for fixed decimals on type
                type = self.concept.type
                self._precision = type.fixedOrDefaultAttrValue("precision") if type is not None else None
            return  self._precision

    @property
    def xmlLang(self):
        """(str) -- xml:lang attribute, if none and non-numeric, disclosure-system specified default lang"""
        lang = self.get("{http://www.w3.org/XML/1998/namespace}lang")
        if lang is None and self.modelXbrl.modelManager.validateDisclosureSystem:
            concept = self.concept
            if concept is not None and not concept.isNumeric:
                lang = self.modelXbrl.modelManager.disclosureSystem.defaultXmlLang
        return lang
    
    @property
    def xsiNil(self):
        """(str) -- value of xsi:nil or 'false' if absent"""
        nil = self.get("{http://www.w3.org/2001/XMLSchema-instance}nil")
        return nil if nil else "false"
    
    @property
    def isNil(self):
        """(bool) -- True if xsi:nil is 'true'"""
        return self.xsiNil == "true"
    
    @property
    def value(self):
        """(str) -- Text value of fact or default or fixed if any, otherwise None"""
        v = self.elementText
        if not v:
            if self.concept.default is not None:
                v = self.concept.default
            elif self.concept.fixed is not None:
                v = self.concept.fixed
        return v
    
    @property
    def fractionValue(self):
        """( (str,str) ) -- (text value of numerator, text value of denominator)"""
        return (XmlUtil.text(XmlUtil.child(self, None, "numerator")),
                XmlUtil.text(XmlUtil.child(self, None, "denominator")))
    
    @property
    def effectiveValue(self):
        """(str) -- Effective value for views, (nil) if isNil, None if no value, 
        locale-formatted string of decimal value (if decimals specified) , otherwise string value"""
        concept = self.concept
        if concept is None or concept.isTuple:
            return None
        if self.isNil:
            return "(nil)"
        try:
            if concept.isNumeric:
                val = self.value
                try:
                    num = float(val)
                    dec = self.decimals
                    if dec is None or dec == "INF":
                        dec = len(val.partition(".")[2])
                    else:
                        dec = int(dec) # 2.7 wants short int, 3.2 takes regular int, don't use _INT here
                    return Locale.format(self.modelXbrl.locale, "%.*f", (dec, num), True)
                except ValueError: 
                    return "(error)"
            return self.value
        except Exception as ex:
            return str(ex)  # could be transform value of inline fact

    @property
    def vEqValue(self):
        """(float or str) -- v-equal value, float if numeric, otherwise string value"""
        if self.concept.isNumeric:
            return float(self.value)
        return self.value
    
    def isVEqualTo(self, other, deemP0Equal=False):
        """(bool) -- v-equality of two facts
        
        Note that facts may be in different instances
        """
        if self.isTuple or other.isTuple:
            return False
        if self.isNil:
            return other.isNil
        if other.isNil:
            return False
        if not self.context.isEqualTo(other.context):
            return False
        if self.concept.isNumeric:
            if other.concept.isNumeric:
                if not self.unit.isEqualTo(other.unit):
                    return False
                if self.modelXbrl.modelManager.validateInferDecimals:
                    d = min((inferredDecimals(self), inferredDecimals(other))); p = None
                    if isnan(d) and deemP0Equal:
                        return True
                else:
                    d = None; p = min((inferredPrecision(self), inferredPrecision(other)))
                    if p == 0 and deemP0Equal:
                        return True
                return roundValue(self.value,precision=p,decimals=d) == roundValue(other.value,precision=p,decimals=d)
            else:
                return False
        selfValue = self.value
        otherValue = other.value
        if isinstance(selfValue,str) and isinstance(otherValue,str):
            return selfValue.strip() == otherValue.strip()
        else:
            return selfValue == otherValue
        
    def isDuplicateOf(self, other, topLevel=True, deemP0Equal=False, unmatchedFactsStack=None): 
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
                self.qname != other or
                self.parentElement.qname != other.parentElement.qname):
                return False    # can't be identical
            # parent test can only be done if in same instauce
            if self.modelXbrl == other.modelXbrl and self.parentElement != other.parentElement:
                return False
            if not (self.context.isEqualTo(other.context,dimensionalAspectModel=False) and
                    (not self.isNumeric or self.unit.isEqualTo(other.unit))):
                return False
        elif self.isTuple:
            if (self == other or
                self.qname != other.qname or
                (topLevel and self.parentElement.qname != other.parentElement.qname)):
                return False    # can't be identical
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
    def propertyView(self):
        try:
            concept = self.concept
            lbl = (("label", concept.label(lang=self.modelXbrl.modelManager.defaultLang)),)
        except KeyError:
            lbl = (("name", self.qname),)
        return lbl + (
               (("contextRef", self.contextID, self.context.propertyView if self.context is not None else ()),
                ("unitRef", self.unitID, self.unit.propertyView if self.isNumeric and self.unit is not None else ()),
                ("decimals", self.decimals),
                ("precision", self.precision),
                ("xsi:nil", self.xsiNil),
                ("value", self.effectiveValue.strip()))
                if self.isItem else () )
        
    def __repr__(self):
        return ("modelFact[{0}, qname: {1}, contextRef: {2}, unitRef: {3}, value: {4}, {5}, line {6}]"
                .format(self.objectIndex, self.qname, self.get("contextRef"), self.get("unitRef"),
                        self.effectiveValue.strip() if self.isItem else '(tuple)',
                        self.modelDocument.basename, self.sourceline))
    
    @property
    def viewConcept(self):
        return self.concept
    
class ModelInlineFact(ModelFact):
    """
    .. class:: ModelInlineFact(modelDocument)
    
    Model inline fact (inline XBRL facts)
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument):
        super(ModelInlineFact, self).init(modelDocument)
        
    @property
    def qname(self):
        """(QName) -- QName of concept from the name attribute, overrides and corresponds to the qname property of a ModelFact (inherited from ModelObject)"""
        try:
            return self._factQname
        except AttributeError:
            self._factQname = self.prefixedNameQname(self.get("name")) if self.get("name") else None
            return self._factQname

    @property
    def sign(self):
        """(str) -- sign attribute of inline element"""
        return self.get("sign")
    
    @property
    def tupleID(self):
        """(str) -- tupleId attribute of inline element"""
        try:
            return self._tupleId
        except AttributeError:
            self._tupleId = self.get("tupleID")
            return self._tupleId
    
    @property
    def tupleRef(self):
        """(str) -- tupleRef attribute of inline element"""
        try:
            return self._tupleRef
        except AttributeError:
            self._tupleRef = self.get("tupleRef")
            return self._tupleRef

    @property
    def order(self):
        """(float) -- order attribute of inline element or None if absent or float conversion error"""
        try:
            return self._order
        except AttributeError:
            try:
                orderAttr = self.get("order")
                self._order = float(orderAttr)
            except (ValueError, TypeError):
                self._order = None
            return self._order

    @property
    def footnoteRefs(self):
        """([str]) -- list of footnoteRefs attribute contents of inline element"""
        return self.get("footnoteRefs").split() if self.get("footnoteRefs") else []

    @property
    def format(self):
        """(QName) -- format attribute of inline element"""
        return self.prefixedNameQname(self.get("format"))

    @property
    def scale(self):
        """(str) -- scale attribute of inline element"""
        return self.get("scale")
    
    def transformedValue(self, value):
        """helper function for value"""
        num = 0
        negate = -1 if self.sign else 1
        try:
            if self.concept is not None:
                baseXsdType = self.concept.baseXsdType
                if baseXsdType in {"integer",
                                   "nonPositiveInteger","negativeInteger","nonNegativeInteger","positiveInteger",
                                   "long","unsignedLong",
                                   "int","unsignedInt",
                                   "short","unsignedShort",
                                   "byte","unsignedByte"}:
                    num = _INT(value)
                else:
                    num = float(value)
            else:
                num = float(value)
            scale = self.scale
            if scale is not None:
                num *= 10 ** _INT(self.scale)
        except ValueError:
            pass
        return "{0}".format(num * negate)
    
    @property
    def value(self):
        """(str) -- Overrides and corresponds to value property of ModelFact, 
        for relevant inner text nodes aggregated and transformed as needed."""
        try:
            return self._ixValue
        except AttributeError:
            v = XmlUtil.innerText(self, ixExclude=True, ixEscape=(self.get("escape") == "true"), strip=True) # transforms are whitespace-collapse
            f = self.format
            if f is not None:
                if (f.namespaceURI in FunctionIxt.ixtNamespaceURIs and
                    f.localName in FunctionIxt.ixtFunctions):
                    try:
                        v = FunctionIxt.ixtFunctions[f.localName](v)
                    except Exception as err:
                        self._ixValue = ModelValue.INVALIDixVALUE
                        raise err
            if self.localName == "nonNumeric" or self.localName == "tuple":
                self._ixValue = v
            else:
                self._ixValue = self.transformedValue(v)
            return self._ixValue

    @property
    def elementText(self):
        """(str) -- override xml-level elementText for transformed value text"""
        return self.value
    
    @property
    def propertyView(self):
        if self.localName == "nonFraction" or self.localName == "fraction":
            numProperties = (("format", self.format),
                ("scale", self.scale),
                ("html value", XmlUtil.innerText(self)))
        else:
            numProperties = ()
        return (("file", self.modelDocument.basename),
                ("line", self.sourceline)) + \
               super(ModelInlineFact,self).propertyView + \
               numProperties
        
    def __repr__(self):
        return ("modelInlineFact[{0}]{1})".format(self.objectId(),self.propertyView))
               
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
    def init(self, modelDocument):
        super(ModelContext, self).init(modelDocument)
        self.segDimValues = {}
        self.scenDimValues = {}
        self.qnameDims = {}
        self.errorDimValues = []
        self.segNonDimValues = []
        self.scenNonDimValues = []
        self._isEqualTo = {}
        
    @property
    def isStartEndPeriod(self):
        """(bool) -- True for startDate/endDate period"""
        try:
            return self._isStartEndPeriod
        except AttributeError:
            self._isStartEndPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, ("startDate","endDate"))
            return self._isStartEndPeriod
                                
    @property
    def isInstantPeriod(self):
        """(bool) -- True for instant period"""
        try:
            return self._isInstantPeriod
        except AttributeError:
            self._isInstantPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "instant")
            return self._isInstantPeriod

    @property
    def isForeverPeriod(self):
        """(bool) -- True for forever period"""
        try:
            return self._isForeverPeriod
        except AttributeError:
            self._isForeverPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "forever")
            return self._isForeverPeriod

    @property
    def startDatetime(self):
        """(datetime) -- startDate attribute"""
        try:
            return self._startDatetime
        except AttributeError:
            self._startDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "startDate"))
            return self._startDatetime

    @property
    def endDatetime(self):
        """(datetime) -- endDate or instant attribute, with adjustment to end-of-day midnight as needed"""
        try:
            return self._endDatetime
        except AttributeError:
            self._endDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, ("endDate","instant")), addOneDay=True)
            return self._endDatetime
        
    @property
    def instantDatetime(self):
        """(datetime) -- instant attribute, with adjustment to end-of-day midnight as needed"""
        try:
            return self._instantDatetime
        except AttributeError:
            self._instantDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "instant"), addOneDay=True)
            return self._instantDatetime
    
    @property
    def period(self):
        """(ModelObject) -- period element"""
        try:
            return self._period
        except AttributeError:
            self._period = XmlUtil.child(self, XbrlConst.xbrli, "period")
            return self._period

    @property
    def periodHash(self):
        """(int) -- hash of period start and end datetimes"""
        try:
            return self._periodHash
        except AttributeError:
            self._periodHash = hash((self.startDatetime,self.endDatetime)) # instant hashes (None, inst), forever hashes (None,None)
            return self._periodHash

    @property
    def entity(self):
        """(ModelObject) -- entity element"""
        try:
            return self._entity
        except AttributeError:
            self._entity = XmlUtil.child(self, XbrlConst.xbrli, "entity")
            return self._entity

    @property
    def entityIdentifierElement(self):
        """(ModelObject) -- entity identifier element"""
        try:
            return self._entityIdentifierElement
        except AttributeError:
            self._entityIdentifierElement = XmlUtil.child(self.entity, XbrlConst.xbrli, "identifier")
            return self._entityIdentifierElement

    @property
    def entityIdentifier(self):
        """( (str,str) ) -- tuple of (scheme value, identifier value)"""
        try:
            return self._entityIdentifier
        except AttributeError:
            eiElt = self.entityIdentifierElement
            if eiElt is not None:
                self._entityIdentifier = (eiElt.get("scheme"), eiElt.xValue)
            else:
                self._entityIdentifier = ("(Error)", "(Error)")
            return self._entityIdentifier

    @property
    def entityIdentifierHash(self):
        """(int) -- hash of entityIdentifier"""
        try:
            return self._entityIdentifierHash
        except AttributeError:
            self._entityIdentifierHash = hash(self.entityIdentifier)
            return self._entityIdentifierHash

    @property
    def hasSegment(self):
        """(bool) -- True if a xbrli:segment element is present"""
        return XmlUtil.hasChild(self.entity, XbrlConst.xbrli, "segment")

    @property
    def segment(self):
        """(ModelObject) -- xbrli:segment element"""
        return XmlUtil.child(self.entity, XbrlConst.xbrli, "segment")

    @property
    def hasScenario(self):
        """(bool) -- True if a xbrli:scenario element is present"""
        return XmlUtil.hasChild(self, XbrlConst.xbrli, "scenario")
    
    @property
    def scenario(self):
        """(ModelObject) -- xbrli:scenario element"""
        return XmlUtil.child(self, XbrlConst.xbrli, "scenario")
    
    def dimValues(self, contextElement):
        """(dict) -- Indicated context element's dimension dict (indexed by ModelConcepts)
        
        :param contextElement: 'segment' or 'scenario'
        :returns: dict of ModelDimension objects indexed by ModelConcept dimension object, or empty dict
        """
        if contextElement == "segment":
            return self.segDimValues
        elif contextElement == "scenario":
            return self.scenDimValues
        return {}
    
    def hasDimension(self, dimQname):
        """(bool) -- True if dimension concept qname is reported by context (in either context element), not including defaulted dimensions."""
        return dimQname in self.qnameDims
    
    # returns ModelDimensionValue for instance dimensions, else QName for defaults
    def dimValue(self, dimQname):
        """(ModelDimension or QName) -- ModelDimension object if dimension is reported (in either context element), or QName of dimension default if there is a default, otherwise None"""
        try:
            return self.qnameDims[dimQname]
        except KeyError:
            try:
                return self.modelXbrl.qnameDimensionDefaults[dimQname]
            except KeyError:
                return None
    
    def dimMemberQname(self, dimQname, includeDefaults=False):
        """(QName) -- QName of explicit dimension if reported (or defaulted if includeDefaults is True), else None"""
        dimValue = self.dimValue(dimQname)
        if isinstance(dimValue, (ModelDimensionValue,DimValuePrototype)) and dimValue.isExplicit:
            return dimValue.memberQname
        elif isinstance(dimValue, ModelValue.QName):
            return dimValue
        if dimValue is None and includeDefaults and dimQname in self.modelXbrl.qnameDimensionDefaults:
            return self.modelXbrl.qnameDimensionDefaults[dimQname]
        return None
    
    def dimAspects(self, defaultDimensionAspects=None):
        """(set) -- For formula and instance aspects processing, set of all dimensions reported or defaulted."""
        if defaultDimensionAspects:
            return _DICT_SET(self.qnameDims.keys()) | defaultDimensionAspects
        return _DICT_SET(self.qnameDims.keys())
    
    @property
    def dimsHash(self):
        """(int) -- A hash of the set of reported dimension values."""
        try:
            return self._dimsHash
        except AttributeError:
            self._dimsHash = hash( frozenset(self.qnameDims.values()) )
            return self._dimsHash
    
    def nonDimValues(self, contextElement):
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
            return XmlUtil.children(self.segment, None, "*")
        elif contextElement == Aspect.COMPLETE_SCENARIO and self.hasScenario:
            return XmlUtil.children(self.scenario, None, "*")
        return []
    
    @property
    def segmentHash(self):
        """(int) -- Hash of the segment, based on s-equality values"""
        return XbrlUtil.equalityHash( self.segment ) # self-caching
        
    @property
    def scenarioHash(self):
        """(int) -- Hash of the scenario, based on s-equality values"""
        return XbrlUtil.equalityHash( self.scenario ) # self-caching
    
    @property
    def nonDimSegmentHash(self):
        """(int) -- Hash, of s-equality values, of non-XDT segment objects"""
        try:
            return self._nonDimSegmentHash
        except AttributeError:
            self._nonDimSegmentHash = XbrlUtil.equalityHash(self.nonDimValues("segment"))
            return self._nonDimSegmentHash
        
    @property
    def nonDimScenarioHash(self):
        """(int) -- Hash, of s-equality values, of non-XDT scenario objects"""
        try:
            return self._nonDimScenarioHash
        except AttributeError:
            self._nonDimScenarioHash = XbrlUtil.equalityHash(self.nonDimValues("scenario"))
            return self._nonDimScenarioHash
        
    @property
    def nonDimHash(self):
        """(int) -- Hash, of s-equality values, of non-XDT segment and scenario objects"""
        try:
            return self._nonDimsHash
        except AttributeError:
            self._nonDimsHash = hash( (self.nonDimSegmentHash, self.nonDimScenarioHash) ) 
            return self._nonDimsHash
        
    @property
    def contextDimAwareHash(self):
        """(int) -- Hash of period, entityIdentifier, dim, and nonDims"""
        try:
            return self._contextDimAwareHash
        except AttributeError:
            self._contextDimAwareHash = hash( (self.periodHash, self.entityIdentifierHash, self.dimsHash, self.nonDimHash) )
            return self._contextDimAwareHash
        
    @property
    def contextNonDimAwareHash(self):
        """(int) -- Hash of period, entityIdentifier, segment, and scenario (s-equal based)"""
        try:
            return self._contextNonDimAwareHash
        except AttributeError:
            self._contextNonDimAwareHash = hash( (self.periodHash, self.entityIdentifierHash, self.segmentHash, self.scenarioHash) )
            return self._contextNonDimAwareHash
        
    
    def isPeriodEqualTo(self, cntx2):
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
        
    def isEntityIdentifierEqualTo(self, cntx2):
        """(bool) -- True if entityIdentifier values are equal (scheme and text value)"""
        return self.entityIdentifierHash == cntx2.entityIdentifierHash
    
    def isEqualTo(self, cntx2, dimensionalAspectModel=None):
        if dimensionalAspectModel is None: dimensionalAspectModel = self.modelXbrl.hasXDT
        try:
            return self._isEqualTo[(cntx2,dimensionalAspectModel)]
        except KeyError:
            result = self.isEqualTo_(cntx2, dimensionalAspectModel)
            self._isEqualTo[(cntx2,dimensionalAspectModel)] = result
            return result
        
    def isEqualTo_(self, cntx2, dimensionalAspectModel):
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
            if _DICT_SET(self.qnameDims.keys()) != _DICT_SET(cntx2.qnameDims.keys()):
                return False
            for dimQname, ctx1Dim in self.qnameDims.items():
                if not ctx1Dim.isEqualTo(cntx2.qnameDims[dimQname]):
                    return False
            for nonDimVals1, nonDimVals2 in ((self.segNonDimValues,cntx2.segNonDimValues),
                                             (self.scenNonDimValues,cntx2.scenNonDimValues)):
                if len(nonDimVals1) !=  len(nonDimVals2):
                    return False
                for i, nonDimVal1 in enumerate(nonDimVals1):
                    if not XbrlUtil.sEqual(self.modelXbrl, nonDimVal1, nonDimVals2[i]):
                        return False                    
        else:
            if self.hasSegment:
                if not cntx2.hasSegment:
                    return False
                if not XbrlUtil.sEqual(self.modelXbrl, self.segment, cntx2.segment):
                    return False
            elif cntx2.hasSegment:
                return False
    
            if self.hasScenario:
                if not cntx2.hasScenario:
                    return False
                if not XbrlUtil.sEqual(self.modelXbrl, self.scenario, cntx2.scenario):
                    return False
            elif cntx2.hasScenario:
                return False
        
        return True

    @property
    def propertyView(self):
        scheme, entityId = self.entityIdentifier
        return ((("entity", entityId, (("scheme", scheme),)),) +
                ((("forever", ""),) if self.isForeverPeriod else
                (("instant", XmlUtil.dateunionValue(self.instantDatetime, subtractOneDay=True)),) if self.isInstantPeriod else
                (("startDate", XmlUtil.dateunionValue(self.startDatetime)),("endDate", XmlUtil.dateunionValue(self.endDatetime, subtractOneDay=True)))) +
                (("dimensions", "({0})".format(len(self.qnameDims)),
                  tuple(mem.propertyView for dim,mem in sorted(self.qnameDims.items())))
                  if self.qnameDims else (),
                ))

    def __repr__(self):
        return ("modelContext[{0}, period: {1}, {2}{3} line {4}]"
                .format(self.id,
                        "forever" if self.isForeverPeriod else
                        "instant " + XmlUtil.dateunionValue(self.instantDatetime, subtractOneDay=True) if self.isInstantPeriod else
                        "duration " + XmlUtil.dateunionValue(self.startDatetime) + " - " + XmlUtil.dateunionValue(self.endDatetime, subtractOneDay=True),
                        "dimensions: ({0}) {1},".format(len(self.qnameDims),
                        tuple(mem.propertyView for dim,mem in sorted(self.qnameDims.items())))
                        if self.qnameDims else "",
                        self.modelDocument.basename, self.sourceline))

class ModelDimensionValue(ModelObject):
    """
    .. class:: ModelDimensionValue(modelDocument)
    
    Model dimension value (both explicit and typed, non-default values)
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument):
        super(ModelDimensionValue, self).init(modelDocument)
        
    def __hash__(self):
        if self.isExplicit:
            return hash( (self.dimensionQname, self.memberQname) )
        else: # need XPath equal so that QNames aren't lexically compared (for fact and context equality in comparing formula results)
            return hash( (self.dimensionQname, XbrlUtil.equalityHash(XmlUtil.child(self), equalMode=XbrlUtil.XPATH_EQ)) )
       
    @property
    def dimensionQname(self):
        """(QName) -- QName of the dimension concept"""
        return self.prefixedNameQname(self.get("dimension"))
        
    @property
    def dimension(self):
        """(ModelConcept) -- Dimension concept"""
        try:
            return self._dimension
        except AttributeError:
            self._dimension = self.modelXbrl.qnameConcepts.get(self.dimensionQname)
            return  self._dimension
        
    @property
    def isExplicit(self):
        """(bool) -- True if explicitMember element"""
        return self.localName == "explicitMember"
    
    @property
    def typedMember(self):
        """(ModelConcept) -- Child ModelObject that is the dimension member element
        
        (To get <typedMember> element use 'self').
        """
        for child in self.iterchildren():
            if isinstance(child, ModelObject):  # skip comment and processing nodes
                return child
        return None

    @property
    def isTyped(self):
        """(bool) -- True if typedMember element"""
        return self.localName == "typedMember"

    @property
    def memberQname(self):
        """(QName) -- QName of an explicit dimension member"""
        try:
            return self._memberQname
        except AttributeError:
            self._memberQname = self.prefixedNameQname(self.elementText) if self.isExplicit else None
            return self._memberQname
        
    @property
    def member(self):
        """(ModelConcept) -- Concept of an explicit dimension member"""
        try:
            return self._member
        except AttributeError:
            self._member = self.modelXbrl.qnameConcepts.get(self.memberQname)
            return  self._member
        
    def isEqualTo(self, other, equalMode=XbrlUtil.XPATH_EQ):
        """(bool) -- True if explicit member QNames equal or typed member nodes correspond, given equalMode (s-equal, s-equal2, or xpath-equal for formula)
        
        :param equalMode: XbrlUtil.S_EQUAL (ordinary S-equality from 2.1 spec), XbrlUtil.S_EQUAL2 (XDT definition of equality, adding QName comparisions), or XbrlUtil.XPATH_EQ (XPath EQ on all types)
        """
        if other is None:
            return False
        if self.isExplicit: # other is either ModelDimensionValue or the QName value of explicit dimension
            return self.memberQname == (other.memberQname if isinstance(other, (ModelDimensionValue,DimValuePrototype)) else other)
        else: # typed dimension compared to another ModelDimensionValue or other is the value nodes
            return XbrlUtil.nodesCorrespond(self.modelXbrl, self.typedMember, 
                                            other.typedMember if isinstance(other, (ModelDimensionValue,DimValuePrototype)) else other, 
                                            equalMode=equalMode, excludeIDs=XbrlUtil.NO_IDs_EXCLUDED)
        
    @property
    def contextElement(self):
        """(str) -- 'segment' or 'scenario'"""
        return self.getparent().localName
    
    @property
    def propertyView(self):
        if self.isExplicit:
            return (str(self.dimensionQname),str(self.memberQname))
        else:
            return (str(self.dimensionQname), XmlUtil.xmlstring( XmlUtil.child(self), stripXmlns=True, prettyPrint=True ) )
        
def measuresOf(parent):
    return sorted([m.xValue for m in parent.iterchildren(tag="{http://www.xbrl.org/2003/instance}measure") if isinstance(m, ModelObject) and m.xValue])

def measuresStr(m):
    return m.localName if m.namespaceURI in (XbrlConst.xbrli, XbrlConst.iso4217) else str(m)

class ModelUnit(ModelObject):
    """
    .. class:: ModelUnit(modelDocument)
    
    Model unit
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def init(self, modelDocument):
        super(ModelUnit, self).init(modelDocument)
        
    @property
    def measures(self):
        """([QName],[Qname]) -- Returns a tuple of multiply measures list and divide members list 
        (empty if not a divide element).  Each list of QNames is in prefixed-name order."""
        try:
            return self._measures
        except AttributeError:
            if self.isDivide:
                self._measures = (measuresOf(XmlUtil.descendant(self, XbrlConst.xbrli, "unitNumerator")),
                                  measuresOf(XmlUtil.descendant(self, XbrlConst.xbrli, "unitDenominator")))
            else:
                self._measures = (measuresOf(self),[])
            return self._measures

    @property
    def hash(self):
        """(bool) -- Hash of measures in both multiply and divide lists."""
        try:
            return self._hash
        except AttributeError:
            # should this use frozenSet of each measures element?
            self._hash = hash( ( tuple(self.measures[0]),tuple(self.measures[1]) ) )
            return self._hash

    @property
    def isDivide(self):
        """(bool) -- True if unit has a divide element"""
        return XmlUtil.hasChild(self, XbrlConst.xbrli, "divide")
    
    @property
    def isSingleMeasure(self):
        """(bool) -- True for a single multiply and no divide measures"""
        measures = self.measures
        return len(measures[0]) == 1 and len(measures[1]) == 0
    
    def isEqualTo(self, unit2):
        """(bool) -- True if measures are equal"""
        if unit2 is None or unit2.hash != self.hash: 
            return False
        return unit2 is self or self.measures == unit2.measures
    
    @property
    def value(self):
        """(str) -- String value for view purposes, space separated list of string qnames 
        of multiply measures, and if any divide, a '/' character and list of string qnames 
        of divide measure qnames."""
        mul, div = self.measures
        return ' '.join([measuresStr(m) for m in mul] + (['/'] + [measuresStr(d) for d in div] if div else []))

    @property
    def propertyView(self):
        measures = self.measures
        if measures[1]:
            return tuple(('mul',m) for m in measures[0]) + \
                   tuple(('div',d) for d in measures[1]) 
        else:
            return tuple(('measure',m) for m in measures[0])

from arelle.ModelFormulaObject import Aspect
from arelle import FunctionIxt
           
from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
     (XbrlConst.qnXbrliItem, ModelFact),
     (XbrlConst.qnXbrliTuple, ModelFact),
     (XbrlConst.qnIXbrlTuple, ModelInlineFact),
     (XbrlConst.qnIXbrlNonNumeric, ModelInlineFact),
     (XbrlConst.qnIXbrlNonFraction, ModelInlineFact),
     (XbrlConst.qnIXbrlFraction, ModelInlineFact),
     (XbrlConst.qnXbrliContext, ModelContext),
     (XbrlConst.qnXbrldiExplicitMember, ModelDimensionValue),
     (XbrlConst.qnXbrldiTypedMember, ModelDimensionValue),
     (XbrlConst.qnXbrliUnit, ModelUnit),
    ))
