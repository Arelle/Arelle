'''
cdrContext provides the validation and execution context for CDR Formula language expressions.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
'''

from collections import OrderedDict
from .cdrParser import astNode
from arelle.ModelFormulaObject import aspectModels, Aspect, aspectStr
from arelle.ModelInstanceObject import ModelFact, ModelDimensionValue
from arelle.FormulaEvaluator import implicitFilter, aspectsMatch
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT, NONDEFAULT
from arelle import XmlUtil
                                       
class  CdrContext:
    def __init__(self, cdrFormulas, orderedFormulaQnames, modelXbrl=None):
        self.modelXbrl = modelXbrl  # the DTS and input instance (if any)
        self.cdrFormulas = cdrFormulas
        self.orderedFormulaQnames = orderedFormulaQnames
        self.hyperspaceBindings = None
        if modelXbrl is not None:
            self.formulaOptions = modelXbrl.modelManager.formulaOptions
            self.defaultDimensionAspects = set(modelXbrl.qnameDimensionDefaults.keys())
        
    def close(self):
        # dereference grammar
        for modelFormula in self.cdrFormulas.items():
            for node in modelFormula.prog:
                if isinstance(node, astNode):
                    node.clear()
            modelFormula.prog.clear()
        self.__dict__.clear()  # delete local attributes
        
class EvaluationBindings:
    def __init__(self, cdrContext):
        self.sCtx = cdrContext
        self.parentHyperspaceBindings = cdrContext.evaluationBindings
        cdrContext.evaluationBindings = self
        self.evaluationBindings = []
        self.nodeBindings = {}
        self.withRestrictionBindings = []
        self.aspectBoundFacts = {}
        self.aggregationNode = None
        self.isValuesIteration = False
        
    def close(self):
        if self.sCtx.evaluationBindings is self:
            self.sCtx.evaluationBindings = self.parentEvaluationBindings
        for binding in self.evaluationBindings:
            binding.close()
        self.__dict__.clear() # dereference
        
    def nodeBinding(self, node, isWithRestrictionNode=False):
        if node in self.nodeBindings:
            return self.nodeBindings[node]
        if self.aggregationNode and self.aggregationNode not in self.nodeBindings and not self.isValuesIteration:
            agrgBalNode =  EvaluationBinding(self, node, isBalancingBinding=True)
            self.nodeBindings[self.aggregationNode] = agrgBalNode
        nodeBinding = EvaluationBinding(self, node, isWithRestrictionNode=isWithRestrictionNode)
        self.nodeBindings[node] = nodeBinding
        self.evaluationBindings.append(nodeBinding)
        return nodeBinding
        
    def forBinding(self, node):
        if node in self.nodeBindings:
            return self.nodeBindings[node]
        nodeBinding = ForBinding(self, node)
        self.nodeBindings[node] = nodeBinding
        self.evaluationBindings.append(nodeBinding)
        return nodeBinding
        
    def next(self, iterateAbove=-1, bindingsLen=-1):        
        # iterate evaluation bindings
        if not self.evaluationBindings:
            raise StopIteration
        evaluationBindingsToReset = []
        if bindingsLen == -1: 
            bindingsLen = len(self.evaluationBindings)
        for iB in range(bindingsLen - 1, iterateAbove, -1):
            evalBinding = self.evaluationBindings[iB]
            try:
                evalBinding.next()
                for evalBinding in evaluationBindingsToReset:
                    evalBinding.reset()
                return # hsB has another value to return
            except StopIteration:
                evaluationBindingsToReset.insert(0, evalBinding)  # reset after outer iterator advanced
        raise StopIteration # no more outermost loop of iteration
    
    @property
    def boundFacts(self):
        return [binding.yieldedFact
                for binding in self.evaluationBindings
                if isinstance(binding, EvaluationBinding) and
                not binding.fallenBack and binding.yieldedFact is not None]
        
