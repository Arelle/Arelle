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
from arelle import arelle_c, XmlUtil, XbrlConst, XbrlUtil, UrlUtil, Locale, ModelValue
from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals, roundValue, rangeValue
from arelle.XmlValidate import UNVALIDATED, INVALID, VALID
from arelle.PrototypeInstanceObject import DimValuePrototype
from math import isnan, isinf
from decimal import Decimal, InvalidOperation
from hashlib import md5
from arelle.HashUtil import md5hash, Md5Sum

Aspect = None
utrEntries = None
utrSymbol = None
POSINF = float("inf")
NEGINF = float("-inf")
DECIMALONE = Decimal(1)

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
                
    
class ModelFact(arelle_c.ModelFact):
    """
    .. class:: ModelFact(modelDocument)
    
    Model fact (both instance document facts and inline XBRL facts)
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument

        .. attribute:: modelTupleFacts
        
        ([ModelFact]) - List of child facts in source document order
    """
    def __init__(self, *args):
        super(ModelFact, self).__init__(*args)

    @property
    def utrEntries(self):
        """(set(UtrEntry)) -- set of UtrEntry objects that match this fact and unit"""
        if self.unit is not None and self.concept is not None:
            return self.unit.utrEntries(self.concept.type)
        return None
    
    def unitSymbol(self):
        """(str) -- utr symbol for this fact and unit"""
        if self.unit is not None and self.concept is not None:
            return self.unit.utrSymbol(self.concept.type)
        return ""

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
    def ancestorQnames(self):
        """(set) -- Set of QNames of ancestor elements (tuple and xbrli:xbrl)"""
        try:
            return self._ancestorQnames
        except AttributeError:
            self._ancestorQnames = set( ModelValue.qname(ancestor) for ancestor in self.iterancestors() )
            return self._ancestorQnames
        
    @property
    def fractionValue(self):
        """( (str,str) ) -- (text value of numerator, text value of denominator)"""
        try:
            return self._fractionValue
        except AttributeError:
            self._fractionValue =  ("", "")
            for numElt in self.iterchildren("{http://www.xbrl.org/2003/instance}numerator"):
                for denomElt in self.iterchildren("{http://www.xbrl.org/2003/instance}denominator"):
                    self._fractionValue = (XmlUtil.text(numElt), XmlUtil.text(denomElt))
                    break;
            return self._fractionValue
    
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
            if concept.isFraction:
                if self.xValid >= VALID:
                    return str(self.xValue)
                return "/".join(self.fractionValue)
            val = self.value
            if val is None: val = ""
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
                            dec = len(val.partition(".")[2])
                        else: # max decimals at 28
                            dec = max( min(int(dec), 28), -28) # 2.7 wants short int, 3.2 takes regular int, don't use _INT here
                        # return Locale.format(self.modelXbrl.locale, "%.*f", (dec, num), True)
                        # switch to new formatting so long-precision decimal numbers are correct
                        if dec < 0:
                            dec = 0 # {} formatting doesn't accept negative dec
                        return Locale.format(self.modelXbrl.locale, "{:.{}f}", (num,dec), True)
                except ValueError: 
                    return "(error)"
            if val is not None and len(val) == 0: # zero length string for HMRC fixed fact
                return "(reported)"
            return val
        except Exception as ex:
            return str(ex)  # could be transform value of inline fact

    @property
    def vEqValue(self):
        """(float or str) -- v-equal value, float if numeric, otherwise string value"""
        if self.concept.isNumeric:
            return float(self.value)
        return self.value
    
    def isVEqualTo(self, other, deemP0Equal=False, deemP0inf=False, normalizeSpace=True, numericIntervalConsistency=False):
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
            if other.concept.isNumeric:
                if self.unit is None or not self.unit.isEqualTo(other.unit):
                    return False
                
                if numericIntervalConsistency: # values consistent with being rounded from same number
                    (a1,b1) = rangeValue(self.value, inferredDecimals(self))
                    (a2,b2) = rangeValue(other.value, inferredDecimals(other))
                    return not (b1 < a2 or b2 < a1)
            
                if self.modelXbrl.modelManager.validateInferDecimals:
                    d = min((inferredDecimals(self), inferredDecimals(other))); p = None
                    if isnan(d):
                        if deemP0Equal:
                            return True
                        elif deemP0inf: # for test cases deem P0 as INF comparison
                            return self.xValue == other.xValue
                else:
                    d = None; p = min((inferredPrecision(self), inferredPrecision(other)))
                    if p == 0:
                        if deemP0Equal:
                            return True
                        elif deemP0inf: # for test cases deem P0 as INF comparison
                            return self.xValue == other.xValue
                return roundValue(self.value,precision=p,decimals=d) == roundValue(other.value,precision=p,decimals=d)
            else:
                return False
        elif self.concept.isFraction:
            return (other.concept.isFraction and
                    self.unit is not None and self.unit.isEqualTo(other.unit) and 
                    self.xValue == other.xValue)
        elif type(self.xValue) == ModelValue.DateTime == type(other.xValue):
            return self.xValue == other.xValue # required to handle date/time with 24 hrs.
        selfValue = self.value
        otherValue = other.value
        if normalizeSpace and isinstance(selfValue,str) and isinstance(otherValue,str): # normalized space comparison
            return ' '.join(selfValue.split()) == ' '.join(otherValue.split())
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
                self.qname != other.qname or
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
    def md5sum(self):  # note this must work in --skipDTS and streaming modes
        _toHash = [self.qname]
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
    def propertyView(self):
        try:
            concept = self.concept
            lbl = (("label", concept.label(lang=self.modelXbrl.modelManager.defaultLang)),)
        except (KeyError, AttributeError):
            lbl = ()
        if self.isNumeric and self.unit is not None:
            unitValue = self.unitID
            unitSymbol = self.unitSymbol()
            if unitSymbol: 
                unitValue += " (" + unitSymbol + ")"
        return lbl + (
               (("namespace", self.qname.namespaceURI),
                ("name", self.qname.localName),
                ("QName", self.qname)) + 
               (((("contextRef", self.contextID, self.context.propertyView) if self.context is not None else ()),
                 (("unitRef", unitValue, self.unit.propertyView) if self.isNumeric and self.unit is not None else ()),
                 (("decimals", self.decimals) if self.isNumeric and self.decimals is not None else ()),
                 (("precision", self.precision) if self.isNumeric and self.precision is not None else ()),
                 ("xsi:nil", "true" if self.isNil else "false"),
                 ("value", self.effectiveValue.strip()))
                 if self.isItem else () ))
        
    def __repr__(self):
        return ("modelFact[{0}, qname: {1}, contextRef: {2}, unitRef: {3}, value: {4}, {5}, line {6}]"
                .format(self.objectIndex, self.qname, self.contextID, self.unitID,
                        (self.effectiveValue or "").strip() if self.isItem else '(tuple)',
                        self.modelDocument.basename, self.sourceline))
    
    @property
    def viewConcept(self):
        return self.concept
    
