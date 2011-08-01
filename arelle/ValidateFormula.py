'''
Created on Dec 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from collections import defaultdict
from arelle.pyparsing.pyparsing_py3 import (ParseException) 
from arelle.ModelFormulaObject import (ModelParameter, ModelInstance,
                                       ModelFormula, ModelVariable, ModelFactVariable, 
                                       ModelVariableSetAssertion, ModelConsistencyAssertion,
                                       ModelExistenceAssertion, ModelValueAssertion,
                                       ModelPrecondition, ModelConceptName, Trace,
                                       Aspect, aspectModels, ModelAspectCover)
from arelle.ModelObject import (ModelObject)
from arelle.ModelValue import (qname,QName)
from arelle import (XbrlConst, XmlUtil, ModelXbrl, ModelDocument, XPathParser, XPathContext, FunctionXs) 

arcroleChecks = {
    XbrlConst.equalityDefinition:   (None, 
                                     XbrlConst.qnEqualityDefinition, 
                                     "xbrlve:info"),
    XbrlConst.assertionSet:          (XbrlConst.qnAssertionSet,
                                      (XbrlConst.qnAssertion, XbrlConst.qnVariableSetAssertion),
                                      "xbrlvalide:info"),
    XbrlConst.variableSet:           (XbrlConst.qnVariableSet,
                                      (XbrlConst.qnVariableVariable, XbrlConst.qnParameter),
                                      "xbrlve:info"),
    XbrlConst.variableSetFilter:    (XbrlConst.qnVariableSet, 
                                     XbrlConst.qnVariableFilter, 
                                     "xbrlve:info"),
    XbrlConst.variableFilter:       (XbrlConst.qnFactVariable, 
                                     XbrlConst.qnVariableFilter, 
                                     "xbrlve:info"),
    XbrlConst.booleanFilter:        (XbrlConst.qnVariableFilter, 
                                     XbrlConst.qnVariableFilter, 
                                     "xbrlbfe:info"),
   XbrlConst.consistencyAssertionFormula:       (XbrlConst.qnConsistencyAssertion, 
                                                 None, 
                                     "xbrlca:info"),
    XbrlConst.functionImplementation: (XbrlConst.qnCustomFunctionSignature,
                                      XbrlConst.qnCustomFunctionImplementation,
                                      "xbrlcfie:info"),
    }
def checkBaseSet(val, arcrole, ELR, relsSet):
    # check hypercube-dimension relationships
     
    if arcrole in arcroleChecks:
        fromQname, toQname, errCode = arcroleChecks[arcrole]
        for modelRel in relsSet.modelRelationships:
            fromMdlObj = modelRel.fromModelObject
            toMdlObj = modelRel.toModelObject
            if fromQname:
                if fromMdlObj is None or not val.modelXbrl.isInSubstitutionGroup(fromMdlObj.elementQname, fromQname):
                    val.modelXbrl.info(errCode,
                        _("Relationship from %(xlinkFrom)s to %(xlinkTo)s should have an %(element)s source"),
                        modelObject=modelRel, xlinkFrom=modelRel.fromLabel, xlinkTo=modelRel.toLabel, element=fromQname)
            if toQname:
                if toMdlObj is None or not val.modelXbrl.isInSubstitutionGroup(toMdlObj.elementQname, toQname):
                    val.modelXbrl.info(errCode,
                        _("Relationship from %(xlinkFrom)s to %(xlinkTo)s should have an %(element)s  target"),
                        modelObject=modelRel, xlinkFrom=modelRel.fromLabel, xlinkTo=modelRel.toLabel, element=toQname)
    if arcrole == XbrlConst.functionImplementation:
        for relFrom, rels in relsSet.fromModelObjects().items():
            if len(rels) > 1:
                val.modelXbrl.error("xbrlcfie:tooManyCFIRelationships",
                    _("Function-implementation relationship from signature %(name)s has more than one implementation target"),
                     modelObject=modelRel, name=relFrom.name)
        for relTo, rels in relsSet.toModelObjects().items():
            if len(rels) > 1:
                val.modelXbrl.error("xbrlcfie:tooManyCFIRelationships",
                    _("Function implementation %(xlinkLabel)s must be the target of only one function-implementation relationship"),
                    modelObject=modelRel, xlinkLabel=relTo.xlinkLabel)
                
def executeCallTest(val, name, callTuple, testTuple):
    if callTuple:
        XPathParser.initializeParser(val)
        
        try:                            
            val.modelXbrl.modelManager.showStatus(_("Executing call"))
            callExprStack = XPathParser.parse(val, callTuple[0], callTuple[1], name + " call", Trace.CALL)
            xpathContext = XPathContext.create(val.modelXbrl, sourceElement=callTuple[1])
            result = xpathContext.evaluate(callExprStack)
            xpathContext.inScopeVars[qname('result',noPrefixIsNoNamespace=True)] = result 
            val.modelXbrl.info("formula:trace", 
                               _("%(name)s result %(result)s"), 
                               modelObject=callTuple[1], name=name, result=str(result))
            
            if testTuple:
                val.modelXbrl.modelManager.showStatus(_("Executing test"))
                testExprStack = XPathParser.parse(val, testTuple[0], testTuple[1], name + " test", Trace.CALL)
                testResult = xpathContext.effectiveBooleanValue( None, xpathContext.evaluate(testExprStack) )
                
                if testResult:
                    val.modelXbrl.info("cfcn:testPass",
                                       _("Test %(name)s result %(result)s"), 
                                       modelObject=testTuple[1], name=name, result=str(testResult))
                else:
                    val.modelXbrl.error("cfcn:testFail",
                                        _("Test %(name)s result %(result)s"), 
                                        modelObject=testTuple[1], name=name, result=str(testResult))
        except XPathContext.XPathException as err:
            val.modelXbrl.error(err.code,
                _("%(name)s evaluation error: %(error)s \n%(errorSource)s"),
                modelObject=callTuple[1], name=name, error=err.message, errorSource=err.sourceErrorIndication)

        val.modelXbrl.modelManager.showStatus(_("ready"), 2000)
                
def validate(val):
    formulaOptions = val.modelXbrl.modelManager.formulaOptions
    XPathParser.initializeParser(val)
    val.modelXbrl.modelManager.showStatus(_("Compiling formulae"))
    initialErrorCount = val.modelXbrl.logCountErr
    
    # global parameter names
    parameterQnames = set()
    instanceQnames = set()
    parameterDependencies = {}
    instanceDependencies = defaultdict(set)  # None-key entries are non-formula dependencies
    dependencyResolvedParameters = set()
    orderedParameters = []
    orderedInstances = []
    for paramQname, modelParameter in val.modelXbrl.qnameParameters.items():
        if isinstance(modelParameter, ModelParameter):
            modelParameter.compile()
            parameterDependencies[paramQname] = modelParameter.variableRefs()
            parameterQnames.add(paramQname)
            if isinstance(modelParameter, ModelInstance):
                instanceQnames.add(paramQname)
            # duplicates checked on loading modelDocument
            
    #resolve dependencies
    resolvedAParameter = True
    while (resolvedAParameter):
        resolvedAParameter = False
        for paramQname in parameterQnames:
            if paramQname not in dependencyResolvedParameters and \
               len(parameterDependencies[paramQname] - dependencyResolvedParameters) == 0:
                dependencyResolvedParameters.add(paramQname)
                orderedParameters.append(paramQname)
                resolvedAParameter = True
    # anything unresolved?
    for paramQname in parameterQnames:
        if paramQname not in dependencyResolvedParameters:
            circularOrUndefDependencies = parameterDependencies[paramQname] - dependencyResolvedParameters
            undefinedVars = circularOrUndefDependencies - parameterQnames 
            paramsCircularDep = circularOrUndefDependencies - undefinedVars
            if len(undefinedVars) > 0:
                val.modelXbrl.error("xbrlve:unresolvedDependency",
                    _("Undefined dependencies in parameter %(name)s, to names %(dependencies)s"),
                    modelObject=val.modelXbrl.qnameParameters[paramQname],
                    name=paramQname, dependencies=", ".join((str(v) for v in undefinedVars)))
            if len(paramsCircularDep) > 0:
                val.modelXbrl.error("xbrlve:parameterCyclicDependencies",
                    _("Cyclic dependencies in parameter %(name)s, to names %(dependencies)s"),
                    modelObject=val.modelXbrl.qnameParameters[paramQname],
                    name=paramQname, dependencies=", ".join((str(d) for d in paramsCircularDep)) )
            
    for custFnSig in val.modelXbrl.modelCustomFunctionSignatures.values():
        custFnQname = custFnSig.qname
        if custFnQname.namespaceURI == "XbrlConst.xfi":
            val.modelXbrl.error("xbrlve:noProhibitedNamespaceForCustomFunction",
                _("Custom function %(name)s has namespace reserved for functions in the function registry %(namespace)s"),
                modelObject=custFnSig, name=custFnQname, namespace=custFnQname.namespaceURI )
        # any custom function implementations?
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.functionImplementation).fromModelObject(custFnSig):
            custFnImpl = modelRel.toModelObject
            custFnSig.customFunctionImplementation = custFnImpl
            if len(custFnImpl.inputNames) != len(custFnSig.inputTypes):
                val.modelXbrl.error("xbrlcfie:inputMismatch",
                    _("Custom function %(name)s signature has %(parameterCountSignature)s parameters but implementation has %(parameterCountImplementation)s, must be matching"),
                    modelObject=custFnSig, name=custFnQname, 
                    parameterCountSignature=len(custFnSig.inputTypes), parameterCountImplementation=len(custFnImpl.inputNames) )
        
    for custFnImpl in val.modelXbrl.modelCustomFunctionImplementations:
        if not val.modelXbrl.relationshipSet(XbrlConst.functionImplementation).toModelObject(custFnImpl):
            val.modelXbrl.error("xbrlcfie:missingCFIRelationship",
                _("Custom function implementation %(xlinkLabel)s has no relationship from any custom function signature"),
                modelObject=custFnSig, xlinkLabel=custFnImpl.xlinkLabel)
        custFnImpl.compile()
            
    # xpathContext is needed for filter setup for expressions such as aspect cover filter
    # determine parameter values
    xpathContext = XPathContext.create(val.modelXbrl)
    for paramQname in orderedParameters:
        modelParameter = val.modelXbrl.qnameParameters[paramQname]
        if not isinstance(modelParameter, ModelInstance):
            asType = modelParameter.asType
            asLocalName = asType.localName if asType else "string"
            try:
                if val.parameters and paramQname in val.parameters:
                    paramDataType, paramValue = val.parameters[paramQname]
                    typeLocalName = paramDataType.localName if paramDataType else "string"
                    value = FunctionXs.call(xpathContext, None, typeLocalName, [paramValue])
                    result = FunctionXs.call(xpathContext, None, asLocalName, [value])
                    if formulaOptions.traceParameterInputValue:
                        val.modelXbrl.info("formula:trace",
                            _("Parameter %(name)s input value %(input)s"), 
                            modelObject=modelParameter, name=paramQname, input=result)
                else:
                    result = modelParameter.evaluate(xpathContext, asType)
                    if formulaOptions.traceParameterExpressionResult:
                        val.modelXbrl.info("formula:trace",
                            _("Parameter %(name)s select result %(result)s"), 
                            modelObject=modelParameter, name=paramQname, result=result)
                xpathContext.inScopeVars[paramQname] = result    # make visible to subsequent parameter expression 
            except XPathContext.XPathException as err:
                val.modelXbrl.error("xbrlve:parameterTypeMismatch" if err.code == "err:FORG0001" else err.code,
                    _("Parameter \n%(name)s \nException: \n%(error)s"), 
                    modelObject=modelParameter, name=paramQname, error=err.message)

    produceOutputXbrlInstance = False
    instanceProducingVariableSets = defaultdict(list)
        
    for modelVariableSet in val.modelXbrl.modelVariableSets:
        varSetInstanceDependencies = set()
        if isinstance(modelVariableSet, ModelFormula):
            instanceQname = None
            for modelRel in val.modelXbrl.relationshipSet(XbrlConst.formulaInstance).fromModelObject(modelVariableSet):
                instance = modelRel.toModelObject
                if isinstance(instance, ModelInstance):
                    if instanceQname is None:
                        instanceQname = instance.qname
                    else:
                        val.modelXbrl.info("arelle:multipleOutputInstances",
                            _("Multiple output instances for formula %(xlinkLabel)s, to names %(instanceTo)s, %(instanceTo2)s"),
                            modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                            instanceTo=instanceQname, instanceTo2=instance.qname)
            if instanceQname is None: 
                instanceQname = XbrlConst.qnStandardOutputInstance
                instanceQnames.add(instanceQname)
            modelVariableSet.outputInstanceQname = instanceQname
            if val.validateSBRNL:
                val.modelXbrl.error("SBR.NL.2.3.9.03",
                    _("Formula:formula %(xlinkLabel)s is not allowed"),
                    modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel)
        else:
            instanceQname = None
            modelVariableSet.countSatisfied = 0
            modelVariableSet.countNotSatisfied = 0
            checkValidationMessages(val, modelVariableSet)
        instanceProducingVariableSets[instanceQname].append(modelVariableSet)
        modelVariableSet.outputInstanceQname = instanceQname
        if modelVariableSet.aspectModel not in ("non-dimensional", "dimensional"):
            val.modelXbrl.error("xbrlve:unknownAspectModel",
                _("Variable set %(xlinkLabel)s, aspect model %(aspectModel)s not recognized"),
                modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, aspectModel=modelVariableSet.aspectModel)
        modelVariableSet.compile()
        modelVariableSet.hasConsistencyAssertion = False
            
        #determine dependencies within variable sets
        nameVariables = {}
        qnameRels = {}
        definedNamesSet = set()
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSet).fromModelObject(modelVariableSet):
            varqname = modelRel.variableQname
            if varqname:
                qnameRels[varqname] = modelRel
                toVariable = modelRel.toModelObject
                if varqname not in definedNamesSet:
                    definedNamesSet.add(varqname)
                if varqname not in nameVariables:
                    nameVariables[varqname] = toVariable
                elif nameVariables[varqname] != toVariable:
                    val.modelXbrl.error("xbrlve:duplicateVariableNames",
                        _("Multiple variables named %(xlinkLabel)s in variable set %(name)s"),
                        modelObject=toVariable, xlinkLabel=modelVariableSet.xlinkLabel, name=varqname )
                fromInstanceQnames = None
                for instRel in val.modelXbrl.relationshipSet(XbrlConst.instanceVariable).toModelObject(toVariable):
                    fromInstance = instRel.fromModelObject
                    if isinstance(fromInstance, ModelInstance):
                        fromInstanceQname = fromInstance.qname
                        varSetInstanceDependencies.add(fromInstanceQname)
                        instanceDependencies[instanceQname].add(fromInstanceQname)
                        if fromInstanceQnames is None: fromInstanceQnames = set()
                        fromInstanceQnames.add(fromInstanceQname)
                if fromInstanceQnames is None:
                    varSetInstanceDependencies.add(XbrlConst.qnStandardInputInstance)
                    if instanceQname: instanceDependencies[instanceQname].add(XbrlConst.qnStandardInputInstance)
                toVariable.fromInstanceQnames = fromInstanceQnames
            else:
                val.modelXbrl.error("xbrlve:variableNameResolutionFailure",
                    _("Variables name %(name)s cannot be determined on arc from %(xlinkLabel)s"),
                    modelObject=modelRel, xlinkLabel=modelVariableSet.xlinkLabel, name=modelRel.variablename )
        definedNamesSet |= parameterQnames
                
        variableDependencies = {}
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSet).fromModelObject(modelVariableSet):
            variable = modelRel.toModelObject
            if isinstance(variable, (ModelParameter,ModelVariable)):    # ignore anything not parameter or variable
                varqname = modelRel.variableQname
                depVars = variable.variableRefs()
                variableDependencies[varqname] = depVars
                if len(depVars) > 0 and formulaOptions.traceVariablesDependencies:
                    val.modelXbrl.info("formula:trace",
                        _("Variable set %(xlinkLabel)s, variable %(name)s, dependences %(dependencies)s"),
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                        name=varqname, dependencies=depVars)
                definedNamesSet.add(varqname)
                # check for fallback value variable references
                if isinstance(variable, ModelFactVariable):
                    for depVar in XPathParser.variableReferencesSet(variable.fallbackValueProg, variable):
                        if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                            val.modelXbrl.error("xbrlve:factVariableReferenceNotAllowed",
                                _("Variable set %(xlinkLabel)s fallbackValue '%(fallbackValue)s' cannot refer to variable %(dependency)s"),
                                modelObject=variable, xlinkLabel=modelVariableSet.xlinkLabel, 
                                fallbackValue=variable.fallbackValue, dependency=depVar)
                    # check for covering aspect not in variable set aspect model
                    checkFilterAspectModel(val, modelVariableSet, variable.filterRelationships, xpathContext)

        orderedNameSet = set()
        orderedNameList = []
        orderedAVariable = True
        while (orderedAVariable):
            orderedAVariable = False
            for varqname, depVars in variableDependencies.items():
                if varqname not in orderedNameSet and len(depVars - parameterQnames - orderedNameSet) == 0:
                    orderedNameList.append(varqname)
                    orderedNameSet.add(varqname)
                    orderedAVariable = True
                if varqname in instanceQnames:
                    varSetInstanceDependencies.add(varqname)
                    instanceDependencies[instanceQname].add(varqname)
                elif isinstance(nameVariables.get(varqname), ModelInstance):
                    instqname = nameVariables[varqname].qname
                    varSetInstanceDependencies.add(instqname)
                    instanceDependencies[instanceQname].add(instqname)
                    
        # anything unresolved?
        for varqname, depVars in variableDependencies.items():
            if varqname not in orderedNameSet:
                circularOrUndefVars = depVars - parameterQnames - orderedNameSet
                undefinedVars = circularOrUndefVars - definedNamesSet 
                varsCircularDep = circularOrUndefVars - undefinedVars
                if len(undefinedVars) > 0:
                    val.modelXbrl.error("xbrlve:unresolvedDependency",
                        _("Undefined variable dependencies in variable set %(xlinkLabel)s, from variable %(nameFrom)s to %(nameTo)s"),
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                        nameFrom=varqname, nameTo=undefinedVars)
                if len(varsCircularDep) > 0:
                    val.modelXbrl.error("xbrlve:cyclicDependencies",
                        _("Cyclic dependencies in variable set %(xlinkLabel)s, from variable %(nameFrom)s to %(nameTo)s"),
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                        nameFrom=varqname, nameTo=varsCircularDep )
                    
        # check unresolved variable set dependencies
        for varSetDepVarQname in modelVariableSet.variableRefs():
            if varSetDepVarQname not in orderedNameSet and varSetDepVarQname not in parameterQnames:
                val.modelXbrl.error("xbrlve:unresolvedDependency",
                    _("Undefined variable dependency in variable set %(xlinkLabel)s, %(name)s"),
                    modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel,
                    name=varSetDepVarQname)
            if varSetDepVarQname in instanceQnames:
                varSetInstanceDependencies.add(varSetDepVarQname)
                instanceDependencies[instanceQname].add(varSetDepVarQname)
            elif isinstance(nameVariables.get(varSetDepVarQname), ModelInstance):
                instqname = nameVariables[varSetDepVarQname].qname
                varSetInstanceDependencies.add(instqname)
                instanceDependencies[instanceQname].add(instqname)
        
        if formulaOptions.traceVariablesOrder:
            val.modelXbrl.info("formula:trace",
                   _("Variable set %(xlinkLabel)s, variables order: %(dependencies)s"),
                   modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, dependencies=orderedNameList)
        
        if (formulaOptions.traceVariablesDependencies and len(varSetInstanceDependencies) > 0 and
            varSetInstanceDependencies != {XbrlConst.qnStandardInputInstance}):
            val.modelXbrl.info("formula:trace",
                   _("Variable set %(xlinkLabel)s, instance dependences %(dependencies)s"),
                   modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, dependencies=varSetInstanceDependencies)
            
        modelVariableSet.orderedVariableRelationships = []
        for varqname in orderedNameList:
            if varqname in qnameRels:
                modelVariableSet.orderedVariableRelationships.append(qnameRels[varqname])
                
        # check existence assertion variable dependencies
        if isinstance(modelVariableSet, ModelExistenceAssertion):
            for depVar in modelVariableSet.variableRefs():
                if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                    val.modelXbrl.error("xbrleae:variableReferenceNotAllowed",
                        _("Existence Assertion %(xlinkLabel)s, cannot refer to variable %(name)s"),
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, name=depVar)
                    
        # check messages variable dependencies
        checkValidationMessageVariables(val, modelVariableSet, qnameRels)
                        
        # check preconditions
        modelVariableSet.preconditions = []
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSetPrecondition).fromModelObject(modelVariableSet):
            precondition = modelRel.toModelObject
            if isinstance(precondition, ModelPrecondition):
                modelVariableSet.preconditions.append(precondition)
                
        # check for variable sets referencing fact or general variables
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSetFilter).fromModelObject(modelVariableSet):
            varSetFilter = modelRel.toModelObject
            if modelRel.isCovered:
                val.modelXbrl.warning("arelle:variableSetFilterCovered",
                    _("Variable set %(xlinkLabel)s, filter %(filterLabel)s, cannot be covered"),
                     modelObject=varSetFilter, xlinkLabel=modelVariableSet.xlinkLabel, filterLabel=varSetFilter.xlinkLabel)
                modelRel._isCovered = False # block group filter from being able to covere
            for depVar in varSetFilter.variableRefs():
                if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                    val.modelXbrl.error("xbrlve:factVariableReferenceNotAllowed",
                        _("Variable set %(xlinkLabel)s, filter %(filterLabel)s, cannot refer to variable %(name)s"),
                        modelObject=varSetFilter, xlinkLabel=modelVariableSet.xlinkLabel, filterLabel=varSetFilter.xlinkLabel, name=depVar)
                    
        # check aspects of formula
        if isinstance(modelVariableSet, ModelFormula):
            checkFormulaRules(val, modelVariableSet, nameVariables)
            
    # determine instance dependency order
    orderedInstancesSet = set()
    stdInpInst = {XbrlConst.qnStandardInputInstance}
    orderedInstancesList = []
    orderedAnInstance = True
    while (orderedAnInstance):
        orderedAnInstance = False
        for instqname, depInsts in instanceDependencies.items():
            if instqname and instqname not in orderedInstancesSet and len(depInsts - stdInpInst - orderedInstancesSet) == 0:
                orderedInstancesList.append(instqname)
                orderedInstancesSet.add(instqname)
                orderedAnInstance = True
    # add instances with variable sets with no variables or other dependencies
    for independentInstance in instanceProducingVariableSets.keys() - orderedInstancesList:
        orderedInstancesList.append(independentInstance)
        orderedInstancesSet.add(independentInstance)
    if None not in orderedInstancesList:
        orderedInstancesList.append(None)  # assertions come after all formulas that produce outputs

    # anything unresolved?
    for instqname, depInsts in instanceDependencies.items():
        if instqname not in orderedInstancesSet:
            # can also be satisfied from an input DTS
            missingDependentInstances = depInsts - stdInpInst
            if val.parameters: missingDependentInstances -= val.parameters.keys() 
            if instqname:
                if missingDependentInstances:
                    val.modelXbrl.error("xbrlvarinste:instanceVariableRecursionCycle",
                        _("Cyclic dependencies of instance %(name)s produced by a formula, with variables consuming instances %(dependencies)s"),
                        modelObject=val.modelXbrl,
                        name=instqname, dependencies=missingDependentInstances )
                elif instqname == XbrlConst.qnStandardOutputInstance:
                    orderedInstancesSet.add(instqname)
                    orderedInstancesList.append(instqname) # standard output formula, all input dependencies in parameters
            ''' future check?  if instance has no external input or producing formula
            else:
                val.modelXbrl.error("xbrlvarinste:instanceVariableRecursionCycle",
                    _("Unresolved dependencies of an assertion's variables on instances %(dependencies)s"),
                    dependencies=str(depInsts - stdInpInst) )
            '''

    if formulaOptions.traceVariablesOrder and len(orderedInstancesList) > 1:
        val.modelXbrl.info("formula:trace",
               _("Variable instances processing order: %(dependencies)s"),
                modelObject=val.modelXbrl, dependencies=orderedInstancesList)

    # linked consistency assertions
    for modelRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).modelRelationships:
        if (modelRel.fromModelObject is not None and modelRel.toModelObject is not None and 
            isinstance(modelRel.toModelObject,ModelFormula)):
            consisAsser = modelRel.fromModelObject
            consisAsser.countSatisfied = 0
            consisAsser.countNotSatisfied = 0
            if consisAsser.hasProportionalAcceptanceRadius and consisAsser.hasAbsoluteAcceptanceRadius:
                val.modelXbrl.error("xbrlcae:acceptanceRadiusConflict",
                    _("Consistency assertion %(xlinkLabel)s has both absolute and proportional acceptance radii"), 
                    modelObject=consisAsser, xlinkLabel=consisAsser.xlinkLabel)
            consisAsser.orderedVariableRelationships = []
            for consisParamRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionParameter).fromModelObject(consisAsser):
                if isinstance(consisParamRel.toModelObject, ModelVariable):
                    val.modelXbrl.error("xbrlcae:variablesNotAllowed",
                        _("Consistency assertion %(xlinkLabel)s has relationship to a %(elementTo)s %(xlinkLabelTo)s"),
                        modelObject=consisAsser, xlinkLabel=consisAsser.xlinkLabel, 
                        elementTo=consisParamRel.toModelObject.localName, xlinkLabelTo=consisParamRel.toModelObject.xlinkLabel)
                else:
                    consisAsser.orderedVariableRelationships.append(consisParamRel)
            consisAsser.compile()
            modelRel.toModelObject.hasConsistencyAssertion = True

    if initialErrorCount < val.modelXbrl.logCountErr:
        return  # don't try to execute
        

    # formula output instances    
    if instanceQnames:      
        schemaRefs = [val.modelXbrl.modelDocument.relativeUri(referencedDoc.uri)
                        for referencedDoc in val.modelXbrl.modelDocument.referencesDocument.keys()
                            if referencedDoc.type == ModelDocument.Type.SCHEMA]
        
    outputXbrlInstance = None
    for instanceQname in instanceQnames:
        if instanceQname == XbrlConst.qnStandardInputInstance:
            continue    # always present the standard way
        if val.parameters and instanceQname in val.parameters:
            namedInstance = val.parameters[instanceQname][1]
        else:   # empty intermediate instance 
            uri = val.modelXbrl.modelDocument.filepath[:-4] + "-output-XBRL-instance"
            if instanceQname != XbrlConst.qnStandardOutputInstance:
                uri = uri + "-" + instanceQname.localName
            uri = uri + ".xml"
            namedInstance = ModelXbrl.create(val.modelXbrl.modelManager, 
                                             newDocumentType=ModelDocument.Type.INSTANCE,
                                             url=uri,
                                             schemaRefs=schemaRefs,
                                             isEntry=True)
        xpathContext.inScopeVars[instanceQname] = namedInstance
        if instanceQname == XbrlConst.qnStandardOutputInstance:
            outputXbrlInstance = namedInstance
        
    # evaluate consistency assertions
    
    # evaluate variable sets not in consistency assertions
    for instanceQname in orderedInstancesList:
        for modelVariableSet in instanceProducingVariableSets[instanceQname]:
            # produce variable evaluations
            from arelle.FormulaEvaluator import evaluate
            try:
                evaluate(xpathContext, modelVariableSet)
            except XPathContext.XPathException as err:
                val.modelXbrl.error(err.code,
                    _("Variable set \n%(variableSet)s \nException: \n%(error)s"), 
                    modelObject=modelVariableSet, variableSet=str(modelVariableSet), error=err.message)
            
    # log assertion result counts
    asserTests = {}
    for exisValAsser in val.modelXbrl.modelVariableSets:
        if isinstance(exisValAsser, ModelVariableSetAssertion):
            asserTests[exisValAsser.id] = (exisValAsser.countSatisfied, exisValAsser.countNotSatisfied)
            if formulaOptions.traceAssertionResultCounts:
                val.modelXbrl.info("formula:trace",
                    _("%(assertionType)s Assertion %(id)s evaluations : %(satisfiedCount)s satisfied, %(notSatisfiedCount)s not satisfied"),
                    modelObject=exisValAsser,
                    assertionType="Existence" if isinstance(exisValAsser, ModelExistenceAssertion) else "Value", 
                    id=exisValAsser.id, satisfiedCount=exisValAsser.countSatisfied, notSatisfiedCount=exisValAsser.countNotSatisfied)

    for modelRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).modelRelationships:
        if modelRel.fromModelObject is not None and modelRel.toModelObject is not None and \
           isinstance(modelRel.toModelObject,ModelFormula):
            consisAsser = modelRel.fromModelObject
            asserTests[consisAsser.id] = (consisAsser.countSatisfied, consisAsser.countNotSatisfied)
            if formulaOptions.traceAssertionResultCounts:
                val.modelXbrl.info("formula:trace",
                   _("Consistency Assertion %(id)s evaluations : %(satisfiedCount) satisfied, %(notSatisfiedCount) not satisfied"),
                    modelObject=consisAsser, id=consisAsser.id, 
                    satisfiedCount=consisAsser.countSatisfied, notSatisfiedCount=consisAsser.countNotSatisfied)
            
    if asserTests: # pass assertion results to validation if appropriate
        val.modelXbrl.info("asrtNoLog", None, assertionResults=asserTests);

    # display output instance
    if outputXbrlInstance:
        if val.modelXbrl.formulaOutputInstance:
            # close prior instance, usually closed by caller to validate as it may affect UI on different thread
            val.modelXbrl.formulaOutputInstance.close()
        val.modelXbrl.formulaOutputInstance = outputXbrlInstance

def checkFilterAspectModel(val, variableSet, filterRelationships, xpathContext, uncoverableAspects=None):
    if uncoverableAspects is None:
        oppositeAspectModel = ({'dimensional','non-dimensional'} - {variableSet.aspectModel}).pop()
        try:
            uncoverableAspects = aspectModels[oppositeAspectModel] - aspectModels[variableSet.aspectModel]
        except KeyError:    # bad aspect model, not an issue for this test
            return
    acfAspectsCovering = {}
    for varFilterRel in filterRelationships:
        filter = varFilterRel.toModelObject
        isAllAspectCoverFilter = False
        if isinstance(filter, ModelAspectCover):
            for aspect in filter.aspectsCovered(None, xpathContext):
                if aspect in acfAspectsCovering:
                    otherFilterCover, otherFilterLabel = acfAspectsCovering[aspect]
                    if otherFilterCover != varFilterRel.isCovered:
                        val.modelXbrl.error("xbrlacfe:inconsistentAspectCoverFilters",
                            _("Variable set %(xlinkLabel)s, aspect cover filter %(filterLabel)s, aspect %(aspect)s, conflicts with %(filterLabel2)s with inconsistent cover attribute"),
                            modelObject=variableSet, xlinkLabel=variableSet.xlinkLabel, filterLabel=filter.xlinkLabel, 
                            aspect=str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect],
                            filterLabel2=otherFilterLabel)
                else:
                    acfAspectsCovering[aspect] = (varFilterRel.isCovered, filter.xlinkLabel)
            isAllAspectCoverFilter = filter.isAll
        if True: # changed for test case 50210 v03 varFilterRel.isCovered:
            try:
                aspectsCovered = filter.aspectsCovered(None)
                if (not isAllAspectCoverFilter and 
                    (any(isinstance(aspect,QName) for aspect in aspectsCovered) and Aspect.DIMENSIONS in uncoverableAspects
                     or (aspectsCovered & uncoverableAspects))):
                    val.modelXbrl.error("xbrlve:filterAspectModelMismatch",
                        _("Variable set %(xlinkLabel)s, aspect model %(aspectModel)s filter %(filterName)s %(filterLabel)s can cover aspect not in aspect model"),
                        modelObject=variableSet, xlinkLabel=variableSet.xlinkLabel, aspectModel=variableSet.aspectModel, 
                        filterName=filter.localName, filterLabel=filter.xlinkLabel)
            except Exception:
                pass
            if hasattr(filter, "filterRelationships"): # check and & or filters
                checkFilterAspectModel(val, variableSet, filter.filterRelationships, xpathContext, uncoverableAspects)
        
def checkFormulaRules(val, formula, nameVariables):
    from arelle.ModelFormulaObject import (Aspect)
    if not (formula.hasRule(Aspect.CONCEPT) or formula.source(Aspect.CONCEPT)):
        if XmlUtil.hasDescendant(formula, XbrlConst.formula, "concept"):
            val.modelXbrl.error("xbrlfe:incompleteConceptRule",
                _("Formula %(xlinkLabel)s concept rule does not have a nearest source and does not have a child element"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
        else:
            val.modelXbrl.error("xbrlfe:missingConceptRule",
                _("Formula %(xlinkLabel)s omits a rule for the concept aspect"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
    if (not (formula.hasRule(Aspect.SCHEME) or formula.source(Aspect.SCHEME)) or
        not (formula.hasRule(Aspect.VALUE) or formula.source(Aspect.VALUE))):
        if XmlUtil.hasDescendant(formula, XbrlConst.formula, "entityIdentifier"):
            val.modelXbrl.error("xbrlfe:incompleteEntityIdentifierRule",
                _("Formula %(xlinkLabel)s entity identifier rule does not have a nearest source and does not have either a @scheme or a @value attribute"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
        else:
            val.modelXbrl.error("xbrlfe:missingEntityIdentifierRule",
                _("Formula %(xlinkLabel)s omits a rule for the entity identifier aspect"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
    if not (formula.hasRule(Aspect.PERIOD_TYPE) or formula.source(Aspect.PERIOD_TYPE)):
        if XmlUtil.hasDescendant(formula, XbrlConst.formula, "period"):
            val.modelXbrl.error("xbrlfe:incompletePeriodRule",
                _("Formula %(xlinkLabel)s period rule does not have a nearest source and does not have a child element"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
        else:
            val.modelXbrl.error("xbrlfe:missingPeriodRule",
                _("Formula %(xlinkLabel)s omits a rule for the period aspect"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
    # for unit need to see if the qname is statically determinable to determine if numeric
    concept = val.modelXbrl.qnameConcepts.get(formula.evaluateRule(None, Aspect.CONCEPT))
    if concept is None: # is there a source with a static QName filter
        sourceFactVar = nameVariables.get(formula.source(Aspect.CONCEPT))
        if isinstance(sourceFactVar, ModelFactVariable):
            for varFilterRels in (formula.groupFilterRelationships, sourceFactVar.filterRelationships):
                for varFilterRel in varFilterRels:
                    filter = varFilterRel.toModelObject
                    if isinstance(filter,ModelConceptName):  # relationship not constrained to real filters
                        for conceptQname in filter.conceptQnames:
                            concept = val.modelXbrl.qnameConcepts.get(conceptQname)
                            if concept is not None and concept.isNumeric:
                                break
    if concept is not None: # from concept aspect rule or from source factVariable concept Qname filter
        if concept.isNumeric:
            if not (formula.hasRule(Aspect.MULTIPLY_BY) or formula.hasRule(Aspect.DIVIDE_BY) or formula.source(Aspect.UNIT)):
                if XmlUtil.hasDescendant(formula, XbrlConst.formula, "unit"):
                    val.modelXbrl.error("xbrlfe:missingSAVForUnitRule",
                        _("Formula %(xlinkLabel)s unit rule does not have a source and does not have a child element"),
                        modelObject=formula, xlinkLabel=formula.xlinkLabel)
                else:
                    val.modelXbrl.error("xbrlfe:missingUnitRule",
                        _("Formula %(xlinkLabel)s omits a rule for the unit aspect"),
                        modelObject=formula, xlinkLabel=formula.xlinkLabel)
        elif (formula.hasRule(Aspect.MULTIPLY_BY) or formula.hasRule(Aspect.DIVIDE_BY) or 
              formula.source(Aspect.UNIT, acceptFormulaSource=False)):
            val.modelXbrl.error("xbrlfe:conflictingAspectRules",
                _("Formula %(xlinkLabel)s has a rule for the unit aspect of a non-numeric concept %(concept)s"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel, concept=concept.qname)
        aspectPeriodType = formula.evaluateRule(None, Aspect.PERIOD_TYPE)
        if ((concept.periodType == "duration" and aspectPeriodType == "instant") or
            (concept.periodType == "instant" and aspectPeriodType in ("duration","forever"))):
            val.modelXbrl.error("xbrlfe:conflictingAspectRules",
                _("Formula %(xlinkLabel)s has a rule for the %(aspectPeriodType)s period aspect of a %(conceptPeriodType)s concept %(concept)s"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel, concept=concept.qname, aspectPeriodType=aspectPeriodType, conceptPeriodType=concept.periodType)
    
    # check dimension elements
    for eltName, dim, badUsageErr, missingSavErr in (("explicitDimension", "explicit", "xbrlfe:badUsageOfExplicitDimensionRule", "xbrlfe:missingSAVForExplicitDimensionRule"),
                                                     ("typedDimension", "typed", "xbrlfe:badUsageOfTypedDimensionRule", "xbrlfe:missingSAVForTypedDimensionRule")):
        for dimElt in XmlUtil.descendants(formula, XbrlConst.formula, eltName):
            dimQname = qname(dimElt, dimElt.get("dimension"))
            dimConcept = val.modelXbrl.qnameConcepts.get(dimQname)
            if dimQname and (dimConcept is None or (not dimConcept.isExplicitDimension if dim == "explicit" else not dimConcept.isTypedDimension)):
                val.modelXbrl.error(badUsageErr,
                    _("Formula %(xlinkLabel)s dimension attribute %(dimension)s on the %(dimensionType)s dimension rule contains a QName that does not identify an (dimensionType)s dimension."),
                    modelObject=formula, xlinkLabel=formula.xlinkLabel, dimensionType=dim, dimension=dimQname)
            elif not XmlUtil.hasChild(dimElt, XbrlConst.formula, "*") and not formula.source(Aspect.DIMENSIONS, dimElt):
                val.modelXbrl.error(missingSavErr,
                    _("Formula %(xlinkLabel)s %(dimension)s dimension rule does not have any child elements and does not have a SAV for the %(dimensionType)s dimension that is identified by its dimension attribute."),
                    modelObject=formula, xlinkLabel=formula.xlinkLabel, dimensionType=dim, dimension=dimQname)
    
    # check aspect model expectations
    if formula.aspectModel == "non-dimensional":
        unexpectedElts = XmlUtil.descendants(formula, XbrlConst.formula, ("explicitDimension", "typedDimension"))
        if unexpectedElts:
            val.modelXbrl.error("xbrlfe:unrecognisedAspectRule",
                _("Formula %(xlinkLabel)s aspect model, %(aspectModel)s, includes an rule for aspect not defined in this aspect model: %(undefinedAspects)s"),
                modelObject=formula, xlinkLabel=formula.xlinkLabel, aspectModel=formula.aspectModel, undefinedAspects=", ".join([elt.localName for elt in unexpectedElts]))

    # check source qnames
    for sourceElt in ([formula] + 
                     XmlUtil.descendants(formula, XbrlConst.formula, "*", "source","*")):
        if sourceElt.get("source") is not None:
            qnSource = qname(sourceElt, sourceElt.get("source"), noPrefixIsNoNamespace=True)
            if qnSource == XbrlConst.qnFormulaUncovered:
                if formula.implicitFiltering != "true":
                    val.modelXbrl.error("xbrlfe:illegalUseOfUncoveredQName",
                        _("Formula %(xlinkLabel)s, not implicit filtering element has formulaUncovered source: %(name)s"),
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=sourceElt.localName) 
            elif qnSource not in nameVariables:
                val.modelXbrl.error("xbrlfe:nonexistentSourceVariable",
                    _("Variable set %(xlinkLabel)s, source %(name)s is not in the variable set"),
                    modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource)
            else:
                factVariable = nameVariables.get(qnSource)
                if not isinstance(factVariable, ModelFactVariable):
                    val.modelXbrl.error("xbrlfe:nonexistentSourceVariable",
                        _("Variable set %(xlinkLabel)s, source %(name)s not a factVariable but is a %(element)s"),
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource, element=factVariable.localName)
                elif factVariable.fallbackValue is not None:
                    val.modelXbrl.error("xbrlfe:bindEmptySourceVariable",
                        _("Formula %(xlinkLabel)s: source %(name)s is a fact variable that has a fallback value"),
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource)
                elif sourceElt.localName == "formula" and factVariable.bindAsSequence == "true":
                    val.modelXbrl.error("xbrlfe:defaultAspectValueConflicts",
                        _("Formula %(xlinkLabel)s: formula source %(name)s is a fact variable that binds as a sequence"),
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource)
                
def checkValidationMessages(val, modelVariableSet):
    for msgRelationship in (XbrlConst.assertionSatisfiedMessage, XbrlConst.assertionUnsatisfiedMessage):
        for modelRel in val.modelXbrl.relationshipSet(msgRelationship).fromModelObject(modelVariableSet):
            message = modelRel.toModelObject
            if not hasattr(message,"expressions"):
                formatString = []
                expressions = []
                bracketNesting = 0
                skipTo = None
                expressionIndex = 0
                expression = None
                lastC = None
                for c in message.text:
                    if skipTo:
                        if c == skipTo:
                            skipTo = None
                    if expression is not None and c in ('\'', '"'):
                        skipTo = c
                    elif lastC == c and c in ('{','}'):
                        lastC = None
                    elif lastC == '{': 
                        bracketNesting += 1
                        expression = []
                        lastC = None
                    elif c == '}' and expression is not None: 
                        expressions.append( ''.join(expression).strip() )
                        expression = None
                        formatString.append( "0[{0}]".format(expressionIndex) )
                        expressionIndex += 1
                        lastC = c
                    elif lastC == '}':
                        bracketNesting -= 1
                        lastC = None
                    else:
                        lastC = c
                        
                    if expression is not None: expression.append(c)
                    else: formatString.append(c)
                    
                if lastC == '}':
                    bracketNesting -= 1
                if bracketNesting:
                    val.modelXbrl.error("xbrlmsge:missingLeftCurlyBracketInMessage" if bracketNesting < 0 else "xbrlmsge:missingRightCurlyBracketInMessage",
                        _("Message %(xlinkLabel)s: unbalanced %(character)s character(s) in: %(text)s"),
                        modelObject=message, xlinkLabel=message.xlinkLabel, 
                        character='{' if bracketNesting < 0 else '}', 
                        text=message.text)
                else:
                    message.expressions = expressions
                    message.formatString = ''.join( formatString )

def checkValidationMessageVariables(val, modelVariableSet, varNames):
    if isinstance(modelVariableSet, ModelConsistencyAssertion):
        varSetVars = (qname(XbrlConst.ca,'aspect-matched-facts'),
                      qname(XbrlConst.ca,'acceptance-radius'),
                      qname(XbrlConst.ca,'absolute-acceptance-radius-expression'),
                      qname(XbrlConst.ca,'proportional-acceptance-radius-expression'))
    elif isinstance(modelVariableSet, ModelExistenceAssertion):
        varSetVars = (qname(XbrlConst.ea,'text-expression'),)
    elif isinstance(modelVariableSet, ModelValueAssertion):
        varSetVars = (qname(XbrlConst.va,'text-expression'),)
    for msgRelationship in (XbrlConst.assertionSatisfiedMessage, XbrlConst.assertionUnsatisfiedMessage):
        for modelRel in val.modelXbrl.relationshipSet(msgRelationship).fromModelObject(modelVariableSet):
            message = modelRel.toModelObject
            message.compile()
            for msgVarQname in message.variableRefs():
                if msgVarQname not in varNames and msgVarQname not in varSetVars:
                    val.modelXbrl.error("err:XPST0008",
                        _("Undefined variable dependency in message %(xlinkLabel)s, %(name)s"),
                        modelObject=message, xlinkLabel=message.xlinkLabel, name=msgVarQname)
