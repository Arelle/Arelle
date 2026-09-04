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
    # A fact may carry several fact value objects -- the same value located in a
    # table and again in narrative text, or an amended value -- which resolve to
    # one by the duplicate rules rather than by taking whichever came first.
    from .FormulaDuplicates import effectiveFactValue
    fv = effectiveFactValue(fact)
    return FormulaValue.fromScalar(fv.value) if fv is not None else NONE_VALUE

def _factPropDecimals(fact, args, ctx):
    from .FormulaDuplicates import effectiveFactValue
    fv = effectiveFactValue(fact)
    return _wrap(getattr(fv, "decimals", None)) if fv is not None else NONE_VALUE

def _factPropFactValues(fact, args, ctx):
    return FormulaValue(FormulaValueType.SET, OrderedSet(
        FormulaValue.fromScalar(getattr(fv, "value", None))
        for fv in (getattr(fact, "factValues", None) or ())
    ))

def _factPropName(fact, args, ctx):
    return _wrap(getattr(fact, "name", None), FormulaValueType.QNAME)

def _factPropIsNil(fact, args, ctx):
    from .FormulaDuplicates import effectiveFactValue
    fv = effectiveFactValue(fact)
    return FormulaValue(FormulaValueType.BOOLEAN,
                        fv is not None and fv.value is None)

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
    "factValues":     _factPropFactValues,
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
    """Labels of an object.

    tavi-formula.md: `label(labelType, language)` and
    `all-labels(labelType, language)`. Both parameters are optional and either
    may be `none` to leave that filter off. A label type is a labelType object
    QName; an XBRL 2.1 label role URI is still accepted, since a rule ported
    from Formula 1.0 has one to hand.
    """
    compMdl = getattr(concept, "xbrlCompMdl", None)
    qn = getattr(concept, "name", None)
    if compMdl is None or qn is None:
        return NONE_VALUE
    tagObjs = compMdl.tagObjects.get(qn, ()) if hasattr(compMdl, "tagObjects") else ()
    labelObjs = [t for t in tagObjs if hasattr(t, "labelType")]

    def argAt(i):
        if len(args) <= i:
            return None
        v = args[i]
        return None if v.type == FormulaValueType.NONE else v.value

    wantType = argAt(0)
    wantLang = argAt(1)

    def typeMatches(t):
        if wantType is None:
            return True
        lt = getattr(t, "labelType", None)
        if isinstance(wantType, QName):
            return lt == wantType
        # a label role URI, as XBRL Formula 1.0 wrote it
        return _resolveLabelTypeUri(lt, ctx) == str(wantType)

    def langMatches(t):
        if wantLang is None:
            return True
        lang = getattr(t, "language", None)
        return lang is not None and str(lang).lower().startswith(str(wantLang).lower())

    matched = [t for t in labelObjs if typeMatches(t) and langMatches(t)]

    if propName in ("labels", "all-labels"):
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.LABEL, t) for t in matched))

    if wantType is None:
        # No label type asked for: prefer the standard label, in the query
        # set's message language where one is declared.
        stdUri = "http://www.xbrl.org/2003/role/label"
        msgLang = getattr(getattr(ctx.globalCtx, "ruleSet", None), "messageLanguage", None)
        def rank(t):
            lt = getattr(t, "labelType", None)
            isStd = (getattr(lt, "localName", None) == "label"
                     or _resolveLabelTypeUri(lt, ctx) == stdUri)
            lang = str(getattr(t, "language", "") or "")
            langOk = (msgLang is None) or lang.lower().startswith(str(msgLang).lower())
            return (0 if isStd else 1, 0 if langOk else 1)
        matched = sorted(matched, key=rank)

    return FormulaValue(FormulaValueType.LABEL, matched[0]) if matched else NONE_VALUE


def _conceptReferences(concept, args, ctx) -> FormulaValue:
    """References of an object, optionally filtered by reference type QName."""
    refs = _conceptReferenceObjects(concept, ctx)
    if args and args[0].type != FormulaValueType.NONE:
        wanted = args[0].value
        refs = [r for r in refs if getattr(r, "referenceType", None) == wanted]
    return FormulaValue(FormulaValueType.SET, OrderedSet(
        FormulaValue(FormulaValueType.REFERENCE, r) for r in refs))


def _conceptReferenceObjects(concept, ctx):
    """The XbrlReference objects that name this object in their forObjects.

    A reference is associated by `forObjects`, a set, and the model indexes
    references by each QName in a reference's *effective* forObjects -- which
    accounts for `extends` merging. Scanning `tagObjects` instead found only
    references that happened to be keyed by this object, and missed the rest.
    """
    compMdl = _mdlOf(concept, ctx)
    qn = getattr(concept, "name", None)
    if compMdl is None or qn is None:
        return []
    byForObject = getattr(compMdl, "_referenceObjectsByForObject", None)
    if callable(byForObject):
        return list(byForObject().get(qn, ()))
    return [t for t in getattr(compMdl, "tagObjects", {}).get(qn, ())
            if hasattr(t, "referenceType")]


# ---------------------------------------------------------------------------
# Label / Reference / DataType / Part / Role / Namespace property handlers
# ---------------------------------------------------------------------------

def _labelProp(label, propName: str, args, ctx) -> FormulaValue:
    if propName in ("text", "value"):
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
    if propName == "labelTypeName":
        return _wrap(getattr(label, "labelType", None), FormulaValueType.QNAME)
    if propName == "forObject":
        return _objValue(_mdlOf(label, ctx), getattr(label, "forObject", None))
    if propName == "concept":
        rn = getattr(label, "forObject", None)
        if rn is not None and ctx.txmyMdl is not None:
            obj = ctx.txmyMdl.namedObjects.get(rn)
            if obj is not None:
                return FormulaValue(FormulaValueType.CONCEPT, obj)
        return NONE_VALUE
    raise FormulaRuntimeError(f"Property {propName!r} is not a property of a 'label'.")


