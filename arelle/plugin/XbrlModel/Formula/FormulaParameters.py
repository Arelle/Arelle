"""
FormulaParameters.py - parameters and report-time expressions.

tavi-formula.md, "Parameters and Report-time Expressions". A parameter's value is
the first of: a value supplied by the processor, a value the report gives it (a
Tavi report parameter), and the value of its `select` expression -- the design
of the XBRL Formula 1.0 `variable:parameter` and its `@select`.

A parameter is determined once for the report, the first time anything reads it.
Parameters, constants and custom functions that read one another are therefore
evaluated in dependency order without that order being worked out in advance,
and a read that comes back round to a parameter still being determined is a
cycle.

ReportTimeEvaluator is the entry point for the XbrlModel validator, which needs
parameter values (and the values of other report-time expressions) before it
matches facts to cubes. The values it determines are kept on the compiled
model, so rule sets run later read the same values rather than computing them
again.

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

from arelle.ModelValue import QName

from .FormulaValue import (
    FormulaValue, FormulaValueType, FormulaRuntimeError, NONE_VALUE,
)
from .DateTimeSupport import (
    InstantValue, DateRangeValue, parse_period_string, parse_date_string, format_instant,
)

try:
    from ordered_set import OrderedSet
except ImportError:
    OrderedSet = list


@dataclass
class ParameterDecl:
    """A parameter, declared by a query set or by the model being evaluated."""
    name: str                       # without the '$'
    asType: Any = None              # QName node or 'prefix:local' text of the type
    required: bool = False
    selectExpr: Any = None          # AST of the report-time expression
    origin: str = "query set"       # or "model"


class ReportTimeViolation(FormulaRuntimeError):
    """A report-time expression reached something it may not (cube membership)."""


# Functions whose result depends on state outside the report and its model.
# model() is allowed; model(url) is not, and is checked by its arguments.
_EXTERNAL_FUNCTIONS = frozenset((
    "taxonomy", "instance",
    "csv-data", "excel-data", "json-data", "xml-data-flat",
    "random",
))


def reportTimeReasons(expr: Any) -> List[str]:
    """Why an expression may not be evaluated at report time, by its syntax.

    Cube membership cannot be told from syntax alone -- `model().cubes` is model
    content, a fact's `cubes` is membership -- so the interpreter refuses it at
    run time instead (ReportTimeViolation).
    """
    from .FormulaConstraints import _walk
    reasons: List[str] = []
    for node in _walk(expr):
        if not isinstance(node, dict):
            continue
        funcCall = node.get("funcCall")
        if isinstance(funcCall, dict):
            name = funcCall.get("funcName")
            if name in _EXTERNAL_FUNCTIONS:
                reasons.append(f"the function {name}() depends on state outside the report")
            elif name == "model" and funcCall.get("args"):
                reasons.append("model(url) reaches another model")
        navigate = node.get("navigateExpr")
        if isinstance(navigate, dict) and navigate.get("modelValue") is not None:
            reasons.append("a navigate `model` clause reaches another model")
        dimName = node.get("dimName")
        if isinstance(dimName, dict):
            qn = dimName.get("qname")
            if isinstance(qn, dict) and qn.get("prefix") in ("*", None) and qn.get("localName") == "cube":
                reasons.append("the @cube filter reads cube membership")
    return list(dict.fromkeys(reasons))


# ---------------------------------------------------------------------------
# Typing (tavi-formula.md, "Typing a parameter's value")
# ---------------------------------------------------------------------------

class _TypeMismatch(Exception):
    pass


def _xsQn(local: str) -> QName:
    from arelle.XbrlConst import xsd
    return QName("xs", xsd, local)


def _scalarFamily(typeQn: QName, typeObj, mdl) -> str:
    """The language value a datatype converts to, by the XML Schema type it derives from."""
    from XbrlModel.XbrlConst import xbrlr
    families = (
        ("period",  (QName("xbrlr", xbrlr, "periodString"),)),
        ("boolean", (_xsQn("boolean"),)),
        ("integer", (_xsQn("integer"),)),
        ("decimal", (_xsQn("decimal"),)),
        ("float",   (_xsQn("float"), _xsQn("double"))),
        ("qname",   (_xsQn("QName"),)),
        ("date",    (_xsQn("date"), _xsQn("dateTime"))),
    )
    for family, qns in families:
        if typeQn in qns:
            return family
        if typeObj is not None and typeObj.instanceOfType(qns, mdl):
            return family
    return "string"


def _asText(value: FormulaValue) -> str:
    if value.type == FormulaValueType.QNAME:
        return str(value.value)
    if value.type == FormulaValueType.DATE:
        return format_instant(value.value)
    return str(value.value)


def _convertScalar(value: FormulaValue, family: str, globalCtx) -> FormulaValue:
    t, v = value.type, value.value
    if t in (FormulaValueType.SET, FormulaValueType.LIST):
        items = list(v)
        if len(items) != 1:
            raise _TypeMismatch(f"a collection of {len(items)} items is not a single value")
        return _convertScalar(items[0], family, globalCtx)
    if t == FormulaValueType.FACT:
        # A fact stands for its value, as a fact item atomizes in XPath.
        from .FormulaProperties import getProperty
        return _convertScalar(getProperty(value, "value", [], None), family, globalCtx)
    if t == FormulaValueType.NONE:
        return value
    try:
        if family == "string":
            return value if t == FormulaValueType.STRING else FormulaValue(FormulaValueType.STRING, _asText(value))
        if family == "boolean":
            if t == FormulaValueType.BOOLEAN:
                return value
            if t == FormulaValueType.STRING and v.strip() in ("true", "false", "1", "0"):
                return FormulaValue(FormulaValueType.BOOLEAN, v.strip() in ("true", "1"))
        elif family == "integer":
            if t == FormulaValueType.INTEGER:
                return value
            d = Decimal(str(v).strip())
            if d == d.to_integral_value() and t != FormulaValueType.BOOLEAN:
                return FormulaValue(FormulaValueType.INTEGER, int(d))
        elif family == "decimal":
            if t in (FormulaValueType.INTEGER, FormulaValueType.DECIMAL, FormulaValueType.FLOAT,
                     FormulaValueType.STRING):
                return FormulaValue(FormulaValueType.DECIMAL, Decimal(str(v).strip()))
        elif family == "float":
            if t in (FormulaValueType.INTEGER, FormulaValueType.DECIMAL, FormulaValueType.FLOAT,
                     FormulaValueType.STRING):
                return FormulaValue(FormulaValueType.FLOAT, float(str(v).strip()))
        elif family == "qname":
            if t == FormulaValueType.QNAME:
                return value
            if t == FormulaValueType.STRING:
                prefix, sep, local = v.strip().rpartition(":")
                return FormulaValue(FormulaValueType.QNAME,
                                    globalCtx.resolveQName(prefix if sep else "", local))
        elif family == "date":
            if t == FormulaValueType.DATE:
                return value
            if t == FormulaValueType.STRING:
                return FormulaValue(FormulaValueType.DATE, InstantValue(parse_date_string(v.strip())))
        elif family == "period":
            if t == FormulaValueType.DATE or (t == FormulaValueType.DURATION
                                              and isinstance(v, DateRangeValue)):
                return value
            if t == FormulaValueType.STRING:
                period = parse_period_string(v.strip())
                return FormulaValue(FormulaValueType.DATE if isinstance(period, InstantValue)
                                    else FormulaValueType.DURATION, period)
    except (InvalidOperation, ValueError, TypeError, KeyError) as exc:
        raise _TypeMismatch(str(exc))
    raise _TypeMismatch(f"a {t.name.lower()} value does not convert to {family}")


def convertToType(value: FormulaValue, asType: Any, globalCtx) -> FormulaValue:
    """Convert a parameter's value to its declared datatype or collection type."""
    typeQn = asType if isinstance(asType, QName) else _resolveTypeQName(asType, globalCtx)
    mdl = globalCtx.txmyMdl
    typeObj = mdl.namedObjects.get(typeQn)
    from XbrlModel.XbrlConcept import XbrlCollectionType, XbrlDataType
    from arelle.XbrlConst import xsd
    if isinstance(typeObj, XbrlCollectionType):
        itemQn = typeObj.dataType
        itemObj = mdl.namedObjects.get(itemQn)
        family = _scalarFamily(itemQn, itemObj if isinstance(itemObj, XbrlDataType) else None, mdl)
        if value.type in (FormulaValueType.SET, FormulaValueType.LIST):
            items = list(value.value)
        elif value.type == FormulaValueType.NONE:
            return value
        else:
            items = [value]
        converted = [_convertScalar(i, family, globalCtx) for i in items]
        if typeObj.uniqueValues:
            converted = list(dict.fromkeys(converted))
        count = len(converted)
        if typeObj.minItems is not None and count < typeObj.minItems:
            raise _TypeMismatch(f"{count} items, fewer than minItems {typeObj.minItems}")
        if typeObj.maxItems is not None and count > typeObj.maxItems:
            raise _TypeMismatch(f"{count} items, more than maxItems {typeObj.maxItems}")
        if typeObj.orderedValues:
            return FormulaValue(FormulaValueType.LIST, converted)
        return FormulaValue(FormulaValueType.SET, OrderedSet(converted))
    if isinstance(typeObj, XbrlDataType) or typeQn.namespaceURI == xsd:
        family = _scalarFamily(typeQn, typeObj if isinstance(typeObj, XbrlDataType) else None, mdl)
        return _convertScalar(value, family, globalCtx)
    raise _TypeMismatch(f"{typeQn} is not a datatype or collection type of the model")


