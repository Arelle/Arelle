from fractions import Fraction
from arelle import ModelDtsObject, ModelInstanceObject, ModelValue, XbrlConst, XbrlUtil, XmlUtil

cdef class ModelFact(ModelObject): # wrapped by python ModelFact
    cdef readonly bool isItem, isTuple
    cdef readonly unicode contextID, unitID
    cdef readonly object decimals, precision # union type, integer or string
    cdef readonly ModelConcept concept
    cdef readonly list modelTupleFacts # null if not a tuple, else initialized as a list
    cdef readonly ModelContext _context
    cdef readonly ModelUnit _unit
    cdef bool _contextIsSet, _unitIsSet
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.modelTupleFacts = list()
        self.isItem = self.isTuple = False
        self.contextID = self.unitID = None
        self.decimals = self.precision = None
        self.concept = None
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        if isAttribute:
            if equals(localName, nFactIsTuple):
                self.isItem = not pyValue
                self.isTuple = pyValue
                if self.isTuple:
                    self.modelTupleFacts = list()
                return
            elif namespace[0] == chNull:
                if equals(localName, lnContextRef):
                    self.contextID = pyValue
                    return
                elif equals(localName, lnUnitRef):
                    self.unitID = pyValue
                    return
                elif equals(localName, lnDecimals):
                    self.decimals = pyValue
                    return
                elif equals(localName, lnPrecision):
                    self.precision = pyValue
                    return
        else:
            if traceToStdout: print("modelFact {} setValue {} {}".format(self.objectIndex, 
                                                       "tail" if namespace == nElementTail else
                                                       "typedValue" if namespace == nElementTypedValue else "text", pyValue))
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)
        
    cdef setup(self): # element attributes have been set up
        ModelObject.setup(self)
        self.concept = self.elementDeclaration() # need this before modelFact.setup is called (after child objects); null for inline XBRL facts
        cdef ModelXbrl modelXbrl = self.modelDocument.modelXbrl
        cdef object numerator, denominator
        cdef object intnumerator, intdenominator # want python int, number may be too large for int or long
        if self.concept is not None:
            if isinstance(self._parent, ModelFact):
                self._parent.modelTupleFacts.append(self)
            else:
                modelXbrl.facts.append(self)
            modelXbrl.factsInInstance.add(self)
            # traditional instance fraction value
            if (self._firstChild is not None and self._firstChild.qname == qnXbrliNumerator and self._lastChild.qname == qnXbrliDenominator and 
                type(self).__name__ != "ModelInlineFact" and self._firstChild.xValid == VALID and self._lastChild.xValid == VALID and not self.isNil):
                    numerator = self._firstChild.xValue
                    denominator = self._lastChild.xValue
                    intnumerator = int(numerator)
                    intdenominator = int(denominator)
                    # if exact integers use those as fraction arguments, else 1/3 looks like 333333333333333/10000000000000
                    if numerator == intnumerator and denominator == intdenominator:
                        self.xValue = Fraction(intnumerator, intdenominator)
                    else:
                        self.xValue = Fraction(numerator / denominator) # xValues are Decimal
        elif type(self).__name__ != "ModelInlineFact":
            modelXbrl.undefinedFacts.append(self) # do not accumulate inline XBRL facts here
            
    def setupTargetInlineFact(self): # for inline XBRL setup with effective QName for fact
        if traceToStdout: print("setupTargetInlineFact trace 1")
        cdef ModelConcept _concept = self.modelDocument.modelXbrl.qnameConcepts.get(self.get("name"))
        if traceToStdout: print("setupTargetInlineFact trace 2")
        self.concept = _concept
        if traceToStdout: print("setupTargetInlineFact trace 3")
        if _concept is not None:
            if traceToStdout: print("setupTargetInlineFact trace 4")
            self.setValue(nFactIsTuple, nFactIsTuple, _concept.isTuple, OBJECT_PROPERTY)
        if traceToStdout: print("setupTargetInlineFact trace 5")
        
    def setInlineFactValue(self, xValid, xValue=NO_VALUE):
        if traceToStdout: print("setInlineFactTypedValue {} value {}".format(self.objectIndex, xValue))
        self.setValue(nValidity, NULL, xValid, OBJECT_PROPERTY)
        if xValue is not NO_VALUE:
            self.setValue(nElementTypedValue, NULL, xValue, OBJECT_VALUE)

    def iterAttrs(self):
        if self.contextID is not None:
            yield (uContextRef, self.contextID)
        if self.unitID is not None:
            yield (uUnitRef, self.unitID)
        if self.decimals is not None:
            yield (uPrecision, self.decimals)
        if self.precision is not None:
            yield (uDecimals, self.precision)
        ModelObject.iterAttrs()      
        
    @property
    def isNumeric(self):
        if self.concept is not None:
            return self.concept.isNumeric

    @property
    def isFraction(self):
        if self.concept is not None:
            return self.concept.isFraction

    @property
    def isMultiLanguage(self):
        """(bool) -- concept.type.isMultiLanguage (string or normalized string)"""
        return self.concept is not None and self.concept.type is not None and self.concept.type.isMultiLanguage
        
    @property
    def parentElement(self):
        """(ModelObject) -- parent element (tuple or xbrli:xbrl)"""
        return self.getparent()

    @property
    def context(self):
        """(ModelContext) -- context of the fact if any else None (e.g., tuple)"""
        if not self._contextIsSet:
            self._context = self.modelDocument.modelXbrl.contexts.get(self.contextID)
            self._contextIsSet = True
        return self._context
    
    @property
    def unit(self):
        """(ModelUnit) -- unit of the fact if any else None (e.g., non-numeric or tuple)"""
        if not self._unitIsSet:
            self._unit = self.modelDocument.modelXbrl.units.get(self.unitID)
            self._unitIsSet = True
        return self._unit
    
    def setDecimals(self, unicode decimals):
        self.decimals = decimals

    @property
    def xsiNil(self):
        """(str) -- value of xsi:nil or 'false' if absent"""
        return "true" if self.isNil else "false"
    
    def setIsNil(self, value):
        if value:
            self.isNil = True
            self.decimals = None  # can't leave decimals or precision
            self.precision = None
        else:
            self.isNil = False
            
    @property
    def value(self):
        """(str) --- string value of the fact"""
        if self.xValue is not None:
            if self.concept is not None:
                if self.concept.baseXsdType == "boolean":
                    return str(self.xValue).lower()
            return str(self.xValue)
        elif not self.isNumeric: # None but string valued
            return "" # empty string for absent value
        return None
        
