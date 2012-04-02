'''
Created on Oct 5, 2010
Refactored from ModelObject on Jun 11, 2011

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from lxml import etree
from arelle import XmlUtil, XbrlConst, XbrlUtil, UrlUtil, Locale, ModelValue
from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals, roundValue
from arelle.ModelObject import ModelObject

class NewFactItemOptions():
    def __init__(self, savedOptions=None, xbrlInstance=None):
        self.entityIdentScheme = ""
        self.entityIdentValue = ""
        self.startDate = None
        self.endDate = None
        self.monetaryUnit = ""
        self.monetaryDecimals = ""
        self.nonMonetaryDecimals = ""
        if savedOptions is not None:
            self.__dict__.update(savedOptions)
        elif xbrlInstance is not None:
            for fact in xbrlInstance.facts:
                if fact.isItem:
                    cntx = fact.context
                    if not self.entityIdentScheme:
                        self.entityIdentScheme, self.entityIdentValue = cntx.entityIdentifier
                    if self.startDate is None and cntx.isStartEndPeriod:
                        self.startDate = cntx.startDatetime
                    if self.startDate is None and (cntx.isStartEndPeriod or cntx.isInstantPeriod):
                        self.endDate = cntx.endDatetime
                    if fact.isNumeric:
                        if fact.concept.isMonetary:
                            if not self.monetaryUnit and fact.unit.measures[0] and fact.unit.measures[0][0].namespaceURI == XbrlConst.iso4217:
                                self.monetaryUnit = fact.unit.measures[0][0].localName
                            if not self.monetaryDecimals:
                                self.monetaryDecimals = fact.decimals
                        elif not self.nonMonetaryDecimals:
                            self.nonMonetaryDecimals = fact.decimals
                if self.entityIdentScheme and self.startDate and self.monetaryUnit and self.monetaryDecimals and self.nonMonetaryDecimals:
                    break 
                
                
    
class ModelFact(ModelObject):
    def init(self, modelDocument):
        super(ModelFact, self).init(modelDocument)
        self.modelTupleFacts = []
        
    @property
    def concept(self):
        return self.elementDeclaration
        
    @property
    def contextID(self):
        return self.get("contextRef")

    @property
    def context(self):
        try:
            return self._context
        except AttributeError:
            self._context = self.modelXbrl.contexts.get(self.contextID)
            return self._context
    
    @property
    def unit(self):
        return self.modelXbrl.units.get(self.unitID)
    
    @property
    def unitID(self):
        return self.get("unitRef")

    @property
    def conceptContextUnitLangHash(self): # for EFM 6.5.12
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
        try:
            return self._isItem
        except AttributeError:
            concept = self.concept
            self._isItem = (concept is not None) and concept.isItem
            return self._isItem

    @property
    def isTuple(self):
        try:
            return self._isTuple
        except AttributeError:
            concept = self.concept
            self._isTuple = (concept is not None) and concept.isTuple
            return self._isTuple

    @property
    def isNumeric(self):
        try:
            return self._isNumeric
        except AttributeError:
            concept = self.concept
            self._isNumeric = (concept is not None) and concept.isNumeric
            return self._isNumeric

    @property
    def isFraction(self):
        try:
            return self._isFraction
        except AttributeError:
            concept = self.concept
            self._isFraction = (concept is not None) and concept.isFraction
            return self._isFraction
        
    @property
    def parentElement(self):
        return self.getparent()

    @property
    def ancestorQnames(self):
        try:
            return self._ancestorQnames
        except AttributeError:
            self._ancestorQnames = set( ModelValue.qname(ancestor) for ancestor in self.iterancestors() )
            return self._ancestorQnames

    @property
    def decimals(self):
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
        lang = self.get("{http://www.w3.org/XML/1998/namespace}lang")
        if lang is None and self.modelXbrl.modelManager.validateDisclosureSystem:
            concept = self.concept
            if concept is not None and not concept.isNumeric:
                lang = self.modelXbrl.modelManager.disclosureSystem.defaultXmlLang
        return lang
    
    @property
    def xsiNil(self):
        nil = self.get("{http://www.w3.org/2001/XMLSchema-instance}nil")
        return nil if nil else "false"
    
    @property
    def isNil(self):
        return self.xsiNil == "true"
    
    @property
    def value(self):
        v = self.elementText
        if not v:
            if self.concept.default is not None:
                v = self.concept.default
            elif self.concept.fixed is not None:
                v = self.concept.fixed
        return v
    
    @property
    def fractionValue(self):
        return (XmlUtil.text(XmlUtil.child(self, None, "numerator")),
                XmlUtil.text(XmlUtil.child(self, None, "denominator")))
    
    @property
    def effectiveValue(self):
        concept = self.concept
        if concept is None or concept.isTuple:
            return None
        if self.isNil:
            return "(nil)"
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

    @property
    def vEqValue(self): #v-equals value (numeric or string)
        if self.concept.isNumeric:
            return float(self.value)
        return self.value
    
    def isVEqualTo(self, other, deemP0Equal=False):  # facts may be in different instances
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
        
    def isDuplicateOf(self, other, topLevel=True, deemP0Equal=False):  # facts may be in different instances
        if self.isItem:
            if (self == other or
                self.qname != other or
                self.parentElement.qname != other.parentElement.qname):
                return False    # can't be identical
            # parent test can only be done if in same instauce
            if self.modelXbrl == other.modelXbrl and self.parentElement != other.parentElement:
                return False
            return  (self.context.isEqualTo(other.context,dimensionalAspectModel=False) and
                     (not self.isNumeric or self.unit.isEqualTo(other.unit)))
        elif self.isTuple:
            if (self == other or
                self.qname != other.qname or
                (topLevel and self.parentElement.qname != other.parentElement.qname)):
                return False    # can't be identical
            if self.isTuple:
                if len(self.modelTupleFacts) == len(other.modelTupleFacts):
                    for child1 in self.modelTupleFacts:
                        if child1.isItem:
                            if not any(child1.isVEqualTo(child2, deemP0Equal) for child2 in other.modelTupleFacts):
                                return False
                        elif child1.isTuple:
                            if not any(child1.isDuplicateOf( child2, topLevel=False, deemP0Equal=deemP0Equal) 
                                       for child2 in other.modelTupleFacts):
                                return False
                    return True
        else:
            return False

    @property
    def propertyView(self):
        try:
            concept = self.modelXbrl.qnameConcepts[self.qname]
            lbl = (("label", concept.label(lang=self.modelXbrl.modelManager.defaultLang)),)
        except KeyError:
            lbl = (("name", self.qname),)
        return lbl + (
               (("contextRef", self.contextID, self.context.propertyView),
                ("unitRef", self.unitID, self.unit.propertyView if self.isNumeric else ()),
                ("decimals", self.decimals),
                ("precision", self.precision),
                ("xsi:nil", self.xsiNil),
                ("value", self.effectiveValue.strip()))
                if self.isItem else () )
        
    def __repr__(self):
        return ("fact({0}{1}{2}, '{3}')".format(
                self.qname, 
                ', ' + self.contextID if self.get("contextRef") else '', 
                ', ' + self.unitID if self.get("unitRef") else '', 
                self.effectiveValue.strip() if self.isItem else '(tuple)'))
    
    @property
    def viewConcept(self):
        return self.concept

class ModelInlineFact(ModelFact):
    def init(self, modelDocument):
        super(ModelInlineFact, self).init(modelDocument)
        
    @property
    def qname(self):
        try:
            return self._factQname
        except AttributeError:
            self._factQname = self.prefixedNameQname(self.get("name")) if self.get("name") else None
            return self._factQname

    @property
    def sign(self):
        return self.get("sign")
    
    @property
    def tupleID(self):
        try:
            return self._tupleId
        except AttributeError:
            self._tupleId = self.get("tupleID")
            return self._tupleId
    
    @property
    def tupleRef(self):
        try:
            return self._tupleRef
        except AttributeError:
            self._tupleRef = self.get("tupleRef")
            return self._tupleRef

    @property
    def order(self):
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
        return self.get("footnoteRefs").split() if self.get("footnoteRefs") else []

    @property
    def format(self):
        return self.prefixedNameQname(self.get("format"))

    @property
    def scale(self):
        return self.get("scale")
    
    def transformedValue(self, value):
        num = 0
        negate = -1 if self.sign else 1
        try:
            num = float(value)
            scale = self.scale
            if scale is not None:
                num *= 10 ** _INT(self.scale)
        except ValueError:
            pass
        return "{0}".format(num * negate)
    
    @property
    def value(self):
        try:
            return self._ixValue
        except AttributeError:
            v = XmlUtil.innerText(self, ixExclude=True, strip=False)
            f = self.format
            if f is not None:
                if (f.namespaceURI in FunctionIxt.ixtNamespaceURIs and
                    f.localName in FunctionIxt.ixtFunctions):
                    v = FunctionIxt.ixtFunctions[f.localName](v)
            if self.localName == "nonNumeric" or self.localName == "tuple":
                self._ixValue = v
            else:
                self._ixValue = self.transformedValue(v)
            return self._ixValue

    @property
    def elementText(self):    # override xml-level elementText for transformed value text
        return self.value
    
    @property
    def propertyView(self):
        if self.localName == "nonFraction" or self.localName == "fraction":
            numProperties = (("format", self.format),
                ("scale", self.scale),
                ("html value", XmlUtil.innerText(self)))
        else:
            numProperties = ()
        return super(ModelInlineFact,self).propertyView + \
               numProperties
        
    def __repr__(self):
        return ("modelInlineFact[{0}]{1})".format(self.objectId(),self.propertyView))
               
class ModelContext(ModelObject):
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
        try:
            return self._isStartEndPeriod
        except AttributeError:
            self._isStartEndPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, ("startDate","endDate"))
            return self._isStartEndPeriod
                                
    @property
    def isInstantPeriod(self):
        try:
            return self._isInstantPeriod
        except AttributeError:
            self._isInstantPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "instant")
            return self._isInstantPeriod

    @property
    def isForeverPeriod(self):
        try:
            return self._isForeverPeriod
        except AttributeError:
            self._isForeverPeriod = XmlUtil.hasChild(self.period, XbrlConst.xbrli, "forever")
            return self._isForeverPeriod

    @property
    def startDatetime(self):
        try:
            return self._startDatetime
        except AttributeError:
            self._startDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "startDate"))
            return self._startDatetime

    @property
    def endDatetime(self):
        try:
            return self._endDatetime
        except AttributeError:
            self._endDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, ("endDate","instant")), addOneDay=True)
            return self._endDatetime
        
    @property
    def instantDatetime(self):
        try:
            return self._instantDatetime
        except AttributeError:
            self._instantDatetime = XmlUtil.datetimeValue(XmlUtil.child(self.period, XbrlConst.xbrli, "instant"), addOneDay=True)
            return self._instantDatetime
    
    @property
    def period(self):
        try:
            return self._period
        except AttributeError:
            self._period = XmlUtil.child(self, XbrlConst.xbrli, "period")
            return self._period

    @property
    def periodHash(self):
        try:
            return self._periodHash
        except AttributeError:
            self._periodHash = hash((self.startDatetime,self.endDatetime)) # instant hashes (None, inst), forever hashes (None,None)
            return self._periodHash

    @property
    def entity(self):
        try:
            return self._entity
        except AttributeError:
            self._entity = XmlUtil.child(self, XbrlConst.xbrli, "entity")
            return self._entity

    @property
    def entityIdentifierElement(self):
        try:
            return self._entityIdentifierElement
        except AttributeError:
            self._entityIdentifierElement = XmlUtil.child(self.entity, XbrlConst.xbrli, "identifier")
            return self._entityIdentifierElement

    @property
    def entityIdentifier(self):
        eiElt = self.entityIdentifierElement
        return (eiElt.get("scheme"), eiElt.xValue)

    @property
    def entityIdentifierHash(self):
        try:
            return self._entityIdentifierHash
        except AttributeError:
            self._entityIdentifierHash = hash(self.entityIdentifier)
            return self._entityIdentifierHash

    @property
    def hasSegment(self):
        return XmlUtil.hasChild(self.entity, XbrlConst.xbrli, "segment")

    @property
    def segment(self):
        return XmlUtil.child(self.entity, XbrlConst.xbrli, "segment")

    @property
    def hasScenario(self):
        return XmlUtil.hasChild(self, XbrlConst.xbrli, "scenario")
    
    @property
    def scenario(self):
        return XmlUtil.child(self, XbrlConst.xbrli, "scenario")
    
    def dimValues(self, contextElement):
        if contextElement == "segment":
            return self.segDimValues
        elif contextElement == "scenario":
            return self.scenDimValues
        return {}
    
    def hasDimension(self, dimQname):
        return dimQname in self.qnameDims
    
    # returns ModelDimensionValue for instance dimensions, else QName for defaults
    def dimValue(self, dimQname):
        if dimQname in self.qnameDims:
            return self.qnameDims[dimQname]
        elif dimQname in self.modelXbrl.qnameDimensionDefaults:
            return self.modelXbrl.qnameDimensionDefaults[dimQname]
        return None
    
    def dimMemberQname(self, dimQname, includeDefaults=False):
        dimValue = self.dimValue(dimQname)
        if isinstance(dimValue, ModelDimensionValue) and dimValue.isExplicit:
            return dimValue.memberQname
        elif isinstance(dimValue, ModelValue.QName):
            return dimValue
        if dimValue is None and includeDefaults and dimQname in self.modelXbrl.qnameDimensionDefaults:
            return self.modelXbrl.qnameDimensionDefaults[dimQname]
        return None
    
    def dimAspects(self, defaultDimensionAspects):
        return _DICT_SET(self.qnameDims.keys()) | defaultDimensionAspects
    
    @property
    def dimsHash(self):
        try:
            return self._dimsHash
        except AttributeError:
            self._dimsHash = hash( frozenset(self.qnameDims.values()) )
            return self._dimsHash
    
    def nonDimValues(self, contextElement):
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
        # s-equality hash
        return XbrlUtil.equalityHash( self.segment ) # self-caching
        
    @property
    def scenarioHash(self):
        # s-equality hash
        return XbrlUtil.equalityHash( self.scenario ) # self-caching
    
    @property
    def nonDimSegmentHash(self):
        try:
            return self._nonDimSegmentHash
        except AttributeError:
            self._nonDimSegmentHash = XbrlUtil.equalityHash(self.nonDimValues("segment"))
            return self._nonDimSegmentHash
        
    @property
    def nonDimScenarioHash(self):
        try:
            return self._nonDimScenarioHash
        except AttributeError:
            self._nonDimScenarioHash = XbrlUtil.equalityHash(self.nonDimValues("scenario"))
            return self._nonDimScenarioHash
        
    @property
    def nonDimHash(self):
        try:
            return self._nonDimsHash
        except AttributeError:
            self._nonDimsHash = hash( (self.nonDimSegmentHash, self.nonDimScenarioHash) ) 
            return self._nonDimsHash
        
    @property
    def contextDimAwareHash(self):
        try:
            return self._contextDimAwareHash
        except AttributeError:
            self._contextDimAwareHash = hash( (self.periodHash, self.entityIdentifierHash, self.dimsHash, self.nonDimHash) )
            return self._contextDimAwareHash
        
    @property
    def contextNonDimAwareHash(self):
        try:
            return self._contextNonDimAwareHash
        except AttributeError:
            self._contextNonDimAwareHash = hash( (self.periodHash, self.entityIdentifierHash, self.segmentHash, self.scenarioHash) )
            return self._contextNonDimAwareHash
        
    
    def isPeriodEqualTo(self, cntx2):
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
        return (("entity", entityId, entityId, (("scheme", scheme),)),
                (("forever", "") if self.isForeverPeriod else
                  (("instant", str(self.instantDatetime)) if self.isInstantPeriod else
                   (("startDate", str(self.startDatetime)),("endDate",str(self.endDatetime))))),
                ("dimensions", "({0})".format(len(self.qnameDims)),
                  tuple(mem.propertyView for dim,mem in sorted(self.qnameDims.items())))
                  if self.qnameDims else (),
                )


class ModelDimensionValue(ModelObject):
    def init(self, modelDocument):
        super(ModelDimensionValue, self).init(modelDocument)
        
    def __hash__(self):
        if self.isExplicit:
            return hash( (self.dimensionQname, self.memberQname) )
        else: # need XPath equal so that QNames aren't lexically compared (for fact and context equality in comparing formula results)
            return hash( (self.dimensionQname, XbrlUtil.equalityHash(XmlUtil.child(self), equalMode=XbrlUtil.XPATH_EQ)) )
       
    @property
    def dimensionQname(self):
        return self.prefixedNameQname(self.get("dimension"))
        
    @property
    def dimension(self):
        try:
            return self._dimension
        except AttributeError:
            self._dimension = self.modelXbrl.qnameConcepts.get(self.dimensionQname)
            return  self._dimension
        
    @property
    def isExplicit(self):
        return self.localName == "explicitMember"
    
    @property
    def typedMember(self):
        # to get <typedMember> element use 'self'; this get's its contents
        for child in self.iterchildren():
            if isinstance(child, ModelObject):  # skip comment and processing nodes
                return child
        return None

    @property
    def isTyped(self):
        return self.localName == "typedMember"

    @property
    def memberQname(self):
        try:
            return self._memberQname
        except AttributeError:
            self._memberQname = self.prefixedNameQname(self.elementText) if self.isExplicit else None
            return self._memberQname
        
    @property
    def member(self):
        try:
            return self._member
        except AttributeError:
            self._member = self.modelXbrl.qnameConcepts.get(self.memberQname)
            return  self._member
        
    def isEqualTo(self, other, equalMode=XbrlUtil.XPATH_EQ):
        if isinstance(other, ModelValue.QName):
            return self.isExplicit and self.memberQname == other
        elif other is None:
            return False
        elif self.isExplicit:
            return self.memberQname == other.memberQname
        else:
            return XbrlUtil.nodesCorrespond(self.modelXbrl, self.typedMember, other.typedMember, 
                                            equalMode=equalMode, excludeIDs=XbrlUtil.NO_IDs_EXCLUDED)
        
    @property
    def contextElement(self):
        return self.getparent().localName
    
    @property
    def propertyView(self):
        if self.isExplicit:
            return (str(self.dimensionQname),str(self.memberQname))
        else:
            return (str(self.dimensionQname), etree.tounicode( XmlUtil.child(self) ) )
        
def measuresOf(parent):
    return sorted([m.xValue for m in parent.iterchildren(tag="{http://www.xbrl.org/2003/instance}measure") if isinstance(m, ModelObject) and m.xValue])

def measuresStr(m):
    return m.localName if m.namespaceURI in (XbrlConst.xbrli, XbrlConst.iso4217) else str(m)

class ModelUnit(ModelObject):
    def init(self, modelDocument):
        super(ModelUnit, self).init(modelDocument)
        
    @property
    def measures(self):
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
        try:
            return self._hash
        except AttributeError:
            # should this use frozenSet of each measures element?
            self._hash = hash( ( tuple(self.measures[0]),tuple(self.measures[1]) ) )
            return self._hash

    @property
    def isDivide(self):
        return XmlUtil.hasChild(self, XbrlConst.xbrli, "divide")
    
    @property
    def isSingleMeasure(self):
        measures = self.measures
        return len(measures[0]) == 1 and len(measures[1]) == 0
    
    def isEqualTo(self, unit2):
        if unit2 is None or unit2.hash != self.hash: 
            return False
        return unit2 is self or self.measures == unit2.measures
    
    @property
    def value(self):
        mul, div = self.measures
        return ' '.join([measuresStr(m) for m in mul] + (['/'] + [measuresStr(d) for d in div] if div else []))

    @property
    def propertyView(self):
        if self.isDivide:
            return tuple(('mul',m) for m in self.measures[0]) + \
                   tuple(('div',d) for d in self.measures[1]) 
        else:
            return tuple(('',m) for m in self.measures[0])

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
