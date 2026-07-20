"""
See COPYRIGHT.md for copyright information.

Shared converters for the built-in legacy fact maps.

The functions here translate the standard XBRL 2.1 instance constructs -- contexts
(entity / period / explicit + typed dimensions), units, footnote language, decimals,
and the generated fact identity -- into their OIM representations. They are format
agnostic: they operate on ordinary ``xbrli:context`` / ``xbrli:period`` / ``xbrli:unit``
lxml elements, so they are reused by

* ``LoadXbrlXmlFacts`` -- which parses a flat XBRL 2.1 instance directly, and
* ``LoadInlineFacts`` -- whose ``ModelInlineFact`` objects expose the same
  ``xbrli:context`` / ``xbrli:unit`` elements (wrapped as ``ModelContext`` /
  ``ModelUnit``) that inline discovery synthesised from the ``ix:resources``.

Keeping the conversion in one place means the two loaders cannot drift on period
day-boundary rules, pure-unit dropping, dimension member resolution, or the
namespace-map redirect.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from arelle.ModelValue import QName

from .XbrlConst import xbrl as xbrlNs

# XBRL 2.1 namespaces (fixed by the XBRL 2.1 / dimensions specifications).
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
LINK = "http://www.xbrl.org/2003/linkbase"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XMLNS = "http://www.w3.org/XML/1998/namespace"

# OIM property QNames emitted for nil facts.
qnNil = QName("xbrl", xbrlNs, "nil")
qnUnknownNilReason = QName("xbrl", xbrlNs, "unknownNilReason")

# xbrli:pure. A unit of pure (the domain value of xbrl:unit) is equivalent to no
# unit, so a lone pure numerator is dropped when building the OIM unit string.
qnPure = QName("xbrli", XBRLI, "pure")


# --------------------------------------------------------------------------
# Generic lxml helpers
# --------------------------------------------------------------------------

def clark(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def localName(elt) -> str:
    tag = elt.tag
    return tag.rpartition('}')[2] if isinstance(tag, str) else tag


def eltQName(elt, nsmap) -> Optional[QName]:
    """Resolve an lxml element's tag to a QName, carrying its source prefix."""
    tag = elt.tag
    if not isinstance(tag, str) or not tag.startswith('{'):
        return None
    ns, _b, local = tag[1:].partition('}')
    prefix = None
    for p, u in (nsmap or {}).items():
        if u == ns:
            prefix = p
            break
    return QName(prefix, ns, local)


def resolvePrefixedName(text: str, nsmap) -> Optional[QName]:
    """Resolve a ``prefix:local`` string against an lxml nsmap into a QName."""
    if not text:
        return None
    text = text.strip()
    prefix, _sep, local = text.rpartition(':')
    if not _sep:  # unprefixed -> default namespace
        ns = (nsmap or {}).get(None)
        return QName(None, ns, local) if ns else None
    ns = (nsmap or {}).get(prefix)
    if ns is None:
        return None
    return QName(prefix, ns, local)


def innerText(elt) -> str:
    return ''.join(elt.itertext())


def inheritedLang(elt) -> Optional[str]:
    p = elt.getparent()
    while p is not None:
        lang = p.get(clark(XMLNS, "lang"))
        if lang:
            return lang
        p = p.getparent()
    return None


# --------------------------------------------------------------------------
# Period
# --------------------------------------------------------------------------

def dayAfter(dateStr: str) -> str:
    """Return the OIM datetime for the *end* of an XBRL 2.1 date (start of the
    following day). A date without a time component is treated as end-of-day, i.e.
    midnight of the next day (per the xBRL-XML fact map)."""
    if 'T' in dateStr:
        return dateStr  # already a dateTime; carry through unchanged
    y, m, d = (int(p) for p in dateStr.split('-'))
    nxt = date(y, m, d) + timedelta(days=1)
    return nxt.strftime("%Y-%m-%dT00:00:00")


def startOfDay(dateStr: str) -> str:
    if 'T' in dateStr:
        return dateStr
    return dateStr + "T00:00:00"


def oimPeriod(periodElt) -> Optional[str]:
    """Map an ``xbrli:period`` element to an OIM period string, or None for forever."""
    instant = periodElt.find(clark(XBRLI, "instant"))
    if instant is not None and instant.text:
        return dayAfter(instant.text.strip())
    start = periodElt.find(clark(XBRLI, "startDate"))
    end = periodElt.find(clark(XBRLI, "endDate"))
    if start is not None and end is not None and start.text and end.text:
        return f"{startOfDay(start.text.strip())}/{dayAfter(end.text.strip())}"
    return None  # xbrli:forever -> no period dimension


# --------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------

