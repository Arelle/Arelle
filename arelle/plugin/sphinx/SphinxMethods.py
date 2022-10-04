'''
sphinxMethods processes the Sphinx language in the context of an XBRL DTS and instance.

See COPYRIGHT.md for copyright information.

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer
(c) Copyright 2012 CoreFiling, Oxford UK.
Sphinx copyright applies to the Sphinx language, not to this software.
Workiva, Inc. conveys neither rights nor license for the Sphinx language.
'''

from math import exp, fabs, isinf, isnan, log, log10, pow, sqrt
import datetime
from arelle.ModelDtsObject import ModelConcept, ModelRelationship
from arelle.ModelDocument import Type
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import QName, dayTimeDuration, DayTimeDuration
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrlCalcs import inferredDecimals, inferredPrecision, roundValue
from arelle import XbrlConst, XmlUtil
from numbers import Number
evaluate = None # initialized at end
SphinxException = None
UNBOUND = None
NONE = None


def moduleInit():
    global evaluate, SphinxException, UNBOUND, NONE
    from .SphinxEvaluator import evaluate, SphinxException, UNBOUND, NONE

class Balance(): # fake class for balance type
    pass

class PeriodType(): # fake class for period type
    pass

class Period():
    def __init__(self, start=None, end=None):
        self.start = start
        self.end = end
    @property
    def isForever(self):
        return self.start is None and self.end is None
    @property
    def isInstant(self):
        return self.start is None and self.end is not None
    @property
    def isStartEnd(self):
        return self.start is not None and self.end is not None
    def __repr__(self):
        return "({0},{1})".format(self.start, self.end)
    def __eq__(self, other):
        if isinstance(other, Period):
            return self.start == other.start and self.end == other.end
        return False
    def __ne__(self, other):
        if isinstance(other, Period):
            return self.start != other.start or self.end != other.end
        return False
    def __lt__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end < other.end
            elif other.isStartEnd:
                return self.end <= other.start
        elif self.isStartEnd:
            if other.isInstant:
                return self.end < other.end
            elif other.isStartEnd:
                return self.end <= other.start
        return False
    def __le__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end <= other.end
            elif other.isStartEnd:
                return self.end <= other.start or self == other
        elif self.isStartEnd:
            if other.isInstant:
                return self.end <= other.end
            elif other.isStartEnd:
                return self.end <= other.start or self == other
        return False
    def __gt__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end > other.end
            elif other.isStartEnd:
                return self.start > other.end
        elif self.isStartEnd:
            if other.isInstant:
                return self.end > other.end
            elif other.isStartEnd:
                return self.start > other.end
        return False
    def __ge__(self, other):
        if not isinstance(other, Period):
            return False
        if self.isInstant:
            if other.isInstant:
                return self.end >= other.end
            elif other.isStartEnd:
                return self.start >= other.start or self == other
        elif self.isStartEnd:
            if other.isInstant:
                return self.end >= other.end
            elif other.isStartEnd:
                return self.start >= other.start or self == other
        return False


def hasArg(node, sphinxContext, args, i):
    if i >= len(args):
        raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                              _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                                name=node.name, required=i, provided=len(node.args))

def numericArg(node, sphinxContext, args, i):
    hasArg(node, sphinxContext, args, i)
    arg = args[i]
    if isinstance(arg, Number):
        return arg
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s numeric parameter %(num)s is not a number: %(value)s"),
                          name=node.name, num=i, value=arg)

def numericArgs(node, sphinxContext, args, expectedArgsLen):
    if expectedArgsLen != len(args):
        raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                              _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                              name=node.name, required=expectedArgsLen, provided=len(args))
    numArgs = []
    for i, arg in enumerate(args):
        if i >= expectedArgsLen:
            break
        value = evaluate(arg, sphinxContext, args, value=True)
        if not isinstance(value, Number):
            raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                                  _("Function %(name)s numeric parameters but %(num)s is not numeric: %(value)s"),
                                  num=i, value=value)
            value = 0
        numArgs.append(value)
    for i in range(i, expectedArgsLen):
        numArgs.append(0)
    return numArgs

def strArg(node, sphinxContext, args, i):
    hasArg(node, sphinxContext, args, i)
    arg = args[i]
    if isinstance(arg, str):
        return arg
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s string parameter %(num)s is not a string: %(value)s"),
                          name=node.name, num=i, value=arg)

