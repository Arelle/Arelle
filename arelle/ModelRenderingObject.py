'''
Created on Mar 7, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import inspect, os
from arelle import XmlUtil, XbrlConst, XPathParser, Locale, XPathContext
from collections import defaultdict
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelValue import qname, QName
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import (Trace, ModelFormulaResource, ModelFormulaRules, ModelConceptName,
                                       ModelParameter, Aspect, aspectStr, aspectRuleAspects)
from arelle.ModelInstanceObject import ModelFact
from arelle.FormulaEvaluator import (filterFacts as formulaEvaluatorFilterFacts, 
                                     aspectsMatch, factsPartitions, VariableBinding)
from arelle.PrototypeInstanceObject import FactPrototype

OPEN_ASPECT_ENTRY_SURROGATE = '\uDBFF'

EMPTY_SET = set()

class LayoutMdlHdrCells:
    def __init__(self, strctMdlNode):
        self.strctMdlNode = strctMdlNode
        self.layoutMdlCells = [] # contains LayoutMdlCell objects
        
class LayoutMdlHdrCell:
    def __init__(self, strctMdlNode):
        self.strctMdlNode = strctMdlNode
        self.parentLayoutMdlHdrCell = None

class LayoutMdlBodyCells:
    def __init__(self, strctMdlNode):
        self.strctMdlNode = strctMdlNode
        self.layoutMdlCells = [] # z body cells contain y's body cells; y body cells contain x's body cells; x's body cells contain individual cells
        
class LayoutMdlBodyCell:
    def __init__(self, strctMdlNode):
        self.strctMdlNode = strctMdlNode
        self.layoutMdlHdrCell = None # leaf header cell
        self.facts = [] # bound facts
        
def definitionNodes(nodes):
    return [(ord.definitionNodeObject if isinstance(node, StrctMdlStructuralNode) else node) for node in nodes]

def parentChildOrder(node):
    _parentChildOrder = node.get("parentChildOrder")
    if _parentChildOrder:
        return _parentChildOrder
    # look for inherited parentChildOrder
    for rel in node.modelXbrl.relationshipSet(node.ancestorArcroles).toModelObject(node):
        if rel.fromModelObject is not None:
            _parentChildOrder = parentChildOrder(rel.fromModelObject)
            if _parentChildOrder:
                return _parentChildOrder        
    return None

# Structural model
class StrctMdlNode:
    def __init__(self, strctMdlParentNode, defnMdlNode=None):
        self.defnMdlNode = defnMdlNode
        self.strctMdlParentNode = strctMdlParentNode
        self.strctMdlChildNodes = []
        if strctMdlParentNode:
            strctMdlParentNode.strctMdlChildNodes.append(self)
        self.aspects = {}
        self.hasChildRollup = False
        self.contextItemBinding = None
        self.variables = {}
        self.zInheritance = None
        self.rollup = False # true when this is the rollup node among its siblings
        
    @property
    def axis(self):
        return getattr(self, "_axis", self.strctMdlParentNode.axis if self.strctMdlParentNode else "")
 
    @property
    def depth(self):
        return self.strctMdlParentNode.depth + 1 if self.strctMdlParentNode else 0

    def aspectsCovered(self, inherit=False):
        return ()
    
    def hasAspect(self, aspect, inherit=True):
        return False
        
    @property
    def hasRollUpChild(self):
        return any(c.hasChildRollup for c in self.strctMdlChildNodes)
     
    @property
    def leafNodeCount(self):
        childLeafCount = 0
        if self.strctMdlChildNodes:
            for strctMdlChildNode in self.strctMdlChildNodes:
                childLeafCount += strctMdlChildNode.leafNodeCount
        if childLeafCount == 0:
            return 1
        if not self.isAbstract and isinstance(self.defnMdlNode, DefnMdlClosedDefinitionNode):
            childLeafCount += 1 # has a roll up
        return childLeafCount

    @property
    def cardinalityAndDepth(self):
        if self.defnMdlNode is not None:
            return self.defnMdlNode.cardinalityAndDepth(self)
        return (1, 0) # no breakdown
        
    def objectId(self, refId=""):
        if self.defnMdlNode is not None:
            return self.defnMdlNode.objectId(refId)
        return None
        
    @property
    def structuralDepth(self):
        return 0
    
    @property
    def childRollupStrctNode(self):
        for childStrctNode in self.strctMdlChildNodes:
            if childStrctNode.rollup:
                return childStrctNode
            grandchildStrctRollup = childStrctNode.childRollupStrctNode
            if grandchildStrctRollup:
                return grandchildStrctRollup
        return None
        
    def headerAndSource(self, role=None, lang=None, evaluate=True, returnGenLabel=True, returnMsgFormatString=False, recurseParent=True, returnStdLabel=True):
        if self.defnMdlNode is None: # root
            return None, None
        if returnGenLabel:
            label = self.defnMdlNode.genLabel(role=role, lang=lang)
            if label:
                return label, None # explicit is default source
        if self.isEntryAspect and role is None:
            # True if open node bound to a prototype, false if boudn to a real fact
            return OPEN_ASPECT_ENTRY_SURROGATE, None # sort pretty high, work ok for python 2.7/3.2 as well as 3.3
        # if there's a child roll up, check for it
        if self.childRollupStrctNode is not None:  # check the rolling-up child too
            return self.childRollupStrctNode.headerAndSource(role, lang, evaluate, returnGenLabel, returnMsgFormatString, recurseParent)
        # if aspect is a concept of dimension, return its standard label
        concept = None
        if role is None and returnStdLabel:
            for aspect in self.aspectsCovered():
                aspectValue = self.aspectValue(aspect, inherit=recurseParent)
                if isinstance(aspect, QName) or aspect == Aspect.CONCEPT: # dimension or concept
                    if isinstance(aspectValue, QName):
                        concept = self.modelXbrl.qnameConcepts[aspectValue]
                        break
                    elif isinstance(aspectValue, ModelDimensionValue):
                        if aspectValue.isExplicit:
                            concept = aspectValue.member
                        elif aspectValue.isTyped:
                            return XmlUtil.innerTextList(aspectValue.typedMember), "processor"
                elif isinstance(aspectValue, ModelObject):
                    text = XmlUtil.innerTextList(aspectValue)
                    if not text and XmlUtil.hasChild(aspectValue, aspectValue.namespaceURI, "forever"):
                        text = "forever" 
                    return text, "processor"
        if concept is not None:
            label = concept.label(lang=lang)
            if label:
                return label, "processor"
        # if there is a role, check if it's available on a parent node
        if role and recurseParent and self.strctMdlParentNode is not None:
            return self.strctMdlParentNode.headerAndSource(role, lang, evaluate, returnGenLabel, returnMsgFormatString, recurseParent)
        return None, None
    
    def header(self, role=None, lang=None, evaluate=True, returnGenLabel=True, returnMsgFormatString=False, recurseParent=True, returnStdLabel=True):
        return self.headerAndSource(role, lang, evaluate, returnGenLabel, returnMsgFormatString, recurseParent, returnStdLabel)[0]
    
    @property
    def isAbstract(self):
        try:
            try:
                return self.abstract # ordinate may have an abstract attribute
            except AttributeError: # if none use axis object
                return self.defnMdlNode.isAbstract
        except AttributeError: # axis may never be abstract
            return False
    
    @property
    def isEntryAspect(self):
        # true if open node and bound to a fact prototype
        return self.contextItemBinding is not None and isinstance(self.contextItemBinding.yieldedFact, FactPrototype)
    
    def isEntryPrototype(self, default=False):
        # true if all axis open nodes before this one are entry prototypes (or not open axes)
        if self.contextItemBinding is not None:
            # True if open node bound to a prototype, false if bound to a real fact
            return isinstance(self.contextItemBinding.yieldedFact, FactPrototype)
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.isEntryPrototype(default)
        return default # nothing open to be bound to a fact
    
    def evaluate(self, evalObject, evalMethod, otherAxisStructuralNode=None, evalArgs=(), handleXPathException=True, **kwargs):
        xc = self._rendrCntx
        if self.contextItemBinding and not isinstance(xc.contextItem, ModelFact):
            previousContextItem = xc.contextItem # xbrli.xbrl
            xc.contextItem = self.contextItemBinding.yieldedFact
        else:
            previousContextItem = None
        variables = self.variables
        removeVarQnames = []
        for variablesItems in variables.items():
            for qn, value in variablesItems:
                if qn not in xc.inScopeVars:
                    removeVarQnames.append(qn)
                    xc.inScopeVars[qn] = value
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            result = self.strctMdlParentNode.evaluate(evalObject, evalMethod, otherAxisStructuralNode, evalArgs)
        elif otherAxisStructuralNode is not None:
            # recurse to other ordinate (which will recurse to z axis)
            result = otherAxisStructuralNode.evaluate(evalObject, evalMethod, None, evalArgs)
        elif self.zInheritance is not None:
            result = self.zInheritance.evaluate(evalObject, evalMethod, None, evalArgs)
        else:
            try:
                result = evalMethod(xc, *evalArgs)
            except XPathContext.XPathException as err:
                if not handleXPathException:
                    raise
                xc.modelXbrl.error(err.code,
                         _("%(element)s set %(xlinkLabel)s \nException: %(error)s"), 
                         modelObject=evalObject, element=evalObject.localName, 
                         xlinkLabel=evalObject.xlinkLabel, error=err.message)
                result = ''
        for qn in removeVarQnames:
            xc.inScopeVars.pop(qn)
        if previousContextItem is not None:
            xc.contextItem = previousContextItem # xbrli.xbrl
        return result
    
    def hasValueExpression(self, otherAxisStructuralNode=None):
        return (self.defnMdlNode.hasValueExpression or 
                (otherAxisStructuralNode is not None and 
                 otherAxisStructuralNode.defnMdlNode is not None and
                 otherAxisStructuralNode.defnMdlNode.hasValueExpression))
    
    def evalValueExpression(self, fact, otherAxisStructuralNode=None):
        for structuralNode in (self, otherAxisStructuralNode):
            if (structuralNode is not None and 
                structuralNode.defnMdlNode is not None and 
                structuralNode.defnMdlNode.hasValueExpression):
                return self.evaluate(self.defnMdlNode, structuralNode.defnMdlNode.evalValueExpression, otherAxisStructuralNode=otherAxisStructuralNode, evalArgs=(fact,))
        return None
    
        
class StrctMdlTableSet(StrctMdlNode):
    def __init__(self, defnMdlTable):
        super(StrctMdlTableSet, self).__init__(None, defnMdlTable)

class StrctMdlTable(StrctMdlNode):
    def __init__(self, defnMdlTable):
        super(StrctMdlTable, self).__init__(None, defnMdlTable)
        self._rendrCntx = defnMdlTable.renderingXPathContext
        # childStrctMdlNodes are StrctMdlBreakdowns
        self.defnMdlBreakdowns = defaultdict(list)
        self.axisDepth = {"x": 0, "y":0, "z":0}
        self.layoutMdlCells = [] # z body cells
        
    def strctMdlFirstAxisBreakdown(self, axis):
        for c in self.strctMdlChildNodes:
            if c._axis == axis:
                return c
        return None
    
class StrctMdlBreakdown(StrctMdlNode):
    # breakdown also acts as the layout model group containing headers of cells
    def __init__(self, strctMdlParentNode, defnMdlBreakdown, axis):
        super(StrctMdlBreakdown, self).__init__(strctMdlParentNode, defnMdlBreakdown)
        self._rendrCntx = strctMdlParentNode._rendrCntx # copy from parent except at root
        self._axis = axis
        self.rendrCntx = strctMdlParentNode._rendrCntx
        self.hasOpenNode = False
        self.isLabeled = False
        self.layoutMdlHdrCells = [] # layoutMdlHeaderCells objects

    def siblingBreakdownNode(self):
        if self.strctMdlParentNode is not None:
            for sibling in self.strctMdlParentNode.strctMdlChildNodes[
                                    self.strctMdlParentNode.strctMdlChildNodes.index(self)+1:]:
                if sibling._axis == self._axis:
                    return (sibling,)
        return ()

    @property     
    def strctMdlEffectiveChildNodes(self):
        if self.strctMdlChildNodes: # not leaf
            return self.strctMdlChildNodes
        # effective child nodes at a leaf node is sibling beakdown node subtee
        return self.siblingBreakdownNode()

    def setHasOpenNode(self):
        self.hasOpenNode = True
        
    @property
    def tagSelectors(self):
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.tagSelectors
        else:
            return set()
    def inheritedAspectValue(self, *args):
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.inheritedAspectValue(*args)
        else:
            return None
             
class StrctMdlStructuralNode(StrctMdlNode):
    def __init__(self, strctMdlParentNode, defnMdlNode, zInheritance=None, contextItemFact=None, tableNode=None, rendrCntx=None):
        super(StrctMdlStructuralNode, self).__init__(strctMdlParentNode, defnMdlNode)
        self._rendrCntx = rendrCntx or strctMdlParentNode._rendrCntx # copy from parent except at root
        self.zInheritance = zInheritance
        if contextItemFact is not None:
            self.contextItemBinding = VariableBinding(self._rendrCntx,
                                                      boundFact=contextItemFact)
            if isinstance(self.contextItemBinding.yieldedFact, FactPrototype):
                for aspect in defnMdlNode.aspectsCovered():
                    if aspect != Aspect.DIMENSIONS:
                        self.aspectEntryObjectId = self.aspects[aspect] = contextItemFact.aspectEntryObjectId
                        break
        else:
            self.contextItemBinding = None
        if tableNode is not None:
            self.tableNode = tableNode
        self.tagSelector = getattr(defnMdlNode, "tagSelector", None)
        self.isLabeled = True
        
    @property
    def modelXbrl(self):
        return self.defnMdlNode.modelXbrl
        
    @property
    def structuralDepth(self):
        if self.strctMdlParentNode is not None:
            return self.strctMdlParentNode.structuralDepth + 1
        return 0
    
    def siblingBreakdownNode(self):
        if self.strctMdlParentNode is not None:
            return self.strctMdlParentNode.siblingBreakdownNode()
        return ()
    
    @property     
    def strctMdlEffectiveChildNodes(self):
        if self.strctMdlChildNodes: # not leaf
            # if nested breakdown which is unlabeled return children of breakdown
            if len(self.strctMdlChildNodes) == 1 and isinstance(self.strctMdlChildNodes[0], StrctMdlBreakdown): # nested layout node
                if True: # TBD determine if labeled: not self.strctMdlChildNodes[0].isLabeled:
                    return self.strctMdlChildNodes[0].strctMdlChildNodes
            return self.strctMdlChildNodes
        # effective child nodes at a leaf node is sibling beakdown node subtee
        return self.siblingBreakdownNode()

    @property     
    def strctMdlAncestorBreakdownNode(self):
        if isinstance(self.strctMdlParentNode, StrctMdlBreakdown):
            return self.strctMdlParentNode
        return self.strctMdlParentNode.strctMdlAncestorBreakdownNode
   
    def constraintSet(self, tagSelectors=None):
        defnMdlNode = self.defnMdlNode
        if defnMdlNode is None:
            return None # root node
        if tagSelectors:
            for tag in tagSelectors:
                if tag in defnMdlNode.constraintSets:
                    return defnMdlNode.constraintSets[tag]
        return defnMdlNode.constraintSets.get(None) # returns None if no default constraint set
    
    def aspectsCovered(self, inherit=False):
        if self.aspects is None:
            return ()
        aspectsCovered = _DICT_SET(self.aspects.keys())
        if self.defnMdlNode is not None and hasattr(self.defnMdlNode, "aspectsCovered"):
            aspectsCovered |= self.defnMdlNode.aspectsCovered()
        if inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            aspectsCovered.update(self.strctMdlParentNode.aspectsCovered(inherit=inherit))
        elif (inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode)):
            aspectsCovered.update(self.strctMdlParentNode.strctMdlParentNode.aspectsCovered(inherit=inherit))
        return aspectsCovered
      
    def hasAspect(self, aspect, inherit=True):
        return (aspect in self.aspects or 
                (self.defnMdlNode is not None and 
                 self.defnMdlNode.hasAspect(self, aspect)) or
                (inherit and
                 isinstance(self.strctMdlParentNode, StrctMdlStructuralNode) and 
                 self.strctMdlParentNode.hasAspect(aspect, inherit)) or 
                (inherit and
                 isinstance(self.strctMdlParentNode, StrctMdlBreakdown) and 
                 self.strctMdlParentNode.strctMdlParentNode.hasAspect(aspect, inherit))
                )
    
    def aspectValue(self, aspect, inherit=True, dims=None, depth=0, tagSelectors=None):
        xc = self._rendrCntx
        aspects = self.aspects
        defnMdlNode = self.defnMdlNode
        contextItemBinding = self.contextItemBinding
        constraintSet = self.constraintSet(tagSelectors)
        if aspect == Aspect.DIMENSIONS:
            if dims is None: dims = set()
            if inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
                dims |= self.strctMdlParentNode.aspectValue(aspect, dims=dims, depth=depth+1)
            if inherit and isinstance(self.strctMdlParentNode, StrctMdlBreakdown) and isinstance(self.strctMdlParentNode.strctMdlParentNode, StrctMdlStructuralNode):
                dims |= self.strctMdlParentNode.strctMdlParentNode.aspectValue(aspect, dims=dims, depth=depth+1)
            if aspect in aspects:
                dims |= aspects[aspect]
            elif constraintSet is not None and constraintSet.hasAspect(self, aspect):
                dims |= set(defnMdlNode.aspectValue(xc, aspect) or {})
            if constraintSet is not None and constraintSet.hasAspect(self, Aspect.OMIT_DIMENSIONS):
                dims -= set(constraintSet.aspectValue(xc, Aspect.OMIT_DIMENSIONS))
            return dims
        if aspect in aspects:
            return aspects[aspect]
        elif constraintSet is not None and constraintSet.hasAspect(self, aspect):
            if isinstance(defnMdlNode, DefnMdlAspectNode):
                if contextItemBinding:
                    return contextItemBinding.aspectValue(aspect)
            else:
                return constraintSet.aspectValue(xc, aspect)
        if inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.aspectValue(aspect, depth=depth+1)
        elif inherit and isinstance(self.strctMdlParentNode, StrctMdlBreakdown) and isinstance(self.strctMdlParentNode.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.strctMdlParentNode.aspectValue(aspect, depth=depth+1)
        return None

    '''
    @property   
    def primaryItemQname(self):  # for compatibility with viewRelationsihps
        if Aspect.CONCEPT in self.aspects:
            return self.aspects[Aspect.CONCEPT]
        return self.defnMdlNode.primaryItemQname
        
    @property
    def explicitDims(self):
        return self.defnMdlNode.explicitDims
    '''
    @property
    def parentChildOrder(self):
        if self.defnMdlNode is not None:
            return self.defnMdlNode.parentChildOrder
        return "parent-first" # default value
            
    @property
    def tableDefinitionNode(self):
        if self.strctMdlParentNode is None:
            return self.tableNode
        else:
            return self.strctMdlParentNode.tableDefinitionNode
        
    @property
    def tagSelectors(self):
        try:
            return self._tagSelectors
        except AttributeError:
            self._tagSelectors = self.strctMdlParentNode.tagSelectors
            if self.tagSelector:
                self._tagSelectors.add(self.tagSelector)
            return self._tagSelectors
    
    @property
    def leafNodeCount(self):
        childLeafCount = 0
        if self.strctMdlChildNodes:
            for childStructuralNode in self.strctMdlChildNodes:
                childLeafCount += childStructuralNode.leafNodeCount
        if childLeafCount == 0:
            return 1
        return childLeafCount
    
    def setHasOpenNode(self):
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            self.strctMdlParentNode.setHasOpenNode()
        else:
            self.hasOpenNode = True

    def inheritedPrimaryItemQname(self, view):
        return (self.primaryItemQname or self.inheritedPrimaryItemQname(self.strctMdlParentNode, view))
            
    def inheritedExplicitDims(self, view, dims=None, nested=False):
        if dims is None: dims = {}
        if self.parentOrdinateContext:
            self.strctMdlParentNode.inheritedExplicitDims(view, dims, True)
        for dim, mem in self.explicitDims:
            dims[dim] = mem
        if not nested:
            return {(dim,mem) for dim,mem in dims.items() if mem != 'omit'}

    def inheritedAspectValue(self, otherAxisStructuralNode,
                             view, aspect, tagSelectors, 
                             xAspectStructuralNodes, yAspectStructuralNodes, zAspectStructuralNodes):
        aspectStructuralNodes = xAspectStructuralNodes.get(aspect, EMPTY_SET) | yAspectStructuralNodes.get(aspect, EMPTY_SET) | zAspectStructuralNodes.get(aspect, EMPTY_SET)
        structuralNode = None
        if len(aspectStructuralNodes) == 1:
            structuralNode = aspectStructuralNodes.pop()
        elif len(aspectStructuralNodes) > 1:
            if aspect == Aspect.LOCATION:
                hasClash = False
                for _aspectStructuralNode in aspectStructuralNodes:
                    if not _aspectStructuralNode.defnMdlNode.aspectValueDependsOnVars(aspect):
                        if structuralNode:
                            hasClash = True
                        else:
                            structuralNode = _aspectStructuralNode 
            else:
                # take closest structural node
                hasClash = True
                
            ''' reported in static analysis by RenderingEvaluator.py
            if hasClash:
                from arelle.ModelFormulaObject import aspectStr
                view.modelXbrl.error("xbrlte:aspectClashBetweenBreakdowns",
                    _("Aspect %(aspect)s covered by multiple axes."),
                    modelObject=view.modelTable, aspect=aspectStr(aspect))
            '''
        if structuralNode:
            definitionNodeConstraintSet = structuralNode.constraintSet(tagSelectors)
            if definitionNodeConstraintSet is not None and definitionNodeConstraintSet.aspectValueDependsOnVars(aspect):
                return self.evaluate(definitionNodeConstraintSet, 
                                     definitionNodeConstraintSet.aspectValue, # this passes a method
                                     otherAxisStructuralNode=otherAxisStructuralNode,
                                     evalArgs=(aspect,))
            return structuralNode.aspectValue(aspect, tagSelectors=tagSelectors)
        return None 
        
# Root class for rendering is formula, to allow linked and nested compiled expressions
def defnMdlLabelsView(mdlObj):
    return tuple(sorted([("{} {} {} {}".format(label.localName,
                                            str(rel.order).rstrip("0").rstrip("."),
                                            os.path.basename(label.role or ""),
                                            label.xmlLang), 
                          label.stringValue)
                         for rel in mdlObj.modelXbrl.relationshipSet((XbrlConst.elementLabel,XbrlConst.elementReference)).fromModelObject(mdlObj)
                         for label in (rel.toModelObject,)] +
                        [("xlink:label", mdlObj.xlinkLabel)]))

# REC Table linkbase
class DefnMdlTable(ModelFormulaResource):
    def init(self, modelDocument):
        super(DefnMdlTable, self).init(modelDocument)
        self.modelXbrl.modelRenderingTables.add(self)
        self.modelXbrl.hasRenderingTables = True
        self.aspectsInTaggedConstraintSets = set()
        
    def clear(self):
        if getattr(self, "_rendrCntx"):
            self._rendrCntx.close()
        super(ModelTable, self).clear()  # delete children
        
    @property
    def parentChildOrder(self):
        return parentChildOrder(self)

    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableFilter, XbrlConst.tableFilterMMDD,
                XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD,
                XbrlConst.tableParameter, XbrlConst.tableParameterMMDD)

    @property
    def ancestorArcroles(self):        
        return ()
                   
    @property
    def aspectModel(self):
        return "dimensional" # attribute removed 2013-06, always dimensional
                
    @property
    def filterRelationships(self):
        try:
            return self._filterRelationships
        except AttributeError:
            rels = [] # order so conceptName filter is first (if any) (may want more sorting in future)
            for rel in self.modelXbrl.relationshipSet((XbrlConst.tableFilter, XbrlConst.tableFilterMMDD)).fromModelObject(self):
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            self._filterRelationships = rels
            return rels
        
    ''' now only accessed from structural node    
    def header(self, role=None, lang=None, strip=False, evaluate=True):
        return self.genLabel(role=role, lang=lang, strip=strip)
    '''
  
    @property
    def definitionLabelsView(self):
        return defnMdlLabelsView(self)
    
    def filteredFacts(self, xpCtx, facts):
        return formulaEvaluatorFilterFacts(xpCtx, VariableBinding(xpCtx), 
                                           facts, self.filterRelationships, None)
        
    @property
    def renderingXPathContext(self):
        try:
            return self._rendrCntx
        except AttributeError:
            xpCtx = getattr(self.modelXbrl, "rendrCntx", None)
            if xpCtx is not None:
                self._rendrCntx = xpCtx.copy()
                for tblParamRel in self.modelXbrl.relationshipSet((XbrlConst.tableParameter, XbrlConst.tableParameterMMDD)).fromModelObject(self):
                    varQname = tblParamRel.variableQname
                    parameter = tblParamRel.toModelObject
                    if isinstance(parameter, ModelParameter):
                        self._rendrCntx.inScopeVars[varQname] = xpCtx.inScopeVars.get(parameter.parameterQname)
            else:
                self._rendrCntx = None
            return self._rendrCntx
        
    @property
    def propertyView(self):
        return ((("id", self.id),("xlink:label", self.xlinkLabel)) +
                self.definitionLabelsView)
        
    def __repr__(self):
        return ("DefnMdlTable[{0}]{1})".format(self.objectId(),self.propertyView))

    @property
    def definitionNodeView(self):        
        return XmlUtil.xmlstring(self, stripXmlns=True, prettyPrint=True)
  
    @property
    def definitionLabelsView(self):
        return defnMdlLabelsView(self)
  
class DefnMdlBreakdown(ModelFormulaResource):
    def init(self, modelDocument):
        super(DefnMdlBreakdown, self).init(modelDocument)
        
    @property
    def parentChildOrder(self):
        return parentChildOrder(self)

    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD)

    @property
    def ancestorArcroles(self):        
        return (XbrlConst.tableModel, XbrlConst.tableModelMMDD)

    @property
    def isRollUp(self):
        return False

    def hasAspect(self, structuralNode, aspect):
        return False

    @property
    def hasValueExpression(self):
        return False
        
    @property
    def isAbstract(self):
        return False
        
    def cardinalityAndDepth(self, structuralNode, **kwargs):
        return (1, 
                1 if (structuralNode.header(evaluate=False) is not None) else 0)
    @property
    def propertyView(self):
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("parent child order", self.get("parentChildOrder"))) +
                 defnMdlLabelsView(self))

        
    def __repr__(self):
        return ("DefnMdlBreakdown[{0}]{1})".format(self.objectId(),self.propertyView))

    @property
    def definitionNodeView(self):        
        return XmlUtil.xmlstring(self, stripXmlns=True, prettyPrint=True)
  
    @property
    def definitionLabelsView(self):
        return defnMdlLabelsView(self)

class DefnMdlDefinitionNode(ModelFormulaResource):
    aspectModel = "dimensional"
    
    def init(self, modelDocument):
        super(DefnMdlDefinitionNode, self).init(modelDocument)
    
    @property
    def parentDefinitionNode(self):
        return None
                
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD)
        
    def hasAspect(self, structuralNode, aspect):
        return False

    def aspectValueDependsOnVars(self, aspect):
        return False
    
    @property
    def variablename(self):
        """(str) -- name attribute"""
        return self.getStripped("name")

    @property
    def variableQname(self):
        """(QName) -- resolved name for an XPath bound result having a QName name attribute"""
        varName = self.variablename
        return qname(self, varName, noPrefixIsNoNamespace=True) if varName else None

    def aspectValue(self, xpCtx, aspect, inherit=True):
        if aspect == Aspect.DIMENSIONS:
            return []
        return None
    
    def aspectsCovered(self):
        return set()

    @property
    def constraintSets(self):
        return {None: self}
                    
    @property
    def tagSelector(self):
        return self.get("tagSelector")
            
    @property
    def valueExpression(self):
        return self.get("value") 

    @property
    def hasValueExpression(self):
        return bool(self.valueProg)  # non empty program
    
    def compile(self):
        if not hasattr(self, "valueProg"):
            value = self.valueExpression
            self.valueProg = XPathParser.parse(self, value, self, "value", Trace.VARIABLE)
        # duplicates formula resource for RuleAxis but not for other subclasses
        super(DefnMdlDefinitionNode, self).compile()
        
    def evalValueExpression(self, xpCtx, fact):
        # compiled by FormulaResource compile()
        return xpCtx.evaluateAtomicValue(self.valueProg, 'xs:string', fact)
    
    '''
    @property   
    def primaryItemQname(self):  # for compatibility with viewRelationsihps
        return None
        
    @property
    def explicitDims(self):
        return set()
    '''
        
    @property
    def isAbstract(self):
        return False
    
    @property
    def isMerged(self):
        return False
    
    def cardinalityAndDepth(self, structuralNode, **kwargs):
        return (1, 
                1 if (structuralNode.header(evaluate=False) is not None) else 0)
        
    ''' now only accessed from structural node (mulst have table context for evaluate)           
    def header(self, role=None, lang=None, strip=False, evaluate=True):
        if role is None:
            # check for message before checking for genLabel
            msgsRelationshipSet = self.modelXbrl.relationshipSet((XbrlConst.tableDefinitionNodeMessage201301, XbrlConst.tableAxisMessage2011))
            if msgsRelationshipSet:
                msg = msgsRelationshipSet.label(self, XbrlConst.standardMessage, lang, returnText=False)
                if msg is not None:
                    if evaluate:
                        result = msg.evaluate(self.modelXbrl.rendrCntx)
                    else:
                        result = XmlUtil.text(msg)
                    if strip:
                        return result.strip()
                    return result
        return self.genLabel(role=role, lang=lang, strip=strip)
    '''

    @property
    def definitionNodeView(self):        
        return XmlUtil.xmlstring(self, stripXmlns=True, prettyPrint=True)
  
    @property
    def definitionLabelsView(self):
        return defnMdlLabelsView(self)

class DefnMdlClosedDefinitionNode(DefnMdlDefinitionNode):
    def init(self, modelDocument):
        super(DefnMdlClosedDefinitionNode, self).init(modelDocument)
        
    @property
    def abstract(self):
        return self.get("abstract")
    
    @property
    def isAbstract(self):
        return self.abstract == 'true'
        
    @property
    def parentChildOrder(self):
        return parentChildOrder(self)

    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD)

    @property
    def ancestorArcroles(self):        
        return (XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD, XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD)
    
    def filteredFacts(self, xpCtx, facts):
        aspects = self.aspectsCovered()
        axisAspectValues = dict((aspect, self.aspectValue(xpCtx, aspect))
                                for aspect in aspects)
        fp = FactPrototype(self, axisAspectValues)
        return set(fact
                   for fact in facts
                   if aspectsMatch(xpCtx, fact, fp, aspects))
        
    @property
    def isRollUp(self):
        # indicates this definition node has children with same aspect
        descendantRels = self.modelXbrl.relationshipSet(self.descendantArcroles).fromModelObject(self)
        if descendantRels:
            selfAspectsCovered = self.aspectsCovered()
            if selfAspectsCovered: # is roll up if self and descendants cover same aspects
                return all(selfAspectsCovered == rel.toModelObject.aspectsCovered()
                           for rel in descendantRels
                           if rel.toModelObject is not None)
            aDescendantAspectsCovered = None
            for rel in descendantRels: # no self aspects, find any descendant's aspects
                if rel.toModelObject is not None:
                    aDescendantAspectsCovered = rel.toModelObject.aspectsCovered()
                    break
            if aDescendantAspectsCovered: # all descendants must contribute same aspects to be a roll up
                return all(aDescendantAspectsCovered == rel.toModelObject.aspectsCovered()
                           for rel in descendantRels
                           if rel.toModelObject is not None)
        return False
    
        
class DefnMdlConstraintSet(ModelFormulaRules):
    def init(self, modelDocument):
        super(DefnMdlConstraintSet, self).init(modelDocument)
        self.aspectValues = {} # only needed if error blocks compiling this node, replaced by compile()
        self.aspectProgs = {} # ditto
        
    def hasAspect(self, structuralNode, aspect, inherit=None):
        return self._hasAspect(structuralNode, aspect, inherit)
    
    def _hasAspect(self, structuralNode, aspect, inherit=None): # opaque from ModelRuleDefinitionNode
        if aspect in aspectRuleAspects:
            return any(self.hasRule(a) for a in aspectRuleAspects[aspect])
        return self.hasRule(aspect)
    
    def aspectValue(self, xpCtx, aspect, inherit=None):
        try:
            # if xpCtx is None: xpCtx = self.modelXbrl.rendrCntx (must have xpCtx of callint table)
            return self.evaluateRule(xpCtx, aspect)
        except AttributeError:
            return '(unavailable)'  # table defective or not initialized
    
    def aspectValueDependsOnVars(self, aspect):
        return aspect in _DICT_SET(self.aspectProgs.keys())
    
    def aspectsCovered(self):
        return _DICT_SET(self.aspectValues.keys()) | _DICT_SET(self.aspectProgs.keys())
    
    '''
    @property   
    def primaryItemQname(self):
        return self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.CONCEPT)

    @property
    def explicitDims(self):
        dimMemSet = set()
        dims = self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.DIMENSIONS)
        if dims: # may be none if no dim aspects on this ruleAxis
            for dim in dims:
                mem = self.evaluateRule(self.modelXbrl.rendrCntx, dim)
                if mem: # may be none if dimension was omitted
                    dimMemSet.add( (dim, mem) )
        return dimMemSet
    
    @property
    def instant(self):
        periodType = self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.PERIOD_TYPE)
        if periodType == "forever":
            return None
        return self.evaluateRule(self.modelXbrl.rendrCntx, 
                                 {"instant": Aspect.INSTANT,
                                  "duration": Aspect.END}[periodType])
    '''
    
    def cardinalityAndDepth(self, structuralNode, **kwargs):
        if self.aspectValues or self.aspectProgs or structuralNode.header(evaluate=False) is not None:
            return (1, 1)
        else:
            return (0, 0)

class DefnMdlRuleSet(DefnMdlConstraintSet, ModelFormulaResource):
    def init(self, modelDocument):
        super(DefnMdlRuleSet, self).init(modelDocument)
        
    @property
    def tagName(self):  # can't call it tag because that would hide ElementBase.tag
        return self.get("tag")

class DefnMdlRuleDefinitionNode(DefnMdlConstraintSet, DefnMdlClosedDefinitionNode):
    def init(self, modelDocument):
        super(DefnMdlRuleDefinitionNode, self).init(modelDocument)
        
    @property
    def merge(self):
        return self.get("merge")
    
    @property
    def isMerged(self):
        return self.merge == "true"
    
    @property
    def constraintSets(self):
        try:
            return self._constraintSets
        except AttributeError:
            self._constraintSets = dict((ruleSet.tagName, ruleSet)
                                        for ruleSet in XmlUtil.children(self, self.namespaceURI, "ruleSet"))
            if self.aspectsCovered(): # any local rule?
                self._constraintSets[None] = self                
            return self._constraintSets
            
    def hasAspect(self, structuralNode, aspect):
        return any(constraintSet._hasAspect(structuralNode, aspect)
                   for constraintSet in self.constraintSets.values())
        
    @property
    def aspectsInTaggedConstraintSet(self):
        try:
            return self._aspectsInTaggedConstraintSet
        except AttributeError:
            self._aspectsInTaggedConstraintSet = set()
            for tag, constraintSet in self.constraitSets().items():
                if tag is not None:
                    for aspect in constraintSet.aspectsCovered():
                        if aspect != Aspect.DIMENSIONS:
                            self._aspectsInTaggedConstraintSet.add(aspect)
            return self._aspectsInTaggedConstraintSet
                    
    def compile(self):
        super(DefnMdlRuleDefinitionNode, self).compile()
        for constraintSet in self.constraintSets.values():
            if constraintSet != self: # compile nested constraint sets
                constraintSet.compile()
   
    @property
    def propertyView(self):
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("abstract", self.abstract),
                 ("merge", self.merge),
                 ("definition", self.definitionNodeView)) +
                 self.definitionLabelsView)
        
    def __repr__(self):
        return ("DefnMdlRuleDefinitionNode[{0}]{1})".format(self.objectId(),self.propertyView))

class DefnMdlRelationshipNode(DefnMdlClosedDefinitionNode):
    def init(self, modelDocument):
        super(DefnMdlRelationshipNode, self).init(modelDocument)
        
    def aspectsCovered(self):
        return {Aspect.CONCEPT}

    @property
    def conceptQname(self):
        name = self.getStripped("conceptname")
        return qname(self, name, noPrefixIsNoNamespace=True) if name else None
        
    @property
    def relationshipSourceQname(self):
        sourceQname = XmlUtil.child(self, (XbrlConst.table, XbrlConst.tableMMDD), "relationshipSource")
        if sourceQname is not None:
            return qname( sourceQname, XmlUtil.text(sourceQname) )
        return None
    
    @property
    def linkrole(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "linkrole")

    @property
    def axis(self):
        a = XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), ("axis", "formulaAxis"))
        if not a: a = 'descendant'  # would be an XML error
        return a
    
    @property
    def isOrSelfAxis(self):
        return self.axis.endswith('-or-self')

    @property
    def generations(self):
        try:
            return _INT( XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "generations") )
        except (TypeError, ValueError):
            if self.axis in ('sibling', 'child', 'parent'): 
                return 1
            return 0

    @property
    def relationshipSourceQnameExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "relationshipSourceExpression")

    @property
    def linkroleExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "linkroleExpression")

    @property
    def axisExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), ("axisExpression", "formulAxisExpression"))

    @property
    def generationsExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "generationsExpression")

    def compile(self):
        if not hasattr(self, "relationshipSourceQnameExpressionProg"):
            self.relationshipSourceQnameExpressionProg = XPathParser.parse(self, self.relationshipSourceQnameExpression, self, "relationshipSourceQnameExpressionProg", Trace.VARIABLE)
            self.linkroleExpressionProg = XPathParser.parse(self, self.linkroleExpression, self, "linkroleQnameExpressionProg", Trace.VARIABLE)
            self.axisExpressionProg = XPathParser.parse(self, self.axisExpression, self, "axisExpressionProg", Trace.VARIABLE)
            self.generationsExpressionProg = XPathParser.parse(self, self.generationsExpression, self, "generationsExpressionProg", Trace.VARIABLE)
            super(DefnMdlRelationshipNode, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        if self.relationshipSourceQname and self.relationshipSourceQname != XbrlConst.qnXfiRoot:
            if varRefSet is None: varRefSet = set()
            varRefSet.add(self.relationshipSourceQname)
        return super(DefnMdlRelationshipNode, self).variableRefs(
                                                [p for p in (self.relationshipSourceQnameExpressionProg,
                                                             self.linkroleExpressionProg, self.axisExpressionProg,
                                                             self.generationsExpressionProg)
                                        if p], varRefSet)

    def evalRrelationshipSourceQname(self, xpCtx, fact=None):
        if self.relationshipSourceQname:
            return self.relationshipSourceQname
        return xpCtx.evaluateAtomicValue(self.relationshipSourceQnameExpressionProg, 'xs:QName', fact)
    
    def evalLinkrole(self, xpCtx, fact=None):
        if self.linkrole:
            return self.linkrole
        return xpCtx.evaluateAtomicValue(self.linkroleExpressionProg, 'xs:anyURI', fact)
    
    def evalAxis(self, xpCtx, fact=None):
        if self.axis:
            return self.axis
        return xpCtx.evaluateAtomicValue(self.axisExpressionProg, 'xs:token', fact)
    
    def evalGenerations(self, xpCtx, fact=None):
        if self.generations:
            return self.generations
        return xpCtx.evaluateAtomicValue(self.generationsExpressionProg, 'xs:integer', fact)

    def cardinalityAndDepth(self, structuralNode, **kwargs):
        return self.lenDepth(self.relationships(structuralNode, **kwargs), 
                             self.axis.endswith('-or-self'))
    
    def lenDepth(self, nestedRelationships, includeSelf):
        l = 0
        d = 1
        for rel in nestedRelationships:
            if isinstance(rel, list):
                nl, nd = self.lenDepth(rel, False)
                l += nl
                nd += 1 # returns 0 if sublist is not nested
                if nd > d:
                    d = nd
            else:
                l += 1
                if includeSelf:
                    l += 1 # root relationships include root in addition
        if includeSelf:
            d += 1
        return (l, d)
    
    @property
    def propertyView(self):
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("abstract", self.abstract),
                 ("definition", self.definitionNodeView)) +
                self.definitionLabelsView)
        
    def __repr__(self):
        return ("defnMdlRelationshipNode[{0}]{1})".format(self.objectId(),self.propertyView))
    
class DefnMdlConceptRelationshipNode(DefnMdlRelationshipNode):
    def init(self, modelDocument):
        super(DefnMdlConceptRelationshipNode, self).init(modelDocument)
    
    def hasAspect(self, structuralNode, aspect):
        return aspect == Aspect.CONCEPT

    @property
    def arcrole(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcrole")

    @property
    def arcQname(self):
        arcnameElt = XmlUtil.child(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcname")
        if arcnameElt is not None:
            return qname( arcnameElt, XmlUtil.text(arcnameElt) )
        return None

    @property
    def linkQname(self):
        linknameElt = XmlUtil.child(self, (XbrlConst.table, XbrlConst.tableMMDD), "linkname")
        if linknameElt is not None:
            return qname( linknameElt, XmlUtil.text(linknameElt) )
        return None
    

    def compile(self):
        if not hasattr(self, "arcroleExpressionProg"):
            self.arcroleExpressionProg = XPathParser.parse(self, self.arcroleExpression, self, "arcroleExpressionProg", Trace.VARIABLE)
            self.linkQnameExpressionProg = XPathParser.parse(self, self.linkQnameExpression, self, "linkQnameExpressionProg", Trace.VARIABLE)
            self.arcQnameExpressionProg = XPathParser.parse(self, self.arcQnameExpression, self, "arcQnameExpressionProg", Trace.VARIABLE)
            super(DefnMdlConceptRelationshipNode, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super(DefnMdlConceptRelationshipNode, self).variableRefs(
                                                [p for p in (self.arcroleExpressionProg,
                                                             self.linkQnameExpressionProg, self.arcQnameExpressionProg)
                                                 if p], varRefSet)

    def evalArcrole(self, xpCtx, fact=None):
        if self.arcrole:
            return self.arcrole
        return xpCtx.evaluateAtomicValue(self.arcroleExpressionProg, 'xs:anyURI', fact)
    
    def evalLinkQname(self, xpCtx, fact=None):
        if self.linkQname:
            return self.linkQname
        return xpCtx.evaluateAtomicValue(self.linkQnameExpressionProg, 'xs:QName', fact)
    
    def evalArcQname(self, xpCtx, fact=None):
        if self.arcQname:
            return self.arcQname
        return xpCtx.evaluateAtomicValue(self.arcQnameExpressionProg, 'xs:QName', fact)

    @property
    def arcroleExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcroleExpression")

    @property
    def linkQnameExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "linknameExpression")

    @property
    def arcQnameExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcnameExpression")
    
    def coveredAspect(self, ordCntx=None):
        return Aspect.CONCEPT

    def relationships(self, structuralNode, **kwargs):
        self._sourceQname = structuralNode.evaluate(self, self.evalRrelationshipSourceQname, **kwargs) or XbrlConst.qnXfiRoot
        linkrole = structuralNode.evaluate(self, self.evalLinkrole)
        if not linkrole:
            linkrole = "XBRL-all-linkroles"
        linkQname = (structuralNode.evaluate(self, self.evalLinkQname) or () )
        arcrole = (structuralNode.evaluate(self, self.evalArcrole) or () )
        arcQname = (structuralNode.evaluate(self, self.evalArcQname) or () )
        self._axis = (structuralNode.evaluate(self, self.evalAxis) or () )
        self._generations = (structuralNode.evaluate(self, self.evalGenerations) or () )
        return concept_relationships(self.modelXbrl.rendrCntx, 
                                     None, 
                                     (self._sourceQname,
                                      linkrole,
                                      arcrole,
                                      self._axis.replace('-or-self',''),
                                      self._generations,
                                      linkQname,
                                      arcQname),
                                     True) # return nested lists representing concept tree nesting
    
class DefnMdlDimensionRelationshipNode(DefnMdlRelationshipNode):
    def init(self, modelDocument):
        super(DefnMdlDimensionRelationshipNode, self).init(modelDocument)
    
    def hasAspect(self, structuralNode, aspect):
        return aspect == self.coveredAspect(structuralNode) or aspect == Aspect.DIMENSIONS
    
    def aspectValue(self, xpCtx, aspect, inherit=None):
        if aspect == Aspect.DIMENSIONS:
            return (self.coveredAspect(xpCtx), )
        return None
    
    def aspectsCovered(self):
        return {self.dimensionQname}

    @property
    def dimensionQname(self):
        dimensionElt = XmlUtil.child(self, (XbrlConst.table, XbrlConst.tableMMDD), "dimension")
        if dimensionElt is not None:
            return qname( dimensionElt, XmlUtil.text(dimensionElt) )
        return None

    @property
    def dimensionQnameExpression(self):
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "dimensionExpression")

    def compile(self):
        if not hasattr(self, "dimensionQnameExpressionProg"):
            self.dimensionQnameExpressionProg = XPathParser.parse(self, self.dimensionQnameExpression, self, "dimensionQnameExpressionProg", Trace.VARIABLE)
            super(DefnMdlDimensionRelationshipNode, self).compile()
        
    def variableRefs(self, progs=[], varRefSet=None):
        return super(DefnMdlDimensionRelationshipNode, self).variableRefs(self.dimensionQnameExpressionProg, varRefSet)

    def evalDimensionQname(self, xpCtx, fact=None):
        if self.dimensionQname:
            return self.dimensionQname
        return xpCtx.evaluateAtomicValue(self.dimensionQnameExpressionProg, 'xs:QName', fact)
    
    def coveredAspect(self, structuralNode=None):
        try:
            return self._coveredAspect
        except AttributeError:
            self._coveredAspect = self.dimRelationships(structuralNode, getDimQname=True)
            return self._coveredAspect
        
    def relationships(self, structuralNode, **kwargs):
        return self.dimRelationships(structuralNode, getMembers=True)
    
    def dimRelationships(self, structuralNode, getMembers=False, getDimQname=False):
        self._dimensionQname = structuralNode.evaluate(self, self.evalDimensionQname)
        self._sourceQname = structuralNode.evaluate(self, self.evalRrelationshipSourceQname) or XbrlConst.qnXfiRoot
        linkrole = structuralNode.evaluate(self, self.evalLinkrole)
        if not linkrole and getMembers:
            linkrole = "XBRL-all-linkroles"
        dimConcept = self.modelXbrl.qnameConcepts.get(self._dimensionQname)
        sourceConcept = self.modelXbrl.qnameConcepts.get(self._sourceQname)
        self._axis = (structuralNode.evaluate(self, self.evalAxis) or () )
        self._generations = (structuralNode.evaluate(self, self.evalGenerations) or () )
        if ((self._dimensionQname and (dimConcept is None or not dimConcept.isDimensionItem)) or
            (self._sourceQname and self._sourceQname != XbrlConst.qnXfiRoot and (
                    sourceConcept is None or not sourceConcept.isItem))):
            return ()
        if dimConcept is not None:
            if getDimQname:
                return self._dimensionQname
            if sourceConcept is None:
                sourceConcept = dimConcept
        if getMembers:
            return concept_relationships(self.modelXbrl.rendrCntx, 
                                         None, 
                                         (self._sourceQname,
                                          linkrole,
                                          "XBRL-dimensions",  # all dimensions arcroles
                                          self._axis.replace('-or-self',''),
                                          self._generations),
                                         True) # return nested lists representing concept tree nesting
        if getDimQname:
            if sourceConcept is not None:
                # look back from member to a dimension
                return self.stepDimRel(sourceConcept, linkrole)
            return None
        
    def stepDimRel(self, stepConcept, linkrole):
        if stepConcept.isDimensionItem:
            return stepConcept.qname
        for rel in self.modelXbrl.relationshipSet("XBRL-dimensions").toModelObject(stepConcept):
            if not linkrole or linkrole == rel.consecutiveLinkrole:
                dim = self.stepDimRel(rel.fromModelObject, rel.linkrole)
                if dim:
                    return dim
        return None
        
coveredAspectToken = {"concept": Aspect.CONCEPT, 
                      "entity-identifier": Aspect.VALUE, 
                      "period-start": Aspect.START, "period-end": Aspect.END, 
                      "period-instant": Aspect.INSTANT, "period-instant-end": Aspect.INSTANT_END, 
                      "unit": Aspect.UNIT}

class DefnMdlOpenDefinitionNode(DefnMdlDefinitionNode):
    def init(self, modelDocument):
        super(DefnMdlOpenDefinitionNode, self).init(modelDocument)

    @property
    def isRollUp(self):
        return False
            
aspectNodeAspectCovered = {"conceptAspect": Aspect.CONCEPT,
                           "unitAspect": Aspect.UNIT,
                           "entityIdentifierAspect": Aspect.ENTITY_IDENTIFIER,
                           "periodAspect": Aspect.PERIOD}

class DefnMdlAspectNode(DefnMdlOpenDefinitionNode):
    def init(self, modelDocument):
        super(DefnMdlAspectNode, self).init(modelDocument)
    
    @property
    def descendantArcroles(self):        
        return (XbrlConst.tableAspectNodeFilter, XbrlConst.tableAspectNodeFilterMMDD,
                XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD)
    
        
    @property
    def filterRelationships(self):
        try:
            return self._filterRelationships
        except AttributeError:
            rels = [] # order so conceptName filter is first (if any) (may want more sorting in future)
            for rel in self.modelXbrl.relationshipSet((XbrlConst.tableAspectNodeFilter, XbrlConst.tableAspectNodeFilterMMDD)).fromModelObject(self):
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            self._filterRelationships = rels
            return rels
    
    def hasAspect(self, structuralNode, aspect):
        return aspect in self.aspectsCovered()
    
    def aspectsCovered(self, varBinding=None):
        try:
            return self._aspectsCovered
        except AttributeError:
            self._aspectsCovered = set()
            self._dimensionsCovered = set()
            self.includeUnreportedValue = False
            aspectElt = XmlUtil.child(self, self.namespaceURI, ("conceptAspect", "unitAspect", "entityIdentifierAspect", "periodAspect", "dimensionAspect"))
            if aspectElt is not None:
                if aspectElt.localName == "dimensionAspect":
                    dimQname = qname(aspectElt, aspectElt.textValue)
                    self._aspectsCovered.add(dimQname)
                    self._aspectsCovered.add(Aspect.DIMENSIONS)
                    self._dimensionsCovered.add(dimQname)
                    self.includeUnreportedValue = aspectElt.get("includeUnreportedValue") in ("true", "1")
                else:
                    self._aspectsCovered.add(aspectNodeAspectCovered[aspectElt.localName])                                                  
            return self._aspectsCovered

    def aspectValue(self, xpCtx, aspect, inherit=None):
        if aspect == Aspect.DIMENSIONS:
            return self._dimensionsCovered
        # does not apply to filter, value can only come from a bound fact
        return None
    
    def filteredFactsPartitions(self, xpCtx, facts):
        filteredFacts = formulaEvaluatorFilterFacts(xpCtx, VariableBinding(xpCtx), 
                                                    facts, self.filterRelationships, None)
        if not self.includeUnreportedValue:
            # remove unreported falue
            reportedAspectFacts = set()
            for fact in filteredFacts:
                if all(fact.context is not None and
                       isinstance(fact.context.dimValue(dimAspect), ModelDimensionValue)
                       for dimAspect in self._dimensionsCovered):
                    reportedAspectFacts.add(fact)
        else:
            reportedAspectFacts = filteredFacts
        return factsPartitions(xpCtx, reportedAspectFacts, self.aspectsCovered())
        
    @property
    def propertyView(self):
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("aspect", ", ".join(aspectStr(aspect)
                                      for aspect in self.aspectsCovered()
                                      if aspect != Aspect.DIMENSIONS)),
                 ("definition", self.definitionNodeView)) +
                self.definitionLabelsView)
        
        

from arelle.ModelObjectFactory import elementSubstitutionModelClass
elementSubstitutionModelClass.update((
    # IWD
    (XbrlConst.qnTableTableMMDD, DefnMdlTable),
    (XbrlConst.qnTableBreakdownMMDD, DefnMdlBreakdown),
    (XbrlConst.qnTableRuleSetMMDD, DefnMdlRuleSet),
    (XbrlConst.qnTableRuleNodeMMDD, DefnMdlRuleDefinitionNode),
    (XbrlConst.qnTableConceptRelationshipNodeMMDD, DefnMdlConceptRelationshipNode),
    (XbrlConst.qnTableDimensionRelationshipNodeMMDD, DefnMdlDimensionRelationshipNode),
    (XbrlConst.qnTableAspectNodeMMDD, DefnMdlAspectNode),
    # REC
    (XbrlConst.qnTableTable, DefnMdlTable),
    (XbrlConst.qnTableBreakdown, DefnMdlBreakdown),
    (XbrlConst.qnTableRuleSet, DefnMdlRuleSet),
    (XbrlConst.qnTableRuleNode, DefnMdlRuleDefinitionNode),
    (XbrlConst.qnTableConceptRelationshipNode, DefnMdlConceptRelationshipNode),
    (XbrlConst.qnTableDimensionRelationshipNode, DefnMdlDimensionRelationshipNode),
    (XbrlConst.qnTableAspectNode, DefnMdlAspectNode),
     ))

# import after other modules resolved to prevent circular references
from arelle.FunctionXfi import concept_relationships
