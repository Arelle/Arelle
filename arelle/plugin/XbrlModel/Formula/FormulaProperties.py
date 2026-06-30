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
    periodQn = mkQn("https://xbrl.org/2026", "period")
    period = dims.get(periodQn)
    return _wrap(period)

def _factPropEntity(fact, args, ctx):
    from arelle.ModelValue import qname as mkQn
    entityQn = mkQn("https://xbrl.org/2026", "entity")
    ev = fact.factDimensions.get(entityQn)
    if ev is None:
        return NONE_VALUE
    # Wrap as ENTITY so .name / .local-name / .namespace-uri chains work.
    return FormulaValue(FormulaValueType.ENTITY, ev)

def _factPropUnit(fact, args, ctx):
    from arelle.ModelValue import qname as mkQn
    unitQn = mkQn("https://xbrl.org/2026", "unit")
    uv = fact.factDimensions.get(unitQn)
    if uv is None:
        return NONE_VALUE
    # Wrap as UNIT_VALUE so .numerator / .denominator chains work.
    return FormulaValue(FormulaValueType.UNIT_VALUE, uv)

def _factPropConcept(fact, args, ctx):
    from arelle.ModelValue import qname as mkQn
    conceptQn = mkQn("https://xbrl.org/2026", "concept")
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

def _factPropIsFact(fact, args, ctx):
    return FormulaValue(FormulaValueType.BOOLEAN, True)

def _factPropId(fact, args, ctx):
    # Prefer an explicit id attribute on the fact (set during OIM load), else
    # fall back to a stable derived id (the fact's local QName).
    fid = getattr(fact, "id", None)
    if fid is None:
        if fact.factValues:
            fid = getattr(next(iter(fact.factValues)), "id", None)
    if fid is None:
        nm = getattr(fact, "name", None)
        if isinstance(nm, QName):
            fid = nm.localName
    return _wrap(fid, FormulaValueType.STRING) if fid is not None else NONE_VALUE

def _factPropInstance(fact, args, ctx):
    txmyMdl = getattr(fact, "parent", None) or ctx.txmyMdl
    return FormulaValue(FormulaValueType.TAXONOMY, txmyMdl)

def _factPropCubes(fact, args, ctx):
    from XbrlModel.XbrlCube import XbrlCube
    from arelle.ModelValue import qname as mkQn
    txmy = ctx.txmyMdl
    cubeDimQn = mkQn("https://xbrl.org/2026", "cube")
    factCubeNames = fact.factDimensions.get(cubeDimQn)
    cubes = []
    if factCubeNames is not None:
        names = factCubeNames if isinstance(factCubeNames, (list, tuple, set)) else [factCubeNames]
        for n in names:
            obj = txmy.namedObjects.get(n) if isinstance(n, QName) else None
            if isinstance(obj, XbrlCube):
                cubes.append(obj)
    else:
        # Fallback: scan cubes for membership via _cellFacts populated by ValidateFacts.
        for cube in txmy.filterNamedObjects(XbrlCube):
            cellFacts = getattr(cube, "_cellFacts", None) or {}
            for cellEntries in cellFacts.values():
                if any(f is fact for f, _ in cellEntries):
                    cubes.append(cube)
                    break
    return FormulaValue(FormulaValueType.SET, OrderedSet(
        FormulaValue(FormulaValueType.CUBE, c) for c in cubes
    ))

def _factPropAspects(fact, args, ctx):
    from arelle.ModelValue import qname as mkQn
    coreLocals = ("concept", "period", "entity", "unit", "language")
    coreNs = "https://xbrl.org/2026"
    aspects = {}
    for k, v in fact.factDimensions.items():
        if isinstance(k, QName) and k.namespaceURI == coreNs and k.localName in coreLocals:
            aspects[FormulaValue(FormulaValueType.QNAME, k)] = FormulaValue.fromScalar(v)
    return FormulaValue(FormulaValueType.DICT, aspects)

def _factPropNamespaceMap(fact, args, ctx):
    nsMap = {}
    # Try fact.parent (factspace / module) for _prefixNamespaces, else txmyMdl
    src = getattr(fact, "parent", None)
    nsm = getattr(src, "_prefixNamespaces", None) if src is not None else None
    if not nsm:
        nsm = getattr(ctx.txmyMdl, "_prefixNamespaces", None) or {}
    for prefix, uri in nsm.items():
        nsMap[_wrap(prefix or "None", FormulaValueType.STRING)] = _wrap(uri, FormulaValueType.STRING)
    return FormulaValue(FormulaValueType.DICT, nsMap)

def _factPropFootnotes(fact, args, ctx):
    # Footnote retrieval not yet implemented; return empty set.
    return FormulaValue(FormulaValueType.SET, OrderedSet())

FACT_PROPS: Dict[str, Callable] = {
    "period":         _factPropPeriod,
    "entity":         _factPropEntity,
    "unit":           _factPropUnit,
    "concept":        _factPropConcept,
    "dimensions":     _factPropDimensions,
    "value":          _factPropValue,
    "decimals":       _factPropDecimals,
    "name":           _factPropName,
    "is-nil":         _factPropIsNil,
    "is-fact":        _factPropIsFact,
    "dimension":      _factPropDimension,
    "id":             _factPropId,
    "instance":       _factPropInstance,
    "cubes":          _factPropCubes,
    "aspects":        _factPropAspects,
    "namespace-map":  _factPropNamespaceMap,
    "footnotes":      _factPropFootnotes,
}


