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
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.FormulaEvaluator import implicitFilter, aspectsMatch
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT, NONDEFAULT
from arelle import XmlUtil
                                       
class SphinxContext:
    def __init__(self, sphinxProgs, modelXbrl=None):
        self.modelXbrl = modelXbrl  # the DTS and input instance (if any)
        self.sphinxProgs = sphinxProgs
        self.ruleBasePrecondition = None
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
        
    def close(self):
        if self.sCtx.hyperspaceBindings is self:
            self.sCtx.hyperspaceBindings = self.parentHyperspaceBindingSet
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
        
    def next(self):        
        # iterate hyperspace bindings
        if not self.hyperspaceBindings:
            raise StopIteration
        hsBsToReset = []
        for iHsB in range(len(self.hyperspaceBindings) - 1, -1, -1):
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
                 modelObject=self.node, variable=str(self.node), factCount=len(self.facts))
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
        if self.yieldedFact is not None:
            for aspect, priorFact in self.evaluationContributedUncoveredAspects.items():
                if priorFact == "none":
                    del uncoveredAspectFacts[aspect]
                else:
                    uncoveredAspectFacts[aspect] = priorFact
            self.evaluationContributedUncoveredAspects.clear()
        try:
            if not self.isWithRestrictionNode:
                self.yieldedFact = next(self.factIter)
            else:
                self.yieldedFactsPartition = next(self.factIter)
                for self.yieldedFact in self.yieldedFactsPartition:
                    break
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
        for hsAxis in orderedAxes:
            # value is an astHyperspaceAxis
            if hsAxis.whereExpr:
                whereMatchedFacts = set()
                for fact in facts:
                    if hsAxis.asVariableName:
                        self.sCtx.localVariables[hsAxis.asVariableName] = factAspectValue(fact, haAxis.aspect)
                    self.sCtx.localVariables["item"] = fact
                    if evaluate(hsAxis.whereExpr):
                        whereMatchedFacts.add(fact)
                facts = whereMatchedFacts
            elif hsAxis.aspect == Aspect.CONCEPT:
                facts = facts & set.union(*[modelXbrl.factsByQname[qn]
                                            for qn in hsAxis.restriction
                                            if isinstance(qn, QName)])
            elif isinstance(hsAxis.aspect, QName):
                if self.sCtx.dimensionIsExplicit.get(hsAxis.aspect):
                    # explicit dim facts (value None will match the default member)
                    facts = facts & set.union(*[modelXbrl.factsByDimMemQname(hsAxis.aspect, qn)
                                                for qn in hsAxis.restriction
                                                if isinstance(qn, QName)])
                else:
                    facts = facts & set(fact 
                                        for fact in facts
                                        for typedDimValue in hsAxis.restriction
                                        if typedDimTest(hsAxis.aspect, typedDimValue, fact))
            if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("Hyperspace %(variable)s: %(filter)s filter passes %(factCount)s facts"), 
                     modelObject=self.node, variable=str(self.node), filter=aspectStr(axis), factCount=len(facts))
        if self.node.isClosed: # winnow out non-qualified dimension breakdowns
            facts = facts - set(fact
                                for fact in facts
                                if fact.dimAspects - self.aspectsQualified )
            if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("Hyperspace %(variable)s: closed selection filter passes %(factCount)s facts"), 
                     modelObject=self.node, variable=str(self.node), factCount=len(facts))
        return facts

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
