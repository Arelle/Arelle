
from arelle import XmlUtil
from arelle.ModelValue import QName
from arelle.ModelObject import ModelObject
Aspect = None

class FactPrototype():      # behaves like a fact for dimensional validity testing
    def __init__(self, v, aspectValues=None):
        global Aspect
        if Aspect is None:
            from arelle.ModelFormulaObject import Aspect
        self.modelXbrl = v.modelXbrl
        if aspectValues is None:
            aspectValues = {}
        self.aspectEntryObjectId = aspectValues.get("aspectEntryObjectId", None)
        if Aspect.CONCEPT in aspectValues:
            qname = aspectValues[Aspect.CONCEPT]
            self.qname = qname
            self.concept = v.modelXbrl.qnameConcepts.get(qname)
            self.isItem = self.concept is not None and self.concept.isItem
            self.isTuple = self.concept is not None and self.concept.isTuple
        else:
            self.qname = None # undefined concept
            self.concept = None # undefined concept
            self.isItem = False # don't block aspectMatches
            self.isTuple = False
        if Aspect.LOCATION in aspectValues:
            self.parent = aspectValues[Aspect.LOCATION]
            try:
                self.isTuple = self.parent.isTuple
            except AttributeError:
                self.isTuple = False
        else:
            self.parent = v.modelXbrl.modelDocument.xmlRootElement
        self.isNumeric = self.concept is not None and self.concept.isNumeric
        self.context = ContextPrototype(v, aspectValues)
        if Aspect.UNIT in aspectValues:
            self.unit = UnitPrototype(v, aspectValues)
        else:
            self.unit = None
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
                        for dim,dimVal in sorted(dims.items(), key=lambda i:i[0])
                        if hasattr(dimVal,'propertyView')))
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
        self.entityIdentifierHash = self.entityIdentifier = None
        self.isStartEndPeriod = self.isInstantPeriod = self.isForeverPeriod = False
        
        for aspect, aspectValue in aspectValues.items():
            if aspect == Aspect.PERIOD_TYPE:
                if aspectValue == "forever":
                    self.isForeverPeriod = True
                elif aspectValue == "instant":
                    self.isInstantPeriod = True
                elif aspectValue == "duration":
                    self.isStartEndPeriod = True
            elif aspect == Aspect.START:
                self.isStartEndPeriod = True
                self.startDatetime = aspectValue
            elif aspect == Aspect.END:
                self.isStartEndPeriod = True
                self.endDatetime = aspectValue
            elif aspect == Aspect.INSTANT:
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
            elif isinstance(aspectValue, ModelObject):
                # these do not expect a string aspectValue, but the object model aspect value
                if aspect == Aspect.PERIOD: # period xml object
                    context = aspectValue.getparent()
                    for contextPeriodAttribute in ("isForeverPeriod", "isStartEndPeriod", "isInstantPeriod",
                                                   "startDatetime", "endDatetime", "instantDatetime",
                                                   "periodHash"):
                        setattr(self, contextPeriodAttribute, getattr(context, contextPeriodAttribute, None))
                elif aspect == Aspect.ENTITY_IDENTIFIER: # entitytIdentifier xml object
                    context = aspectValue.getparent().getparent()
                    for entityIdentAttribute in ("entityIdentifier", "entityIdentifierHash"):
                        setattr(self, entityIdentAttribute, getattr(context, entityIdentAttribute, None))

    def clear(self):
        try:
            for dim in self.qnameDims.values():
                # only clear if its a prototype, but not a 'reused' model object from other instance
                if isinstance(dim, DimValuePrototype):
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

    def isEntityIdentifierEqualTo(self, cntx2):
        return self.entityIdentifierHash is None or self.entityIdentifierHash == cntx2.entityIdentifierHash
    
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
    
class DimValuePrototype():
    def __init__(self, v, dimConcept, dimQname, mem, contextElement):
        from arelle.ModelValue import QName
        if dimConcept is None: # note no concepts if modelXbrl.skipDTS:
            dimConcept = v.modelXbrl.qnameConcepts.get(dimQname)
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
                    if isinstance(self.typedMember, ModelObject) else "None" )

class UnitPrototype():  # behaves like a context
    def __init__(self, v, aspectValues):
        self.modelXbrl = v.modelXbrl
        self.hash = self.measures = self.isSingleMeasure = None
        for aspect, aspectValue in aspectValues.items():
            if aspect == Aspect.UNIT: # entitytIdentifier xml object
                for unitAttribute in ("measures", "hash", "isSingleMeasure", "isDivide"):
                    setattr(self, unitAttribute, getattr(aspectValue, unitAttribute, None))

    def clear(self):
        self.__dict__.clear()  # delete local attributes

    def isEqualTo(self, unit2):
        if unit2 is None or unit2.hash != self.hash: 
            return False
        return unit2 is self or self.measures == unit2.measures

    @property
    def propertyView(self):
        measures = self.measures
        if measures[1]:
            return tuple(('mul',m) for m in measures[0]) + \
                   tuple(('div',d) for d in measures[1]) 
        else:
            return tuple(('measure',m) for m in measures[0])

class XbrlPrototype(): # behaves like ModelXbrl
    def __init__(self, modelManager, uri, *arg, **kwarg):
        self.modelManager = modelManager
        self.errors = []
        self.skipDTS = False
        from arelle.PrototypeDtsObject import DocumentPrototype
        self.modelDocument = DocumentPrototype(self, uri)

    def close(self):
        self.modelDocument.clear()
        self.__dict__.clear()  # delete local attributes
        