# Property names recognised on a single CONCEPT, used to decide whether to
# project an accessor across a set/list of concepts.
_CONCEPT_PROP_NAMES = {
    "name", "local-name", "namespace-uri", "data-type", "base-type",
    "period-type", "balance", "is-heading", "is-numeric", "is-monetary",
    "nillable", "substitution", "labels", "all-references",
    "clark", "label", "all-labels", "references", "has-enumerations",
    "enumerations", "document-location",
}

# Xule allows property names in camelCase as aliases to the kebab-case
# canonical form. This is applied at dispatch time.
_PROP_NAME_ALIASES = {
    "periodType": "period-type",
    "dataType": "data-type",
    "baseType": "base-type",
    "localName": "local-name",
    "namespaceUri": "namespace-uri",
    "isHeading": "is-heading",
    "isNumeric": "is-numeric",
    "isMonetary": "is-monetary",
    "isNil": "is-nil",
    "isFact": "is-fact",
    "allReferences": "all-references",
    "cubeConcept": "cube-concept",
}


# ---------------------------------------------------------------------------
# Concept properties
# ---------------------------------------------------------------------------

def _objectDocumentLocation(obj) -> Optional[str]:
    mod = getattr(obj, "module", None)
    if mod is None:
        return None
    for attr in ("documentUri", "documentURI", "uri", "url", "href", "location"):
        v = getattr(mod, attr, None)
        if v:
            return str(v)
    return None


def _resolveLabelTypeUri(lt, ctx) -> Optional[str]:
    """Resolve an XBRL labelType QName to its canonical role URI.

    Tries the loaded taxonomy's namedObjects first, then falls back to
    well-known mappings for standard XBRL label roles.
    """
    if not isinstance(lt, QName):
        return None
    if ctx is not None and ctx.txmyMdl is not None:
        ltObj = ctx.txmyMdl.namedObjects.get(lt)
        u = getattr(ltObj, "uri", None)
        if u:
            return str(u)
    if lt.namespaceURI in (
        "http://www.xbrl.org/2003/instance",
        "https://xbrl.org/2026",
        "https://xbrl.org/2021",
    ):
        return f"http://www.xbrl.org/2003/role/{lt.localName}"
    return None


def _conceptLabel(concept, propName: str, args, ctx) -> FormulaValue:
    """Return a label (or set of all labels) for the concept.

    `.label` -> preferred std label (wrapped LABEL).
    `.label(roleUri)` -> label with the given role.
    `.labels` / `.all-labels` -> set of LABEL values.
    """
    from arelle.ModelValue import qname as mkQn
    compMdl = getattr(concept, "xbrlCompMdl", None)
    qn = getattr(concept, "name", None)
    if compMdl is None or qn is None:
        return NONE_VALUE
    tagObjs = compMdl.tagObjects.get(qn, ()) if hasattr(compMdl, "tagObjects") else ()
    labelObjs = [t for t in tagObjs if hasattr(t, "labelType")]
    if propName in ("labels", "all-labels"):
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.LABEL, t) for t in labelObjs))
    # .label or .label(roleUri)
    roleArg = None
    if args:
        rv = args[0].value
        roleArg = rv if isinstance(rv, str) else (str(rv) if rv is not None else None)
    try:
        from arelle.XbrlConst import qnStdLabel
    except Exception:
        qnStdLabel = None
    target = qnStdLabel
    STD_LABEL_URI = "http://www.xbrl.org/2003/role/label"
    for t in labelObjs:
        lt = getattr(t, "labelType", None)
        ltUri = _resolveLabelTypeUri(lt, ctx)
        if roleArg:
            if ltUri and ltUri == roleArg:
                return FormulaValue(FormulaValueType.LABEL, t)
        else:
            if ltUri == STD_LABEL_URI:
                return FormulaValue(FormulaValueType.LABEL, t)
            if lt == target:
                return FormulaValue(FormulaValueType.LABEL, t)
    # Fallback: first label
    if not roleArg and labelObjs:
        return FormulaValue(FormulaValueType.LABEL, labelObjs[0])
    return NONE_VALUE


def _conceptReferences(concept, args, ctx) -> FormulaValue:
    refs = _conceptReferenceObjects(concept, ctx)
    return FormulaValue(FormulaValueType.SET, OrderedSet(
        FormulaValue(FormulaValueType.REFERENCE, r) for r in refs))


def _conceptReferenceObjects(concept, ctx):
    """Return the underlying XbrlReference tag objects for the concept."""
    compMdl = getattr(concept, "xbrlCompMdl", None)
    qn = getattr(concept, "name", None)
    if compMdl is None or qn is None:
        return []
    refs = []
    if hasattr(compMdl, "tagObjects"):
        for t in compMdl.tagObjects.get(qn, ()):
            if hasattr(t, "referenceType"):
                refs.append(t)
    return refs


# ---------------------------------------------------------------------------
# Label / Reference / DataType / Part / Role / Namespace property handlers
# ---------------------------------------------------------------------------

