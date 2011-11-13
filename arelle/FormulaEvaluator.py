'''
Created on Jan 9, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (XPathContext, XbrlConst, XmlUtil, XbrlUtil, XmlValidate)
from arelle.FunctionXs import xsString
from arelle.ModelFormulaObject import (aspectModels, Aspect, aspectModelAspect,
                                 ModelFormula, ModelExistenceAssertion,
                                 ModelValueAssertion, 
                                 ModelFactVariable, ModelGeneralVariable, ModelVariable,
                                 ModelParameter, ModelFilter, ModelAspectCover)
from arelle.ModelValue import (QName)
import datetime

def evaluate(xpCtx, varSet):
    # for each dependent variable, find bindings
    xpCtx.varBindings = {}
    xpCtx.evaluations = []
    try:
        xpCtx.variableSet = varSet
        if isinstance(varSet, ModelExistenceAssertion):
            varSet.evaluationsCount = 0
        initialTraceCount = xpCtx.modelXbrl.logCountInfo
        evaluateVar(xpCtx, varSet, 0)
        if isinstance(varSet, ModelExistenceAssertion):
            prog = varSet.testProg
            if prog:
                assertionParamQnames = []  # set and then remove assertion variable quames
                for varRel in varSet.orderedVariableRelationships:
                    varQname = varRel.variableQname
                    var = varRel.toModelObject
                    if isinstance(var, ModelParameter) and varQname not in xpCtx.inScopeVars:
                        assertionParamQnames.append(varQname)
                        xpCtx.inScopeVars[varQname] = xpCtx.inScopeVars.get(var.qname)
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
            if msg:
                xpCtx.modelXbrl.error(msg.evaluate(xpCtx), "info", "message:" + varSet.id)
        if xpCtx.formulaOptions.traceVariableSetExpressionResult and initialTraceCount == xpCtx.modelXbrl.logCountInfo:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Variable set %(xlinkLabel)s had no xpCtx.evaluations"),
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel)
        xpCtx.variableSet = None
    except XPathContext.XPathException as err:
        xpCtx.modelXbrl.error(err.code,
                 _("Variable set %(xlinkLabel)s \nException: %(error)s"), 
                 modelObject=varSet, xlinkLabel=varSet.xlinkLabel, error=err.message)
        xpCtx.variableSet = None
    
def evaluateVar(xpCtx, varSet, varIndex):
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
        if evaluationIsUnnecessary(thisEvaluation, xpCtx.evaluations):
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                    _("Variable set %(xlinkLabel)s skipped non-different or fallback evaluation, duplicates another evaluation"),
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel)
            return
        xpCtx.evaluations.append(thisEvaluation)
        # evaluate preconditions
        for precondition in varSet.preconditions:
            result = precondition.evalTest(xpCtx)
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Variable set %(xlinkLabel)s \nPrecondition %(precondition)s \nResult: %(result)s"), 
                     modelObject=varSet, xlinkLabel=varSet.xlinkLabel, precondition=precondition.xlinkLabel, result=result)
            if not result: # precondition blocks evaluation
                return
            
        # evaluate variable set
        if isinstance(varSet, ModelExistenceAssertion):
            varSet.evaluationsCount += 1
        else:
            if isinstance(varSet, ModelFormula):
                result = xpCtx.evaluate(varSet.valueProg)
                traceOf = "Formula"
            elif isinstance(varSet, ModelValueAssertion):
                result = xpCtx.evaluateBooleanValue(varSet.testProg)
                if result: varSet.countSatisfied += 1
                else: varSet.countNotSatisfied += 1
                msg = varSet.message(result)
                if msg is not None:
                    xpCtx.modelXbrl.info("message:" + (varSet.id or varSet.xlinkLabel or _("unlabeled variableSet")),
                        msg.evaluate(xpCtx),
                        modelObject=varSet)
                traceOf = "Value Assertion"
            if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("%(variableSetType)s %(xlinkLabel)s \nResult: \n%(result)s"),
                     modelObject=varSet, variableSetType=traceOf, xlinkLabel=varSet.xlinkLabel, result=result)
            if isinstance(varSet, ModelFormula) and varSet.outputInstanceQname in xpCtx.inScopeVars:
                newFact = produceOutputFact(xpCtx, varSet, result)
            if varSet.hasConsistencyAssertion:
                from arelle import FormulaConsisAsser
                FormulaConsisAsser.evaluate(xpCtx, varSet, newFact)
    else:
        # produce variable bindings
        varRel = varSet.orderedVariableRelationships[varIndex]
        vb = VariableBinding(xpCtx, varRel)
        if vb.isFactVar:
            vb.aspectsDefined = set(aspectModels[varSet.aspectModel])  # has to be a mutable set
            vb.values = None
            if vb.var.fromInstanceQnames:
                facts = [f for qn in vb.var.fromInstanceQnames 
                         for instSeq in (xpCtx.inScopeVars[qn],)
                         for inst in (instSeq if isinstance(instSeq,(list,tuple)) else (instSeq,)) 
                         for f in inst.factsInInstance] 
            else:
                facts = xpCtx.modelXbrl.factsInInstance
            if vb.var.nils == "false":
                facts = [fact for fact in facts if not fact.isNil]
            if xpCtx.formulaOptions.traceVariableFilterWinnowing:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Fact Variable %(variable)s filtering: start with %(factCount)s facts"), 
                     modelObject=vb.var, variable=vb.qname, factCount=len(facts))
            coverAspectCoverFilterDims(xpCtx, vb, vb.var.filterRelationships) # filters need to know what dims are covered
            facts = filterFacts(xpCtx, vb, facts, varSet.groupFilterRelationships, "group")
            # implicit filters (relativeFilter) expect no dim aspects yet on variable binding
            facts = filterFacts(xpCtx, vb, facts, vb.var.filterRelationships, None)
            # adding dim aspects must be done after explicit filterin
            for fact in facts:
                if fact.isItem:
                    vb.aspectsDefined |= fact.context.dimAspects(xpCtx.defaultDimensionAspects)
            if varSet.implicitFiltering == "true" and len(xpCtx.varBindings) > 0:
                facts = aspectMatchFilter(xpCtx, facts, (vb.aspectsDefined - vb.aspectsCovered), xpCtx.varBindings.values(), "implicit")
            vb.facts = facts
            if xpCtx.formulaOptions.traceVariableFiltersResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("Fact Variable %(variable)s: filters result %(result)s"), 
                     modelObject=vb.var, variable=vb.qname, result=str(vb.facts))
            if vb.var.fallbackValueProg:
                vb.values = xpCtx.evaluate(vb.var.fallbackValueProg)
                if xpCtx.formulaOptions.traceVariableExpressionResult:
                    xpCtx.modelXbrl.info("formula:trace",
                         _("Fact Variable %(variable)s: fallbackValue result %(result)s"), 
                         modelObject=vb.var, variable=vb.qname, result=str(vb.values))
        elif vb.isGeneralVar: # general variable
            if vb.var.fromInstanceQnames:
                contextItem = [inst.modelDocument.xmlRootElement 
                               for qn in vb.var.fromInstanceQnames 
                               for instSeq in (xpCtx.inScopeVars[qn],)
                               for inst in (instSeq if isinstance(instSeq,(list,tuple)) else (instSeq,)) 
                               ] 
            else:
                contextItem = xpCtx.modelXbrl.modelDocument.xmlRootElement  # default is standard input instance
            vb.values = xpCtx.flattenSequence( xpCtx.evaluate(vb.var.selectProg, contextItem=contextItem) )
            if xpCtx.formulaOptions.traceVariableExpressionResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("General Variable %(variable)s: select result %(result)s"),
                     modelObject=vb.var, variable=vb.qname, result=str(vb.values))
        elif vb.isParameter:
            vb.parameterValue = xpCtx.inScopeVars.get(vb.var.qname)
        # recurse partitions
        xpCtx.varBindings[vb.qname] = vb
        for evaluationResult in vb.evaluationResults:
            overriddenInScopeVar = None
            if vb.qname in xpCtx.inScopeVars: # save overridden value if there was one
                overriddenInScopeVar = xpCtx.inScopeVars[vb.qname]
            xpCtx.inScopeVars[vb.qname] = evaluationResult
            if xpCtx.formulaOptions.traceVariableFiltersResult:
                xpCtx.modelXbrl.info("formula:trace",
                     _("%(variableType)s %(variable)s: bound value %(result)s"), 
                     modelObject=vb.var, variableType=vb.resourceElementName, variable=vb.qname, result=str(evaluationResult))
            evaluateVar(xpCtx, varSet, varIndex + 1)
            xpCtx.inScopeVars.pop(vb.qname)
            if overriddenInScopeVar is not None:  # restore overridden value if there was one
                xpCtx.inScopeVars[vb.qname] = overriddenInScopeVar
        xpCtx.varBindings.pop(vb.qname)
        
def filterFacts(xpCtx, vb, facts, filterRelationships, filterType):
    typeLbl = filterType + " " if filterType else ""
    orFilter = filterType == "or"
    if orFilter: 
        factSet = set()
    for varFilterRel in filterRelationships:
        filter = varFilterRel.toModelObject
        if isinstance(filter,ModelFilter):  # relationship not constrained to real filters
            result = filter.filter(xpCtx, vb, facts, varFilterRel.isComplemented)
            if xpCtx.formulaOptions.traceVariableFilterWinnowing:
                xpCtx.modelXbrl.info("formula:trace",
                    _("Fact Variable %(variable)s %(filterType)s %(filter)s filter %(xlinkLabel)s passes %(factCount)s facts"), 
                    modelObject=vb.var, variable=vb.qname,
                    filterType=typeLbl, filter=filter.localName, xlinkLabel=filter.xlinkLabel, factCount=len(result)),
            if orFilter: 
                for fact in result: factSet.add(fact)
            else: 
                facts = result
            if varFilterRel.isCovered:
                vb.aspectsCovered |= filter.aspectsCovered(vb)
    if orFilter: 
        return factSet
    else: 
        return facts
            
def coverAspectCoverFilterDims(xpCtx, vb, filterRelationships):
    for varFilterRel in filterRelationships:
        filter = varFilterRel.toModelObject
        if isinstance(filter,ModelAspectCover):  # relationship not constrained to real filters
            if varFilterRel.isCovered:
                vb.aspectsCovered |= filter.dimAspectsCovered(vb)
            
def aspectMatchFilter(xpCtx, facts, aspects, varBindings, filterType, relBinding=None):
    for aspect in aspects:
        for vb in (varBindings if hasattr(varBindings, '__iter__') else (varBindings,)):
            if (vb.isFactVar and not vb.isFallback and not vb.hasAspectValueCovered(aspect) and
                (relBinding is None or (relBinding.isFactVar and not relBinding.isFallback and not relBinding.hasAspectValueCovered(aspect)))):
            #if not vb.isFallback and vb.hasAspectValueUncovered(aspect):
                facts = [fact for fact in facts if aspectMatches(xpCtx, vb.yieldedFact, fact, aspect)]
                if xpCtx.formulaOptions.traceVariableFilterWinnowing:
                    a = str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect]
                    xpCtx.modelXbrl.info("formula:trace",
                        _("Fact Variable %(variable)s %(filter)s filter %(aspect)s passes %(factCount)s facts"), 
                        modelObject=vb.var, variable=vb.qname, filter=filterType, aspect=a, factCount=len(facts)),
                if len(facts) == 0: break
    if relBinding is not None and vb.isFactVar and not vb.isFallback and relBinding.isFactVar and not relBinding.isFallback:    
        # check each dimension aspect of candidate fact (no dim aspect in aspects, only fact's apply)
        matchedFacts = []
        for fact in facts:
            matches = True
            if vb.isFactVar and not vb.isFallback:
                for dimAspect in fact.context.dimAspects(xpCtx.defaultDimensionAspects):
                    if (not vb.hasAspectValueCovered(dimAspect) and
                        not relBinding.hasAspectValueCovered(dimAspect) and 
                        not aspectMatches(xpCtx, vb.yieldedFact, fact, dimAspect)):
                        matches = False
            if matches:
                matchedFacts.append(fact)
        facts = matchedFacts
        if xpCtx.formulaOptions.traceVariableFilterWinnowing:
            xpCtx.modelXbrl.info("formula:trace",
                _("Fact Variable %(variable)s %(filter)s filter dimension matching passes %(factCount)s facts"), 
                modelObject=vb.var, variable=vb.qname, filter=filterType, factCount=len(facts)),
    return facts
    
def aspectMatches(xpCtx, fact1, fact2, aspects):
    if fact1 is None or fact2 is None:  # fallback (atomic) never matches any aspect
        return False
    matches = True
    for aspect in (aspects if hasattr(aspects,'__iter__') else (aspects,)):
        if aspect == Aspect.LOCATION:
            if (fact1.modelXbrl == fact2.modelXbrl and # test deemed true for multi-instance comparisons
                fact1.getparent() != fact2.getparent()): matches = False
        elif aspect == Aspect.CONCEPT:
            if fact1.concept.qname != fact2.concept.qname: matches = False
        elif fact1.isTuple or fact2.isTuple:
            return True # only match the aspects both facts have 
        elif aspect == Aspect.PERIOD:
            if not fact1.context.isPeriodEqualTo(fact2.context): matches = False
        elif aspect == Aspect.ENTITY_IDENTIFIER:
            if not fact1.context.isEntityIdentifierEqualTo(fact2.context): matches = False
        elif aspect == Aspect.COMPLETE_SEGMENT:
            if not XbrlUtil.nodesCorrespond(fact1.modelXbrl, fact1.context.segment, fact2.context.segment, dts2=fact2.modelXbrl): 
                matches = False
        elif aspect == Aspect.COMPLETE_SCENARIO:
            if not XbrlUtil.nodesCorrespond(fact1.modelXbrl, fact1.context.scenario, fact2.context.scenario, dts2=fact2.modelXbrl): 
                matches = False
        elif aspect in (Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
            nXs1 = fact1.context.nonDimValues(aspect)
            nXs2 = fact2.context.nonDimValues(aspect)
            if len(nXs1) != len(nXs2):
                matches = False
            else:
                for i in range(len(nXs1)):
                    if not XbrlUtil.nodesCorrespond(fact1.modelXbrl, nXs1[i], nXs2[i], dts2=fact2.modelXbrl): 
                        matches = False
                        break
        elif aspect == Aspect.UNIT:
            u1 = fact1.unit
            u2 = fact2.unit
            if (u1 is None) != (u2 is None):
                matches = False
            elif u1 is not None and u2 is not None and u1.measures != u2.measures:
                matches = False
        elif aspect == Aspect.DIMENSIONS:
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
            from arelle.ModelInstanceObject import ModelDimensionValue
            dimValue1 = fact1.context.dimValue(aspect)
            dimValue2 = fact2.context.dimValue(aspect)
            if isinstance(dimValue1, ModelDimensionValue):
                if dimValue1.isExplicit: 
                    if isinstance(dimValue2, QName):
                        if dimValue1.memberQname != dimValue2:
                            matches = False
                    elif isinstance(dimValue2, ModelDimensionValue):
                        if dimValue2.isTyped:
                            matches = False
                        elif dimValue1.memberQname != dimValue2.memberQname:
                            matches = False 
                    elif dimValue2 is None:
                        matches = False
                elif dimValue1.isTyped:
                    if isinstance(dimValue2, QName):
                        matches = False
                    elif isinstance(dimValue2, ModelDimensionValue):
                        if dimValue2.isExplicit:
                            matches = False
                        elif dimValue1.dimension.typedDomainElement in xpCtx.modelXbrl.modelFormulaEqualityDefinitions:
                            equalityDefinition = xpCtx.modelXbrl.modelFormulaEqualityDefinitions[dimValue1.dimension.typedDomainElement]
                            matches = equalityDefinition.evalTest(xpCtx, fact1, fact2)
                        elif not XbrlUtil.nodesCorrespond(fact1.modelXbrl, dimValue1.typedMember, dimValue2.typedMember, dts2=fact2.modelXbrl):
                            matches = False
                    elif dimValue2 is None:
                        matches = False
            elif isinstance(dimValue1,QName): # first dim is default value of an explicit dim
                if isinstance(dimValue2, QName): # second dim is default value of an explicit dim
                    # multi-instance does not consider member's qname here where it is a default
                    # only check if qnames match if the facts are from same instance
                    if fact1.modelXbrl == fact2.modelXbrl and dimValue1 != dimValue2:
                        matches = False
                elif isinstance(dimValue2, ModelDimensionValue):
                    if dimValue2.isTyped:
                        matches = False
                    elif dimValue1 != dimValue2.memberQname:
                        matches = False 
                elif dimValue2 is None: # no dim aspect for fact 2
                    if fact1.modelXbrl == fact2.modelXbrl: # only allowed for multi-instance
                        matches = False
            elif dimValue1 is None:
                # absent dim member from fact1 allowed if fact2 is default in different instance
                if isinstance(dimValue2,QName):
                    if fact1.modelXbrl == fact2.modelXbrl:
                        matches = False
                elif dimValue2 is not None:
                    matches = False
                # else if both are None, matches True for single and multiple instance
        if not matches: 
            break
    return matches

def evaluationIsUnnecessary(thisEval, otherEvals):
    # detects evaluations which are not different (duplicate) and extra fallback evaluations
    r = range(len(thisEval))
    for otherEval in otherEvals:
        if all([thisEval[i] is None or thisEval[i] == otherEval[i] for i in r]):
            return True
    return False

def produceOutputFact(xpCtx, formula, result):
    priorErrorCount = len(xpCtx.modelXbrl.errors)
    
    # assemble context
    conceptQname = aspectValue(xpCtx, formula, Aspect.CONCEPT, "xbrlfe:missingConceptRule")
    if isinstance(conceptQname, VariableBindingError):
        xpCtx.modelXbrl.error(conceptQname.err,
           _("Formula %(xlinkLabel)s concept: %(concept)s"), 
           modelObject=formula, xlinkLabel=formula.xlinkLabel, concept=conceptQname.msg)
        modelConcept = None
    else:
        modelConcept = xpCtx.modelXbrl.qnameConcepts[conceptQname]
        if modelConcept is None or not modelConcept.isItem:
            xpCtx.modelXbrl.error("xbrlfe:missingConceptRule",
               _("Formula %(xlinkLabel)s concept %(concept)s is not an item"), 
               modelObject=formula, xlinkLabel=formula.xlinkLabel, concept=conceptQname)
        
    # entity
    entityIdentScheme = aspectValue(xpCtx, formula, Aspect.SCHEME, "xbrlfe:missingEntityIdentifierRule")
    if isinstance(entityIdentScheme, VariableBindingError):
        xpCtx.modelXbrl.error(str(entityIdentScheme),
              _("Formula %(xlinkLabel)s entity identifier scheme: %(scheme)s"),
              modelObject=formula, xlinkLabel=formula.xlinkLabel, scheme=entityIdentScheme.msg)
        entityIdentValue = None
    else:
        entityIdentValue = aspectValue(xpCtx, formula, Aspect.VALUE, "xbrlfe:missingEntityIdentifierRule")
        if isinstance(entityIdentValue, VariableBindingError):
            xpCtx.modelXbrl.error(str(entityIdentScheme),
                  _("Formula %(xlinkLabel)s entity identifier value: %(entityIdentifier)s"), 
                  modelObject=formula, xlinkLabel=formula.xlinkLabel, entityIdentifier=entityIdentValue.msg)
    
    # period
    periodType = aspectValue(xpCtx, formula, Aspect.PERIOD_TYPE, "xbrlfe:missingPeriodRule")
    periodStart = None
    periodEndInstant = None
    if isinstance(periodType, VariableBindingError):
        xpCtx.modelXbrl.error(str(periodType),
               _("Formula %(xlinkLabel)s period type: %(periodType)s"),
               modelObject=formula, xlinkLabel=formula.xlinkLabel, periodType=periodType.msg)
    elif periodType == "instant":
        periodEndInstant = aspectValue(xpCtx, formula, Aspect.INSTANT, "xbrlfe:missingPeriodRule")
        if isinstance(periodEndInstant, VariableBindingError):
            xpCtx.modelXbrl.error(str(periodEndInstant),
               _("Formula %(xlinkLabel)s period end: %(period)s"), 
               modelObject=formula, xlinkLabel=formula.xlinkLabel, period=periodEndInstant.msg)
    elif periodType == "duration":
        periodStart = aspectValue(xpCtx, formula, Aspect.START, "xbrlfe:missingPeriodRule")
        if isinstance(periodStart, VariableBindingError):
            xpCtx.modelXbrl.error(str(periodStart),
               _("Formula %(xlinkLabel)s period start: %(period)s"), 
               modelObject=formula, xlinkLabel=formula.xlinkLabel, period=periodStart.msg)
        periodEndInstant = aspectValue(xpCtx, formula, Aspect.END, "xbrlfe:missingPeriodRule")
        if isinstance(periodEndInstant, VariableBindingError):
            xpCtx.modelXbrl.error(str(periodEndInstant),
               _("Formula %(xlinkLabel)s period end: %(period)s"),
               modelObject=formula, xlinkLabel=formula.xlinkLabel, period=periodEndInstant.msg)
        
    # unit
    if modelConcept is not None and modelConcept.isNumeric:
        unitSource = aspectValue(xpCtx, formula, Aspect.UNIT_MEASURES, None)
        multDivBy = aspectValue(xpCtx, formula, Aspect.MULTIPLY_BY, "xbrlfe:missingUnitRule")
        if isinstance(multDivBy, VariableBindingError):
            xpCtx.modelXbrl.error(str(multDivBy) if isinstance(multDivBy, VariableBindingError) else "xbrlfe:missingUnitRule",
               _("Formula %(xlinkLabel)s unit: %(unit)s"),
               modelObject=formula, xlinkLabel=formula.xlinkLabel, unit=multDivBy.msg)
            multiplyBy = (); divideBy = () # prevent errors later if bad
        else:
            divMultBy = aspectValue(xpCtx, formula, Aspect.DIVIDE_BY, "xbrlfe:missingUnitRule")
            if isinstance(divMultBy, VariableBindingError):
                xpCtx.modelXbrl.error(str(multDivBy) if isinstance(divMultBy, VariableBindingError) else "xbrlfe:missingUnitRule",
                   _("Formula %(xlinkLabel)s unit: %(unit)s"), 
                   modelObject=formula, xlinkLabel=formula.xlinkLabel, unit=divMultBy.msg)
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
                    multiplyBy.append(XbrlConst.qnXbrliPure)
                        
    
    # dimensions
    segOCCs = []
    scenOCCs = []
    if formula.aspectModel == "dimensional":
        dimAspects = {}
        dimQnames = aspectValue(xpCtx, formula, Aspect.DIMENSIONS, None)
        if dimQnames:
            for dimQname in dimQnames:
                dimConcept = xpCtx.modelXbrl.qnameConcepts[dimQname]
                dimErr = "xbrlfe:missing{0}DimensionRule".format("typed" if dimConcept is not None and dimConcept.isTypedDimension else "explicit")
                dimValue = aspectValue(xpCtx, formula, dimQname, dimErr)
                if isinstance(dimValue, VariableBindingError):
                    xpCtx.modelXbrl.error(dimErr,
                       _("Formula %(xlinkLabel)s dimension %(dimension)s: %(value)s"),
                       modelObject=formula, xlinkLabel=formula.xlinkLabel, 
                       dimension=dimQname, value=dimValue.msg)
                elif dimValue is not None and xpCtx.modelXbrl.qnameDimensionDefaults.get(dimQname) != dimValue:
                    dimAspects[dimQname] = dimValue
        segOCCs = aspectValue(xpCtx, formula, Aspect.NON_XDT_SEGMENT, None)
        scenOCCs = aspectValue(xpCtx, formula, Aspect.NON_XDT_SCENARIO, None)
    else:
        dimAspects = None   # non-dimensional
        segOCCs = aspectValue(xpCtx, formula, Aspect.COMPLETE_SEGMENT, None)
        scenOCCs = aspectValue(xpCtx, formula, Aspect.COMPLETE_SCENARIO, None)
                    
    if priorErrorCount < len(xpCtx.modelXbrl.errors):
        return None # had errors, don't produce output fact
    
    # does context exist in out instance document
    outputInstanceQname = formula.outputInstanceQname
    outputXbrlInstance = xpCtx.inScopeVars[outputInstanceQname]
    xbrlElt = outputXbrlInstance.modelDocument.xmlRootElement
    
    # in source instance document
    
    # add context
    prevCntx = outputXbrlInstance.matchContext(
         entityIdentScheme, entityIdentValue, periodType, periodStart, periodEndInstant, 
         dimAspects, segOCCs, scenOCCs)
    if prevCntx is not None:
        cntxId = prevCntx.id
        newCntxElt = prevCntx
    else:
        cntxId = 'c-{0:02n}'.format( len(outputXbrlInstance.contexts) + 1)
        newCntxElt = XmlUtil.addChild(xbrlElt, XbrlConst.xbrli, "context", attributes=("id", cntxId),
                                      afterSibling=xpCtx.outputLastContext.get(outputInstanceQname))
        xpCtx.outputLastContext[outputInstanceQname] = newCntxElt
        entityElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "entity")
        XmlUtil.addChild(entityElt, XbrlConst.xbrli, "identifier",
                            attributes=("scheme", entityIdentScheme),
                            text=entityIdentValue)
        periodElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "period")
        if periodType == "forever":
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "forever")
        elif periodType == "instant":
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "instant", 
                             text=XmlUtil.dateunionValue(periodEndInstant, subtractOneDay=True))
        elif periodType == "duration":
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "startDate", 
                             text=XmlUtil.dateunionValue(periodStart))
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "endDate", 
                             text=XmlUtil.dateunionValue(periodEndInstant, subtractOneDay=True))
        segmentElt = None
        scenarioElt = None
        from arelle.ModelInstanceObject import ModelDimensionValue
        if dimAspects:
            for dimQname in sorted(dimAspects.keys()):
                dimValue = dimAspects[dimQname]
                if isinstance(dimValue, ModelDimensionValue):
                    if dimValue.isExplicit: 
                        dimMemberQname = dimValue.memberQname
                    contextEltName = dimValue.contextElement
                else: # qname for explicit or node for typed
                    dimMemberQname = dimValue
                    contextEltName = xpCtx.modelXbrl.qnameDimensionContextElement.get(dimQname)
                if contextEltName == "segment":
                    if segmentElt is None: 
                        segmentElt = XmlUtil.addChild(entityElt, XbrlConst.xbrli, "segment")
                    contextElt = segmentElt
                elif contextEltName == "scenario":
                    if scenarioElt is None: 
                        scenarioElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "scenario")
                    contextElt = scenarioElt
                else:
                    continue
                dimConcept = xpCtx.modelXbrl.qnameConcepts[dimQname]
                dimAttr = ("dimension", XmlUtil.addQnameValue(xbrlElt, dimConcept.qname))
                if dimConcept.isTypedDimension:
                    dimElt = XmlUtil.addChild(contextElt, XbrlConst.xbrldi, "xbrldi:typedMember", 
                                              attributes=dimAttr)
                    if isinstance(dimValue, ModelDimensionValue) and dimValue.isTyped:
                        XmlUtil.copyChildren(dimElt, dimValue)
                elif dimMemberQname:
                    dimElt = XmlUtil.addChild(contextElt, XbrlConst.xbrldi, "xbrldi:explicitMember",
                                              attributes=dimAttr,
                                              text=XmlUtil.addQnameValue(xbrlElt, dimMemberQname))
        if segOCCs:
            if segmentElt is None: 
                segmentElt = XmlUtil.addChild(entityElt, XbrlConst.xbrli, "segment")
            XmlUtil.copyNodes(segmentElt, segOCCs)
        if scenOCCs:
            if scenarioElt is None: 
                scenarioElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "scenario")
            XmlUtil.copyNodes(scenarioElt, scenOCCs)
                
        outputXbrlInstance.modelDocument.contextDiscover(newCntxElt)
        XmlValidate.validate(outputXbrlInstance, newCntxElt)    
    # does unit exist
    
    # add unit
    if modelConcept.isNumeric:
        prevUnit = outputXbrlInstance.matchUnit(multiplyBy, divideBy)
        if prevUnit is not None:
            unitId = prevUnit.id
            newUnitElt = prevUnit
        else:
            unitId = 'u-{0:02n}'.format( len(outputXbrlInstance.units) + 1)
            newUnitElt = XmlUtil.addChild(xbrlElt, XbrlConst.xbrli, "unit", attributes=("id", unitId),
                                          afterSibling=xpCtx.outputLastUnit.get(outputInstanceQname))
            xpCtx.outputLastUnit[outputInstanceQname] = newUnitElt
            if len(divideBy) == 0:
                for multiply in multiplyBy:
                    XmlUtil.addChild(newUnitElt, XbrlConst.xbrli, "measure", text=XmlUtil.addQnameValue(xbrlElt, multiply))
            else:
                divElt = XmlUtil.addChild(newUnitElt, XbrlConst.xbrli, "divide")
                numElt = XmlUtil.addChild(divElt, XbrlConst.xbrli, "unitNumerator")
                denElt = XmlUtil.addChild(divElt, XbrlConst.xbrli, "unitDenominator")
                for multiply in multiplyBy:
                    XmlUtil.addChild(numElt, XbrlConst.xbrli, "measure", text=XmlUtil.addQnameValue(xbrlElt, multiply))
                for divide in divideBy:
                    XmlUtil.addChild(denElt, XbrlConst.xbrli, "measure", text=XmlUtil.addQnameValue(xbrlElt, divide))
            outputXbrlInstance.modelDocument.unitDiscover(newUnitElt)
            XmlValidate.validate(outputXbrlInstance, newUnitElt)    
    
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
            _("Formula %(xlinkLabel)s value is a sequence of length %(valueSequenceLength)s"),
            modelObject=formula, xlinkLabel=formula.xlinkLabel, valueSequenceLength=valueSeqLen) 
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
                from math import (log10, isnan, isinf, fabs)
                if (isnan(x) or
                    (precision and (isinf(precision) or precision == 0)) or 
                    (decimals and isinf(decimals))):
                    v = xsString(xpCtx, x)
                elif decimals is not None:
                    v = "%.*f" % ( int(decimals), x)
                elif precision is not None and precision != 0:
                    a = fabs(x)
                    log = log10(a) if a != 0 else 0
                    v = "%.*f" % ( int(precision) - int(log) - (1 if a >= 1 else 0), x)
                else: # no implicit precision yet
                    v = xsString(xpCtx, x)
            elif isinstance(x,QName):
                v = XmlUtil.addQnameValue(xbrlElt, x)
            elif isinstance(x,datetime.datetime):
                v = XmlUtil.dateunionValue(x)
            else:
                v = xsString(xpCtx, x)
        newFact = XmlUtil.addChild(xbrlElt, conceptQname,
                                   attributes=attrs, text=v,
                                   afterSibling=xpCtx.outputLastFact.get(outputInstanceQname))
        xpCtx.outputLastFact[outputInstanceQname] = newFact
        outputXbrlInstance.modelDocument.factDiscover(newFact, outputXbrlInstance.facts)
        XmlValidate.validate(outputXbrlInstance, newFact)    
        return newFact

def aspectValue(xpCtx, formula, aspect, srcMissingErr):
    if aspect == Aspect.LOCATION:
        return xpCtx.inScopeVars[formula.outputInstanceQname].xmlRootElement

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
    if aspect == Aspect.DIMENSIONS and formulaUncovered:
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
                
        
    # modify by any specific rules
    if aspect in (Aspect.CONCEPT, 
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
    def __init__(self, xpCtx, varRel):
        self.xpCtx = xpCtx
        self.qname = varRel.variableQname
        self.var = varRel.toModelObject
        self.aspectsDefined = set()
        self.aspectsCovered = set()
        self.isFactVar = isinstance(self.var, ModelFactVariable)
        self.isGeneralVar = isinstance(self.var, ModelGeneralVariable)
        self.isParameter = isinstance(self.var, ModelParameter)
        self.isBindAsSequence = self.var.bindAsSequence == "true" if isinstance(self.var,ModelVariable) else False
        self.yieldedFact = None
        self.yieldedFactResult = None
        self.isFallback = False
        
    @property
    def resourceElementName(self):
        if self.isFactVar: return _("Fact Variable")
        elif self.isGeneralVar: return _("General Variable")
        elif self.isParameter: return _("Parameter")
        
    def factsPartitions(self, aspects):
        factsPartitions = []
        for fact in self.facts:
            matched = False
            for partition in factsPartitions:
                if aspectMatches(self.xpCtx, fact, partition[0], aspects):
                    partition.append(fact)
                    matched = True
                    break
            if not matched:
                factsPartitions.append([fact,])
        return factsPartitions
 
    def matchesSubPartitions(self, partition, aspects):
        if self.var.matches == "true":
            return [partition]
        subPartitions = []
        for fact in partition:
            foundSubPartition = False
            for subPartition in subPartitions:
                matchedInSubPartition = False
                for fact2 in subPartition:
                    if aspectMatches(self.xpCtx, fact, fact2, aspects):
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
                for factsPartition in self.factsPartitions(self.aspectsDefined - self.aspectsCovered):
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
            
    def matchableBoundFact(self, fbVars):
        if (self.isFallback or self.isParameter 
            # remove to allow different gen var evaluations: or self.isGeneralVar
            or not fbVars.isdisjoint(self.var.variableRefs())):
            return None
        return self.yieldedEvaluation
        
    def hasDimension(self, dimension):
        return dimension in self.definedDimensions
    
    def hasDimensionValueDefined(self, dimension):
        return dimension in self.definedDimensions
    
    def definedDimensions(self, dimension):
        return self.yieldedFact.context.dimAspects(self.xpCtx.defaultDimensionAspects) if self.yieldedFact.isItem else set()
    
    def isDimensionalValid(self, dimension):
        return False
    
    def hasAspectValueUncovered(self, aspect):
        if aspect in aspectModelAspect: aspect = aspectModelAspect[aspect]
        return aspect in self.aspectsDefined and aspect not in self.aspectsCovered
    
    def hasAspectValueCovered(self, aspect):
        if aspect in aspectModelAspect: aspect = aspectModelAspect[aspect]
        return aspect in self.aspectsCovered
    
    def hasAspectValueDefined(self, aspect):
        if aspect in aspectModelAspect: aspect = aspectModelAspect[aspect]
        return aspect in self.aspectsDefined
    
    def aspectValue(self, aspect):
        if self.yieldedFact is None:
            if aspect == Aspect.DIMENSIONS:
                return set()
            else:
                return None
        if aspect == Aspect.LOCATION:
            return self.yieldedFact.getparent()
        elif aspect == Aspect.CONCEPT:
            return self.yieldedFact.concept.qname
        elif self.yieldedFact.isTuple or self.yieldedFactContext is None:
            return None     #subsequent aspects don't exist for tuples
        elif aspect == Aspect.PERIOD:
            return self.yieldedFactContext.period
        elif aspect == Aspect.PERIOD_TYPE:
            if self.yieldedFactContext.isInstantPeriod: return "instant"
            elif self.yieldedFactContext.isStartEndPeriod: return "duration"
            elif self.yieldedFactContext.isForeverPeriod: return "forever"
            return None
        elif aspect == Aspect.INSTANT:
            return self.yieldedFactContext.instantDatetime
        elif aspect == Aspect.START:
            return self.yieldedFactContext.startDatetime
        elif aspect == Aspect.END:
            return self.yieldedFactContext.endDatetime
        elif aspect == Aspect.ENTITY_IDENTIFIER:
            return self.yieldedFactContext.entityIdentifierElement
        elif aspect == Aspect.SCHEME:
            return self.yieldedFactContext.entityIdentifier[0]
        elif aspect == Aspect.VALUE:
            return self.yieldedFactContext.entityIdentifier[1]
        elif aspect in (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO,
                        Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO):
            return self.yieldedFactContext.nonDimValues(aspect)
        elif aspect == Aspect.UNIT and self.yieldedFact.unit is not None:
            return self.yieldedFact.unit
        elif aspect in (Aspect.UNIT_MEASURES, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY):
            return self.yieldedFact.unit.measures
        elif aspect == Aspect.DIMENSIONS:
            return self.yieldedFactContext.dimAspects(self.xpCtx.defaultDimensionAspects)
        elif isinstance(aspect, QName):
            return self.yieldedFact.context.dimValue(aspect)
        return None
    