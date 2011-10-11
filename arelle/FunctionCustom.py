'''
Created on Apr 21, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import xml.dom, math, re
from arelle.ModelValue import qname
from arelle import XPathContext, XbrlUtil
from arelle.ModelInstanceObject import ModelDimensionValue
    
class fnFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  ("custom function not available",)
    def __repr__(self):
        return self.args[0]
    
def call(xc, p, qname, contextItem, args):
    try:
        cfSig = xc.modelXbrl.modelCustomFunctionSignatures[qname]
        if cfSig is not None and cfSig.customFunctionImplementation is not None:
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

# for test case 22015 v01        
def  my_fn_PDxEV(xc, p, contextItem, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    PDseq = args[0] if isinstance(args[0],(list,tuple)) else (args[0],)
    EVseq = args[1] if isinstance(args[1],(list,tuple)) else (args[1],)
    dimQname = qname("{http://www.example.com/wgt-avg}ExposuresDimension")
    PDxEV = []
    for pd in PDseq:
        if pd.context is not None:
            pdDim = pd.context.dimValue(dimQname)
            for ev in EVseq:
                if ev.context is not None:
                    evDim = ev.context.dimValue(dimQname)
                    if pdDim is not None and isinstance(pdDim,ModelDimensionValue):
                        dimEqual =  pdDim.isEqualTo(evDim, equalMode=XbrlUtil.S_EQUAL2)
                    elif evDim is not None and isinstance(evDim,ModelDimensionValue):
                        dimEqual =  evDim.isEqualTo(pdDim, equalMode=XbrlUtil.S_EQUAL2)
                    else:
                        dimEqual = (pdDim == evDim)
                    if dimEqual:
                        PDxEV.append(pd.xValue * ev.xValue)
                        break
    return PDxEV


customFunctions = {
    qname("{http://www.example.com/wgt-avg/function}my-fn:PDxEV"): my_fn_PDxEV
}