def _labelProp(label, propName: str, args, ctx) -> FormulaValue:
    if propName == "text":
        return _wrap(getattr(label, "value", None), FormulaValueType.STRING)
    if propName == "role":
        rt = getattr(label, "labelType", None)
        uri = _resolveLabelTypeUri(rt, ctx)
        if uri:
            # Return a ROLE value so chained ._type / .uri work as expected.
            from types import SimpleNamespace
            return FormulaValue(FormulaValueType.ROLE, SimpleNamespace(uri=uri))
        return _wrap(str(rt) if rt is not None else None, FormulaValueType.STRING)
    if propName in ("lang", "language"):
        return _wrap(getattr(label, "language", None), FormulaValueType.STRING)
    if propName == "concept":
        rn = getattr(label, "forObject", None)
        if rn is not None and ctx.txmyMdl is not None:
            obj = ctx.txmyMdl.namedObjects.get(rn)
            if obj is not None:
                return FormulaValue(FormulaValueType.CONCEPT, obj)
        return NONE_VALUE
    raise FormulaRuntimeError(f"Property {propName!r} is not a property of a 'label'.")


def _referenceProp(ref, propName: str, args, ctx) -> FormulaValue:
    if propName == "parts":
        parts = list(getattr(ref, "properties", ()) or ())
        # Return as ordered list of PART values (sets lose order)
        return FormulaValue(FormulaValueType.LIST,
                            [FormulaValue(FormulaValueType.PART, p) for p in parts])
    if propName == "role":
        rt = getattr(ref, "referenceType", None)
        return FormulaValue(FormulaValueType.ROLE, rt) if rt is not None else NONE_VALUE
    if propName == "concept":
        rn = next(iter(getattr(ref, "forObjects", None) or ()), None) or getattr(ref, "name", None)
        if rn is not None and ctx.txmyMdl is not None:
            obj = ctx.txmyMdl.namedObjects.get(rn)
            if obj is not None:
                return FormulaValue(FormulaValueType.CONCEPT, obj)
        return NONE_VALUE
    if propName == "part-by-name":
        if not args or args[0].type != FormulaValueType.QNAME:
            raise FormulaRuntimeError("part-by-name() requires a QName argument")
        target = args[0].value
        for p in getattr(ref, "properties", ()) or ():
            pq = getattr(p, "property", None)
            if pq == target:
                return FormulaValue(FormulaValueType.PART, p)
        return NONE_VALUE
    raise FormulaRuntimeError(f"Property {propName!r} is not a property of a 'reference'.")


def _partProp(part, propName: str, args, ctx) -> FormulaValue:
    if propName == "name":
        pq = getattr(part, "property", None)
        if isinstance(pq, QName):
            return FormulaValue(FormulaValueType.QNAME, pq)
        return NONE_VALUE
    if propName == "part-value":
        return _wrap(getattr(part, "value", None))
    if propName == "local-name":
        pq = getattr(part, "property", None)
        if isinstance(pq, QName):
            return _wrap(pq.localName, FormulaValueType.STRING)
        return NONE_VALUE
    if propName == "namespace-uri":
        pq = getattr(part, "property", None)
        if isinstance(pq, QName):
            return _wrap(pq.namespaceURI, FormulaValueType.STRING)
        return NONE_VALUE
    if propName == "order":
        return _wrap(getattr(part, "order", None))
    raise FormulaRuntimeError(f"Property {propName!r} is not a property of a 'part'.")


def _roleProp(role, propName: str, args, ctx) -> FormulaValue:
    # role is typically a QName for OIM
    if propName == "uri":
        if isinstance(role, QName):
            uri = (role.namespaceURI or "")
            # roleType QName uses namespaceURI as the role URI base
            if role.localName:
                uri = uri + ("/" if uri and not uri.endswith("/") else "") + role.localName
            return _wrap(uri or str(role), FormulaValueType.STRING)
        return _wrap(str(role), FormulaValueType.STRING)
    if propName == "description":
        return _wrap(str(role), FormulaValueType.STRING)
    raise FormulaRuntimeError(f"Property {propName!r} is not a property of a 'role'.")


def _namespaceProp(ns, propName: str, args, ctx) -> FormulaValue:
    if propName == "uri":
        return _wrap(ns if isinstance(ns, str) else str(ns), FormulaValueType.STRING)
    raise FormulaRuntimeError(f"Property {propName!r} is not a property of a 'namespace'.")


def _dataTypeProp(dt, propName: str, args, ctx) -> FormulaValue:
    if propName == "name":
        return _wrap(getattr(dt, "name", None), FormulaValueType.QNAME)
    if propName == "base-type":
        bt = getattr(dt, "baseType", None)
        if bt is None:
            return NONE_VALUE
        btObj = ctx.txmyMdl.namedObjects.get(bt)
        if btObj is not None:
            return FormulaValue(FormulaValueType.DATA_TYPE, btObj)
        return _wrap(bt, FormulaValueType.QNAME)
    if propName == "enumerations":
        return _wrapSet(getattr(dt, "enumeration", None) or ())
    if propName == "has-enumerations":
        e = getattr(dt, "enumeration", None) or ()
        return _wrap(len(e) > 0, FormulaValueType.BOOLEAN)
    if propName in ("local-name", "namespace-uri"):
        nm = getattr(dt, "name", None)
        if isinstance(nm, QName):
            return _wrap(nm.localName if propName == "local-name" else nm.namespaceURI,
                         FormulaValueType.STRING)
        return NONE_VALUE
    raise FormulaRuntimeError(f"Property {propName!r} is not a property of a 'type'.")