def strArgs(node, sphinxContext, args, expectedArgsLen):
    if expectedArgsLen != len(args):
        raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                              _("Function %(name)s requires %(required)s parameters but %(provided)s are provided"),
                              name=node.name, required=expectedArgsLen, provided=len(args))
    strArgs = []
    for i, arg in enumerate(args):
        if i >= expectedArgsLen:
            break
        value = evaluate(arg, sphinxContext, value=True)
        if not isinstance(value, str):
            raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                                  _("Function %(name)s string parameters but %(num)s is not numeric: %(value)s"),
                                  name=node.name, num=i, value=value)
            value = 0
        strArgs.append(value)
    for i in range(i, expectedArgsLen):
        strArgs.append(0)
    return strArgs

def factArg(node, sphinxContext, args, i):
    hasArg(node, sphinxContext, args, i)
    fact = evaluate(args[i], sphinxContext, value=False, hsBoundFact=True)
    if isinstance(fact, ModelFact):
        return fact
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s fact parameter %(num)s is not a fact: %(value)s"),
                          name=node.name,
                          num=i, value=fact)

def conceptOrFactArg(node, sphinxContext, args, i):
    hasArg(node, sphinxContext, args, i)
    conceptOrFact = evaluate(args[i], sphinxContext, value=False)
    if isinstance(conceptOrFact, (ModelConcept,ModelFact)):
        return conceptOrFact
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s parameter %(num)s is not a concept or fact: %(value)s"),
                          name=node.name,
                          num=i, value=conceptOrFact)

def conceptArg(node, sphinxContext, args, i):
    hasArg(node, sphinxContext, args, i)
    concept = evaluate(args[i], sphinxContext, value=False)
    if isinstance(concept, ModelConcept):
        return concept
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s fact parameter %(num)s is not a concept: %(value)s"),
                          name=node.name,
                          num=i, value=concept)

def dtsArg(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    dts = evaluate(args[0], sphinxContext, value=False)
    if isinstance(dts, ModelXbrl):
        return dts
    raise SphinxException(node, "sphinx.methodArgumentsMismatch",
                          _("Method %(name)s taxonomy parameter is not a DTS: %(value)s"),
                          name=node.name, value=dts)

def networkArg(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    network = evaluate(args[0], sphinxContext, value=False)
    if isinstance(network, ModelRelationshipSet):
        return network
    raise SphinxException(node, "sphinx.methodArgumentsMismatch",
                          _("Method %(name)s taxonomy parameter is not a network: %(value)s"),
                          name=node.name, value=network)

def networkConceptArg(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 1)
    arg = args[1]
    if isinstance(arg, QName):
        arg = network.modelXbrl.qnameConcepts.get(arg, NONE)
    if isinstance(arg, ModelConcept):
        return arg
    raise SphinxException(node, "sphinx.methodArgumentsMismatch",
                          _("Method %(name)s network concept parameter is not a concept: %(value)s"),
                          name=node.name, value=arg)

def relationshipArg(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    rel = evaluate(args[0], sphinxContext, value=False)
    if isinstance(rel, ModelRelationship):
        return rel
    raise SphinxException(node, "sphinx.methodArgumentsMismatch",
                          _("Method %(name)s taxonomy parameter is not a relationship: %(value)s"),
                          name=node.name, value=rel)

# numeric functions
NaN = float("NaN")
POSINF = float("INF")
NEGINF = float("-INF")

def _addTimePeriod(node, sphinxContext, args, subtract=False):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    hasArg(node, sphinxContext, args, 1)
    duration = args[1]
    if isinstance(arg, Period) and arg.isInstant and isinstance(duration, DayTimeDuration):
        try:
            return Period(None, (arg.end - duration) if subtract else (arg.end + duration))
        except ValueError:
            raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                                  _("Function %(name)s argument is not an day time duration %(value)s"),
                                  name=node.name, value=duration)
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not an instant period %(value)s"),
                          name=node.name, value=arg)

def _abs(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 1)
    return fabs(args[0])

def _balance(node, sphinxContext, args):
    if len(node.args) == 1 and node.args[0] is None:
        return Balance()
    fact = factArg(node, sphinxContext, args, 0)
    return fact.balance

def _booleanFunction(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    # >>>> arg can be XML, what does this mean???
    if arg == "true":
        return True
    if args[0] == "false":
        return False
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s fact parameter %(num)s is not \"true\" or \"false\": %(value)s"),
                          name=node.name,
                          num=0, value=arg)

