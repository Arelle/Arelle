'''
Formula OIM functions plugin.

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from regex import compile as rc_compile
from collections.abc import Callable

from arelle.formula import XPathContext
from arelle.formula.XPathContext import XPathException as OIMFunctionException
from arelle.FunctionUtil import qnameArg, stringArg, anytypeArg
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName, qname, AnyURI, DateTime, DATETIME
from arelle.Version import authorLabel, copyrightLabel
from arelle.formula.XPathParser import OperationDef
from arelle.typing import EmptyTuple
from arelle.plugin.loadFromOIM import PeriodPattern
from arelle.plugin.saveLoadableOIM import oimPeriodValue, oimUnitValue

ClarkPattern = rc_compile(r"\{([^}]+)\}(.+)$")
ExpandedUnitStrPattern = rc_compile(r"\{\w+\}\w+(\ \{\w+\}\w+)*(\ /\ \{\w+\}\w+(\ \{\w+\}\w+)*)?$")

def checkArgs(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    args: XPathContext.ResultStack,
    numArgs: int,
) -> None:
    if not xc.oimMode:
        raise OIMFunctionException(p, "oimfe:oimIncompatibleRegistryFunction",
                                   _("Function {} requires OIM-compatible mode.").format(p.name))
    if len(args) != numArgs: raise XPathContext.FunctionNumArgs()

def r_distinct_dimension_values(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> list[Any] | EmptyTuple:
    checkArgs(xc, p, args, 1)
    qn = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    if not (qn in qnOimCoreDimensions or
            (qn in xc.modelXbrl.qnameConcepts and xc.modelXbrl.qnameConcepts[qn].isDimensionItem)):
        raise OIMFunctionException(p, "re:invalidDimension",
                                   _("QName {} does not correspond to either an OIM Core Dimension, or a taxonomy-defined dimension defined in the DTS of the report.")
                                   .format(qn))
    if qn == qnOimConcept:
        return xc.modelXbrl.factsByQname.keys()
    if qn == qnOimEntity:
        return set(qname(*c.entityIdentifier) for c in xc.modelXbrl.contexts.values())
    if qn == qnOimPeriod:
        return set(oimPeriodValue(cntx) for cntx in xc.modelXbrl.contexts.values())
    if qn == qnOimUnit:
        return set(oimUnitValue(unit, lambda u: u.clarkNotation, " ", " / ", False)
                   for unit in xc.modelXbrl.units.values())
    if qn == qnOimLanguage:
        return set(f.xmlLang for f in facts if f.xmlLang)
    if qn == qnOimNoteId:
        pass # TBD
    if qn in xc.modelXbrl.qnameConcepts:
        return set(d.dimensionQname if d.isExplicit else d.typedMember.stringVaue
                   for c in self.contexts.values()  # use contextsInUse?  slower?
                   for d in cntx.qnameDims.values())
    return ()

def r_default_dimension_value(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> QName | EmptyTuple:
    checkArgs(xc, p, args, 1)
    qn = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    if qn in qnOimCoreDimensions:
        return ()
    if not (qn in xc.modelXbrl.qnameConcepts and xc.modelXbrl.qnameConcepts[qn].isDimensionItem):
        raise OIMFunctionException(p, "re:invalidDimension",
                                   _("QName {} does not correspond to either an OIM Core Dimension, or a taxonomy-defined dimension defined in the DTS of the report.")
                                   .format(qn))
    return xc.modelXbrl.qnameDimensionDefaults.get(dimQname, ())

def r_defaulted_dimensions(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> QName | EmptyTuple:
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    return xc.modelXbrl.qnameDimensionDefaults.keys()

def r_parse_clark(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> tuple[AnyURI, str] | EmptyTuple:
    checkArgs(xc, p, args, 1)
    cn = stringArg(xc, p, args, 0, 'ClarkName', emptyFallback=None)
    match = ClarkPattern.match(cn)
    if not match:
        raise OIMFunctionException(p, "re:invalidClarkValue",
                                   _("Provided value \"{}\"is not a valid Clark Notation string.")
                                   .format(cn))
    return tuple(match.group(1), match.group(2))

def r_entity_string_scheme(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> AnyURI | EmptyTuple:
    return r_parse_clark(xc, p, contextItem, args)[0]

def r_entity_string_identifier(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return r_parse_clark(xc, p, contextItem, args)[1]

def r_period_string(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
    start: bool,
) -> DateTime | EmptyTuple:
    checkArgs(xc, p, args, 1)
    period = stringArg(xc, p, args, 0, 'Period String Representation', emptyFallback=None)
    match = PeriodPattern.match(period)
    if not match:
        raise OIMFunctionException(p, "re:invalidPeriodRepresentation",
                                   _("Provided value \"{}\"is not a valid Period String Representation string.")
                                   .format(period))
    _start, _sep, _end = period.rpartition('/')
    if _start == _end or not _start or not start:
        return dateTime(_end, type=DATETIME)
    else:
        return dateTime(_start, type=DATETIME)

def r_period_string_start(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> DateTime | EmptyTuple:
    return r_period_string(xc, p, contextItem, args, true)


def r_period_string_end(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> DateTime | EmptyTuple:
    return r_period_string(xc, p, contextItem, args, false)

def r_unit_string(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
    numerator: bool,
) -> list[QName] | EmptyTuple:
    checkArgs(xc, p, args, 1)
    expandedUnitStr = stringArg(xc, p, args, 0, 'Expanded Unit String', emptyFallback=None)
    if not expandedUnitStr:
        return [XbrlConst.qnXbrliPure]
    match = ExpandedUnitStrPattern.match(expandedUnitStr)
    if not match:
        raise OIMFunctionException(p, "re:invalidExpandedUnitStringRepresentation",
                                   _("Provided value \"{}\"is not a valid Expanded Unit String.")
                                   .format(expandedUnitStr))
    _num, _sep, _denom = expandedUnitStr.rpartition(' / ')
    return [qname(m) for m in (_num if numerator else _denom).split()]

def r_unit_string_numerators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> list[QName] | EmptyTuple:
    return r_unit_string(xc, p, contextItem, args, true)

def r_unit_string_denominators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> list[QName] | EmptyTuple:
    return r_unit_string(xc, p, contextItem, args, false)

def r_facts(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> list[ModelFact]:
    return xc.modelXbrl.facts

def r_fact_with_id(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> ModelFact | EmptyTuple:
    checkArgs(xc, p, args, 1)
    id = stringArg(xc, p, args, 0, 'Id', emptyFallback=None)
    return xc.modelXbrl.factById.get(id, ())

def f_period(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.context is not None:
        return oimPeriodValue(fact.context)
    return ()

def f_period_type(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.context is not None:
        if fact.context.isStartEndPeriod or fact.context.isForeverPeriod:
            return "duration"
        if fact.context.isInstantPeriod:
            return "instant"
    return ()

def f_period_is_instant(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> bool | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    return fact.context is not None and fact.context.isInstantPeriod

def f_period_is_duration(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> bool | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    return fact.context is not None and (fact.context.isStartEndPeriod or fact.context.isForeverPeriod)

def f_period_start(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> DateTime | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.context is None:
        raise OIMFunctionException(p, "fe:noPeriod",
                                   _("Fact has no period."))
    return fact.context.startDatetime if fact.context.isStartEndPeriod else fact.context.instantDatetime

def f_period_end(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> DateTime | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.context is None:
        raise OIMFunctionException(p, "fe:noPeriod",
                                   _("Fact has no period."))
    return fact.context.endDatetime


def f_period_instant(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> DateTime | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.context is None or not fact.context.isInstantPeriod:
        raise OIMFunctionException(p, "fe:periodIsNotInstant",
                                   _("Fact does not have an instant period."))
    return fact.context.instantDatetime

def f_has_dimension(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> bool | EmptyTuple:
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    qn = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    if qn == qnOimConcept:
        return True
    if qn == qnOimEntity:
        return fact.context is not None
    if qn == qnOimPeriod:
        return fact.context is not None
    if qn == qnOimUnit:
        return fact.isNumeric and fact.unit is not None # what about xbrli:pure?
    if qn == qnOimLanguage:
        return f.xmlLang
    if qn == qnOimNoteId:
        return None # TBD
    return fact.context is not None and qn in cntx.qnameDims

def f_dimension_value(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> AnyType | EmptyTuple:
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    qn = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    if qn == qnOimConcept:
        return fact.qname
    if fact.context is None:
        return ()
    cntx = fact.context
    if qn == qnOimEntity:
        return qname(*fact.context.entityIdentifier)
    if qn == qnOimPeriod:
        return oimPeriodValue(cntx)
    if qn == qnOimUnit:
        if fact.isNumeric and fact.unit is not None:
            return oimUnitValue(fact.unit, lambda u: u.clarkNotation, " ", " / ", False)
    if qn == qnOimLanguage and f.xmlLang:
        return f.xmlLang
    if qn == qnOimNoteId:
        return () # TBD
    if qn in cntx.qnameDims:
        d = cntx[qn]
        return d.dimensionQname if d.isExplicit else d.typedMember.stringVaue
    return ()

def f_taxonomy_defined_dimensions(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> list[QName] | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if fact.context is not None:
        return fact.context.qnameDims.keys()
    return ()

def f_notes(xc, p, args):
    return ()  # TBD

def f_linked_facts(xc, p, args):
    return ()

def f_entity(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
    identifier: bool,
) -> str | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.context is not None:
        return fact.context.entityIdentifier[identifier]
    return ()

def f_entity_identifier(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return f_entity(xc, p, args, True)


def f_entity_scheme(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return f_entity(xc, p, args, False)

def f_unit_measures(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
    denominator: bool,
) -> list[QName] | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.isNumeric and fact.unit is not None:
        return fact.unit.measures[denominator]

def f_unit_numerators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> list[QName] | EmptyTuple:
    return f_unit_measures(xc, p, args, False)

def f_unit_denominators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> list[QName] | EmptyTuple:
    return f_unit_measures(xc, p, args, True)

def f_unit(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> int | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.isNumeric and fact.unit is not None:
        return oimUnitValue(fact.unit, lambda u: u.clarkNotation, " ", " / ", False)
    return ()

def f_decimals(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> int | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    if fact.isNumeric and fact.decimals not in (None, "INF"):
        return fact.decimals
    return ()

def f_id(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    checkArgs(xc, p, args, 1)
    fact = anytypeArg(xc, args, 0, "Fact", missingArgFallback=None)
    if not isinstance(fact, ModelFact): raise XPathContext.FunctionArgType(0,"xbrl:item")
    return fact.id

def oimFunctions() -> dict[
    QName, Callable[[
        XPathContext.XPathContext,
        OperationDef,
        XPathContext.ContextItem,
        XPathContext.ResultStack,
    ], float | EmptyTuple]
]:
    return {
        # report functions
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}default-dimension-value"): r_default_dimension_value,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}defaulted-dimensions"): r_defaulted_dimensions,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}parse-clark"): r_parse_clark,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}entity-string-scheme"): r_entity_string_scheme,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}entity-string-identifier"): r_entity_string_identifier,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}period-string-start"): r_period_string_start,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}period-string-end"): r_period_string_end,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}unit-string-numerators"): r_unit_string_numerators,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}unit-string-denominators"): r_unit_string_denominators,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}facts"): r_facts,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/report}fact-with-id"): r_fact_with_id,
        # fact functions
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}period"): f_period,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}period-type"): f_period_type,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}period-is-instant"): f_period_is_instant,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}period-is-duration"): f_period_is_duration,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}period-start"): f_period_start,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}period-end"): f_period_end,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}period-instant"): f_period_instant,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}has-dimension"): f_has_dimension,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}dimension-value"): f_dimension_value,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}taxonomy-defined-dimensions"): f_taxonomy_defined_dimensions,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}notes"): f_notes,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}linked-facts"): f_linked_facts,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}entity-identifier"): f_entity_identifier,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}entity-scheme"): f_entity_scheme,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}unit-numerators"): f_unit_numerators,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}unit-denominators"): f_unit_denominators,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}unit"): f_unit,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}decimals"): f_decimals,
        qname("{https://xbrl.org/WGWD/YYYY-MM-DD/function/fact}id"): f_id,
    }


__pluginInfo__ = {
    'name': 'Formula OIM Functions',
    'version': '1.0',
    'description': "This plug-in adds formula OIM functions.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Formula.CustomFunctions': oimFunctions,
}