def modulePrefixedName(module, qn) -> str:
    """Serialise a measure QName as an OIM ``prefix:local`` string whose prefix is
    bound in the module's namespace map (registering the namespace if needed), so
    the resulting unit string resolves during fact validation. QName equality
    ignores the prefix, so a measure declared via a default namespace (e.g.
    ``<measure>USD</measure>`` in an xbrli default-namespaced instance) still gets a
    usable prefix here."""
    prefixNs = getattr(module, "_prefixNamespaces", None)
    if prefixNs is None:
        return f"{qn.prefix}:{qn.localName}" if qn.prefix else qn.localName
    for p, u in prefixNs.items():
        if u == qn.namespaceURI and p is not None:
            return f"{p}:{qn.localName}"
    prefix = qn.prefix
    if not prefix or prefix in prefixNs:
        i = 0
        while f"ns{i}" in prefixNs:
            i += 1
        prefix = f"ns{i}"
    prefixNs[prefix] = qn.namespaceURI
    return f"{prefix}:{qn.localName}"


def oimUnit(unitElt, module) -> Optional[str]:
    """Map an ``xbrli:unit`` element to an OIM unit string representation.

    A single ``xbrli:pure`` numerator with no denominator is dropped (returns
    None): a unit of pure is equivalent to no unit, so such facts are unit-less.
    """
    def measureQNames(parent) -> list:
        qns = []
        for m in parent.findall(clark(XBRLI, "measure")):
            qn = resolvePrefixedName((m.text or "").strip(), m.nsmap)
            if qn is not None:
                qns.append(qn)
        return qns

    def emit(qns) -> str:
        # measures serialised as module-valid prefixed names, in alphabetical order
        names = sorted(modulePrefixedName(module, qn) for qn in qns)
        joined = '*'.join(names)
        return f"({joined})" if len(names) > 1 else joined

    divide = unitElt.find(clark(XBRLI, "divide"))
    if divide is not None:
        num = divide.find(clark(XBRLI, "unitNumerator"))
        den = divide.find(clark(XBRLI, "unitDenominator"))
        nums = measureQNames(num) if num is not None else []
        dens = measureQNames(den) if den is not None else []
        numStr = emit(nums)
        denStr = emit(dens)
        return f"{numStr}/{denStr}" if denStr else numStr
    nums = measureQNames(unitElt)
    if not nums:
        return None
    if len(nums) == 1 and nums[0] == qnPure:
        return None  # a lone xbrli:pure numerator is equivalent to no unit
    return emit(nums)


# --------------------------------------------------------------------------
# Contexts / dimensions
# --------------------------------------------------------------------------

def parseDimensions(container, dims) -> None:
    for dimElt in container:
        ln = localName(dimElt)
        dimAttr = dimElt.get("dimension")
        if not dimAttr:
            continue
        dimQn = resolvePrefixedName(dimAttr, dimElt.nsmap)
        if dimQn is None:
            continue
        if ln == "explicitMember":
            memQn = resolvePrefixedName((dimElt.text or "").strip(), dimElt.nsmap)
            if memQn is not None:
                dims[dimQn] = memQn
        elif ln == "typedMember":
            # typed value: use the concatenated text of the typed member content
            child = next((c for c in dimElt if isinstance(c.tag, str)), None)
            dims[dimQn] = (child.text or "").strip() if child is not None else (dimElt.text or "").strip()


def oimContextDimensions(ctxElt, rootNsmap=None):
    """Convert a single ``xbrli:context`` element to
    ``(entityQName, oimPeriodStr, {dimQName: memberValue})``.

    ``rootNsmap`` is used only to find a display prefix for the entity scheme URI;
    when omitted the context element's own in-scope namespaces are used (which, in
    lxml, already include the inherited root declarations)."""
    if rootNsmap is None:
        rootNsmap = ctxElt.nsmap
    entityQn = None
    ent = ctxElt.find(clark(XBRLI, "entity"))
    dims = {}
    if ent is not None:
        ident = ent.find(clark(XBRLI, "identifier"))
        if ident is not None and ident.text:
            scheme = ident.get("scheme")
            identifier = ident.text.strip()
            # entity value carried as a QName whose namespace is the scheme URI
            # (matching how OIM carries xbrl:entity as scheme:identifier).
            prefix = None
            for p, u in (rootNsmap or {}).items():
                if u == scheme:
                    prefix = p
                    break
            entityQn = QName(prefix, scheme, identifier)
        # explicit / typed members appear in segment and/or scenario
        for container in ("segment", "scenario"):
            cElt = ent.find(clark(XBRLI, container))
            if cElt is not None:
                parseDimensions(cElt, dims)
    perElt = ctxElt.find(clark(XBRLI, "period"))
    oimPer = oimPeriod(perElt) if perElt is not None else None
    return (entityQn, oimPer, dims)