class ModelInlineValueObject:
    def __init__(self, modelDocument):
        super(ModelInlineValueObject, self).__init__(modelDocument)
        
    @property
    def sign(self):
        """(str) -- sign attribute of inline element"""
        return self.get("sign")
    
    @property
    def format(self):
        """(QName) -- format attribute of inline element"""
        return self.get("format")

    @property
    def scale(self):
        """(int) -- scale attribute of inline element"""
        return self.get("scale")
        
    def setInvalid(self):
        self._ixValue = ModelValue.INVALIDixVALUE
        self.setInlineFactValue(INVALID, None)
    
    @property
    def value(self):
        """(str) -- Overrides and corresponds to value property of ModelFact, 
        for relevant inner text nodes aggregated and transformed as needed."""
        try:
            return self._ixValue
        except AttributeError:
            self.setInlineFactValue(UNVALIDATED) # may not be initialized otherwise
            f = self.format
            ixEscape = self.get("escape", False)
            v = XmlUtil.innerText(self, 
                                  ixExclude="tuple" if self.elementQName == XbrlConst.qnIXbrl11Tuple else "html", 
                                  ixEscape=ixEscape, 
                                  ixContinuation=(self.elementQName == XbrlConst.qnIXbrl11NonNumeric),
                                  ixResolveUris=ixEscape,
                                  strip=(f is not None)) # transforms are whitespace-collapse, otherwise it is preserved.
            if self.isNil:
                self._ixValue = v
            else:
                if f is not None:
                    if f.namespaceURI in FunctionIxt.ixtNamespaceFunctions:
                        try:
                            v = FunctionIxt.ixtNamespaceFunctions[f.namespaceURI][f.localName](v)
                        except KeyError as err:
                            self._ixValue = ModelValue.INVALIDixVALUE
                            raise FunctionIxt.ixtFunctionNotAvailable
                        except Exception as err:
                            self._ixValue = ModelValue.INVALIDixVALUE
                            raise err
                    else:
                        try:
                            v = self.modelXbrl.modelManager.customTransforms[f](v)
                        except KeyError as err:
                            self._ixValue = ModelValue.INVALIDixVALUE
                            raise FunctionIxt.ixtFunctionNotAvailable
                        except Exception as err:
                            self._ixValue = ModelValue.INVALIDixVALUE
                            raise err
                if self.localName == "nonNumeric":
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
                        raise ValueError("Invalid value for {} number: {}".format(self.localName, v))
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
                            if num == num.to_integral() and ".0" not in v:
                                num = num.quantize(DECIMALONE) # drop any .0
                            self._ixValue = "{:f}".format(num)
                    except (ValueError, InvalidOperation):
                        self.setInvalid()
                        raise ValueError("Invalid value for {} scale {} for number {}".format(self.localName, scale, v))
            return self._ixValue

    @property
    def textValue(self):
        """(str) -- override xml-level textValue for transformed value text()
            will raise any value errors if transforming string or numeric has an error
        """
        return self.value
    
    @property
    def stringValue(self):
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
    def __init__(self, *args):
        super(ModelInlineFact, self).__init__(*args)
        
    @property
    def qname(self):
        """(QName) -- QName of concept from the name attribute, overrides and corresponds to the qname property of a ModelFact (inherited from ModelObject)"""
        return self.get("name")

    @property
    def tupleID(self):
        """(str) -- tupleId attribute of inline element"""
        return self.get("tupleID")
    
    @property
    def tupleRef(self):
        """(str) -- tupleRef attribute of inline element"""
        return self.get("tupleRef")

    @property
    def order(self):
        """(Decimal) -- order attribute of inline element or None if absent or Decimal conversion error"""
        try:
            return self._order
        except AttributeError:
            try:
                orderAttr = self.get("order")
                self._order = Decimal(orderAttr)
            except (ValueError, TypeError, InvalidOperation):
                self._order = None
            return self._order

    @property
    def parentElement(self):
        """(ModelObject) -- parent element (tuple or xbrli:xbrl) of the inline target instance document
            for inline root element, the xbrli:xbrl element is substituted for by the inline root element"""
        return getattr(self, "_ixFactParent") # set by ModelDocument locateFactInTuple for the inline target's root element

    @property
    def fractionValue(self):
        """( (str,str) ) -- (text value of numerator, text value of denominator)"""
        for numElt in self.iterdescendants(self.modelDocument.ixNStag + "numerator"): # note that inline elements have xbrli qnames
            for denomElt in self.iterdescendants(self.modelDocument.ixNStag + "denominator"):
                return (XmlUtil.text(numElt), XmlUtil.text(denomElt))
        return ("", "")
    
    @property
    def footnoteRefs(self):
        """([str]) -- list of footnoteRefs attribute contents of inline element"""
        return self.get("footnoteRefs", "").split()

    def __iter__(self):
        if self.localName == "fraction":
            for n in self.iterdescendants(self.modelDocument.ixNStag + "numerator"):
                for d in self.iterdescendants(self.modelDocument.ixNStag + "denominator"):
                    yield n
                    yield d
                    break
        for tupleFact in self.modelTupleFacts:
            yield tupleFact
            
    def setup(self):
        print("ModelInlineFact.setup")
        super(ModelInlineFact,self).setup()
     
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
    
