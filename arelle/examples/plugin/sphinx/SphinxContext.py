'''
sphinxContext provides the validation and execution context for Sphinx language expressions.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

from .SphinxParser import astNode, astWith
from arelle.ModelFormulaObject import aspectModels, Aspect, aspectStr
from arelle.ModelInstanceObject import ModelFact, ModelDimensionValue
from arelle.FormulaEvaluator import implicitFilter, aspectsMatch
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT, NONDEFAULT
from arelle import XmlUtil
                                       
class SphinxContext:
    def __init__(self, sphinxProgs, modelXbrl=None):
        self.modelXbrl = modelXbrl  # the DTS and input instance (if any)
        self.sphinxProgs = sphinxProgs
        self.rules = []
        self.transformQnames = {}
        self.transformNamespaces = {}
        self.constants = {}
        self.functions = {}
        self.preconditions = {}
        self.localVariables = {}
        self.tags = {}
        self.hyperspaceBindings = None
        self.staticSeverity = None
        self.dynamicSeverity = None
        self.dimensionIsExplicit = {}  # qname of dimension (axis), True if explicit, False if typed
        if modelXbrl is not None:
            self.formulaOptions = modelXbrl.modelManager.formulaOptions
            self.defaultDimensionAspects = set(modelXbrl.qnameDimensionDefaults.keys())
        
    def close(self):
        # dereference grammar
        for prog in self.sphinxProgs:
            for node in prog:
                if isinstance(node, astNode):
                    node.clear()
            prog.clear
        del self.sphinxProgs[:]
        self.__dict__.clear()  # delete local attributes
        
class HyperspaceBindings:
    def __init__(self, sphinxContext):
        self.sCtx = sphinxContext
        self.parentHyperspaceBindings = sphinxContext.hyperspaceBindings
        sphinxContext.hyperspaceBindings = self
        self.hyperspaceBindings = []
        self.nodeBindings = {}
        self.withRestrictionBindings = []
        self.aspectBoundFacts = {}
        self.nestedAggregationsDepth = 0
        
    def close(self):
        if self.sCtx.hyperspaceBindings is self:
            self.sCtx.hyperspaceBindings = self.parentHyperspaceBindings
        for hsBinding in self.hyperspaceBindings:
            hsBinding.close()
        self.__dict__.clear() # dereference
        
    def nodeBinding(self, node, isWithRestrictionNode=False):
        if node in self.nodeBindings:
            return self.nodeBindings[node]
        nodeBinding = HyperspaceBinding(self, node, isWithRestrictionNode=isWithRestrictionNode)
        self.nodeBindings[node] = nodeBinding
        self.hyperspaceBindings.append(nodeBinding)
        return nodeBinding
        
    def next(self, iterateAbove=-1, bindingsLen=-1):        
        # iterate hyperspace bindings
        if not self.hyperspaceBindings:
            raise StopIteration
        hsBsToReset = []
        if bindingsLen == -1: 
            bindingsLen = len(self.hyperspaceBindings)
        for iHsB in range(bindingsLen - 1, iterateAbove, -1):
            hsB = self.hyperspaceBindings[iHsB]
            try:
                hsB.next()
                for hsB in hsBsToReset:
                    hsB.reset()
                return # hsB has another value to return
            except StopIteration:
                hsBsToReset.insert(0, hsB)  # reset after outer iterator advanced
        raise StopIteration # no more outermost loop of iteration
    
    @property
    def boundFacts(self):
        return [binding.yieldedFact
                for binding in self.hyperspaceBindings
                if not binding.fallenBack and binding.yieldedFact is not None]
        
class HyperspaceBinding:
    def __init__(self, hyperspaceBindings, node, fallback=False, isWithRestrictionNode=False):
        self.hyperspaceBindings = hyperspaceBindings
        self.sCtx = hyperspaceBindings.sCtx
        self.node = node
        self.isWithRestrictionNode = isWithRestrictionNode
        self.fallback = fallback
        self.aspectsQualified = set()
        self.varName = None
        self.tagName = None
        self.aspectsDefined = set(aspectModels["dimensional"])
        if hyperspaceBindings.withRestrictionBindings:
            withAspectsQualified = hyperspaceBindings.withRestrictionBindings[-1].aspectsQualified
        else:
            withAspectsQualified = set()
        self.aspectsQualified = _DICT_SET(self.node.axes.keys()) | withAspectsQualified
        self.reset()  # will raise StopIteration if no facts or fallback
        
    def close(self):
        self.__dict__.clear() # dereference
        
    @property
    def value(self):
        if self.fallenBack:
            return None
        if self.yieldedFact is not None:
            return self.yieldedFact.xValue
        return None

    def __repr__(self):
        if self.fallenBack:
            return "fallen-back"
        if self.yieldedFact is not None:
            return self.yieldedFact.__repr__()
        return "none"
        
    def reset(self):
        # start with all facts
        if self.hyperspaceBindings.withRestrictionBindings:
            facts = self.hyperspaceBindings.withRestrictionBindings[-1].yieldedFactsPartition
        else:
            facts = self.sCtx.modelXbrl.nonNilFactsInInstance
        if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
            self.sCtx.modelXbrl.info("sphinx:trace",
                 _("Hyperspace %(variable)s binding: start with %(factCount)s facts"), 
                 modelObject=self.node, variable=str(self.node), factCount=len(facts))
        # filter by hyperspace aspects
        facts = self.filterFacts(facts)
        for fact in facts:
            if fact.isItem:
                self.aspectsDefined |= fact.context.dimAspects(self.sCtx.defaultDimensionAspects)
        self.unQualifiedAspects = self.aspectsDefined - self.aspectsQualified - {Aspect.DIMENSIONS}
        # implicitly filter by prior uncoveredAspectFacts
        if self.hyperspaceBindings.aspectBoundFacts:
            facts = implicitFilter(self.sCtx, self, facts, self.unQualifiedAspects, self.hyperspaceBindings.aspectBoundFacts)
        if self.sCtx.formulaOptions.traceVariableFiltersResult:
            self.sCtx.modelXbrl.info("sphinx:trace",
                 _("Hyperspace %(variable)s binding: filters result %(factCount)s facts"), 
                 modelObject=self.node, variable=str(self.node), factCount=len(facts))
        if self.isWithRestrictionNode: # if withNode, combine facts into partitions by qualified aspects
            factsPartitions = []
            for fact in facts:
                matched = False
                for partition in factsPartitions:
                    if aspectsMatch(self.sCtx, fact, partition[0], self.aspectsQualified):
                        partition.append(fact)
                        matched = True
                        break
                if not matched:
                    factsPartitions.append([fact,])
            self.factIter = iter([set(p) for p in factsPartitions])  # must be sets
            self.yieldedFactsPartition = []
        else: # just a hyperspaceExpression node
            self.factIter = iter(facts)
        self.yieldedFact = None
        self.fallenBack = False
        self.next()

        
    def next(self): # will raise StopIteration if no (more) facts or fallback
        uncoveredAspectFacts = self.hyperspaceBindings.aspectBoundFacts
        if self.yieldedFact is not None and self.hyperspaceBindings.nestedAggregationsDepth == 0:
            for aspect, priorFact in self.evaluationContributedUncoveredAspects.items():
                if priorFact == "none":
                    del uncoveredAspectFacts[aspect]
                else:
                    uncoveredAspectFacts[aspect] = priorFact
            self.evaluationContributedUncoveredAspects.clear()
        try:
            if self.isWithRestrictionNode:
                self.yieldedFactsPartition = next(self.factIter)
                for self.yieldedFact in self.yieldedFactsPartition:
                    break
            else:
                self.yieldedFact = next(self.factIter)
            self.evaluationContributedUncoveredAspects = {}
            for aspect in self.unQualifiedAspects:  # covered aspects may not be defined e.g., test 12062 v11, undefined aspect is a complemented aspect
                if uncoveredAspectFacts.get(aspect) is None:
                    self.evaluationContributedUncoveredAspects[aspect] = uncoveredAspectFacts.get(aspect,"none")
                    uncoveredAspectFacts[aspect] = None if aspect in self.node.axes else self.yieldedFact
            if self.sCtx.formulaOptions.traceVariableFiltersResult:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("Hyperspace %(variable)s: bound value %(result)s"), 
                     modelObject=self.node, variable=str(self.node), result=str(self.yieldedFact))
        except StopIteration:
            self.yieldedFact = None
            if self.isWithRestrictionNode:
                self.yieldedFactsPartition = []
            if self.fallback and not self.fallenBack:
                self.fallenBack = True
                if self.sCtx.formulaOptions.traceVariableExpressionResult:
                    self.sCtx.modelXbrl.info("sphinx:trace",
                         _("Hyperspace %(variable)s: fallbackValue result %(result)s"), 
                         modelObject=self.node, variable=str(self.node), result=0)
            else:
                raise StopIteration

    def filterFacts(self, facts):
        modelXbrl = self.sCtx.modelXbrl
        orderedAxes = []
        # process with bindings and this node
        for aspect, hsAxis in self.node.axes.items():
            if aspect == Aspect.CONCEPT:
                orderedAxes.insert(0, hsAxis)
            else:
                orderedAxes.append(hsAxis)
        for i, hsAxis in enumerate(orderedAxes):
            # value is an astHyperspaceAxis
            if hsAxis.whereExpr and facts:
                whereMatchedFacts = set()
                asVars = set()
                for fact in facts:
                    for hsAxisAs in orderedAxes[0:i+1]:
                        if hsAxisAs.asVariableName:
                            self.sCtx.localVariables[hsAxisAs.asVariableName] = factAspectValue(fact, hsAxisAs.aspect)
                            asVars.add(hsAxisAs.asVariableName)
                    self.sCtx.localVariables["item"] = fact
                    if evaluate(hsAxis.whereExpr, self.sCtx):
                        whereMatchedFacts.add(fact)
                del self.sCtx.localVariables["item"]
                for asVar in asVars:
                    del self.sCtx.localVariables[asVar]
                facts = whereMatchedFacts
            elif hsAxis.restriction:
                restrictions = [evaluate(r, self.sCtx, value=True) if isinstance(r, astNode)
                                else r
                                for r in hsAxis.restriction]
                if hsAxis.aspect == Aspect.CONCEPT:
                    aspectQualifiedFacts = [modelXbrl.factsByQname[qn]
                                            for qn in restrictions
                                            if isinstance(qn, QName)]
                    facts = facts & set.union(*aspectQualifiedFacts) if aspectQualifiedFacts else set()
                elif hsAxis.aspect == Aspect.PERIOD:
                    facts = set(f for f in facts if isPeriodEqualTo(f, restrictions))
                elif hsAxis.aspect == Aspect.ENTITY_IDENTIFIER:
                    facts = set(f for f in facts if isEntityIdentifierEqualTo(f, restrictions))
                elif isinstance(hsAxis.aspect, QName):
                    if self.sCtx.dimensionIsExplicit.get(hsAxis.aspect):
                        # explicit dim facts (value None will match the default member)
                        aspectQualifiedFacts = [modelXbrl.factsByDimMemQname(hsAxis.aspect, qn)
                                                for qn in restrictions
                                                if isinstance(qn, QName) or qn is DEFAULT or qn is NONDEFAULT]
                        facts = facts & set.union(*aspectQualifiedFacts) if aspectQualifiedFacts else set()
                    else:
                        facts = facts & set(fact 
                                            for fact in facts
                                            for typedDimValue in hsAxis.restriction
                                            if typedDimTest(hsAxis.aspect, typedDimValue, fact))
            if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("Hyperspace %(variable)s: %(filter)s filter passes %(factCount)s facts"), 
                     modelObject=self.node, variable=str(self.node), filter=aspectStr(hsAxis.aspect), factCount=len(facts))
        if self.node.isClosed: # winnow out non-qualified dimension breakdowns
            facts = facts - set(fact
                                for fact in facts
                                if fact.dimAspects - self.aspectsQualified )
            if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("Hyperspace %(variable)s: closed selection filter passes %(factCount)s facts"), 
                     modelObject=self.node, variable=str(self.node), factCount=len(facts))
        return facts

def isPeriodEqualTo(fact, periodRestrictions):
    context = fact.context
    if context is not None:
        for period in periodRestrictions:
            if ((context.isInstantPeriod and context.instantDatetime == period) or
                (context.isStartEndPeriod and (context.startDatetime, context.endDatetime) == period) or
                (context.isForeverPeriod and period == (None, None))):
                return True
    return False
    
def isEntityIdentifierEqualTo(fact, entityIdentifierRestrictions):
    context = fact.context
    if context is not None:
        for entityIdentifier in entityIdentifierRestrictions:
            if fact.entityIdentifier == entityIdentifier:
                return True
    return False
    
def typedDimTest(aspect, value, fact):
    if fact.context is None:
        return False
    modelDim = fact.context.dimValue(aspect)
    if isinstance(modelDim, ModelDimensionValue):
        memElt = modelDim.typedMember
        if memElt.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true":
            return value is DEFAULT
        if value is NONDEFAULT:
            return True
        return memElt.elementText == value
    else:
        return value is DEFAULT
        
from .SphinxEvaluator import evaluate, factAspectValue