def _referenceProp(ref, propName: str, args, ctx) -> FormulaValue:
    if propName == "name":
        return _wrap(getattr(ref, "name", None), FormulaValueType.QNAME)
    if propName == "forObjects":
        mdl = _mdlOf(ref, ctx)
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            _objValue(mdl, qn) for qn in (getattr(ref, "forObjects", None) or ())))
    if propName in ("referenceTypeName", "reference-type-name"):
        return _wrap(getattr(ref, "referenceType", None), FormulaValueType.QNAME)
    if propName == "referenceType":
        return _objValue(_mdlOf(ref, ctx), getattr(ref, "referenceType", None))
    if propName == "properties":
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.PART, p)
            for p in (getattr(ref, "properties", None) or ())))
    if propName == "property":
        return _propertyByQName(ref, args[0].value) if args else NONE_VALUE
    if propName == "object-type":
        return _wrap(_objectTypeQNameOf(ref), FormulaValueType.QNAME)
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
                return FormulaValue.fromScalar(getattr(p, "value", None))
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
    if propName == "property":
        if not args:
            raise FormulaRuntimeError("property() requires a property type QName")
        return _propertyByQName(concept, args[0].value)
    if propName == "properties":
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.PART, p)
            for p in (getattr(concept, "properties", None) or ())))
    if propName == "object-type":
        return _wrap(getattr(concept, "objectTypeQName", None)
                     or _objectTypeQNameOf(concept), FormulaValueType.QNAME)
    if propName in ("dataTypeName", "data-type-name"):
        return _wrap(getattr(concept, "dataType", None), FormulaValueType.QNAME)
    if propName == "enumerationDomain":
        return _objValue(_mdlOf(concept, ctx), getattr(concept, "enumerationDomain", None))
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

def _entryModule(txmy):
    """The module a model was loaded from, as opposed to the ones it imports.

    `xbrlModels` holds the entry module alongside everything it pulled in, so
    taking the first gave `xs:XMLSchemaTypes`. The entry is the module no other
    module imports.
    """
    modules = getattr(txmy, "xbrlModels", None) or {}
    if not modules:
        return None
    imported = set()
    for mod in modules.values():
        for imp in getattr(mod, "importedTaxonomies", None) or ():
            imported.add(getattr(imp, "xbrlModelName", None))
    for name, mod in modules.items():
        if name not in imported:
            return mod
    return list(modules.values())[-1]