class ModelInlineFraction(ModelInlineFact):
    def __init__(self, modelDocument):
        super(ModelInlineFraction, self).__init__(modelDocument)
        
    @property
    def textValue(self):
        return ""  # no text value for fraction

class ModelInlineFractionTerm(ModelInlineValueObject, arelle_c.ModelObject):
    def __init__(self, modelDocument):
        super(ModelInlineFractionTerm, self).__init__(modelDocument)
        self.isNil = False # required for inherited value property
        self.modelTupleFacts = [] # required for inherited XmlValudate of fraction term
        
    @property
    def qname(self):
        if self.localName == "numerator":
            return XbrlConst.qnXbrliNumerator
        elif self.localName == "denominator":
            return XbrlConst.qnXbrliDenominator
        return self.elementQName
    
    @property
    def concept(self):
        return self.modelXbrl.qnameConcepts.get(self.qname) # for fraction term type determination
    
    def setInlineFactValue(self, xValid, xValue=None):
        pass # not relevant for fraction term

    def __iter__(self):
        if False: yield None # generator with nothing to generate
    
               
class ModelContext(arelle_c.ModelContext):
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
    def __init__(self, *args):
        super(ModelContext, self).__init__(*args)
        

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
        
    @property
    def md5sum(self):
        try:
            return self._md5sum
        except AttributeError:
            _toHash = [self.entityIdentifier[0], self.entityIdentifier[1]]
            if self.isInstantPeriod:
                _toHash.append(self.instantDatetime)
            elif self.isStartEndPeriod:
                _toHash.append(self.startDatetime)
                _toHash.append(self.endDatetime)
            elif self.isForeverPeriod:
                _toHash.append("forever")
            if self.qnameDims:
                _toHash.extend([dim.md5sum for dim in self.qnameDims.values()])
            self._md5sum = md5hash(_toHash)
            return self._md5sum
    
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


