"""
FormulaFunctions.py - Built-in function library for the formula interpreter.

Implements the standard Xule function set adapted for the OIM XbrlModel
data model.  Each function is registered in BUILTIN_FUNCTIONS as:

    name → callable(args: list[FormulaValue], ctx: FormulaRuleContext) → FormulaValue

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

from arelle.ModelValue import QName

from .FormulaValue import (
    FormulaValue, FormulaValueType, FormulaRuntimeError,
    NONE_VALUE, TRUE_VALUE, FALSE_VALUE
)

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


# ---------------------------------------------------------------------------
# Aggregate functions
# ---------------------------------------------------------------------------

def _fn_sum(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """sum(collection) → Decimal sum of all numeric items."""
    if len(args) != 1:
        raise FormulaRuntimeError("sum() requires exactly one argument")

    def _flatten(items: List[FormulaValue]) -> List[FormulaValue]:
        flat: List[FormulaValue] = []
        for item in items:
            if item.type in (FormulaValueType.SET, FormulaValueType.LIST):
                flat.extend(_flatten(list(item.value)))
            else:
                flat.append(item)
        return flat

    items = _flatten(_unwrapCollection(args[0]))
    total = Decimal(0)
    for item in items:
        try:
            total += _num(item)
        except FormulaRuntimeError:
            pass   # skip non-numeric items (spec says produce none if empty)
    return FormulaValue(FormulaValueType.DECIMAL, total)


def _fn_count(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    """count(collection) → integer count of items."""
    if len(args) != 1:
        raise FormulaRuntimeError("count() requires exactly one argument")
    items = _unwrapCollection(args[0])
    return FormulaValue(FormulaValueType.INTEGER, len(items))


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
        raise FormulaRuntimeError("avg() requires exactly one argument")
    items = _unwrapCollection(args[0])
    nums = [_num(i) for i in items if i.type != FormulaValueType.NONE]
    if not nums:
        return NONE_VALUE
    return FormulaValue(FormulaValueType.DECIMAL, sum(nums) / len(nums))


# ---------------------------------------------------------------------------
# Existence / nil functions
# ---------------------------------------------------------------------------

def _fn_exists(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 1:
        raise FormulaRuntimeError("exists() requires exactly one argument")
    arg = args[0]
    return TRUE_VALUE if (arg.type not in (FormulaValueType.NONE, FormulaValueType.SKIP)) else FALSE_VALUE


def _fn_notExists(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
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
    return FormulaValue(FormulaValueType.LIST, list(args))


def _fn_set(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    return FormulaValue(FormulaValueType.SET, frozenset(args))


def _fn_first(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("first() requires an argument")
    items = _unwrapCollection(args[0])
    return items[0] if items else NONE_VALUE


def _fn_last(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("last() requires an argument")
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
    items = _unwrapCollection(args[0])
    return FormulaValue(FormulaValueType.BOOLEAN, args[1] in items)


def _fn_sort(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("sort() requires an argument")
    items = _unwrapCollection(args[0])
    try:
        sorted_items = sorted(items, key=lambda x: (str(x.type.name), str(x.value)))
    except TypeError:
        sorted_items = items
    return FormulaValue(FormulaValueType.LIST, sorted_items)


def _fn_union(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("union() requires at least two arguments")
    result = set()
    for a in args:
        result.update(_unwrapCollection(a))
    return FormulaValue(FormulaValueType.SET, frozenset(result))


def _fn_intersect(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("intersect() requires at least two arguments")
    result = set(_unwrapCollection(args[0]))
    for a in args[1:]:
        result &= set(_unwrapCollection(a))
    return FormulaValue(FormulaValueType.SET, frozenset(result))


def _fn_difference(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("difference() requires at least two arguments")
    result = set(_unwrapCollection(args[0]))
    for a in args[1:]:
        result -= set(_unwrapCollection(a))
    return FormulaValue(FormulaValueType.SET, frozenset(result))


# ---------------------------------------------------------------------------
# String functions
# ---------------------------------------------------------------------------

def _fn_string(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("string() requires an argument")
    if args[0].type == FormulaValueType.FACT:
        val = args[0].numericValue() if args[0].isNumeric else None
        if val is None and args[0].value.factValues:
            val = next(iter(args[0].value.factValues)).value
        return FormulaValue(FormulaValueType.STRING, str(val) if val is not None else "")
    return FormulaValue(FormulaValueType.STRING, str(args[0].value))


def _fn_concat(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    return FormulaValue(FormulaValueType.STRING, "".join(str(a.value) for a in args))


def _fn_substring(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) < 2:
        raise FormulaRuntimeError("substring() requires at least two arguments")
    s    = str(args[0].value)
    start = int(args[1].value) - 1   # 1-based
    end   = int(args[2].value) if len(args) >= 3 else len(s)
    return FormulaValue(FormulaValueType.STRING, s[start:end])


def _fn_stringLength(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("string-length() requires an argument")
    return FormulaValue(FormulaValueType.INTEGER, len(str(args[0].value)))


def _fn_contains_str(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if len(args) != 2:
        raise FormulaRuntimeError("contains-string() requires two arguments")
    return FormulaValue(FormulaValueType.BOOLEAN, str(args[1].value) in str(args[0].value))


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
    if not args:
        raise FormulaRuntimeError("abs() requires an argument")
    return FormulaValue(FormulaValueType.DECIMAL, abs(_num(args[0])))


def _fn_round(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    if not args:
        raise FormulaRuntimeError("round() requires an argument")
    decimals_arg = int(args[1].value) if len(args) >= 2 else 0
    return FormulaValue(FormulaValueType.DECIMAL, round(_num(args[0]), decimals_arg))


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
    base = float(_num(args[0]))
    exp  = float(_num(args[1]))
    return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(base ** exp)))


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
    from arelle.plugin.XbrlModel import castToXbrlCompiledModel
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
    if ctx.alignment is None:
        return FormulaValue(FormulaValueType.DICT, {})
    result = {}
    for dimQn, value in ctx.alignment:
        result[FormulaValue(FormulaValueType.QNAME, dimQn)] = FormulaValue.fromScalar(value)
    return FormulaValue(FormulaValueType.DICT, result)


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
    # Existence
    "exists":           _fn_exists,
    "not-exists":       _fn_notExists,
    "is-nil":           _fn_isNil,
    # Type testing
    "is-numeric":       _fn_isNumeric,
    "is-string":        _fn_isString,
    "is-boolean":       _fn_isBoolean,
    # Collections
    "list":             _fn_list,
    "set":              _fn_set,
    "first":            _fn_first,
    "last":             _fn_last,
    "index":            _fn_index,
    "contains":         _fn_contains,
    "sort":             _fn_sort,
    "union":            _fn_union,
    "intersect":        _fn_intersect,
    "difference":       _fn_difference,
    # Strings
    "string":           _fn_string,
    "concat":           _fn_concat,
    "substring":        _fn_substring,
    "string-length":    _fn_stringLength,
    "contains-string":  _fn_contains_str,
    "starts-with":      _fn_startsWith,
    "ends-with":        _fn_endsWith,
    # Math
    "abs":              _fn_abs,
    "round":            _fn_round,
    "floor":            _fn_floor,
    "ceiling":          _fn_ceiling,
    "power":            _fn_power,
    # Taxonomy / model
    "taxonomy":         _fn_taxonomy,
    # Alignment
    "alignment":        _fn_alignment,
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