cdef newModelFact(ModelDocument modelDocument, bool isTuple):
    cdef ModelFact modelFact
    modelFact = ModelInstanceObject.ModelFact(modelDocument) # python ModelFact wraps cython ModelFact
    modelFact.setValue(nFactIsTuple, nFactIsTuple, isTuple, OBJECT_PROPERTY)
    return modelFact

cdef class ModelContext(ModelObject): # wrapped by python ModelFact
    cdef readonly dict segDimValues
    cdef readonly dict scenDimValues
    cdef readonly dict qnameDims
    cdef readonly list errorDimValues
    cdef readonly list segNonDimValues
    cdef readonly list scenNonDimValues
    cdef readonly object entityIdentifier
    cdef readonly dict _isEqualTo
    cdef readonly hash_t periodHash, entityIdentifierHash
    cdef readonly bool isStartEndPeriod, isInstantPeriod, isForeverPeriod, hasSegment, hasScenario
    cdef readonly object startDatetime, endDatetime, instantDatetime
    cdef readonly ModelObject period, entity, segment, scenario
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.segDimValues = dict()
        self.scenDimValues = dict()
        self.qnameDims = dict()
        self.errorDimValues = list()
        self.segNonDimValues = list()
        self.scenNonDimValues = list()
        self._isEqualTo = dict()
        self.isStartEndPeriod = self.isInstantPeriod = self.isForeverPeriod = False
        self.hasSegment = self.hasScenario = False
        self.entity = self.segment = self.scenario = self.period = None
        self.startDatetime = self.endDatetime = self.instantDatetime = None
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)
        
    cdef setupDims(self, ModelObject parentElt, dict dimValues, list nonDimValues):
        cdef ModelObject sElt
        cdef ModelConcept dimModelConcept
        if traceToStdout: print("setup dims 1")
        if parentElt is None:
            return
        if traceToStdout: print("setup dims 2")
        for sElt in parentElt.iterchildren():
            if traceToStdout: print("setup dims qn {}".format(sElt.qname))
            if sElt.qname == qnXbrldiExplicitMember or sElt.qname == qnXbrldiTypedMember:
                self.qnameDims[sElt.dimensionQName] = sElt # both segment and scenario
                dimModelConcept = sElt.dimension
                if dimModelConcept is not None and dimModelConcept not in dimValues:
                    dimValues[dimModelConcept] = sElt
                else:
                    self.errorDimValues.append(sElt)
            else:
                nonDimValues.append(sElt)

    cdef setup(self): # element attributes have been set up
        ModelObject.setup(self)
        cdef ModelXbrl modelXbrl = self.modelDocument.modelXbrl
        cdef ModelObject elt1, elt2
        cdef QName qn
        cdef object xValue
        for elt1 in self.iterchildren():
            qn = elt1.qname
            if qn == qnXbrliPeriod:
                self.period = elt1
                for elt2 in elt1.iterchildren():
                    qn = elt2.qname
                    xValue = elt2.xValue
                    if qn == qnXbrliStartDate:
                        self.isStartEndPeriod = True
                        self.startDatetime = xValue
                    elif qn == qnXbrliEndDate:
                        self.isStartEndPeriod = True
                        self.endDatetime = xValue
                    elif qn == qnXbrliInstant:
                        self.isInstantPeriod = True
                        self.instantDatetime = self.endDatetime = xValue
                    elif qn == qnXbrliForever:
                        self.isForeverPeriod = True
            elif qn == qnXbrliEntity:
                self.entity = elt1
                for elt2 in elt1.iterchildren():
                    qn = elt2.qname
                    if qn == qnXbrliIdentifier:
                        self.entityIdentifier = (elt2.get("scheme"), elt2.xValue)
                    elif qn == qnXbrliSegment:
                        self.hasSegment = True
                        self.segment = elt2
                        self.setupDims(elt2, self.segDimValues, self.segNonDimValues)
            elif qn == qnXbrliScenario:
                self.scenario = elt1
                self.hasScenario = True
                self.setupDims(elt1, self.scenDimValues, self.scenNonDimValues)
                
        self.periodHash = PyObject_Hash( (self.startDatetime,self.endDatetime) )
        self.entityIdentifierHash = PyObject_Hash(self.entityIdentifier)
        modelXbrl.contexts[self.id] = self
    
    def dimValues(self, contextElement):
        """(dict) -- Indicated context element's dimension dict (indexed by ModelConcepts)
        
        :param contextElement: 'segment' or 'scenario'
        :returns: dict of ModelDimension objects indexed by ModelConcept dimension object, or empty dict
        """
        if contextElement == uSegment:
            return self.segDimValues
        elif contextElement == uScenario:
            return self.scenDimValues
        return EMPTY_DICT
    
    def hasDimension(self, dimQName):
        """(bool) -- True if dimension concept qname is reported by context (in either context element), not including defaulted dimensions."""
        return dimQName in self.qnameDims
    
    # returns ModelDimensionValue for instance dimensions, else QName for defaults
    def dimValue(self, dimQName):
        """(ModelDimension or QName) -- ModelDimension object if dimension is reported (in either context element), or QName of dimension default if there is a default, otherwise None"""
        try:
            return self.qnameDims[dimQName]
        except KeyError:
            try:
                return self.modelXbrl.qnameDimensionDefaults[dimQName]
            except KeyError:
                return None
    
    def dimMemberQName(self, dimQName, includeDefaults=False):
        """(QName) -- QName of explicit dimension if reported (or defaulted if includeDefaults is True), else None"""
        dimValue = self.dimValue(dimQName)
        if isinstance(dimValue, ModelDimensionValue) and dimValue.isExplicit:
            return dimValue.memberQName
        elif isinstance(dimValue, QName):
            return dimValue
        if dimValue is None and includeDefaults and dimQName in self.modelXbrl.qnameDimensionDefaults:
            return self.modelXbrl.qnameDimensionDefaults[dimQName]
        return None
    
    def dimAspects(self, defaultDimensionAspects=None):
        """(set) -- For formula and instance aspects processing, set of all dimensions reported or defaulted."""
        if defaultDimensionAspects:
            return self.qnameDims.keys() | defaultDimensionAspects
        return self.qnameDims.keys()
    
    @property
    def propertyView(self):
        return ((("entity", self.entityIdentifier[1], (("scheme", self.entityIdentifier[0]),)),) +
                ((("forever", ""),) if self.isForeverPeriod else
                 (("instant", XmlUtil.dateunionValue(self.instantDatetime, subtractOneDay=True)),) if self.isInstantPeriod else
                 (("startDate", XmlUtil.dateunionValue(self.startDatetime)),("endDate", XmlUtil.dateunionValue(self.endDatetime, subtractOneDay=True))) if self.isStartEndPeriod else
                 (("(none)", ""),) ) +
                (("dimensions", "({0})".format(len(self.qnameDims)),
                  tuple(mem.propertyView for dim,mem in sorted(self.qnameDims.items())))
                  if self.qnameDims else (),
                ))

    def __repr__(self):
        return ("modelContext[{0}, period: {1}, {2}{3} line {4}]"
                .format(self.id,
                        "forever" if self.isForeverPeriod else
                        "instant " + XmlUtil.dateunionValue(self.instantDatetime, subtractOneDay=True) if self.isInstantPeriod else
                        "duration " + XmlUtil.dateunionValue(self.startDatetime) + " - " + XmlUtil.dateunionValue(self.endDatetime, subtractOneDay=True) if self.isStartEndPeriod else
                        "none",
                        "dimensions: ({0}) {1},".format(len(self.qnameDims),
                        tuple(mem.propertyView for dim,mem in sorted(self.qnameDims.items())))
                        if self.qnameDims else "",
                        self.modelDocument.basename, self.sourceline))

        
