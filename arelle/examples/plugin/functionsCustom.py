'''
Sample custom functions plugin for formula custom functions

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
from arelle import XPathContext, XbrlUtil
from arelle.ModelValue import qname
from arelle.ModelInstanceObject import ModelDimensionValue

# custom function for test case 22015 v01, same as in FunctionCustom.py        
def  test_22015v01_my_fn_PDxEV(xc, p, contextItem, args):
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
    
# returns dict of function QName and method executing the function
def customFunctions():
    return {
        # sample function included for formula tests
        qname("{http://www.example.com/wgt-avg/function}my-fn:PDxEV"): test_22015v01_my_fn_PDxEV
    }

__pluginInfo__ = {
    'name': 'Custom Formula Functions (example)',
    'version': '1.0',
    'description': "This plug-in adds a custom function implemented by a plug-in.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Formula.CustomFunctions': customFunctions,
}