def _conceptEnumerations(concept, ctx):
    from XbrlModel.XbrlConcept import XbrlDataType
    dt = ctx.txmyMdl.namedObjects.get(getattr(concept, "dataType", None))
    if isinstance(dt, XbrlDataType):
        return list(getattr(dt, "enumeration", None) or ())
    return None


def _conceptIsMonetary(concept, ctx) -> bool:
    from XbrlModel.XbrlConcept import XbrlDataType
    dt = ctx.txmyMdl.namedObjects.get(getattr(concept, "dataType", None))
    seen = set()
    while isinstance(dt, XbrlDataType):
        nm = getattr(dt, "name", None)
        if nm in seen:
            break
        seen.add(nm)
        if isinstance(nm, QName) and "monetary" in nm.localName.lower():
            return True
        bt = getattr(dt, "baseType", None)
        if isinstance(bt, QName) and "monetary" in bt.localName.lower():
            return True
        if bt is None:
            break
        dt = ctx.txmyMdl.namedObjects.get(bt)
    return False


def _conceptIsType(concept, target, ctx) -> bool:
    from XbrlModel.XbrlConcept import XbrlDataType
    if not isinstance(target, QName):
        raise FormulaRuntimeError(
            f"is-type() argument must be a QName, got {type(target).__name__}")
    dtQn = getattr(concept, "dataType", None)
    if dtQn == target:
        return True
    dt = ctx.txmyMdl.namedObjects.get(dtQn)
    seen = set()
    while isinstance(dt, XbrlDataType):
        nm = getattr(dt, "name", None)
        if nm == target:
            return True
        if nm in seen:
            break
        seen.add(nm)
        bt = getattr(dt, "baseType", None)
        if bt == target:
            return True
        if bt is None:
            break
        dt = ctx.txmyMdl.namedObjects.get(bt)
    return False


