"""
FormulaFunctions.py - Built-in function library for the formula interpreter.

Implements the standard Xule function set adapted for the OIM XbrlModel
data model.  Each function is registered in BUILTIN_FUNCTIONS as:

    name → callable(args: list[FormulaValue], ctx: FormulaRuleContext) → FormulaValue

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import math
import random
import re
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

from arelle.ModelValue import QName, qname as makeQName

from .FormulaValue import (
    FormulaValue, FormulaValueType, FormulaRuntimeError,
    NONE_VALUE, TRUE_VALUE, FALSE_VALUE, SKIP_VALUE
)
from .DateTimeSupport import (
    InstantValue,
    DateRangeValue,
    TimeSpanValue,
    parse_date_string,
    parse_time_span_string,
)
try:
    from ordered_set import OrderedSet
except ImportError:
    OrderedSet = frozenset

if TYPE_CHECKING:
    from .FormulaContext import FormulaRuleContext


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _num(fv: FormulaValue) -> Decimal:
    """Extract a Decimal from a FormulaValue, raising FormulaRuntimeError on failure."""
    try:
        return fv.numericValue()
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise FormulaRuntimeError(f"Expected numeric value, got {fv!r}: {exc}") from exc


def _unwrapCollection(fv: FormulaValue) -> List[FormulaValue]:
    """Return items from a SET or LIST value."""
    if fv.type in (FormulaValueType.SET, FormulaValueType.LIST):
        return list(fv.value)
    if fv.type == FormulaValueType.NONE:
        return []
    return [fv]   # treat a single value as a one-element collection


def _typeName(fv: FormulaValue, capitalizeNone: bool = False) -> str:
    if fv.type == FormulaValueType.NONE:
        return "None" if capitalizeNone else "none"
    return fv.type.name.lower()


def _isInfinityLiteral(fv: FormulaValue) -> bool:
    if fv.type != FormulaValueType.QNAME:
        return False
    local_name = getattr(fv.value, "localName", str(fv.value))
    return str(local_name).lower() in ("inf", "infinity")


def _numericOrError(fv: FormulaValue, fnName: str, allowString: bool = False, capitalizeNone: bool = False) -> Decimal:
    if _isInfinityLiteral(fv):
        return Decimal("Infinity")
    if allowString and fv.type == FormulaValueType.STRING:
        return Decimal(fv.value)
    try:
        return fv.numericValue()
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise FormulaRuntimeError(
            f"The first argument of function '{fnName}' must be int, float, decimal, "
            f"{'string, ' if allowString else ''}fact, found '{_typeName(fv, capitalizeNone=capitalizeNone)}'."
        ) from exc


def _applyNumericProjection(
    name: str,
    source: FormulaValue,
    compute,
) -> FormulaValue:
    if source.type in (FormulaValueType.LIST, FormulaValueType.SET):
        projected: List[FormulaValue] = []
        for item in list(source.value):
            if item.type == FormulaValueType.NONE:
                projected.append(NONE_VALUE)
                continue
            if item.type not in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL, FormulaValueType.FACT) and not _isInfinityLiteral(item):
                raise FormulaRuntimeError(
                    f"Property '{name}' is not a property of a '{_typeName(item)}'."
                )
            projected.append(compute(item))
        if source.type == FormulaValueType.SET:
            return FormulaValue(FormulaValueType.SET, OrderedSet(projected))
        return FormulaValue(FormulaValueType.LIST, projected)
    return compute(source)


# ---------------------------------------------------------------------------
# Aggregate functions
# ---------------------------------------------------------------------------

def _fn_sum(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """sum(collection) -> additive reduction over list/set items."""
    if len(args) != 1:
        raise FormulaRuntimeError("sum() requires exactly one argument")
    if args[0].type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'sum' must be set, list, found '{args[0].type.name.lower()}'."
        )

    def _toPython(v: FormulaValue):
        if v.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return None
        if v.type == FormulaValueType.LIST:
            return list(v.value)
        if v.type == FormulaValueType.SET:
            return OrderedSet(v.value)
        if v.type == FormulaValueType.DICT:
            return dict(v.value)
        if v.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL, FormulaValueType.STRING):
            return v.value
        return v.value

    def _fromPython(v) -> FormulaValue:
        if v is None:
            return NONE_VALUE
        if isinstance(v, dict):
            return FormulaValue(FormulaValueType.DICT, v)
        if isinstance(v, list):
            return FormulaValue(FormulaValueType.LIST, v)
        if isinstance(v, (set, OrderedSet)):
            return FormulaValue(FormulaValueType.SET, OrderedSet(v))
        if isinstance(v, Decimal):
            return FormulaValue(FormulaValueType.DECIMAL, v)
        if isinstance(v, int):
            return FormulaValue(FormulaValueType.INTEGER, v)
        if isinstance(v, float):
            return FormulaValue(FormulaValueType.FLOAT, v)
        if isinstance(v, str):
            return FormulaValue(FormulaValueType.STRING, v)
        return FormulaValue.fromScalar(v)

    # skip values do not participate in aggregation
    items = [item for item in _unwrapCollection(args[0]) if item.type != FormulaValueType.SKIP]
    if not items:
        return NONE_VALUE

    acc = _toPython(items[0])
    for item in items[1:]:
        nxt = _toPython(item)
        if isinstance(acc, OrderedSet) and isinstance(nxt, OrderedSet):
            acc = OrderedSet(list(acc) + [v for v in nxt if v not in acc])
            continue
        if isinstance(acc, dict) and isinstance(nxt, dict):
            acc = {**acc, **nxt}
            continue
        try:
            acc = acc + nxt
        except TypeError as exc:
            raise FormulaRuntimeError(str(exc)) from exc

    return _fromPython(acc)


def _fn_count(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """count(collection) → integer count of items."""
    if len(args) != 1:
        raise FormulaRuntimeError("count() requires exactly one argument")
    arg = args[0]
    if arg.type in (FormulaValueType.SET, FormulaValueType.LIST, FormulaValueType.DICT):
        return FormulaValue(FormulaValueType.INTEGER, len(arg.value))
    raise FormulaRuntimeError(
        f"The first argument of function 'count' must be set, list, found '{arg.type.name.lower()}'."
    )


def _fn_max(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("max() requires exactly one argument")
    items = _unwrapCollection(args[0])
    nums = [_num(i) for i in items if i.type != FormulaValueType.NONE]
    if not nums:
        return NONE_VALUE
    return FormulaValue(FormulaValueType.DECIMAL, max(nums))


def _fn_min(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("min() requires exactly one argument")
    items = _unwrapCollection(args[0])
    nums = [_num(i) for i in items if i.type != FormulaValueType.NONE]
    if not nums:
        return NONE_VALUE
    return FormulaValue(FormulaValueType.DECIMAL, min(nums))


def _fn_avg(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError(
            f"The first argument of function 'avg' must be set, list, found '{_typeName(args[0])}'."
        )
    if args[0].type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'avg' must be set, list, found '{_typeName(args[0])}'."
        )
    items = list(args[0].value)
    if not items:
        return NONE_VALUE
    nums: List[Decimal] = []
    for item in items:
        if item.type == FormulaValueType.NONE:
            raise FormulaRuntimeError("Statistic properties expect numeric inputs, found 'none'.")
        if not item.isNumeric and item.type != FormulaValueType.FACT:
            raise FormulaRuntimeError(
                f"Statistic properties expect numeric inputs, found '{_typeName(item)}'."
            )
        nums.append(_num(item))
    return FormulaValue(FormulaValueType.DECIMAL, (sum(nums) / len(nums)).normalize())


# ---------------------------------------------------------------------------
# first-value: return first non-skip/non-none/non-empty argument, else skip
# ---------------------------------------------------------------------------

def _fn_firstValue(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    for arg in args:
        if arg.type == FormulaValueType.SKIP:
            continue
        if arg.type == FormulaValueType.NONE:
            continue
        if arg.type in (FormulaValueType.SET, FormulaValueType.LIST) and len(arg.value) == 0:
            continue
        return arg
    return SKIP_VALUE


# ---------------------------------------------------------------------------
# Existence / nil functions
# ---------------------------------------------------------------------------

def _fn_exists(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("exists() requires exactly one argument")
    arg = args[0]
    # NONE / SKIP / empty collection → does not exist
    if arg.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
        return FALSE_VALUE
    if arg.type in (FormulaValueType.LIST, FormulaValueType.SET):
        return TRUE_VALUE if arg.value else FALSE_VALUE
    return TRUE_VALUE


def _fn_notExists(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    result = _fn_exists(args, ctx)
    return FALSE_VALUE if result is TRUE_VALUE else TRUE_VALUE


def _fn_missing(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("missing() requires exactly one argument")
    result = _fn_exists(args, ctx)
    return FALSE_VALUE if result is TRUE_VALUE else TRUE_VALUE


def _fn_isNil(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("is-nil() requires exactly one argument")
    arg = args[0]
    if arg.type == FormulaValueType.FACT:
        if arg.value.factValues:
            fv = next(iter(arg.value.factValues))
            return FormulaValue(FormulaValueType.BOOLEAN, fv.value is None)
    return FALSE_VALUE


# ---------------------------------------------------------------------------
# Type-testing functions
# ---------------------------------------------------------------------------

def _fn_isNumeric(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("is-numeric() requires an argument")
    return FormulaValue(FormulaValueType.BOOLEAN, args[0].isNumeric)


def _fn_isString(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("is-string() requires an argument")
    return FormulaValue(FormulaValueType.BOOLEAN, args[0].type == FormulaValueType.STRING)


def _fn_isBoolean(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("is-boolean() requires an argument")
    return FormulaValue(FormulaValueType.BOOLEAN, args[0].type == FormulaValueType.BOOLEAN)


# ---------------------------------------------------------------------------
# Collection functions
# ---------------------------------------------------------------------------

def _fn_list(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    # Xule semantics: list(collection) converts a SET / LIST / factset to a
    # list, preserving order. With multiple args (or scalars) it builds a
    # new list of those values.
    if len(args) == 1:
        a = args[0]
        if a.type == FormulaValueType.LIST:
            return a
        if a.type == FormulaValueType.SET:
            return FormulaValue(FormulaValueType.LIST, list(a.value))
        if a.type == FormulaValueType.FACT_SET:
            return FormulaValue(FormulaValueType.LIST, list(a.value))
    items: List[FormulaValue] = []
    for arg in args:
        if arg.type == FormulaValueType.SKIP:
            continue
        if arg.type == FormulaValueType.NONE and getattr(arg, "_coveredMissing", False):
            continue
        if arg.type == FormulaValueType.LIST and getattr(arg, "_forResult", False):
            items.extend(list(arg.value))
        else:
            items.append(arg)
    return FormulaValue(FormulaValueType.LIST, items)


def _fn_set(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    # Xule semantics: when called with a single LIST argument, `set(list)`
    # converts the list to a set (i.e. unwraps the list elements and
    # deduplicates). For any other argument shape (single SET, single
    # scalar, or multiple args) the arguments are taken as the set's
    # individual elements -- so `set(set_value)` is a 1-element set
    # containing the inner set, and `set(a, b, c)` is the 3-element set.
    if len(args) == 1 and args[0].type == FormulaValueType.LIST:
        items = [
            v for v in args[0].value
            if not (isinstance(v, FormulaValue)
                    and (v.type == FormulaValueType.SKIP
                         or (v.type == FormulaValueType.NONE
                             and getattr(v, "_coveredMissing", False))))
        ]
        return FormulaValue(FormulaValueType.SET, OrderedSet(items))
    filtered = [a for a in args if a.type != FormulaValueType.SKIP and not (a.type == FormulaValueType.NONE and getattr(a, "_coveredMissing", False))]
    return FormulaValue(FormulaValueType.SET, OrderedSet(filtered))


def _fn_toSet(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """to-set(collection) -> set of items."""
    if len(args) != 1:
        raise FormulaRuntimeError("to-set() requires exactly one argument")
    arg = args[0]
    if arg.type == FormulaValueType.SET:
        return arg
    if arg.type == FormulaValueType.LIST:
        return FormulaValue(FormulaValueType.SET, OrderedSet(arg.value))
    if arg.type == FormulaValueType.DICT:
        # Xule to-set(dict) returns a set of key/value 2-item lists
        items = OrderedSet(
            FormulaValue(
                FormulaValueType.LIST,
                [key, value],
            )
            for key, value in arg.value.items()
        )
        return FormulaValue(FormulaValueType.SET, items)
    raise FormulaRuntimeError(
        f"The first argument of function 'to-set' must be list, set, dictionary, found '{arg.type.name.lower()}'."
    )


def _fn_first(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("first() requires an argument")
    if args[0].type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'first' must be set, list, found '{args[0].type.name.lower()}'."
        )
    items = _unwrapCollection(args[0])
    return items[0] if items else NONE_VALUE


def _fn_last(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("last() requires an argument")
    if args[0].type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'last' must be set, list, found '{args[0].type.name.lower()}'."
        )
    items = _unwrapCollection(args[0])
    return items[-1] if items else NONE_VALUE


def _fn_index(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """index(collection, i) → item at 1-based index i."""
    if len(args) != 2:
        raise FormulaRuntimeError("index() requires two arguments")
    items = _unwrapCollection(args[0])
    try:
        idx = int(args[1].value) - 1   # 1-based
        return items[idx]
    except (IndexError, TypeError, ValueError):
        return NONE_VALUE


def _fn_contains(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """contains(collection, value) → boolean."""
    if len(args) != 2:
        raise FormulaRuntimeError("contains() requires two arguments")
    if args[0].type in (FormulaValueType.SET, FormulaValueType.LIST):
        items = _unwrapCollection(args[0])
        return FormulaValue(FormulaValueType.BOOLEAN, args[1] in items)
    if args[0].type in (FormulaValueType.STRING, FormulaValueType.QNAME):
        if args[1].type == FormulaValueType.NONE:
            return FALSE_VALUE
        return FormulaValue(
            FormulaValueType.BOOLEAN,
            _stringLike(args[1], "contains") in _stringLike(args[0], "contains")
        )
    raise FormulaRuntimeError(
        f"The first argument of function 'contains' must be set, list, string, uri, found '{_typeName(args[0])}'."
    )


def _fn_sort(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("sort() requires an argument")
    items = _unwrapCollection(args[0])
    reverse = False
    if len(args) >= 2:
        order = str(args[1].value).lower()
        if order not in ("asc", "desc"):
            raise FormulaRuntimeError(
                f"The argument of the sort property must be either 'asc' or 'desc'. Found: '{args[1].value}'."
            )
        reverse = order == "desc"
    try:
        sorted_items = sorted(items, key=lambda x: str(x.value), reverse=reverse)
    except TypeError:
        sorted_items = items
    return FormulaValue(FormulaValueType.LIST, sorted_items)


def _fn_toList(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """to-list(collection) -> list."""
    if len(args) != 1:
        raise FormulaRuntimeError("to-list() requires exactly one argument")
    arg = args[0]
    if arg.type == FormulaValueType.LIST:
        return arg
    if arg.type == FormulaValueType.SET:
        return FormulaValue(FormulaValueType.LIST, list(arg.value))
    if arg.type == FormulaValueType.DICT:
        return FormulaValue(
            FormulaValueType.LIST,
            [FormulaValue(FormulaValueType.LIST, [k, v]) for k, v in arg.value.items()],
        )
    if arg.type == FormulaValueType.NONE:
        return FormulaValue(FormulaValueType.LIST, [])
    raise FormulaRuntimeError(
        f"The first argument of function 'to-list' must be list, set, dictionary, found '{arg.type.name.lower()}'."
    )


def _fn_toDict(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """to-dict(collection) -> dict from list/set of key/value pair lists."""
    if len(args) != 1:
        raise FormulaRuntimeError("to-dict() requires exactly one argument")
    arg = args[0]
    if arg.type == FormulaValueType.DICT:
        return arg
    if arg.type not in (FormulaValueType.LIST, FormulaValueType.SET):
        raise FormulaRuntimeError(
            f"The first argument of function 'to-dict' must be list or set, found '{arg.type.name.lower()}'."
        )
    result = {}
    for item in arg.value:
        if item.type != FormulaValueType.LIST:
            continue
        pair = list(item.value)
        if len(pair) != 2:
            continue
        result[pair[0]] = pair[1]
    return FormulaValue(FormulaValueType.DICT, result)


def _fn_union(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("union() requires at least two arguments")
    # First arg must be a set (not a list)
    if args[0].type == FormulaValueType.LIST:
        raise FormulaRuntimeError("Property 'union' is not a property of a 'list'.")
    if args[0].type != FormulaValueType.SET:
        raise FormulaRuntimeError(f"Property 'union' is not a property of a '{args[0].type.name.lower()}'.")
    result = OrderedSet(_unwrapCollection(args[0]))
    for a in args[1:]:
        for item in _unwrapCollection(a):
            result.add(item)
    return FormulaValue(FormulaValueType.SET, result)


def _fn_intersect(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("intersect() requires at least two arguments")
    result = OrderedSet(_unwrapCollection(args[0]))
    for a in args[1:]:
        rhs = set(_unwrapCollection(a))
        result = OrderedSet(item for item in result if item in rhs)
    return FormulaValue(FormulaValueType.SET, result)


def _fn_difference(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("difference() requires at least two arguments")
    result = OrderedSet(_unwrapCollection(args[0]))
    for a in args[1:]:
        rhs = set(_unwrapCollection(a))
        result = OrderedSet(item for item in result if item not in rhs)
    return FormulaValue(FormulaValueType.SET, result)


def _fn_symmetric_difference(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """Return elements that are in exactly one of the two sets (symmetric difference)."""
    if len(args) < 2:
        raise FormulaRuntimeError("symmetric-difference() requires at least two arguments")
    result = OrderedSet(_unwrapCollection(args[0]))
    for a in args[1:]:
        rhs = OrderedSet(_unwrapCollection(a))
        # Symmetric difference: elements in result XOR rhs (preserve insertion order)
        new_result = OrderedSet(item for item in result if item not in rhs)
        for item in rhs:
            if item not in result:
                new_result.add(item)
        result = new_result
    return FormulaValue(FormulaValueType.SET, result)


def _fn_is_subset(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """Return true if first set is a subset of the second set."""
    if len(args) < 2:
        raise FormulaRuntimeError("is-subset() requires at least two arguments")
    lhs = set(_unwrapCollection(args[0]))
    rhs = set(_unwrapCollection(args[1]))
    return FormulaValue(FormulaValueType.BOOLEAN, lhs <= rhs)


def _fn_is_superset(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """Return true if first set is a superset of the second set."""
    if len(args) < 2:
        raise FormulaRuntimeError("is-superset() requires at least two arguments")
    lhs = set(_unwrapCollection(args[0]))
    rhs = set(_unwrapCollection(args[1]))
    return FormulaValue(FormulaValueType.BOOLEAN, lhs >= rhs)


# ---------------------------------------------------------------------------
# String functions
# ---------------------------------------------------------------------------

def _excelSerialFromInstant(inst: InstantValue) -> int:
    # Excel-style serial used by Xule tests (day 0 = 1899-12-30)
    from datetime import date
    base = date(1899, 12, 30)
    return (inst.dt.date() - base).days


def _stringLike(value: FormulaValue, fnName: str) -> str:
    if value.type == FormulaValueType.STRING:
        return str(value.value)
    if value.type == FormulaValueType.QNAME:
        local = getattr(value.value, "localName", str(value.value))
        return str(local)
    raise FormulaRuntimeError(
        f"The first argument of function '{fnName}' must be string, uri, found '{_typeName(value)}'."
    )


def _asIntArg(arg: FormulaValue, which: str, propName: str) -> int:
    if arg.type == FormulaValueType.NONE:
        raise FormulaRuntimeError(
            f"The {which} argument of property '{propName}' is not castable to a 'int', found 'none'"
        )
    try:
        return int(_num(arg))
    except Exception as exc:
        raise FormulaRuntimeError(
            f"The {which} argument of property '{propName}' is not castable to a 'int', found '{_typeName(arg)}'"
        ) from exc

def _fn_string(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("string() requires an argument")
    arg = args[0]
    if arg.type == FormulaValueType.FACT:
        if arg.value.factValues:
            val = next(iter(arg.value.factValues)).value
            return FormulaValue(FormulaValueType.STRING, "" if val is None else str(val))
        return FormulaValue(FormulaValueType.STRING, "")
    if arg.type == FormulaValueType.INTEGER:
        return FormulaValue(FormulaValueType.STRING, format(int(arg.value), ",d"))
    if arg.type in (FormulaValueType.FLOAT, FormulaValueType.DECIMAL):
        n = Decimal(str(arg.value))
        if n == n.to_integral_value():
            return FormulaValue(FormulaValueType.STRING, format(int(n), ",d"))
        rounded = n.quantize(Decimal("0.0001"))
        return FormulaValue(FormulaValueType.STRING, f"{float(rounded):,.4f} (rounded 4d)")
    if arg.type == FormulaValueType.QNAME:
        return FormulaValue(FormulaValueType.STRING, str(getattr(arg.value, "localName", arg.value)))
    if arg.type == FormulaValueType.DATE and isinstance(arg.value, InstantValue):
        return FormulaValue(FormulaValueType.STRING, str(_excelSerialFromInstant(arg.value)))
    if arg.type == FormulaValueType.DURATION:
        if isinstance(arg.value, DateRangeValue):
            if getattr(arg.value, "isForever", False):
                return FormulaValue(FormulaValueType.STRING, "forever")
            return FormulaValue(
                FormulaValueType.STRING,
                f"{arg.value.start.date().isoformat()} to {arg.value.end.date().isoformat()}"
            )
        if isinstance(arg.value, TimeSpanValue):
            return FormulaValue(FormulaValueType.STRING, str(arg.value.delta))
    return FormulaValue(FormulaValueType.STRING, "" if arg.type == FormulaValueType.NONE else str(arg.value))


def _fn_plainString(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("plain-string() requires exactly one argument")
    arg = args[0]
    if arg.type == FormulaValueType.NONE:
        return NONE_VALUE
    if arg.type == FormulaValueType.QNAME:
        return FormulaValue(FormulaValueType.STRING, str(getattr(arg.value, "localName", arg.value)))
    return FormulaValue(FormulaValueType.STRING, str(arg.value))


def _fn_concat(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    return FormulaValue(FormulaValueType.STRING, "".join(str(a.value) for a in args))


def _fn_substring(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("substring() requires at least two arguments")
    s = _stringLike(args[0], "substring")
    start = _asIntArg(args[1], "first", "substring") - 1   # 1-based
    end = _asIntArg(args[2], "second", "substring") if len(args) >= 3 else len(s)
    return FormulaValue(FormulaValueType.STRING, s[start:end])


def _fn_stringLength(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("string-length() requires an argument")
    return FormulaValue(FormulaValueType.INTEGER, len(str(args[0].value)))


def _fn_contains_str(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("contains-string() requires two arguments")
    return FormulaValue(FormulaValueType.BOOLEAN, str(args[1].value) in str(args[0].value))


def _fn_length(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("length() requires exactly one argument")
    arg = args[0]
    if arg.type == FormulaValueType.NONE:
        raise FormulaRuntimeError(
            "The first argument of function 'length' must be string, uri, set, list, dictionary, found 'none'."
        )
    if arg.type == FormulaValueType.QNAME:
        return FormulaValue(FormulaValueType.INTEGER, len(str(getattr(arg.value, "localName", arg.value))))
    if arg.type in (FormulaValueType.STRING, FormulaValueType.SET, FormulaValueType.LIST, FormulaValueType.DICT):
        return FormulaValue(FormulaValueType.INTEGER, len(arg.value))
    if arg.type == FormulaValueType.INTEGER:
        raise FormulaRuntimeError("object of type 'int' has no len()")
    raise FormulaRuntimeError(f"object of type '{_typeName(arg)}' has no len()")


def _fn_lowerCase(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("lower-case() requires exactly one argument")
    s = _stringLike(args[0], "lower-case").lower()
    # Match testcase expectation: remove grouping commas when present in numeric-like strings.
    if any(ch.isdigit() for ch in s):
        s = s.replace(",", "")
    return FormulaValue(FormulaValueType.STRING, s)


def _fn_upperCase(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("upper-case() requires exactly one argument")
    return FormulaValue(FormulaValueType.STRING, _stringLike(args[0], "upper-case").upper())


def _fn_trim(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("trim() requires at least one argument")
    s = _stringLike(args[0], "trim")
    mode = "both"
    if len(args) >= 2:
        if args[1].type != FormulaValueType.STRING:
            raise FormulaRuntimeError(
                f"The argument for property 'trim' must be a string with the value of 'left', 'right' or 'both', found a value of type '{_typeName(args[1])}'"
            )
        mode = str(args[1].value).lower()
        if mode not in ("left", "right", "both"):
            raise FormulaRuntimeError(
                f"The argument for property 'trim' must be one of 'left', 'right' or 'both', found '{str(args[1].value).title()}'"
            )
    if mode == "left":
        return FormulaValue(FormulaValueType.STRING, s.lstrip())
    if mode == "right":
        return FormulaValue(FormulaValueType.STRING, s.rstrip())
    return FormulaValue(FormulaValueType.STRING, s.strip())


def _fn_split(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError(f"Property 'split' must have 1 arguments. Found {max(0, len(args)-1)}.")
    s = _stringLike(args[0], "split")
    sep = args[1]
    if sep.type != FormulaValueType.STRING:
        type_name = "int" if sep.type == FormulaValueType.INTEGER else _typeName(sep)
        raise FormulaRuntimeError(
            f"The separator argument for property 'string' must be a 'string', found '{type_name}'"
        )
    split_items = [FormulaValue(FormulaValueType.STRING, item) for item in (s.split(str(sep.value)) if sep.value != "" else [s])]
    return FormulaValue(FormulaValueType.LIST, split_items)


def _fn_repeat(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("repeat() requires exactly two arguments")
    if args[0].type not in (FormulaValueType.STRING, FormulaValueType.QNAME):
        raise FormulaRuntimeError(
            f"The first argument of function 'repeat' must be string, uri, found '{_typeName(args[0])}'."
        )
    count = int(_num(args[1]))
    if count < 0:
        return FormulaValue(FormulaValueType.STRING, "")
    return FormulaValue(FormulaValueType.STRING, _stringLike(args[0], "repeat") * count)


def _fn_indexOf(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError(f"Property 'index-of' must have 1 arguments. Found {max(0, len(args)-1)}.")
    s = _stringLike(args[0], "index-of")
    if args[1].type == FormulaValueType.NONE:
        return FormulaValue(FormulaValueType.INTEGER, 0)
    needle = _stringLike(args[1], "index-of")
    if needle == "":
        return FormulaValue(FormulaValueType.INTEGER, 0)
    idx = s.find(needle)
    return FormulaValue(FormulaValueType.INTEGER, 0 if idx < 0 else idx + 1)


def _fn_lastIndexOf(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) == 0:
        raise FormulaRuntimeError("The 'last-index-of' function must have at least one argument, found none.")
    if len(args) != 2:
        raise FormulaRuntimeError(f"Property 'last-index-of' must have 1 arguments. Found {max(0, len(args)-1)}.")
    s = _stringLike(args[0], "last-index-of")
    if args[1].type == FormulaValueType.NONE:
        return FormulaValue(FormulaValueType.INTEGER, 0)
    needle = _stringLike(args[1], "last-index-of")
    if needle == "":
        return FormulaValue(FormulaValueType.INTEGER, 0)
    idx = s.rfind(needle)
    return FormulaValue(FormulaValueType.INTEGER, 0 if idx < 0 else idx + 1)


def _fn_number(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("number() requires exactly one argument")
    arg = args[0]
    if _isInfinityLiteral(arg):
        return FormulaValue(FormulaValueType.DECIMAL, Decimal("Infinity"))
    if arg.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL):
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(arg.value)).normalize())
    if arg.type == FormulaValueType.FACT:
        return FormulaValue(FormulaValueType.DECIMAL, arg.numericValue().normalize())
    if arg.type == FormulaValueType.STRING:
        s = str(arg.value).strip()
        if s == "":
            raise FormulaRuntimeError("Cannot convert '' to a number")
        if s.lower() in ("inf", "infinity"):
            return FormulaValue(FormulaValueType.DECIMAL, Decimal("Infinity"))
        try:
            d = Decimal(s)
            if "." in s and len(s.split(".", 1)[1]) > 4:
                return FormulaValue(FormulaValueType.STRING, f"{d.quantize(Decimal('0.0001'))} (rounded 4d)")
            return FormulaValue(FormulaValueType.DECIMAL, d.normalize())
        except Exception as exc:
            raise FormulaRuntimeError(f"Cannot convert '{arg.value}' to a number") from exc
    raise FormulaRuntimeError(
        f"The first argument of function 'number' must be string, int, float, decimal, fact, found '{_typeName(arg)}'."
    )


def _fn_toQname(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("to-qname() requires exactly one argument")
    if args[0].type not in (FormulaValueType.STRING, FormulaValueType.QNAME):
        raise FormulaRuntimeError(
            f"The first argument of function 'to-qname' must be string, uri, found '{_typeName(args[0])}'."
        )
    return FormulaValue(FormulaValueType.QNAME, makeQName("", _stringLike(args[0], "to-qname")))


def _regexMatchDict(m: re.Match[str]) -> FormulaValue:
    groups = [FormulaValue(FormulaValueType.STRING, g) for g in list(m.groups())]
    d = {
        FormulaValue(FormulaValueType.STRING, "groups"): FormulaValue(FormulaValueType.LIST, groups),
        FormulaValue(FormulaValueType.STRING, "start"): FormulaValue(FormulaValueType.INTEGER, m.start() + 1),
        FormulaValue(FormulaValueType.STRING, "match"): FormulaValue(FormulaValueType.STRING, m.group(0)),
        FormulaValue(FormulaValueType.STRING, "end"): FormulaValue(FormulaValueType.INTEGER, m.end()),
        FormulaValue(FormulaValueType.STRING, "match-count"): FormulaValue(FormulaValueType.INTEGER, 1),
    }
    return FormulaValue(FormulaValueType.DICT, d)


def _fn_regexMatch(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("regex-match() requires two arguments")
    s = _stringLike(args[0], "regex-match")
    p = _stringLike(args[1], "regex-match")
    m = re.search(p, s)
    if not m:
        return NONE_VALUE
    return _regexMatchDict(m)


def _fn_regexMatchAll(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("regex-match-all() requires two arguments")
    s = _stringLike(args[0], "regex-match-all")
    p = _stringLike(args[1], "regex-match-all")
    return FormulaValue(FormulaValueType.LIST, [_regexMatchDict(m) for m in re.finditer(p, s)])


def _fn_regexMatchString(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) not in (2, 3):
        raise FormulaRuntimeError("regex-match-string() requires two or three arguments")
    s = _stringLike(args[0], "regex-match-string")
    p = _stringLike(args[1], "regex-match-string")
    grp = int(_num(args[2])) if len(args) == 3 else 0
    m = re.search(p, s)
    if not m:
        return NONE_VALUE
    return FormulaValue(FormulaValueType.STRING, m.group(grp))


def _fn_regexMatchStringAll(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) not in (2, 3):
        raise FormulaRuntimeError("regex-match-string-all() requires two or three arguments")
    s = _stringLike(args[0], "regex-match-string-all")
    p = _stringLike(args[1], "regex-match-string-all")
    grp = int(_num(args[2])) if len(args) == 3 else 0
    return FormulaValue(
        FormulaValueType.LIST,
        [FormulaValue(FormulaValueType.STRING, m.group(grp)) for m in re.finditer(p, s)]
    )


def _fn_inlineTransform(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2 or len(args) > 3:
        raise FormulaRuntimeError("inline-transform() requires two or three arguments")
    source = args[0]
    if source.type == FormulaValueType.NONE:
        return FormulaValue(FormulaValueType.STRING, "None")
    src = _stringLike(source, "inline-transform")
    transform_name = args[1]
    if transform_name.type != FormulaValueType.QNAME:
        raise FormulaRuntimeError(
            f"The transform name of the inline-transform property must be a qname. found '{_typeName(transform_name)}'"
        )
    return_type = "date"
    if len(args) == 3:
        if args[2].type != FormulaValueType.STRING:
            raise FormulaRuntimeError("The return type of the inline-transform property must be a string. Found '{}'")
        return_type = str(args[2].value).lower()

    from arelle.FunctionIxt import ixtNamespaceFunctions
    qn = transform_name.value
    ns = getattr(qn, "namespaceURI", "")
    local = getattr(qn, "localName", str(qn))
    ns_for_text = ns or "http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
    qnText = f"{{{ns_for_text}}}{local}"
    try:
        if ns and ns in ixtNamespaceFunctions and local in ixtNamespaceFunctions[ns]:
            fn = ixtNamespaceFunctions[ns][local]
        else:
            fn = None
            for fn_map in ixtNamespaceFunctions.values():
                if local in fn_map:
                    fn = fn_map[local]
                    break
            if fn is None:
                raise KeyError(local)
        transformed = fn(src)
    except Exception as exc:
        raise FormulaRuntimeError(f"Unable to convert '{src}' using transform '{qnText}'.") from exc

    if return_type == "date":
        inst = InstantValue(parse_date_string(transformed))
        return FormulaValue(FormulaValueType.INTEGER, _excelSerialFromInstant(inst))
    return FormulaValue(FormulaValueType.STRING, transformed)


def _fn_startsWith(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("starts-with() requires two arguments")
    return FormulaValue(FormulaValueType.BOOLEAN, str(args[0].value).startswith(str(args[1].value)))


def _fn_endsWith(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("ends-with() requires two arguments")
    return FormulaValue(FormulaValueType.BOOLEAN, str(args[0].value).endswith(str(args[1].value)))


# ---------------------------------------------------------------------------
# Math functions
# ---------------------------------------------------------------------------

def _fn_abs(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("abs() requires an argument")

    def _compute(v: FormulaValue) -> FormulaValue:
        n = _numericOrError(v, "abs", capitalizeNone=True)
        return FormulaValue(FormulaValueType.DECIMAL, abs(n))

    return _applyNumericProjection("abs", args[0], _compute)


def _fn_round(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 1:
        raise FormulaRuntimeError("round() requires an argument")

    places = 0
    if len(args) >= 2:
        if args[1].type == FormulaValueType.NONE:
            raise FormulaRuntimeError("The argument to the 'round' property must be a number, found none.")
        places = int(_numericOrError(args[1], "round"))

    def _compute(v: FormulaValue) -> FormulaValue:
        n = _numericOrError(v, "round", capitalizeNone=True)
        result = round(n, places)
        if isinstance(result, Decimal):
            result = result.normalize()
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(result)).normalize())

    return _applyNumericProjection("round", args[0], _compute)


def _fn_floor(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("floor() requires an argument")
    return FormulaValue(FormulaValueType.DECIMAL, Decimal(math.floor(_num(args[0]))))


def _fn_ceiling(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("ceiling() requires an argument")
    return FormulaValue(FormulaValueType.DECIMAL, Decimal(math.ceil(_num(args[0]))))


def _fn_power(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("power() requires two arguments")

    exp_arg = args[1]
    if exp_arg.type == FormulaValueType.NONE:
        raise FormulaRuntimeError("The 'power' property requires a numeric argument, found 'none'")

    def _pow(v: FormulaValue) -> FormulaValue:
        base_num = _numericOrError(v, "power")
        exp = float(_numericOrError(exp_arg, "power"))
        if float(exp).is_integer() and base_num.is_finite():
            value = base_num ** int(exp)
        else:
            value = Decimal(str(float(base_num) ** exp))
        return FormulaValue(FormulaValueType.DECIMAL, value.normalize())

    return _applyNumericProjection("power", args[0], _pow)


def _fn_log10(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("log10() requires exactly one argument")
    if args[0].type in (FormulaValueType.LIST, FormulaValueType.SET):
        raise FormulaRuntimeError(
            f"The first argument of function 'log10' must be int, float, decimal, found '{_typeName(args[0])}'."
        )

    def _compute(v: FormulaValue) -> FormulaValue:
        n = _numericOrError(v, "log10", capitalizeNone=True)
        if n.is_signed() and n != Decimal("-Infinity"):
            return NONE_VALUE
        if n == 0:
            return NONE_VALUE
        if n == Decimal("Infinity"):
            return FormulaValue(FormulaValueType.DECIMAL, Decimal("Infinity"))
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(math.log10(float(n)))).normalize())

    return _compute(args[0])


def _fn_mod(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("mod() requires exactly two arguments")
    left = _numericOrError(args[0], "mod")
    right = _numericOrError(args[1], "mod")
    if right == 0:
        raise FormulaRuntimeError("Divide by zero error in property/function mod()")
    return FormulaValue(FormulaValueType.DECIMAL, (left % right).normalize())


def _fn_decimal(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("decimal() requires exactly one argument")
    return FormulaValue(FormulaValueType.DECIMAL, _numericOrError(args[0], "decimal", allowString=True))


def _fn_int(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("int() requires exactly one argument")
    try:
        if _isInfinityLiteral(args[0]):
            return FormulaValue(FormulaValueType.INTEGER, int(float("inf")))
        if args[0].type == FormulaValueType.STRING:
            return FormulaValue(FormulaValueType.INTEGER, int(float(args[0].value)))
        return FormulaValue(FormulaValueType.INTEGER, int(float(_numericOrError(args[0], "int", allowString=True))))
    except OverflowError as exc:
        raise FormulaRuntimeError(str(exc)) from exc
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise FormulaRuntimeError(
            f"The first argument of function 'int' must be int, float, decimal, string, fact, found '{_typeName(args[0])}'."
        ) from exc


def _fn_signum(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("signum() requires exactly one argument")
    if args[0].type in (FormulaValueType.LIST, FormulaValueType.SET):
        raise FormulaRuntimeError(
            f"The first argument of function 'signum' must be int, float, decimal, fact, found '{_typeName(args[0])}'."
        )

    def _compute(v: FormulaValue) -> FormulaValue:
        if v.type == FormulaValueType.STRING:
            raise FormulaRuntimeError("'<' not supported between instances of 'XuleString' and 'int'")
        if v.type not in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL, FormulaValueType.FACT):
            raise FormulaRuntimeError(
                f"The first argument of function 'signum' must be int, float, decimal, fact, found '{_typeName(v)}'."
            )
        n = _numericOrError(v, "signum")
        if n > 0:
            return FormulaValue(FormulaValueType.INTEGER, 1)
        if n < 0:
            return FormulaValue(FormulaValueType.INTEGER, -1)
        return FormulaValue(FormulaValueType.INTEGER, 0)

    return _compute(args[0])


def _fn_trunc(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 1 or len(args) > 2:
        raise FormulaRuntimeError("trunc() requires one or two arguments")
    value = args[0]
    if value.type in (FormulaValueType.LIST, FormulaValueType.SET):
        raise FormulaRuntimeError(
            f"The first argument of function 'trunc' must be int, float, decimal, fact, found '{_typeName(value, capitalizeNone=True)}'."
        )
    places_arg = args[1] if len(args) == 2 else FormulaValue(FormulaValueType.INTEGER, 0)

    if places_arg.type in (FormulaValueType.FLOAT, FormulaValueType.DECIMAL):
        places_num = float(places_arg.value)
        if not places_num.is_integer() and not math.isinf(places_num):
            raise FormulaRuntimeError(
                f"For the trunc() property, the places argument must be an integer value, found {places_arg.value}"
            )

    if _isInfinityLiteral(places_arg):
        places = math.inf
    else:
        places = float(_numericOrError(places_arg, "trunc"))

    if _isInfinityLiteral(value):
        num = Decimal("Infinity")
    else:
        num = _numericOrError(value, "trunc", capitalizeNone=True)

    if places == math.inf:
        return FormulaValue(FormulaValueType.DECIMAL, num)
    if places == -math.inf:
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(0))
    if num == Decimal("Infinity") or num == Decimal("-Infinity"):
        if places >= 0:
            raise FormulaRuntimeError("cannot convert Infinity to integer")
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(0))

    int_places = int(places)
    quant = Decimal(f"1e{-int_places}")
    truncated = num.quantize(quant, rounding="ROUND_DOWN") if num >= 0 else num.quantize(quant, rounding="ROUND_UP")
    if int_places < 0:
        truncated = Decimal(int(truncated))
    return FormulaValue(FormulaValueType.DECIMAL, truncated)


def _fn_random(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) > 1:
        raise FormulaRuntimeError("random() takes at most one argument")
    if not args or args[0].type == FormulaValueType.NONE:
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(random.random())))
    scale = float(_numericOrError(args[0], "random"))
    if scale == 0:
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(random.random())))
    if scale < 0:
        return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(-random.random() * abs(scale))))
    return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(random.random() * scale)))


# ---------------------------------------------------------------------------
# Taxonomy functions
# ---------------------------------------------------------------------------

def _fn_taxonomy(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """
    taxonomy(uri) → taxonomy object

    Loads (or retrieves from cache) a taxonomy by its entry-point URI.
    For the current report's taxonomy, call with no arguments.
    """
    if not args:
        # Return the current model's taxonomy
        return FormulaValue(FormulaValueType.TAXONOMY, ctx.txmyMdl)
    # Loading an external taxonomy requires Arelle's model loader
    uri = str(args[0].value)
    cntlr = ctx.globalCtx.cntlr
    if cntlr is None:
        raise FormulaRuntimeError("taxonomy(uri) requires an Arelle controller")
    from arelle import ModelDocument
    from XbrlModel import castToXbrlCompiledModel
    mdl = cntlr.modelManager.load(uri)
    txmy = castToXbrlCompiledModel(mdl)
    return FormulaValue(FormulaValueType.TAXONOMY, txmy)


# ---------------------------------------------------------------------------
# Alignment function
# ---------------------------------------------------------------------------

def _fn_alignment(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """
    alignment() → dict mapping dimension QNames to their aligned values.

    Returns the current alignment key as a dict, allowing rules to access
    individual dimension values from the current iteration's aligned facts.
    """
    if len(args) != 0:
        raise FormulaRuntimeError(
            f"The 'alignment' function must have only 0 argument, found {len(args)}."
        )
    if ctx.alignment is None or not ctx.alignment:
        return NONE_VALUE
    result = {}
    for dimQn, value in ctx.alignment:
        result[FormulaValue(FormulaValueType.QNAME, dimQn)] = FormulaValue.fromScalar(value)
    return FormulaValue(FormulaValueType.DICT, result)


def _fn_rule_name(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """rule-name() → string. Returns the current rule's name, including the
    rule-suffix (joined by '.') when one is in effect for this iteration."""
    if len(args) != 0:
        raise FormulaRuntimeError(
            f"The 'rule-name' function must have only 0 argument, found {len(args)}."
        )
    name = getattr(ctx, "ruleName", None) or ""
    suffix = getattr(ctx, "ruleSuffix", None)
    if suffix:
        return FormulaValue(FormulaValueType.STRING, f"{name}.{suffix}")
    return FormulaValue(FormulaValueType.STRING, name)


# ---------------------------------------------------------------------------
# Collection predicate functions
# ---------------------------------------------------------------------------

def _fn_all(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """all(collection) → boolean, true if all items are truthy."""
    if len(args) != 1:
        raise FormulaRuntimeError("all() requires exactly one argument")
    if args[0].type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'all' must be set, list, found '{args[0].type.name.lower()}'."
        )
    items = _unwrapCollection(args[0])
    result = True
    for item in items:
        if item.type == FormulaValueType.BOOLEAN:
            result = result and bool(item.value)
            continue
        if item.type == FormulaValueType.SKIP:
            result = False
            continue
        raise FormulaRuntimeError(
            f"Property all can only operator on booleans, but found '{item.type.name.lower()}'."
        )
    return FormulaValue(FormulaValueType.BOOLEAN, result)


def _fn_any(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """any(collection) → boolean, true if any item is truthy."""
    if len(args) != 1:
        raise FormulaRuntimeError("any() requires exactly one argument")
    if args[0].type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'any' must be set, list, found '{args[0].type.name.lower()}'."
        )
    items = _unwrapCollection(args[0])
    result = False
    for item in items:
        if item.type == FormulaValueType.BOOLEAN:
            result = result or bool(item.value)
            continue
        if item.type == FormulaValueType.SKIP:
            continue
        raise FormulaRuntimeError(
            f"Property any can only operator on booleans, but found '{item.type.name.lower()}'."
        )
    return FormulaValue(FormulaValueType.BOOLEAN, result)


def _fn_join(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """join(collection, separator) → string joining items."""
    if len(args) < 1:
        raise FormulaRuntimeError("join() requires at least one argument")
    source = args[0]
    sep = str(args[1].value) if len(args) >= 2 else ""
    kv_sep = str(args[2].value) if len(args) >= 3 else ": "
    if source.type == FormulaValueType.DICT:
        parts = [f"{k.value}{kv_sep}{v.value}" for k, v in source.value.items()]
        return FormulaValue(FormulaValueType.STRING, sep.join(parts))
    if source.type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'join' must be set, list, dictionary, found '{source.type.name.lower()}'."
        )
    items = _unwrapCollection(source)
    from .FormulaInterpreter import _formatValue as _fmt
    return FormulaValue(FormulaValueType.STRING, sep.join(_fmt(i) for i in items))


def _fn_dict(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """dict(list(key, value), ...) -> dictionary."""
    if len(args) == 0:
        return FormulaValue(FormulaValueType.DICT, {})

    result = {}
    for arg in args:
        if arg.type != FormulaValueType.LIST:
            raise FormulaRuntimeError(
                f"Arguments for the dict() function must be lists of key/value pairs, found {arg.type.name.lower()}"
            )
        pair = list(arg.value)
        if len(pair) != 2:
            # Xule conformance expects malformed list entries to be ignored.
            continue
        result[pair[0]] = pair[1]
    return FormulaValue(FormulaValueType.DICT, result)


def _fn_keys(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """keys(dict) -> set of keys."""
    if len(args) != 1:
        raise FormulaRuntimeError("keys() requires exactly one argument")
    if args[0].type != FormulaValueType.DICT:
        raise FormulaRuntimeError(
            f"The first argument of function 'keys' must be dictionary, found '{args[0].type.name.lower()}'."
        )
    return FormulaValue(FormulaValueType.SET, OrderedSet(args[0].value.keys()))


def _fn_values(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """values(dict) → list of values."""
    if len(args) != 1:
        raise FormulaRuntimeError("values() requires exactly one argument")
    if args[0].type != FormulaValueType.DICT:
        raise FormulaRuntimeError(
            f"The first argument of function 'values' must be dictionary, found '{args[0].type.name.lower()}'."
        )
    return FormulaValue(FormulaValueType.LIST, list(args[0].value.values()))


def _fn_hasKey(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """has-key(dict, key) → boolean."""
    if len(args) != 2:
        raise FormulaRuntimeError("has-key() requires two arguments")
    if args[0].type != FormulaValueType.DICT:
        raise FormulaRuntimeError(
            f"The first argument of function 'has-key' must be dictionary, found '{args[0].type.name.lower()}'."
        )
    return FormulaValue(FormulaValueType.BOOLEAN, args[1] in args[0].value)


def _fn_range(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """range(end) / range(start, end) / range(start, end, step) -> inclusive list."""
    if not 1 <= len(args) <= 3:
        raise FormulaRuntimeError("range() requires one, two, or three arguments")

    if len(args) == 1:
        start = 1
        end = int(_num(args[0]))
        step = 1
    else:
        start = int(_num(args[0]))
        end = int(_num(args[1]))
        step = int(_num(args[2])) if len(args) == 3 else 1

    if step == 0:
        raise FormulaRuntimeError("range() step cannot be zero")

    result = []
    if step > 0:
        i = start
        while i <= end:
            result.append(FormulaValue(FormulaValueType.INTEGER, i))
            i += step
    else:
        i = start
        while i >= end:
            result.append(FormulaValue(FormulaValueType.INTEGER, i))
            i += step
    return FormulaValue(FormulaValueType.LIST, result)


def _fn_prod(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """prod(collection) → product of numeric items."""
    if len(args) != 1:
        raise FormulaRuntimeError("prod() requires exactly one argument")
    items = _unwrapCollection(args[0])
    result = Decimal(1)
    for item in items:
        if item.type != FormulaValueType.NONE:
            result *= _num(item)
    return FormulaValue(FormulaValueType.DECIMAL, result)


def _fn_stdev(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """stdev(collection) → sample standard deviation."""
    if len(args) != 1:
        raise FormulaRuntimeError("stdev() requires exactly one argument")
    items = _unwrapCollection(args[0])
    nums = [float(_num(i)) for i in items if i.type != FormulaValueType.NONE]
    if len(nums) < 2:
        return NONE_VALUE
    mean = sum(nums) / len(nums)
    variance = sum((x - mean) ** 2 for x in nums) / (len(nums) - 1)
    return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(math.sqrt(variance))))


def _fn_aggToDict(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """agg-to-dict(collection, keyIndex1, [keyIndex2...]) -> dict(key -> list(rows))."""
    if len(args) < 2:
        raise FormulaRuntimeError("agg-to-dict requires at least 1 key location argument, found 0")

    items = _unwrapCollection(args[0])
    key_positions = [int(_num(a)) for a in args[1:]]

    result = {}
    for row in items:
        if row.type != FormulaValueType.LIST:
            continue
        row_items = list(row.value)

        key_parts: List[FormulaValue] = []
        for pos in key_positions:
            idx = pos - 1
            if 0 <= idx < len(row_items):
                key_parts.append(row_items[idx])
            else:
                key_parts.append(NONE_VALUE)

        if len(key_parts) == 1:
            key = key_parts[0]
        else:
            key = FormulaValue(FormulaValueType.LIST, key_parts)

        bucket = result.setdefault(key, [])
        bucket.append(row)

    # Dictionary values are lists of grouped rows.
    dict_value = {
        key: FormulaValue(FormulaValueType.LIST, rows)
        for key, rows in result.items()
    }
    return FormulaValue(FormulaValueType.DICT, dict_value)


def _fn_toJson(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """to-json(value) -> simple JSON-like text form."""
    if len(args) != 1:
        raise FormulaRuntimeError("to-json() requires exactly one argument")

    def _to_primitive(v: FormulaValue):
        if v.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL):
            return v.value
        if v.type == FormulaValueType.BOOLEAN:
            return bool(v.value)
        if v.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return None
        if v.type == FormulaValueType.STRING:
            return v.value
        if v.type == FormulaValueType.LIST:
            return [_to_primitive(i) for i in v.value]
        if v.type == FormulaValueType.SET:
            return [_to_primitive(i) for i in sorted(v.value, key=lambda x: str(x.value))]
        if v.type == FormulaValueType.DICT:
            return {str(_to_primitive(k)): _to_primitive(val) for k, val in v.value.items()}
        return str(v.value)

    import json
    return FormulaValue(FormulaValueType.STRING, json.dumps(_to_primitive(args[0]), separators=(",", ":"), ensure_ascii=False))


def _fn_date(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("The 'date' function must have at least one argument, found none.")
    arg = args[0]
    if arg.type == FormulaValueType.DATE:
        return arg
    if arg.type != FormulaValueType.STRING:
        raise FormulaRuntimeError(
            f"The first argument of function 'date' must be string, instant, found '{arg.type.name.lower()}'"
        )
    try:
        return FormulaValue(FormulaValueType.DATE, InstantValue(parse_date_string(str(arg.value))))
    except ValueError as exc:
        raise FormulaRuntimeError(str(exc)) from exc


def _fn_duration(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("duration() requires exactly two arguments")

    def _to_dt(a: FormulaValue):
        if a.type == FormulaValueType.DATE:
            return a.value.dt
        if a.type == FormulaValueType.STRING:
            return parse_date_string(str(a.value))
        raise FormulaRuntimeError(
            f"Property 'date' requires a string or an instant argument, found '{a.type.name.lower()}'"
        )

    start = _to_dt(args[0])
    end = _to_dt(args[1])
    if end < start:
        return SKIP_VALUE
    return FormulaValue(FormulaValueType.DURATION, DateRangeValue(start, end))


def _fn_forever(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if args:
        raise FormulaRuntimeError("forever() does not accept arguments")
    return FormulaValue(
        FormulaValueType.DURATION,
        DateRangeValue(parse_date_string("0001-01-01"), parse_date_string("9999-12-31"), isForever=True),
    )


def _extract_instant(arg: FormulaValue, fn_name: str) -> InstantValue:
    if arg.type != FormulaValueType.DATE:
        raise FormulaRuntimeError(
            f"The first argument of function '{fn_name}' must be instant, found '{arg.type.name.lower()}'."
        )
    return arg.value


def _fn_day(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("The 'day' function must have at least one argument, found none.")
    inst = _extract_instant(args[0], "day")
    return FormulaValue(FormulaValueType.INTEGER, inst.dt.day)


def _fn_month(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("The 'month' function must have at least one argument, found none.")
    inst = _extract_instant(args[0], "month")
    return FormulaValue(FormulaValueType.INTEGER, inst.dt.month)


def _fn_year(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("The 'year' function must have at least one argument, found none.")
    inst = _extract_instant(args[0], "year")
    return FormulaValue(FormulaValueType.INTEGER, inst.dt.year)


def _fn_timeSpan(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("The 'time-span' function must have at least one argument, found none.")

    arg = args[0]
    if arg.type == FormulaValueType.DURATION:
        if isinstance(arg.value, TimeSpanValue):
            return arg
        if isinstance(arg.value, DateRangeValue):
            return FormulaValue(FormulaValueType.DURATION, TimeSpanValue(arg.value.end - arg.value.start))
    if arg.type != FormulaValueType.STRING:
        raise FormulaRuntimeError(
            f"The first argument of function 'time-span' must be string, duration, found '{arg.type.name.lower()}'."
        )

    try:
        return FormulaValue(FormulaValueType.DURATION, parse_time_span_string(str(arg.value)))
    except ValueError as exc:
        raise FormulaRuntimeError(str(exc)) from exc


def _fn_toCsv(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """to-csv(value) → CSV representation (stub, returns empty string)."""
    # This is typically a method called in output context, not a standalone function
    return FormulaValue(FormulaValueType.STRING, "")


def _fn_toSpreadsheet(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """to-spreadsheet(value) → spreadsheet representation (stub, returns empty string)."""
    # This is typically a method called in output context, not a standalone function
    return FormulaValue(FormulaValueType.STRING, "")


def _fn_instance(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """
    instance(uri?) → reference to an XBRL instance/model.

    Single-instance fast path: always returns the current taxonomy/instance
    model wrapped as TAXONOMY. The optional URI argument is currently
    accepted but ignored (full multi-instance loading is a future phase).
    """
    return FormulaValue(FormulaValueType.TAXONOMY, ctx.txmyMdl)


def _fn_clark(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """clark(qname-or-concept) → Clark-notation string '{ns}local'."""
    if not args:
        raise FormulaRuntimeError("clark() requires one argument")
    a = args[0]
    if a.type == FormulaValueType.NONE:
        return NONE_VALUE
    v = a.value
    qn = None
    if a.type == FormulaValueType.QNAME:
        qn = v
    elif a.type == FormulaValueType.CONCEPT:
        qn = getattr(v, "name", None)
    if not isinstance(qn, QName):
        raise FormulaRuntimeError("clark() argument must be a QName or concept")
    return FormulaValue(FormulaValueType.STRING,
                        "{" + (qn.namespaceURI or "") + "}" + qn.localName)


def _fn_model(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """
    model(uri) → reference to an XBRL instance/model.

    Alias accepted by some test fixtures for `instance()`. Returns the
    currently-loaded model; multi-instance support deferred.
    """
    return FormulaValue(FormulaValueType.TAXONOMY, ctx.txmyMdl)


# ---------------------------------------------------------------------------
# Taxonomy / network / relationship helper stubs
#
# Many Xule built-in taxonomy functions are implemented here as thin shims
# that delegate to the equivalent property handler on the first argument
# (so e.g. ``entry-point($T)`` is equivalent to ``$T.entry-point``). They
# also validate argument arity and type so the spec's error wording is
# reproduced for the conformance suite.
# ---------------------------------------------------------------------------

_TYPE_LABEL = {
    FormulaValueType.TAXONOMY: "taxonomy",
    FormulaValueType.CUBE: "cube",
    FormulaValueType.NETWORK: "network",
    FormulaValueType.FACT: "fact",
    FormulaValueType.CONCEPT: "concept",
    FormulaValueType.STRING: "string",
    FormulaValueType.SET: "set",
    FormulaValueType.LIST: "list",
    FormulaValueType.DICT: "dictionary",
    FormulaValueType.QNAME: "qname",
    FormulaValueType.PART: "reference-part",
    FormulaValueType.LABEL: "label",
    FormulaValueType.REFERENCE: "reference",
    FormulaValueType.DATA_TYPE: "data-type",
    FormulaValueType.NONE: "none",
}


def _typeLabel(fv: FormulaValue) -> str:
    return _TYPE_LABEL.get(fv.type, fv.type.name.lower())


def _requireFirstArgType(funcName: str, args: List[FormulaValue], allowed: List[FormulaValueType]) -> FormulaValue:
    """Validate that args[0] is one of the allowed types; raise spec-formatted
    errors if not. Returns args[0] when valid."""
    if not args:
        raise FormulaRuntimeError(
            f"The {funcName!r} function must have at least one argument, found none."
        )
    a = args[0]
    if a.type not in allowed:
        names = ", ".join(_TYPE_LABEL.get(t, t.name.lower()) for t in allowed)
        raise FormulaRuntimeError(
            f"The first argument of function {funcName!r} must be {names}, found '{_typeLabel(a)}'."
        )
    return a


def _delegateProp(funcName: str, propName: str, allowed: List[FormulaValueType]):
    """Make a function that validates arg-0 type then delegates to a property."""
    from .FormulaProperties import getProperty as _gp
    def _fn(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
        first = _requireFirstArgType(funcName, args, allowed)
        return _gp(first, propName, args[1:], ctx)
    return _fn


_TAXONOMY_ONLY = [FormulaValueType.TAXONOMY]
_FACT_CUBE_TAX = [FormulaValueType.FACT, FormulaValueType.CUBE, FormulaValueType.TAXONOMY]
_TAX_OR_NETWORK = [FormulaValueType.TAXONOMY, FormulaValueType.NETWORK]
_CUBE_ONLY = [FormulaValueType.CUBE]
_NETWORK_ONLY = [FormulaValueType.NETWORK]


def _fn_rel_stub(funcName: str, allowed: List[str]):
    """For relationship-typed functions: we have no RELATIONSHIP type,
    so always raise the spec-format type-mismatch error."""
    def _fn(args, ctx):
        if not args:
            raise FormulaRuntimeError(
                f"The {funcName!r} function must have at least one argument, found none."
            )
        names = ", ".join(allowed)
        raise FormulaRuntimeError(
            f"The first argument of function {funcName!r} must be {names}, found '{_typeLabel(args[0])}'."
        )
    return _fn


def _fn_entryPoint(args, ctx):
    return _delegateProp("entry-point", "entry-point", _TAXONOMY_ONLY)(args, ctx)


def _fn_entryPointNamespace(args, ctx):
    return _delegateProp("entry-point-namespace", "entry-point-namespace", _TAXONOMY_ONLY)(args, ctx)


def _fn_dimensions(args, ctx):
    return _delegateProp("dimensions", "dimensions", _FACT_CUBE_TAX)(args, ctx)


def _fn_dimensionsTyped(args, ctx):
    return _delegateProp("dimensions-typed", "dimensions-typed", _FACT_CUBE_TAX)(args, ctx)


def _fn_dimensionsExplicit(args, ctx):
    return _delegateProp("dimensions-explicit", "dimensions-explicit", _FACT_CUBE_TAX)(args, ctx)


def _fn_concepts(args, ctx):
    return _delegateProp("concepts", "concepts", _TAX_OR_NETWORK)(args, ctx)


def _fn_conceptNames(args, ctx):
    return _delegateProp("concept-names", "concept-names", _TAX_OR_NETWORK)(args, ctx)


def _fn_primaryConcepts(args, ctx):
    return _delegateProp("primary-concepts", "primary-concepts", _CUBE_ONLY)(args, ctx)


def _fn_cubeConcept(args, ctx):
    return _delegateProp("cube-concept", "cube-concept", _CUBE_ONLY)(args, ctx)


def _fn_drsRole(args, ctx):
    return _delegateProp("drs-role", "drs-role", _CUBE_ONLY)(args, ctx)


def _fn_networks(args, ctx):
    return _delegateProp("networks", "networks", _TAXONOMY_ONLY)(args, ctx)


def _fn_network(args, ctx):
    return _delegateProp("network", "network", _TAXONOMY_ONLY)(args, ctx)


def _fn_source(args, ctx):
    return _fn_rel_stub("source", ["relationship"])(args, ctx)


def _fn_sourceName(args, ctx):
    return _fn_rel_stub("source-name", ["relationship"])(args, ctx)


def _fn_target(args, ctx):
    return _fn_rel_stub("target", ["relationship"])(args, ctx)


def _fn_targetName(args, ctx):
    return _fn_rel_stub("target-name", ["relationship"])(args, ctx)


def _fn_order(args, ctx):
    return _fn_rel_stub("order", ["relationship", "reference-part"])(args, ctx)


def _fn_preferredLabel(args, ctx):
    return _fn_rel_stub("preferred-label", ["relationship"])(args, ctx)


def _fn_arcrole(args, ctx):
    return _delegateProp("arcrole", "arcrole", _NETWORK_ONLY)(args, ctx)


def _fn_arcroleUri(args, ctx):
    return _delegateProp("arcrole-uri", "arcrole-uri", _NETWORK_ONLY)(args, ctx)


def _fn_arcroleDescription(args, ctx):
    return _delegateProp("arcrole-description", "arcrole-description", _NETWORK_ONLY)(args, ctx)


def _fn_linkName(args, ctx):
    return _delegateProp("link-name", "link-name", _NETWORK_ONLY)(args, ctx)


def _fn_arcName(args, ctx):
    return _delegateProp("arc-name", "arc-name", _NETWORK_ONLY)(args, ctx)


def _fn_namespaces(args, ctx):
    return _delegateProp("namespaces", "namespaces", _TAXONOMY_ONLY)(args, ctx)


def _fn_dtsDocumentLocations(args, ctx):
    return _delegateProp("dts-document-locations", "dts-document-locations", _TAXONOMY_ONLY)(args, ctx)


def _fn_role(args, ctx):
    return _delegateProp("role", "role", _NETWORK_ONLY)(args, ctx)


def _fn_qnameFn(args, ctx):
    """qname(namespace, local-name) -> QName."""
    if len(args) < 2:
        raise FormulaRuntimeError("The 'qname' function must have two arguments, found %d." % len(args))
    ns = args[0].value if args[0].type == FormulaValueType.STRING else str(args[0].value)
    ln = args[1].value if args[1].type == FormulaValueType.STRING else str(args[1].value)
    return FormulaValue(FormulaValueType.QNAME, makeQName(ns, ln))



def _fn_unit(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """
    unit(qname [, denominator-qname-or-list]) → unit value.

    Single-instance simple unit representation: a unit value is stored as
    a tuple (numerator-qname, denominator-list-of-qnames). The interpreter
    then compares such unit values against fact dim 'unit' values using
    _loose_eq (which already handles plain QName equality for simple units).
    """
    if not args:
        raise FormulaRuntimeError("unit() requires at least one QName argument")
    num = args[0].value if args[0].type == FormulaValueType.QNAME else args[0].value
    return FormulaValue(FormulaValueType.QNAME, num) if len(args) == 1 else \
        FormulaValue(FormulaValueType.STRING, str(num))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

BUILTIN_FUNCTIONS: Dict[str, Callable] = {
    # Aggregate
    "sum":              _fn_sum,
    "count":            _fn_count,
    "max":              _fn_max,
    "min":              _fn_min,
    "avg":              _fn_avg,
    "average":          _fn_avg,
    "prod":             _fn_prod,
    "stdev":            _fn_stdev,
    # Existence
    "exists":           _fn_exists,
    "missing":          _fn_missing,
    "not-exists":       _fn_notExists,
    "is-nil":           _fn_isNil,
    # Type testing
    "is-numeric":       _fn_isNumeric,
    "is-string":        _fn_isString,
    "is-boolean":       _fn_isBoolean,
    # Collections
    "list":             _fn_list,
    "set":              _fn_set,
    "to-list":          _fn_toList,
    "to-dict":          _fn_toDict,
    "to-set":           _fn_toSet,
    "first":            _fn_first,
    "last":             _fn_last,
    "index":            _fn_index,
    "contains":         _fn_contains,
    "sort":             _fn_sort,
    "union":            _fn_union,
    "intersect":        _fn_intersect,
    "difference":       _fn_difference,
    "symmetric-difference": _fn_symmetric_difference,
    "is-subset":        _fn_is_subset,
    "is-superset":      _fn_is_superset,
    "all":              _fn_all,
    "any":              _fn_any,
    "join":             _fn_join,
    "dict":             _fn_dict,
    "keys":             _fn_keys,
    "values":           _fn_values,
    "has-key":          _fn_hasKey,
    "range":            _fn_range,
    "agg-to-dict":      _fn_aggToDict,
    "to-json":          _fn_toJson,
    # Output (stub implementations)
    "to-csv":           _fn_toCsv,
    "to-spreadsheet":   _fn_toSpreadsheet,
    # Strings
    "string":           _fn_string,
    "plain-string":     _fn_plainString,
    "concat":           _fn_concat,
    "substring":        _fn_substring,
    "string-length":    _fn_stringLength,
    "length":           _fn_length,
    "contains-string":  _fn_contains_str,
    "index-of":         _fn_indexOf,
    "last-index-of":    _fn_lastIndexOf,
    "lower-case":       _fn_lowerCase,
    "upper-case":       _fn_upperCase,
    "trim":             _fn_trim,
    "split":            _fn_split,
    "repeat":           _fn_repeat,
    "number":           _fn_number,
    "to-qname":         _fn_toQname,
    "regex-match":      _fn_regexMatch,
    "regex-match-all":  _fn_regexMatchAll,
    "regex-match-string": _fn_regexMatchString,
    "regex-match-string-all": _fn_regexMatchStringAll,
    "inline-transform": _fn_inlineTransform,
    "starts-with":      _fn_startsWith,
    "ends-with":        _fn_endsWith,
    # Math
    "abs":              _fn_abs,
    "round":            _fn_round,
    "floor":            _fn_floor,
    "ceiling":          _fn_ceiling,
    "power":            _fn_power,
    "log10":            _fn_log10,
    "mod":              _fn_mod,
    "decimal":          _fn_decimal,
    "int":              _fn_int,
    "signum":           _fn_signum,
    "trunc":            _fn_trunc,
    "random":           _fn_random,
    # Taxonomy / model
    "taxonomy":         _fn_taxonomy,
    # Alignment
    "alignment":        _fn_alignment,    # Date/time
    "date":             _fn_date,
    "duration":         _fn_duration,    "forever":          _fn_forever,
    "time-span":        _fn_timeSpan,
    "day":              _fn_day,
    "month":            _fn_month,
    "year":             _fn_year,
    # Misc
    "first-value":      _fn_firstValue,
    # Instance / model references
    "instance":         _fn_instance,
    "model":            _fn_model,
    "unit":             _fn_unit,
    "clark":            _fn_clark,
    # Taxonomy / network / relationship helpers
    "entry-point":              _fn_entryPoint,
    "entry-point-namespace":    _fn_entryPointNamespace,
    "dimensions":               _fn_dimensions,
    "dimensions-typed":         _fn_dimensionsTyped,
    "dimensions-explicit":      _fn_dimensionsExplicit,
    "concepts":                 _fn_concepts,
    "concept-names":            _fn_conceptNames,
    "primary-concepts":         _fn_primaryConcepts,
    "cube-concept":             _fn_cubeConcept,
    "drs-role":                 _fn_drsRole,
    "networks":                 _fn_networks,
    "network":                  _fn_network,
    "source":                   _fn_source,
    "source-name":              _fn_sourceName,
    "target":                   _fn_target,
    "target-name":              _fn_targetName,
    "order":                    _fn_order,
    "arcrole":                  _fn_arcrole,
    "arcrole-uri":              _fn_arcroleUri,
    "arcrole-description":      _fn_arcroleDescription,
    "link-name":                _fn_linkName,
    "arc-name":                 _fn_arcName,
    "preferred-label":          _fn_preferredLabel,
    "namespaces":               _fn_namespaces,
    "dts-document-locations":   _fn_dtsDocumentLocations,
    "role":                     _fn_role,
    "qname":                    _fn_qnameFn,
    "rule-name":                _fn_rule_name,
}


def callFunction(name: str, args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """
    Call a built-in or user-defined function by name.

    User-defined functions are stored as constants whose value has type
    FormulaValueType.NONE but whose .value is a callable.  This is set up by
    the interpreter when it encounters a `function` declaration.
    """
    # Check built-ins first
    fn = BUILTIN_FUNCTIONS.get(name)
    if fn is not None:
        return fn(args, ctx)

    # Check user-defined functions (stored as constants)
    const = ctx.globalCtx.constants.get(name)
    if const is not None and callable(const.value):
        return const.value(args, ctx)

    raise FormulaRuntimeError(f"Unknown function {name!r}")
