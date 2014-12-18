'''
Created on Jan 9, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XPathContext, XbrlConst, XmlUtil, XbrlUtil, XmlValidate)
from arelle.FunctionXs import xsString
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import (aspectModels, Aspect, aspectModelAspect,
                                 ModelFormula, ModelTuple, ModelExistenceAssertion,
                                 ModelValueAssertion,
                                 ModelFactVariable, ModelGeneralVariable, ModelVariable,
                                 ModelParameter, ModelFilter, ModelAspectCover, ModelBooleanFilter)
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.ModelValue import (QName)
import datetime, time, logging, re
from decimal import Decimal
from math import log10, isnan, isinf, fabs
from arelle.Locale import format_string
from collections import defaultdict
ModelDimensionValue = None

expressionVariablesPattern = re.compile(r"([^$]*)([$]\w[\w:.-]*)([^$]*)")

def outputEvaluatedValues(xpCtx, varSet, result, traceOf=''):
    if xpCtx.formulaOptions.traceVariableSetExpressionInError:
        expression = varSet.expression
        xpCtx.modelXbrl.info("formula:" + (varSet.id or varSet.xlinkLabel or _("unlabeled variableSet")),
             _("%(variableSetType)s %(xlinkLabel)s{0} \n    Expression: %(expression)s \n    Evaluated: %(evaluatedExpression)s \n    Result: %(result)s"),
             modelObject=varSet, variableSetType=traceOf, xlinkLabel=varSet.xlinkLabel, 
             result=result, expression=expression,
             evaluatedExpression=''.join(xpCtx.traceEffectiveVariableValue(varSet,expr)
                                         for grp in expressionVariablesPattern.findall(expression)
                                         for expr in grp))

def evaluate(xpCtx, varSet, variablesInScope=False, uncoveredAspectFacts=None):
    # for each dependent variable, find bindings
    if variablesInScope:
        stackedEvaluations = (xpCtx.evaluations, xpCtx.evaluationHashDicts)
    else:
        xpCtx.varBindings = {}
        uncoveredAspectFacts = {}
    xpCtx.evaluations = []  # list of evaluations 
    xpCtx.evaluationHashDicts = [] # hash indexs of evaluations
    try:
        xpCtx.variableSet = varSet
        if isinstance(varSet, ModelExistenceAssertion):
            varSet.evaluationsCount = 0
        if xpCtx.formulaOptions.timeVariableSetEvaluation:
            varSet.timeEvaluationStarted = timeEvaluationsStarted = time.time()
        varSet.evaluationNumber = 0
        initialTraceCount = xpCtx.modelXbrl.logCount.get(logging.getLevelName('INFO'), 0)
        evaluateVar(xpCtx, varSet, 0, {}, uncoveredAspectFacts)
        if isinstance(varSet, ModelExistenceAssertion):
            prog = varSet.testProg
            if prog:
                assertionParamQnames = []  # set and then remove assertion variable quames
                for varRel in varSet.orderedVariableRelationships:
                    varQname = varRel.variableQname
                    var = varRel.toModelObject
                    if isinstance(var, ModelParameter) and varQname not in xpCtx.inScopeVars:
                        assertionParamQnames.append(varQname)
                        xpCtx.inScopeVars[varQname] = xpCtx.inScopeVars.get(var.parameterQname)
                result = xpCtx.evaluateBooleanValue(prog, contextItem=varSet.evaluationsCount)
                for varQname in assertionParamQnames:
                    xpCtx.inScopeVars.pop(varQname)
            else:
                result = varSet.evaluationsCount > 0
            if result: varSet.countSatisfied += 1
            else: varSet.countNotSatisfied += 1
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Existence Assertion %(xlinkLabel)s \nResult: %(result)s"), 
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel, result=result)
            msg = varSet.message(result)
            if msg is not None:
                xpCtx.inScopeVars[XbrlConst.qnEaTestExpression] = varSet.test
                xpCtx.modelXbrl.info("message:" + (varSet.id or varSet.xlinkLabel or _("unlabeled variableSet")),
                    msg.evaluate(xpCtx),
                    modelObject=varSet,
                    messageCodes=("message:{variableSetID|xlinkLabel}"))
                xpCtx.inScopeVars.pop(XbrlConst.qnEaTestExpression)
                outputEvaluatedValues(xpCtx, varSet, result)
            elif varSet.countNotSatisfied > 0:
                # Assume that there is a problem in the taxonomy (i. e EBA COREP/FINREP prior to 2014/07/31).
                # Assume that a message simplified message should be displayed if there are some rules that are not
                # satisfied.
                xpCtx.modelXbrl.info("rule not satisfied:", varSet.logLabel())
                outputEvaluatedValues(xpCtx, varSet, result)
        if xpCtx.formulaOptions.traceVariableSetExpressionResult and initialTraceCount == xpCtx.modelXbrl.logCount.get(logging._checkLevel('INFO'), 0):
            xpCtx.modelXbrl.info("formula:trace",
                 _("Variable set %(xlinkLabel)s had no xpCtx.evaluations"),
                 modelObject=varSet, xlinkLabel=varSet.xlinkLabel)
        if xpCtx.formulaOptions.timeVariableSetEvaluation:
            xpCtx.modelXbrl.info("formula:time",
                 _("Variable set %(xlinkLabel)s time for %(count)s evaluations: %(time)s"), 
                 modelObject=varSet, xlinkLabel=varSet.xlinkLabel, count=varSet.evaluationNumber,
                 time=format_string(xpCtx.modelXbrl.modelManager.locale, "%.3f", time.time() - timeEvaluationsStarted))
        xpCtx.variableSet = None
    except XPathContext.XPathException as err:
        xpCtx.modelXbrl.error(err.code,
                 _("Variable set %(logLabel)s:\nException: %(error)s"), 
                 modelObject=varSet, logLabel=varSet.logLabel(), error=err.message)
        xpCtx.variableSet = None
    if xpCtx.formulaOptions.traceVariableSetExpressionResult:
        xpCtx.modelXbrl.info("formula:trace",
                             _("Variable set %(xlinkLabel)s evaluations: %(evaluations)s x %(variables)s"),
                             modelObject=varSet, xlinkLabel=varSet.xlinkLabel,
                             evaluations=len(xpCtx.evaluations), 
                             variables=max(len(e) for e in xpCtx.evaluations) if xpCtx.evaluations else 0)
    del xpCtx.evaluations[:]  # dereference
    del xpCtx.evaluationHashDicts[:]
    if variablesInScope:
        xpCtx.evaluations, xpCtx.evaluationHashDicts = stackedEvaluations
    else:
        for vb in xpCtx.varBindings.values():
            vb.close()  # dereference
        xpCtx.varBindings.clear() # dereference
        uncoveredAspectFacts.clear()    # dereference
        pass     

def evaluateVar(xpCtx, varSet, varIndex, cachedFilteredFacts, uncoveredAspectFacts):
    if varIndex == len(varSet.orderedVariableRelationships):
        # check if all fact vars are fallen back
        anyFactVar = False; anyBoundFactVar = False
        for vb in xpCtx.varBindings.values():
            if vb.isFactVar:
                anyFactVar = True
                if not vb.isFallback: anyBoundFactVar = True 
        if xpCtx.varBindings and anyFactVar and not anyBoundFactVar:
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Variable set %(xlinkLabel)s skipped evaluation, all fact variables have fallen back"),
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel)
            return
        # record completed evaluation, for fallback blocking purposes
        fbVars = set(vb.qname for vb in xpCtx.varBindings.values() if vb.isFallback)
        thisEvaluation = tuple(vb.matchableBoundFact(fbVars) for vb in xpCtx.varBindings.values())
        if evaluationIsUnnecessary(thisEvaluation, xpCtx.evaluationHashDicts, xpCtx.evaluations):
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                    _("Variable set %(xlinkLabel)s skipped non-different or fallback evaluation, duplicates another evaluation"),
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel)
            varSet.evaluationNumber += 1
            if xpCtx.formulaOptions.timeVariableSetEvaluation:
                now = time.time()
                xpCtx.modelXbrl.info("formula:time",
                     _("Variable set %(xlinkLabel)s skipped evaluation %(count)s: %(time)s sec"), 
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel, count=varSet.evaluationNumber,
                     time=format_string(xpCtx.modelXbrl.modelManager.locale, "%.3f", now - varSet.timeEvaluationStarted))
                varSet.timeEvaluationStarted = now
            if xpCtx.isRunTimeExceeded: raise XPathContext.RunTimeExceededException()
            xpCtx.modelXbrl.profileActivity("...   evaluation {0} (skipped)".format(varSet.evaluationNumber), minTimeToShow=10.0)
            return
        xpCtx.modelXbrl.profileActivity("...   evaluation {0}".format(varSet.evaluationNumber), minTimeToShow=10.0)
        for i, fb in enumerate(thisEvaluation):
            while i >= len(xpCtx.evaluationHashDicts): xpCtx.evaluationHashDicts.append(defaultdict(set))
            xpCtx.evaluationHashDicts[i][hash(fb)].add(len(xpCtx.evaluations))  # hash and eval index        
        xpCtx.evaluations.append(thisEvaluation)  # complete evaluations tuple
        # evaluate preconditions
        for precondition in varSet.preconditions:
            result = precondition.evalTest(xpCtx)
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Variable set %(xlinkLabel)s \nPrecondition %(precondition)s \nResult: %(result)s"), 
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel, precondition=precondition.xlinkLabel, result=result)
            if not result: # precondition blocks evaluation
                if xpCtx.formulaOptions.timeVariableSetEvaluation:
                    varSet.evaluationNumber += 1
                    now = time.time()
                    xpCtx.modelXbrl.info("formula:time",
                         _("Variable set %(xlinkLabel)s precondition blocked evaluation %(count)s: %(time)s sec"), 
                         modelObject=varSet, xlinkLabel=varSet.xlinkLabel, count=varSet.evaluationNumber,
                         time=format_string(xpCtx.modelXbrl.modelManager.locale, "%.3f", now - varSet.timeEvaluationStarted))
                    varSet.timeEvaluationStarted = now
                if xpCtx.isRunTimeExceeded: raise XPathContext.RunTimeExceededException()
                return
            
        # evaluate variable set
        if isinstance(varSet, ModelExistenceAssertion):
            varSet.evaluationsCount += 1
        else:
            if isinstance(varSet, ModelTuple):
                result = "(tuple)"
                traceOf = "Tuple"
            elif isinstance(varSet, ModelFormula):
                result = xpCtx.evaluate(varSet.valueProg)
                traceOf = "Formula"
            elif isinstance(varSet, ModelValueAssertion):
                result = xpCtx.evaluateBooleanValue(varSet.testProg)
                if result: varSet.countSatisfied += 1
                else: varSet.countNotSatisfied += 1
                msg = varSet.message(result)
                traceOf = "Value Assertion"
                if msg is not None:
                    xpCtx.inScopeVars[XbrlConst.qnVaTestExpression] = varSet.test
                    xpCtx.modelXbrl.info("message:" + (varSet.id or varSet.xlinkLabel or  _("unlabeled variableSet")),
                        msg.evaluate(xpCtx),
                        modelObject=varSet,
                        label=varSet.logLabel(),
                        messageCodes=("message:{variableSetID|xlinkLabel}"))
                    xpCtx.inScopeVars.pop(XbrlConst.qnVaTestExpression)
                    outputEvaluatedValues(xpCtx, varSet, result, traceOf)
                elif varSet.countNotSatisfied > 0:
                    # Assume that there is a problem in the taxonomy (i. e EBA COREP/FINREP prior to 2014/07/31).
                    # Assume that a message simplified message should be displayed if there are some rules that are not
                    # satisfied.
                    xpCtx.modelXbrl.info("evaluation not satisfied:", varSet.logLabel())
                    outputEvaluatedValues(xpCtx, varSet, result, traceOf)
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                label = varSet.logLabel()
                expression = varSet.expression
                xpCtx.modelXbrl.info("formula:trace",
                     _("%(variableSetType)s %(xlinkLabel)s{0} \nExpression: %(expression)s \nEvaluated: %(evaluatedExpression)s \nResult: %(result)s")
                     .format(" \n%(label)s" if label else ""),
                     modelObject=varSet, variableSetType=traceOf, xlinkLabel=varSet.xlinkLabel, 
                     label=label, result=result, expression=expression,
                     evaluatedExpression=''.join(xpCtx.traceEffectiveVariableValue(varSet,expr)
                                                 for grp in expressionVariablesPattern.findall(expression)
                                                 for expr in grp))
            if isinstance(varSet, ModelFormula) and varSet.outputInstanceQname in xpCtx.inScopeVars:
                newFact = produceOutputFact(xpCtx, varSet, result)
            else:
                newFact = None
            if varSet.hasConsistencyAssertion:
                from arelle import FormulaConsisAsser
                FormulaConsisAsser.evaluate(xpCtx, varSet, newFact)
                
            if xpCtx.formulaOptions.timeVariableSetEvaluation:
                varSet.evaluationNumber += 1
                now = time.time()
                xpCtx.modelXbrl.info("formula:time",
                     _("Variable set %(xlinkLabel)s completed evaluation %(count)s: %(time)s sec"), 
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel, count=varSet.evaluationNumber,
                     time=format_string(xpCtx.modelXbrl.modelManager.locale, "%.3f", now - varSet.timeEvaluationStarted))
                varSet.timeEvaluationStarted = now
            if xpCtx.isRunTimeExceeded: raise XPathContext.RunTimeExceededException()
                
            # do dependent variable scope relationships
            for varScopeRel in xpCtx.modelXbrl.relationshipSet(XbrlConst.variablesScope).fromModelObject(varSet):
                try:
                    resultQname = varScopeRel.variableQname
                    if resultQname:
                        overriddenInScopeVar = xpCtx.inScopeVars.get(resultQname)
                        xpCtx.inScopeVars[resultQname] = result
                        vb = VariableBinding(xpCtx, varScopeRel)
                        vb.yieldedEvaluation = result
                        vb.yieldedFact = newFact
                        overriddenVarBinding = xpCtx.varBindings.get(resultQname)            
                        xpCtx.varBindings[resultQname] = vb
                    evaluate(xpCtx, varScopeRel.toModelObject, True, uncoveredAspectFacts)
                    if resultQname:
                        xpCtx.inScopeVars.pop(resultQname)
                        if overriddenInScopeVar is not None:  # restore overridden value if there was one
                            xpCtx.inScopeVars[resultQname] = overriddenInScopeVar
                        xpCtx.varBindings.pop(resultQname)
                        if overriddenVarBinding is not None:
                            xpCtx.varBindings[resultQname] = overriddenVarBinding
                        vb.close() # dereference
                except XPathContext.XPathException as err:
                    xpCtx.modelXbrl.error(err.code,
                        _("Variable set chained in scope of variable set %(variableSet)s \nException: \n%(error)s"), 
                        modelObject=varScopeRel.toModelObject, variableSet=varSet.logLabel(), error=err.message)
            
    else:
        # produce variable bindings
        varRel = varSet.orderedVariableRelationships[varIndex]
        varQname = varRel.variableQname
        vb = VariableBinding(xpCtx, varRel)
        var = vb.var
        if vb.isFactVar:
            vb.aspectsDefined = set(aspectModels[varSet.aspectModel])  # has to be a mutable set
            vb.values = None
            varHasNoVariableDependencies = var.hasNoVariableDependencies
            varHasNilFacts = var.nils == "true"
            if varHasNoVariableDependencies and varQname in cachedFilteredFacts:
                facts, vb.aspectsDefined, vb.aspectsCovered = cachedFilteredFacts[varQname]
                if xpCtx.formulaOptions.traceVariableFilterWinnowing:
                    xpCtx.modelXbrl.info("formula:trace",
                         _("Fact Variable %(variable)s: start with %(factCount)s facts previously cached after explicit filters"), 
                         modelObject=var, variable=varQname, factCount=len(facts))
            else:
                if var.fromInstanceQnames:
                    groupFilteredFactsKey = "grp:" + str(varQname) # multi instance vars or  non-var-dependent variables
                elif varHasNilFacts:
                    groupFilteredFactsKey = "grp:stdInstWithNils"
                else:
                    groupFilteredFactsKey = "grp:stdInstNonNil"
                if groupFilteredFactsKey in cachedFilteredFacts:
                    facts = cachedFilteredFacts[groupFilteredFactsKey]
                    if xpCtx.formulaOptions.traceVariableFilterWinnowing:
                        xpCtx.modelXbrl.info("formula:trace",
                             _("Fact Variable %(variable)s: start with %(factCount)s facts previously cached before variable filters"), 
                             modelObject=var, variable=varQname, factCount=len(facts))
                else:
                    facts = set.union(*[(inst.factsInInstance if varHasNilFacts else inst.nonNilFactsInInstance)
                                        for inst in vb.instances])
                    if xpCtx.formulaOptions.traceVariableFilterWinnowing:
                        xpCtx.modelXbrl.info("formula:trace",
                             _("Fact Variable %(variable)s filtering: start with %(factCount)s facts"), 
                             modelObject=var, variable=varQname, factCount=len(facts))
                    facts = filterFacts(xpCtx, vb, facts, varSet.groupFilterRelationships, "group")
                    vb.aspectsCovered.clear()  # group boolean sub-filters may have covered aspects
                    cachedFilteredFacts[groupFilteredFactsKey] = facts
                facts = filterFacts(xpCtx, vb, facts, var.filterRelationships, None) # also finds covered aspects (except aspect cover filter dims, not known until after this complete pass)
                # adding dim aspects must be done after explicit filterin
                for fact in facts:
                    if fact.isItem and fact.context is not None:
                        vb.aspectsDefined |= fact.context.dimAspects(xpCtx.defaultDimensionAspects)
                coverAspectCoverFilterDims(xpCtx, vb, var.filterRelationships) # filters need to know what dims are covered
                if varHasNoVariableDependencies:
                    cachedFilteredFacts[varQname] = (facts, vb.aspectsDefined, vb.aspectsCovered)
            considerFallback = bool(var.fallbackValueProg)
            if varSet.implicitFiltering == "true":
                if any((_vb.isFactVar and not _vb.isFallback) for _vb in xpCtx.varBindings.values()):
                    factCount = len(facts)
                    # uncovered aspects of the prior variable bindings may include aspects not in current variable binding
                    uncoveredAspects = (vb.aspectsDefined | _DICT_SET(uncoveredAspectFacts.keys())) - vb.aspectsCovered - {Aspect.DIMENSIONS}
                    facts = implicitFilter(xpCtx, vb, facts, uncoveredAspects, uncoveredAspectFacts)
                    if (considerFallback and varHasNoVariableDependencies and 
                        factCount and
                        factCount - len(facts) == 0 and
                        len(xpCtx.varBindings) > 1 and
                        all((len(_vb.aspectsDefined) == len(vb.aspectsDefined) for _vb in xpCtx.varBindings.values()))):
                        considerFallback = False
            vb.facts = facts
            if xpCtx.formulaOptions.traceVariableFiltersResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Fact Variable %(variable)s: filters result %(result)s"), 
                     modelObject=var, variable=varQname, result=str(vb.facts))
            if considerFallback:
                vb.values = xpCtx.evaluate(var.fallbackValueProg)
                if xpCtx.formulaOptions.traceVariableExpressionResult:
                    xpCtx.modelXbrl.info("formula:trace",
                         _("Fact Variable %(variable)s: fallbackValue result %(result)s"), 
                         modelObject=var, variable=varQname, result=str(vb.values))
        elif vb.isGeneralVar: # general variable
            if var.fromInstanceQnames:
                contextItem = [inst.modelDocument.xmlRootElement 
                               for qn in var.fromInstanceQnames 
                               for instSeq in (xpCtx.inScopeVars[qn],)
                               for inst in (instSeq if isinstance(instSeq,(list,tuple)) else (instSeq,)) 
                               ] 
            else:
                contextItem = xpCtx.modelXbrl.modelDocument.xmlRootElement  # default is standard input instance
            vb.values = xpCtx.flattenSequence( xpCtx.evaluate(var.selectProg, contextItem=contextItem) )
            if xpCtx.formulaOptions.traceVariableExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("General Variable %(variable)s: select result %(result)s"),
                     modelObject=var, variable=varQname, result=str(vb.values))
        elif vb.isParameter:
            vb.parameterValue = xpCtx.inScopeVars.get(var.parameterQname)
        # recurse partitions, preserve overlaid var bindings and inScopeVars
        overriddenVarBinding = xpCtx.varBindings.get(varQname)            
        xpCtx.varBindings[varQname] = vb
        for evaluationResult in vb.evaluationResults:
            overriddenInScopeVar = xpCtx.inScopeVars.get(varQname)
            xpCtx.inScopeVars[varQname] = evaluationResult
            evaluationContributedUncoveredAspects = {}
            if vb.isFactVar and not vb.isFallback:
                # cache uncoveredAspect facts for nested evaluations
                for aspect in vb.aspectsDefined | vb.aspectsCovered:  # covered aspects may not be defined e.g., test 12062 v11, undefined aspect is a complemented aspect
                    if uncoveredAspectFacts.get(aspect) is None:
                        evaluationContributedUncoveredAspects[aspect] = uncoveredAspectFacts.get(aspect,"none")
                        uncoveredAspectFacts[aspect] = None if vb.hasAspectValueCovered(aspect) else vb.yieldedFact
            if xpCtx.formulaOptions.traceVariableFiltersResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("%(variableType)s %(variable)s: bound value %(result)s"), 
                     modelObject=var, variableType=vb.resourceElementName, variable=varQname, result=str(evaluationResult))
            if xpCtx.isRunTimeExceeded: raise XPathContext.RunTimeExceededException()
            evaluateVar(xpCtx, varSet, varIndex + 1, cachedFilteredFacts, uncoveredAspectFacts)
            xpCtx.inScopeVars.pop(varQname)
            if overriddenInScopeVar is not None:  # restore overridden value if there was one
                xpCtx.inScopeVars[varQname] = overriddenInScopeVar
            for aspect, priorFact in evaluationContributedUncoveredAspects.items():
                if priorFact == "none":
                    del uncoveredAspectFacts[aspect]
                else:
                    uncoveredAspectFacts[aspect] = priorFact
        xpCtx.varBindings.pop(varQname)
        vb.close() # dereference
        if overriddenVarBinding is not None:
            xpCtx.varBindings[varQname] = overriddenVarBinding
        
def filterFacts(xpCtx, vb, facts, filterRelationships, filterType):
    typeLbl = filterType + " " if filterType else ""
    orFilter = filterType == "or"
    groupFilter = filterType == "group"
    if orFilter: 
        factSet = set()
    for varFilterRel in filterRelationships:
        _filter = varFilterRel.toModelObject
        if isinstance(_filter,ModelFilter):  # relationship not constrained to real filters
            result = _filter.filter(xpCtx, vb, facts, varFilterRel.isComplemented)
            if xpCtx.formulaOptions.traceVariableFilterWinnowing:
                xpCtx.modelXbrl.info("formula:trace",
                    _("Fact Variable %(variable)s %(filterType)s %(filter)s filter %(xlinkLabel)s passes %(factCount)s facts"), 
                    modelObject=vb.var, variable=vb.qname,
                    filterType=typeLbl, filter=_filter.localName, xlinkLabel=_filter.xlinkLabel, factCount=len(result)),
            if orFilter: 
                factSet |= result
            else: 
                facts = result
            if not groupFilter and varFilterRel.isCovered:  # block boolean group filters that have cover in subnetworks
                vb.aspectsCovered |= _filter.aspectsCovered(vb)
    if orFilter: 
        return factSet
    else: 
        return facts
            
def coverAspectCoverFilterDims(xpCtx, vb, filterRelationships):
    for varFilterRel in filterRelationships:
        _filter = varFilterRel.toModelObject
        if isinstance(_filter,ModelAspectCover):  # relationship not constrained to real filters
            if varFilterRel.isCovered:
                vb.aspectsCovered |= _filter.dimAspectsCovered(vb)
        elif isinstance(_filter,ModelBooleanFilter) and varFilterRel.isCovered:
            coverAspectCoverFilterDims(xpCtx, vb, _filter.filterRelationships)
            
def implicitFilter(xpCtx, vb, facts, aspects, uncoveredAspectFacts):
    if xpCtx.formulaOptions.traceVariableFilterWinnowing:  # trace shows by aspect by bound variable match    
        for aspect in aspects:
            if uncoveredAspectFacts.get(aspect, "none") is not None:
                facts = [fact 
                         for fact in facts 
                         if aspectMatches(xpCtx, uncoveredAspectFacts.get(aspect), fact, aspect)]
                a = str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect]
                xpCtx.modelXbrl.info("formula:trace",
                    _("Fact Variable %(variable)s implicit filter %(aspect)s passes %(factCount)s facts"), 
                    modelObject=vb.var, variable=vb.qname, aspect=a, factCount=len(facts))
                if len(facts) == 0: break
    else: 
        testableAspectFacts = [(aspect, uncoveredAspectFacts.get(aspect)) 
                               for aspect in aspects 
                               if uncoveredAspectFacts.get(aspect, "none") is not None]
        #testableAspectFacts = [(aspect, fact) 
        #                       for aspect, fact in uncoveredAspectFacts.items()
        #                       if not vb.hasAspectValueCovered(aspect)]
        if testableAspectFacts:
            # not tracing, do bulk aspect filtering
            facts = [fact
                     for fact in facts
                     if all(aspectMatches(xpCtx, uncoveredAspectFact, fact, aspect)
                            for (aspect, uncoveredAspectFact) in testableAspectFacts)]
    return facts
    
def aspectsMatch(xpCtx, fact1, fact2, aspects):
    return all(aspectMatches(xpCtx, fact1, fact2, aspect) for aspect in aspects)

def aspectMatches(xpCtx, fact1, fact2, aspect):
    if fact1 is None:  # fallback (atomic) never matches any aspect
        return False
    if aspect == 1: # Aspect.LOCATION:
        return (fact2 is not None and
                fact1.modelXbrl != fact2.modelXbrl or # test deemed true for multi-instance comparisons
                fact1.getparent() == fact2.getparent())
    elif aspect == 2: # Aspect.CONCEPT:
        return fact2 is not None and fact1.qname == fact2.qname
    elif fact1.isTuple or fact2.isTuple:
        return fact1.isTuple and fact2.isTuple # only match the aspects both facts have
    elif aspect == 5: # Aspect.UNIT:
        u1 = fact1.unit
        u2 = fact2.unit if fact2 is not None else None
        if u1 is not None:
            return u1.isEqualTo(u2)
        return u2 is None
    else:
        # rest of comparisons are for context
        c1 = fact1.context
        c2 = fact2.context if fact2 is not None else None
        if c1 is None or (c2 is None and aspect != 10):
            return False # something wrong, must be a context
        if c1 is c2:
            return True # same context
        if aspect == 4: # Aspect.PERIOD:
            return c1.isPeriodEqualTo(c2)
        if aspect == 3: # Aspect.ENTITY_IDENTIFIER:
            return c1.isEntityIdentifierEqualTo(c2)
        if aspect == 6: # Aspect.COMPLETE_SEGMENT:
            return XbrlUtil.nodesCorrespond(fact1.modelXbrl, c1.segment, c2.segment, dts2=fact2.modelXbrl) 
        elif aspect == 7: # Aspect.COMPLETE_SCENARIO:
            return XbrlUtil.nodesCorrespond(fact1.modelXbrl, c1.scenario, c2.scenario, dts2=fact2.modelXbrl) 
        elif aspect == 8 or aspect == 9: # aspect in (Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
            nXs1 = c1.nonDimValues(aspect)
            nXs2 = c2.nonDimValues(aspect)
            lXs1 = len(nXs1)
            lXs2 = len(nXs2)
            if lXs1 != lXs2:
                return False
            elif lXs1 > 0:
                for i in range(lXs1):
                    if not XbrlUtil.nodesCorrespond(fact1.modelXbrl, nXs1[i], nXs2[i], dts2=fact2.modelXbrl): 
                        return False
            return True
        elif aspect == 10: # Aspect.DIMENSIONS:
            ''' (no implicit filtering on ALL dimensions for now)
            dimQnames1 = fact1.context.dimAspects
            dimQnames2 = fact2.context.dimAspects
            if len(dimQnames1 ^ dimQnames2):  # dims not in both
                matches = False
            else:
                for dimQname1 in dimQnames1:
                    if dimQname1 not in dimQnames2 or \
                       not aspectMatches(fact1, fact2, dimQname1):
                        matches = False
                        break
            '''
        elif isinstance(aspect, QName):
            global ModelDimensionValue
            if ModelDimensionValue is None:
                from arelle.ModelInstanceObject import ModelDimensionValue
            dimValue1 = c1.dimValue(aspect)
            if c2 is None:
                if dimValue1 is None: # neither fact nor matching facts have this dimension aspect
                    return True
                return False
            dimValue2 = c2.dimValue(aspect)
            if isinstance(dimValue1, ModelDimensionValue):
                if dimValue1.isExplicit: 
                    if isinstance(dimValue2, QName):
                        if dimValue1.memberQname != dimValue2:
                            return False
                    elif isinstance(dimValue2, (ModelDimensionValue,DimValuePrototype)):
                        if dimValue2.isTyped:
                            return False
                        elif dimValue1.memberQname != dimValue2.memberQname:
                            return False 
                    elif dimValue2 is None:
                        return False
                elif dimValue1.isTyped:
                    if isinstance(dimValue2, QName):
                        return False
                    elif isinstance(dimValue2, (ModelDimensionValue,DimValuePrototype)):
                        if dimValue2.isExplicit:
                            return False
                        elif dimValue1.dimension.typedDomainElement in xpCtx.modelXbrl.modelFormulaEqualityDefinitions:
                            equalityDefinition = xpCtx.modelXbrl.modelFormulaEqualityDefinitions[dimValue1.dimension.typedDomainElement]
                            return equalityDefinition.evalTest(xpCtx, fact1, fact2)
                        elif not XbrlUtil.nodesCorrespond(fact1.modelXbrl, dimValue1.typedMember, dimValue2.typedMember, dts2=fact2.modelXbrl):
                            return False
                    elif dimValue2 is None:
                        return False
            elif isinstance(dimValue1,QName): # first dim is default value of an explicit dim
                if isinstance(dimValue2, QName): # second dim is default value of an explicit dim
                    # multi-instance does not consider member's qname here where it is a default
                    # only check if qnames match if the facts are from same instance
                    if fact1.modelXbrl == fact2.modelXbrl and dimValue1 != dimValue2:
                        return False
                elif isinstance(dimValue2, (ModelDimensionValue,DimValuePrototype)):
                    if dimValue2.isTyped:
                        return False
                    elif dimValue1 != dimValue2.memberQname:
                        return False 
                elif dimValue2 is None: # no dim aspect for fact 2
                    if fact1.modelXbrl == fact2.modelXbrl: # only allowed for multi-instance
                        return False
            elif dimValue1 is None:
                # absent dim member from fact1 allowed if fact2 is default in different instance
                if isinstance(dimValue2,QName):
                    if fact1.modelXbrl == fact2.modelXbrl:
                        return False
                elif dimValue2 is not None:
                    return False
                # else if both are None, matches True for single and multiple instance
    return True

def factsPartitions(xpCtx, facts, aspects):
    factsPartitions = []
    for fact in facts:
        matched = False
        for partition in factsPartitions:
            if aspectsMatch(xpCtx, fact, partition[0], aspects):
                partition.append(fact)
                matched = True
                break
        if not matched:
            factsPartitions.append([fact,])
    return factsPartitions

def evaluationIsUnnecessary(thisEval, otherEvalHashDicts, otherEvals):
    if otherEvals:
        if all(e is None for e in thisEval):
            return True  # evaluation not necessary, all fallen back
        # hash check if any hashes merit further look for equality
        otherEvalSets = [otherEvalHashDicts[i].get(hash(e), set())
                         for i, e in enumerate(thisEval)
                         if e is not None]
        if otherEvalSets:
            matchingEvals = [otherEvals[i] for i in  set.intersection(*otherEvalSets)]
            # detects evaluations which are not different (duplicate) and extra fallback evaluations
            return any(all([e == matchingEval[i] for i, e in enumerate(thisEval) if e is not None])
                       for matchingEval in matchingEvals)
    return False
    '''
    r = range(len(thisEval))
    for otherEval in otherEvals:
        if all([thisEval[i] is None or thisEval[i] == otherEval[i] for i in r]):
            return True
    return False
    '''

def produceOutputFact(xpCtx, formula, result):
    priorErrorCount = len(xpCtx.modelXbrl.errors)
    isTuple = isinstance(formula,ModelTuple)
    
    # assemble context
    conceptQname = formulaAspectValue(xpCtx, formula, Aspect.CONCEPT, "xbrlfe:missingConceptRule")
    if isinstance(conceptQname, VariableBindingError):
        xpCtx.modelXbrl.error(conceptQname.err,
           _("Formula %(logLabel)s concept: %(concept)s"), 
           modelObject=formula, logLabel=formula.logLabel(), concept=conceptQname.msg)
        modelConcept = None
    else:
        modelConcept = xpCtx.modelXbrl.qnameConcepts[conceptQname]
        if modelConcept is None or (not modelConcept.isTuple if isTuple else not modelConcept.isItem):
            xpCtx.modelXbrl.error("xbrlfe:missingConceptRule",
               _("Formula %(logLabel)s concept %(concept)s is not a %(element)s"), 
               modelObject=formula, logLabel=formula.logLabel(), concept=conceptQname, element=formula.localName)
    
    outputLocation = formulaAspectValue(xpCtx, formula, Aspect.LOCATION_RULE, None)

    if not isTuple: 
        # entity
        entityIdentScheme = formulaAspectValue(xpCtx, formula, Aspect.SCHEME, "xbrlfe:missingEntityIdentifierRule")
        if isinstance(entityIdentScheme, VariableBindingError):
            xpCtx.modelXbrl.error(str(entityIdentScheme),
                  _("Formula %(logLabel)s entity identifier scheme: %(scheme)s"),
                  modelObject=formula, logLabel=formula.logLabel(), scheme=entityIdentScheme.msg)
            entityIdentValue = None
        else:
            entityIdentValue = formulaAspectValue(xpCtx, formula, Aspect.VALUE, "xbrlfe:missingEntityIdentifierRule")
            if isinstance(entityIdentValue, VariableBindingError):
                xpCtx.modelXbrl.error(str(entityIdentScheme),
                      _("Formula %(logLabel)s entity identifier value: %(entityIdentifier)s"), 
                      modelObject=formula, logLabel=formula.logLabel(), entityIdentifier=entityIdentValue.msg)
        
        # period
        periodType = formulaAspectValue(xpCtx, formula, Aspect.PERIOD_TYPE, "xbrlfe:missingPeriodRule")
        periodStart = None
        periodEndInstant = None
        if isinstance(periodType, VariableBindingError):
            xpCtx.modelXbrl.error(str(periodType),
                   _("Formula %(logLabel)s period type: %(periodType)s"),
                   modelObject=formula, logLabel=formula.logLabel(), periodType=periodType.msg)
        elif periodType == "instant":
            periodEndInstant = formulaAspectValue(xpCtx, formula, Aspect.INSTANT, "xbrlfe:missingPeriodRule")
            if isinstance(periodEndInstant, VariableBindingError):
                xpCtx.modelXbrl.error(str(periodEndInstant),
                   _("Formula %(logLabel)s period end: %(period)s"), 
                   modelObject=formula, logLabel=formula.logLabel(), period=periodEndInstant.msg)
        elif periodType == "duration":
            periodStart = formulaAspectValue(xpCtx, formula, Aspect.START, "xbrlfe:missingPeriodRule")
            if isinstance(periodStart, VariableBindingError):
                xpCtx.modelXbrl.error(str(periodStart),
                   _("Formula %(logLabel)s period start: %(period)s"), 
                   modelObject=formula, logLabel=formula.logLabel(), period=periodStart.msg)
            periodEndInstant = formulaAspectValue(xpCtx, formula, Aspect.END, "xbrlfe:missingPeriodRule")
            if isinstance(periodEndInstant, VariableBindingError):
                xpCtx.modelXbrl.error(str(periodEndInstant),
                   _("Formula %(logLabel)s period end: %(period)s"),
                   modelObject=formula, logLabel=formula.logLabel(), period=periodEndInstant.msg)
            
        # unit
        if modelConcept is not None and modelConcept.isNumeric:
            unitSource = formulaAspectValue(xpCtx, formula, Aspect.UNIT_MEASURES, None)
            multDivBy = formulaAspectValue(xpCtx, formula, Aspect.MULTIPLY_BY, "xbrlfe:missingUnitRule")
            if isinstance(multDivBy, VariableBindingError):
                xpCtx.modelXbrl.error(str(multDivBy) if isinstance(multDivBy, VariableBindingError) else "xbrlfe:missingUnitRule",
                   _("Formula %(logLabel)s unit: %(unit)s"),
                   modelObject=formula, logLabel=formula.logLabel(), unit=multDivBy.msg)
                multiplyBy = (); divideBy = () # prevent errors later if bad
            else:
                divMultBy = formulaAspectValue(xpCtx, formula, Aspect.DIVIDE_BY, "xbrlfe:missingUnitRule")
                if isinstance(divMultBy, VariableBindingError):
                    xpCtx.modelXbrl.error(str(multDivBy) if isinstance(divMultBy, VariableBindingError) else "xbrlfe:missingUnitRule",
                       _("Formula %(logLabel)s unit: %(unit)s"), 
                       modelObject=formula, logLabel=formula.logLabel(), unit=divMultBy.msg)
                    multiplyBy = (); divideBy = () # prevent errors later if bad
                else:
                    multiplyBy = unitSource[0] + multDivBy[0] + divMultBy[1]
                    divideBy = unitSource[1] + multDivBy[1] + divMultBy[0]
                    # remove cancelling mult/div units
                    lookForCommonUnits = True
                    while lookForCommonUnits:
                        lookForCommonUnits = False
                        for commonUnit in multiplyBy:
                            if commonUnit in divideBy:
                                multiplyBy.remove(commonUnit)
                                divideBy.remove(commonUnit)
                                lookForCommonUnits = True
                                break
                    if len(multiplyBy) == 0: # if no units add pure
                        if (Aspect.MULTIPLY_BY not in formula.aspectValues and Aspect.MULTIPLY_BY not in formula.aspectProgs and
                            Aspect.DIVIDE_BY not in formula.aspectValues and Aspect.DIVIDE_BY not in formula.aspectProgs):
                            xpCtx.modelXbrl.error("xbrlfe:missingUnitRule",
                               _("Formula %(logLabel)s"), 
                               modelObject=formula, logLabel=formula.logLabel())
                        multiplyBy.append(XbrlConst.qnXbrliPure)
                            
        
        # dimensions
        segOCCs = []
        scenOCCs = []
        if formula.aspectModel == "dimensional":
            dimAspects = {}
            dimQnames = formulaAspectValue(xpCtx, formula, Aspect.DIMENSIONS, None)
            if dimQnames:
                for dimQname in dimQnames:
                    dimConcept = xpCtx.modelXbrl.qnameConcepts[dimQname]
                    dimErr = "xbrlfe:missing{0}DimensionRule".format("typed" if dimConcept is not None and dimConcept.isTypedDimension else "explicit")
                    dimValue = formulaAspectValue(xpCtx, formula, dimQname, dimErr)
                    if isinstance(dimValue, VariableBindingError):
                        xpCtx.modelXbrl.error(dimErr,
                           _("Formula %(logLabel)s dimension %(dimension)s: %(value)s"),
                           modelObject=formula, logLabel=formula.logLabel(), 
                           dimension=dimQname, value=dimValue.msg)
                    elif dimConcept.isTypedDimension:
                        if isinstance(dimValue, list): # result of flatten, always a list
                            if len(dimValue) != 1 or not isinstance(dimValue[0], ModelObject):
                                xpCtx.modelXbrl.error("xbrlfe:wrongXpathResultForTypedDimensionRule",
                                   _("Formula %(logLabel)s dimension %(dimension)s value is not a node: %(value)s"),
                                   modelObject=formula, logLabel=formula.logLabel(), 
                                   dimension=dimQname, value=dimValue)
                                continue
                            dimValue = dimValue[0]
                        dimAspects[dimQname] = dimValue
                    elif dimValue is not None and xpCtx.modelXbrl.qnameDimensionDefaults.get(dimQname) != dimValue:
                        dimAspects[dimQname] = dimValue
            segOCCs = formulaAspectValue(xpCtx, formula, Aspect.NON_XDT_SEGMENT, None)
            scenOCCs = formulaAspectValue(xpCtx, formula, Aspect.NON_XDT_SCENARIO, None)
            for occElt in xpCtx.flattenSequence((segOCCs, scenOCCs)):
                if isinstance(occElt, ModelObject) and occElt.namespaceURI == XbrlConst.xbrldi:
                    xpCtx.modelXbrl.error("xbrlfe:badSubsequentOCCValue",
                       _("Formula %(logLabel)s OCC element %(occ)s covers a dimensional aspect"),
                       modelObject=(formula,occElt), logLabel=formula.logLabel(), 
                       occ=occElt.elementQname)
        else:
            dimAspects = None   # non-dimensional
            segOCCs = formulaAspectValue(xpCtx, formula, Aspect.COMPLETE_SEGMENT, None)
            scenOCCs = formulaAspectValue(xpCtx, formula, Aspect.COMPLETE_SCENARIO, None)
                    
    if priorErrorCount < len(xpCtx.modelXbrl.errors):
        return None # had errors, don't produce output fact
    
    # does context exist in out instance document
    outputInstanceQname = formula.outputInstanceQname
    outputXbrlInstance = xpCtx.inScopeVars[outputInstanceQname]
    xbrlElt = outputXbrlInstance.modelDocument.xmlRootElement
    
    # in source instance document
    newFact = None
    if isTuple:
        newFact = outputXbrlInstance.createFact(conceptQname, parent=outputLocation,
                                                afterSibling=xpCtx.outputLastFact.get(outputInstanceQname))
    else:
        # add context
        prevCntx = outputXbrlInstance.matchContext(
             entityIdentScheme, entityIdentValue, periodType, periodStart, periodEndInstant, 
             dimAspects, segOCCs, scenOCCs)
        if prevCntx is not None:
            cntxId = prevCntx.id
            newCntxElt = prevCntx
        else:
            newCntxElt = outputXbrlInstance.createContext(entityIdentScheme, entityIdentValue, 
                          periodType, periodStart, periodEndInstant, conceptQname, dimAspects, segOCCs, scenOCCs,
                          afterSibling=xpCtx.outputLastContext.get(outputInstanceQname),
                          beforeSibling=xpCtx.outputFirstFact.get(outputInstanceQname))
            cntxId = newCntxElt.id
            xpCtx.outputLastContext[outputInstanceQname] = newCntxElt
        # does unit exist
        
        # add unit
        if modelConcept.isNumeric:
            prevUnit = outputXbrlInstance.matchUnit(multiplyBy, divideBy)
            if prevUnit is not None:
                unitId = prevUnit.id
                newUnitElt = prevUnit
            else:
                newUnitElt = outputXbrlInstance.createUnit(multiplyBy, divideBy, 
                                      afterSibling=xpCtx.outputLastUnit.get(outputInstanceQname),
                                      beforeSibling=xpCtx.outputFirstFact.get(outputInstanceQname))
                unitId = newUnitElt.id
                xpCtx.outputLastUnit[outputInstanceQname] = newUnitElt
    
        # add fact
        attrs = [("contextRef", cntxId)]
        precision = None
        decimals = None
        if modelConcept.isNumeric:
            attrs.append(("unitRef", unitId))
        value = formula.evaluate(xpCtx)
        valueSeqLen = len(value)
        if valueSeqLen > 1:
            xpCtx.modelXbrl.error("xbrlfe:nonSingletonOutputValue",
                _("Formula %(logLabel)s value is a sequence of length %(valueSequenceLength)s"),
                modelObject=formula, logLabel=formula.logLabel(), valueSequenceLength=valueSeqLen) 
        else: 
            if valueSeqLen == 0: #xsi:nil if no value
                attrs.append((XbrlConst.qnXsiNil, "true"))
                v = None
            else:
                # add precision/decimals for non-fraction numerics
                if modelConcept.isNumeric and not modelConcept.isFraction:
                    if formula.hasDecimals:
                        decimals = formula.evaluateRule(xpCtx, Aspect.DECIMALS)
                        attrs.append(("decimals", decimals))
                    else:
                        if formula.hasPrecision:
                            precision = formula.evaluateRule(xpCtx, Aspect.PRECISION)
                        else:
                            precision = 0
                        attrs.append(("precision", precision))
                        
                x = value[0]
                if isinstance(x,float):
                    if (isnan(x) or
                        (precision and (isinf(precision) or precision == 0)) or 
                        (decimals and isinf(decimals))):
                        v = xsString(xpCtx, None, x)
                    elif decimals is not None:
                        v = "%.*f" % ( int(decimals), x)
                    elif precision is not None and precision != 0:
                        a = fabs(x)
                        log = log10(a) if a != 0 else 0
                        v = "%.*f" % ( int(precision) - int(log) - (1 if a >= 1 else 0), x)
                    else: # no implicit precision yet
                        v = xsString(xpCtx, None, x)
                elif isinstance(x,Decimal):
                    if (x.is_nan() or
                        (precision and (isinf(precision) or precision == 0)) or 
                        (decimals and isinf(decimals))):
                        v = xsString(xpCtx, None, x)
                    elif decimals is not None:
                        v = "%.*f" % ( int(decimals), x)
                    elif precision is not None and precision != 0:
                        a = x.copy_abs()
                        log = a.log10() if a != 0 else 0
                        v = "%.*f" % ( int(precision) - int(log) - (1 if a >= 1 else 0), x)
                    else: # no implicit precision yet
                        v = xsString(xpCtx, None, x)
                elif isinstance(x,QName):
                    v = XmlUtil.addQnameValue(xbrlElt, x)
                elif isinstance(x,datetime.datetime):
                    v = XmlUtil.dateunionValue(x)
                else:
                    v = xsString(xpCtx, None, x)
            newFact = outputXbrlInstance.createFact(conceptQname, attributes=attrs, text=v,
                                                    parent=outputLocation,
                                                    afterSibling=xpCtx.outputLastFact.get(outputInstanceQname))
    if newFact is not None:
        xpCtx.outputLastFact[outputInstanceQname] = newFact
        if outputInstanceQname not in xpCtx.outputFirstFact:
            xpCtx.outputFirstFact[outputInstanceQname] = newFact
    return newFact

def formulaAspectValue(xpCtx, formula, aspect, srcMissingErr):
    ruleValue = formula.evaluateRule(xpCtx, aspect)
    
    if ruleValue is not None:
        if aspect in (Aspect.CONCEPT, 
                      Aspect.VALUE, Aspect.SCHEME,
                      Aspect.PERIOD_TYPE, Aspect.START, Aspect.END, Aspect.INSTANT,
                      ):
            return ruleValue
        if isinstance(aspect,QName) and ruleValue != XbrlConst.qnFormulaDimensionSAV:
            return ruleValue
    
    sourceQname = formula.source(aspect)
    formulaUncovered = sourceQname == XbrlConst.qnFormulaUncovered
    if aspect == Aspect.LOCATION_RULE and sourceQname is None:
        return xpCtx.inScopeVars[formula.outputInstanceQname].modelDocument.xmlRootElement
    elif aspect == Aspect.DIMENSIONS and formulaUncovered:
        aspectSourceValue = set()   # union of uncovered dimensions, all variables
    elif srcMissingErr is None:
        aspectSourceValue = None    # important for dimensions, missing is not an error
    elif formulaUncovered:
        if isinstance(aspect,QName): # absent uncovered dimension is ok, just not copied to output OCC
            aspectSourceValue = None
        else:
            aspectSourceValue = xbrlfe_undefinedSAV # other then dimensions, absent is an error

    else:
        aspectSourceValue =  VariableBindingError(srcMissingErr, 
                                                  _("neither source {0}, nor an aspect rule, were found.")
                                                  .format(sourceQname if sourceQname else ''))
    for vb in xpCtx.varBindings.values():
        if vb.isFactVar and not vb.isFallback:
            if aspect == Aspect.DIMENSIONS and formulaUncovered:
                aspectSourceValue |= vb.aspectValue(aspect)
            elif formulaUncovered and vb.hasAspectValueUncovered(aspect):
                aspectSourceValue = vb.aspectValue(aspect)
                break
            elif sourceQname == vb.qname:
                if not vb.isBindAsSequence or vb.hasAspectValueUncovered(aspect):
                    aspectSourceValue = vb.aspectValue(aspect)
                else:
                    aspectSourceValue =  VariableBindingError("xbrlfe:sequenceSAVConflicts", 
                                                              _("source, {0}, contains the QName of a fact variable that binds as a sequence where that fact's aspect rule covers this filtered aspect")
                                                              .format(sourceQname))
                break
        elif aspect == Aspect.LOCATION_RULE and sourceQname == vb.qname:
            aspectSourceValue = vb.aspectValue(aspect)
            break
                
        
    # modify by any specific rules
    if aspect in (Aspect.CONCEPT, Aspect.LOCATION_RULE, 
                  Aspect.VALUE, Aspect.SCHEME,
                  Aspect.PERIOD_TYPE, Aspect.START, Aspect.END, Aspect.INSTANT,
                  ) or isinstance(aspect,QName):
        return aspectSourceValue
    elif aspect == Aspect.UNIT_MEASURES:
        augment = formula.evaluateRule(xpCtx, Aspect.AUGMENT)
        if aspectSourceValue and (not augment or augment == "true"): # true is the default behavior
            return aspectSourceValue
        else:
            return ([],[])
    elif aspect in (Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY):
        if sourceQname and aspectSourceValue:
            return aspectSourceValue
        else:
            return (ruleValue,[])
    elif aspect == Aspect.DIMENSIONS:
        if aspectSourceValue is None: aspectSourceValue = set()
        if ruleValue is None: ruleValueSet = set()
        else: ruleValueSet = set(ruleValue)
        omitDims = formula.evaluateRule(xpCtx, Aspect.OMIT_DIMENSIONS)
        if omitDims is None: omitDimsSet = set()
        else: omitDimsSet = set(omitDims)
        return (aspectSourceValue | ruleValueSet) - omitDimsSet
    elif isinstance(aspect, QName):
        return aspectSourceValue
    elif aspect in (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO,
                    Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
        occFragments = []
        occEmpty = ruleValue and ruleValue[0] == XbrlConst.qnFormulaOccEmpty
        if not occEmpty and aspectSourceValue:
            occFragments.extend(aspectSourceValue)
        if ruleValue:
            occFragments.extend(ruleValue[1 if occEmpty else 0:])
        return occFragments
    
    return None

def uncoveredAspectValue(xpCtx, aspect):
    for vb in xpCtx.varBindings.values():
        if vb.isFactVar and not vb.isFallback and vb.hasAspectValueUncovered(aspect):
            return vb.aspectValue(aspect)
    return None

def variableBindingIsFallback(xpCtx, variableQname):
    for vb in xpCtx.varBindings.values():
        if vb.qname == variableQname:
            return vb.isFactVar and vb.isFallback
    return False

def uncoveredVariableSetAspects(xpCtx):
    aspectsDefined = set()
    aspectsCovered = set()
    for vb in xpCtx.varBindings.values():
        if vb.isFactVar and not vb.isFallback:
            aspectsCovered |= vb.aspectsCovered
            aspectsDefined |= vb.aspectsDefined  
    return (aspectsDefined - aspectsCovered)

class VariableBindingError:
    def __init__(self, err,  msg=None):
        self.err = err
        self.msg = msg
    def __repr__(self):
        return self.err
    
xbrlfe_undefinedSAV = VariableBindingError("xbrlfe:undefinedSAV")
         
class VariableBinding:
    def __init__(self, xpCtx, varRel=None, boundFact=None):
        self.xpCtx = xpCtx
        if varRel is not None:
            self.qname = varRel.variableQname
            self.var = varRel.toModelObject
        else:
            self.qname = self.var = None
        self.aspectsDefined = set()
        self.aspectsCovered = set()
        self.isFactVar = isinstance(self.var, ModelFactVariable)
        self.isGeneralVar = isinstance(self.var, ModelGeneralVariable)
        self.isParameter = isinstance(self.var, ModelParameter)
        self.isFormulaResult = isinstance(self.var, ModelFormula)
        self.isBindAsSequence = self.var.bindAsSequence == "true" if isinstance(self.var,ModelVariable) else False
        self.yieldedFact = boundFact
        self.yieldedFactResult = None
        self.isFallback = False
        self.instances = ([inst
                           for qn in self.var.fromInstanceQnames 
                           for inst in xpCtx.flattenSequence(xpCtx.inScopeVars[qn])]
                          if self.var is not None and self.var.fromInstanceQnames 
                          else [xpCtx.modelXbrl])
        
    def close(self):
        self.__dict__.clear() # dereference
        pass
        
    @property
    def resourceElementName(self):
        if self.isFactVar: return _("Fact Variable")
        elif self.isGeneralVar: return _("General Variable")
        elif self.isParameter: return _("Parameter")
        elif isinstance(self.var, ModelTuple): return _("Tuple")
        elif isinstance(self.var, ModelFormula): return _("Formula")
        elif isinstance(self.var, ModelValueAssertion): return _("ValueAssertion")
        elif isinstance(self.var, ModelExistenceAssertion): return _("ExistenceAssertion")
        
    def matchesSubPartitions(self, partition, aspects):
        if self.var.matches == "true":
            return [partition]
        subPartitions = []
        for fact in partition:
            foundSubPartition = False
            for subPartition in subPartitions:
                matchedInSubPartition = False
                for fact2 in subPartition:
                    if aspectsMatch(self.xpCtx, fact, fact2, aspects):
                        matchedInSubPartition = True
                        break
                if not matchedInSubPartition:
                    subPartition.append(fact)
                    foundSubPartition = True
                    break
            if not foundSubPartition:
                subPartitions.append([fact,])
        return subPartitions
 
    @property
    def evaluationResults(self):
        if self.isFactVar:
            if self.isBindAsSequence and self.facts:
                for factsPartition in factsPartitions(self.xpCtx, self.facts, self.aspectsDefined - self.aspectsCovered):
                    for matchesSubPartition in self.matchesSubPartitions(factsPartition, self.aspectsDefined):
                        self.yieldedFact = matchesSubPartition[0]
                        self.yieldedFactContext = self.yieldedFact.context
                        self.yieldedEvaluation = matchesSubPartition
                        self.isFallback = False
                        yield matchesSubPartition
            else:
                for fact in self.facts:
                    self.yieldedFact = fact
                    self.yieldedFactContext = self.yieldedFact.context
                    self.yieldedEvaluation = fact
                    self.isFallback = False
                    yield fact
            if self.values:
                self.yieldedFact = None
                self.yieldedFactContext = None
                self.yieldedEvaluation = "fallback"
                self.isFallback = True
                yield self.values
        elif self.isGeneralVar:
            self.yieldedFact = None
            self.yieldedFactContext = None
            self.isFallback = False

            if self.isBindAsSequence:
                self.yieldedEvaluation = self.values
                yield self.values
            else:
                for value in self.values:
                    self.yieldedEvaluation = value
                    yield value
        elif self.isParameter:
            self.yieldedFact = None
            self.yieldedEvaluation = None
            self.isFallback = False
            yield self.parameterValue
            
    def matchableBoundFact(self, fbVars):  # return from this function has to be hashable
        if (self.isFallback or self.isParameter 
            # remove to allow different gen var evaluations: or self.isGeneralVar
            or (self.isGeneralVar and not fbVars.isdisjoint(self.var.variableRefs()))):
            return None
        if self.isBindAsSequence:
            return tuple(self.yieldedEvaluation)
        if self.isFormulaResult:
            return self.yieldedFact
        return self.yieldedEvaluation
        
    def hasDimension(self, dimension):
        return dimension in self.definedDimensions
    
    def hasDimensionValueDefined(self, dimension):
        return dimension in self.definedDimensions
    
    def definedDimensions(self, dimension):
        return self.yieldedFact.context.dimAspects(self.xpCtx.defaultDimensionAspects) if self.yieldedFact.isItem and self.yieldedFact.context is not None else set()
    
    def isDimensionalValid(self, dimension):
        return False
    
    def hasAspectValueUncovered(self, aspect):
        if aspect in aspectModelAspect: aspect = aspectModelAspect[aspect]
        return aspect in self.aspectsDefined and aspect not in self.aspectsCovered
    
    def hasAspectValueCovered(self, aspect):
        if aspect in aspectModelAspect: aspect = aspectModelAspect[aspect]
        return aspect in self.aspectsCovered
    
    def aspectsNotCovered(self, aspects):
        return set(a for a in aspects if not self.hasAspectValueCovered(a))
    
    def hasAspectValueDefined(self, aspect):
        if aspect in aspectModelAspect: aspect = aspectModelAspect[aspect]
        return aspect in self.aspectsDefined
    
    def aspectValue(self, aspect):
        fact = self.yieldedFact
        if fact is None:
            if aspect == Aspect.DIMENSIONS:
                return set()
            else:
                return None
        if aspect == Aspect.LOCATION:
            return fact.getparent()
        elif aspect == Aspect.LOCATION_RULE:
            return fact
        elif aspect == Aspect.CONCEPT:
            return fact.qname
        elif fact.isTuple or fact.context is None:
            return None     #subsequent aspects don't exist for tuples
        # context is known to be not None after here
        elif aspect == Aspect.PERIOD:
            return fact.context.period
        elif aspect == Aspect.PERIOD_TYPE:
            if fact.context.isInstantPeriod: return "instant"
            elif fact.context.isStartEndPeriod: return "duration"
            elif fact.context.isForeverPeriod: return "forever"
            return None
        elif aspect == Aspect.INSTANT:
            return fact.context.instantDatetime
        elif aspect == Aspect.START:
            return fact.context.startDatetime
        elif aspect == Aspect.END:
            return fact.context.endDatetime
        elif aspect == Aspect.ENTITY_IDENTIFIER:
            return fact.context.entityIdentifierElement
        elif aspect == Aspect.SCHEME:
            return fact.context.entityIdentifier[0]
        elif aspect == Aspect.VALUE:
            return fact.context.entityIdentifier[1]
        elif aspect in (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO,
                        Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
            return fact.context.nonDimValues(aspect)
        elif aspect == Aspect.DIMENSIONS:
            return fact.context.dimAspects(self.xpCtx.defaultDimensionAspects)
        elif isinstance(aspect, QName):
            return fact.context.dimValue(aspect)
        elif fact.unit is not None:
            if aspect == Aspect.UNIT:
                return fact.unit
            elif aspect in (Aspect.UNIT_MEASURES, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY):
                return fact.unit.measures
        return None

     
    