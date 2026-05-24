"""
FormulaInterpreter.py - AST evaluator for the XBRL Query and Rules Language.

This is the central engine of the formula plugin.  It walks the parsed AST
produced by FormulaParser and evaluates expressions against an XbrlModel
instance, driving iteration over aligned fact groups via the VectorSearch-
based FormulaAlignment module.

Key design
----------
1.  evaluateRuleSet(globalCtx)
    Top-level entry point.  Evaluates constants, then runs every output/assert
    rule in the rule set.

2.  evaluateRule(rule, globalCtx)
    Collects all fact-query slots in the rule body, builds the Cartesian
    product of aligned groups (via GPU-accelerated FormulaAlignment), then
    calls evaluateExpr for each iteration with variable bindings set.

3.  evaluateExpr(node, ruleCtx)
    Recursive expression evaluator.  Handles literals, operators, function
    calls, property accesses, variable references, fact queries, if/else,
    for-loops, collection literals, etc.

Alignment strategy
------------------
When the rule body contains N fact queries (@ConceptA, @ConceptB, …), the
interpreter:

  a. Calls globalCtx.factsForConcept() for each concept → N fact lists.
  b. Calls FormulaAlignment.alignedGroups() which uses VectorSearch batch
     matrix multiplies to find aligned K-tuples in O(N * D) GPU time.
  c. Iterates over each aligned K-tuple, binding each fact to its tag/index
     variable, evaluating the expression, and collecting results.

If the VectorSearch index is not available (no torch, no embedding built yet),
the interpreter falls back to FormulaAlignment.exactAlignedGroups() which is
exact but O(Σ N_k) using a hash index on AlignmentKey.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterator, List, Optional, Tuple, TYPE_CHECKING

from pyparsing import ParseResults

from arelle.ModelValue import QName

from .FormulaValue import (
    FormulaValue, FormulaValueType,
    FormulaRuntimeError, FormulaAlignmentError, FormulaIterationStop, FormulaSkip,
    NONE_VALUE, TRUE_VALUE, FALSE_VALUE, SKIP_VALUE,
)
from .FormulaContext import FormulaGlobalContext, FormulaRuleContext
from .FormulaFunctions import callFunction, BUILTIN_FUNCTIONS
from .FormulaProperties import getProperty
from .DateTimeSupport import (
    InstantValue,
    DateRangeValue,
    TimeSpanValue,
    format_excel_serial,
    format_instant,
    format_range,
)
try:
    from ordered_set import OrderedSet
except ImportError:
    OrderedSet = frozenset


if TYPE_CHECKING:
    from .FormulaRuleSet import FormulaRuleSet, OutputRule, AssertRule, ConstantDecl


# ---------------------------------------------------------------------------
# Top-level entry points
# ---------------------------------------------------------------------------

def evaluateRuleSet(globalCtx: FormulaGlobalContext) -> None:
    """
    Evaluate all constants, then all output/assert rules in the rule set.
    Results are collected into globalCtx.results and logged via the controller.
    """
    ruleSet = globalCtx.ruleSet

    # Evaluate constants in declaration order (they may depend on each other)
    for constDecl in ruleSet.constants:
        try:
            val = _evalConstant(constDecl, globalCtx)
            globalCtx.constants[constDecl.name] = val
        except Exception as exc:
            globalCtx.log("WARNING", f"formula:constant:{constDecl.name}",
                          f"Error evaluating constant ${constDecl.name}: {exc}")

    # Run rules
    for rule in ruleSet.allRules:
        try:
            evaluateRule(rule, globalCtx)
        except Exception as exc:
            globalCtx.log("ERROR", f"formula:rule:{rule.name}",
                          f"Unexpected error in rule {rule.name!r}: {exc}")


def evaluateRule(rule, globalCtx: FormulaGlobalContext) -> None:
    """
    Run a single output or assert rule, iterating over all aligned fact groups.
    """
    from .FormulaRuleSet import OutputRule, AssertRule

    # Collect fact-query slots from the rule body AST
    slots: List[_FactQuerySlot] = []
    _collectFactQueries(rule.expr, slots)

    if not slots:
        # No fact queries — evaluate the expression once, no alignment needed
        ruleCtx = FormulaRuleContext(globalCtx)
        _runRuleIteration(rule, ruleCtx, globalCtx, boundFacts=[])
        return

    # Gather fact lists for each slot
    factSets: List[List] = []
    for slot in slots:
        qn = globalCtx.resolveQName(slot.prefix, slot.localName)
        facts = globalCtx.factsForConcept(qn) if qn.namespaceURI else \
                _findFactsByLocalName(globalCtx, slot.localName)
        factSets.append(facts)

    # Align fact groups using VectorSearch (GPU) or exact fallback
    for factGroup in _alignedGroups(globalCtx, factSets):
        ruleCtx = FormulaRuleContext(globalCtx)
        _runRuleIteration(rule, ruleCtx, globalCtx, boundFacts=list(zip(slots, factGroup)))


# ---------------------------------------------------------------------------
# Fact slot collector (walks AST to find all @concept nodes)
# ---------------------------------------------------------------------------

class _FactQuerySlot:
    __slots__ = ("prefix", "localName", "tag", "filters", "nilsFlag", "coveredFlag")
    def __init__(self, prefix, localName, tag=None, filters=None, nilsFlag=None, coveredFlag=None):
        self.prefix       = prefix or "*"
        self.localName    = localName
        self.tag          = tag
        self.filters      = filters or []
        self.nilsFlag     = nilsFlag
        self.coveredFlag  = coveredFlag


def _collectFactQueries(node: Any, slots: List[_FactQuerySlot]) -> None:
    """
    Walk the AST and collect factQuery nodes that should drive rule iteration.

    In the new spec-aligned factQuery grammar, queries are evaluated inline
    as collections (LIST of FACT) and do not drive alignment iteration.
    This collector therefore returns no slots for the new shape; the rule
    body is evaluated once and each factQuery returns its full result set.
    Kept for backward compatibility with any legacy AST shape that may have
    surfaced a `concept` field directly under `factQuery`.
    """
    if not isinstance(node, dict):
        return
    if node.get("exprName") == "factQuery" or "factQuery" in node:
        fqNode = node.get("factQuery", node)
        # New shape: fqCurly / fqSquare / fqBare wrappers → do NOT add slot.
        if isinstance(fqNode, dict) and any(
            k in fqNode for k in ("fqCurly", "fqSquare", "fqBare")
        ):
            return
        # Legacy shape (no longer produced by the grammar): preserve behavior.
        concept = fqNode.get("concept", {}) if isinstance(fqNode, dict) else {}
        slot = _FactQuerySlot(
            prefix=concept.get("prefix", "*"),
            localName=concept.get("localName", ""),
            tag=fqNode.get("tag"),
            filters=fqNode.get("filters", []),
            nilsFlag=fqNode.get("nilsFlag"),
            coveredFlag=fqNode.get("coveredFlag"),
        )
        if slot.localName:
            slots.append(slot)
        return
    for val in node.values():
        if isinstance(val, dict):
            _collectFactQueries(val, slots)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _collectFactQueries(item, slots)


# ---------------------------------------------------------------------------
# Aligned groups selection
# ---------------------------------------------------------------------------

def _alignedGroups(globalCtx: FormulaGlobalContext, factSets: List[List]) -> Iterator[List]:
    """
    Yield aligned K-tuples of facts.

    Tries the GPU-accelerated VectorSearch approach first; falls back to
    exact alignment if VectorSearch is unavailable.
    """
    if not any(factSets):
        return   # at least one slot has no facts → no iterations

    try:
        from .FormulaAlignment import alignedGroups, exactAlignedGroups
        try:
            import torch
            yield from alignedGroups(globalCtx.txmyMdl, factSets)
        except (ImportError, AttributeError):
            yield from exactAlignedGroups(factSets)
    except Exception as exc:
        globalCtx.log("WARNING", "formula:alignment",
                      f"Alignment error, falling back to exact: {exc}")
        from .FormulaAlignment import exactAlignedGroups
        yield from exactAlignedGroups(factSets)


def _findFactsByLocalName(globalCtx: FormulaGlobalContext, localName: str) -> List:
    """
    Wildcard concept lookup: find all facts whose concept QName has the
    given localName in any namespace.
    """
    from XbrlModel.XbrlFact import XbrlFact
    from XbrlModel.XbrlCube import conceptCoreDim as conceptDimQn
    from arelle.XmlValidateConst import VALID

    return [
        obj for obj in globalCtx.txmyMdl.filterNamedObjects(XbrlFact)
        if (getattr(obj, "_xValid", VALID) >= VALID
            and isinstance(obj.factDimensions.get(conceptDimQn), QName)
            and obj.factDimensions[conceptDimQn].localName == localName)
    ]


# ---------------------------------------------------------------------------
# Per-iteration runner
# ---------------------------------------------------------------------------

def _runRuleIteration(rule, ruleCtx: FormulaRuleContext,
                      globalCtx: FormulaGlobalContext,
                      boundFacts: List[Tuple]) -> None:
    """
    Bind fact variables into ruleCtx, evaluate the rule expression, then
    emit an output/assertion result.
    """
    from .FormulaRuleSet import OutputRule, AssertRule

    # Bind facts to their slot tags and set alignment
    for slot, fact in boundFacts:
        factVal = FormulaValue.fromFact(fact)
        # Merge alignment
        if ruleCtx.alignment is None:
            ruleCtx.alignment = factVal.alignment
        elif factVal.alignment is not None and factVal.alignment != ruleCtx.alignment:
            # Misaligned — skip this iteration silently
            return
        # Bind by tag if provided
        if slot.tag:
            ruleCtx.bindVariable(slot.tag, factVal)

    # Evaluate the rule body expression
    try:
        result = evaluateExpr(rule.expr, ruleCtx)
    except FormulaIterationStop:
        return
    except FormulaSkip:
        return
    except FormulaRuntimeError as exc:
        globalCtx.log("WARNING", f"formula:eval:{rule.name}",
                      f"Runtime error in rule {rule.name!r}: {exc}")
        return

    if result.isSkip:
        return

    ruleCtx.ruleValue = result

    # Build the message string
    message = _buildMessage(rule, result, ruleCtx)

    # Emit result
    if isinstance(rule, AssertRule):
        # Assert: fire message when condition is FALSE
        passed = _isTruthy(result)
        if not passed:
            globalCtx.addResult(
                ruleName=rule.name,
                ruleType="assert",
                severity=rule.severity or "error",
                message=message,
                alignment=ruleCtx.alignment,
                factObj=boundFacts[0][1] if boundFacts else None,
            )
    else:
        # Output: always emit
        globalCtx.addResult(
            ruleName=rule.name,
            ruleType="output",
            severity=rule.severity or "info",
            message=message,
            alignment=ruleCtx.alignment,
            factObj=boundFacts[0][1] if boundFacts else None,
        )


# ---------------------------------------------------------------------------
# Constant evaluator
# ---------------------------------------------------------------------------

def _evalConstant(constDecl, globalCtx: FormulaGlobalContext) -> FormulaValue:
    if isinstance(constDecl.expr, dict) and constDecl.expr.get("exprName") == "funcDecl":
        # User-defined function: wrap as a callable stored in a FormulaValue
        funcNode = constDecl.expr
        params = [p.get("paramName") for p in funcNode.get("params", [])]
        bodyNode = funcNode.get("body")

        def userFunc(args: List[FormulaValue], ctx: FormulaRuleContext) -> FormulaValue:
            childCtx = ctx.childContext()
            for name, val in zip(params, args):
                childCtx.bindVariable(name, val)
            return evaluateExpr(bodyNode, childCtx)

        return FormulaValue(FormulaValueType.NONE, userFunc)

    # Regular constant: evaluate the expression in a minimal context
    ruleCtx = FormulaRuleContext(globalCtx)
    return evaluateExpr(constDecl.expr, ruleCtx)


# ---------------------------------------------------------------------------
# Expression evaluator
# ---------------------------------------------------------------------------

def evaluateExpr(node: Any, ctx: FormulaRuleContext) -> FormulaValue:
    """
    Recursively evaluate an AST node and return a FormulaValue.
    """
    if node is None:
        return NONE_VALUE

    # ---- Python scalar literals (produced directly by pyparsing) ----
    if isinstance(node, bool):
        return TRUE_VALUE if node else FALSE_VALUE
    if isinstance(node, ParseResults):
        if "base" in node or "props" in node:
            baseNode = None
            for namedKey in (
                "funcCall", "varRef", "factQuery", "ifExpr", "forExpr",
                "setLiteral", "listLiteral", "boolean", "none", "skip",
                "severity", "string", "qname",
            ):
                if namedKey in node:
                    baseNode = {namedKey: node.get(namedKey)}
                    break

            if baseNode is None:
                baseNode = node.get("base")
            if isinstance(baseNode, ParseResults) and len(baseNode) == 1:
                baseNode = baseNode[0]
            if isinstance(baseNode, ParseResults) and "value" in baseNode and len(baseNode) == 1:
                token = str(baseNode.get("value", "")).lower()
                if token == "none":
                    baseNode = {"none": {"value": "none"}}
                elif token == "skip":
                    baseNode = {"skip": {"value": "skip"}}
                elif token in ("true", "false"):
                    baseNode = {"boolean": {"value": token}}
            elif isinstance(baseNode, list) and len(baseNode) == 1:
                baseNode = baseNode[0]
            rawProps = node.get("props", [])
            if isinstance(rawProps, ParseResults):
                propsList = list(rawProps)
            elif isinstance(rawProps, dict):
                propsList = [rawProps]
            else:
                propsList = list(rawProps) if rawProps else []
            return _evalAtomWithProps({"base": baseNode, "props": propsList}, ctx)

        if len(node) == 1:
            return evaluateExpr(node[0], ctx)

        if len(node) == 2 and not node.keys():
            return evaluateExpr(node[0], ctx)

    if isinstance(node, int):
        return FormulaValue(FormulaValueType.INTEGER, node)
    if isinstance(node, float):
        return FormulaValue(FormulaValueType.FLOAT, node)
    if isinstance(node, Decimal):
        return FormulaValue(FormulaValueType.DECIMAL, node)
    if isinstance(node, str):
        return FormulaValue(FormulaValueType.STRING, node)

    if not isinstance(node, dict):
        return FormulaValue.fromScalar(node)

    exprName = node.get("exprName", "")

    # ---- Literals ----
    if exprName == "integer" or "integer" in node:
        inner = node.get("integer", node)
        return FormulaValue(FormulaValueType.INTEGER, int(inner.get("value", 0)))

    if exprName == "float" or "float" in node:
        inner = node.get("float", node)
        try:
            return FormulaValue(FormulaValueType.FLOAT, float(inner.get("value", 0)))
        except (ValueError, TypeError):
            return FormulaValue(FormulaValueType.FLOAT, 0.0)

    if exprName == "boolean" or "boolean" in node:
        inner = node.get("boolean", node)
        val = str(inner.get("value", "false")).lower() == "true"
        return TRUE_VALUE if val else FALSE_VALUE

    if exprName == "none" or "none" in node:
        return NONE_VALUE

    if exprName == "skip" or "skip" in node:
        return SKIP_VALUE

    if exprName == "severity" or "severity" in node:
        inner = node.get("severity", node)
        return FormulaValue(FormulaValueType.SEVERITY, inner.get("value", "error"))

    if exprName == "string" or "string" in node:
        return _evalString(node.get("string", node), ctx)

    # ---- QName literal (bare identifier used as qname) ----
    if exprName == "qname" or "qname" in node:
        return _evalQName(node.get("qname", node), ctx)

    # ---- Variable reference ----
    if exprName == "varRef" or "varRef" in node:
        inner = node.get("varRef", node)
        return ctx.lookupVariable(inner.get("varName", ""))

    # ---- Fact query ----
    if exprName == "factQuery" or "factQuery" in node:
        return _evalFactQuery(node.get("factQuery", node), ctx)

    # ---- Atom with property chain ----
    if exprName == "atomWithProps" or "atomWithProps" in node:
        return _evalAtomWithProps(node.get("atomWithProps", node), ctx)

    # ---- Function call ----
    if exprName == "funcCall" or "funcCall" in node:
        return _evalFuncCall(node.get("funcCall", node), ctx)

    # ---- Binary expression ----
    if exprName == "binaryExpr" or "binaryExpr" in node:
        return _evalBinary(node.get("binaryExpr", node), ctx)

    # ---- Unary expression ----
    if exprName == "unaryExpr" or "unaryExpr" in node:
        return _evalUnary(node.get("unaryExpr", node), ctx)

    # ---- If-then-else ----
    if exprName == "ifExpr" or "ifExpr" in node:
        return _evalIf(node.get("ifExpr", node), ctx)

    # ---- For loop ----
    if exprName == "forExpr" or "forExpr" in node:
        return _evalFor(node.get("forExpr", node), ctx)

    # ---- Assignment / block expression ----
    if exprName == "assignExpr" or "assignExpr" in node:
        return _evalAssign(node.get("assignExpr", node), ctx)
    if exprName == "blockExpr" or "blockExpr" in node:
        return _evalBlockExpr(node.get("blockExpr", node), ctx)

    # ---- Set / list literals ----
    if exprName == "setLiteral" or "setLiteral" in node:
        return _evalSetLiteral(node.get("setLiteral", node), ctx)
    if exprName == "listLiteral" or "listLiteral" in node:
        return _evalListLiteral(node.get("listLiteral", node), ctx)

    # ---- Passthrough for nested dicts (e.g. from infix_notation) ----
    if "leftExpr" in node and "rightExpr" in node:
        return _evalBinary(node, ctx)

    # ---- Unknown / passthrough ----
    return NONE_VALUE


# ---------------------------------------------------------------------------
# String expression evaluator (handles interpolations)
# ---------------------------------------------------------------------------

def _evalString(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    """
    Build a string value from a parsed string node.

    String parts can be:
      - 'text':  plain string segment
      - 'escape': escaped character (\\n, \\\\ etc.)
      - 'interp': embedded expression inside { }
    """
    parts_node = node.get("stringParts") or node.get("parts") or []
    segments: List[str] = []
    for part in parts_node:
        if not isinstance(part, dict):
            segments.append(_stringText(part))
            continue
        ptype = next(iter(part), None)
        inner = part.get(ptype, part)
        if ptype == "text":
            segments.append(_stringText(inner))
        elif ptype == "escape":
            ch = _stringText(inner)
            segments.append(_unescape(ch))
        elif ptype == "interp":
            val = evaluateExpr(inner, ctx)
            segments.append(_formatValue(val))
        else:
            segments.append(_stringText(inner))
    return FormulaValue(FormulaValueType.STRING, "".join(segments))


def _stringText(value: Any) -> str:
    """Convert parser-produced string fragments into plain text."""
    if isinstance(value, ParseResults):
        if "value" in value:
            return _stringText(value.get("value"))
        if "text" in value:
            return _stringText(value.get("text"))
        value = value.as_list()

    if isinstance(value, dict):
        if "value" in value:
            return _stringText(value["value"])
        if "text" in value:
            return _stringText(value["text"])
        return "".join(_stringText(v) for v in value.values())

    if isinstance(value, (list, tuple)):
        if len(value) == 1:
            return _stringText(value[0])
        return "".join(_stringText(v) for v in value)

    return "" if value is None else str(value)


def _unescape(ch: str) -> str:
    escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "{": "{", "}": "}"}
    return escapes.get(ch, ch)


def _itemSortKey(val: FormulaValue) -> tuple:
    """Create a sort key for a FormulaValue to enable consistent set ordering."""
    # Sort by type first, then by value
    type_order = {
        FormulaValueType.NONE: 0,
        FormulaValueType.BOOLEAN: 1,
        FormulaValueType.INTEGER: 2,
        FormulaValueType.FLOAT: 2,
        FormulaValueType.DECIMAL: 2,
        FormulaValueType.STRING: 3,
        FormulaValueType.QNAME: 4,
        FormulaValueType.DATE: 5,
        FormulaValueType.DURATION: 6,
    }
    type_idx = type_order.get(val.type, 99)
    
    if val.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL):
        return (type_idx, float(val.value) if val.value is not None else float('inf'))
    elif val.type == FormulaValueType.STRING:
        return (type_idx, str(val.value))
    elif val.type == FormulaValueType.BOOLEAN:
        return (type_idx, int(bool(val.value)))
    else:
        return (type_idx, str(val.value))


def _formatCollectionItem(val: FormulaValue) -> str:
    if val.type == FormulaValueType.NONE:
        return "None"
    if val.type == FormulaValueType.DATE and isinstance(val.value, InstantValue):
        return format_instant(val.value)
    if val.type == FormulaValueType.DURATION and isinstance(val.value, DateRangeValue):
        return format_range(val.value)
    return _formatValue(val)


def _formatValue(val: FormulaValue) -> str:
    if val.type == FormulaValueType.FACT:
        if val.value.factValues:
            fv = next(iter(val.value.factValues))
            return str(fv.value) if fv.value is not None else ""
        return ""
    if val.type == FormulaValueType.NONE:
        return "none"
    if val.type == FormulaValueType.SKIP:
        return "skip"
    if val.type == FormulaValueType.BOOLEAN:
        return "true" if bool(val.value) else "false"
    if val.type == FormulaValueType.LIST:
        items = [_formatCollectionItem(v if isinstance(v, FormulaValue) else FormulaValue(FormulaValueType.STRING, v)) for v in val.value]
        return f"list({', '.join(items)})"
    if val.type == FormulaValueType.SET:
        # Display in insertion order, but None elements come last
        items_list = list(val.value)
        non_none = [v for v in items_list if not (isinstance(v, FormulaValue) and v.type == FormulaValueType.NONE)]
        none_items = [v for v in items_list if isinstance(v, FormulaValue) and v.type == FormulaValueType.NONE]
        ordered = non_none + none_items
        items = [_formatCollectionItem(v if isinstance(v, FormulaValue) else FormulaValue(FormulaValueType.STRING, v)) for v in ordered]
        return f"set({', '.join(items)})"
    if val.type == FormulaValueType.DICT:
        parts = []
        for k, v in val.value.items():
            keyText = _formatCollectionItem(k if isinstance(k, FormulaValue) else FormulaValue.fromScalar(k))
            valText = _formatCollectionItem(v if isinstance(v, FormulaValue) else FormulaValue.fromScalar(v))
            parts.append(f"{keyText}={valText}")
        return f"dictionary({','.join(parts)})"
    if val.type == FormulaValueType.DATE and isinstance(val.value, InstantValue):
        return format_instant(val.value)
    if val.type == FormulaValueType.DURATION:
        if isinstance(val.value, DateRangeValue):
            return format_range(val.value)
        if isinstance(val.value, TimeSpanValue):
            return str(val.value.delta)
    if val.type == FormulaValueType.DECIMAL and isinstance(val.value, Decimal):
        if val.value.is_nan():
            return "nan"
    return str(val.value)


# ---------------------------------------------------------------------------
# QName evaluation
# ---------------------------------------------------------------------------

def _evalQName(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    prefix    = node.get("prefix", "*")
    localName = node.get("localName", "")
    if localName == "forever":
        return callFunction("forever", [], ctx)
    if localName.startswith("forever."):
        value = callFunction("forever", [], ctx)
        for propName in localName.split(".")[1:]:
            value = getProperty(value, propName, [], ctx)
        return value
    if "." in localName:
        head, *props = localName.split(".")
        try:
            qn = ctx.globalCtx.resolveQName(prefix, head)
            value = FormulaValue(FormulaValueType.QNAME, qn)
        except KeyError:
            from arelle.ModelValue import qname as mkQn
            value = FormulaValue(FormulaValueType.QNAME, mkQn("", head))
        for propName in props:
            value = getProperty(value, propName, [], ctx)
        return value
    try:
        qn = ctx.globalCtx.resolveQName(prefix, localName)
        return FormulaValue(FormulaValueType.QNAME, qn)
    except KeyError:
        # Unknown prefix — return as bare qname
        from arelle.ModelValue import qname as mkQn
        return FormulaValue(FormulaValueType.QNAME, mkQn("", localName))


# ---------------------------------------------------------------------------
# Fact query evaluator
# ---------------------------------------------------------------------------

def _evalFactQuery(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    """
    Evaluate a factQuery node (spec-aligned grammar) and return a FormulaValue.

    The AST shape is::

        node == {"fqCurly"|"fqSquare"|"fqBare": {
            "modifiers": [{"kw": "covered"|"covered-dims"|"nils"|"nonils"|...}, ...],
            "filters":   [{"atSign": "@"|"@@",
                           "dimName": {"qname": {...}, "propChain": [...]},
                           "op": "="|"!="|"in"|"not in",
                           "value": <expr>|"*",
                           "wildcard": "*",  # if value was '*'
                           "alias": {"aliasName": str}}, ...],
            "fqWhere":   {"cond": <expr>},  # optional
        }}

    Bracket semantics (per formula.md "Square and Curly Bracket Control"):
      - {} / bare : taxonomy-defined dimensions allowed (default).
      - []        : only facts with NO taxonomy-defined dimensions
                    other than those explicitly named in filters.

    Returns a LIST FormulaValue of FACT values (possibly empty).
    """
    # Unwrap bracket form
    body = None
    bracket = None
    for k in ("fqCurly", "fqSquare", "fqBare"):
        if k in node:
            body = node[k]
            bracket = k
            break
    if body is None:
        # Legacy shape — degrade to empty list to avoid crashing.
        return FormulaValue(FormulaValueType.LIST, [])

    excludeTaxDims = (bracket == "fqSquare")

    # ---- Parse modifiers ----
    modifiersRaw = body.get("modifiers", [])
    if isinstance(modifiersRaw, dict):
        modifiersRaw = modifiersRaw.get("modifier", [])
    if isinstance(modifiersRaw, dict):
        modifiersRaw = [modifiersRaw]
    elif not isinstance(modifiersRaw, list):
        modifiersRaw = []
    modKws = {
        (m.get("kw") if isinstance(m, dict) else str(m)).lower()
        for m in modifiersRaw if m
    }
    # covered / covered-dims / uncovered are alignment hints — single-instance
    # interpreter currently returns the full collection unconditionally.
    nilsMode = None
    if "nils" in modKws:        nilsMode = "nils"
    elif "nonils" in modKws:    nilsMode = "nonils"
    elif "nildefault" in modKws: nilsMode = "nildefault"

    # ---- Parse filters ----
    filtersRaw = body.get("filters", [])
    if isinstance(filtersRaw, dict):
        filtersRaw = filtersRaw.get("dimFilter", [])
    if isinstance(filtersRaw, dict):
        filtersRaw = [filtersRaw]
    elif not isinstance(filtersRaw, list):
        filtersRaw = []

    parsedFilters = [_parseDimFilter(f, ctx) for f in filtersRaw if isinstance(f, dict)]
    namedDims = {pf["dimQn"] for pf in parsedFilters if pf.get("dimQn") is not None}

    # ---- Fact source: concept-indexed shortcut when a concept filter is present ----
    from XbrlModel.XbrlFact import XbrlFact
    from XbrlModel.XbrlCube import conceptCoreDim as conceptDimQn

    conceptFilter = next(
        (pf for pf in parsedFilters
         if pf.get("kind") == "concept" and pf.get("op") in ("=", "==") and pf.get("isQName")),
        None,
    )

    if conceptFilter is not None:
        conceptQn = conceptFilter["expected"]
        if isinstance(conceptQn, QName):
            seedFacts = ctx.globalCtx.factsForConcept(conceptQn)
        else:
            seedFacts = []
    else:
        # Full scan of all non-footnote facts.
        seedFacts = [
            f for f in ctx.globalCtx.txmyMdl.filterNamedObjects(XbrlFact)
            if getattr(f, "factDimensions", None)
        ]

    # ---- Apply filters ----
    matched: List[Any] = []
    whereCond = body.get("fqWhere", {}).get("cond") if isinstance(body.get("fqWhere"), dict) else None

    for fact in seedFacts:
        # Exclude footnote facts (concept name 'note' per spec)
        conceptVal = fact.factDimensions.get(conceptDimQn)
        if isinstance(conceptVal, QName) and conceptVal.localName == "note":
            continue

        # Nils handling
        if nilsMode == "nonils" and _isNil(fact):
            continue
        if nilsMode == "nils" and not _isNil(fact):
            continue

        # Apply dimension filters
        ok = True
        aliasBindings: Dict[str, Any] = {}
        for pf in parsedFilters:
            if not _factMatchesFilter(fact, pf, ctx):
                ok = False
                break
            alias = pf.get("alias")
            if alias and pf.get("dimQn") is not None:
                aliasBindings[alias] = fact.factDimensions.get(pf["dimQn"])
        if not ok:
            continue

        # Square-bracket exclusion: reject facts carrying taxonomy-defined
        # dimensions that were not explicitly named in filters.
        if excludeTaxDims:
            hasUnnamedTaxDim = any(
                (dimQn not in namedDims) and not _isCoreDimQn(dimQn)
                for dimQn in fact.factDimensions
            )
            if hasUnnamedTaxDim:
                continue

        # Where clause (evaluate with $fact + aliases bound)
        if whereCond is not None:
            savedFact = ctx.variables.get("fact")
            savedAliases = {k: ctx.variables.get(k) for k in aliasBindings}
            ctx.bindVariable("fact", FormulaValue.fromFact(fact))
            for k, v in aliasBindings.items():
                ctx.bindVariable(k, FormulaValue.fromScalar(v))
            try:
                cond = evaluateExpr(whereCond, ctx)
            except (FormulaIterationStop, FormulaSkip):
                cond = FALSE_VALUE
            finally:
                if savedFact is None:
                    ctx.variables.pop("fact", None)
                else:
                    ctx.variables["fact"] = savedFact
                for k, v in savedAliases.items():
                    if v is None:
                        ctx.variables.pop(k, None)
                    else:
                        ctx.variables[k] = v
            if not (cond.type == FormulaValueType.BOOLEAN and cond.value):
                continue

        matched.append(fact)

    return FormulaValue(
        FormulaValueType.LIST,
        [FormulaValue.fromFact(f) for f in matched],
    )


# ---- Core dim QNames (formula.md "core dimensions") -----------------------

_CORE_DIM_LOCALS = frozenset((
    "concept", "period", "entity", "unit", "language", "noteId",
))
_CORE_DIM_NS = "https://xbrl.org/2025"

def _isCoreDimQn(qn) -> bool:
    if not isinstance(qn, QName):
        return False
    return qn.namespaceURI == _CORE_DIM_NS and qn.localName in _CORE_DIM_LOCALS


_coreDimQnCache: Dict[str, QName] = {}

def _coreDimQn(localName: str) -> QName:
    qn = _coreDimQnCache.get(localName)
    if qn is None:
        from arelle.ModelValue import qname as mkQn
        qn = mkQn(_CORE_DIM_NS, localName)
        _coreDimQnCache[localName] = qn
    return qn


# ---- dimFilter parsing -----------------------------------------------------

# Special pseudo-dimension names (not core, but recognised in filters)
_PSEUDO_DIMS = frozenset(("cube", "model", "dimensions", "language"))


def _parseDimFilter(filt: dict, ctx: FormulaRuleContext) -> dict:
    """
    Convert a raw dimFilter AST node into a normalized dict::

        {"kind": "concept"|"core"|"taxDim"|"pseudo"|"any",
         "dimQn": QName|None,         # actual dim QName (None for @ alone)
         "atSign": "@"|"@@",
         "propChain": [str, ...],     # e.g. ['balance'] for @concept.balance
         "op": "="|"!="|"in"|"not in"|None,
         "value": <FormulaValue>|None,
         "expected": <raw value>,     # unwrapped value for fast compare
         "isWildcard": bool,
         "isNone": bool,
         "isQName": bool,
         "alias": str|None}
    """
    out = {
        "atSign":     filt.get("atSign", "@"),
        "kind":       "any",
        "dimQn":      None,
        "propChain":  [],
        "op":         None,
        "value":      None,
        "expected":   None,
        "isWildcard": False,
        "isNone":     False,
        "isQName":    False,
        "alias":      None,
    }

    # ---- Dimension name + property chain ----
    dimName = filt.get("dimName")
    if isinstance(dimName, dict):
        qnNode = dimName.get("qname", {})
        prefix = qnNode.get("prefix", "*") if isinstance(qnNode, dict) else "*"
        localName = qnNode.get("localName", "") if isinstance(qnNode, dict) else str(qnNode)
        propChainRaw = dimName.get("propChain", [])
        if isinstance(propChainRaw, dict):
            propChainRaw = [propChainRaw]
        elif not isinstance(propChainRaw, list):
            propChainRaw = []
        propChain = [p.get("propName") for p in propChainRaw
                     if isinstance(p, dict) and p.get("propName")]
        out["propChain"] = propChain

        # Classify the dim
        if prefix in ("*", None) and localName == "concept":
            out["kind"] = "concept"
            out["dimQn"] = _coreDimQn("concept")
        elif prefix in ("*", None) and localName == "period":
            out["kind"] = "core"
            out["dimQn"] = _coreDimQn("period")
        elif prefix in ("*", None) and localName == "entity":
            out["kind"] = "core"
            out["dimQn"] = _coreDimQn("entity")
        elif prefix in ("*", None) and localName == "unit":
            out["kind"] = "core"
            out["dimQn"] = _coreDimQn("unit")
        elif prefix in ("*", None) and localName == "language":
            out["kind"] = "core"
            out["dimQn"] = _coreDimQn("language")
        elif prefix in ("*", None) and localName in _PSEUDO_DIMS:
            out["kind"] = "pseudo"
            out["pseudoName"] = localName
        else:
            # Either a typed core dim with propChain, or a taxonomy-defined dim
            try:
                qn = ctx.globalCtx.resolveQName(prefix, localName)
            except KeyError:
                from arelle.ModelValue import qname as mkQn
                qn = mkQn("", localName)
            out["dimQn"] = qn
            if _isCoreDimQn(qn):
                out["kind"] = "core"
            else:
                # Treat as shortcut: @QName  ==>  @concept = QName
                if not filt.get("op") and not propChain:
                    out["kind"]     = "concept"
                    out["dimQn"]    = _coreDimQn("concept")
                    out["op"]       = "="
                    out["value"]    = FormulaValue(FormulaValueType.QNAME, qn)
                    out["expected"] = qn
                    out["isQName"]  = True
                else:
                    out["kind"] = "taxDim"
    else:
        # @ alone — match every fact, no constraint
        out["kind"] = "any"

    # ---- Operator + value ----
    if out["value"] is None and filt.get("op"):
        out["op"] = filt.get("op")
        if filt.get("wildcard") == "*":
            out["isWildcard"] = True
        else:
            valNode = filt.get("value")
            if valNode is not None:
                fv = evaluateExpr(valNode, ctx)
                out["value"] = fv
                if fv.type == FormulaValueType.NONE:
                    out["isNone"] = True
                elif fv.type == FormulaValueType.QNAME:
                    out["expected"] = fv.value
                    out["isQName"] = True
                else:
                    out["expected"] = fv.value

    # ---- Alias ----
    aliasNode = filt.get("alias")
    if isinstance(aliasNode, dict):
        out["alias"] = aliasNode.get("aliasName")

    return out


def _factMatchesFilter(fact, pf: dict, ctx: FormulaRuleContext) -> bool:
    """Test a single fact against a parsed dimFilter."""
    kind = pf["kind"]

    # @ alone — accept any fact
    if kind == "any":
        return True

    # @model — instance filter; single-instance interpreter treats as no-op
    # (any non-* value is accepted as the current model).
    if kind == "pseudo" and pf.get("pseudoName") == "model":
        return True

    # @cube — fact must appear in some cube; @cube.name / @cube.drs-role refine
    if kind == "pseudo" and pf.get("pseudoName") == "cube":
        return _factMatchesCubeFilter(fact, pf, ctx)

    # @dimensions — taxonomy-defined dim dictionary filter (not yet impl)
    if kind == "pseudo" and pf.get("pseudoName") == "dimensions":
        return _factMatchesDimsFilter(fact, pf, ctx)

    dimQn = pf.get("dimQn")
    if dimQn is None:
        return True
    factDimVal = fact.factDimensions.get(dimQn)

    # Optional property chain: e.g. @concept.balance — resolve fact's dim value
    # to the object (concept) then apply property chain.
    if pf["propChain"]:
        # Wrap the fact's dim value into a FormulaValue of the appropriate
        # type so that property dispatch (getProperty) works correctly.
        target = factDimVal
        if target is None:
            return False
        if dimQn.localName == "concept" and isinstance(factDimVal, QName):
            obj = ctx.globalCtx.txmyMdl.namedObjects.get(factDimVal)
            cur = FormulaValue(FormulaValueType.CONCEPT, obj) if obj is not None \
                else FormulaValue(FormulaValueType.QNAME, factDimVal)
        elif dimQn.localName == "entity":
            cur = FormulaValue(FormulaValueType.ENTITY, factDimVal)
        elif dimQn.localName == "unit":
            cur = FormulaValue(FormulaValueType.UNIT_VALUE, factDimVal)
        else:
            cur = target if isinstance(target, FormulaValue) else FormulaValue.fromScalar(target)
        try:
            for prop in pf["propChain"]:
                cur = getProperty(cur, prop, [], ctx)
        except FormulaRuntimeError:
            return False
        factDimVal = cur.value if isinstance(cur, FormulaValue) else cur

    op = pf["op"]

    # No operator — dim present in alignment (any value accepted)
    if op is None:
        return factDimVal is not None

    if pf["isWildcard"]:
        # "= *" means dim is present with any value
        if op in ("=", "=="):
            return factDimVal is not None
        if op == "!=":
            return factDimVal is None
        return False

    if pf["isNone"] or (pf["value"] is not None and pf["value"].type == FormulaValueType.NONE):
        if op in ("=", "=="):
            return factDimVal is None
        if op == "!=":
            return factDimVal is not None
        return False

    expected = pf["expected"]

    # 'in' / 'not in' against list/set
    if op in ("in", "not in"):
        if pf["value"] is not None and pf["value"].type in (FormulaValueType.LIST, FormulaValueType.SET):
            items = [
                (i.value if isinstance(i, FormulaValue) else i)
                for i in pf["value"].value
            ]
            match = any(_loose_eq(factDimVal, e) for e in items)
            return match if op == "in" else not match
        # scalar — fall through to == / !=
        match = _loose_eq(factDimVal, expected)
        return match if op == "in" else not match

    if op in ("=", "=="):
        return _loose_eq(factDimVal, expected)
    if op == "!=":
        return not _loose_eq(factDimVal, expected)

    # Numeric comparisons (rare in dim filters but supported)
    return _compareValues(factDimVal, op, expected)


def _loose_eq(actual, expected) -> bool:
    """Equality that handles QName ↔ string-form and date ↔ InstantValue."""
    if actual == expected:
        return True
    # QName vs "prefix:local" string
    if isinstance(actual, QName) and isinstance(expected, str):
        if ":" in expected:
            _, _, local = expected.rpartition(":")
            return actual.localName == local
        return actual.localName == expected
    if isinstance(expected, QName) and isinstance(actual, str):
        return _loose_eq(expected, actual)
    # InstantValue vs date
    if isinstance(actual, InstantValue) and hasattr(expected, "dt"):
        return actual.dt == expected.dt
    if hasattr(actual, "dt") and hasattr(expected, "dt"):
        return actual.dt == expected.dt
    return False


def _factMatchesCubeFilter(fact, pf: dict, ctx: FormulaRuleContext) -> bool:
    """`@cube`, `@cube = *`, `@cube = none`, `@cube.name = X`, `@cube.drs-role = R`."""
    from XbrlModel.XbrlCube import XbrlCube
    from XbrlModel.XbrlFact import XbrlFact  # noqa
    from arelle.ModelValue import qname as mkQn

    cubeDimQn = mkQn("https://xbrl.org/2025", "cube")
    factCubeNames = fact.factDimensions.get(cubeDimQn)
    if factCubeNames is None:
        # Fall back: scan cubes' _cellFacts (populated by ValidateFacts) to
        # determine cube membership.
        cubeNames = []
        for cube in ctx.globalCtx.txmyMdl.filterNamedObjects(XbrlCube):
            cellFacts = getattr(cube, "_cellFacts", None)
            if cellFacts:
                for cellEntries in cellFacts.values():
                    if any(f is fact for f, _ in cellEntries):
                        cubeNames.append(getattr(cube, "name", None))
                        break
        factCubeQns = [n for n in cubeNames if n is not None]
    elif isinstance(factCubeNames, (list, tuple, set)):
        factCubeQns = list(factCubeNames)
    else:
        factCubeQns = [factCubeNames]

    op = pf["op"]
    if op is None:
        return bool(factCubeQns)
    if pf["isWildcard"]:
        return bool(factCubeQns) if op in ("=", "==") else not factCubeQns
    if pf["isNone"]:
        return (not factCubeQns) if op in ("=", "==") else bool(factCubeQns)

    # @cube.name = X  or  @cube.drs-role = R
    propChain = pf["propChain"]
    expected = pf["expected"]
    for cubeQn in factCubeQns:
        cube = ctx.globalCtx.txmyMdl.namedObjects.get(cubeQn) if isinstance(cubeQn, QName) else None
        if not propChain:
            # @cube = SomeConcept
            if _loose_eq(cubeQn, expected):
                return op in ("=", "==")
        else:
            val = None
            if propChain[0] == "name":
                val = getattr(cube, "name", None) if cube else cubeQn
            elif propChain[0] in ("drs-role", "drsRole", "role"):
                val = getattr(cube, "drsRole", None) if cube else None
            if val is not None and _loose_eq(val, expected):
                return op in ("=", "==")
    return op == "!="


def _factMatchesDimsFilter(fact, pf: dict, ctx: FormulaRuleContext) -> bool:
    """`@dimensions = $dict`, `@dimensions = *`, `@dimensions = none`."""
    taxDims = {
        qn: v for qn, v in fact.factDimensions.items()
        if not _isCoreDimQn(qn)
    }
    op = pf["op"]
    if op is None:
        return True  # take dim dictionary out of alignment, no filter
    if pf["isWildcard"]:
        return bool(taxDims) if op in ("=", "==") else not taxDims
    if pf["isNone"]:
        return (not taxDims) if op in ("=", "==") else bool(taxDims)
    if pf["value"] is not None and pf["value"].type == FormulaValueType.DICT:
        expectedDims = {
            (k.value if isinstance(k, FormulaValue) else k):
            (v.value if isinstance(v, FormulaValue) else v)
            for k, v in pf["value"].value.items()
        }
        if op in ("=", "=="):
            return taxDims == expectedDims
        if op == "!=":
            return taxDims != expectedDims
    return False


def _compareValues(actual: Any, op: str, expected: Any) -> bool:
    try:
        if op in ("==", "="):
            return actual == expected
        if op == "!=":
            return actual != expected
        # Numeric comparisons
        a, e = Decimal(str(actual)), Decimal(str(expected))
        if op == "<":  return a < e
        if op == "<=": return a <= e
        if op == ">":  return a > e
        if op == ">=": return a >= e
    except (InvalidOperation, TypeError):
        pass
    return False


def _isNil(fact) -> bool:
    if getattr(fact, "factValues", None):
        fv = next(iter(fact.factValues))
        return fv.value is None
    return False


# ---------------------------------------------------------------------------
# Atom-with-property-chain evaluator
# ---------------------------------------------------------------------------

def _evalAtomWithProps(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    baseExpr = node.get("base")
    props = node.get("props", [])

    # pyparsing can collapse repeated named accessors to the last named value,
    # while still preserving the full accessor sequence in positional tokens.
    if isinstance(node, ParseResults):
        if baseExpr is None and len(node) >= 1:
            baseExpr = node[0]
        if len(node) >= 2 and isinstance(node[1], ParseResults):
            props = node[1]

    base = baseExpr if isinstance(baseExpr, FormulaValue) else evaluateExpr(baseExpr, ctx)

    if isinstance(props, ParseResults):
        props = list(props)
    elif isinstance(props, dict):
        props = [props]

    for propNode in props:
        if isinstance(propNode, ParseResults):
            if "indexAccess" in propNode or "indexExpr" in propNode:
                inner = propNode.get("indexAccess", propNode)
                indexVal = evaluateExpr(inner.get("indexExpr"), ctx)
                base = getProperty(base, "index", [indexVal], ctx)
                continue
            inner = propNode.get("propAccess", propNode)
        elif isinstance(propNode, dict):
            if "indexAccess" in propNode or "indexExpr" in propNode:
                inner = propNode.get("indexAccess", propNode)
                indexVal = evaluateExpr(inner.get("indexExpr"), ctx)
                base = getProperty(base, "index", [indexVal], ctx)
                continue
            inner = propNode.get("propAccess", propNode)
        else:
            continue
        propName = inner.get("propName", "")
        rawArgs  = inner.get("propArgs", [])
        args = [evaluateExpr(a, ctx) for a in rawArgs] if rawArgs else []
        base = getProperty(base, propName, args, ctx)
    return base


# ---------------------------------------------------------------------------
# Function call evaluator
# ---------------------------------------------------------------------------

def _evalFuncCall(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    funcName = node.get("funcName", "")
    rawArgs  = node.get("args", [])
    # Normalisation: pyparsing's Group(delimited_list(...)) collapses a
    # single-element list to the element itself in some pyparsing versions.
    # Make sure rawArgs is always a list of expression nodes.
    if isinstance(rawArgs, dict):
        rawArgs = [rawArgs]
    elif rawArgs is None:
        rawArgs = []
    args = [evaluateExpr(a, ctx) for a in rawArgs]
    return callFunction(funcName, args, ctx)


# ---------------------------------------------------------------------------
# Binary and unary expression evaluators
# ---------------------------------------------------------------------------

def _evalBinary(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    left = evaluateExpr(node.get("leftExpr"), ctx)
    op   = str(node.get("op", ""))
    right = evaluateExpr(node.get("rightExpr"), ctx)

    # Merge alignments
    try:
        merged = left.mergeAlignment(right)
    except FormulaAlignmentError:
        raise FormulaIterationStop()

    # ---- Strict/lax arithmetic variants used by Xule ----
    if op in ("+>", "->"):
        return _strictBinary(left, "+" if op == "+>" else "-", right, merged)
    if op in ("<+", "<-"):
        return _laxBinary(left, "+" if op == "<+" else "-", right, merged)
    if op in ("<+>", "<->"):
        return _strictSkipBinary(left, "+" if op == "<+>" else "-", right, merged)

    # ---- Arithmetic ----
    if op in ("+", "-", "*", "/"):
        return _arith(left, op, right, merged)

    # ---- Comparison ----
    if op in ("==", "=", "!=", "<", "<=", ">", ">="):
        # Ordering comparisons involving none:
        # strict (<, >) always return none; non-strict (<=, >=) return true when both are none
        if op in ("<", ">"):
            if left.type == FormulaValueType.NONE or right.type == FormulaValueType.NONE:
                return NONE_VALUE
        elif op in (">=", "<="):
            if left.type == FormulaValueType.NONE or right.type == FormulaValueType.NONE:
                if left.type == FormulaValueType.NONE and right.type == FormulaValueType.NONE:
                    return TRUE_VALUE  # none <= none and none >= none are true via equality
                return NONE_VALUE
        return _compare(left, op, right, merged)

    # ---- In / not in ----
    if op == "in":
        if right.type in (FormulaValueType.DURATION, FormulaValueType.NONE, FormulaValueType.SKIP) or \
                left.type in (FormulaValueType.DURATION,):
            raise FormulaRuntimeError(
                f"Property 'contains' or 'in' expression cannot operate on a '{right.type.name.lower()}' and '{left.type.name.lower()}'"
            )
        if right.type in (FormulaValueType.STRING, FormulaValueType.QNAME):
            if left.type == FormulaValueType.NONE:
                return FALSE_VALUE
            lhs = str(getattr(left.value, "localName", left.value))
            rhs = str(getattr(right.value, "localName", right.value))
            return FormulaValue(FormulaValueType.BOOLEAN, lhs in rhs, alignment=merged)
        items = _unwrapColl(right)
        result = left in items
        return FormulaValue(FormulaValueType.BOOLEAN, result, alignment=merged)
    if op in ("not in", "not  in"):
        if right.type in (FormulaValueType.STRING, FormulaValueType.QNAME):
            if left.type == FormulaValueType.NONE:
                return TRUE_VALUE
            lhs = str(getattr(left.value, "localName", left.value))
            rhs = str(getattr(right.value, "localName", right.value))
            return FormulaValue(FormulaValueType.BOOLEAN, lhs not in rhs, alignment=merged)
        items = _unwrapColl(right)
        result = left not in items
        return FormulaValue(FormulaValueType.BOOLEAN, result, alignment=merged)

    # ---- Boolean ----
    if op.lower() == "and":
        # Three-valued behavior used by conformance tests:
        # false dominates, none/skip propagates to skip when result is unknown.
        if (left.type == FormulaValueType.BOOLEAN and not bool(left.value)) or \
           (right.type == FormulaValueType.BOOLEAN and not bool(right.value)):
            return FALSE_VALUE
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP) or \
           right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return SKIP_VALUE
        return FormulaValue(FormulaValueType.BOOLEAN,
                            _isTruthy(left) and _isTruthy(right), alignment=merged)
    if op.lower() == "or":
        # Three-valued behavior used by conformance tests:
        # true dominates, none/skip propagates to skip when result is unknown.
        if (left.type == FormulaValueType.BOOLEAN and bool(left.value)) or \
           (right.type == FormulaValueType.BOOLEAN and bool(right.value)):
            return TRUE_VALUE
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP) or \
           right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return SKIP_VALUE
        return FormulaValue(FormulaValueType.BOOLEAN,
                            _isTruthy(left) or _isTruthy(right), alignment=merged)

    # ---- Set intersection ----
    if op.lower() == "intersect":
        if left.type != FormulaValueType.SET:
            leftName = 'unbound' if left.type == FormulaValueType.NONE else left.type.name.lower()
            raise FormulaRuntimeError(
                f"Intersection can only operatate on sets. The left side is a '{leftName}'."
            )
        if right.type != FormulaValueType.SET:
            rightName = 'unbound' if right.type == FormulaValueType.NONE else right.type.name.lower()
            raise FormulaRuntimeError(
                f"Intersection can only operatate on sets. The right side is a '{rightName}'."
            )
        return _setOp(left, "intersect", right, merged)
    if op == "&":
        if left.type != FormulaValueType.SET:
            typeName = 'unbound' if left.type == FormulaValueType.NONE else left.type.name.lower()
            raise FormulaRuntimeError(
                f"Intersection can only operatate on sets. The left side is a '{typeName}'."
            )
        return _setOp(left, "intersect", right, merged)

    # ---- Symmetric difference ----
    if op == "^":
        if left.type != FormulaValueType.SET:
            typeName = 'unbound' if left.type == FormulaValueType.NONE else left.type.name.lower()
            raise FormulaRuntimeError(
                f"Symetric difference can only operatate on sets. The left side is a '{typeName}'."
            )
        return _setOp(left, "symDiff", right, merged)

    raise FormulaRuntimeError(f"Unknown operator {op!r}")


def _evalUnary(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    op   = str(node.get("op", ""))
    exprNode = node.get("expr")
    expr = evaluateExpr(exprNode, ctx)

    if op == "-":
        # Interpret -10.abs as (-10).abs and -123.log10 as (-123).log10.
        if isinstance(exprNode, (dict, ParseResults)) and "props" in exprNode and exprNode.get("props"):
            base_node = exprNode.get("base")
            props_node = exprNode.get("props")
            if isinstance(base_node, ParseResults):
                base_node = base_node[0] if len(base_node) == 1 else base_node
            base_val = evaluateExpr(base_node, ctx)
            if base_val.isNumeric:
                neg_base = FormulaValue(base_val.type, -base_val.numericValue(), alignment=base_val.alignment)
                return _evalAtomWithProps({"base": neg_base, "props": props_node}, ctx)
        if expr.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return expr
        if expr.type == FormulaValueType.QNAME:
            local_name = getattr(expr.value, "localName", str(expr.value))
            if str(local_name).lower() in ("inf", "infinity"):
                return FormulaValue(FormulaValueType.FLOAT, float("-inf"), alignment=expr.alignment)
        if expr.isNumeric:
            return FormulaValue(expr.type, -expr.numericValue(), alignment=expr.alignment)
        raise FormulaRuntimeError(f"Unary minus requires numeric value, got {expr.type.name}")
    if op == "+":
        return expr
    if op.lower() == "not":
        return FormulaValue(FormulaValueType.BOOLEAN, not _isTruthy(expr), alignment=expr.alignment)
    raise FormulaRuntimeError(f"Unknown unary operator {op!r}")


# ---------------------------------------------------------------------------
# Arithmetic helpers
# ---------------------------------------------------------------------------

def _arith(left: FormulaValue, op: str, right: FormulaValue,
           merged) -> FormulaValue:
    if op == "+":
        if left.type == FormulaValueType.BOOLEAN:
            raise FormulaRuntimeError("Left side of a + operation cannot be bool.")
        if right.type == FormulaValueType.BOOLEAN:
            raise FormulaRuntimeError("Right side of a + operation cannot be bool.")
        if left.type == FormulaValueType.DURATION and isinstance(left.value, DateRangeValue):
            raise FormulaRuntimeError("Left side of a + operation cannot be duration.")
        # Set union - use insertion-order union (left elements first, new right elements appended)
        if left.type == FormulaValueType.SET and right.type == FormulaValueType.SET:
            result_set = left.value | right.value
            return FormulaValue(FormulaValueType.SET, result_set, alignment=merged)
        # set + none/skip = identity (set unchanged)
        if left.type == FormulaValueType.SET and right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return FormulaValue(FormulaValueType.SET, left.value, alignment=merged)
        if right.type == FormulaValueType.SET and left.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return FormulaValue(FormulaValueType.SET, right.value, alignment=merged)
        # Type mismatch: set + list/other non-set
        if left.type == FormulaValueType.SET or right.type == FormulaValueType.SET:
            lname = left.type.name.lower()
            rname = right.type.name.lower()
            raise FormulaRuntimeError(f"Incompatabile operands {lname} + {rname}.")
        if left.type == FormulaValueType.DICT and right.type == FormulaValueType.DICT:
            resultDict = dict(left.value)
            resultDict.update(right.value)
            return FormulaValue(FormulaValueType.DICT, resultDict, alignment=merged)
        if left.type == FormulaValueType.DATE and right.type == FormulaValueType.DURATION and isinstance(right.value, TimeSpanValue):
            return FormulaValue(FormulaValueType.DATE, InstantValue(left.value.dt + right.value.delta), alignment=merged)
        if left.type == FormulaValueType.DURATION and isinstance(left.value, TimeSpanValue) and right.type == FormulaValueType.DATE:
            raise FormulaRuntimeError("Incompatabile operands time-period + instant.")
        if left.type == FormulaValueType.DURATION and right.type == FormulaValueType.DURATION and isinstance(left.value, TimeSpanValue) and isinstance(right.value, TimeSpanValue):
            return FormulaValue(FormulaValueType.DURATION, TimeSpanValue(left.value.delta + right.value.delta), alignment=merged)

    if op == "+" and (left.type == FormulaValueType.STRING or right.type == FormulaValueType.STRING):
        leftText = "" if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP) else _formatValue(left)
        rightText = "" if right.type in (FormulaValueType.NONE, FormulaValueType.SKIP) else _formatValue(right)
        return FormulaValue(FormulaValueType.STRING, leftText + rightText, alignment=merged)

    if op == "+":
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP) and right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return SKIP_VALUE
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return FormulaValue(right.type, right.value, alignment=merged)
        if right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return FormulaValue(left.type, left.value, alignment=merged)

    if op == "-":
        if left.type == FormulaValueType.DURATION and isinstance(left.value, DateRangeValue):
            raise FormulaRuntimeError("Left side of a - operation cannot be duration.")
        # Set difference
        if left.type == FormulaValueType.SET and right.type == FormulaValueType.SET:
            return FormulaValue(FormulaValueType.SET, left.value - right.value, alignment=merged)
        if left.type == FormulaValueType.DICT and right.type == FormulaValueType.DICT:
            resultDict = {k: v for k, v in left.value.items() if k not in right.value}
            return FormulaValue(FormulaValueType.DICT, resultDict, alignment=merged)
        if left.type == FormulaValueType.DICT and right.type in (FormulaValueType.LIST, FormulaValueType.SET):
            removeKeys = set(_unwrapColl(right))
            resultDict = {k: v for k, v in left.value.items() if k not in removeKeys}
            return FormulaValue(FormulaValueType.DICT, resultDict, alignment=merged)
        if left.type == FormulaValueType.DATE and right.type == FormulaValueType.DURATION and isinstance(right.value, TimeSpanValue):
            return FormulaValue(FormulaValueType.DATE, InstantValue(left.value.dt - right.value.delta), alignment=merged)
        if left.type == FormulaValueType.DATE and right.type == FormulaValueType.DATE:
            return FormulaValue(FormulaValueType.DURATION, TimeSpanValue(left.value.dt - right.value.dt), alignment=merged)
        if left.type == FormulaValueType.DURATION and right.type == FormulaValueType.DURATION and isinstance(left.value, TimeSpanValue) and isinstance(right.value, TimeSpanValue):
            return FormulaValue(FormulaValueType.DURATION, TimeSpanValue(left.value.delta - right.value.delta), alignment=merged)
        if left.type == FormulaValueType.DURATION and isinstance(left.value, TimeSpanValue) and right.type == FormulaValueType.DATE:
            raise FormulaRuntimeError("Incompatabile operands time-period - instant.")
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP) and right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return SKIP_VALUE
        if right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return FormulaValue(left.type, left.value, alignment=merged)
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            # none - numeric  → negate (0 - n);  none - non-numeric  → identity
            if right.isNumeric:
                return FormulaValue(FormulaValueType.DECIMAL, -right.numericValue(), alignment=merged)
            return FormulaValue(right.type, right.value, alignment=merged)

    # none or skip with * or / → skip
    if op in ("*", "/"):
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP) or \
                right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return SKIP_VALUE

    try:
        l = left.numericValue()
        r = right.numericValue()
    except (TypeError, FormulaRuntimeError) as exc:
        raise FormulaRuntimeError(f"Arithmetic error: {exc}") from exc

    try:
        if op == "+":
            result = l + r
        elif op == "-":
            result = l - r
        elif op == "*":
            result = l * r
        elif op == "/":
            if r == 0:
                raise FormulaRuntimeError("Division by zero")
            result = l / r
        else:
            raise FormulaRuntimeError(f"Unknown arithmetic operator {op!r}")
    except InvalidOperation:
        result = Decimal("NaN")

    return FormulaValue(FormulaValueType.DECIMAL, result, alignment=merged)


def _strictBinary(left: FormulaValue, op: str, right: FormulaValue, merged) -> FormulaValue:
    if right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
        return SKIP_VALUE
    return _arith(left, op, right, merged)


def _laxBinary(left: FormulaValue, op: str, right: FormulaValue, merged) -> FormulaValue:
    if right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
        return FormulaValue(left.type, left.value, alignment=merged)
    return _arith(left, op, right, merged)


def _strictSkipBinary(left: FormulaValue, op: str, right: FormulaValue, merged) -> FormulaValue:
    if right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
        raise FormulaSkip()
    return _arith(left, op, right, merged)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _compare(left: FormulaValue, op: str, right: FormulaValue,
             merged) -> FormulaValue:
    def _asComparable(fv: FormulaValue):
        if fv.type == FormulaValueType.SET:
            return frozenset(_asComparable(item) for item in fv.value)
        if fv.type == FormulaValueType.LIST:
            return tuple(_asComparable(item) for item in fv.value)
        if fv.isNumeric:
            return fv.numericValue()
        if fv.type == FormulaValueType.FACT:
            try:
                return fv.numericValue()
            except (TypeError, FormulaRuntimeError):
                if fv.value.factValues:
                    return next(iter(fv.value.factValues)).value
                return None
        if fv.type == FormulaValueType.DATE and isinstance(fv.value, InstantValue):
            return fv.value.dt
        if fv.type == FormulaValueType.DURATION:
            if isinstance(fv.value, DateRangeValue):
                return (fv.value.start, fv.value.end)
            if isinstance(fv.value, TimeSpanValue):
                return fv.value.delta.total_seconds()
        return fv.value

    lv = _asComparable(left)
    rv = _asComparable(right)

    try:
        if op in ("==", "="):  res = lv == rv
        elif op == "!=": res = lv != rv
        elif op == "<":  res = lv < rv   # type: ignore
        elif op == "<=": res = lv <= rv  # type: ignore
        elif op == ">":  res = lv > rv   # type: ignore
        elif op == ">=": res = lv >= rv  # type: ignore
        else: res = False
    except TypeError:
        res = (op in ("!=",)) if (lv != rv) else (op == "==")

    return FormulaValue(FormulaValueType.BOOLEAN, res, alignment=merged)


# ---------------------------------------------------------------------------
# Set operation helpers
# ---------------------------------------------------------------------------

def _unwrapColl(fv: FormulaValue) -> List[FormulaValue]:
    if fv.type == FormulaValueType.SET:
        return list(fv.value)
    if fv.type == FormulaValueType.LIST:
        return list(fv.value)
    return [fv]


def _setOp(left: FormulaValue, op: str, right: FormulaValue, merged) -> FormulaValue:
    ls = OrderedSet(_unwrapColl(left))
    rs = OrderedSet(_unwrapColl(right))
    if op == "union":
        result = ls | rs
    elif op == "intersect":
        result = ls & rs
    elif op == "difference":
        result = ls - rs
    elif op == "symDiff":
        result = ls ^ rs
    else:
        raise FormulaRuntimeError(f"Unknown set operation {op!r}")
    return FormulaValue(FormulaValueType.SET, result, alignment=merged)


# ---------------------------------------------------------------------------
# If-then-else and for-loop evaluators
# ---------------------------------------------------------------------------

def _evalIf(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    try:
        cond = evaluateExpr(node.get("condition"), ctx)
    except FormulaIterationStop:
        # A missing (uncovered) fact in the condition → skip
        return SKIP_VALUE
    # none/skip condition propagates as skip
    if cond.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
        return SKIP_VALUE
    # non-boolean condition is an evaluation error
    if cond.type != FormulaValueType.BOOLEAN:
        raise FormulaRuntimeError(
            f"If condition is not a boolean, found '{cond.type.name.lower()}'"
        )
    if cond.value:
        return evaluateExpr(node.get("thenExpr"), ctx)
    else:
        elseNode = node.get("elseExpr")
        if elseNode is not None:
            return evaluateExpr(elseNode, ctx)
        return NONE_VALUE


def _evalFor(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    varName    = node.get("varName", "")
    collection = evaluateExpr(node.get("collection"), ctx)
    body       = node.get("body")
    if collection.type not in (FormulaValueType.SET, FormulaValueType.LIST):
        raise FormulaRuntimeError(
            f"For loop requires a set or list, found '{collection.type.name.lower()}'."
        )
    items      = _unwrapColl(collection)
    results: List[FormulaValue] = []
    for item in items:
        childCtx = ctx.childContext()
        childCtx.bindVariable(varName, item)
        val = evaluateExpr(body, childCtx)
        if not val.isSkip:
            results.append(val)
    if len(results) == 1:
        return results[0]
    resultVal = FormulaValue(FormulaValueType.LIST, results)
    setattr(resultVal, "_forResult", True)
    return resultVal


def _evalAssign(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    varName = node.get("varName", "")
    valueExpr = node.get("valueExpr")
    val = evaluateExpr(valueExpr, ctx)
    if varName:
        ctx.bindVariable(varName, val)
    return val


def _evalBlockExpr(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    steps = node.get("steps", [])
    if not isinstance(steps, list):
        steps = [steps]

    result = NONE_VALUE
    for step in steps:
        # Parser may flatten accessors like [idx] or .prop(...) into a following
        # standalone step. Apply those accessors to the current result value.
        if isinstance(step, (ParseResults, dict)) and (
            (isinstance(step, ParseResults) and ("indexAccess" in step or "propAccess" in step))
            or (isinstance(step, dict) and ("indexAccess" in step or "propAccess" in step))
        ):
            result = _evalAtomWithProps({"base": result, "props": [step]}, ctx)
            continue
        try:
            result = evaluateExpr(step, ctx)
        except FormulaIterationStop:
            if _nodeHasCoveredFlag(step):
                coveredNone = FormulaValue(FormulaValueType.NONE, None)
                setattr(coveredNone, "_coveredMissing", True)
                result = coveredNone
                continue
            raise
    return result


def _nodeHasCoveredFlag(node: Any) -> bool:
    if isinstance(node, dict):
        cf = node.get("coveredFlag")
        if cf is not None:
            val = cf.get("value", "") if isinstance(cf, dict) else cf
            if str(val).lower() == "covered" or str(val).lower() == "['covered']":
                return True
        return any(_nodeHasCoveredFlag(v) for v in node.values())
    if isinstance(node, ParseResults):
        cf = node.get("coveredFlag") if "coveredFlag" in node else None
        if cf is not None and str(cf).lower().find("covered") >= 0:
            return True
        return any(_nodeHasCoveredFlag(v) for v in list(node))
    if isinstance(node, list):
        return any(_nodeHasCoveredFlag(v) for v in node)
    return False


# ---------------------------------------------------------------------------
# Collection literals
# ---------------------------------------------------------------------------

def _evalSetLiteral(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    raw = node.get("items", [])
    items = OrderedSet(evaluateExpr(i, ctx) for i in raw)
    return FormulaValue(FormulaValueType.SET, items)


def _evalListLiteral(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    raw = node.get("items", [])
    items = [evaluateExpr(i, ctx) for i in raw]
    return FormulaValue(FormulaValueType.LIST, items)


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def _buildMessage(rule, result: FormulaValue, ctx: FormulaRuleContext) -> str:
    if rule.messageExpr is None:
        # Default message
        from .FormulaRuleSet import AssertRule
        if isinstance(rule, AssertRule):
            return f"Assertion {rule.name!r} failed"
        return f"Output {rule.name!r}: {_formatValue(result)}"
    try:
        msgVal = _evalString(rule.messageExpr, ctx)
        return msgVal.value
    except Exception as exc:
        return f"[message error: {exc}]"


# ---------------------------------------------------------------------------
# Truthiness
# ---------------------------------------------------------------------------

def _isTruthy(val: FormulaValue) -> bool:
    """Return Python bool for a FormulaValue, following Xule semantics."""
    if val.type == FormulaValueType.BOOLEAN:
        return bool(val.value)
    if val.type == FormulaValueType.NONE:
        return False
    if val.type == FormulaValueType.SKIP:
        return False
    if val.type in (FormulaValueType.INTEGER, FormulaValueType.FLOAT, FormulaValueType.DECIMAL):
        return bool(val.value)
    if val.type == FormulaValueType.STRING:
        return bool(val.value)
    if val.type in (FormulaValueType.SET, FormulaValueType.LIST):
        return bool(val.value)
    # Facts, taxonomy objects, etc. are truthy
    return True