def _resolveTypeQName(asType: Any, globalCtx) -> QName:
    if isinstance(asType, dict):        # a parsed QName node
        asType = asType.get("qname", asType)
        prefix, local = asType.get("prefix") or "", asType.get("localName")
    else:
        prefix, _sep, local = str(asType).rpartition(":")
    try:
        return globalCtx.resolveQName(prefix, local)
    except KeyError:
        raise _TypeMismatch(f"the prefix of {prefix}:{local} is not declared")


def fromPython(value: Any) -> FormulaValue:
    """A value supplied from outside the language (a CLI string, a set of CIKs)."""
    if isinstance(value, FormulaValue):
        return value
    if value is None:
        return NONE_VALUE
    if isinstance(value, (set, frozenset)):
        return FormulaValue(FormulaValueType.SET, OrderedSet(fromPython(v) for v in value))
    if isinstance(value, (list, tuple)):
        return FormulaValue(FormulaValueType.LIST, [fromPython(v) for v in value])
    return FormulaValue.fromScalar(value)


def toModelValue(value: FormulaValue) -> Any:
    """A language value as the XbrlModel represents it, for a caller outside the language.

    A date names a whole day and an OIM instant is the midnight that ends it, so a
    date converts to the following midnight; a duration of whole days ends at the
    midnight after its last day. Collections convert item by item.
    """
    t, v = value.type, value.value
    if t == FormulaValueType.NONE:
        return None
    if t == FormulaValueType.SET:
        return frozenset(toModelValue(i) for i in v)
    if t == FormulaValueType.LIST:
        return [toModelValue(i) for i in v]
    if t == FormulaValueType.DATE and isinstance(v, InstantValue):
        dt = v.dt
        return dt + timedelta(days=1) if dt.hour == dt.minute == dt.second == 0 else dt
    if t == FormulaValueType.DURATION and isinstance(v, DateRangeValue):
        from arelle.ModelValue import TimeInterval
        return TimeInterval(v.start, v.end + (timedelta(days=1) if v.endOfDay else timedelta(0)))
    return v