class ModelDimensionValue(arelle_c.ModelDimensionValue):
    """
    .. class:: ModelDimensionValue(modelDocument)
    
    Model dimension value (both explicit and typed, non-default values)
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def __init__(self, modelDocument):
        super(ModelDimensionValue, self).__init__(modelDocument)
        
    @property
    def md5sum(self):
        if self.isExplicit:
            return md5hash([self.dimensionQName, self.memberQName])
        else:
            return md5hash([self.dimensionQName, self.typedMember])
    
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
    def propertyView(self):
        if self.isExplicit:
            return (str(self.dimensionQName),str(self.memberQName))
        else:
            return (str(self.dimensionQName), XmlUtil.xmlstring( XmlUtil.child(self), stripXmlns=True, prettyPrint=True ) )
        
class ModelUnit(arelle_c.ModelUnit):
    """
    .. class:: ModelUnit(modelDocument)
    
    Model unit
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def __init__(self, *args):
        super(ModelUnit, self).__init__(*args)
                
    @property
    def md5hash(self):
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
                        md5hash.update(measure.namespaceURI.encode('utf-8','replace'))
                    md5hash.update(measure.localName.encode('utf-8','replace'))
            # should this use frozenSet of each measures element?
            self._md5hash = md5hash.hexdigest()
            return self._md5hash
    
    @property
    def md5sum(self):
        try:
            return self._md5sum
        except AttributeError:
            if self.isDivide: # hash of mult and div hex strings of hashes of measures
                self._md5sum = md5hash([md5hash([md5hash(m) for m in md]).toHex() 
                                        for md in self.measures])
            else: # sum of hash sums
                self._md5sum = md5hash([md5hash(m) for m in self.measures[0]])
            return self._md5sum
 
    def utrEntries(self, modelType):
        try:
            return self._utrEntries[modelType]
        except AttributeError:
            self._utrEntries = {}
            return self.utrEntries(modelType)
        except KeyError:
            global utrEntries
            if utrEntries is None:
                from arelle.ValidateUtr import utrEntries
            self._utrEntries[modelType] = utrEntries(modelType, self)
            return self._utrEntries[modelType]
    
    def utrSymbol(self, modelType):
        try:
            return self._utrSymbols[modelType]
        except AttributeError:
            self._utrSymbols = {}
            return self.utrSymbol(modelType)
        except KeyError:
            global utrSymbol
            if utrSymbol is None:
                from arelle.ValidateUtr import utrSymbol
            self._utrSymbols[modelType] = utrSymbol(modelType, self.measures)
            return self._utrSymbols[modelType]
                
    