class EvaluationBinding:
    def __init__(self, evaluationBindings, node, fallback=False, isWithRestrictionNode=False, isBalancingBinding=False):
        self.evaluationBindings = evaluationBindings
        self.sCtx = evaluationBindings.sCtx
        self.node = node
        self.isWithRestrictionNode = isWithRestrictionNode
        self.isBalancingBinding = isBalancingBinding
        self.isValuesIteration = evaluationBindings.isValuesIteration
        self.fallback = fallback
        self.aspectsQualified = set()
        self.aspectsDefined = set(aspectModels["dimensional"])
        if evaluationBindings.withRestrictionBindings:
            withAspectsQualified = evaluationBindings.withRestrictionBindings[-1].aspectsQualified
        else:
            withAspectsQualified = set()
        # axes from macros need to be expanded
        self.aspectAxisTuples = []
        self.axesAspects = set()
        for hsAxis in node.axes:
            if hsAxis.aspect: # no aspect if just a where clause
                aspect = evaluate(hsAxis.aspect, self.sCtx, value=True)
                if aspect not in self.aspectsDefined and not isinstance(aspect, QName):
                    raise CdrException(node, "cdr:aspectValue", 
                          _("Evaluation aspect indeterminate %(aspect)s"),
                          aspect=aspect)
                if isinstance(aspect, QName):
                    if aspect not in self.sCtx.dimensionIsExplicit: # probably dynamic macro aspect
                        concept = self.sCtx.modelXbrl.qnameConcepts.get(aspect)
                        if concept is None or not concept.isDimensionItem:
                            raise CdrException(node, "cdrBinding:axisNotDimension",
                                _("Axis aspect is not a dimension in the DTS %(aspect)s"),
                                aspect=aspect)
                        self.sCtx.dimensionIsExplicit[aspect] = concept.isExplicitDimension                        
                self.axesAspects.add(aspect) # resolved aspect value
                self.aspectAxisTuples.append( (aspect, hsAxis) )
        self.aspectsQualified = self.axesAspects | withAspectsQualified
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
    
    @property
    def var(self): # used in implicitFilter winnowing trace
        return []
    
    @property
    def qname(self): # used in implicitFilter winnowing trace
        return ''

    def __repr__(self):
        if self.fallenBack:
            return "fallen-back"
        if self.yieldedFact is not None:
            return self.yieldedFact.__repr__()
        return "none"
        
    def reset(self):
        # start with all facts
        if self.evaluationBindings.withRestrictionBindings:
            facts = self.evaluationBindings.withRestrictionBindings[-1].yieldedFactsPartition
        else:
            facts = self.sCtx.modelXbrl.nonNilFactsInInstance
        if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
            self.sCtx.modelXbrl.info("cdr:trace",
                 _("Evaluation %(variable)s binding: start with %(factCount)s facts"), 
                 sourceFileLine=self.node.sourceFileLine, variable=str(self.node), factCount=len(facts))
        # filter by binding aspects
        facts = self.filterFacts(facts)
        for fact in facts:
            if fact.isItem:
                self.aspectsDefined |= fact.context.dimAspects(self.sCtx.defaultDimensionAspects)
        self.unQualifiedAspects = self.aspectsDefined - self.aspectsQualified - {Aspect.DIMENSIONS}
        # implicitly filter by prior uncoveredAspectFacts
        if self.hyperspaceBindings.aspectBoundFacts and not self.isValuesIteration:
            facts = implicitFilter(self.sCtx, self, facts, self.unQualifiedAspects, self.hyperspaceBindings.aspectBoundFacts)
        if self.sCtx.formulaOptions.traceVariableFiltersResult:
            self.sCtx.modelXbrl.info("cdr:trace",
                 _("Evaluation %(variable)s binding: filters result %(factCount)s facts"), 
                 sourceFileLine=self.node.sourceFileLine, variable=str(self.node), factCount=len(facts))
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
        uncoveredAspectFacts = self.evaluationBindings.aspectBoundFacts
        if self.yieldedFact is not None and self.evaluationBindings.aggregationNode is None:
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
            if not self.isValuesIteration:
                for aspect in self.unQualifiedAspects:  # covered aspects may not be defined e.g., test 12062 v11, undefined aspect is a complemented aspect
                    if uncoveredAspectFacts.get(aspect) is None:
                        self.evaluationContributedUncoveredAspects[aspect] = uncoveredAspectFacts.get(aspect,"none")
                        uncoveredAspectFacts[aspect] = None if aspect in self.axesAspects else self.yieldedFact
            if self.sCtx.formulaOptions.traceVariableFiltersResult:
                self.sCtx.modelXbrl.info("cdr:trace",
                     _("Evaluation %(variable)s: bound value %(result)s"), 
                     sourceFileLine=self.node.sourceFileLine, variable=str(self.node), result=str(self.yieldedFact))
        except StopIteration:
            self.yieldedFact = None
            if self.isWithRestrictionNode:
                self.yieldedFactsPartition = []
            if self.fallback and not self.fallenBack:
                self.fallenBack = True
                if self.sCtx.formulaOptions.traceVariableExpressionResult:
                    self.sCtx.modelXbrl.info("cdr:trace",
                         _("Evaluation %(variable)s: fallbackValue result %(result)s"), 
                         sourceFileLine=self.node.sourceFileLine, variable=str(self.node), result=0)
            else:
                raise StopIteration

    def filterFacts(self, facts):
        modelXbrl = self.sCtx.modelXbrl
        # process with bindings and this node
        for i, aspectAxis in enumerate(self.aspectAxisTuples):
            aspect, hsAxis = aspectAxis
            # value is an astHyperspaceAxis
            if hsAxis.restriction:
                restriction = evaluate(hsAxis.restriction, self.sCtx, value=True)
                if aspect == Aspect.CONCEPT:
                    aspectQualifiedFacts = [modelXbrl.factsByQname[qn]
                                            for qn in restriction
                                            if isinstance(qn, QName)]
                    facts = facts & set.union(*aspectQualifiedFacts) if aspectQualifiedFacts else set()
                elif aspect == Aspect.PERIOD:
                    facts = set(f for f in facts if isPeriodEqualTo(f, restriction))
                elif aspect == Aspect.ENTITY_IDENTIFIER:
                    facts = set(f for f in facts if isEntityIdentifierEqualTo(f, restriction))
                elif isinstance(aspect, QName):
                    if self.sCtx.dimensionIsExplicit.get(aspect):
                        # explicit dim facts (value None will match the default member)
                        aspectQualifiedFacts = []
                        for qn in restriction:
                            if self.isBalancingBinding: # complement dimension for aggregation balancing binding
                                if isinstance(qn, QName) or qn is NONDEFAULT:
                                    qn = DEFAULT
                                else:
                                    qn = NONDEFAULT
                            if qn is NONE:
                                qn = DEFAULT
                            elif not (isinstance(qn, QName) or qn is DEFAULT or qn is NONDEFAULT):
                                continue
                            aspectQualifiedFacts.append(modelXbrl.factsByDimMemQname(aspect, qn))
                        facts = facts & set.union(*aspectQualifiedFacts) if aspectQualifiedFacts else set()
                    else:
                        facts = facts & set(fact 
                                            for fact in facts
                                            for typedDimValue in hsAxis.restriction
                                            if typedDimTest(aspect, typedDimValue, fact))
            if hsAxis.whereExpr and facts:  # process where against facts passing restriction
                whereMatchedFacts = set()
                asVars = set()
                for fact in facts:
                    for asAspectAxis in self.aspectAxisTuples[0:i+1]:
                        asAspect, asHsAxis = asAspectAxis
                        if asHsAxis.asVariableName:
                            self.sCtx.localVariables[asHsAxis.asVariableName] = factAspectValue(fact, asAspect)
                            asVars.add(asHsAxis.asVariableName)
                    self.sCtx.localVariables["item"] = fact
                    if evaluate(hsAxis.whereExpr, self.sCtx) ^ self.isBalancingBinding:
                        whereMatchedFacts.add(fact)
                del self.sCtx.localVariables["item"]
                for asVar in asVars:
                    del self.sCtx.localVariables[asVar]
                facts = whereMatchedFacts
            if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
                self.sCtx.modelXbrl.info("cdr:trace",
                     _("Evaluation %(variable)s: %(filter)s filter passes %(factCount)s facts"), 
                     sourceFileLine=self.node.sourceFileLine, variable=str(self.node), filter=aspectStr(aspect), factCount=len(facts))
        if self.node.isClosed: # winnow out non-qualified dimension breakdowns
            facts = facts - set(fact
                                for fact in facts
                                if fact.dimAspects - self.aspectsQualified )
            if self.sCtx.formulaOptions.traceVariableFilterWinnowing:
                self.sCtx.modelXbrl.info("cdr:trace",
                     _("Evaluation %(variable)s: closed selection filter passes %(factCount)s facts"), 
                     sourceFileLine=self.node.sourceFileLine, variable=str(self.node), factCount=len(facts))
        return facts