# ---------------------------------------------------------------------------
# Determining parameter values
# ---------------------------------------------------------------------------

def evaluateIterations(expr: Any, globalCtx, label: str) -> List[FormulaValue]:
    """The values an expression produces, one per iteration, as a query block would."""
    from .FormulaInterpreter import evaluateRule, evaluateExpr
    from .FormulaRuleSet import OutputRule
    from .FormulaValue import FormulaSkip, FormulaIterationStop

    values: List[FormulaValue] = []

    def onIteration(ruleCtx, guard):
        try:
            value = evaluateExpr(expr, ruleCtx)
        except (FormulaSkip, FormulaIterationStop):
            return
        if guard is None or guard(ruleCtx):
            values.append(value)

    globalCtx.reportTimeDepth += 1
    try:
        evaluateRule(OutputRule(name=label, expr=expr), globalCtx, onIteration=onIteration)
    finally:
        globalCtx.reportTimeDepth -= 1
    return values


class ParameterResolver:
    """The parameters visible to one evaluation, determined on first read."""

    def __init__(self, globalCtx, decls: Dict[str, ParameterDecl],
                 supplied: Optional[Dict[str, Any]] = None,
                 reportValues: Optional[Dict[str, Any]] = None,
                 determined: Optional[Dict[str, FormulaValue]] = None):
        self.globalCtx = globalCtx
        self.decls = decls
        self.supplied = supplied or {}
        self.reportValues = reportValues or {}
        # Values already determined for this report (by the validator, before
        # cube matching) are not determined again.
        self.values: Dict[str, FormulaValue] = dict(determined or {})
        self._stack: List[str] = []
        self._cyclic: set = set()

    def __contains__(self, name: str) -> bool:
        return name in self.decls or name in self.values

    def declare(self, decl: ParameterDecl) -> None:
        prior = self.decls.get(decl.name)
        if prior is not None and prior.selectExpr is not None and decl.selectExpr is not None:
            self._error("taviqe:duplicateParameterName",
                        "Parameter $%(name)s is declared with an expression by both the %(a)s and the %(b)s.",
                        name=decl.name, a=prior.origin, b=decl.origin)
            return
        if prior is not None and decl.selectExpr is None:
            # A declaration without an expression adds nothing but its type.
            if prior.asType is None:
                prior.asType = decl.asType
            prior.required = prior.required or decl.required
            return
        self.decls[decl.name] = decl

    def value(self, name: str) -> FormulaValue:
        if name in self.values:
            return self.values[name]
        if name in self._stack:
            cycle = self._stack[self._stack.index(name):]
            if not set(cycle) <= self._cyclic:
                self._cyclic.update(cycle)
                self._error("taviqe:parameterCycle",
                            "Parameters %(cycle)s depend on one another in a cycle and are undetermined.",
                            cycle=" -> ".join(f"${n}" for n in cycle + [name]))
            return NONE_VALUE
        decl = self.decls.get(name)
        if decl is None:
            return NONE_VALUE
        self._stack.append(name)
        try:
            value = self._determine(decl)
        finally:
            self._stack.pop()
        if name in self._cyclic:
            value = NONE_VALUE
        self.values[name] = value
        return value

    def determineAll(self) -> Dict[str, FormulaValue]:
        for name in list(self.decls):
            self.value(name)
        return dict(self.values)

    def _determine(self, decl: ParameterDecl) -> FormulaValue:
        for source, given in (("supplied", self.supplied), ("report", self.reportValues)):
            if decl.name in given and given[decl.name] is not None:
                return self._typed(decl, fromPython(given[decl.name]), source)
        if decl.required:
            self._error("taviqe:missingParameterValue",
                        "Parameter $%(name)s is required and no value was supplied for it.",
                        name=decl.name)
            return NONE_VALUE
        if decl.selectExpr is None:
            return NONE_VALUE
        reasons = reportTimeReasons(decl.selectExpr)
        if reasons:
            self._error("taviqe:invalidReportTimeExpression",
                        "The select expression of parameter $%(name)s may not be evaluated at report time: %(reasons)s.",
                        name=decl.name, reasons="; ".join(reasons))
            return NONE_VALUE
        try:
            results = evaluateIterations(decl.selectExpr, self.globalCtx, f"${decl.name}")
        except ReportTimeViolation as exc:
            self._error("taviqe:invalidReportTimeExpression",
                        "The select expression of parameter $%(name)s may not be evaluated at report time: %(reason)s.",
                        name=decl.name, reason=str(exc))
            return NONE_VALUE
        except FormulaRuntimeError as exc:
            self._error("taviqe:parameterEvaluationError",
                        "The select expression of parameter $%(name)s raised an error: %(error)s",
                        name=decl.name, error=str(exc))
            return NONE_VALUE
        if len(results) > 1:
            self._error("taviqe:parameterNotSingleValued",
                        "The select expression of parameter $%(name)s produced %(count)s iterations, not one value.",
                        name=decl.name, count=len(results))
            return NONE_VALUE
        if not results or results[0].type == FormulaValueType.NONE:
            return NONE_VALUE           # undetermined, which is not an error
        return self._typed(decl, results[0], "select")

    def _typed(self, decl: ParameterDecl, value: FormulaValue, source: str) -> FormulaValue:
        if decl.asType is None or value.type == FormulaValueType.NONE:
            return value
        try:
            return convertToType(value, decl.asType, self.globalCtx)
        except _TypeMismatch as exc:
            self._error("taviqe:parameterTypeMismatch",
                        "The %(source)s value of parameter $%(name)s does not convert to its type: %(error)s",
                        source=source, name=decl.name, error=str(exc))
            return NONE_VALUE

    def _error(self, code: str, msg: str, **kwargs) -> None:
        mdl = self.globalCtx.txmyMdl
        if hasattr(mdl, "error"):
            mdl.error(code, msg, **kwargs)
        else:
            self.globalCtx.log("ERROR", code, msg % kwargs)


