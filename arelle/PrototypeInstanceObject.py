
from arelle import XmlUtil
from arelle.ModelValue import QName
Aspect = None

class FactPrototype():      # behaves like a fact for dimensional validity testing
    def __init__(self, v, aspectValues):
        global Aspect
        if Aspect is None:
            from arelle.ModelFormulaObject import Aspect
        self.modelXbrl = v.modelXbrl
        if Aspect.CONCEPT in aspectValues:
            qname = aspectValues[Aspect.CONCEPT]
            self.qname = qname
            self.concept = v.modelXbrl.qnameConcepts.get(qname)
            self.isItem = self.concept is not None and self.concept.isItem
            self.isTuple = self.concept is not None and self.concept.isTuple
        else:
            self.qname = None # undefined concept
            self.concept = None # undefined concept
            self.isTuple = False # don't block aspectMatches
        if Aspect.LOCATION in aspectValues:
            self.parent = aspectValues[Aspect.LOCATION]
            try:
                self.isTuple = self.parent.isTuple
            except AttributeError:
                self.isTuple = False
        else:
            self.parent = v.modelXbrl.modelDocument.xmlRootElement
        self.context = ContextPrototype(v, aspectValues)
        self.factObjectId = None

    def clear(self):
        if self.context is not None:
            self.context.clear()
        self.__dict__.clear()  # delete local attributes
        
    def objectId(self):
        return "_factPrototype_" + str(self.qname)
    
    def getparent(self):
        return self.parent
    
    @property
    def propertyView(self):
        dims = self.context.qnameDims
        return (("concept", str(self.qname) if self.concept is not None else "not specified"),
                ("dimensions", "({0})".format(len(dims)),
                  tuple(dimVal.propertyView if dimVal is not None else (str(dim.qname),"None")
                        for dim,dimVal in sorted(dims.items(), key=lambda i:i[0])))
                  if dims else (),
                )

    @property
    def viewConcept(self):
        return self

class ContextPrototype():  # behaves like a context
    def __init__(self, v, aspectValues):
        self.modelXbrl = v.modelXbrl
        self.segDimVals = {}
        self.scenDimVals = {}
        self.qnameDims = {}
        for aspect, aspectValue in aspectValues.items():
            if aspect == Aspect.PERIOD_TYPE:
                if aspectValue == "forever":
                    self.isStartEndPeriod = self.isInstantPeriod = False
                    self._isForeverPeriod = True
                elif aspectValue == "instant":
                    self.isStartEndPeriod = self.isForeverPeriod = False
                    self.isInstantPeriod = True
                elif aspectValue == "duration":
                    self.isStartEndPeriod = self.isInstantPeriod = False
                    self.isStartEndPeriod = True
            elif aspect == Aspect.START:
                self.isStartEndPeriod = self.isInstantPeriod = False
                self.isStartEndPeriod = True
                self.startDatetime = aspectValue
            elif aspect == Aspect.END:
                self.isStartEndPeriod = self.isInstantPeriod = False
                self.isStartEndPeriod = True
                self.endDatetime = aspectValue
            elif aspect == Aspect.INSTANT:
                self.isStartEndPeriod = self.isForeverPeriod = False
                self.isInstantPeriod = True
                self.endDatetime = self.instantDatetime = aspectValue
            elif isinstance(aspect, QName):
                try: # if a DimVal, then it has a suggested context element
                    contextElement = aspectValue.contextElement
                    aspectValue = (aspectValue.memberQname or aspectValue.typedMember)
                except AttributeError: # probably is a QName, not a dim value or dim prototype
                    contextElement = v.modelXbrl.qnameDimensionContextElement.get(aspect)
                if v.modelXbrl.qnameDimensionDefaults.get(aspect) != aspectValue: # not a default
                    try:
                        dimConcept = v.modelXbrl.qnameConcepts[aspect]
                        dimValPrototype = DimValuePrototype(v, dimConcept, aspect, aspectValue, contextElement)
                        self.qnameDims[aspect] = dimValPrototype
                        if contextElement != "scenario": # could be segment, ambiguous, or no information
                            self.segDimVals[dimConcept] = dimValPrototype
                        else:
                            self.scenDimVals[dimConcept] = dimValPrototype
                    except KeyError:
                        pass

    def clear(self):
        try:
            for dim in self.qnameDims.values():
                dim.clear()
        except AttributeError:
            pass
        self.__dict__.clear()  # delete local attributes
        
    def dimValue(self, dimQname):
        """(ModelDimension or QName) -- ModelDimension object if dimension is reported (in either context element), or QName of dimension default if there is a default, otherwise None"""
        try:
            return self.qnameDims[dimQname]
        except KeyError:
            try:
                return self.modelXbrl.qnameDimensionDefaults[dimQname]
            except KeyError:
                return None

    def dimValues(self, contextElement, oppositeContextElement=False):
        if not oppositeContextElement:
            return self.segDimVals if contextElement == "segment" else self.scenDimVals
        else:
            return self.scenDimVals if contextElement == "segment" else self.segDimVals
    
    def nonDimValues(self, contextElement):
        return []
    
class DimValuePrototype():
    def __init__(self, v, dimConcept, dimQname, mem, contextElement):
        from arelle.ModelValue import QName
        self.dimension = dimConcept
        self.dimensionQname = dimQname
        self.contextElement = contextElement
        if isinstance(mem,QName):
            self.isExplicit = True
            self.isTyped = False
            self.memberQname = mem
            self.member = v.modelXbrl.qnameConcepts.get(mem)
            self.typedMember = None
        else:
            self.isExplicit = False
            self.isTyped = True
            self.typedMember = mem
            self.memberQname = None
            self.member = None

    def clear(self):
        self.__dict__.clear()  # delete local attributes

    @property
    def propertyView(self):
        if self.isExplicit:
            return (str(self.dimensionQname),str(self.memberQname))
        else:
            return (str(self.dimensionQname), 
                    XmlUtil.xmlstring( self.typedMember, stripXmlns=True, prettyPrint=True )
                    if self.typedMember is not None else "None" )
