'''
Created on Apr 21, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import xml.dom, math, re
from arelle.ModelValue import (qname, dateTime, DateTime, DATE, DATETIME, dayTimeDuration,
                         YearMonthDuration, DayTimeDuration, time, Time)
from arelle.FunctionUtil import (anytypeArg, stringArg, numericArg, qnameArg, nodeArg)
from arelle import (XPathContext, ModelObject, XbrlUtil, XmlUtil)
    
class fnFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  ("custom function not available",)
    def __repr__(self):
        return self.args[0]
    
def call(xc, p, qname, contextItem, args):
    try:
        cfSig = xc.modelXbrl.modelCustomFunctionSignatures[qname]
        if cfSig is not None and cfSig.customFunctionImplementation:
            return callCfi(xc, p, qname, cfSig, contextItem, args)
        elif qname not in customFunctions: 
            raise fnFunctionNotAvailable
        return customFunctions[qname](xc, p, contextItem, args)
    except (fnFunctionNotAvailable, KeyError):
        raise XPathContext.FunctionNotAvailable("custom function:{0}".format(str(qname)))

def callCfi(xc, p, qname, cfSig, contextItem, args):
    if len(args) != len(cfSig.inputTypes): 
        raise XPathContext.FunctionNumArgs()

    cfi = cfSig.customFunctionImplementation
    overriddenInScopeVars = {}
    traceSource = xc.formulaOptions.traceSource(xc.traceType)
    traceEvaluation = xc.formulaOptions.traceEvaluation(xc.traceType)
    inputNames = cfi.inputNames
    for i, argName in enumerate(inputNames):
        if argName in xc.inScopeVars:
            overriddenInScopeVars[argName] = xc.inScopeVars[argName]
        xc.inScopeVars[argName] = args[i]
        
    for i, step in enumerate(cfi.stepExpressions):
        stepQname, stepExpression = step
        stepProg = cfi.stepProgs[i]
        if traceSource:
            xc.modelXbrl.info("formula:trace",
                                _("%(cfi)s step %(step)s \nExpression: \n%(expression)s"),
                                modelObject=cfi,
                                cfi=qname, step=stepQname, expression=stepExpression)
        result = xc.evaluate(stepProg)
        if traceEvaluation:
            xc.modelXbrl.info("formula:trace",
                                _("%(cfi)s step %(step)s \nResult: \n%(expression)s"),
                                modelObject=cfi,
                                cfi=qname, step=stepQname, expression=result)
        if stepQname in xc.inScopeVars:
            overriddenInScopeVars[stepQname] = xc.inScopeVars[stepQname]
        xc.inScopeVars[stepQname] = result

    if traceSource:
        xc.modelXbrl.info("formula:trace",
                            _("%(cfi)s output \nExpression: \n%(expression)s"),
                            modelObject=cfi,
                            cfi=qname, expression=cfi.outputExpression)
    result = xc.evaluateAtomicValue(cfi.outputProg, cfSig.outputType)
    if traceEvaluation:
        xc.modelXbrl.info("formula:trace",
                            _("%(cfi)s output \nResult: \n%(expression)s"),
                            modelObject=cfi,
                            cfi=qname, expression=result)

    for step in cfi.stepExpressions:
        stepQname = step[0]
        if stepQname in overriddenInScopeVars:
            xc.inScopeVars[stepQname] = overriddenInScopeVars[stepQname]

    for i, argName in enumerate(inputNames):
        if argName in overriddenInScopeVars:
            xc.inScopeVars[argName] = overriddenInScopeVars[argName]
        else:
            del xc.inScopeVars[argName]

    return result
        
customFunctions = {
}
