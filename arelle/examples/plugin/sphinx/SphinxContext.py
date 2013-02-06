'''
sphinxContext provides the validation and execution context for Sphinx language expressions.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

from .SphinxParser import astNode
from arelle.ModelFormulaObject import aspectModels, Aspect, aspectStr
from arelle.FormulaEvaluator import implicitFilter
from arelle.ModelValue import QName
                                       
class SphinxContext:
    def __init__(self, sphinxProgs, modelXbrl=None):
        self.modelXbrl = modelXbrl  # the DTS and input instance (if any)
        self.sphinxProgs = sphinxProgs
        self.ruleBasePrecondition = None
        self.rules = []
        self.transformQnames = {}
        self.transformNamespaces = {}
        self.constants = {}
        self.preconditions = {}
        self.localVariables = {}
        self.tags = {}
        self.hyperspaceBindings = None
        if modelXbrl is not None:
            self.sphinxOptions = modelXbrl.modelManager.formulaOptions
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
        self.hyperspaceBindings = []
        self.nodeBindings = {}
        self.aspectBoundFacts = {}
        
    def close(self):
        if self.sCtx == self:
            self.sCtx = self.parentHyperspaceBindingSet
        for hsBinding in self.hyperspaceBindings:
            hsBinding.close()
        self.__dict__.clear() # dereference
        
    def nodeBinding(self, node, bindAggregate):
        if node in self.nodeBindings:
            return self.nodeBindings[node]
        nodeBinding = HyperspaceBinding(self.sCtx, node)
        self.nodeBindings[node] = nodeBinding
        return nodeBinding
        
    def next(self):        
        # iterate hyperspace bindings
        if not self.hyperspaceBindings:
            raise StopIteration
        for iHsB in range(len(self.hyperspaceBindings) - 1, 0, -1):
            hsB = self.hyperspaceBindings[iHsB]
            try:
                hsB.next()
                return # hsB has another value to return
            except StopIteration:
                hsB.reset() # may raise StopIteration if nothing to iterate
        raise StopIteration # no more outermost loop of iteration
        
class HyperspaceBinding:
    def __init__(self, sphinxContext, node, fallback=False):
        self.sCtx = sphinxContext
        self.node = node
        self.fallback = fallback
        self.aspectsQualified = set()
        self.varName = None
        self.tagName = None
        self.aspectsDefined = set(aspectModels["dimensional"])
        self.aspectsQualified.clear()
        for aspect in self.node.axes.keys():
            self.aspectsQualified |= aspect
        self.unQualifiedAspects = self.aspectsDefined = self.aspectsQualified
        self.reset()  # will raise StopIteration if no facts or fallback
        
    def close(self):
        self.__dict__.clear() # dereference
        
    def reset(self):
        if self.sCtx.sphinxOptions.traceVariableFilterWinnowing:
            self.sCtx.modelXbrl.info("sphinx:trace",
                 _("Hyperspace %(variable)s binding: start with %(factCount)s facts"), 
                 modelObject=self.node, variable=str(self.node), factCount=len(self.facts))
        # start with all facts
        facts = self.sCtx.modelXbrl.nonNilFactsInInstance
        # filter by hyperspace aspects
        facts = self.filterFacts(facts)
        # implicitly filter by prior uncoveredAspectFacts
        facts = implicitFilter(self.sCtx, self, facts, self.unQualifiedAspects, self.hyperspaceBindings.aspectBoundFacts)
        for fact in facts:
            if fact.isItem:
                self.aspectsDefined |= fact.context.dimAspects(self.sCtx.defaultDimensionAspects)
        if self.sCtx.sphinxOptions.traceVariableFiltersResult:
            self.sCtx.modelXbrl.info("sphinx:trace",
                 _("Hyperspace %(variable)s binding: filters result %(factCount)s facts"), 
                 modelObject=self.node, variable=str(self.node), factCount=len(self.facts))
        self.facts = facts
        self.factIter = iter(self.facts)
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
        try:
            self.yieldedFact = next(self.factIter)
            self.evaluationContributedUncoveredAspects = {}
            for aspect in self.aspectsDefined | self.aspectsQualified:  # covered aspects may not be defined e.g., test 12062 v11, undefined aspect is a complemented aspect
                if uncoveredAspectFacts.get(aspect) is None:
                    self.evaluationContributedUncoveredAspects[aspect] = uncoveredAspectFacts.get(aspect,"none")
                    uncoveredAspectFacts[aspect] = None if aspect in self.node.axes else self.yieldedFact
            if self.sCtx.sphinxOptions.traceVariableFiltersResult:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("Hyperspace %(variable)s: bound value %(result)s"), 
                     modelObject=self.node, variable=str(self.node), result=str(self.yieldedFact))
        except StopIteration:
            self.yieldedFact = None
            if self.fallback and not self.fallenBack:
                self.fallenBack = True
                if self.sCtx.sphinxOptions.traceVariableExpressionResult:
                    self.sCtx.modelXbrl.info("sphinx:trace",
                         _("Hyperspace %(variable)s: fallbackValue result %(result)s"), 
                         modelObject=self.node, variable=str(self.node), result=0)
            else:
                raise StopIteration

    def filterFacts(self, facts):
        modelXbrl = self.sCtx.modelXbrl
        orderedAxes = []
        for axisValue in self.node.axes.items():
            if axisValue[0] == Aspect.CONCEPT:
                orderedAxes.insert(0, axisValue)
            else:
                orderedAxes.append(axisValue)
        for axis,value in orderedAxes:
            if axis == Aspect.CONCEPT:
                facts = facts & modelXbrl.factsByQname[value]
            elif isinstance(axis, QName):
                # explicit dim facts
                facts = facts & modelXbrl.factsByDimMemQname(axis, value)
            if self.sCtx.sphinxOptions.traceVariableFilterWinnowing:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("Hyperspace %(variable)s: %(filter)s filter passes %(factCount)s facts"), 
                     modelObject=self.node, variable=str(self.node), filter=aspectStr(axis), factCount=len(facts))
        return facts

