"""
FormulaConstraints.py - relationship constraints as static expressions.

A relationship type may carry `constraints`, each a boolean expression in this
language over the relationship's own objects (tavi.md, relationship constraints
object; tavi-formula.md, "Static Expressions").  They are evaluated while
validating a model, once per relationship of that type.

The expression is *static*: it may reference model objects and their properties,
and it may navigate, but it may not reference reported data or anything outside
the model.  That restriction is what makes a constraint checkable at compile
time rather than a query that happens to run then, and it is enforced here
rather than left as a claim in the specification.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, List, Optional, Tuple

from arelle.ModelValue import QName


# Functions whose result depends on state outside the model. model() is the
# model being evaluated and is static; model(url) is another model.
_NON_STATIC_FUNCTIONS = frozenset((
    "taxonomy", "instance",
    "csv-data", "excel-data", "json-data", "xml-data-flat",
    "random",
))

# Properties whose value depends on reported data.
_FACT_DEPENDENT_PROPERTIES = frozenset((
    "facts", "factValues", "footnotes", "entities", "units",
))


def _walk(node: Any) -> Iterable[Any]:
    """Yield every dict-like node of a parsed expression."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)
    else:
        # a ParseResults behaves like a sequence and may carry named children
        asList = getattr(node, "asList", None)
        if callable(asList):
            try:
                for item in node:
                    yield from _walk(item)
            except TypeError:
                pass


def nonStaticReasons(expr: Any) -> List[str]:
    """Why an expression is not static, or an empty list if it is.

    Reported all at once rather than first-only: an author fixing a constraint
    wants to see everything wrong with it.
    """
    reasons: List[str] = []
    for node in _walk(expr):
        if not isinstance(node, dict):
            continue
        if "factQuery" in node:
            reasons.append("a fact query references reported data")
        funcCall = node.get("funcCall")
        if isinstance(funcCall, dict):
            name = funcCall.get("funcName")
            if name in _NON_STATIC_FUNCTIONS:
                reasons.append(f"the function {name}() reaches outside the model")
            elif name == "model" and funcCall.get("args"):
                reasons.append("model(url) reaches another model")
        navigate = node.get("navigateExpr")
        if isinstance(navigate, dict) and navigate.get("modelValue") is not None:
            reasons.append("a navigate `model` clause reaches another model")
        propName = node.get("propName")
        if propName in _FACT_DEPENDENT_PROPERTIES:
            reasons.append(f"the property {propName} depends on reported data")
    # stable, de-duplicated
    seen, unique = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


# The JSON schema constrains a relationship constraint to a purpose-built
# comparison grammar rather than to this language:
#
#   relationship.source.xbrlr:dataType == relationship.target.xbrlr:dataType
#     AND relationship.source.property.xbrla:balance == ...
#
# -- no `$` sigil, prefixed QNames as property names, AND/OR/NOT, and a chain
# rooted at relationship.(source|target|property|properties). The shipped
# xbrla.json uses it. tavi.md meanwhile says constraints are "defined using the
# OIM formula expression language", which is a different thing. Until that is
# settled, a constraint in the schema's form is recognised and passed over
# rather than reported as a broken expression in this language.
_SCHEMA_FORM = re.compile(r"^\s*relationship\.(source|target|property|properties)\b")


def isSchemaFormConstraint(text: str) -> bool:
    return bool(_SCHEMA_FORM.match(text or ""))


def parseConstraint(text: str):
    """Parse a constraint expression, returning (expr, errorMessage)."""
    from .FormulaParser import parseFormulaString
    try:
        ruleSet = parseFormulaString(f"output _constraint\n  {text}\n", "<constraint>")
    except Exception as exc:
        return None, str(exc)
    rule = ruleSet.outputRules.get("_constraint")
    if rule is None:
        return None, "the constraint parsed to no expression"
    return rule.expr, None


def _relationshipTypesWithConstraints(txmyMdl):
    from XbrlModel.XbrlNetwork import XbrlRelationshipType
    for rt in txmyMdl.filterNamedObjects(XbrlRelationshipType):
        if rt.constraints:
            yield rt


