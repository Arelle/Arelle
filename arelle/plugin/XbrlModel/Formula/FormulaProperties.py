"""
FormulaProperties.py - Property accessor dispatch for OIM model objects.

Implements the `.property` and `.property(args)` syntax of the XBRL Query
and Rules Language against the XbrlModel OIM data model.

Each object type (fact, concept, taxonomy, cube, …) has its own handler
dict mapping property name → callable(obj, args, ctx) → FormulaValue.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from arelle.ModelValue import QName

from .FormulaValue import (
    FormulaValue, FormulaValueType, FormulaRuntimeError, NONE_VALUE
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

def _wrap(value: Any, vtype: FormulaValueType = None) -> FormulaValue:
    if value is None:
        return NONE_VALUE
    if vtype is not None:
        return FormulaValue(vtype, value)
    return FormulaValue.fromScalar(value)


def _wrapSet(items) -> FormulaValue:
    return FormulaValue(FormulaValueType.SET, OrderedSet(
        FormulaValue.fromScalar(i) for i in items
    ))


# ---------------------------------------------------------------------------
# Fact properties
# ---------------------------------------------------------------------------

def _factPropPeriod(fact, args, ctx):
    dims = fact.factDimensions
    from arelle.ModelValue import qname as mkQn
    periodQn = mkQn("https://xbrl.org/2021", "period")
    period = dims.get(periodQn)
    return _wrap(period)

def _factPropEntity(fact, args, ctx):
    from arelle.ModelValue import qname as mkQn
    entityQn = mkQn("https://xbrl.org/2021", "entity")
    return _wrap(fact.factDimensions.get(entityQn))

def _factPropUnit(fact, args, ctx):
    from arelle.ModelValue import qname as mkQn
    unitQn = mkQn("https://xbrl.org/2021", "unit")
    return _wrap(fact.factDimensions.get(unitQn))

def _factPropConcept(fact, args, ctx):
    from arelle.ModelValue import qname as mkQn
    conceptQn = mkQn("https://xbrl.org/2021", "concept")
    qn = fact.factDimensions.get(conceptQn)
    if qn is None:
        return NONE_VALUE
    # Look up concept object from taxonomy
    conceptObj = ctx.txmyMdl.namedObjects.get(qn)
    if conceptObj is not None:
        return FormulaValue(FormulaValueType.CONCEPT, conceptObj)
    return _wrap(qn, FormulaValueType.QNAME)

def _factPropDimensions(fact, args, ctx):
    dims = {k: v for k, v in fact.factDimensions.items()}
    return FormulaValue(FormulaValueType.DICT, {
        FormulaValue(FormulaValueType.QNAME, k): FormulaValue.fromScalar(v)
        for k, v in dims.items()
    })

def _factPropValue(fact, args, ctx):
    if fact.factValues:
        fv = next(iter(fact.factValues))
        return FormulaValue.fromScalar(fv.value)
    return NONE_VALUE

def _factPropDecimals(fact, args, ctx):
    if fact.factValues:
        fv = next(iter(fact.factValues))
        return _wrap(getattr(fv, "decimals", None))
    return NONE_VALUE

def _factPropName(fact, args, ctx):
    return _wrap(getattr(fact, "name", None), FormulaValueType.QNAME)

def _factPropIsNil(fact, args, ctx):
    if fact.factValues:
        fv = next(iter(fact.factValues))
        return FormulaValue(FormulaValueType.BOOLEAN, fv.value is None)
    return FormulaValue(FormulaValueType.BOOLEAN, False)

def _factPropDimension(fact, args, ctx):
    """fact.dimension(dimQName) → member value"""
    if not args:
        raise FormulaRuntimeError("fact.dimension() requires a QName argument")
    dimArg = args[0]
    dimQn = dimArg.value if dimArg.type == FormulaValueType.QNAME else None
    if dimQn is None:
        raise FormulaRuntimeError("fact.dimension() argument must be a QName")
    return FormulaValue.fromScalar(fact.factDimensions.get(dimQn))

FACT_PROPS: Dict[str, Callable] = {
    "period":       _factPropPeriod,
    "entity":       _factPropEntity,
    "unit":         _factPropUnit,
    "concept":      _factPropConcept,
    "dimensions":   _factPropDimensions,
    "value":        _factPropValue,
    "decimals":     _factPropDecimals,
    "name":         _factPropName,
    "is-nil":       _factPropIsNil,
    "dimension":    _factPropDimension,
}


# ---------------------------------------------------------------------------
# Concept properties
# ---------------------------------------------------------------------------

def _conceptProp(concept, propName: str, args, ctx) -> FormulaValue:
    attr_map = {
        "name":           ("name",         FormulaValueType.QNAME),
        "local-name":     None,  # special
        "namespace-uri":  None,  # special
        "data-type":      ("dataType",     None),
        "base-type":      ("baseType",     None),
        "period-type":    ("periodType",   FormulaValueType.STRING),
        "balance":        ("balance",      FormulaValueType.STRING),
        "is-abstract":    ("isAbstract",   FormulaValueType.BOOLEAN),
        "is-numeric":     ("isNumeric",    FormulaValueType.BOOLEAN),
        "is-monetary":    ("isMonetary",   FormulaValueType.BOOLEAN),
        "nillable":       ("nillable",     FormulaValueType.BOOLEAN),
        "substitution":   ("substitutionGroup", None),
    }
    if propName == "local-name":
        qn = getattr(concept, "name", None)
        if isinstance(qn, QName):
            return _wrap(qn.localName, FormulaValueType.STRING)
        return NONE_VALUE
    if propName == "namespace-uri":
        qn = getattr(concept, "name", None)
        if isinstance(qn, QName):
            return _wrap(qn.namespaceURI, FormulaValueType.STRING)
        return NONE_VALUE
    if propName == "labels":
        labels = getattr(concept, "labels", None) or []
        return _wrapSet(labels)
    if propName == "all-references":
        refs = getattr(concept, "references", None) or []
        return _wrapSet(refs)

    if propName in attr_map:
        spec = attr_map[propName]
        if spec is None:
            return NONE_VALUE
        attr, vtype = spec
        raw = getattr(concept, attr, None)
        if raw is None:
            return NONE_VALUE
        return _wrap(raw, vtype) if vtype else FormulaValue.fromScalar(raw)

    raise FormulaRuntimeError(f"Unknown concept property {propName!r}")


# ---------------------------------------------------------------------------
# Taxonomy properties
# ---------------------------------------------------------------------------

def _taxonomyProp(txmy, propName: str, args, ctx) -> FormulaValue:
    from arelle.plugin.XbrlModel.XbrlConcept import XbrlConcept
    from arelle.plugin.XbrlModel.XbrlCube import XbrlCube
    from arelle.plugin.XbrlModel.XbrlDimension import XbrlDimension
    from arelle.plugin.XbrlModel.XbrlNetwork import XbrlNetwork

    if propName == "concepts":
        objs = list(txmy.filterNamedObjects(XbrlConcept))
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.CONCEPT, c) for c in objs
        ))
    if propName == "concept-names":
        objs = list(txmy.filterNamedObjects(XbrlConcept))
        return _wrapSet(c.name for c in objs if hasattr(c, "name"))
    if propName == "cubes":
        objs = list(txmy.filterNamedObjects(XbrlCube))
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.CUBE, c) for c in objs
        ))
    if propName == "dimensions":
        objs = list(txmy.filterNamedObjects(XbrlDimension))
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue.fromScalar(d.name) for d in objs if hasattr(d, "name")
        ))
    if propName == "networks":
        objs = list(txmy.filterNamedObjects(XbrlNetwork))
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.NETWORK, n) for n in objs
        ))
    if propName == "namespaces":
        return _wrapSet(getattr(txmy, "namespaces", {}).values())
    if propName == "entry-point":
        return _wrap(getattr(txmy, "entryPoint", None))
    if propName == "uri":
        return _wrap(getattr(txmy, "entryPoint", None))
    # concept(qname) function
    if propName == "concept":
        if not args:
            raise FormulaRuntimeError("taxonomy.concept() requires a QName argument")
        qn = args[0].value
        if isinstance(qn, QName):
            obj = txmy.namedObjects.get(qn)
            if obj is not None:
                return FormulaValue(FormulaValueType.CONCEPT, obj)
        return NONE_VALUE
    # cube(qname, role) function
    if propName == "cube":
        if not args:
            raise FormulaRuntimeError("taxonomy.cube() requires arguments")
        qn = args[0].value
        # simplified — return first cube with matching concept
        from arelle.plugin.XbrlModel.XbrlCube import XbrlCube
        for cube in txmy.filterNamedObjects(XbrlCube):
            if getattr(cube, "name", None) == qn:
                return FormulaValue(FormulaValueType.CUBE, cube)
        return NONE_VALUE
    if propName == "networks":
        return _taxonomyProp(txmy, "networks", args, ctx)

    raise FormulaRuntimeError(f"Unknown taxonomy property {propName!r}")


# ---------------------------------------------------------------------------
# Cube properties
# ---------------------------------------------------------------------------

def _cubeProp(cube, propName: str, args, ctx) -> FormulaValue:
    if propName == "cube-concept":
        qn = getattr(cube, "name", None)
        if qn:
            obj = ctx.txmyMdl.namedObjects.get(qn)
            if obj:
                return FormulaValue(FormulaValueType.CONCEPT, obj)
        return NONE_VALUE
    if propName == "dimensions":
        dims = getattr(cube, "cubeDimensions", None) or []
        return _wrapSet(getattr(d, "dimensionName", None) for d in dims)
    if propName == "facts":
        from arelle.plugin.XbrlModel.XbrlReport import XbrlFact
        from arelle.ModelValue import qname as mkQn
        cubeDimQn = mkQn("https://xbrl.org/2021", "cube")
        cubeQn = getattr(cube, "name", None)
        facts = [
            f for f in ctx.txmyMdl.filterNamedObjects(XbrlFact)
            if f.factDimensions.get(cubeDimQn) == cubeQn
        ]
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.FACT, f) for f in facts
        ))
    raise FormulaRuntimeError(f"Unknown cube property {propName!r}")


# ---------------------------------------------------------------------------
# Public dispatch entry point
# ---------------------------------------------------------------------------

def getProperty(
    obj: FormulaValue,
    propName: str,
    args: List[FormulaValue],
    ctx: "FormulaRuleContext",
) -> FormulaValue:
    """
    Dispatch a property access on a FormulaValue.

    Equivalent to `obj.propName` or `obj.propName(args)` in Xule.
    """
    if obj.type == FormulaValueType.FACT:
        handler = FACT_PROPS.get(propName)
        if handler:
            return handler(obj.value, args, ctx)
        raise FormulaRuntimeError(f"Unknown fact property {propName!r}")

    if obj.type == FormulaValueType.CONCEPT:
        return _conceptProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.TAXONOMY:
        return _taxonomyProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.CUBE:
        return _cubeProp(obj.value, propName, args, ctx)

    # String properties
    if obj.type == FormulaValueType.STRING:
        s = obj.value
        if propName == "length":
            return FormulaValue(FormulaValueType.INTEGER, len(s))
        if propName == "upper-case":
            return FormulaValue(FormulaValueType.STRING, s.upper())
        if propName == "lower-case":
            return FormulaValue(FormulaValueType.STRING, s.lower())
        if propName == "trim":
            return FormulaValue(FormulaValueType.STRING, s.strip())
        if propName == "date":
            from .FormulaFunctions import callFunction
            return callFunction("date", [obj], ctx)
        if propName == "time-span":
            from .FormulaFunctions import callFunction
            return callFunction("time-span", [obj], ctx)
        if propName in ("day", "month", "year", "days", "start", "end"):
            raise FormulaRuntimeError(f"Property '{propName}' is not a property of a 'string'.")
        raise FormulaRuntimeError(f"Unknown string property {propName!r}")

    # QName properties
    if obj.type == FormulaValueType.QNAME:
        qn = obj.value
        if propName == "local-name":
            return FormulaValue(FormulaValueType.STRING, qn.localName if hasattr(qn, "localName") else str(qn))
        if propName == "namespace-uri":
            return FormulaValue(FormulaValueType.STRING, qn.namespaceURI if hasattr(qn, "namespaceURI") else "")
        if propName in ("day", "month", "year", "days", "start", "end", "date"):
            raise FormulaRuntimeError(f"Property '{propName}' is not a property of a 'QName'.")
        raise FormulaRuntimeError(f"Unknown QName property {propName!r}")

    if obj.type == FormulaValueType.NONE:
        if propName in ("keys", "values", "length", "date"):
            return NONE_VALUE
        raise FormulaRuntimeError(f"Cannot access property {propName!r} on NONE value")

    if obj.type == FormulaValueType.DATE:
        inst = obj.value
        if propName == "day":
            return FormulaValue(FormulaValueType.INTEGER, inst.dt.day)
        if propName == "month":
            return FormulaValue(FormulaValueType.INTEGER, inst.dt.month)
        if propName == "year":
            return FormulaValue(FormulaValueType.INTEGER, inst.dt.year)
        if propName in ("start", "date"):
            return obj
        if propName == "days":
            return FormulaValue(FormulaValueType.INTEGER, 0)
        if propName == "end":
            return obj
        raise FormulaRuntimeError(f"Unknown date property {propName!r}")

    if obj.type == FormulaValueType.DURATION:
        value = obj.value
        if propName == "contains":
            raise FormulaRuntimeError("Property 'contains' is not a property of a 'duration'.")
        if propName in ("day", "month", "year"):
            raise FormulaRuntimeError(f"Property '{propName}' is not a property of a 'duration'.")
        if isinstance(value, DateRangeValue):
            if propName == "start":
                return FormulaValue(FormulaValueType.DATE, InstantValue(value.start))
            if propName == "end":
                return FormulaValue(FormulaValueType.DATE, InstantValue(value.end))
            if propName == "days":
                return FormulaValue(FormulaValueType.INTEGER, (value.end - value.start).days)
            if propName == "time-span":
                return FormulaValue(FormulaValueType.DURATION, TimeSpanValue(value.end - value.start))
            if propName == "date":
                return FormulaValue(FormulaValueType.DATE, InstantValue(value.start))
        if isinstance(value, TimeSpanValue):
            if propName == "days":
                return FormulaValue(FormulaValueType.FLOAT, value.delta.total_seconds() / 86400.0)
            if propName == "_type":
                return FormulaValue(FormulaValueType.STRING, "time-period")
        raise FormulaRuntimeError(f"Unknown duration property {propName!r}")

    # Set/list properties
    if obj.type in (FormulaValueType.SET, FormulaValueType.LIST):
        coll = obj.value
        if propName == "count":
            return FormulaValue(FormulaValueType.INTEGER, len(coll))
        if propName == "length":
            return FormulaValue(FormulaValueType.INTEGER, len(coll))
        if propName == "string":
            from .FormulaFunctions import callFunction
            return FormulaValue(
                FormulaValueType.LIST,
                [callFunction("string", [item], ctx) for item in list(coll)],
            )
        if propName == "is-numeric":
            return FormulaValue(
                FormulaValueType.LIST,
                [FormulaValue(FormulaValueType.BOOLEAN, item.isNumeric) for item in list(coll)],
            )
        if propName in ("day", "month", "year", "start", "end", "days", "date"):
            projected = [getProperty(item, propName, args, ctx) for item in list(coll)]
            if obj.type == FormulaValueType.SET:
                return FormulaValue(FormulaValueType.SET, OrderedSet(projected))
            return FormulaValue(FormulaValueType.LIST, projected)
        if propName == "first":
            items = list(coll)
            return items[0] if items else NONE_VALUE
        if propName == "last":
            items = list(coll)
            return items[-1] if items else NONE_VALUE
        if propName == "to-set":
            # Convert list to set (already a set if type is SET)
            if obj.type == FormulaValueType.SET:
                return obj
            return FormulaValue(FormulaValueType.SET, OrderedSet(coll))
        if propName in (
            "to-list", "to-dict", "to-json", "to-csv", "to-spreadsheet", "agg-to-dict",
            "sort", "sum", "max", "min", "prod", "stdev", "join",
            "all", "any", "contains", "intersect", "union", "difference",
            "values", "keys",
        ):
            from .FormulaFunctions import callFunction
            return callFunction(propName, [obj] + list(args), ctx)
        raise FormulaRuntimeError(f"Unknown collection property {propName!r}")

    if obj.type == FormulaValueType.DICT:
        if propName in ("keys", "values", "has-key", "to-set", "to-json", "to-csv", "to-spreadsheet", "join"):
            from .FormulaFunctions import callFunction
            return callFunction(propName, [obj] + list(args), ctx)
        if propName in ("count", "length"):
            return FormulaValue(FormulaValueType.INTEGER, len(obj.value))
        raise FormulaRuntimeError(f"Unknown dictionary property {propName!r}")

    raise FormulaRuntimeError(
        f"Cannot access property {propName!r} on {obj.type.name} value"
    )
