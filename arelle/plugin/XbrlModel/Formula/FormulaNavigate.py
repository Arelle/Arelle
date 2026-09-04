"""
FormulaNavigate.py - model navigation for the Tavi Query and Rules Language.

Implements the `navigate` expression specified in
`oim/specifications/tavi-formula/tavi-formula.md`, section "Model Navigation".

Navigation traverses XbrlRelationship objects, which live in exactly one
*relationship container*: an XbrlNetwork (relationships of one declared
relationship type) or an XbrlDomainNetwork (relationships of the implicit type
xbrl:domain-member).  Everything else a navigate query names -- a group, a cube
-- selects containers rather than being traversed itself.  There is deliberately
no dimensional-navigation mode: a cube's structure is held in cube dimension
objects, which are properties, so `cube` scope resolves to the domain networks
those cube dimensions reference.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from arelle.ModelValue import QName, qname
from ordered_set import OrderedSet

from .FormulaValue import FormulaValue, FormulaValueType, NONE_VALUE


class FormulaNavigateError(Exception):
    """Raised for a malformed or unsatisfiable navigate query."""


# Relationships whose source is xbrl:rootSource anchor a network's roots.  They
# are an anchoring device rather than model content: the specification neither
# returns them nor counts them in navigation-depth.
def _rootSourceQn() -> QName:
    from XbrlModel.XbrlConst import qnXbrlRootSource
    return qnXbrlRootSource


def _domainMemberQn(mdl) -> QName:
    """The implicit relationship type QName of a domain network's relationships.

    xbrl:domain-member has no relationship type object in the built-in model, so
    it cannot be resolved through namedObjects; it is constructed against the
    model's own xbrl namespace so that it compares equal to a QName a rule wrote.
    """
    from XbrlModel.XbrlConst import xbrl
    return qname(xbrl, "xbrl:domain-member")


DIRECTIONS = frozenset((
    "descendants", "children", "ancestors", "parents",
    "siblings", "previous-siblings", "next-siblings", "self",
))


# ---------------------------------------------------------------------------
# Navigation result
# ---------------------------------------------------------------------------

class NavRelationship:
    """A relationship as reached by one traversal.

    The same XbrlRelationship can be reached by several paths and from several
    containers, and the return components depend on how it was reached, so the
    traversal context travels with the relationship rather than being looked up
    from it afterwards.
    """
    __slots__ = ("rel", "container", "cube", "cubeDimension",
                 "depth", "navOrder", "isStart", "isCycle", "resultOrder")

    def __init__(self, rel, container, cube=None, cubeDimension=None,
                 depth=0, navOrder=0, isStart=False, isCycle=False):
        self.rel = rel
        self.container = container
        self.cube = cube
        self.cubeDimension = cubeDimension
        self.depth = depth
        self.navOrder = navOrder
        self.isStart = isStart
        self.isCycle = isCycle
        self.resultOrder = 0
        self.resultOrder = 0

    @property
    def source(self):
        return None if self.isStart else getattr(self.rel, "source", None)

    @property
    def target(self):
        return getattr(self.rel, "target", None)

    def __repr__(self):
        return f"<NavRelationship {self.source}→{self.target} depth={self.depth}>"


class _StartRel:
    """The synthetic relationship produced by `include start`."""
    __slots__ = ("source", "target", "order", "properties")

    def __init__(self, target):
        self.source = None
        self.target = target
        self.order = Decimal(0)
        self.properties = None


# ---------------------------------------------------------------------------
# Container selection
# ---------------------------------------------------------------------------

def _asQNames(value: FormulaValue) -> List[QName]:
    """Flatten a scope argument to QNames, accepting an object, a QName, or a
    set/list of either."""
    out: List[QName] = []

    def add(v):
        if v is None:
            return
        if isinstance(v, FormulaValue):
            if v.type in (FormulaValueType.SET, FormulaValueType.LIST):
                for item in v.value:
                    add(item)
                return
            add(v.value)
            return
        if isinstance(v, QName):
            out.append(v)
            return
        nm = getattr(v, "name", None)
        if isinstance(nm, QName):
            out.append(nm)

    add(value)
    return out


def selectContainers(ctx, scopeKind: Optional[str], scopeValue: Optional[FormulaValue],
                     dimensionValue: Optional[FormulaValue], mdl) -> List[Tuple[Any, Any, Any]]:
    """Return the containers in scope as (container, cube, cubeDimension) triples.

    cube and cubeDimension are non-None only under `cube` scope, where they say
    how the container was reached so that the `cube` and `cubeDimension` return
    components can answer.
    """
    from XbrlModel.XbrlNetwork import XbrlNetwork
    from XbrlModel.XbrlDimension import XbrlDomainNetwork
    from XbrlModel.XbrlCube import XbrlCube

    if scopeKind is None:
        containers = [(o, None, None)
                      for o in mdl.filterNamedObjects(XbrlNetwork)]
        containers += [(o, None, None)
                       for o in mdl.filterNamedObjects(XbrlDomainNetwork)]
        return containers

    qns = _asQNames(scopeValue)

    if scopeKind == "network":
        return [(o, None, None) for o in
                (mdl.namedObjects.get(q) for q in qns)
                if isinstance(o, XbrlNetwork)]

    if scopeKind == "domain":
        return [(o, None, None) for o in
                (mdl.namedObjects.get(q) for q in qns)
                if isinstance(o, XbrlDomainNetwork)]

    if scopeKind == "group":
        wanted = set(qns)
        out = []
        for mod in getattr(mdl, "xbrlModels", {}).values():
            for gc in getattr(mod, "groupContents", ()) or ():
                if getattr(gc, "groupName", None) not in wanted:
                    continue
                obj = mdl.namedObjects.get(getattr(gc, "forObject", None))
                if isinstance(obj, (XbrlNetwork, XbrlDomainNetwork)):
                    out.append((obj, None, None))
        return out

    if scopeKind == "cube":
        dimQns = set(_asQNames(dimensionValue)) if dimensionValue is not None else None
        out = []
        for q in qns:
            cube = mdl.namedObjects.get(q)
            if not isinstance(cube, XbrlCube):
                continue
            for cd in getattr(cube, "cubeDimensions", ()) or ():
                if dimQns is not None and getattr(cd, "dimension", None) not in dimQns:
                    continue
                # A cube dimension with no domain network, or a typed one, holds
                # no hierarchy: the cube admits any member of the dimension's
                # domain class, so there is nothing to traverse.
                domQn = getattr(cd, "domainNetwork", None)
                if domQn is None:
                    continue
                dom = mdl.namedObjects.get(domQn)
                if isinstance(dom, XbrlDomainNetwork):
                    out.append((dom, cube, cd))
        return out

    raise FormulaNavigateError(f"Unknown navigation scope {scopeKind!r}")


def _containerRelationshipType(container, mdl) -> Optional[QName]:
    from XbrlModel.XbrlDimension import XbrlDomainNetwork
    if isinstance(container, XbrlDomainNetwork):
        return _domainMemberQn(mdl)
    return getattr(container, "relationshipTypeName", None)


def _relationshipTypeMatches(container, wanted: Optional[set], mdl) -> bool:
    if not wanted:
        return True
    rtn = _containerRelationshipType(container, mdl)
    if rtn is None:
        return False
    return rtn in wanted


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------

def _relsFrom(mdl, container) -> Dict[QName, List[Any]]:
    try:
        return mdl.effectiveRelationshipsFrom(container)
    except Exception:
        return getattr(container, "relationshipsFrom", {}) or {}


def _relsTo(mdl, container) -> Dict[QName, List[Any]]:
    rels = _effectiveRelationships(mdl, container)
    out: Dict[QName, List[Any]] = {}
    rootQn = _rootSourceQn()
    for rel in rels:
        if getattr(rel, "source", None) == rootQn:
            continue
        out.setdefault(getattr(rel, "target", None), []).append(rel)
    return out


def _effectiveRelationships(mdl, container):
    try:
        return list(mdl.effectiveRelationships(container))
    except Exception:
        return list(getattr(container, "relationships", ()) or ())


def _roots(mdl, container) -> List[QName]:
    from XbrlModel.XbrlDimension import XbrlDomainNetwork
    if isinstance(container, XbrlDomainNetwork):
        root = getattr(container, "root", None)
        if root is not None:
            return [root]
    try:
        return list(mdl.effectiveRelationshipRoots(container))
    except Exception:
        return list(getattr(container, "relationshipRoots", ()) or ())


def _ordered(rels: Iterable[Any]) -> List[Any]:
    """Order relationships by their `order` property, stable within equal orders.

    A relationship with no stated order defaults to 0, so unordered
    relationships keep the order they appear in.
    """
    indexed = list(enumerate(rels))
    def key(pair):
        i, rel = pair
        o = getattr(rel, "order", None)
        return (Decimal(o) if o is not None else Decimal(0), i)
    return [rel for _, rel in sorted(indexed, key=key)]


def _descend(mdl, container, cube, cubeDim, startQn, maxDepth,
             stopFn, acrossContainers, allContainers, results, visited, depth=1):
    rootQn = _rootSourceQn()
    relsFrom = _relsFrom(mdl, container)
    outgoing = [r for r in relsFrom.get(startQn, ()) if getattr(r, "source", None) != rootQn]
    if acrossContainers:
        for other, oCube, oCd in allContainers:
            if other is container:
                continue
            outgoing += [r for r in _relsFrom(mdl, other).get(startQn, ())
                         if getattr(r, "source", None) != rootQn]
    for navOrder, rel in enumerate(_ordered(outgoing), start=1):
        key = (id(container), id(rel), getattr(rel, "target", None))
        isCycle = key in visited
        nav = NavRelationship(rel, container, cube, cubeDim,
                              depth=depth, navOrder=navOrder, isCycle=isCycle)
        results.append(nav)
        if isCycle:
            continue
        if stopFn is not None and stopFn(nav):
            continue
        if maxDepth is not None and depth >= maxDepth:
            continue
        visited.add(key)
        _descend(mdl, container, cube, cubeDim, getattr(rel, "target", None),
                 maxDepth, stopFn, acrossContainers, allContainers,
                 results, visited, depth + 1)
        visited.discard(key)


def _ascend(mdl, container, cube, cubeDim, startQn, maxDepth,
            stopFn, acrossContainers, allContainers, results, visited, depth=1):
    relsTo = _relsTo(mdl, container)
    incoming = list(relsTo.get(startQn, ()))
    if acrossContainers:
        for other, oCube, oCd in allContainers:
            if other is container:
                continue
            incoming += list(_relsTo(mdl, other).get(startQn, ()))
    for navOrder, rel in enumerate(_ordered(incoming), start=1):
        key = (id(container), id(rel), getattr(rel, "source", None))
        isCycle = key in visited
        nav = NavRelationship(rel, container, cube, cubeDim,
                              depth=depth, navOrder=navOrder, isCycle=isCycle)
        results.append(nav)
        if isCycle:
            continue
        if stopFn is not None and stopFn(nav):
            continue
        if maxDepth is not None and depth >= maxDepth:
            continue
        visited.add(key)
        _ascend(mdl, container, cube, cubeDim, getattr(rel, "source", None),
                maxDepth, stopFn, acrossContainers, allContainers,
                results, visited, depth + 1)
        visited.discard(key)


def _siblings(mdl, container, cube, cubeDim, startQn, which, results):
    """Relationships sharing a parent with the relationships targeting startQn."""
    relsTo = _relsTo(mdl, container)
    relsFrom = _relsFrom(mdl, container)
    rootQn = _rootSourceQn()
    for parentRel in relsTo.get(startQn, ()):
        parentQn = getattr(parentRel, "source", None)
        sibs = _ordered([r for r in relsFrom.get(parentQn, ())
                         if getattr(r, "source", None) != rootQn])
        try:
            atIdx = next(i for i, r in enumerate(sibs)
                         if getattr(r, "target", None) == startQn)
        except StopIteration:
            continue
        if which == "previous-siblings":
            sibs = sibs[:atIdx]
        elif which == "next-siblings":
            sibs = sibs[atIdx + 1:]
        for navOrder, rel in enumerate(sibs, start=1):
            results.append(NavRelationship(rel, container, cube, cubeDim,
                                           depth=1, navOrder=navOrder))


def navigate(ctx, spec: Dict[str, Any]) -> List[NavRelationship]:
    """Run a navigate query and return the NavRelationships it reaches.

    `spec` carries the parsed clauses, with expression-valued clauses already
    evaluated by the interpreter.
    """
    mdl = spec.get("model") or ctx.txmyMdl
    direction = spec["direction"]
    if direction not in DIRECTIONS:
        raise FormulaNavigateError(f"Unknown navigation direction {direction!r}")

    wantedTypes = set(_asQNames(spec["relationshipType"])) if spec.get("relationshipType") is not None else None
    containers = selectContainers(ctx, spec.get("scopeKind"), spec.get("scopeValue"),
                                  spec.get("dimensionValue"), mdl)
    containers = [(c, cube, cd) for (c, cube, cd) in containers
                  if _relationshipTypeMatches(c, wantedTypes, mdl)]

    fromQns = _asQNames(spec["fromValue"]) if spec.get("fromValue") is not None else None
    toQns = set(_asQNames(spec["toValue"])) if spec.get("toValue") is not None else None
    maxDepth = spec.get("depth")
    stopFn = spec.get("stopFn")
    acrossContainers = bool(spec.get("acrossContainers"))
    includeStart = bool(spec.get("includeStart"))

    results: List[NavRelationship] = []
    for container, cube, cubeDim in containers:
        starts = fromQns if fromQns is not None else _roots(mdl, container)
        for startQn in starts:
            if startQn is None:
                continue
            if includeStart:
                results.append(NavRelationship(_StartRel(startQn), container, cube, cubeDim,
                                               depth=0, navOrder=0, isStart=True))
            if direction in ("descendants", "children"):
                _descend(mdl, container, cube, cubeDim, startQn,
                         1 if direction == "children" else maxDepth,
                         stopFn, acrossContainers, containers, results, set())
            elif direction in ("ancestors", "parents"):
                _ascend(mdl, container, cube, cubeDim, startQn,
                        1 if direction == "parents" else maxDepth,
                        stopFn, acrossContainers, containers, results, set())
            elif direction in ("siblings", "previous-siblings", "next-siblings"):
                _siblings(mdl, container, cube, cubeDim, startQn, direction, results)
            elif direction == "self":
                for rel in _relsTo(mdl, container).get(startQn, ()):
                    results.append(NavRelationship(rel, container, cube, cubeDim, depth=0))

    if toQns is not None:
        results = _prunePathsTo(results, toQns)

    for i, nav in enumerate(results, start=1):
        nav.resultOrder = i
    return results


def _prunePathsTo(results: List[NavRelationship], toQns: set) -> List[NavRelationship]:
    """Keep only relationships on a path that reaches one of `toQns`.

    Traversal is depth-first, so a relationship is on such a path when it is the
    reaching relationship itself or an ancestor of one -- that is, when a later
    result at a strictly greater depth reaches the target without the depth
    first dropping back to or below this relationship's own depth.
    """
    keep = [False] * len(results)
    for i, nav in enumerate(results):
        if nav.target in toQns:
            keep[i] = True
            depth = nav.depth
            for j in range(i - 1, -1, -1):
                if results[j].depth < depth:
                    keep[j] = True
                    depth = results[j].depth
                    if depth <= 0:
                        break
    return [nav for nav, k in zip(results, keep) if k]