def validateRelationshipConstraints(txmyMdl, cntlr=None, options=None) -> None:
    """Evaluate every relationship type's constraints over the model.

    Separate constraint objects on one relationship type are alternatives: a
    relationship satisfies the type when it satisfies any of them (tavi.md,
    "Separate relationshipConstraint objects are considered to be an OR").
    """
    from XbrlModel.XbrlNetwork import XbrlNetwork
    from .FormulaContext import FormulaGlobalContext, FormulaRuleContext
    from .FormulaInterpreter import evaluateExpr
    from .FormulaNavigate import NavRelationship
    from .FormulaRuleSet import FormulaRuleSet
    from .FormulaValue import FormulaValue, FormulaValueType, FormulaRuntimeError

    relTypes = list(_relationshipTypesWithConstraints(txmyMdl))
    if not relTypes:
        return

    globalCtx = FormulaGlobalContext(FormulaRuleSet(), txmyMdl, cntlr=cntlr, options=options)

    for rt in relTypes:
        rtName = rt.name
        parsed: List[Tuple[Any, str]] = []
        for constraintObj in rt.constraints or ():
            text = constraintObj.constraint
            if not isinstance(text, str) or not text.strip():
                continue
            if isSchemaFormConstraint(text):
                txmyMdl.info("arelle:constraintNotEvaluated",
                             _("Relationship type %(relationshipType)s carries a constraint in the "
                               "schema's comparison form, which this implementation does not yet "
                               "evaluate: %(constraint)s"),
                             xbrlObject=rt, relationshipType=rtName, constraint=text)
                continue
            expr, parseError = parseConstraint(text)
            if parseError is not None:
                txmyMdl.error("taviqe:invalidStaticExpression",
                              _("Relationship type %(relationshipType)s constraint could not be "
                                "parsed: %(error)s. Constraint: %(constraint)s"),
                              xbrlObject=rt, relationshipType=rtName,
                              error=parseError, constraint=text)
                continue
            reasons = nonStaticReasons(expr)
            if reasons:
                txmyMdl.error("taviqe:nonStaticExpression",
                              _("Relationship type %(relationshipType)s constraint is not a static "
                                "expression: %(reasons)s. Constraint: %(constraint)s"),
                              xbrlObject=rt, relationshipType=rtName,
                              reasons="; ".join(reasons), constraint=text)
                continue
            parsed.append((expr, text))

        if not parsed:
            continue

        for network in txmyMdl.filterNamedObjects(XbrlNetwork):
            if network.relationshipTypeName != rtName:
                continue
            if network.relationships is None:
                continue
            from XbrlModel.XbrlConst import qnXbrlRootSource
            for rel in txmyMdl.effectiveRelationships(network):
                if rel.source == qnXbrlRootSource:
                    continue  # the root source anchors roots; it is not content
                satisfied = False
                failures = []
                for expr, text in parsed:
                    ruleCtx = FormulaRuleContext(globalCtx)
                    ruleCtx.bindVariable("relationship", FormulaValue(
                        FormulaValueType.RELATIONSHIP, NavRelationship(rel, network)))
                    try:
                        result = evaluateExpr(expr, ruleCtx)
                    except FormulaRuntimeError as exc:
                        failures.append(f"{text} ({exc})")
                        continue
                    if result.type != FormulaValueType.BOOLEAN:
                        txmyMdl.error("taviqe:nonBooleanConstraint",
                                      _("Relationship type %(relationshipType)s constraint did not "
                                        "evaluate to a boolean. Constraint: %(constraint)s"),
                                      xbrlObject=rt, relationshipType=rtName, constraint=text)
                        satisfied = True  # reported already; do not also report a violation
                        break
                    if result.value:
                        satisfied = True
                        break
                    failures.append(text)
                if not satisfied:
                    txmyMdl.error("oimte:relationshipConstraintViolation",
                                  _("Relationship %(source)s->%(target)s in network %(network)s "
                                    "does not satisfy the constraints of relationship type "
                                    "%(relationshipType)s: %(constraints)s"),
                                  xbrlObject=network,
                                  source=rel.source,
                                  target=rel.target,
                                  network=network.name,
                                  relationshipType=rtName,
                                  constraints="; ".join(failures))