def _effectiveWeight(txmy, propName, args, ctx) -> FormulaValue:
    """Effective calculation weight between two concepts.

    Aggregated over every network whose relationship type is
    xbrl:summation-concept; 0 where the weight is not the same in all of them,
    or where no path relates the concepts.
    """
    from arelle.ModelValue import qname as mkQn
    from XbrlModel.XbrlConst import xbrl, qnXbrlRootSource
    from XbrlModel.XbrlNetwork import XbrlNetwork
    if len(args) < 2:
        raise FormulaRuntimeError(
            f"The '{propName}' property must have at least 2 arguments. Found {len(args)}.")

    def asQn(v):
        return v if isinstance(v, QName) else getattr(v, "name", None)

    src, tgt = asQn(args[0].value), asQn(args[1].value)
    wantNetwork = asQn(args[2].value) if len(args) > 2 and args[2].type != FormulaValueType.NONE else None
    summationQn = mkQn(xbrl, "xbrl:summation-concept")
    weightQn = mkQn(xbrl, "xbrl:weight")

    def weightOf(rel):
        for p in getattr(rel, "properties", None) or ():
            if getattr(p, "property", None) == weightQn:
                try:
                    return Decimal(str(getattr(p, "value", 1)))
                except Exception:
                    return Decimal(1)
        return Decimal(1)

    def pathWeight(nwk, frm, to, seen):
        """Product of weights along any path from frm to to, or None."""
        if frm == to:
            return Decimal(1)
        if frm in seen:
            return None
        seen = seen | {frm}
        for rel in txmy.effectiveRelationships(nwk) if getattr(nwk, "relationships", None) else ():
            if getattr(rel, "source", None) != frm or getattr(rel, "source", None) == qnXbrlRootSource:
                continue
            below = pathWeight(nwk, getattr(rel, "target", None), to, seen)
            if below is not None:
                return weightOf(rel) * below
        return None

    results = []
    for nwk in txmy.filterNamedObjects(XbrlNetwork):
        if getattr(nwk, "relationshipTypeName", None) != summationQn:
            continue
        if wantNetwork is not None and getattr(nwk, "name", None) != wantNetwork:
            continue
        w = pathWeight(nwk, src, tgt, frozenset())
        if w is not None:
            results.append((w, nwk))

    if propName == "effective-weight-network":
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.LIST, [FormulaValue.fromScalar(w),
                                                 FormulaValue(FormulaValueType.NETWORK, n)])
            for w, n in results))
    if not results:
        return FormulaValue.fromScalar(0)
    weights = {w for w, _n in results}
    return FormulaValue.fromScalar(weights.pop() if len(weights) == 1 else 0)


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
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.HEADING, h)
            for h in txmy.filterNamedObjects(XbrlHeading)))
    if propName == "heading-names":
        return _wrapSet(h.name for h in txmy.filterNamedObjects(XbrlHeading)
                        if hasattr(h, "name"))
    if propName == "cubes":
        objs = list(txmy.filterNamedObjects(XbrlCube))
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.CUBE, c) for c in objs
        ))
    if propName == "dimensions":
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.DIMENSION, d)
            for d in txmy.filterNamedObjects(XbrlDimension)))
    if propName == "dimension-names":
        return _wrapSet(d.name for d in txmy.filterNamedObjects(XbrlDimension)
                        if hasattr(d, "name"))
    if propName == "dimension":
        if not args:
            raise FormulaRuntimeError("model.dimension() requires a QName argument")
        obj = txmy.namedObjects.get(args[0].value)
        return (FormulaValue(FormulaValueType.DIMENSION, obj)
                if isinstance(obj, XbrlDimension) else NONE_VALUE)
    if propName == "networks":
        # networks()                    -> every network in the model
        # networks(relationshipType)    -> networks of that relationship type
        # networks(relationshipType, g) -> ...that group `g` contains
        #
        # tavi-formula.md changes the second parameter from a role URI (XBRL
        # Formula 1.0) to a group QName: a network is already addressable by its
        # own name through network(), so filtering by network name here would
        # make the function redundant, whereas selecting a group is a selection
        # no other function offers.
        arcArg = args[0].value if args else None
        objs = list(txmy.filterNetworks(arcrole=arcArg))
        if len(args) > 1 and args[1].type != FormulaValueType.NONE:
            groupQn = args[1].value
            if not isinstance(groupQn, QName):
                groupQn = getattr(groupQn, "name", None)
            wanted = set()
            for mod in (getattr(txmy, "xbrlModels", None) or {}).values():
                for gc in getattr(mod, "groupContents", ()) or ():
                    if getattr(gc, "groupName", None) == groupQn:
                        wanted.add(getattr(gc, "forObject", None))
            objs = [n for n in objs if getattr(n, "name", None) in wanted]
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.NETWORK, n) for n in objs
        ))
    if propName == "domainNetworks":
        from XbrlModel.XbrlDimension import XbrlDomainNetwork
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.DOMAIN_NETWORK, d)
            for d in txmy.filterNamedObjects(XbrlDomainNetwork)
        ))
    if propName == "groups":
        from XbrlModel.XbrlGroup import XbrlGroup
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.GROUP, g)
            for g in txmy.filterNamedObjects(XbrlGroup)
        ))
    if propName == "relationshipTypes":
        from XbrlModel.XbrlNetwork import XbrlRelationshipType
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.RELATIONSHIP_TYPE, rt)
            for rt in txmy.filterNamedObjects(XbrlRelationshipType)
        ))
    if propName == "members":
        from XbrlModel.XbrlDimension import XbrlMember
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.MEMBER, m)
            for m in txmy.filterNamedObjects(XbrlMember)
        ))
    if propName in ("network", "domainNetwork", "group"):
        # Single-object lookups by QName.
        if not args:
            raise FormulaRuntimeError(f"model.{propName}() requires a QName argument")
        from XbrlModel.XbrlDimension import XbrlDomainNetwork
        from XbrlModel.XbrlGroup import XbrlGroup
        from XbrlModel.XbrlNetwork import XbrlNetwork
        cls, vtype = {
            "network": (XbrlNetwork, FormulaValueType.NETWORK),
            "domainNetwork": (XbrlDomainNetwork, FormulaValueType.DOMAIN_NETWORK),
            "group": (XbrlGroup, FormulaValueType.GROUP),
        }[propName]
        obj = txmy.namedObjects.get(args[0].value)
        return FormulaValue(vtype, obj) if isinstance(obj, cls) else NONE_VALUE
    # Object collections of the model object (tavi-formula.md "Model object").
    # Each is an optional set on the model, so it is None when the model
    # declares no members rather than empty.
    _COLLECTIONS = {
        "facts":            ("XbrlModel.XbrlFact", "XbrlFact", FormulaValueType.FACT),
        "footnotes":        ("XbrlModel.XbrlFact", "XbrlFootnote", None),
        "entities":         ("XbrlModel.XbrlEntity", "XbrlEntity", FormulaValueType.ENTITY),
        "units":            ("XbrlModel.XbrlUnit", "XbrlUnit", None),
        "members":          ("XbrlModel.XbrlDimension", "XbrlMember", FormulaValueType.MEMBER),
        "domainClasses":    ("XbrlModel.XbrlDimension", "XbrlDomainClass", FormulaValueType.DOMAIN_CLASS),
        "labels":           ("XbrlModel.XbrlLabel", "XbrlLabel", FormulaValueType.LABEL),

        "dataTypes":        ("XbrlModel.XbrlConcept", "XbrlDataType", FormulaValueType.DATA_TYPE),
        "propertyTypes":    ("XbrlModel.XbrlProperty", "XbrlPropertyType", None),
        "labelTypes":       ("XbrlModel.XbrlLabel", "XbrlLabelType", None),
        "referenceTypes":   ("XbrlModel.XbrlReference", "XbrlReferenceType", None),
        "cubeTypes":        ("XbrlModel.XbrlCube", "XbrlCubeType", None),
        "tableTemplates":   ("XbrlModel.XbrlLayout", "XbrlTableTemplate", None),
        "transforms":       ("XbrlModel.XbrlTransform", "XbrlTransform", None),
    }
    if propName in _COLLECTIONS:
        modName, clsName, vtype = _COLLECTIONS[propName]
        import importlib
        try:
            cls = getattr(importlib.import_module(modName), clsName)
        except (ImportError, AttributeError):
            return FormulaValue(FormulaValueType.SET, OrderedSet())
        objs = list(txmy.filterNamedObjects(cls))
        if vtype is None:
            return FormulaValue(FormulaValueType.SET, OrderedSet(
                _objValue(txmy, getattr(o, "name", None)) if getattr(o, "name", None) is not None
                else FormulaValue.fromScalar(o) for o in objs))
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(vtype, o) for o in objs))

    if propName in ("name", "frameworkName", "version", "duplicateFactsInModel",
                    "modelType"):
        value = getattr(txmy, propName, None)
        if value is None or (propName == "name" and not isinstance(value, QName)):
            entry = _entryModule(txmy)
            value = getattr(entry, propName, None) if entry is not None else None
        if propName == "modelType":
            return _objValue(txmy, value)
        return _wrap(value, FormulaValueType.QNAME if propName == "name"
                     else FormulaValueType.STRING)
    if propName == "groupContents":
        out = OrderedSet()
        for mod in (getattr(txmy, "xbrlModels", None) or {}).values():
            for gc in getattr(mod, "groupContents", None) or ():
                out.add(FormulaValue.fromScalar(gc))
        return FormulaValue(FormulaValueType.SET, out)
    if propName == "importedTaxonomies":
        out = OrderedSet()
        for mod in (getattr(txmy, "xbrlModels", None) or {}).values():
            for imp in getattr(mod, "importedTaxonomies", None) or ():
                nm = getattr(imp, "xbrlModelName", None)
                if nm is not None:
                    out.add(FormulaValue(FormulaValueType.QNAME, nm))
        return FormulaValue(FormulaValueType.SET, out)
    if propName in ("effective-weight", "effective-weight-network"):
        return _effectiveWeight(txmy, propName, args, ctx)
    if propName == "references":
        # A reference is a tag object rather than a named one, so it is reached
        # through the model's object list, not filterNamedObjects.
        from XbrlModel.XbrlReference import XbrlReference
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.REFERENCE, o)
            for o in (getattr(txmy, "xbrlObjects", None) or ())
            if isinstance(o, XbrlReference)
            and getattr(o, "referenceType", None) is not None))
    if propName == "document-location":
        uri = getattr(getattr(txmy, "modelDocument", None), "uri", None)
        return _wrap(uri or _objectDocumentLocation(txmy))
    if propName == "namespaces":
        return _wrapSet(getattr(txmy, "namespaces", {}).values())
    if propName == "entry-point":
        return _wrap(getattr(txmy, "entryPoint", None))
    if propName == "uri":
        return _wrap(getattr(txmy, "entryPoint", None))
    # concept(qname) function
    if propName == "concept":
        if not args:
            raise FormulaRuntimeError("model.concept() requires a QName argument")
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
            raise FormulaRuntimeError("model.cube() requires a QName argument")
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
    mdl = _mdlOf(cube, ctx)
    if propName == "name":
        return FormulaValue(FormulaValueType.QNAME, getattr(cube, "name", None))
    if propName == "cubeType":
        return _objValue(mdl, getattr(cube, "cubeType", None))
    if propName == "cube-concept":
        qn = getattr(cube, "name", None)
        if qn:
            obj = mdl.namedObjects.get(qn)
            if obj:
                return FormulaValue(FormulaValueType.CONCEPT, obj)
        return NONE_VALUE
    if propName == "dimensions":
        dims = getattr(cube, "cubeDimensions", None) or ()
        return _wrapSet(getattr(d, "dimension", None) for d in dims)
    if propName == "cubeDimensions":
        return FormulaValue(FormulaValueType.LIST, [
            FormulaValue(FormulaValueType.CUBE_DIMENSION, cd)
            for cd in (getattr(cube, "cubeDimensions", None) or ())
        ])
    if propName == "dimension":
        if not args:
            raise FormulaRuntimeError("cube.dimension() requires a QName argument")
        wanted = args[0].value
        for cd in getattr(cube, "cubeDimensions", None) or ():
            if getattr(cd, "dimension", None) == wanted:
                return FormulaValue(FormulaValueType.CUBE_DIMENSION, cd)
        return NONE_VALUE
    if propName == "concepts":
        # The concepts a cube admits are the members of the domain network its
        # xbrl:concept cube dimension names.
        from arelle.ModelValue import qname as mkQn
        from XbrlModel.XbrlConst import xbrl
        conceptDimQn = mkQn(xbrl, "xbrl:concept")
        for cd in getattr(cube, "cubeDimensions", None) or ():
            if getattr(cd, "dimension", None) == conceptDimQn:
                try:
                    members = cd.allowedMembers(mdl)
                except AttributeError:
                    members = ()
                return FormulaValue(FormulaValueType.SET, OrderedSet(
                    _objValue(mdl, q) for q in members))
        return FormulaValue(FormulaValueType.SET, OrderedSet())
    if propName == "groups":
        return _groupsOf(mdl, getattr(cube, "name", None))
    if propName == "facts":
        from XbrlModel.XbrlFact import XbrlFact
        from arelle.ModelValue import qname as mkQn
        cubeDimQn = mkQn("https://xbrl.org/2026", "cube")
        cubeQn = getattr(cube, "name", None)
        facts = [
            f for f in mdl.filterNamedObjects(XbrlFact)
            if f.factDimensions.get(cubeDimQn) == cubeQn
        ]
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.FACT, f) for f in facts
        ))
    raise FormulaRuntimeError(f"Unknown cube property {propName!r}")