def isPeriodEqualTo(fact, periodRestriction):
    context = fact.context
    if context is not None:
        for period in periodRestriction:
            if ((context.isInstantPeriod and context.instantDatetime == period) or
                (context.isStartEndPeriod and (context.startDatetime, context.endDatetime) == period) or
                (context.isForeverPeriod and period == (None, None))):
                return True
    return False
    
def isEntityIdentifierEqualTo(fact, entityIdentifierRestriction):
    context = fact.context
    if context is not None:
        for entityIdentifier in entityIdentifierRestriction:
            if context.entityIdentifier == entityIdentifier:
                return True
    return False
    
def typedDimTest(aspect, value, fact):
    if fact.context is None:
        return False
    modelDim = fact.context.dimValue(aspect)
    if isinstance(modelDim, ModelDimensionValue):
        memElt = modelDim.typedMember
        if memElt is None or memElt.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true":
            return value is NONE or value is DEFAULT
        if value is NONDEFAULT:
            return True
        return memElt.textValue == value
    else:
        return value is NONE or value is DEFAULT
    
class ForBinding:
    def __init__(self, hyperspaceBindings, node):
        self.hyperspaceBindings = hyperspaceBindings
        self.sCtx = hyperspaceBindings.sCtx
        self.node = node
        self.collection = evaluate(node.collectionExpr, self.sCtx)
        self.reset()  # will raise StopIteration if no for items
        
    def close(self):
        self.__dict__.clear() # dereference
        
    @property
    def value(self):
        if self.yieldedValue is not None:
            return self.yieldedValue
        return None

    def __repr__(self):
        if self.yieldedValue is not None:
            return self.yieldedValue.__repr__()
        return "none"
        
    def reset(self):
        self.forIter = iter(self.collection)
        self.yieldedValue = None
        self.next()

        
    def next(self): # will raise StopIteration if no (more) facts or fallback
        try:
            self.yieldedValue = next(self.forIter)
            # set next value here as well as in for node, because may be cleared above context of for node
            self.sCtx.localVariables[self.node.name] = self.yieldedValue
            if self.sCtx.formulaOptions.traceVariableFiltersResult:
                self.sCtx.modelXbrl.info("sphinx:trace",
                     _("For loop %(variable)s: bound value %(result)s"), 
                     sourceFileLine=self.node.sourceFileLine, variable=str(self.node.name), result=str(self.yieldedValue))
        except StopIteration:
            if self.yieldedValue is not None:
                del self.sCtx.localVariables[self.node.name]
            self.yieldedValue = None
            raise StopIteration
        
from .cdrEvaluator import evaluate, factAspectValue, CdrException, NONE