cdef newModelContext(ModelDocument modelDocument):
    cdef ModelContext modelContext
    modelContext = ModelInstanceObject.ModelContext(modelDocument) # python ModelFact wraps cython ModelContext
    return modelContext

cdef class ModelDimensionValue(ModelObject): # wrapped by python ModelDimensionValue
    cdef readonly QName dimensionQName, memberQName
    cdef readonly ModelConcept dimension, member
    cdef readonly ModelObject typedMember
    cdef readonly bool isExplicit, isTyped
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.dimensionQName = None
        self.memberQName = None
        self.typedMember = None
        self.isExplicit = self.isTyped = False
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #if traceToStdout: print("mdlRlTy setV ln {} isAttr {} val {}".format(transcode(localName), isAttribute, psviValue))
        if isAttribute:
            if namespace == nElementQName:
                self.isExplicit = pyValue == qnXbrldiExplicitMember
                self.isTyped = not self.isExplicit
            elif namespace[0] == chNull:
                if equals(localName, lnDimension):
                    self.dimensionQName = pyValue
                    return
        else:
            if self.isExplicit:
                self.memberQName = pyValue
                return
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)

    cdef setup(self): # element attributes have been set up
        ModelObject.setup(self)
        cdef ModelXbrl modelXbrl = self.modelXbrl
        cdef ModelObject elt
        self.dimension = modelXbrl.qnameConcepts.get(self.dimensionQName)
        self.member = modelXbrl.qnameConcepts.get(self.memberQName)
        if not self.isExplicit:
            for elt in self.iterchildren():
                self.typedMember = elt
                break

    def iterAttrs(self):
        if self.dimensionQName is not None:
            yield (uDimension, self.dimensionQName)
        ModelObject.iterAttrs()      

    def __hash__(self):
        if self.isExplicit:
            return PyObject_Hash( (self.dimensionQName, self.memberQName) )
        else: # need XPath equal so that QNames aren't lexically compared (for fact and context equality in comparing formula results)
            return PyObject_Hash( (self.dimensionQName, XbrlUtil.equalityHash(self.typedMember, equalMode=XbrlUtil.XPATH_EQ)) )

    @property
    def contextElement(self):
        """(str) -- 'segment' or 'scenario'"""
        return self.getparent().localName
    
        
