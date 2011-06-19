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
                                      XbrlConst.qnAssertion,
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
                    val.modelXbrl.error(
                        _("{0} relationship from {1} to {2} should have an {3} source").format(
                              os.path.basename(arcrole), modelRel.fromLabel, modelRel.toLabel,
                              fromQname), 
                        "info", errCode)
            if toQname:
                if toMdlObj is None or not val.modelXbrl.isInSubstitutionGroup(toMdlObj.elementQname, toQname):
                    val.modelXbrl.error(
                        _("{0} relationship from {1} to {2} should have an {3} target").format(
                              os.path.basename(arcrole), modelRel.fromLabel, modelRel.toLabel,
                              toQname), 
                        "info", errCode)
    if arcrole == XbrlConst.functionImplementation:
        for relFrom, rels in relsSet.fromModelObjects().items():
            if len(rels) > 1:
                val.modelXbrl.error(
                    _("Function-implementation relationship from signature {0} has more than one implementation target").format(
                          relFrom.name), 
                    "err", "xbrlcfie:tooManyCFIRelationships")                
        for relTo, rels in relsSet.toModelObjects().items():
            if len(rels) > 1:
                val.modelXbrl.error(
                    _("Function implementation {0} must be the target of only one function-implementation relationship").format(
                          relTo.xlinkLabel), 
                    "err", "xbrlcfie:tooManyCFIRelationships")
                