def suppliedFromValidationParameters(parameters) -> Dict[str, Any]:
    """Values supplied as Arelle formula parameters (--parameters, or a test case's)."""
    supplied: Dict[str, Any] = {}
    for paramQn, typedValue in (parameters or {}).items():
        name = getattr(paramQn, "localName", paramQn)   # a QName, or a name already
        if isinstance(typedValue, tuple) and len(typedValue) == 2:
            typedValue = typedValue[1]
        if typedValue not in (None, "null", "None"):
            supplied[str(name)] = typedValue
    return supplied


def parseExpression(text: str):
    """Parse one expression, as the body of a constant."""
    from .FormulaParser import parseFormulaString
    ruleSet = parseFormulaString(f"constant $_reportTimeExpression = {text}\n", "<report-time expression>")
    return ruleSet.constants[-1].expr


# ---------------------------------------------------------------------------
# Entry point for the XbrlModel validator
# ---------------------------------------------------------------------------

class ReportTimeEvaluator:
    """Evaluates parameters and other report-time expressions against a compiled model.

    Used by the XbrlModel validator once the report's facts are materialized and
    before any fact is matched to a cube::

        evaluator = ReportTimeEvaluator(compMdl, rulesetPaths, supplied={"submissionCiks": {"0000320193"}})
        evaluator.declareParameter("requiredContext", "required-context(fewest(eligible()))[2]",
                                   asType="xbrlr:periodString")
        period = toModelValue(evaluator.parameter("requiredContext"))   # None when undetermined
        evaluator.determineAll()   # kept on compMdl for the rule sets run later

    The functions, constants, parameters and namespace declarations of the named
    rule sets are in scope of every expression.
    """

    def __init__(self, compMdl, rulesetPaths: Iterable[str] = (),
                 supplied: Optional[Dict[str, Any]] = None,
                 reportValues: Optional[Dict[str, Any]] = None, cntlr=None):
        from .FormulaRuleSet import FormulaRuleSet, loadRuleSet
        from .FormulaContext import FormulaGlobalContext
        paths = list(rulesetPaths)
        ruleSet = loadRuleSet(paths, cntlr=cntlr) if paths else FormulaRuleSet()
        self.compMdl = compMdl
        self.globalCtx = FormulaGlobalContext(ruleSet, compMdl, cntlr=cntlr)
        self.globalCtx.prepareParameters(supplied, reportValues)

    def declareParameter(self, name: str, select: Optional[str] = None, asType: Any = None,
                         required: bool = False) -> None:
        """Declare a model parameter (a Tavi parameter whose value is an expression)."""
        self.globalCtx.parameters.declare(ParameterDecl(
            name=name, asType=asType, required=required,
            selectExpr=parseExpression(select) if select else None, origin="model"))

    def parameter(self, name: str) -> FormulaValue:
        return self.globalCtx.parameters.value(name)

    def determineAll(self) -> Dict[str, FormulaValue]:
        values = self.globalCtx.parameters.determineAll()
        # Kept for the rule sets evaluated after validation: a parameter is
        # determined once per report.
        self.compMdl._formulaParameterValues = values
        return values

    def evaluate(self, expression: str, asType: Any = None) -> FormulaValue:
        """The value of one report-time expression; none when it is undetermined."""
        # Determined as an anonymous parameter would be, so the same errors apply,
        # but not kept: an expression is not named, and nothing else can read it.
        decl = ParameterDecl(name="_expression", asType=asType,
                             selectExpr=parseExpression(expression), origin="model")
        return self.globalCtx.parameters._determine(decl)