def parseContexts(root):
    """Return {contextId: (entityQName, oimPeriodStr, {dimQName: memberValue})} for
    every ``xbrli:context`` in a flat XBRL 2.1 instance root."""
    contexts = {}
    for ctx in root.findall(clark(XBRLI, "context")):
        cid = ctx.get("id")
        if not cid:
            continue
        contexts[cid] = oimContextDimensions(ctx, root.nsmap)
    return contexts


def parseUnits(root, module):
    units = {}
    for unitElt in root.findall(clark(XBRLI, "unit")):
        uid = unitElt.get("id")
        if uid:
            units[uid] = oimUnit(unitElt, module)
    return units


# --------------------------------------------------------------------------
# Namespaces / fact identity
# --------------------------------------------------------------------------

def mergeInstanceNamespaces(module, nsmap) -> None:
    """Merge a source document's namespace declarations into the module's prefix
    map so that OIM unit strings and member QNames generated from the source (e.g.
    ``iso4217:USD``, ``utr:bbl``) resolve during fact validation.

    Only prefixes not already bound in the module are added; a prefix already bound
    to a *different* URI is left untouched (the module wins)."""
    prefixNs = getattr(module, "_prefixNamespaces", None)
    if prefixNs is None:
        return
    for prefix, ns in (nsmap or {}).items():
        if prefix is None or not ns:
            continue
        if prefix not in prefixNs:
            prefixNs[prefix] = ns


def factIdentity(module, factSource):
    """Resolve ``(factPrefix, factNs, redirect)`` for a fact source.

    ``factPrefix`` / ``factNs`` are the namespace prefix (from
    ``factSource.factIdentifierNamespacePrefix``, else the module's namespace) and
    its URI used for generated fact / factValue / footnote QNames. ``redirect`` is a
    QName -> QName function applying the fact source's ``namespaceMaps`` (an entry
    with no ``fromNamespacePrefix`` remaps every source namespace to its
    ``toNamespacePrefix`` namespace). Call after ``mergeInstanceNamespaces`` so the
    module prefix map is populated."""
    prefixNs = getattr(module, "_prefixNamespaces", {}) or {}
    factPrefix = getattr(factSource, "factIdentifierNamespacePrefix", None)
    if factPrefix:
        factNs = prefixNs.get(factPrefix)
    else:
        factNs = getattr(module, "_documentNamespaceURI", None)
        factPrefix = next((p for p, u in prefixNs.items() if u == factNs), None)

    nsRedirect = {}
    nsRedirectAll = None
    for nsMap in (getattr(factSource, "namespaceMaps", None) or ()):
        frm = prefixNs.get(getattr(nsMap, "fromNamespacePrefix", None))
        to = prefixNs.get(getattr(nsMap, "toNamespacePrefix", None))
        if to:
            if frm:
                nsRedirect[str(frm)] = str(to)
            elif getattr(nsMap, "fromNamespacePrefix", None) is None:
                nsRedirectAll = str(to)

    def redirect(qn: Optional[QName]) -> Optional[QName]:
        if qn is not None:
            if qn.namespaceURI in nsRedirect:
                return QName(qn.prefix, nsRedirect[qn.namespaceURI], qn.localName)
            if nsRedirectAll is not None and qn.namespaceURI != nsRedirectAll:
                return QName(qn.prefix, nsRedirectAll, qn.localName)
        return qn

    return factPrefix, factNs, redirect


# --------------------------------------------------------------------------
# Fact-level helpers
# --------------------------------------------------------------------------

def factLocalName(factElt, positionalId: str) -> str:
    """Derive the local part of the generated fact SQName per the fact map spec:
    the element ``@id`` (prefixed ``e.`` when it starts with a digit), else a
    caller-supplied positional id."""
    fid = factElt.get("id")
    if fid:
        return f"e.{fid}" if fid[0].isdigit() else fid
    return positionalId


def decimalsValue(elt) -> Optional[int]:
    """Decimals for a numeric fact: @decimals (INF -> None), else inferred from
    @precision, else None."""
    dec = elt.get("decimals")
    if dec is not None:
        dec = dec.strip()
        if dec in ("INF", "INFINITY"):
            return None
        try:
            return int(dec)
        except ValueError:
            return None
    prec = elt.get("precision")
    if prec is not None:
        prec = prec.strip()
        if prec in ("INF", "INFINITY"):
            return None
        # decimals cannot be inferred from precision without the value magnitude;
        # treat as infinitely precise (best-effort) rather than mis-report.
        return None
    return None
