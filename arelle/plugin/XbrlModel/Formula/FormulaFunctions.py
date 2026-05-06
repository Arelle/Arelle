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
            return set(v.value)
        if v.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL, FormulaValueType.STRING):
            return v.value
        return v.value

    def _fromPython(v) -> FormulaValue:
        if v is None:
            return NONE_VALUE
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

    items = _unwrapCollection(args[0])
    if not items:
        return NONE_VALUE

    acc = _toPython(items[0])
    for item in items[1:]:
        nxt = _toPython(item)
        if isinstance(acc, set) and isinstance(nxt, set):
            acc = acc | nxt
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
        f"The first argument of function 'count' must be set, list, dictionary, found '{arg.type.name.lower()}'."
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
    # Conformance tests treat none, set(none), and list(none) as existing.
    # "missing" is the explicit function for absent values.
    arg = args[0]
    return FALSE_VALUE if arg.type == FormulaValueType.SKIP else TRUE_VALUE


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
    items: List[FormulaValue] = []
    for arg in args:
        if arg.type == FormulaValueType.LIST and getattr(arg, "_forResult", False):
            items.extend(list(arg.value))
        else:
            items.append(arg)
    return FormulaValue(FormulaValueType.LIST, items)


def _fn_set(args: List[FormulaValue], ctx: "FormulaRuleContext") -> FormulaValue:
    return FormulaValue(FormulaValueType.SET, OrderedSet(args))


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
    if args[0].type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"The first argument of function 'contains' must be set, list, found '{args[0].type.name.lower()}'."
        )
    items = _unwrapCollection(args[0])
    return FormulaValue(FormulaValueType.BOOLEAN, args[1] in items)


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
    result = OrderedSet()
    for a in args:
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
    return FormulaValue(FormulaValueType.STRING, sep.join(str(i.value) for i in items))


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
    # Date/time
    "date":             _fn_date,
    "duration":         _fn_duration,
    "forever":          _fn_forever,
    "time-span":        _fn_timeSpan,
    "day":              _fn_day,
    "month":            _fn_month,
    "year":             _fn_year,
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