# ---------------------------------------------------------------------------
# Relationship, network, domain network, group and relationship type properties
#
# tavi-formula.md, "Object Data Model".  A property that yields a Tavi object
# property's stated value carries that property's name; where the stated value
# is a reference, a second property named without the `Name` suffix resolves it
# to the object.
# ---------------------------------------------------------------------------

_OBJECT_TYPE_QNAMES = {
    "XbrlConcept": "conceptObject", "XbrlHeading": "headingObject",
    "XbrlMember": "memberObject", "XbrlCube": "cubeObject",
    "XbrlDimension": "dimensionObject", "XbrlDomainNetwork": "domainNetworkObject",
    "XbrlDomainClass": "domainClassObject", "XbrlNetwork": "networkObject",
    "XbrlGroup": "groupObject", "XbrlRelationshipType": "relationshipTypeObject",
    "XbrlRelationship": "relationshipObject", "XbrlLabel": "labelObject",
    "XbrlReference": "referenceObject", "XbrlDataType": "dataTypeObject",
    "XbrlCubeType": "cubeTypeObject", "XbrlFact": "factObject",
    "XbrlEntity": "entityObject", "XbrlUnit": "unitObject",
}


def _objectTypeQNameOf(obj):
    """The object type QName of a model object, as tavi.md names them."""
    from arelle.ModelValue import qname as mkQn
    from XbrlModel.XbrlConst import xbrl
    local = _OBJECT_TYPE_QNAMES.get(type(obj).__name__)
    return mkQn(xbrl, "xbrl:" + local) if local else None


def _mdlOf(obj, ctx):
    """The compiled model an object belongs to, falling back to the evaluated one.

    A rule may query a model other than the one loaded -- `$US-GAAP-2020.networks`,
    `navigate ... model $OTHER` -- and the QNames on those objects resolve in
    *their* model, not in the evaluation context's. Resolving against ctx.txmyMdl
    silently returned none for every object reached that way.
    """
    seen = 0
    node = obj
    while node is not None and seen < 6:
        mdl = getattr(node, "xbrlCompMdl", None)
        if mdl is not None:
            return mdl
        node = (getattr(node, "cube", None) or getattr(node, "module", None)
                or getattr(node, "parentObject", None))
        seen += 1
    return ctx.txmyMdl