def executeCallTest(val, name, callTuple, testTuple):
    if callTuple:
        XPathParser.initializeParser(val)
        
        try:                            
            val.modelXbrl.modelManager.showStatus(_("Executing call"))
            callExprStack = XPathParser.parse(val, callTuple[0], callTuple[1], name + " call", Trace.CALL)
            xpathContext = XPathContext.create(val.modelXbrl, sourceElement=callTuple[1])
            result = xpathContext.evaluate(callExprStack)
            xpathContext.inScopeVars[qname('result',noPrefixIsNoNamespace=True)] = result 
            val.modelXbrl.error( _("{0} result {1}").format( name, result),
                "info", "formula:trace")
            
            if testTuple:
                val.modelXbrl.modelManager.showStatus(_("Executing test"))
                testExprStack = XPathParser.parse(val, testTuple[0], testTuple[1], name + " test", Trace.CALL)
                testResult = xpathContext.effectiveBooleanValue( None, xpathContext.evaluate(testExprStack) )
                
                val.modelXbrl.error(
                    _("Test {0} result {1}").format( name, testResult), 
                    "info" if testResult else "err", 
                    "cfcn:testPass" if testResult else "cfcn:testFail")
        except XPathContext.XPathException as err:
            val.modelXbrl.error(
                _("{0} evaluation error: {1} \n{2}").format(name,
                     err.message, err.sourceErrorIndication), 
                "err", err.code)

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
                val.modelXbrl.error(
                    _("Undefined dependencies in parameter {0}, to names {1}").format(
                          paramQname, ", ".join((str(v) for v in undefinedVars))), 
                    "err", "xbrlve:unresolvedDependency")
            if len(paramsCircularDep) > 0:
                val.modelXbrl.error(
                    _("Cyclic dependencies in parameter {0}, to names {1}").format(
                          paramQname, ", ".join((str(d) for d in paramsCircularDep)) ), 
                    "err", "xbrlve:parameterCyclicDependencies")
            
    for custFnSig in val.modelXbrl.modelCustomFunctionSignatures.values():
        custFnQname = custFnSig.qname
        if custFnQname.namespaceURI == "XbrlConst.xfi":
            val.modelXbrl.error(
                _("Custom function {0} has namespace reserved for functions in the function registry {1}").format(
                      str(custFnQname), custFnQname.namespaceURI ), 
                "err", "xbrlve:noProhibitedNamespaceForCustomFunction")
        # any custom function implementations?
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.functionImplementation).fromModelObject(custFnSig):
            custFnImpl = modelRel.toModelObject
            custFnSig.customFunctionImplementation = custFnImpl
            if len(custFnImpl.inputNames) != len(custFnSig.inputTypes):
                val.modelXbrl.error(
                    _("Custom function {0} signature has {1} parameters but implementation has {2}, must be matching").format(
                          str(custFnQname), len(custFnSig.inputTypes), len(custFnImpl.inputNames) ), 
                    "err", "xbrlcfie:inputMismatch")
        
    for custFnImpl in val.modelXbrl.modelCustomFunctionImplementations:
        if not val.modelXbrl.relationshipSet(XbrlConst.functionImplementation).toModelObject(custFnImpl):
            val.modelXbrl.error(
                _("Custom function implementation {0} has no relationship from any custom function signature").format(
                      custFnImpl.xlinkLabel), 
                "err", "xbrlcfie:missingCFIRelationship")
        custFnImpl.compile()
            
    # xpathContext is needed for filter setup for expressions such as aspect cover filter
    # determine parameter values
    xpathContext = XPathContext.create(val.modelXbrl)
    for paramQname in orderedParameters:
        if not isinstance(modelParameter, ModelInstance):
            modelParameter = val.modelXbrl.qnameParameters[paramQname]
            asType = modelParameter.asType
            asLocalName = asType.localName if asType else "string"
            try:
                if val.parameters and paramQname in val.parameters:
                    paramDataType, paramValue = val.parameters[paramQname]
                    typeLocalName = paramDataType.localName if paramDataType else "string"
                    value = FunctionXs.call(xpathContext, None, typeLocalName, [paramValue])
                    result = FunctionXs.call(xpathContext, None, asLocalName, [value])
                    if formulaOptions.traceParameterInputValue:
                        val.modelXbrl.error( _("Parameter {0} input {1}").format( paramQname, result),
                            "info", "formula:trace")
                else:
                    result = modelParameter.evaluate(xpathContext, asType)
                    if formulaOptions.traceParameterExpressionResult:
                        val.modelXbrl.error( _("Parameter {0} result {1}").format( paramQname, result),
                            "info", "formula:trace")
                xpathContext.inScopeVars[paramQname] = result    # make visible to subsequent parameter expression 
            except XPathContext.XPathException as err:
                val.modelXbrl.error( _("Parameter \n{0} \nException: \n{1}").format( paramQname, err.message),
                    "err", "xbrlve:parameterTypeMismatch" if err.code == "err:FORG0001" else err.code)

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
                        val.modelXbrl.error(
                            _("Multiple output instances for formula {0}, to names {1}, {2}").format(
                                  modelVariableSet.xlinkLabel, instanceQname, instance.qname ), 
                            "info", "arelle:multipleOutputInstances")
            if instanceQname is None: 
                instanceQname = XbrlConst.qnStandardOutputInstance
                instanceQnames.add(instanceQname)
            modelVariableSet.outputInstanceQname = instanceQname
            if val.validateSBRNL:
                val.modelXbrl.error(
                    _("Formula linkbase {0} formula:formula {1} is not allowed").format(
                        os.path.basename(modelVariableSet.modelDocument.uri), modelVariableSet.xlinkLabel), 
                    "err", "SBR.NL.2.3.9.03")
        else:
            instanceQname = None
            modelVariableSet.countSatisfied = 0
            modelVariableSet.countNotSatisfied = 0
            checkValidationMessages(val, modelVariableSet)
        instanceProducingVariableSets[instanceQname].append(modelVariableSet)
        modelVariableSet.outputInstanceQname = instanceQname
        if modelVariableSet.aspectModel not in ("non-dimensional", "dimensional"):
            val.modelXbrl.error(
                _("Variable set {0}, aspect model {1} not recognized").format(
                      modelVariableSet.xlinkLabel, modelVariableSet.aspectModel), 
                "err", "xbrlve:unknownAspectModel")
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
                    val.modelXbrl.error(
                        _("Multiple variables named {1} in variable set {0}").format(
                              modelVariableSet.xlinkLabel, varqname ), 
                        "err", "xbrlve:duplicateVariableNames")
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
                val.modelXbrl.error(
                    _("Variables name {1} cannot be determined on arc from {0}").format(
                          modelVariableSet.xlinkLabel, modelRel.variablename ), 
                    "err", "xbrlve:variableNameResolutionFailure")
        definedNamesSet |= parameterQnames
                
        variableDependencies = {}
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSet).fromModelObject(modelVariableSet):
            variable = modelRel.toModelObject
            if isinstance(variable, (ModelParameter,ModelVariable)):    # ignore anything not parameter or variable
                varqname = modelRel.variableQname
                depVars = variable.variableRefs()
                variableDependencies[varqname] = depVars
                if len(depVars) > 0 and formulaOptions.traceVariablesDependencies:
                    val.modelXbrl.error(_("Variable set {0}, variable {1}, dependences {2}").format(
                                  modelVariableSet.xlinkLabel, varqname, depVars), 
                                  "info", "formula:trace") 
                definedNamesSet.add(varqname)
                # check for fallback value variable references
                if isinstance(variable, ModelFactVariable):
                    for depVar in XPathParser.variableReferencesSet(variable.fallbackValueProg, variable):
                        if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                            val.modelXbrl.error(_("Variable set {0} fallbackValue '{1}' cannot refer to variable {2}").format(
                                          modelVariableSet.xlinkLabel, variable.fallbackValue, depVar),
                                          "err", "xbrlve:factVariableReferenceNotAllowed") 
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
                    val.modelXbrl.error(
                        _("Undefined variable dependencies in variable st {0}, from variable {1} to {2}").format(
                              modelVariableSet.xlinkLabel, varqname, undefinedVars), 
                        "err", "xbrlve:unresolvedDependency")
                if len(varsCircularDep) > 0:
                    val.modelXbrl.error(
                        _("Cyclic dependencies in variable set {0}, from variable {1} to {2}").format(
                              modelVariableSet.xlinkLabel, varqname, varsCircularDep ), 
                        "err", "xbrlve:cyclicDependencies")
                    
        # check unresolved variable set dependencies
        for varSetDepVarQname in modelVariableSet.variableRefs():
            if varSetDepVarQname not in orderedNameSet and varSetDepVarQname not in parameterQnames:
                val.modelXbrl.error(
                    _("Undefined variable dependency in variable set {0}, {1}").format(
                          modelVariableSet.xlinkLabel, varSetDepVarQname), 
                    "err", "xbrlve:unresolvedDependency")
            if varSetDepVarQname in instanceQnames:
                varSetInstanceDependencies.add(varSetDepVarQname)
                instanceDependencies[instanceQname].add(varSetDepVarQname)
            elif isinstance(nameVariables.get(varSetDepVarQname), ModelInstance):
                instqname = nameVariables[varSetDepVarQname].qname
                varSetInstanceDependencies.add(instqname)
                instanceDependencies[instanceQname].add(instqname)
        
        if formulaOptions.traceVariablesOrder:
            val.modelXbrl.error(_("Variable set {0}, variables order: {1}").format(
                          modelVariableSet.xlinkLabel, orderedNameList), "info", "formula:trace") 
        
        if (formulaOptions.traceVariablesDependencies and len(varSetInstanceDependencies) > 0 and
            varSetInstanceDependencies != {XbrlConst.qnStandardInputInstance}):
            val.modelXbrl.error(_("Variable set {0}, instance dependences {1}").format(
                          modelVariableSet.xlinkLabel, varSetInstanceDependencies), 
                          "info", "formula:trace") 
            
        modelVariableSet.orderedVariableRelationships = []
        for varqname in orderedNameList:
            if varqname in qnameRels:
                modelVariableSet.orderedVariableRelationships.append(qnameRels[varqname])
                
        # check existence assertion variable dependencies
        if isinstance(modelVariableSet, ModelExistenceAssertion):
            for depVar in modelVariableSet.variableRefs():
                if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                    val.modelXbrl.error(_("Existence Assertion {0}, cannot refer to variable {1}").format(
                                  modelVariableSet.xlinkLabel, depVar),
                                  "err", "xbrleae:variableReferenceNotAllowed") 
                    
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
                val.modelXbrl.error(_("Variable set {0}, filter {1}, cannot be covered").format(
                              modelVariableSet.xlinkLabel, varSetFilter.xlinkLabel),
                              "wrn", "arelle:variableSetFilterCovered") 
                modelRel._isCovered = False # block group filter from being able to covere
            for depVar in varSetFilter.variableRefs():
                if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                    val.modelXbrl.error(_("Variable set {0}, filter {1}, cannot refer to variable {2}").format(
                                  modelVariableSet.xlinkLabel, varSetFilter.xlinkLabel, depVar),
                                  "err", "xbrlve:factVariableReferenceNotAllowed") 
                    
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
    orderedInstancesList.append(None)  # assertions come after all formulas that produce outputs

    # anything unresolved?
    for instqname, depInsts in instanceDependencies.items():
        if instqname not in orderedInstancesSet:
            # can also be satisfied from an input DTS
            missingDependentInstances = depInsts - stdInpInst
            if val.parameters: missingDependentInstances -= val.parameters.keys() 
            if instqname:
                if missingDependentInstances:
                    val.modelXbrl.error(
                        _("Cyclic dependencies of instance {0} produced by a formula, with variables consuming instances {1}").format(
                              instqname, missingDependentInstances ), 
                        "err", "xbrlvarinste:instanceVariableRecursionCycle")
                elif instqname == XbrlConst.qnStandardOutputInstance:
                    orderedInstancesSet.add(instqname)
                    orderedInstancesList.append(instqname) # standard output formula, all input dependencies in parameters
            ''' future check?  if instance has no external input or producing formula
            else:
                val.modelXbrl.error(
                    _("Unresolved dependencies of an assertion's variables on instances {0}").format(
                          depInsts - stdInpInst ), 
                    "err", "xbrlvarinste:instanceVariableRecursionCycle")
            '''

    if formulaOptions.traceVariablesOrder and len(orderedInstancesList) > 1:
        val.modelXbrl.error(_("Variable instances processing order: {0}").format(
                            orderedInstancesList), "info", "formula:trace") 

    # linked consistency assertions
    for modelRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).modelRelationships:
        if (modelRel.fromModelObject is not None and modelRel.toModelObject is not None and 
            isinstance(modelRel.toModelObject,ModelFormula)):
            consisAsser = modelRel.fromModelObject
            consisAsser.countSatisfied = 0
            consisAsser.countNotSatisfied = 0
            if consisAsser.hasProportionalAcceptanceRadius and consisAsser.hasAbsoluteAcceptanceRadius:
                val.modelXbrl.error( _("Consistency assertion {0} has both absolute and proportional acceptance radii").format( 
                     consisAsser.xlinkLabel),
                    "err", "xbrlcae:acceptanceRadiusConflict")
            consisAsser.orderedVariableRelationships = []
            for consisParamRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionParameter).fromModelObject(consisAsser):
                if isinstance(consisParamRel.toModelObject, ModelVariable):
                    val.modelXbrl.error( _("Consistency assertion {0} has relationship to a {1} {2}").format( 
                         consisAsser.xlinkLabel, consisParamRel.toModelObject.localName, consisParamRel.toModelObject.xlinkLabel),
                        "err", "xbrlcae:variablesNotAllowed")
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
                val.modelXbrl.error( _("Variable set \n{0} \nException: \n{1}").format( modelVariableSet, err.message),
                    "err", err.code)
            
    # log assertion result counts
    asserTests = {}
    for exisValAsser in val.modelXbrl.modelVariableSets:
        if isinstance(exisValAsser, ModelVariableSetAssertion):
            asserTests[exisValAsser.id] = (exisValAsser.countSatisfied, exisValAsser.countNotSatisfied)
            if formulaOptions.traceAssertionResultCounts:
                val.modelXbrl.error( _("{0} Assertion {1} evaluations : {2} satisfied, {3} not satisfied").format(
                    "Existence" if isinstance(exisValAsser, ModelExistenceAssertion) else "Value", 
                    exisValAsser.id, exisValAsser.countSatisfied, exisValAsser.countNotSatisfied),
                    "info", "formula:trace")

    for modelRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).modelRelationships:
        if modelRel.fromModelObject is not None and modelRel.toModelObject is not None and \
           isinstance(modelRel.toModelObject,ModelFormula):
            consisAsser = modelRel.fromModelObject
            asserTests[consisAsser.id] = (consisAsser.countSatisfied, consisAsser.countNotSatisfied)
            if formulaOptions.traceAssertionResultCounts:
                val.modelXbrl.error( _("Consistency Assertion {0} evaluations : {1} satisfied, {2} not satisfied").format(
                    consisAsser.id, consisAsser.countSatisfied, consisAsser.countNotSatisfied),
                    "info", "formula:trace")
            
    if asserTests:
        val.modelXbrl.error( _("Assertion results {0}").format(asserTests),
            "asrtNoLog", asserTests)

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
                        val.modelXbrl.error(
                            _("Variable set {0}, aspect cover filter {1}, aspect {2}, conflicts with {3} with inconsistent cover attribute").format(
                                  variableSet.xlinkLabel, filter.xlinkLabel, 
                                  str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect],
                                  otherFilterLabel),
                            "err", "xbrlacfe:inconsistentAspectCoverFilters")
                else:
                    acfAspectsCovering[aspect] = (varFilterRel.isCovered, filter.xlinkLabel)
            isAllAspectCoverFilter = filter.isAll
        if varFilterRel.isCovered:
            try:
                aspectsCovered = filter.aspectsCovered(None)
                if (not isAllAspectCoverFilter and 
                    (any(isinstance(aspect,QName) for aspect in aspectsCovered) and Aspect.DIMENSIONS in uncoverableAspects
                     or (aspectsCovered & uncoverableAspects))):
                    val.modelXbrl.error(
                        _("Variable set {0}, aspect model {1} filter {2} {3} can cover aspect not in aspect model").format(
                              variableSet.xlinkLabel, variableSet.aspectModel, filter.localName, filter.xlinkLabel), 
                        "err", "xbrlve:filterAspectModelMismatch")
            except Exception:
                pass
            if hasattr(filter, "filterRelationships"): # check and & or filters
                checkFilterAspectModel(val, variableSet, filter.filterRelationships, xpathContext, uncoverableAspects)
        