def _concept(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    if isinstance(args[0], ModelXbrl):
        dts = dtsArg(node, sphinxContext, args)
        hasArg(node, sphinxContext, args, 1)
        return dts.qnameConcepts.get(args[1], UNBOUND)
    fact = factArg(node, sphinxContext, args, 0)
    return fact.concept


def _concepts(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    if isinstance(args[0], ModelXbrl):  # taxonomy concepts
        dts = dtsArg(node, sphinxContext, args)
        return set(concept
                   for concept in dts.qnameConcepts.values()
                   if concept.isItem or concept.isTuple)
    # otherwise must be network concepts
    network = networkArg(node, sphinxContext, args)
    return network.toModelObjects.keys() | network.fromModelObjects.keys()


def _contains(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 1)
    collection = args[0]
    arg = args[1]
    # period contains
    if isinstance(arg, (Period, datetime.datetime)) and isinstance(collection, Period):
        if collection.isForever:
            return True
        if collection.isDuration:
            if isinstance(arg, datetime):
                return collection.start <= arg <= collection.end
            elif arg.isInstant:
                return collection.start <= arg.end <= collection.end
            elif arg.isDuration:
                return collection.start <= arg.start <= collection.end and collection.start <= arg.end <= collection.end
        if collection.isInstant:
            if isinstance(arg, datetime):
                return collection.end == arg
            if arg.isInstant:
                return collection.end == arg.end
        return False
    # non-period contains
    if isinstance(collection, (tuple, list, set, str)):
        return arg in collection
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a collection %(value)s"),
                          name=node.name, value=collection)

def _credit(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    if isinstance(args[0], Balance):
        return "credit"
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a ::balance %(value)s"),
                          name=node.name, value=args[0])

def _days(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    if isinstance(arg, Period):
        if arg.isInstant:
            return 0
        elif arg.isForever:
            return float("inf")
        return (arg.end - arg.start).days
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a period %(value)s"),
                          name=node.name, value=arg)

def _debit(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    if isinstance(args[0], Balance):
        return "debit"
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a ::balance %(value)s"),
                          name=node.name, value=args[0])

def _decimals(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return inferredDecimals(fact)

def _dimension(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    hasArg(node, sphinxContext, args, 1)
    dimQName = args[1]
    context = fact.context
    if context is not None and dimQName in context.qnameDims:
        modelDimension = context.qnameDims[dimQName]
        if modelDimension.isExplicit:
            return modelDimension.memberQname
        else:
            return modelDimension.typedMember
    return NONE

def _dtsDocumentLocations(node, sphinxContext, args):
    dts = dtsArg(node, sphinxContext, args)
    return set(modelDocument.uri
               for modelDocument in dts.urlDocs.values()
               if modelDocument.type in (Type.SCHEMA, Type.LINKBASE))

def _duration(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    if isinstance(args[0], PeriodType):
        return "duration"
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a ::period-type %(value)s"),
                          name=node.name, value=args[0])

def _durationFunction(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 1)
    startArg = args[0]
    if isinstance(startArg, str):
        startDateTime = Period(None, XmlUtil.datetimeValue(startArg, none=NONE))
    elif isinstance(startArg, datetime.datetime):
        startDateTime = startArg
    elif isinstance(arg, datetime.date):
        startDateTime = datetime.date(startArg.year, startArg.month, startArg.day)
    endArg = args[1]
    if isinstance(endArg, str):
        endDateTime = Period(None, XmlUtil.datetimeValue(startArg, addOneDay=True, none=NONE))
    elif isinstance(endArg, datetime.datetime):
        endDateTime = endArg
    elif isinstance(endArg, datetime.date):
        endDateTime = datetime.date(endArg.year, endArg.month, endArg.day) + datetime.timedelta(1)
    if (startDateTime and endDateTime):
        return Period(startDateTime, endDateTime)
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s requires two argument that are a date or datetime string or value: %(start)s and %(end)s", ),
                          name=node.name, start=startArg, end=endArg)

def _endDate(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    if isinstance(arg, Period):
        if arg.isForever:
            return UNBOUND
        return arg.end
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a period %(value)s"),
                          name=node.name, value=arg)

def _endsWith(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    suffix = strArgs(node, sphinxContext, args, 1)
    return value.endswith(suffix)

def _entityMethod(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    if fact.context is not None:
        return fact.context.entityIdentifier
    else:
        return UNBOUND

def _entityFunction(node, sphinxContext, args):
    args = strArgs(node, sphinxContext, args, 2)
    return (args[0], args[1])

def _exp(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 1)
    x = args[0]
    if isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == NEGINF: return 0
    return exp(x)

def _foreverFunction(node, sphinxContext, args):
    return Period(None, None)

def _identifier(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    if isinstance(arg, tuple) and len(arg) == 2:
        return arg[1]
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not an entity identifier %(value)s"),
                          name=node.name, value=arg)

def _hasDecimals(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return fact.decimals is not None

def _indexOf(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    arg = strArgs(node, sphinxContext, args, 1)
    return value.find(arg)

def _hasPrecision(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return fact.precision is not None

def _instant(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    if isinstance(args[0], PeriodType):
        return "instant"
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a ::period-type %(value)s"),
                          name=node.name, value=args[0])

def _instantFunction(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    if isinstance(arg, str):
        instDateTime = Period(None, XmlUtil.datetimeValue(arg, addOneDay=True, none=NONE))
        if instDateTime:  # none if date is not valid
            return instDateTime
    elif isinstance(arg, datetime.datetime):
        return Period(None, arg)
    elif isinstance(arg, datetime.date): # must be turned into midnight of the day reported
        return Period(None, datetime.date(arg.year, arg.month, arg.day) + datetime.timedelta(1))
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a date or datetime string or value %(value)s"),
                          name=node.name, value=arg)

def _isForever(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    if isinstance(arg, Period):
        return arg.isForever
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a period %(value)s"),
                          name=node.name, value=arg)

def _isMonetary(node, sphinxContext, args):
    conceptOrFact = conceptOrFactArg(node, sphinxContext, args, 0)
    if isinstance(conceptOrFact, ModelFact):
        return conceptOrFact.concept.isMonetary
    else:
        return conceptOrFact.isMonetary

def _isNumeric(node, sphinxContext, args):
    conceptOrFact = conceptOrFactArg(node, sphinxContext, args, 0)
    return conceptOrFact.isNumeric

def _lastIndexOf(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    arg = strArgs(node, sphinxContext, args, 1)
    return value.rfind(arg)

def _length(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    return len(value)

def _lowerCase(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    return value.lower()

def _ln(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 1)
    x = args[0]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == 0: return NEGINF
    return log(x)

def _localPart(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    qn = args[0]
    if isinstance(qn, QName):
        return qn.localName
    elif isinstance(qn, str):
        return qn
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a QName %(value)s"),
                          name=node.name, value=args[0])

def _log(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 2)
    x = args[0]
    base = args[1]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == 0: return POSINF
    if base == 0 or base == POSINF: return 0
    if base == 10: return log10(x)
    return log(x, base)

def _log10(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 1)
    x = args[0]
    base = args[1]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    if x == 0: return POSINF
    return log10(x)

def _name(node, sphinxContext, args):
    concept = conceptArg(node, sphinxContext, args, 0)
    return concept.qname

def _numberFunction(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    try:
        return float(arg)
    except Exception as ex:
        raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                              _("Function %(name)s argument: %(value)s, error converting to number: %(error)s"),
                              name=node.name, value=arg, error=str(ex))
def _period(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    context = fact.context
    if context is not None:
        if context.isForeverPeriod:
            return Period()
        if context.isStartEndPeriod:
            return Period(context.startDatetime, context.endDatetime)
        return Period(None, context.instantDatetime)
    return NONE

def _periodType(node, sphinxContext, args):
    if len(node.args) == 1 and node.args[0] is None:
        return PeriodType()
    hasArg(node, sphinxContext, args, 0)
    if isinstance(args[0], Period):
        arg = args[0]
        if arg.isForever:
            return "forever"
        elif arg.isStartEnd:
            return "duration"
        return "instant"
    elif args[0] is NONE: # special case, such as for tuples
        return "none"
    concept = conceptArg(node, sphinxContext, args, 0)
    return concept.periodType

def _power(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 2)
    x = args[0]
    exp = args[1]
    if isnan(exp) or (isnan(x) and exp != 0) or (isinf(exp) and x in (1, -1)):
        return NaN
    if ((x == POSINF and exp > 0) or
        (x == NEGINF and x > 0 and not x & 1) or
        (exp == POSINF and not -1 <= x <= 1) or
        (x == 0 and exp < 0)):
        return POSINF
    if x == NEGINF and x > 0 and x & 1:
        return NEGINF
    return pow(x, exp)

def _precision(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return inferredPrecision(fact)

def _primary(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return fact.qname

def _replace(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    old = strArgs(node, sphinxContext, args, 1)
    new = strArgs(node, sphinxContext, args, 2)
    return value.replace(old, new)

def _roundItem(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return roundValue(fact.xValue, decimals=fact.decimals, precision=fact.precision)

def _roundDecimals(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 2)
    return roundValue(args[0], decmials=args[1])

def _roundPrecision(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 2)
    return roundValue(args[0], precision=args[1])

def _schemaTypeFunction(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    schemaTypeQn = args[0]
    return schemaTypeQn

def _schemaTypeMethod(node, sphinxContext, args):
    concept = conceptArg(node, sphinxContext, args, 0)
    return concept.typeQname

def _signum(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 1)
    x = args[0]
    if x == 0 or isnan(x): return 0
    if x > 0: return 1
    return -1

def _scenario(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return fact.context.segment.nonDimValues("scenario")

def _scheme(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    if isinstance(arg, tuple) and len(arg) == 2:
        return arg[0]
    raise SphinxException(node, "sphinx.methodArgumentsMismatch",
                          _("Method %(name)s argument is not an entity identifier %(value)s"),
                          name=node.name, value=arg)

def _segment(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return fact.context.segment.nonDimValues("segment")

def _size(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    collection = args[0]
    if isinstance(collection, (tuple, list, set)):
        return len(collection)
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a collection %(value)s"),
                          name=node.name, value=collection)

def _sqrt(node, sphinxContext, args):
    args = numericArgs(node, sphinxContext, args, 1)
    x = args[0]
    if x < 0 or isnan(x): return NaN
    if x == POSINF: return POSINF
    return sqrt(x)

def _startDate(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    arg = args[0]
    if isinstance(arg, Period):
        if arg.isForever:
            return UNBOUND
        if arg.isDuration:
            return arg.start
        return arg.end
    raise SphinxException(node, "sphinx.functionArgumentsMismatch",
                          _("Function %(name)s argument is not a period %(value)s"),
                          name=node.name, value=arg)

def _startsWith(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    suffix = strArgs(node, sphinxContext, args, 1)
    return value.startswith(suffix)

def _substring(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    start = strArgs(node, sphinxContext, args, 1)
    end = strArgs(node, sphinxContext, args, 2)
    if isinf(start): start = len(value)
    if isinf(end): end = len(value)
    return value[start:end]

def _subtractTimePeriod(node, sphinxContext, args):
    return _addTimePeriod(node, sphinxContext, args, subtract=True)

def _taxonomy(node, sphinxContext, args):
    return sphinxContext.modelXbrl

def _timePeriodFunction(node, sphinxContext, args):
    duration = strArgs(node, sphinxContext, args, 0)
    return dayTimeDuration(duration)

nowUTC = datetime.datetime.utcnow()
todayUTC = datetime.date(nowUTC.year, nowUTC.month, nowUTC.day)

def _todayUTC(node, sphinxContext, args):
    return todayUTC

def _timeDuration(node, sphinxContext, args):
    duration = strArgs(node, sphinxContext, args, 0)
    return dayTimeDuration(duration)

def toCollection(node, sphinxContext, args, collectionCreator):
    hasArg(node, sphinxContext, args, 0)
    collection = args[0]
    if isinstance(collection, (tuple, list, set)):
        return collectionCreator(collection)
    raise SphinxException(node, "sphinx.methodArgumentsMismatch",
                          _("Method %(name)s argument is not a collection %(value)s"),
                          name=node.name, value=collection)

def _toList(node, sphinxContext, args):
    return toCollection(node, sphinxContext, args, list)

def _toSet(node, sphinxContext, args):
    return toCollection(node, sphinxContext, args, set)

def _trim(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    return value.strip()

def _tuple(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    parentModelObject = fact.getparent()
    parentQn = parentModelObject.qname
    if parentQn == XbrlConst.qnXbrliXbrl:
        return NONE
    return parentQn

def _unitMethod(node, sphinxContext, args):
    fact = factArg(node, sphinxContext, args, 0)
    return fact.unit.measures

def _unitFunction(node, sphinxContext, args):
    hasArg(node, sphinxContext, args, 0)
    unitQn = args[0]
    return ([unitQn],[])

def _upperCase(node, sphinxContext, args):
    value = strArgs(node, sphinxContext, args, 0)
    return value.upper()

def _xbrlTypeMethod(node, sphinxContext, args):
    concept = conceptArg(node, sphinxContext, args, 0)
    baseTypeLocalName = concept.baseXbrliType
    if not baseTypeLocalName:
        return NONE
    return QName("{http://www.xbrl.org/2003/instance}xbrli:" + baseTypeLocalName)


# netework functions

def network(node, sphinxContext, args, linkqname=None, linkrole=None, arcqname=None, arcrole=None):
    dts = dtsArg(node, sphinxContext, args)
    return ModelRelationshipSet(dts, arcrole, linkrole=linkrole, linkqname=linkqname, arcqname=arcqname)

def networks(node, sphinxContext, args, linkqname=None, linkrole=None, arcqname=None, arcrole=None):
    networkAllLinkroles = network(node, sphinxContext, args, linkqname, None, arcqname, arcrole)
    linkroles = networkAllLinkroles.linkRoleUris
    return set(network(node, sphinxContext, args, linkqname, linkrole, arcqname, arcrole)
               for linkrole in linkroles)

def _conceptHypercubeAll(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.all)

def _conceptHypercubeAllNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.all)

def _conceptHypercubeNotAll(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.notAll)

def _conceptHypercubeNotAllNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.notAll)

def _dimensionDefault(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.dimensionDefault)

def _dimensionDefaultNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.dimensionDefault)

def _dimensionDomain(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.dimensionDomain)

def _dimensionDomainNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.dimensionDomain)

def _domainMember(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.domainMember)

def _domainMemberNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.domainMember)

def _essenceAlias(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.essenceAlias)

def _essenceAliasNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.essenceAlias)

def _generalSpecial(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.generalSpecial)

def _generalSpecialNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.generalSpecial)

def _genericLink(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    arcrole = strArg(node, sphinxContext, args, 2)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=arcrole)

def _genericLinkNetworks(node, sphinxContext, args):
    arcrole = strArg(node, sphinxContext, args, 1)
    return networks(node, sphinxContext, args, arcrole=arcrole)

def _hypercubeDimension(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.hypercubeDimension)

def _hypercubeDimensionNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.hypercubeDimension)

def _network(node, sphinxContext, args, linkqname, linkrole, arcqname, arcrole):
    return network(node, sphinxContext, args, linkqname, linkrole, arcqname, arcrole)

def _networks(node, sphinxContext, args, linkqname, linkrole, arcqname, arcrole):
    return networks(node, sphinxContext, args, linkqname, linkrole, arcqname, arcrole)

def _parentChild(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.parentChild)

def _parentChildNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.parentChild)

def _requiresElement(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.requiresElement)

def _requiresElementNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.requiresElement)

def _similarTuples(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.similarTuples)

def _similarTuplesNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.similarTuples)

def _summationItem(node, sphinxContext, args):
    linkrole = strArg(node, sphinxContext, args, 1)
    return network(node, sphinxContext, args, linkrole=linkrole, arcrole=XbrlConst.summationItem)

def _summationItemNetworks(node, sphinxContext, args):
    return networks(node, sphinxContext, args, arcrole=XbrlConst.summationItem)

# network methods

def _ancestors(node, sphinxContext, args):
    return set(rel.toModelObject
               for rel in _ancestorRelationships(node, sphinxContext, args))

def _ancestorRelationships(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    concept = networkConceptArg(node, sphinxContext, args)
    def descRels(fromConcept, depth, visited, rels):
        if depth > 0 and concept not in visited:
            visited.add(concept)
            for rel in network.toModelObject(fromConcept):
                rels.add(rel)
                descRels(rel.fromModelObject, depth - 1, visited, rels)
            visited.discard(concept)
    rels = set()
    descRels(concept, numericArg(node, sphinxContext, args, 2), set(), rels)
    return rels

def _arcName(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    return network.arcqname

def _arcrole(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    return network.arcrole

def _children(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    concept = networkConceptArg(node, sphinxContext, args)
    return set(rel.fromModelObject for rel in network.fromModelObject(concept))

def _descendantRelationships(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    concept = networkConceptArg(node, sphinxContext, args)
    def descRels(fromConcept, depth, visited, rels):
        if depth > 0 and concept not in visited:
            visited.add(concept)
            for rel in network.fromModelObject(fromConcept):
                rels.add(rel)
                descRels(rel.toModelObject, depth - 1, visited, rels)
            visited.discard(concept)
    rels = set()
    descRels(concept, numericArg(node, sphinxContext, args, 2), set(), rels)
    return rels

def _descendants(node, sphinxContext, args):
    return set(rel.toModelObject
               for rel in _descendantRelationships(node, sphinxContext, args))

def _extendedLinkName(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    return network.linkrole

def _incomingRelationships(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    concept = networkConceptArg(node, sphinxContext, args)
    return set(network.toModelObject(concept))

def _outgoingRelationships(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    concept = networkConceptArg(node, sphinxContext, args)
    return set(network.fromModelObject(concept))

def _parents(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    concept = networkConceptArg(node, sphinxContext, args)
    return set(rel.fromModelObject for rel in network.toModelObject(concept))

def _relationships(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    return set(network.modelRelationships)

def _linkRole(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    return network.linkrole

def _sourceConcepts(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    return network.fromModelObjects().keys()

def _targetConcepts(node, sphinxContext, args):
    network = networkArg(node, sphinxContext, args)
    return network.toModelObjects().keys()

# relationship methods

def _order(node, sphinxContext, args):
    relationship = relationshipArg(node, sphinxContext, args)
    return relationship.order

def _preferredLabel(node, sphinxContext, args):
    relationship = relationshipArg(node, sphinxContext, args)
    return relationship.preferredLabel

def _source(node, sphinxContext, args):
    relationship = relationshipArg(node, sphinxContext, args)
    return relationship.fromModelObject

def _target(node, sphinxContext, args):
    relationship = relationshipArg(node, sphinxContext, args)
    return relationship.toModelObject

def _weight(node, sphinxContext, args):
    relationship = relationshipArg(node, sphinxContext, args)
    return relationship.weight

# aggregative functions

def _all(node, sphinxContext, args):
    return all(args)

def _any(node, sphinxContext, args):
    return any(args)

def _avg(node, sphinxContext, args):
    return sum(args) / len(args)

def _count(node, sphinxContext, args):
    return len(args)

def _exists(node, sphinxContext, args):
    return len(args) > 0

def _first(node, sphinxContext, args):
    if len(args):
        return args[0]
    return UNBOUND

def _list(node, sphinxContext, args):
    return [args]

def _max(node, sphinxContext, args):
    return max(args)

def _median(node, sphinxContext, args):
    if not args: # empty list
        return 0
    args = sorted(args)  # don't sort in place, args may be reused by caller
    middle = int(len(list) / 2)
    if len(list) % 2 == 0:
        return (args[middle - 1] + args[middle]) / 2  # average middle args
    else:
        return args[middle]  # middle item

def _min(node, sphinxContext, args):
    return min(args)

def _missing(node, sphinxContext, args):
    return len(args) == 0

def modes(args):
    counts = {}
    firstAt = {}
    maxcount = 0
    for i, arg in enumerate(args):
        newcount = counts.get(arg, 0) + 1
        counts[arg] = newcount
        if newcount > maxcount:
            maxcount = newcount
        if arg not in firstAt:
            firstAt[arg] = i
    return [(maxcount - count, firstAt[value], value)
            for value, count in counts.items()
            if count == maxcount].sort()

def _mode(node, sphinxContext, args):
    return modes(args)[0][2]

def _modes(node, sphinxContext, args):
    return set(mode[2] for mode in modes(args))

def _stdevp(node, sphinxContext, args):
    return _notImplemented(node, sphinxContext)

def _set(node, sphinxContext, args):
    return set(args)

def _sum(node, sphinxContext, args):
    return sum(args)

def _var(node, sphinxContext, args):
    return _notImplemented(node, sphinxContext)

def _varp(node, sphinxContext, args):
    return _notImplemented(node, sphinxContext)


# miscellaneous methods

def _notImplemented(node, sphinxContext, args):
    sphinxContext.modelXbrl.log("ERROR", "sphinx.functionNotImplemented",
                                _("Function %(name)s is not currently implemented"),
                                sourceFileLine=node.sourceFileLine,
                                name=node.name)
    return NaN

methodImplementation = {
    "abs":          _abs,
    "add-time-period": _addTimePeriod,
    "balance":      _balance,
    "concept":      _concept,
    "concepts":     _concepts,
    "contains":     _contains,
    "credit":       _credit,
    "days":         _days,
    "debit":        _debit,
    "decimals":     _decimals,
    "dimension":    _dimension,
    "dts-document-locations": _dtsDocumentLocations,
    "duration":     _duration,
    "end-date":     _endDate,
    "ends-with":    _endsWith,
    "entity":       _entityMethod,
    "exp":          _exp,
    "has-decimals": _hasDecimals,
    "has-precision":_hasPrecision,
    "identifier":   _identifier,
    "index-of":     _indexOf,
    "instant":      _instant,
    "is-forever":   _isForever,
    "is-monetary":  _isMonetary,
    "is-numeric":   _isNumeric,
    "last-index-of":_lastIndexOf,
    "ln":           _ln,
    "length":       _length,
    "local-part":   _localPart,
    "log":          _log,
    "log10":        _log10,
    "lower-case":   _lowerCase,
    "name":         _name,
    "period":       _period,
    "period-type":  _periodType,
    "power":        _power,
    "precision":    _precision,
    "primary":      _primary,
    "replace":      _replace,
    "round":        _roundItem,
    "round-by-decimals": _roundDecimals,
    "round-by-precision": _roundPrecision,
    "scenario":     _scenario,
    "schema-type":  _schemaTypeMethod,
    "scheme":       _scheme,
    "segment":      _segment,
    "signum":       _signum,
    "size":         _size,
    "sqrt":         _sqrt,
    "start-date":   _startDate,
    "starts-with":  _startsWith,
    "subtract-time-period": _subtractTimePeriod,
    "taxonomy":     _taxonomy,
    "to-list":      _toList,
    "to-set":       _toSet,
    "tuple":        _tuple,
    "unit":         _unitMethod,
    "unknown":      _notImplemented,
    "upper-case":   _upperCase,
    "xbrl-type":    _xbrlTypeMethod,

    #networks
    "concept-hypercube-all":                _conceptHypercubeAll,
    "concept-hypercube-all-networks":       _conceptHypercubeAllNetworks,
    "concept-hypercube-not-all":            _conceptHypercubeNotAll,
    "concept-hypercube-not-all-networks":   _conceptHypercubeNotAllNetworks,
    "dimension-default":                    _dimensionDefault,
    "dimension-default-networks":           _dimensionDefaultNetworks,
    "dimension-domain":                     _dimensionDomain,
    "dimension-domain-networks":            _dimensionDomainNetworks,
    "domain-member":                        _domainMember,
    "domain-member-networks":               _domainMemberNetworks,
    "essence-alias":                        _essenceAlias,
    "essence-alias-networks":               _essenceAliasNetworks,
    "general-special":                      _generalSpecial,
    "general-special-networks":             _generalSpecialNetworks,
    "generic-link":                         _genericLink,
    "generic-link-networks":                _genericLinkNetworks,
    "hypercube-dimension":                  _hypercubeDimension,
    "hypercube-dimension-networks":         _hypercubeDimensionNetworks,
    "network":                              _network,
    "networks":                             _networks,
    "parent-child":                         _parentChild,
    "parent-child-networks":                _parentChildNetworks,
    "requires-element":                     _requiresElement,
    "requires-element-networks":            _requiresElementNetworks,
    "similar-tuples":                       _similarTuples,
    "similar-tuples-networks":              _similarTuplesNetworks,
    "summation-item":                       _summationItem,
    "summation-item-networks":              _summationItemNetworks,

    #network methods
    "ancestors":                            _ancestors,
    "ancestor-relationships":               _ancestorRelationships,
    "arc-name":                             _arcName,
    "arcrole":                              _arcrole,
    "children":                             _children,
    "concepts":                             _concepts,
    "descendant-relationships":             _descendantRelationships,
    "descendants":                          _descendants,
    "extended-link-name":                   _extendedLinkName,
    "incoming-relationships":               _incomingRelationships,
    "outgoing-relationships":               _outgoingRelationships,
    "parents":                              _parents,
    "relationships":                        _relationships,
    "role":                                 _linkRole,
    "source-concepts":                      _sourceConcepts,
    "target-concepts":                      _targetConcepts,

    #relationship methods
    "order":                                _order,
    "preferred-label":                      _preferredLabel,
    "source":                               _source,
    "target":                               _target,
    "weight":                               _weight,
    }

functionImplementation = {
    "boolean":      _booleanFunction,
    "current-date-as-utc": _todayUTC,
    "duration":     _durationFunction,
    "entity":       _entityFunction,
    "forever":      _foreverFunction,
    "instant":      _instantFunction,
    "number":       _numberFunction,
    "schema-type":  _schemaTypeFunction,
    "time-period":  _timePeriodFunction,
    "unit":         _unitFunction,
    }

aggreateFunctionImplementation = {
    "all":          _all,
    "any":          _any,
    "avg":          _avg,
    "count":        _count,
    "exists":       _exists,
    "first":        _first,
    "list":         _list,
    "max":          _max,
    "median":       _median,
    "min":          _min,
    "missing":      _missing,
    "mode":         _mode,
    "modes":        _modes,
    "set":          _set,
    "stdevp":       _stdevp,
    "sum":          _sum,
    "var":          _var,
    "varp":         _varp,
    }

aggreateFunctionAcceptsFactArgs = {
    "all":          False,
    "any":          False,
    "avg":          False,
    "count":        True,
    "exists":       True,
    "first":        True,
    "list":         True,
    "max":          True,
    "median":       False,
    "min":          False,
    "missing":      True,
    "mode":         False,
    "modes":        False,
    "set":          True,
    "stdevp":       False,
    "sum":          False,
    "var":          False,
    "varp":         False,
    }