def _objValue(mdl, qn) -> FormulaValue:
    """Wrap a model object QName as the typed FormulaValue for its object kind."""
    if qn is None:
        return NONE_VALUE
    from XbrlModel.XbrlConcept import XbrlConcept
    from XbrlModel.XbrlCube import XbrlCube
    from XbrlModel.XbrlDimension import (
        XbrlDimension, XbrlDomainClass, XbrlDomainNetwork, XbrlMember)
    from XbrlModel.XbrlGroup import XbrlGroup
    from XbrlModel.XbrlHeading import XbrlHeading
    from XbrlModel.XbrlNetwork import XbrlNetwork, XbrlRelationshipType

    obj = mdl.namedObjects.get(qn) if mdl is not None else None
    if obj is None:
        # A relationship source or target need not resolve — xbrl:rootSource
        # names no object, and a domain class root may be a built-in — so the
        # QName itself is the value rather than an error.
        return FormulaValue(FormulaValueType.QNAME, qn)
    from XbrlModel.XbrlCube import XbrlCubeType
    from XbrlModel.XbrlConcept import XbrlDataType
    for cls, vtype in (
        (XbrlConcept, FormulaValueType.CONCEPT),
        (XbrlHeading, FormulaValueType.HEADING),
        (XbrlMember, FormulaValueType.MEMBER),
        (XbrlCube, FormulaValueType.CUBE),
        (XbrlDimension, FormulaValueType.DIMENSION),
        (XbrlDomainClass, FormulaValueType.DOMAIN_CLASS),
        (XbrlDomainNetwork, FormulaValueType.DOMAIN_NETWORK),
        (XbrlNetwork, FormulaValueType.NETWORK),
        (XbrlGroup, FormulaValueType.GROUP),
        (XbrlRelationshipType, FormulaValueType.RELATIONSHIP_TYPE),
        (XbrlCubeType, FormulaValueType.CUBE_TYPE),
        (XbrlDataType, FormulaValueType.DATA_TYPE),
    ):
        if isinstance(obj, cls):
            return FormulaValue(vtype, obj)
    return FormulaValue(FormulaValueType.MODEL_OBJECT, obj)


def _propertyByQName(obj, qn) -> FormulaValue:
    """The model-defined property value of `obj` whose propertyType is `qn`."""
    for propObj in getattr(obj, "properties", None) or ():
        if getattr(propObj, "property", None) == qn:
            return FormulaValue.fromScalar(getattr(propObj, "value", None))
    return NONE_VALUE


def _propertyByLocalName(obj, localName: str) -> Optional[FormulaValue]:
    """Property-name shorthand: match `localName` against property type local
    names.  Returns None when nothing matches so the caller can go on to raise
    a proper unknown-property error; raises when the name is ambiguous."""
    matches = [p for p in (getattr(obj, "properties", None) or ())
               if getattr(getattr(p, "property", None), "localName", None) == localName]
    if not matches:
        return None
    if len(matches) > 1:
        raise FormulaRuntimeError(
            f"Property name {localName!r} matches more than one property type; "
            f"use the QName form."
        )
    return FormulaValue.fromScalar(getattr(matches[0], "value", None))


def _groupsOf(mdl, containerName) -> FormulaValue:
    if containerName is None or mdl is None:
        return FormulaValue(FormulaValueType.SET, OrderedSet())
    from XbrlModel.XbrlGroup import XbrlGroup
    out = OrderedSet()
    for mod in (getattr(mdl, "xbrlModels", None) or {}).values():
        for gc in getattr(mod, "groupContents", ()) or ():
            if getattr(gc, "forObject", None) != containerName:
                continue
            grp = mdl.namedObjects.get(getattr(gc, "groupName", None))
            if isinstance(grp, XbrlGroup):
                out.add(FormulaValue(FormulaValueType.GROUP, grp))
    return FormulaValue(FormulaValueType.SET, out)


def _relationshipProp(nav, propName: str, args, ctx) -> FormulaValue:
    """Properties of a relationship as reached by navigation.

    `nav` is a FormulaNavigate.NavRelationship, which carries the traversal
    context (container, cube, depth) alongside the XbrlRelationship, because the
    same relationship reached two ways answers these differently.
    """
    from XbrlModel.XbrlDimension import XbrlDomainNetwork
    from .FormulaNavigate import _domainMemberQn

    rel = nav.rel
    container = nav.container
    mdl = _mdlOf(container, ctx)

    if propName in ("source",):
        return _objValue(mdl, nav.source)
    if propName in ("source-name", "sourceName"):
        return FormulaValue(FormulaValueType.QNAME, nav.source) if nav.source is not None else NONE_VALUE
    if propName in ("target",):
        return _objValue(mdl, nav.target)
    if propName in ("target-name", "targetName"):
        return FormulaValue(FormulaValueType.QNAME, nav.target) if nav.target is not None else NONE_VALUE
    if propName == "order":
        o = getattr(rel, "order", None)
        return FormulaValue.fromScalar(o if o is not None else 0)
    if propName == "relationship":
        return FormulaValue(FormulaValueType.RELATIONSHIP, nav)

    if propName in ("relationshipType", "relationship-type"):
        if isinstance(container, XbrlDomainNetwork):
            # xbrl:domain-member has no relationship type object to resolve.
            return NONE_VALUE
        rt = getattr(container, "relationshipType", None)
        return FormulaValue(FormulaValueType.RELATIONSHIP_TYPE, rt) if rt is not None else NONE_VALUE
    if propName in ("relationshipTypeName", "relationship-type-name"):
        if isinstance(container, XbrlDomainNetwork):
            return FormulaValue(FormulaValueType.QNAME, _domainMemberQn(mdl))
        rtn = getattr(container, "relationshipTypeName", None)
        return FormulaValue(FormulaValueType.QNAME, rtn) if rtn is not None else NONE_VALUE

    if propName == "network":
        return (NONE_VALUE if isinstance(container, XbrlDomainNetwork)
                else FormulaValue(FormulaValueType.NETWORK, container))
    if propName in ("domainNetwork", "domain-network"):
        return (FormulaValue(FormulaValueType.DOMAIN_NETWORK, container)
                if isinstance(container, XbrlDomainNetwork) else NONE_VALUE)
    if propName == "container":
        vtype = (FormulaValueType.DOMAIN_NETWORK if isinstance(container, XbrlDomainNetwork)
                 else FormulaValueType.NETWORK)
        return FormulaValue(vtype, container)
    if propName in ("group", "groups"):
        grps = _groupsOf(mdl, getattr(container, "name", None))
        if propName == "group":
            items = list(grps.value)
            return items[0] if items else NONE_VALUE
        return grps

    if propName == "cube":
        return FormulaValue(FormulaValueType.CUBE, nav.cube) if nav.cube is not None else NONE_VALUE
    if propName in ("cubeDimension", "cube-dimension"):
        return (FormulaValue(FormulaValueType.CUBE_DIMENSION, nav.cubeDimension)
                if nav.cubeDimension is not None else NONE_VALUE)
    if propName == "dimension":
        cd = nav.cubeDimension
        return _objValue(mdl, getattr(cd, "dimension", None)) if cd is not None else NONE_VALUE

    if propName == "cycle":
        return FormulaValue(FormulaValueType.BOOLEAN, bool(nav.isCycle))
    if propName in ("navigation-depth", "navigationDepth"):
        return FormulaValue(FormulaValueType.INTEGER, nav.depth)
    if propName in ("navigation-order", "navigationOrder"):
        return FormulaValue(FormulaValueType.INTEGER, nav.navOrder)
    if propName in ("result-order", "resultOrder"):
        return FormulaValue(FormulaValueType.INTEGER, getattr(nav, "resultOrder", 0))
    if propName in ("is-root-source", "isRootSource"):
        from XbrlModel.XbrlConst import qnXbrlRootSource
        return FormulaValue(FormulaValueType.BOOLEAN,
                            getattr(rel, "source", None) == qnXbrlRootSource)
    if propName == "properties":
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.PART, p)
            for p in (getattr(rel, "properties", None) or ())
        ))
    if propName == "property":
        if not args:
            raise FormulaRuntimeError("relationship.property() requires a QName argument")
        return _propertyByQName(rel, args[0].value)

    # Property-name shorthand over the relationship's link properties, so that
    # `weight` and `preferredLabel` reach xbrl:weight and xbrl:preferredLabel.
    shorthand = _propertyByLocalName(rel, propName)
    if shorthand is not None:
        return shorthand
    raise FormulaRuntimeError(f"Unknown relationship property {propName!r}")


