"""
Formula math functions plugin.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import math
from collections.abc import Callable

from arelle.formula import XPathContext
from arelle.FunctionUtil import numericArg
from arelle.ModelValue import QName
from arelle.Version import authorLabel, copyrightLabel
from arelle.formula.XPathParser import OperationDef
from arelle.typing import EmptyTuple

_XFM_NAMESPACE = "http://www.xbrl.org/2008/function/math"
_XFM_PREFIX = "xfm"

INF = float("inf")
MINUSINF = float("-inf")
NaN = float("nan")


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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
    if x != ():
        y = numericArg(xc, p, args, 1)
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    x = numericArg(xc, p, args, 0, emptyFallback=())
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
    y = numericArg(xc, p, args, 0)
    x = numericArg(xc, p, args, 1)
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
        QName.fromParts("pi", _XFM_NAMESPACE, _XFM_PREFIX): xfm_pi,
        QName.fromParts("exp", _XFM_NAMESPACE, _XFM_PREFIX): xfm_exp,
        QName.fromParts("exp10", _XFM_NAMESPACE, _XFM_PREFIX): xfm_exp10,
        QName.fromParts("log", _XFM_NAMESPACE, _XFM_PREFIX): xfm_log,
        QName.fromParts("log10", _XFM_NAMESPACE, _XFM_PREFIX): xfm_log10,
        QName.fromParts("pow", _XFM_NAMESPACE, _XFM_PREFIX): xfm_pow,
        QName.fromParts("sqrt", _XFM_NAMESPACE, _XFM_PREFIX): xfm_sqrt,
        QName.fromParts("sin", _XFM_NAMESPACE, _XFM_PREFIX): xfm_sin,
        QName.fromParts("cos", _XFM_NAMESPACE, _XFM_PREFIX): xfm_cos,
        QName.fromParts("tan", _XFM_NAMESPACE, _XFM_PREFIX): xfm_tan,
        QName.fromParts("asin", _XFM_NAMESPACE, _XFM_PREFIX): xfm_asin,
        QName.fromParts("acos", _XFM_NAMESPACE, _XFM_PREFIX): xfm_acos,
        QName.fromParts("atan", _XFM_NAMESPACE, _XFM_PREFIX): xfm_atan,
        QName.fromParts("atan2", _XFM_NAMESPACE, _XFM_PREFIX): xfm_atan2,
    }


__pluginInfo__ = {
    "name": "Formula Math Functions",
    "version": "1.0",
    "description": "This plug-in adds formula math functions.  ",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    # classes of mount points (required)
    "Formula.CustomFunctions": xfmMathFunctions,
}
