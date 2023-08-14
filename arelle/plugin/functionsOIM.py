'''
Formula OIM functions plugin.

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from math import isinf
from collections.abc import Callable
from regex import compile as re_compile

from arelle.Aspect import Aspect as Aspect
from arelle.formula import XPathContext
from arelle.FunctionUtil import anytypeArg, stringArg, numericArg, qnameArg
from arelle.ModelDtsObject import ModelResource
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName, qname, datetime
from arelle.ValidateXbrlCalcs import inferredDecimals
from arelle.Version import authorLabel, copyrightLabel
from arelle.formula.XPathParser import OperationDef
from arelle.typing import EmptyTuple
from .saveLoadableOIM import taxonomyRefs, PeriodPattern

def f_fact(
    xc: XPathContext.XPathContext,
    args: XPathContext.ResultStack,
) -> ModelFact:
    if len(args[i]) != 1: raise XPathContext.FunctionArgType(1,"oim:fact")
    modelItem = xc.modelItem(args[0][0])
    if modelItem is not None:
        return modelItem
    raise XPathContext.FunctionArgType(1,"oim:fact")

def f_period(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    if c is None or c.isForeverPeriod:
        return ()
    return c.oimPeriodString

def f_periodType(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    if c is None or c.isForeverPeriod:
        return ()
    elif c.isInstantPeriod:
        return "instant"
    else:
        return "duration"

def f_periodIsInstant(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> bool | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    return c is not None and  c.isInstantPeriod

def f_periodIsDuration(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> bool | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    return c is not None and  c.isStartEndPeriod

def f_periodStart(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    if c is None or c.isForeverPeriod:
        raise XPathContext.XPathException(p, 'oim-fe:NoPeriod', _('Fact has no period'))
    return f"{XmlUtil.dateunionValue(s = c.endDatetime) if c.isInstantPeriod else c.startDatetime}"

def f_periodEnd(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    if c is None or c.isForeverPeriod:
        raise XPathContext.XPathException(p, 'oim-fe:NoPeriod', _('Fact has no period'))
    return f"{XmlUtil.dateunionValue(c.endDatetime)}"

def f_periodInstant(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    if c is None or not c.isInstantPeriod:
        raise XPathContext.XPathException(p, 'oim-fe:PeriodIsNotInstant', _('Fact does not have an instant period'))
    return f"{XmlUtil.dateunionValue(c.instantDatetime)}"

def f_hasDimension(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if not 2 <= len(args) <= 3:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    d = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    excludeDefaults = atomicArg(xc, p, args, 2, "xs:boolean", emptyFallback=False)
    c = f.context
    if d.namespaceURI == "https://xbrl.org/2021":
        if d.localName == "concept":
            return f.concept is not None
        elif d.localName == "period":
            return c is not None and not c.isForeverPeriod
        elif d.localName == "entity":
            return c is not None
        elif d.localName == "unit":
            return f.unit is not None
        elif d.localName == "language":
            return f.concept is not None and f.concept.type.isOimTextFactType and f.xmlLang
        elif d.localName == "noteId":
            return False
    elif c is not None:
        if c.hasDimension(d) or (excludeDefaults == False and d in xc.modelXbrl.qnameDimensionDefaults):
            return True
    return False


def f_dimensionValue(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if not 2 <= len(args) <= 3:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    d = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    excludeDefaults = atomicArg(xc, p, args, 2, "xs:boolean", emptyFallback=False)
    c = f.context
    if d.namespaceURI == "https://xbrl.org/2021":
        if d.localName == "concept":
            return f.qname
        elif d.localName == "period":
            if c is not None and not c.isForeverPeriod:
                return c.oimPeriodString
        elif d.localName == "entity":
            return f_entity(xc, p, contextItem, args)
        elif d.localName == "unit":
            if f.unit:
                u = f.unit.oimString
                if u:
                    return u
        elif d.localName == "language":
            return f.concept is not None and f.concept.type.isOimTextFactType and f.xmlLang
        elif d.localName == "noteId":
            return False
    elif c is not None:
        if c.hasDimension(d):
            dimValue = c.dimOimValue(d)
            if dimValue is not None:
                return dimValue
        elif excludeDefaults == False and d in xc.modelXbrl.qnameDimensionDefaults:
            return xc.modelXbrl.qnameDimensionDefaults[d]
    return ()

def f_taxonomyDefinedDimensions(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    if c is not None:
        if excludeDefaults:
            return c.qnameDims
        else:
            return c.qnameDims.keys |  xc.modelXbrl.qnameDimensionDefaults.keys()
    reutrn ()

def fact_footnotes(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    args: XPathContext.ResultStack,
    defaultLinkrole: str,
    defaultArcrole: str,
) -> ModelRelationshipSet.ModelRelationshipSet:
    linkroleURI = stringArg(xc, args, 2, "xs:string", emptyFallback='')
    if not linkroleURI: linkroleURI = defaultLinkrole
    arcroleURI = stringArg(xc, args, 3, "xs:string", emptyFallback='')
    if not arcroleURI: arcroleURI = defaultArcrole
    return inst.relationshipSet(arcroleURI,linkroleURI)

def f_notes(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if not 1 <= len(args) <= 2:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    rels = fact_footnotes(xc, p, args, None, XbrlConst.factFootnote)
    notes = []
    for rel in rels:
        if isinstance(rel.toModelObject, ModelResource):
            noteFact = FactPrototype(xc, {
                Aspect.CONCEPT: qname("{https://xbrl.org/2021}note"),
                Aspect.PERIOD_TYPE: "forever",
                Aspect.ENTITY_IDENTIFIER: ["https://xbrl.org/2021/entities","NA"]})
            noteFact.value = noteFact.textValue = noteFact.stringValue = rel.toModelObject.value
            noteFact.xmlLang = rel.toModelObject.xmlLang
            notes.append(rel.toModelObject)
    return notes

def f_linkedFacts(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if not 1 <= len(args) <= 3:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    rels = fact_footnotes(xc, p, args, None, "XBRL-footnotes")
    notes = []
    for rel in rels:
        if isinstance(rel.toModelObject, ModelFact):
            notes.append(rel.toModelObject)
    return notes

def factEntityItem(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
    item: int # 0=scheme, 1=identifier, -1=clark name
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    c = f.context
    if c is not None:
        if i == -1:
            return f"{{{c.entityIdentifier[0]}}}{c.entityIdentifier[1]}"
        return c.entityIdentifier[item]
    return ()

def f_entityIdentifier(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return factEntityItem(xc, p, contextItem, args, 1)

def f_entityScheme(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return factEntityItem(xc, p, contextItem, args, 0)

def f_entity(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return factEntityItem(xc, p, contextItem, args, -1)

def f_unitNumerators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    u = f.unit
    if f.unit is not None:
        return f.unit.measures[0]
    return ()

def f_unitDenominators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    u = f.unit
    if f.unit is not None:
        return f.unit.measures[1]
    return ()

def f_unit(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    if f.unit is not None:
        _sUnit = f.unit.oimString
        if _sUnit:
            return _sUnit
    return ()

def f_decimals(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> int | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    f = f_fact(xc, args)
    dec = f.decimals
    if f.isNumeric:
        d = inferredDecimals(f)
        if not isinf(d):
            return d
    return ()

def r_distinctDimensionValues(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    d = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    if d.namespaceURI == "https://xbrl.org/2021":
        if d.localName == "concept":
            return f.qname
        elif d.localName == "period":
            return set(c.oimPeriodString
                       for f in xc.modelXbrl.factsInInstance
                       if f.context is not None and not c.isForeverPeriod)
        elif d.localName == "entity":
            return set(f"{{{s}}}{i}"
                       for f in xc.modelXbrl.factsInInstance
                       if f.context is not None
                       for s,i in f.context.entityIdentifier)
        elif d.localName == "unit":
            return set(f.unit.oimString
                       for f in xc.modelXbrl.factsInInstance
                       if f.unit is not None and f.unit.oimString is not None)
        elif d.localName == "language":
            return set(f.xmlLang
                       for f in xc.modelXbrl.factsInInstance
                       if f.concept.type.isOimTextFactType)
        elif d.localName == "noteId":
            return False
        else:
            raise XPathContext.XPathException(p, 'oim-fe:InvalidDimension', _('Dimension {0} does not match an OIM core dimension').format(d.localName))
    else:
        if d not in xc.modelXbrl.qnameConcepts or not xc.modelXbrl.qnameConcepts[d].isDimensionItem:
            raise XPathContext.XPathException(p, 'oim-fe:InvalidDimension', _('Dimension {0} does not match an OIM core dimension').format(d.localName))
        return set(f.context.dimOimValue(d)
                   for f in modelXbrl.factsInInstance
                   if f.context.dimOimValue(d) is not None)
    return ()

def r_taxonomy(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 0:
        raise XPathContext.FunctionNumArgs()
    return taxonomyRefs(xc.modelXbrl)

clarkPattern = re_compile("[{]([^}]+)[}](.+)")
def r_parseClark(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    clarkName = stringArg(xc, args, 0, "xs:string")
    m = clarkPattern.match(clarkName)
    if not m:
        raise XPathContext.XPathException(p, 'oim-re:InvalidClarkValue', _('Invalid Clark value {0}').format(clarkName))
    return [m.group(1), m.group(2)]

def r_entityStringScheme(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return r_parseClark(xc, p, contextItem, args)[0]

def r_entityStringIdentifier(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return r_parseClark(xc, p, contextItem, args)[1]

def r_periodStringStart(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    isoDate = stringArg(xc, args, 0, "xs:string")
    if not PeriodPattern.match(isoDate):
        raise XPathContext.XPathException(p, 'oim-re:invalidPeriodRepresentation', _('Invalid Period value {0}').format(isoDate))
    return datetime(isoDate.partition("/")[0])

def r_periodStringEnd(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    isoDate = stringArg(xc, args, 0, "xs:string")
    if not PeriodPattern.match(isoDate):
        raise XPathContext.XPathException(p, 'oim-re:invalidPeriodRepresentation', _('Invalid Period value {0}').format(isoDate))
    return datetime(isoDate.Rpartition("/")[2])

def unitStringToQNames(
    xc: XPathContext.XPathContext,
    args: XPathContext.ResultStack,
    num: bool
) -> QName :
    if len(args) != 1:
        raise XPathContext.FunctionNumArgs()
    if not hasattr(xs, "unitPrefixDict"):
        xs.unixPrefixesDict = dict((measure.prefix, measure.namespaceURI)
                                 for unit in xs.modelXbrl.units
                                 for numDenom in unit.measures
                                 for measure in numDenom)
    units = stringArg(xc, args, 0, "xs:string")
    if num:
        units = units.partition("/")[0]
    else:
        units = units.rpartition("/")[2]
    if units[0] == "(": units = units[1:]
    if units[-1] == ")": units = units[:-1]
    units = units.split('*')
    return [qname(u, xs.unixPrefixesDict) for u in units]


def r_unitStringNumerators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return unitStringToQNames(xc, args, true)

def r_unitStringDenominators(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    return unitStringToQNames(xc, args, false)

def r_facts(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 0:
        raise XPathContext.FunctionNumArgs()
    return xc.modelXbrl.factsInInstance

def r_nonFilFacts(
    xc: XPathContext.XPathContext,
    p: OperationDef,
    contextItem: XPathContext.ContextItem,
    args: XPathContext.ResultStack,
) -> str | EmptyTuple:
    if len(args) != 0:
        raise XPathContext.FunctionNumArgs()
    return [f for f in xc.modelXbrl.factsInInstance if not f.isNil]



def oimFunctions() -> dict[
    QName, Callable[[
        XPathContext.XPathContext,
        OperationDef,
        XPathContext.ContextItem,
        XPathContext.ResultStack,
    ], float | EmptyTuple]
]:
    return {
        qname("{http://www.xbrl.org/YYYY/f}f:period"): f_period,
        qname("{http://www.xbrl.org/YYYY/f}f:period-type"): f_periodType,
        qname("{http://www.xbrl.org/YYYY/f}f:period-is-instant"): f_periodIsInstant,
        qname("{http://www.xbrl.org/YYYY/f}f:period-is-duration"): f_periodIsDuration,
        qname("{http://www.xbrl.org/YYYY/f}f:period-start"): f_periodStart,
        qname("{http://www.xbrl.org/YYYY/f}f:period-end"): f_periodEnd,
        qname("{http://www.xbrl.org/YYYY/f}f:period-instant"): f_periodInstant,
        qname("{http://www.xbrl.org/YYYY/f}f:has-dimension"): f_hasDimension,
        qname("{http://www.xbrl.org/YYYY/f}f:dimension-value"): f_dimensionValue,
        qname("{http://www.xbrl.org/YYYY/f}f:taxonomy-defined-dimensions"): f_taxonomyDefinedDimensions,
        qname("{http://www.xbrl.org/YYYY/f}f:notes"): f_notes,
        qname("{http://www.xbrl.org/YYYY/f}f:linked-facts"): f_linkedFacts,
        qname("{http://www.xbrl.org/YYYY/f}f:entity-identifier"): f_entityIdentifier,
        qname("{http://www.xbrl.org/YYYY/f}f:entity-scheme"): f_entityScheme,
        qname("{http://www.xbrl.org/YYYY/f}f:entity"): f_entity,
        qname("{http://www.xbrl.org/YYYY/f}f:unit-numerators"): f_unitNumerators,
        qname("{http://www.xbrl.org/YYYY/f}f:unit-denominators"): f_unitDenominators,
        qname("{http://www.xbrl.org/YYYY/f}f:unit"): f_unit,
        qname("{http://www.xbrl.org/YYYY/f}f:decimals"): f_decimals,
        qname("{http://www.xbrl.org/YYYY/r}r:distinct-dimension-values"): r_distinctDimensionValues,
        qname("{http://www.xbrl.org/YYYY/r}r:taxonomy"): r_taxonomy,
        qname("{http://www.xbrl.org/YYYY/r}r:parse-clark"): r_parseClark,
        qname("{http://www.xbrl.org/YYYY/r}r:entity-string-scheme"): r_entityStringScheme,
        qname("{http://www.xbrl.org/YYYY/r}r:entity-string-identifier"): r_entityStringIdentifier,
        qname("{http://www.xbrl.org/YYYY/r}r:period-string-start"): r_periodStringStart,
        qname("{http://www.xbrl.org/YYYY/r}r:period-string-end"): r_periodStringEnd,
        qname("{http://www.xbrl.org/YYYY/r}r:unit-string-numerators"): r_unitStringNumerators,
        qname("{http://www.xbrl.org/YYYY/r}r:unit-string-denominators"): r_unitStringDenominators,
        qname("{http://www.xbrl.org/YYYY/r}r:facts"): r_facts,
        qname("{http://www.xbrl.org/YYYY/r}r:non-nil-facts"): r_nonNilFacts,
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
