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
    """Recursively walk the AST and collect all factQuery nodes into slots."""
    if not isinstance(node, dict):
        return
    if node.get("exprName") == "factQuery" or "factQuery" in node:
        fqNode = node.get("factQuery", node)
        concept = fqNode.get("concept", {})
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
    from arelle.plugin.XbrlModel.XbrlReport import XbrlFact
    from arelle.XmlValidate import VALID
    from arelle.ModelValue import qname as mkQn

    conceptDimQn = mkQn("https://xbrl.org/2021", "concept")
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
            return _evalAtomWithProps({"base": baseNode, "props": list(node.get("props", []))}, ctx)

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


def _formatValue(val: FormulaValue) -> str:
    if val.type == FormulaValueType.FACT:
        if val.value.factValues:
            fv = next(iter(val.value.factValues))
            return str(fv.value) if fv.value is not None else ""
        return ""
    if val.type == FormulaValueType.NONE:
        return ""
    if val.type == FormulaValueType.BOOLEAN:
        return "true" if bool(val.value) else "false"
    return str(val.value)


# ---------------------------------------------------------------------------
# QName evaluation
# ---------------------------------------------------------------------------

def _evalQName(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    prefix    = node.get("prefix", "*")
    localName = node.get("localName", "")
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
    Evaluate a single @Concept fact query in the current iteration context.

    In the alignment model, fact queries inside an expression are evaluated
    against the already-bound facts (from the rule's iteration setup).  If
    a matching fact was pre-bound by the interpreter (via a tag), return it.
    If not found among bindings, perform a live lookup and return the first
    matching fact or none.
    """
    concept = node.get("concept", {})
    prefix    = concept.get("prefix", "*")
    localName = concept.get("localName", "")
    tag       = node.get("tag")

    # If this fact was pre-bound to a tag in the current iteration, return it
    if tag and tag in ctx.variables:
        return ctx.variables[tag]

    # Live lookup: find facts matching the concept (and optional dimension filters)
    try:
        qn = ctx.globalCtx.resolveQName(prefix, localName)
    except KeyError:
        return NONE_VALUE

    facts = ctx.globalCtx.factsForConcept(qn)

    # Apply dimension filters from the query: @Concept[dim==value]
    filters = node.get("filters", [])
    if filters and isinstance(filters, (list,)):
        facts = _applyFactFilters(facts, filters, ctx)

    # Nils handling
    nilsFlag = node.get("nilsFlag")
    if nilsFlag:
        nilsStr = nilsFlag.get("value", "") if isinstance(nilsFlag, dict) else str(nilsFlag)
        if nilsStr == "nonils":
            facts = [f for f in facts if not _isNil(f)]
        elif nilsStr == "nils":
            facts = [f for f in facts if _isNil(f)]

    if not facts:
        raise FormulaIterationStop()

    # In a non-iteration context return all matching facts as a set
    fact_values = [FormulaValue.fromFact(f) for f in facts]
    if len(fact_values) == 1:
        fv = fact_values[0]
        if tag:
            ctx.bindVariable(tag, fv)
        return fv

    # Multiple facts — return as a list; the rule iteration will align them
    result = FormulaValue(FormulaValueType.LIST, fact_values)
    if tag:
        ctx.bindVariable(tag, result)
    return result


def _isNil(fact) -> bool:
    if fact.factValues:
        fv = next(iter(fact.factValues))
        return fv.value is None
    return False


def _applyFactFilters(facts: List, filters: List, ctx: FormulaRuleContext) -> List:
    """Filter a list of facts by dimension equality constraints."""
    from arelle.ModelValue import qname as mkQn
    conceptDimQn = mkQn("https://xbrl.org/2021", "concept")

    result = []
    for fact in facts:
        match = True
        for filt in filters:
            if not isinstance(filt, dict):
                continue
            dim_node = filt.get("dim", {})
            op       = filt.get("op", "==")
            val_node = filt.get("value")

            try:
                prefix    = dim_node.get("prefix", "*") if isinstance(dim_node, dict) else "*"
                localName = dim_node.get("localName", "") if isinstance(dim_node, dict) else str(dim_node)
                dimQn = ctx.globalCtx.resolveQName(prefix, localName)
            except KeyError:
                match = False
                break

            factDimVal = fact.factDimensions.get(dimQn)
            expectedVal = evaluateExpr(val_node, ctx).value if val_node else None

            if not _compareValues(factDimVal, op, expectedVal):
                match = False
                break
        if match:
            result.append(fact)
    return result


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


# ---------------------------------------------------------------------------
# Atom-with-property-chain evaluator
# ---------------------------------------------------------------------------

def _evalAtomWithProps(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    base = evaluateExpr(node.get("base"), ctx)
    props = node.get("props", [])
    for propNode in props:
        if not isinstance(propNode, dict):
            continue
        inner = propNode.get("propAccess", propNode)
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
    if op in ("==", "!=", "<", "<=", ">", ">="):
        return _compare(left, op, right, merged)

    # ---- In / not in ----
    if op == "in":
        items = _unwrapColl(right)
        result = left in items
        return FormulaValue(FormulaValueType.BOOLEAN, result, alignment=merged)
    if op in ("not in", "not  in"):
        items = _unwrapColl(right)
        result = left not in items
        return FormulaValue(FormulaValueType.BOOLEAN, result, alignment=merged)

    # ---- Boolean ----
    if op.lower() == "and":
        return FormulaValue(FormulaValueType.BOOLEAN,
                            _isTruthy(left) and _isTruthy(right), alignment=merged)
    if op.lower() == "or":
        return FormulaValue(FormulaValueType.BOOLEAN,
                            _isTruthy(left) or _isTruthy(right), alignment=merged)

    # ---- Set intersection ----
    if op.lower() in ("&", "intersect"):
        return _setOp(left, "intersect", right, merged)

    # ---- Symmetric difference ----
    if op == "^":
        return _setOp(left, "symDiff", right, merged)

    raise FormulaRuntimeError(f"Unknown operator {op!r}")


def _evalUnary(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    op   = str(node.get("op", ""))
    expr = evaluateExpr(node.get("expr"), ctx)

    if op == "-":
        if expr.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return expr
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
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP) and right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return SKIP_VALUE
        if right.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            return FormulaValue(left.type, left.value, alignment=merged)
        if left.type in (FormulaValueType.NONE, FormulaValueType.SKIP):
            if right.isNumeric:
                return FormulaValue(FormulaValueType.DECIMAL, -right.numericValue(), alignment=merged)
            raise FormulaRuntimeError(f"Arithmetic error: Cannot negate non-numeric {right.type.name}")

    try:
        l = left.numericValue()
        r = right.numericValue()
    except (TypeError, FormulaRuntimeError) as exc:
        raise FormulaRuntimeError(f"Arithmetic error: {exc}") from exc

    if op == "+":  result = l + r
    elif op == "-": result = l - r
    elif op == "*": result = l * r
    elif op == "/":
        if r == 0:
            raise FormulaRuntimeError("Division by zero")
        result = l / r
    else:
        raise FormulaRuntimeError(f"Unknown arithmetic operator {op!r}")

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
        if fv.isNumeric:
            return fv.numericValue()
        if fv.type == FormulaValueType.FACT:
            try:
                return fv.numericValue()
            except (TypeError, FormulaRuntimeError):
                if fv.value.factValues:
                    return next(iter(fv.value.factValues)).value
                return None
        return fv.value

    lv = _asComparable(left)
    rv = _asComparable(right)

    try:
        if op == "==":  res = lv == rv
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
    ls = set(_unwrapColl(left))
    rs = set(_unwrapColl(right))
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
    return FormulaValue(FormulaValueType.SET, frozenset(result), alignment=merged)


# ---------------------------------------------------------------------------
# If-then-else and for-loop evaluators
# ---------------------------------------------------------------------------

def _evalIf(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    cond = evaluateExpr(node.get("condition"), ctx)
    if _isTruthy(cond):
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
    items      = _unwrapColl(collection)
    results: List[FormulaValue] = []
    for item in items:
        childCtx = ctx.childContext()
        childCtx.bindVariable(varName, item)
        val = evaluateExpr(body, childCtx)
        if not val.isSkip:
            results.append(val)
    return FormulaValue(FormulaValueType.LIST, results)


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
        result = evaluateExpr(step, ctx)
    return result


# ---------------------------------------------------------------------------
# Collection literals
# ---------------------------------------------------------------------------

def _evalSetLiteral(node: dict, ctx: FormulaRuleContext) -> FormulaValue:
    raw = node.get("items", [])
    items = frozenset(evaluateExpr(i, ctx) for i in raw)
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