def _networkProp(nwk, propName: str, args, ctx) -> FormulaValue:
    from XbrlModel.XbrlConst import qnXbrlRootSource
    mdl = _mdlOf(nwk, ctx)
    if propName == "name":
        return FormulaValue(FormulaValueType.QNAME, getattr(nwk, "name", None))
    if propName in ("relationshipTypeName", "relationship-type-name"):
        rtn = getattr(nwk, "relationshipTypeName", None)
        return FormulaValue(FormulaValueType.QNAME, rtn) if rtn is not None else NONE_VALUE
    if propName in ("relationshipType", "relationship-type"):
        rt = getattr(nwk, "relationshipType", None)
        return FormulaValue(FormulaValueType.RELATIONSHIP_TYPE, rt) if rt is not None else NONE_VALUE
    if propName == "relationships":
        from .FormulaNavigate import NavRelationship, _effectiveRelationships
        rels = [r for r in _effectiveRelationships(mdl, nwk)
                if getattr(r, "source", None) != qnXbrlRootSource]
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.RELATIONSHIP, NavRelationship(r, nwk)) for r in rels
        ))
    if propName in ("roots", "root-names"):
        from .FormulaNavigate import _roots
        qns = _roots(mdl, nwk)
        if propName == "root-names":
            return _wrapSet(qns)
        return FormulaValue(FormulaValueType.SET, OrderedSet(_objValue(mdl, q) for q in qns))
    if propName in ("sources", "targets", "concepts", "concept-names"):
        from .FormulaNavigate import _effectiveRelationships
        from XbrlModel.XbrlConcept import XbrlConcept
        rels = [r for r in _effectiveRelationships(mdl, nwk)
                if getattr(r, "source", None) != qnXbrlRootSource]
        if propName == "sources":
            qns = OrderedSet(getattr(r, "source", None) for r in rels)
        elif propName == "targets":
            qns = OrderedSet(getattr(r, "target", None) for r in rels)
        else:
            qns = OrderedSet()
            for r in rels:
                qns.add(getattr(r, "source", None))
                qns.add(getattr(r, "target", None))
            qns = OrderedSet(q for q in qns
                             if isinstance(mdl.namedObjects.get(q), XbrlConcept))
        if propName == "concept-names":
            return _wrapSet(qns)
        return FormulaValue(FormulaValueType.SET, OrderedSet(_objValue(mdl, q) for q in qns))
    if propName in ("group", "groups"):
        grps = _groupsOf(mdl, getattr(nwk, "name", None))
        if propName == "group":
            items = list(grps.value)
            return items[0] if items else NONE_VALUE
        return grps
    if propName == "isExtensible":
        return FormulaValue(FormulaValueType.BOOLEAN, bool(getattr(nwk, "isExtensible", True)))
    if propName in ("label", "all-labels", "references"):
        return _conceptLabel(nwk, propName, args, ctx) if propName != "references" \
            else _conceptReferences(nwk, args, ctx)
    if propName == "property":
        return _propertyByQName(nwk, args[0].value) if args else NONE_VALUE
    shorthand = _propertyByLocalName(nwk, propName)
    if shorthand is not None:
        return shorthand
    raise FormulaRuntimeError(f"Unknown network property {propName!r}")