class ModelInlineFootnote(arelle_c.ModelXlinkResource):
    """
    .. class:: ModelInlineFootnote(modelDocument)
    
    Model inline footnote (inline XBRL facts)
    
    :param modelDocument: owner document
    :type modelDocument: ModelDocument
    """
    def __init__(self, modelDocument):
        super(ModelInlineFootnote, self).__init__(modelDocument)
        
    @property
    def qname(self):
        """(QName) -- QName of generated object"""
        return XbrlConst.qnLinkFootnote
    
    @property
    def footnoteID(self):
        if self.namespaceURI == XbrlConst.ixbrl:
            return self.get("footnoteID")
        else:
            return self.id

    @property
    def value(self):
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
    def textValue(self):
        """(str) -- override xml-level stringValue for transformed value descendants text"""
        return self.value
        
    @property
    def stringValue(self):
        """(str) -- override xml-level stringValue for transformed value descendants text"""
        return self.value
    
    @property
    def role(self):
        """(str) -- xlink:role attribute"""
        return self.get("footnoteRole") or XbrlConst.footnote
        
    @property
    def xlinkLabel(self):
        """(str) -- xlink:label attribute"""
        return self.footnoteID

    @property
    def xmlLang(self):
        """(str) -- xml:lang attribute"""
        return XmlUtil.ancestorOrSelfAttr(self, "{http://www.w3.org/XML/1998/namespace}lang")
    
    @property
    def attributes(self):
        # for output of derived instance, includes all output-applicable attributes
        attributes = {"{http://www.w3.org/1999/xlink}type":"resource",
                      "{http://www.w3.org/1999/xlink}label":self.xlinkLabel,
                      "{http://www.w3.org/1999/xlink}role": self.role}
        if self.id:
            attributes["id"] = self.footnoteID
        lang = self.xmlLang
        if lang:
            attributes["{http://www.w3.org/XML/1998/namespace}lang"] = lang
        return attributes

    def viewText(self, labelrole=None, lang=None):
        return self.value
        
    @property
    def propertyView(self):
        return (("file", self.modelDocument.basename),
                ("line", self.sourceline)) + \
               super(ModelInlineFootnote,self).propertyView + \
               (("html value", XmlUtil.innerText(self)),)
        
    def __repr__(self):
        return ("modelInlineFootnote[{0}]{1})".format(self.objectId(),self.propertyView))
               
        
from arelle.ModelFormulaObject import Aspect
from arelle import FunctionIxt
           
from arelle.ModelObjectFactory import registerModelObjectClass
for _qn, _class in ((
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
     )):
    registerModelObjectClass(_qn, _class)
