"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
from numbers import Number
from typing import Any, Sequence, TypeAlias

from arelle import ModelValue
from arelle.ModelObject import ModelAttribute, ModelObject
from arelle.PythonUtil import pyTypeName
from arelle.formula.XPathContext import ContextItem, FunctionArgType, XPathContext, XPathException, ResultStack
from arelle.formula.XPathParser import FormulaToken
from arelle.typing import TypeGetText

emptyFallbackType: TypeAlias = tuple[()] | str | int | float | None
_: TypeGetText


def anytypeArg(
        xc: XPathContext,
        args: ResultStack,
        i: int,
        type: str,
        missingArgFallback: ContextItem = None,
    ) -> Any:
    if len(args) > i:
        item = args[i]
    else:
        item = missingArgFallback  # type: ignore[assignment]

    if isinstance(item, (tuple, list)):
        if len(item) > 1:
            raise FunctionArgType(i, type, item)

        if len(item) == 0:
            return ()

        item = item[0]
    return item


def atomicArg(
        xc: XPathContext,
        p: FormulaToken,
        args: ResultStack,
        i: int,
        type: str,
        missingArgFallback: ContextItem = None,
        emptyFallback: emptyFallbackType = (),
    ) -> Any:
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == ():
        return emptyFallback

    return xc.atomize(p, item)


def stringArg(
        xc: XPathContext,
        args: ResultStack,
        i: int,
        type: str,
        missingArgFallback: ContextItem = None,
        emptyFallback: emptyFallbackType = "",
    ) -> Any:
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == ():
        return emptyFallback

    if isinstance(item, (ModelObject, ModelAttribute)):
        return item.text or emptyFallback

    return str(item)


def numericArg(
        xc: XPathContext,
        p: FormulaToken,
        args: ResultStack,
        i: int = 0,
        missingArgFallback: ContextItem = None,
        emptyFallback: emptyFallbackType = 0,
        convertFallback: str | int | float | None = None,
    ) -> Any:
    item = anytypeArg(xc, args, i, "numeric?", missingArgFallback)
    if item == ():
        return emptyFallback

    numeric = xc.atomize(p, item)
    if not isinstance(numeric, Number):
        if convertFallback is None:
            raise FunctionArgType(i, "numeric?", numeric)
        try:
            numeric = float(numeric)
        except ValueError:
            numeric = convertFallback

    return numeric


def integerArg(
        xc: XPathContext,
        p: FormulaToken,
        args: ResultStack,
        i: int = 0,
        missingArgFallback: ContextItem = None,
        emptyFallback: emptyFallbackType = 0,
        convertFallback: int | None = None,
    ) -> emptyFallbackType:
    item = anytypeArg(xc, args, i, "integer?", missingArgFallback)
    if item == ():
        return emptyFallback

    numeric = xc.atomize(p, item)
    if not isinstance(numeric, int):
        if convertFallback is None:
            raise FunctionArgType(i, "integer?", numeric)
        try:
            numeric = int(numeric)
        except ValueError:
            numeric = convertFallback

    return numeric


def qnameArg(
        xc: XPathContext,
        p: FormulaToken,
        args: ResultStack,
        i: int,
        type: str,
        missingArgFallback: ContextItem = None,
        emptyFallback: emptyFallbackType = (),
    ) -> ModelValue.QName | emptyFallbackType:
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == ():
        return emptyFallback

    qn = xc.atomize(p, item)
    if not isinstance(qn, ModelValue.QName):
        raise FunctionArgType(i, type, qn)

    return qn


def nodeArg(
        xc: XPathContext,
        args: ResultStack,
        i: int,
        type: str,
        missingArgFallback: ContextItem = None,
        emptyFallback: emptyFallbackType = None,
    ) -> ModelObject | ModelAttribute | emptyFallbackType | ModelValue.QName:
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == ():
        return emptyFallback

    if not isinstance(item, (ModelObject, ModelAttribute)):
        raise FunctionArgType(i, type, item)

    return item


def testTypeCompatibility(
        xc: XPathContext,
        p: FormulaToken,
        op: str,
        a1: ContextItem,
        a2: ContextItem,
    ) -> None:
    if isinstance(a1, ModelValue.DateTime) and isinstance(a2, ModelValue.DateTime):
        if a1.dateOnly == a2.dateOnly:
            return  # can't interoperate between date and datetime

    elif isinstance(a1, bool) != isinstance(a2, bool):
        pass  # fail if one arg is bool and the other is not (don't le t bool be subclass of num types)
    elif (type(a1) == type(a2)
          or (isinstance(a1, Number) and isinstance(a2, Number))
          or (isinstance(a1, str) and isinstance(a2, str))):
        return
    elif op in ("+", "-"):
        if ((isinstance(a1, ModelValue.DateTime) and isinstance(a2, (ModelValue.YearMonthDuration, datetime.timedelta)))
                or ((isinstance(a1, datetime.date) and isinstance(a2, datetime.timedelta)))):
            return
    else:
        if isinstance(a1, datetime.date) and isinstance(a2, datetime.date):
            return

    raise XPathException(
        p,
        "err:XPTY0004",
        _(
            "Value operation {0} incompatible arguments {1} ({2}) and {3} ({4})"
            ).format(op, a1, pyTypeName(a1), a2, pyTypeName(a2))  # type: ignore[no-untyped-call]
    )