cdef newModelDimensionValue(ModelDocument modelDocument):
    cdef ModelDimensionValue modelDimensionValue
    modelDimensionValue = ModelInstanceObject.ModelDimensionValue(modelDocument) # python ModelDimensionValue wraps cython ModelDimensionValue
    return modelDimensionValue

def unitMeasureStr(m):
    return m.localName if m.namespaceURI == uNsXbrli or m.namespaceURI == uNsIso4217 else str(m)

cdef class ModelUnit(ModelObject): # wrapped by python ModelFact
    cdef readonly bool isDivide, isSingleMeasure
    cdef readonly tuple measures #([QName],[Qname]) - tuple of multiply measures list and divide members list, in prefixed-name order
    cdef readonly hash_t hash
    
    def __init__(self, ModelDocument modelDocument):
        super().__init__(modelDocument)
        self.isDivide = self.isSingleMeasure = False
        self.measures = None
        self.hash_t = 0
        
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        ModelObject.setValue(self, namespace, localName, pyValue, isAttribute)

    cdef setup(self): # element attributes have been set up
        ModelObject.setup(self)
        cdef ModelXbrl modelXbrl = self.modelDocument.modelXbrl
        cdef ModelObject divElt, unitElt, measElt
        for divElt in self.iterchildren():
            if divElt.qname == qnXbrliDivide:
                self.isDivide = True
                self.measures = (sorted([measElt.xValue
                                         for unitElt in divElt.iterchildren(qnXbrliUnitNumerator)
                                         for measElt in unitElt.iterchildren(qnXbrliMeasure)]),
                                 sorted([measElt.xValue
                                         for unitElt in divElt.iterchildren(qnXbrliUnitDenominator)
                                         for measElt in unitElt.iterchildren(qnXbrliMeasure)]))
            break
        if not self.isDivide:
            self.measures = (sorted([measElt.xValue
                                     for measElt in self.iterchildren(qnXbrliMeasure)]),
                             [])
        self.isSingleMeasure = len(self.measures[0]) == 1
        self.hash = PyObject_Hash( (tuple(self.measures[0]), tuple(self.measures[1])) )
        modelXbrl.units[self.id] = self

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
        cdef list mul, div
        mul, div = self.measures
        return ' '.join([unitMeasureStr(m) for m in mul] + (['/'] + [unitMeasureStr(d) for d in div] if div else []))
    
    @property
    def propertyView(self):
        cdef list mul, div
        mul, div = self.measures
        if div:
            return tuple(('mul',m) for m in mul) + tuple(('div',d) for d in div) 
        else:
            return tuple(('measure',m) for m in mul)
        
cdef newModelUnit(ModelDocument modelDocument):
    cdef ModelUnit modelUnit
    modelUnit = ModelInstanceObject.ModelUnit(modelDocument) # python ModelFact wraps cython ModelUnit
    return modelUnit