def _domainNetworkProp(dom, propName: str, args, ctx) -> FormulaValue:
    mdl = _mdlOf(dom, ctx)
    if propName == "name":
        return FormulaValue(FormulaValueType.QNAME, getattr(dom, "name", None))
    if propName == "root":
        return _objValue(mdl, getattr(dom, "root", None))
    if propName == "relationships":
        from .FormulaNavigate import NavRelationship, _effectiveRelationships
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            FormulaValue(FormulaValueType.RELATIONSHIP, NavRelationship(r, dom))
            for r in _effectiveRelationships(mdl, dom)
        ))
    if propName in ("members", "member-names"):
        from .FormulaNavigate import _effectiveRelationships
        qns = OrderedSet(getattr(r, "target", None)
                         for r in _effectiveRelationships(mdl, dom))
        if propName == "member-names":
            return _wrapSet(qns)
        return FormulaValue(FormulaValueType.SET, OrderedSet(_objValue(mdl, q) for q in qns))
    if propName in ("relationshipTypeName", "relationship-type-name"):
        from .FormulaNavigate import _domainMemberQn
        return FormulaValue(FormulaValueType.QNAME, _domainMemberQn(mdl))
    if propName in ("group", "groups"):
        grps = _groupsOf(mdl, getattr(dom, "name", None))
        if propName == "group":
            items = list(grps.value)
            return items[0] if items else NONE_VALUE
        return grps
    if propName == "isExtensible":
        return FormulaValue(FormulaValueType.BOOLEAN, bool(getattr(dom, "isExtensible", True)))
    if propName == "property":
        return _propertyByQName(dom, args[0].value) if args else NONE_VALUE
    shorthand = _propertyByLocalName(dom, propName)
    if shorthand is not None:
        return shorthand
    raise FormulaRuntimeError(f"Unknown domainNetwork property {propName!r}")


def _groupProp(grp, propName: str, args, ctx) -> FormulaValue:
    mdl = _mdlOf(grp, ctx)
    if propName == "name":
        return FormulaValue(FormulaValueType.QNAME, getattr(grp, "name", None))
    if propName in ("groupURI", "group-uri", "uri"):
        return _wrap(getattr(grp, "groupURI", None))
    if propName in ("label", "all-labels"):
        return _conceptLabel(grp, propName, args, ctx)
    if propName == "references":
        return _conceptReferences(grp, args, ctx)
    if propName in ("contents", "networks", "domainNetworks", "cubes", "tableTemplates"):
        from XbrlModel.XbrlCube import XbrlCube
        from XbrlModel.XbrlDimension import XbrlDomainNetwork
        from XbrlModel.XbrlNetwork import XbrlNetwork
        wanted = {"networks": XbrlNetwork, "domainNetworks": XbrlDomainNetwork,
                  "cubes": XbrlCube}.get(propName)
        gName = getattr(grp, "name", None)
        out = OrderedSet()
        for mod in (getattr(mdl, "xbrlModels", None) or {}).values():
            for gc in getattr(mod, "groupContents", ()) or ():
                if getattr(gc, "groupName", None) != gName:
                    continue
                qn = getattr(gc, "forObject", None)
                obj = mdl.namedObjects.get(qn)
                if wanted is not None and not isinstance(obj, wanted):
                    continue
                if propName == "tableTemplates":
                    if type(obj).__name__ != "XbrlTableTemplate":
                        continue
                out.add(_objValue(mdl, qn))
        return FormulaValue(FormulaValueType.SET, out)
    if propName == "property":
        return _propertyByQName(grp, args[0].value) if args else NONE_VALUE
    shorthand = _propertyByLocalName(grp, propName)
    if shorthand is not None:
        return shorthand
    raise FormulaRuntimeError(f"Unknown group property {propName!r}")


def _relationshipTypeProp(rt, propName: str, args, ctx) -> FormulaValue:
    if propName == "name":
        return FormulaValue(FormulaValueType.QNAME, getattr(rt, "name", None))
    if propName == "uri":
        return _wrap(getattr(rt, "uri", None))
    if propName in ("cycles", "cycles-allowed", "cyclesAllowed"):
        return _wrap(getattr(rt, "cycles", None) or "none")
    if propName in ("allowedLinkProperties", "requiredLinkProperties",
                    "sourceObjects", "targetObjects"):
        return _wrapSet(getattr(rt, propName, None) or ())
    if propName in ("label", "all-labels"):
        return _conceptLabel(rt, propName, args, ctx)
    if propName == "references":
        return _conceptReferences(rt, args, ctx)
    raise FormulaRuntimeError(f"Unknown relationshipType property {propName!r}")


