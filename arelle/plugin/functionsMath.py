'''
Formula math functions plugin.

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import math
from collections.abc import Callable

from arelle.formula import XPathContext
from arelle.FunctionUtil import numericArg
from arelle.ModelValue import QName, qname
from arelle.Version import authorLabel, copyrightLabel
from arelle.formula.XPathParser import OperationDef
from arelle.typing import EmptyTuple

INF = float('inf')
MINUSINF = float('-inf')
NaN = float('nan')


def xfm_pi(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 0:
        raise XPathContext.FunctionNumArgs()
    return math.pi


def xfm_exp(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        return math.exp(x)
    return ()


def xfm_exp10(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        return math.pow(10.0, x)
    return ()


def xfm_log(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        if x == 0:
            return MINUSINF
        elif x == -1:
            return NaN
        elif x == MINUSINF:
            return NaN
        return math.log(x)
    return ()


def xfm_log10(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        if x == 0:
            return MINUSINF
        elif x == -1:
            return NaN
        elif x == MINUSINF:
            return NaN
        return math.log10(x)
    return ()


def xfm_pow(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 2:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        y = numericArg(xc, p, args, 1)  # type: ignore[no-untyped-call]
        if x == 0:
            if math.copysign(1, x) < 0:  # e.g., value is -0.0
                if y < 0:
                    # special case for odd integer exponents
                    _intY = int(y)
                    if _intY & 1 and y == _intY:  # special case for whole numbers
                        return MINUSINF
                    return INF
                elif y == 0:
                    return 1.0
                else:
                    return -0.0
            else:  # value is +0.0
                if y < 0:
                    return INF
                elif y == 0:
                    return 1.0
                else:
                    return 0.0
        try:
            return math.pow(x, y)
        except ValueError:
            return NaN  # pow(-2.5e0, 2.00000001e0) returns xs:double('NaN').
    return ()


def xfm_sqrt(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        if x == MINUSINF:
            return NaN
        elif x < 0:
            return INF
        return math.sqrt(x)
    return ()


def xfm_sin(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        if math.isinf(x):
            return NaN
        return math.sin(x)
    return ()


def xfm_cos(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        if math.isinf(x):
            return NaN
        return math.cos(x)
    return ()


def xfm_tan(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        if math.isinf(x):
            return NaN
        return math.tan(x)
    return ()


def xfm_asin(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        try:
            return math.asin(x)
        except ValueError:
            return NaN
    return ()


def xfm_acos(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        try:
            return math.acos(x)
        except ValueError:
            return NaN
    return ()


def xfm_atan(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    x = numericArg(xc, p, args, 0, emptyFallback=())  # type: ignore[no-untyped-call]
    if x != ():
        try:
            return math.atan(x)
        except ValueError:
            return NaN
    return ()


def xfm_atan2(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> float:
    if len(args) != 2:
        raise XPathContext.FunctionNumArgs()
    y = numericArg(xc, p, args, 0)  # type: ignore[no-untyped-call]
    x = numericArg(xc, p, args, 1)  # type: ignore[no-untyped-call]
    return math.atan2(y, x)


def xfmMathFunctions() -> dict[
    QName, Callable[[
        XPathContext.XPathContext,
        OperationDef,
        XPathContext.ContextItem,
        XPathContext.ResultStack,
    ], float | EmptyTuple]
]:
    return {
        qname("{http://www.xbrl.org/2008/function/math}xfm:pi"): xfm_pi,
        qname("{http://www.xbrl.org/2008/function/math}xfm:exp"): xfm_exp,
        qname("{http://www.xbrl.org/2008/function/math}xfm:exp10"): xfm_exp10,
        qname("{http://www.xbrl.org/2008/function/math}xfm:log"): xfm_log,
        qname("{http://www.xbrl.org/2008/function/math}xfm:log10"): xfm_log10,
        qname("{http://www.xbrl.org/2008/function/math}xfm:pow"): xfm_pow,
        qname("{http://www.xbrl.org/2008/function/math}xfm:sqrt"): xfm_sqrt,
        qname("{http://www.xbrl.org/2008/function/math}xfm:sin"): xfm_sin,
        qname("{http://www.xbrl.org/2008/function/math}xfm:cos"): xfm_cos,
        qname("{http://www.xbrl.org/2008/function/math}xfm:tan"): xfm_tan,
        qname("{http://www.xbrl.org/2008/function/math}xfm:asin"): xfm_asin,
        qname("{http://www.xbrl.org/2008/function/math}xfm:acos"): xfm_acos,
        qname("{http://www.xbrl.org/2008/function/math}xfm:atan"): xfm_atan,
        qname("{http://www.xbrl.org/2008/function/math}xfm:atan2"): xfm_atan2,
    }


__pluginInfo__ = {
    'name': 'Formula Math Functions',
    'version': '1.0',
    'description': "This plug-in adds formula math functions.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Formula.CustomFunctions': xfmMathFunctions,
}
