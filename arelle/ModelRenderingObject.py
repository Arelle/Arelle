'''
Created on Mar 7, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import XmlUtil, XbrlConst, XPathParser
from arelle.ModelDtsObject import ModelResource
from arelle.ModelValue import qname, QName
from arelle.ModelFormulaObject import (Trace, ModelFormulaResource, ModelFormulaRules, ModelConceptName,
                                       Aspect)

# Root class for rendering is formula, to allow linked and nested compiled expressions

# 2010 EU Table linkbase
class ModelEuTable(ModelResource):
    def init(self, modelDocument):
        super(ModelEuTable, self).init(modelDocument)
        
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel))
        
    def __repr__(self):
        return ("table[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelEuAxisCoord(ModelResource):
    def init(self, modelDocument):
        super(ModelEuAxisCoord, self).init(modelDocument)
        
    @property
    def abstract(self):
        return self.get("abstract") if self.get("abstract") else 'false'
    
    @property
    def parentChildOrder(self):
        return self.get("parentChildOrder")

    @property
    def primaryItemQname(self):
        priItem = XmlUtil.childAttr(self, XbrlConst.euRend, "primaryItem", "name")
        if priItem is not None:
            return self.prefixedNameQname(priItem)
        return None
    
    @property
    def explicitDims(self):
        return {(self.prefixedNameQname(e.get("dimension")),
                 self.prefixedNameQname(e.get("value")))
                for e in XmlUtil.children(self, XbrlConst.euRend, "explicitDimCoord")}
    
    @property
    def instant(self):
        return XmlUtil.childAttr(self, XbrlConst.euRend, "timeReference","instant")
    
    @property
    def propertyView(self):
        explicitDims = self.explicitDims
        return (("id", self.id),
                ("xlink:label", self.xlinkLabel),
                ("header label", self.genLabel()),
                ("header doc", self.genLabel(role="http://www.xbrl.org/2008/role/documentation")),
                ("header code", self.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code")),
                ("primary item", self.primaryItemQname),
                ("dimensions", "({0})".format(len(explicitDims)),
                  tuple((str(dim),str(mem)) for dim,mem in sorted(explicitDims)))
                  if explicitDims else (),
                ("abstract", self.abstract),
                ("instant", self.instant))
        
    def __repr__(self):
        return ("axisCoord[{0}]{1})".format(self.objectId(),self.propertyView))

# 2011 Table linkbase
class ModelTable(ModelFormulaResource):
    def init(self, modelDocument):
        super(ModelTable, self).init(modelDocument)
        self.modelXbrl.modelRenderingTables.add(self)
        self.modelXbrl.hasRenderingTables = True
        
    @property
    def aspectModel(self):
        return self.get("aspectModel")

    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableFilter, XbrlConst.tableAxis)
                
    @property
    def filterRelationships(self):
        try:
            return self._filterRelationships
        except AttributeError:
            rels = [] # order so conceptName filter is first (if any) (may want more sorting in future)
            for rel in self.modelXbrl.relationshipSet(XbrlConst.tableFilter).fromModelObject(self):
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            self._filterRelationships = rels
            return rels
    
    @property
    def propertyView(self):
        return (("id", self.id),
                ("label", self.xlinkLabel))
        
    def __repr__(self):
        return ("table[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelOpenAxis(ModelFormulaResource):
    def init(self, modelDocument):
        super(ModelOpenAxis, self).init(modelDocument)
                
    @property
    def variablename(self):
        """(str) -- name attribute"""
        return self.getStripped("name")

    @property
    def variableQname(self):
        """(QName) -- resolved name for an XPath bound result having a QName name attribute"""
        varName = self.variablename
        return qname(self, varName, noPrefixIsNoNamespace=True) if varName else None

    @property   
    def primaryItemQname(self):  # for compatibility with viewRelationsihps
        return None
        
    @property
    def explicitDims(self):
        return set()
    
class ModelPredefinedAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelPredefinedAxis, self).init(modelDocument)
        
    @property
    def abstract(self):
        if self.get("abstract") == 'true':
            return 'true'
        return 'false'
        
    @property
    def parentChildOrder(self):
        return self.get("parentChildOrder")

    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableAxisSubtree,)
    
class ModelRuleAxis(ModelFormulaRules, ModelPredefinedAxis):
    def init(self, modelDocument):
        super(ModelRuleAxis, self).init(modelDocument)
        
    @property   
    def primaryItemQname(self):
        conceptRule = XmlUtil.child(self, XbrlConst.formula, "concept")
        if conceptRule is not None:
            qnameElt = XmlUtil.child(conceptRule, XbrlConst.formula, "qname")
            if qnameElt is not None:
                return qname(qnameElt, qnameElt.text)
        return None
    
    @property
    def explicitDims(self):
        dims = set()
        for e in XmlUtil.children(self, XbrlConst.formula, "explicitDimension"):
            d = self.prefixedNameQname(e.get("dimension"))
            if XmlUtil.children(e, XbrlConst.formula, "omit"):
                dims.add( (d, "omit") )
            else:
                for m in XmlUtil.children(e, XbrlConst.formula, "member"):
                    for qn in XmlUtil.children(m, XbrlConst.formula, "qname"):
                        dims.add( (d, self.prefixedNameQname(XmlUtil.text(qn))) )
        return dims
    
    @property
    def instant(self):
        return XmlUtil.childAttr(self, XbrlConst.euRend, "timeReference","instant")
    
    @property
    def propertyView(self):
        explicitDims = self.explicitDims
        return (("id", self.id),
                ("xlink:label", self.xlinkLabel),
                ("header label", self.genLabel()),
                ("header doc", self.genLabel(role="http://www.xbrl.org/2008/role/documentation")),
                ("header code", self.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code")),
                ("primary item", self.primaryItemQname),
                ("dimensions", "({0})".format(len(explicitDims)),
                  tuple((str(dim),str(mem)) for dim,mem in sorted(explicitDims)))
                  if explicitDims else (),
                ("abstract", self.abstract),
                ("instant", self.instant))
        
    def __repr__(self):
        return ("explicitAxisMember[{0}]{1})".format(self.objectId(),self.propertyView))

class ModelCompositionAxis(ModelPredefinedAxis):
    def init(self, modelDocument):
        super(ModelCompositionAxis, self).init(modelDocument)
        
class ModelConceptRelationshipAxis(ModelPredefinedAxis):
    def init(self, modelDocument):
        super(ModelConceptRelationshipAxis, self).init(modelDocument)
        
class ModelDimensionRelationshipAxis(ModelPredefinedAxis):
    def init(self, modelDocument):
        super(ModelDimensionRelationshipAxis, self).init(modelDocument)
        
        
coveredAspectToken = {"concept": Aspect.CONCEPT, 
                      "entity-identifier": Aspect.VALUE, 
                      "period-start": Aspect.START, "period-end": Aspect.END, 
                      "period-instant": Aspect.INSTANT, "period-instant-end": Aspect.INSTANT_END, 
                      "unit": Aspect.UNIT}

class ModelSelectionAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelSelectionAxis, self).init(modelDocument)
        
    def clear(self):
        XPathParser.clearNamedProg(self, "selectProg")
        super(ModelSelectionAxis, self).clear()
    
    def coveredAspect(self, varBinding, xpCtx=None):
        try:
            return self._coveredAspect
        except AttributeError:
            coveredAspect = self.get("coveredAspect")
            if coveredAspect in coveredAspectToken:
                self._coveredAspect = coveredAspectToken[coveredAspect]
            else:  # must be a qname
                self._coveredAspect = qname(self, coveredAspect)
            return self._coveredAspect

    @property
    def select(self):
        return self.get("select")
    
    def compile(self):
        if not hasattr(self, "selectProg"):
            self.selectProg = XPathParser.parse(self, self.select, self, "select", Trace.PARAMETER)
            super(ModelSelectionAxis, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super(ModelSelectionAxis, self).variableRefs(self.selectProg, varRefSet)
        
    def evaluate(self, xpCtx, typeQname):
        try:
            return xpCtx.evaluateAtomicValue(self.selectProg, typeQname)
        except AttributeError:
            return None
            
class ModelFilterAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelFilterAxis, self).init(modelDocument)
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableAxisFilter,)
        
    @property
    def filterRelationships(self):
        try:
            return self._filterRelationships
        except AttributeError:
            rels = [] # order so conceptName filter is first (if any) (may want more sorting in future)
            for rel in self.modelXbrl.relationshipSet(XbrlConst.tableAxisFilter).fromModelObject(self):
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            self._filterRelationships = rels
            return rels
    
class ModelTupleAxis(ModelOpenAxis):
    def init(self, modelDocument):
        super(ModelTupleAxis, self).init(modelDocument)
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableTupleContent,)
        
    @property
    def contentRelationships(self):
        return self.modelXbrl.relationshipSet(XbrlConst.tableTupleContent).fromModelObject(self)
        
from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    (XbrlConst.qnEuTable, ModelEuTable),
    (XbrlConst.qnEuAxisCoord, ModelEuAxisCoord),
    (XbrlConst.qnTableTable, ModelTable),
    (XbrlConst.qnTableRuleAxis, ModelRuleAxis),
    (XbrlConst.qnTableCompositionAxis, ModelCompositionAxis),
    (XbrlConst.qnTableConceptRelationshipAxis, ModelConceptRelationshipAxis),
    (XbrlConst.qnTableDimensionRelationshipAxis, ModelDimensionRelationshipAxis),
    (XbrlConst.qnTableSelectionAxis, ModelSelectionAxis),
    (XbrlConst.qnTableFilterAxis, ModelFilterAxis),
    (XbrlConst.qnTableTupleAxis, ModelTupleAxis),
     ))