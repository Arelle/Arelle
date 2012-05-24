'''
Created on Mar 7, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import XmlUtil, XbrlConst, XPathParser
from arelle.ModelDtsObject import ModelResource
from arelle.ModelValue import qname
from arelle.ModelFormulaObject import Trace, ModelFormulaResource, ModelConceptName

# Root class for rendering is formula, to allow linked and nested compiled expressions

class ModelTable(ModelFormulaResource):
    def __init__(self, modelDocument):
        super(ModelTable, self).__init__(modelDocument)
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableFilter,)
                
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

# 2010 EU Table linkbase
class ModelAxisCoord(ModelFormulaResource):
    def __init__(self, modelDocument):
        super(ModelAxisCoord, self).__init__(modelDocument)
        
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
class ModelOpenAxis(ModelFormulaResource):
    def __init__(self, modelDocument):
        super(ModelOpenAxis, self).__init__(modelDocument)
                
class ModelPredefinedAxis(ModelOpenAxis):
    def __init__(self, modelDocument):
        super(ModelPredefinedAxis, self).__init__(modelDocument)
        
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
    
class ModelRuleAxis(ModelPredefinedAxis):
    def __init__(self, modelDocument):
        super(ModelRuleAxis, self).__init__(modelDocument)
        
    @property
    def parentChildOrder(self):
        return self.get("parentChildOrder")
    
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
        return {(self.prefixedNameQname(e.get("dimension")),
                 self.prefixedNameQname(XmlUtil.text(qn)))
                for e in XmlUtil.children(self, XbrlConst.formula, "explicitDimension")
                for m in XmlUtil.children(e, XbrlConst.formula, "member")
                for qn in XmlUtil.children(m, XbrlConst.formula, "qname")}
    
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
    def __init__(self, modelDocument):
        super(ModelCompositionAxis, self).__init__(modelDocument)
        
class ModelConceptRelationshipAxis(ModelPredefinedAxis):
    def __init__(self, modelDocument):
        super(ModelConceptRelationshipAxis, self).__init__(modelDocument)
        
class ModelDimensionRelationshipAxis(ModelPredefinedAxis):
    def __init__(self, modelDocument):
        super(ModelDimensionRelationshipAxis, self).__init__(modelDocument)
        
class ModelSelectionAxis(ModelOpenAxis):
    def __init__(self, modelDocument):
        super(ModelSelectionAxis, self).__init__(modelDocument)
        
    def clear(self):
        XPathParser.clearNamedProg(self, "selectProg")
        super(ModelSelectionAxis, self).clear()
    
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
    def __init__(self, modelDocument):
        super(ModelFilterAxis, self).__init__(modelDocument)
        
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
    def __init__(self, modelDocument):
        super(ModelTupleAxis, self).__init__(modelDocument)
        
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableAxisFilter,)
        
from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    (XbrlConst.qnEuTable, ModelTable),
    (XbrlConst.qnTableTable, ModelTable),
    (XbrlConst.qnEuAxisCoord, ModelAxisCoord),
    (XbrlConst.qnTableRuleAxis, ModelRuleAxis),
    (XbrlConst.qnTableCompositionAxis, ModelCompositionAxis),
    (XbrlConst.qnTableConceptRelationshipAxis, ModelConceptRelationshipAxis),
    (XbrlConst.qnTableDimensionRelationshipAxis, ModelDimensionRelationshipAxis),
    (XbrlConst.qnTableSelectionAxis, ModelSelectionAxis),
    (XbrlConst.qnTableFilterAxis, ModelFilterAxis),
    (XbrlConst.qnTableTupleAxis, ModelTupleAxis),
     ))