def _cubeDimensionProp(cd, propName: str, args, ctx) -> FormulaValue:
    mdl = _mdlOf(cd, ctx)
    if propName == "dimension":
        return _objValue(mdl, getattr(cd, "dimension", None))
    if propName in ("dimensionName", "dimension-name"):
        return FormulaValue(FormulaValueType.QNAME, getattr(cd, "dimension", None))
    if propName == "domainNetwork":
        return _objValue(mdl, getattr(cd, "domainNetwork", None))
    if propName == "domainDataType":
        return _objValue(mdl, getattr(cd, "domainDataType", None))
    if propName in ("is-typed", "isTyped"):
        return FormulaValue(FormulaValueType.BOOLEAN,
                            getattr(cd, "domainDataType", None) is not None)
    if propName in ("is-explicit", "isExplicit"):
        return FormulaValue(FormulaValueType.BOOLEAN,
                            getattr(cd, "domainDataType", None) is None)
    if propName == "typedSort":
        return _wrap(getattr(cd, "typedSort", None))
    if propName == "optional":
        return FormulaValue(FormulaValueType.BOOLEAN, bool(getattr(cd, "optional", False)))
    if propName == "members":
        from XbrlModel.XbrlDimension import XbrlDomainNetwork
        dom = mdl.namedObjects.get(getattr(cd, "domainNetwork", None))
        if not isinstance(dom, XbrlDomainNetwork):
            return FormulaValue(FormulaValueType.SET, OrderedSet())
        from .FormulaNavigate import _effectiveRelationships
        return FormulaValue(FormulaValueType.SET, OrderedSet(
            _objValue(mdl, getattr(r, "target", None))
            for r in _effectiveRelationships(mdl, dom)))
    if propName == "allowed-members":
        # What a fact may carry: includes the domain class root where the
        # dimension is optional, which is the absent-dimension position.
        try:
            qns = cd.allowedMembers(mdl)
        except AttributeError:
            qns = ()
        return FormulaValue(FormulaValueType.SET, OrderedSet(_objValue(mdl, q) for q in qns))
    if propName == "cube":
        cube = getattr(cd, "cube", None)
        return FormulaValue(FormulaValueType.CUBE, cube) if cube is not None else NONE_VALUE
    raise FormulaRuntimeError(f"Unknown cubeDimension property {propName!r}")


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
    FormulaValueType.DOMAIN_NETWORK: "domainNetwork",
    FormulaValueType.DOMAIN_CLASS: "domainClass",
    FormulaValueType.CUBE_TYPE: "cubeType",
    FormulaValueType.MODEL_OBJECT: "object",
    FormulaValueType.RELATIONSHIP:   "relationship",
    FormulaValueType.RELATIONSHIP_TYPE: "relationshipType",
    FormulaValueType.GROUP:      "group",
    FormulaValueType.CUBE_DIMENSION: "cubeDimension",
    FormulaValueType.MEMBER:     "member",
    FormulaValueType.DIMENSION:  "dimension",
    FormulaValueType.HEADING:    "heading",
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

    if obj.type == FormulaValueType.QNAME and propName in ("name", "local-name", "namespace-uri"):
        qn = obj.value
        if propName == "name":
            return obj
        if propName == "local-name":
            return _wrap(getattr(qn, "localName", None), FormulaValueType.STRING)
        return _wrap(getattr(qn, "namespaceURI", None), FormulaValueType.STRING)

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

    if obj.type == FormulaValueType.RELATIONSHIP:
        return _relationshipProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.NETWORK:
        return _networkProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.DOMAIN_NETWORK:
        return _domainNetworkProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.GROUP:
        return _groupProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.DIMENSION:
        dim = obj.value
        mdl = _mdlOf(dim, ctx)
        if propName == "name":
            return _wrap(getattr(dim, "name", None), FormulaValueType.QNAME)
        if propName == "local-name":
            return _wrap(getattr(getattr(dim, "name", None), "localName", None),
                         FormulaValueType.STRING)
        if propName == "namespace-uri":
            return _wrap(getattr(getattr(dim, "name", None), "namespaceURI", None),
                         FormulaValueType.STRING)
        if propName == "domainClass":
            return _objValue(mdl, getattr(dim, "domainClass", None))
        if propName == "cubeTypes":
            return _wrapSet(getattr(dim, "cubeTypes", None) or ())
        if propName == "is-core":
            nm = getattr(dim, "name", None)
            return FormulaValue(FormulaValueType.BOOLEAN,
                                getattr(nm, "localName", None) in
                                ("concept", "period", "entity", "unit", "language"))
        if propName == "object-type":
            return _wrap(_objectTypeQNameOf(dim), FormulaValueType.QNAME)
        if propName in ("label", "all-labels"):
            return _conceptLabel(dim, propName, args, ctx)
        if propName == "references":
            return _conceptReferences(dim, args, ctx)
        if propName == "property":
            return _propertyByQName(dim, args[0].value) if args else NONE_VALUE
        shorthand = _propertyByLocalName(dim, propName)
        if shorthand is not None:
            return shorthand
        raise FormulaRuntimeError(f"Unknown dimension property {propName!r}")

    if obj.type in (FormulaValueType.MODEL_OBJECT, FormulaValueType.CUBE_TYPE):
        o = obj.value
        if o is None:
            return NONE_VALUE
        if propName == "name":
            return _wrap(getattr(o, "name", None), FormulaValueType.QNAME)
        if propName == "local-name":
            nm = getattr(o, "name", None)
            return _wrap(getattr(nm, "localName", None), FormulaValueType.STRING)
        if propName == "namespace-uri":
            nm = getattr(o, "name", None)
            return _wrap(getattr(nm, "namespaceURI", None), FormulaValueType.STRING)
        if propName == "object-type":
            return _wrap(_objectTypeQNameOf(o), FormulaValueType.QNAME)
        if propName == "uri":
            return _wrap(getattr(o, "uri", None))
        if propName in ("label", "all-labels"):
            return _conceptLabel(o, propName, args, ctx)
        if propName == "property":
            return _propertyByQName(o, args[0].value) if args else NONE_VALUE
        shorthand = _propertyByLocalName(o, propName)
        if shorthand is not None:
            return shorthand
        value = getattr(o, propName, None)
        if value is not None:
            return FormulaValue.fromScalar(value)
        raise FormulaRuntimeError(
            f"Property {propName!r} is not a property of a {_typeNameOf(obj)!r}.")

    if obj.type == FormulaValueType.DOMAIN_CLASS:
        dc = obj.value
        if propName == "name":
            return FormulaValue(FormulaValueType.QNAME, getattr(dc, "name", None))
        if propName == "local-name":
            return _wrap(getattr(getattr(dc, "name", None), "localName", None),
                         FormulaValueType.STRING)
        if propName == "namespace-uri":
            return _wrap(getattr(getattr(dc, "name", None), "namespaceURI", None),
                         FormulaValueType.STRING)
        if propName == "object-type":
            return _wrap(_objectTypeQNameOf(dc), FormulaValueType.QNAME)
        if propName == "allowedDomainItem":
            return _wrap(getattr(dc, "allowedDomainItem", None), FormulaValueType.QNAME)
        if propName == "baseDomainClass":
            return _objValue(_mdlOf(dc, ctx), getattr(dc, "baseDomainClass", None))
        if propName in ("label", "all-labels"):
            return _conceptLabel(dc, propName, args, ctx)
        raise FormulaRuntimeError(f"Unknown domainClass property {propName!r}")

    if obj.type == FormulaValueType.RELATIONSHIP_TYPE:
        return _relationshipTypeProp(obj.value, propName, args, ctx)

    if obj.type == FormulaValueType.CUBE_DIMENSION:
        return _cubeDimensionProp(obj.value, propName, args, ctx)

    if obj.type in (FormulaValueType.MEMBER, FormulaValueType.HEADING):
        return _conceptProp(obj.value, propName, args, ctx)

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
        # Per-element projection for FACT items: a collection of facts answers
        # a fact property by answering it for each fact, which is how
        # `$facts.concept`, `$facts.decimals` and `$facts.entity` read.
        if (items_list
            and all(isinstance(it, FormulaValue) and it.type == FormulaValueType.FACT
                    for it in items_list)
            and propName in FACT_PROPS):
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
            "all", "any", "contains", "intersect", "union", "difference", "denone",
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