def _conceptProp(concept, propName: str, args, ctx) -> FormulaValue:
    attr_map = {
        "name":           ("name",         FormulaValueType.QNAME),
        "local-name":     None,  # special
        "namespace-uri":  None,  # special
        "data-type":      ("dataType",     None),
        "base-type":      ("baseType",     None),
        "period-type":    ("periodType",   FormulaValueType.STRING),
        "balance":        ("balance",      FormulaValueType.STRING),
        "is-heading":     None,
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
    if propName == "clark":
        qn = getattr(concept, "name", None)
        if isinstance(qn, QName):
            return _wrap("{" + (qn.namespaceURI or "") + "}" + qn.localName,
                         FormulaValueType.STRING)
        return NONE_VALUE
    if propName in ("data-type", "base-type"):
        # Resolve the dataType (or derived base) to the XbrlDataType object
        # so chained `.enumerations`, `.has-enumerations`, etc. work.
        from XbrlModel.XbrlConcept import XbrlDataType
        dtQn = getattr(concept, "dataType", None)
        if dtQn is None:
            return NONE_VALUE
        dt = ctx.txmyMdl.namedObjects.get(dtQn)
        if propName == "base-type":
            # Walk to the root XSD baseType
            seen = set()
            while isinstance(dt, XbrlDataType):
                bt = getattr(dt, "baseType", None)
                if bt is None or bt in seen:
                    break
                seen.add(bt)
                btObj = ctx.txmyMdl.namedObjects.get(bt)
                if not isinstance(btObj, XbrlDataType):
                    break
                dt = btObj
        if isinstance(dt, XbrlDataType):
            return FormulaValue(FormulaValueType.DATA_TYPE, dt)
        if dtQn is not None:
            return FormulaValue(FormulaValueType.QNAME, dtQn)
        return NONE_VALUE
    if propName in ("label", "all-labels", "labels"):
        return _conceptLabel(concept, propName, args, ctx)
    if propName in ("references", "all-references"):
        return _conceptReferences(concept, args, ctx)
    if propName == "has-enumerations":
        return _wrap(_conceptEnumerations(concept, ctx) is not None and
                     len(_conceptEnumerations(concept, ctx)) > 0,
                     FormulaValueType.BOOLEAN)
    if propName == "enumerations":
        enums = _conceptEnumerations(concept, ctx)
        return _wrapSet(enums or ())
    if propName == "document-location":
        loc = _objectDocumentLocation(concept)
        return _wrap(loc, FormulaValueType.STRING) if loc else NONE_VALUE
    if propName == "is-type":
        if not args:
            raise FormulaRuntimeError("is-type() requires a QName argument")
        target = args[0].value
        return _wrap(_conceptIsType(concept, target, ctx), FormulaValueType.BOOLEAN)
    if propName == "is-monetary":
        return _wrap(_conceptIsMonetary(concept, ctx), FormulaValueType.BOOLEAN)
    if propName == "is-numeric":
        try:
            return _wrap(bool(concept.isNumeric(ctx.txmyMdl)), FormulaValueType.BOOLEAN)
        except Exception:
            return _wrap(False, FormulaValueType.BOOLEAN)
    if propName == "is-heading":
        # OIM models headings as first-class heading objects.
        # Concept objects are not headings by default, but allow an explicit
        # heading marker as a concept property for compatibility with
        # extension taxonomies.
        for prop in getattr(concept, "properties", None) or ():
            pq = getattr(prop, "property", None)
            if isinstance(pq, QName) and pq.localName == "heading":
                v = getattr(prop, "value", None)
                return _wrap(str(v).lower() in ("true", "1"), FormulaValueType.BOOLEAN)
        return _wrap(False, FormulaValueType.BOOLEAN)
    if propName == "substitution":
        for prop in getattr(concept, "properties", None) or ():
            pq = getattr(prop, "property", None)
            if isinstance(pq, QName) and pq.localName == "substitutionGroup":
                v = getattr(prop, "value", None)
                if isinstance(v, QName):
                    return _wrap(v, FormulaValueType.QNAME)
                # may be a string like 'xbrli:item'
                return _wrap(v)
        # Default substitution group for an item-type concept is xbrli:item
        from arelle.ModelValue import qname as mkQn
        return _wrap(mkQn("http://www.xbrl.org/2003/instance", "xbrli:item"),
                     FormulaValueType.QNAME)
    if propName == "all-references":
        return _conceptReferences(concept, args, ctx)
    if propName == "balance":
        # Stored as a property with QName 'xbrla:balance' on the concept.
        for prop in getattr(concept, "properties", None) or ():
            pq = getattr(prop, "property", None)
            if isinstance(pq, QName) and pq.localName == "balance":
                return _wrap(getattr(prop, "value", None), FormulaValueType.STRING)
        return NONE_VALUE

    if propName in attr_map:
        spec = attr_map[propName]
        if spec is None:
            return NONE_VALUE
        attr, vtype = spec
        raw = getattr(concept, attr, None)
        if raw is None:
            return NONE_VALUE
        return _wrap(raw, vtype) if vtype else FormulaValue.fromScalar(raw)

    # Concept-defined properties that the OIM model doesn't represent as
    # first-class accessors; spec wants a 'is not a property' error rather
    # than 'unknown'.
    if propName in ("relationships", "attribute"):
        if propName == "attribute" and args:
            argVal = args[0]
            if argVal.type != FormulaValueType.QNAME:
                raise FormulaRuntimeError(
                    f"The argument for the 'attribute' property must be a qname, "
                    f"found '{argVal.type.name.lower()}'")
        raise FormulaRuntimeError(
            f"Property {propName!r} is not a property of a 'concept'.")
    raise FormulaRuntimeError(f"{propName!r} is not a valid property.")


# ---------------------------------------------------------------------------
# Taxonomy properties
# ---------------------------------------------------------------------------

def _taxonomyProp(txmy, propName: str, args, ctx) -> FormulaValue:
    from XbrlModel.XbrlConcept import XbrlConcept
    from XbrlModel.XbrlCube import XbrlCube
    from XbrlModel.XbrlDimension import XbrlDimension
    from XbrlModel.XbrlHeading import XbrlHeading
    from XbrlModel.XbrlNetwork import XbrlNetwork

    if propName == "concepts":
        objs = list(txmy.filterNamedObjects(XbrlConcept))
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.CONCEPT, c) for c in objs
        ))
    if propName == "concept-names":
        objs = list(txmy.filterNamedObjects(XbrlConcept))
        return _wrapSet(c.name for c in objs if hasattr(c, "name"))
    if propName == "headings":
        objs = list(txmy.filterNamedObjects(XbrlHeading))
        # Return heading QNames so list/set operations and name-based comparisons
        # behave consistently with other *-names style accessors.
        return _wrapSet(h.name for h in objs if hasattr(h, "name"))
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
        # networks($T)                       -> all networks
        # networks($T, arcrole)              -> filter by arcrole (QName, shorthand, or arcrole URI)
        # networks($T, arcrole, roleUri)     -> additionally filter by role URI
        arcArg = args[0].value if args else None
        roleArg = args[1].value if len(args) > 1 else None
        objs = list(txmy.filterNetworks(arcrole=arcArg, role=roleArg))
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
            # Fallback: match by local name across the loaded taxonomy
            # (rule sets often pin a default namespace to a specific
            # us-gaap year, but the model loaded at runtime may use a
            # different year's namespace).
            ln = qn.localName
            for c in txmy.filterNamedObjects(XbrlConcept):
                cn = getattr(c, "name", None)
                if isinstance(cn, QName) and cn.localName == ln:
                    return FormulaValue(FormulaValueType.CONCEPT, c)
        return NONE_VALUE
    # cube(qname, role) function
    if propName == "cube":
        if not args:
            raise FormulaRuntimeError("taxonomy.cube() requires arguments")
        qn = args[0].value
        # simplified — return first cube with matching concept
        from XbrlModel.XbrlCube import XbrlCube
        for cube in txmy.filterNamedObjects(XbrlCube):
            if getattr(cube, "name", None) == qn:
                return FormulaValue(FormulaValueType.CUBE, cube)
        return NONE_VALUE
    if propName == "networks":
        return _taxonomyProp(txmy, "networks", args, ctx)

    raise FormulaRuntimeError(f"{propName!r} is not a valid property.")


# (was: Unknown taxonomy property)
_TXMY_INVALID_PROP_MARKER = None


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
        from XbrlModel.XbrlFact import XbrlFact
        from arelle.ModelValue import qname as mkQn
        cubeDimQn = mkQn("https://xbrl.org/2026", "cube")
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


