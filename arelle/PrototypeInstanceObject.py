
'''
def dimContextElement(view, dimConcept):
    # should replace this with modelXbrl.qnameDimensionContextElement if not ambiguous, else same logic as create context
    contextElement = view.modelXbrl.qnameDimensionContextElement.get(dimConcept.qname)
    try:
        return view.dimsContextElement[dimConcept]
    except KeyError:
        if contextElement and contextElement != "ambiguous":
            return contextElement
        if view.hcDimRelSet:
            for dimHcRel in view.hcDimRelSet.toModelObject(dimConcept):
                if dimHcRel.fromModelObject is not None:
                    for hcRel in view.hcDimRelSet.toModelObject(dimHcRel.fromModelObject):
                        contextElement = hcRel.contextElement
                        view.dimsContextElement[dimConcept] = contextElement
                        return contextElement
        return None
'''
        
class FactPrototype():      # behaves like a fact for dimensional validity testing
    def __init__(self, v, qname, dims):
        self.qname = qname
        self.concept = v.modelXbrl.qnameConcepts.get(qname)
        self.context = ContextPrototype(v, dims)
        self.dims = dims # dim items
        self.dimKeys = set(dim for dim,mem in dims)
        self.factObjectId = None
        
    def objectId(self):
        return "_factPrototype_" + str(self.qname)

    @property
    def propertyView(self):
        return (("concept", str(self.qname)),
                ("dimensions", "({0})".format(len(self.dims)),
                  tuple((str(dim),str(mem)) for dim,mem in sorted(self.dims)))
                  if self.dims else (),
                )

    @property
    def viewConcept(self):
        return self

class ContextPrototype():  # behaves like a context
    def __init__(self, v, dims):
        self.segDimVals = {}
        self.scenDimVals = {}
        self.qnameDims = {}
        for dimQname,mem in dims:
            try: # if a DimVal, then it has a suggested context element
                contextElement = mem.contextElement
                mem = (mem.memberQname or mem.typedMember)
            except AttributeError: # probably is a QName, not a dim value or dim prototype
                contextElement = v.modelXbrl.qnameDimensionContextElement.get(dimQname)
            if v.modelXbrl.qnameDimensionDefaults.get(dimQname) != mem: # not a default
                try:
                    dimConcept = v.modelXbrl.qnameConcepts[dimQname]
                    #if contextElement is None:
                    #    contextElement = dimContextElement(v, dimConcept)
                    dimValPrototype = DimValuePrototype(v, dimConcept, dimQname, mem, contextElement)
                    self.qnameDims[dimQname] = dimValPrototype
                    if contextElement != "scenario": # could be segment, ambiguous, or no information
                        self.segDimVals[dimConcept] = dimValPrototype
                    else:
                        self.scenDimVals[dimConcept] = dimValPrototype
                except KeyError:
                    pass
        
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
