"""
FormulaIterations.py - iteration expansion for the XBRL Query and Rules Language.

A query block evaluates once by default. A fact query in value position adds one
iteration per fact it selects, and a for loop adds one per value it binds; an
aggregating call collapses whatever is inside it back to a single value, so
``sum({@concept = x})`` is one iteration while a bare ``{@concept = x}`` is many.

The sources are found by walking the rule body once, before it is evaluated.
Each is stamped with an id, and the driver evaluates the body once per
combination of bindings, so the expression evaluator needs to know nothing
about iteration beyond reading the binding for its own node. Sources are bound
outermost-first, which lets an inner source's own expression see the bindings
of the ones outside it -- a nested for loop, or a fact query whose filter uses
the loop variable.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Function calls whose arguments are collapsed to one value. A fact query
# inside one of these does not iterate: it is the collection the function
# consumes. Names are matched without regard to case, as function names are.
AGGREGATING_FUNCTIONS = frozenset((
    "list", "set", "dict", "sum", "count", "max", "min", "avg", "average",
    "median", "mode", "stdev", "first", "last", "any", "all", "filter",
    "sort", "unique", "reverse",
))

# Keys whose sub-expressions are evaluated per candidate rather than per
# iteration, so an iteration source inside them belongs to that evaluation and
# not to the rule.
_PER_CANDIDATE_KEYS = frozenset((
    "fqWhere", "cond", "whereExpr", "stopExpr", "stopWhen",
))


class IterationSource:
    """One thing in a rule body that multiplies the rule's iterations."""

    __slots__ = ("iterId", "kind", "node", "inner")

    def __init__(self, iterId: int, kind: str, node: dict, inner: dict):
        self.iterId = iterId
        self.kind = kind          # "factQuery" | "forExpr"
        self.node = node          # the node the evaluator dispatches on
        self.inner = inner        # where this source's own fields live

    def __repr__(self):
        return f"<IterationSource {self.iterId} {self.kind}>"


def collectIterationSources(expr: Any) -> List[IterationSource]:
    """Return the iteration sources of a rule body, outermost first.

    Each source's node is stamped with ``_iterId`` so that the evaluator can
    find its binding without the two having to agree on identity any other way.
    """
    sources: List[IterationSource] = []
    _walk(expr, sources, inAggregate=False)
    return sources


def _walk(node: Any, sources: List[IterationSource], inAggregate: bool) -> None:
    if isinstance(node, (list, tuple)):
        for item in node:
            _walk(item, sources, inAggregate)
        return
    if not isinstance(node, dict):
        return

    # ---- a fact query in value position is a source ----
    if _isFactQuery(node):
        # A fully covered query has no alignment to iterate over: every fact it
        # selects falls in the one group, so it yields its whole collection
        # once, exactly as it does inside an aggregating call.
        if not inAggregate and not _isCovered(node):
            _stamp(node, "factQuery", sources, inner=node)
        # Its filters and where clause are evaluated per candidate fact, so
        # nothing inside it is a source of the rule's iterations.
        return

    # ---- a for loop in value position is a source ----
    forNode = _forNode(node)
    if forNode is not None:
        if not inAggregate:
            # Stamp the node the evaluator dispatches on, which may be an
            # envelope around the loop's own fields.
            _stamp(node, "forExpr", sources, inner=forNode)
        # The collection is what the loop consumes, so it never iterates the
        # rule; the body may hold further sources, nested inside this one.
        _walk(forNode.get("body"), sources, inAggregate)
        return

    # ---- a call collapses its arguments ----
    funcName = _funcName(node)
    childAggregate = inAggregate or (
        funcName is not None and funcName.lower() in AGGREGATING_FUNCTIONS
    )

    for key, value in node.items():
        if key in _PER_CANDIDATE_KEYS:
            continue
        _walk(value, sources, childAggregate)


def _stamp(node: dict, kind: str, sources: List[IterationSource], inner: dict) -> None:
    iterId = node.get("_iterId")
    if iterId is None:
        iterId = len(sources) + 1
        node["_iterId"] = iterId
    sources.append(IterationSource(iterId, kind, node, inner))


def _isCovered(node: dict) -> bool:
    """True when the query carries the `covered` modifier."""
    body = node.get("factQuery", node)
    if not isinstance(body, dict):
        return False
    for key in ("fqCurly", "fqSquare", "fqBare"):
        inner = body.get(key)
        if isinstance(inner, dict):
            body = inner
            break
    mods = body.get("modifiers")
    if isinstance(mods, dict):
        mods = mods.get("modifier", mods)
    if isinstance(mods, dict):
        mods = [mods]
    if not isinstance(mods, list):
        return False
    return any(
        (m.get("kw") if isinstance(m, dict) else str(m)) == "covered"
        for m in mods if m
    )


def _isFactQuery(node: dict) -> bool:
    if node.get("exprName") == "factQuery":
        return True
    inner = node.get("factQuery")
    return isinstance(inner, dict)


def _forNode(node: dict) -> Optional[dict]:
    if node.get("exprName") == "forExpr":
        return node
    inner = node.get("forExpr")
    return inner if isinstance(inner, dict) else None


def _funcName(node: dict) -> Optional[str]:
    call = node.get("funcCall")
    if isinstance(call, dict):
        name = call.get("funcName")
        if isinstance(name, str):
            return name
    if node.get("exprName") == "funcCall":
        name = node.get("funcName")
        if isinstance(name, str):
            return name
    return None


def alignmentsCompatible(a: Optional[frozenset], b: Optional[frozenset]) -> bool:
    """Two iterations combine when their alignments are equal.

    A value with no alignment -- a scalar, or a fully covered fact query --
    combines with anything without changing it.
    """
    if a is None or b is None:
        return True
    return a == b


def mergeAlignment(a: Optional[frozenset], b: Optional[frozenset]) -> Optional[frozenset]:
    return a if b is None else b if a is None else a