_TYPE_NAMES = {
    FormulaValueType.NONE:       "none",
    FormulaValueType.SKIP:       "skip",
    FormulaValueType.BOOLEAN:    "boolean",
    FormulaValueType.INTEGER:    "int",
    FormulaValueType.FLOAT:      "float",
    FormulaValueType.DECIMAL:    "decimal",
    FormulaValueType.STRING:     "string",
    FormulaValueType.QNAME:      "qname",
    FormulaValueType.DATE:       "instant",
    FormulaValueType.DATETIME:   "instant",
    FormulaValueType.DURATION:   "duration",
    FormulaValueType.FACT:       "fact",
    FormulaValueType.CONCEPT:    "concept",
    FormulaValueType.CUBE:       "cube",
    FormulaValueType.NETWORK:    "network",
    FormulaValueType.TAXONOMY:   "taxonomy",
    FormulaValueType.ENTITY:     "entity",
    FormulaValueType.UNIT_VALUE: "unit",
    FormulaValueType.SET:        "set",
    FormulaValueType.LIST:       "list",
    FormulaValueType.DICT:       "dictionary",
    FormulaValueType.SEVERITY:   "severity",
    FormulaValueType.LABEL:      "label",
    FormulaValueType.REFERENCE:  "reference",
    FormulaValueType.DATA_TYPE:  "data-type",
    FormulaValueType.PART:       "reference-part",
    FormulaValueType.ROLE:       "role",
    FormulaValueType.NAMESPACE:  "namespace",
}