def checkFormulaRules(val, formula, nameVariables):
    from arelle.ModelFormulaObject import (Aspect)
    if not (formula.hasRule(Aspect.CONCEPT) or formula.source(Aspect.CONCEPT)):
        if XmlUtil.hasDescendant(formula, XbrlConst.formula, "concept"):
            val.modelXbrl.error(_("Formula {0} concept rule does not have a nearest source and does not have a child element").format(formula.xlinkLabel),
                                "err", "xbrlfe:incompleteConceptRule") 
        else:
            val.modelXbrl.error(_("Formula {0} omits a rule for the concept aspect").format(formula.xlinkLabel),
                                "err", "xbrlfe:missingConceptRule") 
    if (not (formula.hasRule(Aspect.SCHEME) or formula.source(Aspect.SCHEME)) or
        not (formula.hasRule(Aspect.VALUE) or formula.source(Aspect.VALUE))):
        if XmlUtil.hasDescendant(formula, XbrlConst.formula, "entityIdentifier"):
            val.modelXbrl.error(_("Formula {0} entity identifier rule does not have a nearest source and does not have either a @scheme or a @value attribute").format(formula.xlinkLabel),
                                "err", "xbrlfe:incompleteEntityIdentifierRule") 
        else:
            val.modelXbrl.error(_("Formula {0} omits a rule for the entity identifier aspect").format(formula.xlinkLabel),
                                "err", "xbrlfe:missingEntityIdentifierRule") 
    if not (formula.hasRule(Aspect.PERIOD_TYPE) or formula.source(Aspect.PERIOD_TYPE)):
        if XmlUtil.hasDescendant(formula, XbrlConst.formula, "period"):
            val.modelXbrl.error(_("Formula {0} period rule does not have a nearest source and does not have a child element").format(formula.xlinkLabel),
                                "err", "xbrlfe:incompletePeriodRule") 
        else:
            val.modelXbrl.error(_("Formula {0} omits a rule for the period aspect").format(formula.xlinkLabel),
                                "err", "xbrlfe:missingPeriodRule") 
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
                    val.modelXbrl.error(_("Formula {0} unit rule does not have a source and does not have a child element").format(formula.xlinkLabel),
                                        "err", "xbrlfe:missingSAVForUnitRule") 
                else:
                    val.modelXbrl.error(_("Formula {0} omits a rule for the unit aspect").format(formula.xlinkLabel),
                                        "err", "xbrlfe:missingUnitRule") 
        elif (formula.hasRule(Aspect.MULTIPLY_BY) or formula.hasRule(Aspect.DIVIDE_BY) or 
              formula.source(Aspect.UNIT, acceptFormulaSource=False)):
            val.modelXbrl.error(_("Formula {0} has a rule for the unit aspect of a non-numeric concept {1}").format(formula.xlinkLabel, str(concept.qname)),
                                "err", "xbrlfe:conflictingAspectRules") 
        aspectPeriodType = formula.evaluateRule(None, Aspect.PERIOD_TYPE)
        if ((concept.periodType == "duration" and aspectPeriodType == "instant") or
            (concept.periodType == "instant" and aspectPeriodType in ("duration","forever"))):
            val.modelXbrl.error(_("Formula {0} has a rule for the {2} period aspect of a {3} concept {1}").format(formula.xlinkLabel, str(concept.qname), aspectPeriodType, concept.periodType),
                                "err", "xbrlfe:conflictingAspectRules") 
    
    # check dimension elements
    for eltName, dim, badUsageErr, missingSavErr in (("explicitDimension", "explicit", "xbrlfe:badUsageOfExplicitDimensionRule", "xbrlfe:missingSAVForExplicitDimensionRule"),
                                                     ("typedDimension", "typed", "xbrlfe:badUsageOfTypedDimensionRule", "xbrlfe:missingSAVForTypedDimensionRule")):
        for dimElt in XmlUtil.descendants(formula, XbrlConst.formula, eltName):
            dimQname = qname(dimElt, dimElt.get("dimension"))
            dimConcept = val.modelXbrl.qnameConcepts.get(dimQname)
            if dimQname and (dimConcept is None or (not dimConcept.isExplicitDimension if dim == "explicit" else not dimConcept.isTypedDimension)):
                val.modelXbrl.error(_("Formula {0} dimension attribute {1} on the {2} dimension rule contains a QName that does not identify an {2} dimension.").format(formula.xlinkLabel, dimQname, dim),
                                    "err", badUsageErr) 
            elif not XmlUtil.hasChild(dimElt, XbrlConst.formula, "*") and not formula.source(Aspect.DIMENSIONS, dimElt):
                val.modelXbrl.error(_("Formula {0} {1} dimension rule does not have any child elements and does not have a SAV for the {2} dimension that is identified by its dimension attribute.").format(formula.xlinkLabel, dim, dimQname),
                                    "err", missingSavErr) 
    
    # check aspect model expectations
    if formula.aspectModel == "non-dimensional":
        unexpectedElts = XmlUtil.descendants(formula, XbrlConst.formula, ("explicitDimension", "typedDimension"))
        if unexpectedElts:
            val.modelXbrl.error(_("Formula {0} aspect model, {1}, includes an rule for aspect not defined in this aspect model: {2}").format(
                                formula.xlinkLabel, formula.aspectModel, ", ".join([elt.localName for elt in unexpectedElts])),
                                "err", "xbrlfe:unrecognisedAspectRule") 

    # check source qnames
    for sourceElt in ([formula] + 
                     XmlUtil.descendants(formula, XbrlConst.formula, "*", "source","*")):
        if sourceElt.get("source") is not None:
            qnSource = qname(sourceElt, sourceElt.get("source"), noPrefixIsNoNamespace=True)
            if qnSource == XbrlConst.qnFormulaUncovered:
                if formula.implicitFiltering != "true":
                    val.modelXbrl.error(_("Formula {0}, not implicit filtering element has formulaUncovered source: {1}").format(
                                  formula.xlinkLabel, sourceElt.localName), "err", "xbrlfe:illegalUseOfUncoveredQName") 
            elif qnSource not in nameVariables:
                val.modelXbrl.error(_("Variable set {0}, source {1} is not in the variable set").format(
                              formula.xlinkLabel, qnSource), "err", "xbrlfe:nonexistentSourceVariable")
            else:
                factVariable = nameVariables.get(qnSource)
                if not isinstance(factVariable, ModelFactVariable):
                    val.modelXbrl.error(_("Variable set {0}, source {1} not a factVariable but is a {2}").format(
                                  formula.xlinkLabel, qnSource, factVariable.localName), "err", "xbrlfe:nonexistentSourceVariable")
                elif factVariable.fallbackValue is not None:
                    val.modelXbrl.error(_("Formula {0}: source {1} is a fact variable that has a fallback value").format(formula.xlinkLabel, str(qnSource)),
                                        "err", "xbrlfe:bindEmptySourceVariable")
                elif sourceElt.localName == "formula" and factVariable.bindAsSequence == "true":
                    val.modelXbrl.error(_("Formula {0}: formula source {1} is a fact variable that binds as a sequence").format(formula.xlinkLabel, str(qnSource)),
                                        "err", "xbrlfe:defaultAspectValueConflicts")
                
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
                    val.modelXbrl.error(_("Message {0}: unbalanced '{1}' character(s) in: {2}").format(
                                        message.xlinkLabel, '{' if bracketNesting < 0 else '}', message.text),
                                        "err", "xbrlmsge:missingLeftCurlyBracketInMessage" if bracketNesting < 0 else "xbrlmsge:missingRightCurlyBracketInMessage")
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
                    val.modelXbrl.error(
                        _("Undefined variable dependency in message {0}, {1}").format(
                              message.xlinkLabel, msgVarQname), 
                        "err", "err:XPST0008")
