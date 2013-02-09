'''
sphinxMethods processes the Sphinx language in the context of an XBRL DTS and instance.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

from math import exp, fabs, isinf, isnan, log, log10, pow, sqrt
from arelle.ModelInstanceObject import ModelFact
evaluate = None

def numericArgs(node, sphinxContext, expectedArgsLen):
    global evaluate
    if evaluate is None:
        from .SphinxEvaluator import evaluate
        
    if expectedArgsLen != len(node.args):
        sphinxContext.modelXbrl.log("ERROR", "sphinx.functionArgumentsMismatch",
                                    _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                                    sourceFileLine=node.sourceFileLine,
                                    name=node.name, required=expectedArgsLen, provided=len(node.args))
    numArgs = []
    for arg, i in enumerate(node.args):
        if i >= expectedArgsLen:
            break
        value = evaluate(arg, sphinxContext, value=True)
        if not isinstance(value, _NUM_TYPES):
            sphinxContext.modelXbrl.log("ERROR", "sphinx.functionArgumentMismatch",
                                        _("Function %(name)s numeric parameters but %(num)s is not numeric: %(value)s"),
                                        sourceFileLine=node.sourceFileLine,
                                        num=i, value=value)
            value = 0
        numArgs.append(value)
    for i in range(i, expectedArgsLen):
        numArgs.append(0)
    return numArgs
    
# numeric functions
NaN = float("NaN")
POSINF = float("INF")
NEGINF = float("-INF")

def _abs(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 1)
    return fabs(args[0])
    
def _exp(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 1)
    x = args[0]
    if isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == NEGINF: return 0
    return exp(x)

def _ln(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 1)
    x = args[0]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == 0: return NEGINF
    return log(x)

def _log(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 2)
    x = args[0]
    base = args[1]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == 0: return POSINF
    if base == 0 or base == POSINF: return 0
    if base == 10: return log10(x)
    return log(x, base)

def _log10(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 1)
    x = args[0]
    base = args[1]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == 0: return POSINF
    return log10(x)
    
def _power(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 2)
    x = args[0]
    exp = args[1]
    if isnan(exp) or (isnan(x) and exp != 0) or (isinf(exp) and x in (1, -1)): 
        return NaN
    if ((x == POSINF and exp > 0) or 
        (x == NEGINF and x > 0 and not x & 1) or 
        (exp == POSINF and not -1 <= x <= 1) or
        (x == 0 and exp < 0)): 
        return POSINF
    if x == NEGINF and x > 0 and x & 1:
        return NEGINF
    return pow(x, exp)

def _roundDecimals(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 2)
    return round(args[0], args[1])
    
def _signum(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 1)
    x = args[0]
    if x == 0 or isnan(x): return 0
    if x > 0: return 1
    return -1
    
def _sqrt(node, sphinxContext):
    args = numericArgs(node, sphinxContext, 1)
    x = args[0]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    return sqrt(x)
    
# fact methods
def factArg(node, sphinxContext):
    factarg = node.args[0]
    if not isinstance(factarg, ModelFact):
        sphinxContext.modelXbrl.log("ERROR", "sphinx.functionArgumentMismatch",
                                    _("Function %(name)s fact argument is not a fact: %(value)s"),
                                    sourceFileLine=node.sourceFileLine,
                                    value=factarg)
        return None
    return factarg
    
def _period(node, sphinxContext):
    fact = factArg(node, sphinxContext)

    
# miscellaneous methods    
    
def _notImplemented(node, sphinxContext):
    sphinxContext.modelXbrl.log("ERROR", "sphinx.functionNotImplemented",
                                _("Function %(name)s is not currently implemented"),
                                sourceFileLine=node.sourceFileLine,
                                name=node.name)
    return NaN
    
methodImplementation = {
    "abs":          _abs,
    "exp":          _exp,
    "ln":           _ln,
    "log":           _log,
    "log10":         _log10,
    "power":         _power,
    "round-by-decimals": _roundDecimals,
    "round-by-precision": _notImplemented,
    "signum":       _signum,
    "sqrt":         _sqrt,

    "period":       _period,
    
    "unknown":      _notImplemented,
    }