def _typeNameOf(fv: FormulaValue) -> str:
    return _TYPE_NAMES.get(fv.type, fv.type.name.lower())


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
    # Xule allows property names in camelCase as aliases to the
    # kebab-case canonical form (e.g. periodType -> period-type).
    propName = _PROP_NAME_ALIASES.get(propName, propName)
    # ---- is-fact: defined on every value type ----
    if propName == "is-fact":
        return FormulaValue(
            FormulaValueType.BOOLEAN,
            obj.type == FormulaValueType.FACT,
        )

    # ---- _type: returns the spec-format type name for any value ----
    if propName == "_type":
        return FormulaValue(FormulaValueType.STRING, _typeNameOf(obj))

    if obj.type == FormulaValueType.FACT:
        handler = FACT_PROPS.get(propName)
        if handler:
            return handler(obj.value, args, ctx)
        # Fall back: treat the fact as its underlying scalar value so that
        # property access yields the proper "Property X is not a property of Y"
        # error (rather than a generic "Unknown fact property X").
        underlying = _factPropValue(obj.value, [], ctx)
        if underlying.type != FormulaValueType.NONE and underlying.type != FormulaValueType.FACT:
            return getProperty(underlying, propName, args, ctx)
        raise FormulaRuntimeError(f"Unknown fact property {propName!r}")

    if obj.type == FormulaValueType.ENTITY:
        ev = obj.value
        if propName == "name":
            # The entity "name" in xule is a QName whose ns=scheme, local=identifier.
            if isinstance(ev, QName):
                return FormulaValue(FormulaValueType.QNAME, ev)
            return NONE_VALUE
        if propName == "scheme":
            if isinstance(ev, QName):
                return FormulaValue(FormulaValueType.STRING, ev.namespaceURI)
            return NONE_VALUE
        if propName == "identifier" or propName == "id":
            if isinstance(ev, QName):
                return FormulaValue(FormulaValueType.STRING, ev.localName)
            return NONE_VALUE
        if propName == "local-name":
            if isinstance(ev, QName):
                return FormulaValue(FormulaValueType.STRING, ev.localName)
            return NONE_VALUE
        if propName == "namespace-uri":
            if isinstance(ev, QName):
                return FormulaValue(FormulaValueType.STRING, ev.namespaceURI)
            return NONE_VALUE
        raise FormulaRuntimeError(f"Unknown entity property {propName!r}")

    if obj.type == FormulaValueType.UNIT_VALUE:
        uv = obj.value
        # Normalise: simple unit may be a single QName; full form is (mulQns, divQns)
        if isinstance(uv, QName):
            mulQns, divQns = (uv,), ()
        elif isinstance(uv, tuple) and len(uv) == 2:
            mulQns, divQns = uv
        else:
            mulQns, divQns = (), ()
        if propName == "numerator":
            # Single numerator → return the QName directly so chained
            # .local-name / .namespace-uri work as the tests expect.
            if len(mulQns) == 1:
                return FormulaValue(FormulaValueType.QNAME, mulQns[0])
            return FormulaValue(FormulaValueType.LIST, [
                FormulaValue(FormulaValueType.QNAME, q) for q in mulQns
            ])
        if propName == "denominator":
            if len(divQns) == 1:
                return FormulaValue(FormulaValueType.QNAME, divQns[0])
            return FormulaValue(FormulaValueType.LIST, [
                FormulaValue(FormulaValueType.QNAME, q) for q in divQns
            ])
        raise FormulaRuntimeError(f"Unknown unit property {propName!r}")

    if obj.type == FormulaValueType.CONCEPT:
        return _conceptProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.LABEL:
        return _labelProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.REFERENCE:
        return _referenceProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.DATA_TYPE:
        return _dataTypeProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.PART:
        return _partProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.ROLE:
        return _roleProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.NAMESPACE:
        return _namespaceProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.TAXONOMY:
        return _taxonomyProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.CUBE:
        return _cubeProp(obj.value, propName, args, ctx)

    if propName == "random":
        raise FormulaRuntimeError("'random' is not a valid property.")

    # none → none, skip → skip: any property access propagates the value
    if obj.type == FormulaValueType.NONE:
        if propName == "inline-transform":
            from .FormulaFunctions import callFunction
            return callFunction("inline-transform", [obj] + list(args), ctx)
        return NONE_VALUE
    if obj.type == FormulaValueType.SKIP:
        from .FormulaValue import SKIP_VALUE
        return SKIP_VALUE

    # Numeric scalar properties
    if obj.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL, FormulaValueType.FACT):
        from .FormulaFunctions import callFunction
        if propName in ("string", "plain-string", "number"):
            if args:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 arguments. Found {len(args)}.")
            return callFunction(propName, [obj], ctx)
        if propName == "repeat":
            if obj.type == FormulaValueType.INTEGER:
                raise FormulaRuntimeError("'int' object has no attribute 'replace'")
            raise FormulaRuntimeError(f"Property 'repeat' is not a property of a '{obj.type.name.lower()}'.")
        if propName == "split":
            raise FormulaRuntimeError("'int' object has no attribute 'split'")
        if propName in ("abs", "log10", "decimal", "int", "signum"):
            if args:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 arguments. Found {len(args)}.")
            return callFunction(propName, [obj], ctx)
        if propName in ("power", "mod", "round"):
            if len(args) != 1:
                raise FormulaRuntimeError(f"Property '{propName}' must have 1 arguments. Found {len(args)}.")
            return callFunction(propName, [obj] + list(args), ctx)
        if propName == "trunc":
            if len(args) > 1:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 or 1 arguments. Found {len(args)}.")
            return callFunction(propName, [obj] + list(args), ctx)

    # String properties
    if obj.type == FormulaValueType.STRING:
        s = obj.value
        from .FormulaFunctions import callFunction
        if propName in ("first", "last"):
            raise FormulaRuntimeError(f"Property '{propName}' is not a property of a 'string'.")
        if propName == "index":
            raise FormulaRuntimeError("The 'index' property or index expression '[]' cannot be used on a string")
        if propName in (
            "length", "upper-case", "lower-case", "trim", "contains", "index-of", "last-index-of",
            "number", "split", "string", "plain-string", "repeat", "substring", "to-qname",
            "regex-match", "regex-match-all", "regex-match-string", "regex-match-string-all",
            "inline-transform",
        ):
            if propName in ("length", "upper-case", "lower-case", "string", "plain-string") and len(args) != 0:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 arguments. Found {len(args)}.")
            if propName in ("contains", "index-of", "last-index-of", "split", "repeat", "substring") and len(args) == 0:
                raise FormulaRuntimeError(f"Property '{propName}' must have 1 arguments. Found 0.")
            if propName in ("contains", "index-of", "last-index-of", "split", "repeat") and len(args) != 1:
                raise FormulaRuntimeError(f"Property '{propName}' must have 1 arguments. Found {len(args)}.")
            if propName == "substring" and len(args) not in (1, 2):
                raise FormulaRuntimeError(f"Property '{propName}' must have 1 or 2 arguments. Found {len(args)}.")
            if propName == "inline-transform" and len(args) not in (1, 2):
                raise FormulaRuntimeError(f"Property '{propName}' must have 1 or 2 arguments. Found {len(args)}.")
            return callFunction(propName, [obj] + list(args), ctx)
        if propName == "date":
            return callFunction("date", [obj], ctx)
        if propName == "time-span":
            return callFunction("time-span", [obj], ctx)
        if propName in ("day", "month", "year", "days", "start", "end"):
            raise FormulaRuntimeError(f"Property '{propName}' is not a property of a 'string'.")
        raise FormulaRuntimeError(f"Property '{propName}' is not a property of a 'string'.")

    # QName properties
    if obj.type == FormulaValueType.QNAME:
        qn = obj.value
        from .FormulaFunctions import callFunction
        if propName == "local-name":
            return FormulaValue(FormulaValueType.STRING, qn.localName if hasattr(qn, "localName") else str(qn))
        if propName == "namespace-uri":
            return FormulaValue(FormulaValueType.STRING, qn.namespaceURI if hasattr(qn, "namespaceURI") else "")
        if propName in ("string", "number", "to-qname"):
            if args:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 arguments. Found {len(args)}.")
            return callFunction(propName, [obj], ctx)
        if propName == "split":
            raise FormulaRuntimeError("Property 'split' is not a property of a 'qname'.")
        if propName in ("trim", "repeat", "contains", "index-of", "last-index-of", "substring"):
            return callFunction(propName, [obj] + list(args), ctx)
        if propName in ("day", "month", "year", "days", "start", "end", "date"):
            raise FormulaRuntimeError(f"Property '{propName}' is not a property of a 'QName'.")
        raise FormulaRuntimeError(f"Unknown QName property {propName!r}")

    if obj.type == FormulaValueType.NONE:
        if propName in ("keys", "values", "length", "date"):
            return NONE_VALUE
        raise FormulaRuntimeError(f"Cannot access property {propName!r} on NONE value")

    if obj.type == FormulaValueType.DATE:
        inst = obj.value
        if propName in ("string", "plain-string"):
            from .FormulaFunctions import callFunction
            return callFunction(propName, [obj], ctx)
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
        if propName in ("string", "plain-string"):
            from .FormulaFunctions import callFunction
            return callFunction(propName, [obj], ctx)
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
        raise FormulaRuntimeError(f"Unknown duration property {propName!r}")

    # Set/list properties
    if obj.type in (FormulaValueType.SET, FormulaValueType.LIST):
        coll = obj.value
        items_list = list(coll)
        # Generic per-element projection when collection contains FACT values
        # and the property is a fact-specific property (e.g. .decimals, .concept,
        # .cubes, .footnotes, .entity, ...).
        if (items_list
            and all(isinstance(it, FormulaValue) and it.type == FormulaValueType.FACT
                    for it in items_list)
            and (propName in FACT_PROPS or propName == "is-fact")):
            projected = [getProperty(it, propName, args, ctx) for it in items_list]
            if obj.type == FormulaValueType.SET:
                return FormulaValue(FormulaValueType.SET, OrderedSet(projected))
            return FormulaValue(FormulaValueType.LIST, projected)
        # Per-element projection for CONCEPT items (e.g. .balance, .name,
        # .period-type after applying ``.concept`` to a fact collection).
        if (items_list
            and all(isinstance(it, FormulaValue) and it.type == FormulaValueType.CONCEPT
                    for it in items_list)
            and propName in _CONCEPT_PROP_NAMES):
            projected = [getProperty(it, propName, args, ctx) for it in items_list]
            if obj.type == FormulaValueType.SET:
                return FormulaValue(FormulaValueType.SET, OrderedSet(projected))
            return FormulaValue(FormulaValueType.LIST, projected)
        if propName == "index":
            if len(args) != 1:
                raise FormulaRuntimeError(f"Property 'index' must have 1 arguments. Found {len(args)}.")
            if obj.type != FormulaValueType.LIST:
                raise FormulaRuntimeError(
                    "The 'index' property or index expression '[]' can only operate on a list or dictionary, "
                    f"found '{obj.type.name.lower()}'"
                )
            indexVal = args[0]
            if not indexVal.isNumeric:
                raise FormulaRuntimeError(f"Index of a list must be a number, found {indexVal.type.name.lower()}")
            try:
                oneBasedIdx = int(indexVal.numericValue())
            except Exception as exc:
                raise FormulaRuntimeError(f"Index of a list must be a number, found {indexVal.type.name.lower()}") from exc
            items = list(coll)
            if oneBasedIdx < 1 or oneBasedIdx > len(items):
                raise FormulaRuntimeError(
                    f"Index value of {oneBasedIdx} is out of range for the list with length of {len(items)}"
                )
            return items[oneBasedIdx - 1]
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
        if propName in (
            "lower-case", "upper-case", "trim", "split", "number", "plain-string", "repeat",
            "substring", "contains", "index-of", "last-index-of", "regex-match", "regex-match-all",
            "regex-match-string", "regex-match-string-all", "to-qname", "inline-transform",
        ):
            from .FormulaFunctions import callFunction
            projected = [callFunction(propName, [item] + list(args), ctx) for item in list(coll)]
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
        if propName in ("log10", "signum", "power", "round", "trunc"):
            from .FormulaFunctions import callFunction
            if propName in ("power", "round") and len(args) != 1:
                raise FormulaRuntimeError(f"Property '{propName}' must have 1 arguments. Found {len(args)}.")
            if propName in ("log10", "signum") and len(args) != 0:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 arguments. Found {len(args)}.")
            if propName == "trunc" and len(args) > 1:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 or 1 arguments. Found {len(args)}.")
            projected = [callFunction(propName, [item] + list(args), ctx) for item in list(coll)]
            if obj.type == FormulaValueType.SET:
                return FormulaValue(FormulaValueType.SET, OrderedSet(projected))
            return FormulaValue(FormulaValueType.LIST, projected)
        if propName in (
            "to-list", "to-dict", "to-json", "to-csv", "to-spreadsheet", "agg-to-dict",
            "sort", "sum", "max", "min", "prod", "stdev", "join",
            "all", "any", "contains", "intersect", "union", "difference",
            "symmetric-difference", "is-subset", "is-superset",
            "values", "keys",
            "abs", "avg",
        ):
            from .FormulaFunctions import callFunction
            if propName in ("abs", "avg") and len(args) != 0:
                raise FormulaRuntimeError(f"Property '{propName}' must have 0 arguments. Found {len(args)}.")
            return callFunction(propName, [obj] + list(args), ctx)
        # Fallback: project the property over each item. Per-item getProperty
        # will raise the proper "Property X is not a property of Y" error
        # when the projected property is invalid for that item's type.
        if items_list and all(isinstance(it, FormulaValue) for it in items_list):
            projected = [getProperty(it, propName, args, ctx) for it in items_list]
            if obj.type == FormulaValueType.SET:
                return FormulaValue(FormulaValueType.SET, OrderedSet(projected))
            return FormulaValue(FormulaValueType.LIST, projected)
        raise FormulaRuntimeError(f"Unknown collection property {propName!r}")

    if obj.type == FormulaValueType.DICT:
        if propName == "index":
            if len(args) != 1:
                raise FormulaRuntimeError(f"Property 'index' must have 1 arguments. Found {len(args)}.")
            return obj.value.get(args[0], NONE_VALUE)
        if propName in ("keys", "values", "has-key", "to-set", "to-json", "to-csv", "to-spreadsheet", "join"):
            from .FormulaFunctions import callFunction
            return callFunction(propName, [obj] + list(args), ctx)
        if propName in ("count", "length"):
            return FormulaValue(FormulaValueType.INTEGER, len(obj.value))
        raise FormulaRuntimeError(f"Unknown dictionary property {propName!r}")

    raise FormulaRuntimeError(
        f"Cannot access property {propName!r} on {obj.type.name} value"
    )
