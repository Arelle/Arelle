'''
See COPYRIGHT.md for copyright information.
'''

from arelle.ModelValue import qname, QName
from .XbrlConcept import XbrlConcept
from .XbrlCube import XbrlCube, conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim
from .XbrlDimension import XbrlDimension, XbrlDomainNetwork
from .XbrlFact import XbrlFact
from .UnitSignature import canonicalUnitValue
from .VectorSearch import buildXbrlVectors, searchXbrl, searchXbrlBatchTopk, SEARCH_CUBES, SEARCH_FACTPOSITIONS, SEARCH_BOTH
from arelle.XmlValidateConst import VALID, INVALID

coreToFactDim = {conceptCoreDim: "concept", entityCoreDim: "entity", unitCoreDim: "unit"}

def effectiveCubeType(compMdl, cubeObj, _visited=None):
    """The cube's cubeType QName, inherited through `extends` when the cube sets none of its own.
       An anonymous extension cube (e.g. {"extends": someNegativeCube}) has no local cubeType but
       is effectively the base's type -- so a cube extending a negative cube is itself negative."""
    cubeType = getattr(cubeObj, "cubeType", None)
    if cubeType is not None:
        return cubeType
    extends = getattr(cubeObj, "extends", None)
    if extends is not None:
        if _visited is None:
            _visited = set()
        if id(cubeObj) in _visited:
            return None
        _visited.add(id(cubeObj))
        baseObj = compMdl.namedObjects.get(extends)
        if isinstance(baseObj, XbrlCube):
            return effectiveCubeType(compMdl, baseObj, _visited)
    return None # no local or inherited cubeType -> defaults to xbrl:reportCube (not negative)


def isNegativeCube(compMdl, cubeObj):
    """True if the cube is (or effectively, through extends, is) a negative cube -- one that does
       not provide a valid fact space. Uses the effective cubeType so an extension of a negative
       cube is recognized as negative."""
    cubeTypeQn = effectiveCubeType(compMdl, cubeObj)
    cubeTypeObj = compMdl.namedObjects.get(cubeTypeQn) if cubeTypeQn is not None else None
    return getattr(getattr(cubeTypeObj, "name", None), "localName", None) == "negativeCube"


def isExtensionAddition(cubeObj):
    """True for an unnamed cube that extends another: it adds properties (requiredCubes,
    excludeCubes, cubeNetworks, properties) to its base cube rather than defining a cube of its
    own. It declares no dimensions, so matched on its own it would admit every fact and give every
    fact a fact space."""
    return getattr(cubeObj, "name", None) is None and getattr(cubeObj, "extends", None) is not None


def excludeCubesOf(compMdl, cubeObj):
    """The exclude cube QNames that apply to a cube: its effective excludeCubes (its own and those
    inherited through extends) plus those added by unnamed extension cubes extending it."""
    added = getattr(compMdl, "_extensionExcludeCubesCache", None)
    if added is None:
        added = compMdl._extensionExcludeCubesCache = {}
        for module in compMdl.xbrlModels.values():
            for extCube in getattr(module, "cubes", None) or ():
                if isExtensionAddition(extCube) and extCube.excludeCubes:
                    added.setdefault(extCube.extends, []).extend(extCube.excludeCubes)
    return list(compMdl.effectiveExcludeCubes(cubeObj)) + added.get(getattr(cubeObj, "name", None), [])


def factExcludedFromCube(compMdl, fact, cubeObj):
    """True if an exclude cube of the cube includes the fact (tavi.md "Exclude cube": the
    intersection of the facts of the exclude cube and the defined cube is removed). A fact is in an
    exclude cube when it lies in its dimensional space and satisfies its period constraints."""
    for exclQn in excludeCubesOf(compMdl, cubeObj):
        exclCube = compMdl.namedObjects.get(exclQn)
        if (isinstance(exclCube, XbrlCube) and matchFactToCube(compMdl, fact, exclCube)
                and factMatchesPeriodConstraints(compMdl, fact, exclCube)):
            return True
    return False


def matchFactToCube(compMdl, factspace, cubeObj):
    """Check if the factspace dimensions match the cube dimensions and allowed members.
        Return True if the factspace matches the cube, False otherwise.

        The factspace matches the cube if for each dimension of the cube, there is a corresponding dimension
        in the factspace with a value that matches one of the allowed members of the cube dimension.

        For core dimensions (concept, entity, unit), the factspace dimension value must match one of the
        allowed members of the cube dimension.

        For the period dimension, only presence is checked here: period constraints select which facts
        the cube includes (factMatchesPeriodConstraints), and do not remove the fact from its fact space.

        For taxonomy-defined dimensions, the factspace dimension value must match one of the allowed members of the cube dimension.

        If any cube dimension does not have a matching factspace dimension with a matching value, then the factspace
        does not match the cube and the function returns False.
    """
    hasCoreDims = True
    hasDims = True
    for cubeDimObj in cubeObj.cubeDimensions or ():
        dimName = cubeDimObj.dimension
        if dimName in coreToFactDim:
            mems = cubeDimObj.allowedMembers(compMdl)
            factDimVal = factspace.factDimensions.get(dimName)
            # A required core dimension absent from the fact rules out this cube.
            if factDimVal is None and not cubeDimObj.optional:
                hasDims = False # skip this cube
                break
            # Entity (and other core) dimension values may still be carried as
            # strings (e.g. "exp:ExampleCo") rather than resolved QNames, while
            # `mems` is a set of QName objects. Resolve on the fly so that
            # matching does not spuriously fail.
            if (mems and not isinstance(factDimVal, QName) and isinstance(factDimVal, str)
                    and ":" in factDimVal):
                resolved = qname(factDimVal, getattr(getattr(factspace, "module", None), "_prefixNamespaces", None))
                if resolved is not None:
                    factDimVal = resolved
            if dimName == unitCoreDim and isinstance(factDimVal, tuple):
                # A reported unit dimension value is compared with the cube's unit members by its
                # canonical value, so that utr:ft*utr:sqft matches a domain containing utr:ft3
                # (tavi.md "Unit equivalence"). A value that does not reduce to a single unit
                # matches no member, since a unit domain lists unit objects.
                canonicalValue = canonicalUnitValue(factDimVal, compMdl)
                if len(canonicalValue[0]) == 1 and not canonicalValue[1]:
                    factDimVal = canonicalValue[0][0]
            if mems and factDimVal not in mems:
                hasDims = False # skip this cube
                break
        elif dimName == periodCoreDim:
            factPerVal = factspace.factDimensions.get("_periodValue")
            if factPerVal is None and not cubeDimObj.optional:
                hasDims = False # period required but fact has no period (e.g. periodType:none concept)
                break
            # Period constraints decide MEMBERSHIP, not fact space: a fact whose period does not
            # match is not included in the cube, but still lies in its dimensional space for
            # oimte:noFactSpaceForFact. Membership is applied by factMatchesPeriodConstraints
            # (below), called where facts are recorded in the cube's cells.
            continue
        elif dimName not in factspace.factDimensions:
            if not cubeDimObj.optional:
                hasDims = False # skip this cube
                break
        else: # taxonomy defined dim
            dimObj = compMdl.namedObjects.get(dimName)
            isTyped = bool(cubeDimObj.domainDataType)
            if not isTyped:
                dimMbrQn = qname(factspace.factDimensions.get(dimName), factspace.module._prefixNamespaces)
            mems = cubeDimObj.allowedMembers(compMdl)
            # Empty mems means no domainNetwork is set on this cube dimension:
            # the cube imposes no member restriction, so any member value is accepted.
            if (isinstance(dimObj, XbrlDimension) and not isTyped and
                mems and dimMbrQn not in mems):
                hasDims = False # skip this cube
                break
    return hasDims

def validateCubes(compMdl, factspace):
    """Return the cubes whose dimensional space the factspace (a fact) falls within.

        A fact matches a cube only if, for the cube's concept dimension, the fact's concept is an
        allowed member (or the cube's concept dimension is open) -- see matchFactToCube. So the
        candidate cubes for a fact are exactly the cubes that list the fact's concept as a concept
        member, plus the cubes with an open concept dimension; matchFactToCube then verifies the
        remaining dimensions. This exact concept index (built once, cached) replaces a per-fact
        vector search: it is torch-free, needs no embedding build, and does not miss a cube (the
        vector recall returned an approximate top-k). The vector path is retained for comparison
        behind compMdl._useVectorCubeSearch.
    """
    if getattr(compMdl, "_useVectorCubeSearch", False):
        return _validateCubesVectorSearch(compMdl, factspace)
    conceptToCubes, openCubes = _cubeConceptCandidateIndex(compMdl)
    conceptQn = (factspace.factDimensions or {}).get(conceptCoreDim)
    if isinstance(conceptQn, str) and ":" in conceptQn:
        conceptQn = qname(conceptQn, factspace.module._prefixNamespaces)
    candidates = []
    seen = set()
    for cubeObj in conceptToCubes.get(conceptQn, ()):
        if id(cubeObj) not in seen:
            seen.add(id(cubeObj))
            candidates.append(cubeObj)
    for cubeObj in openCubes: # open-concept cubes accept any concept -- candidates for every fact
        if id(cubeObj) not in seen:
            seen.add(id(cubeObj))
            candidates.append(cubeObj)
    return [cubeObj for cubeObj in candidates if matchFactToCube(compMdl, factspace, cubeObj)]


def _cubeConceptCandidateIndex(compMdl):
    """(conceptToCubes, openCubes): a concept QName -> the cubes listing it as a concept member,
       and the cubes whose concept dimension is open (no domain, so any concept is allowed). Built
       from every module's cubes (including anonymous extension cubes) using the same concept
       member set matchFactToCube consults (XbrlCubeDimension.allowedMembers), and cached on the
       model; cleared by clearEffectiveCaches when the effective relationships change."""
    index = getattr(compMdl, "_cubeConceptCandidateIndexCache", None)
    if index is not None:
        return index
    conceptToCubes = {}
    openCubes = []
    for module in compMdl.xbrlModels.values():
        for cubeObj in getattr(module, "cubes", None) or ():
            if isExtensionAddition(cubeObj):
                continue # adds to its base cube (see isExtensionAddition); not a cube of its own
            conceptDim = next((cd for cd in (cubeObj.cubeDimensions or ())
                               if cd.dimension == conceptCoreDim), None)
            members = conceptDim.allowedMembers(compMdl) if conceptDim is not None else None
            if members:
                for conceptQn in members:
                    conceptToCubes.setdefault(conceptQn, []).append(cubeObj)
            else:
                openCubes.append(cubeObj) # open concept dimension -> matches any fact's concept
    index = (conceptToCubes, openCubes)
    compMdl._cubeConceptCandidateIndexCache = index
    return index


def _validateCubesVectorSearch(compMdl, factspace):
    """Vector-search candidate generation (compMdl._useVectorCubeSearch): find likely cubes by
       embedding similarity, then verify with matchFactToCube. Retained for comparison; the exact
       concept index in validateCubes is the default (faster and does not miss cubes)."""
    cubeFitQuery = [(dimQn, value) for dimQn,value in factspace.factDimensions.items() if isinstance(dimQn, QName)]
    try:
        results = searchXbrl(compMdl, cubeFitQuery, SEARCH_CUBES, 50) # allow sufficient return scores
    except (ValueError, KeyError):
        results = []  # fall back when queryAspects don't exist in vectorized model

    usableCubes = []
    for score, cubeObj in results:
        if score < .1 : # find right value here
            break
        if matchFactToCube(compMdl, factspace, cubeObj):
            usableCubes.append(cubeObj)
    return usableCubes

def validateCompleteCube(compMdl, cubeObj):
    """Validate that a required-complete cube has facts for every concept in its concept domain."""
    cellFacts = getattr(cubeObj, "_cellFacts", None)

    conceptDomainConcepts = set()
    for cubeDimObj in cubeObj.cubeDimensions or ():
        if cubeDimObj.dimension == conceptCoreDim and cubeDimObj.domainNetwork:
            domNwkObj = compMdl.namedObjects.get(cubeDimObj.domainNetwork)
            if isinstance(domNwkObj, XbrlDomainNetwork):
                for relObj in compMdl.effectiveRelationships(domNwkObj):
                    tgtObj = compMdl.namedObjects.get(relObj.target)
                    if isinstance(tgtObj, XbrlConcept):
                        conceptDomainConcepts.add(relObj.target)

    if not conceptDomainConcepts:
        return

    coveredConcepts = set()
    if cellFacts:
        for cellKey in cellFacts:
            for dimQn, dimVal in cellKey:
                if dimQn == conceptCoreDim:
                    coveredConcepts.add(dimVal)

    for concept in conceptDomainConcepts:
        if concept not in coveredConcepts:
            compMdl.error("oimte:factMissingFromCube",
                         _("The complete cube %(name)s is missing facts for concept %(concept)s."),
                          xbrlObject=cubeObj, name=cubeObj.name, concept=concept)


def _effectiveDuplicatePolicy(compMdl, cubeObj):
    """Resolve the effective duplicate-fact policy for a cube.

    Precedence: cubeObj.duplicateFactsInCube overrides the owning module's
    duplicateFactsInModel; when neither is set the OIM Taxonomy default is
    'inconsistent duplicates'.
    """
    pol = getattr(cubeObj, "duplicateFactsInCube", None)
    if pol:
        return pol
    for mod in getattr(compMdl, "xbrlModels", {}).values():
        modPol = getattr(mod, "duplicateFactsInModel", None)
        if modPol:
            return modPol
    return "inconsistent duplicates"


def _roundToDecimals(value, decimals):
    """Round a numeric value to the precision indicated by an OIM decimals
    integer (positive -> right of decimal point, negative -> left).
    Returns None when value cannot be converted to float.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if decimals is None:
        return v
    try:
        d = int(decimals)
    except (TypeError, ValueError):
        return v
    return round(v, d)


def _isConsistentValuePair(v1, d1, v2, d2):
    """Two numeric fact values are consistent duplicates when their values,
    rounded to the lower precision of the two, are equal.
    """
    if d1 is None and d2 is None:
        return v1 == v2
    if d1 is None:
        lower = d2
    elif d2 is None:
        lower = d1
    else:
        lower = min(int(d1), int(d2))
    r1 = _roundToDecimals(v1, lower)
    r2 = _roundToDecimals(v2, lower)
    if r1 is None or r2 is None:
        return v1 == v2
    return r1 == r2


def validateCubeDuplicates(compMdl, cubeObj):
    """Emit oime:disallowedDuplicateFacts when facts collapsing to the same
    cube cell violate the effective duplicate policy.
    """
    cellFacts = getattr(cubeObj, "_cellFacts", None)
    if not cellFacts:
        return
    policy = _effectiveDuplicatePolicy(compMdl, cubeObj)
    if policy == "inconsistent duplicates":
        return  # default: any duplicates allowed
    for cellKey, entries in cellFacts.items():
        if len(entries) < 2:
            continue
        # Determine whether this group of duplicates violates the policy.
        violates = False
        if policy == "no duplicates":
            violates = True
        else:
            # Compare every pair against the policy.
            for i in range(len(entries)):
                _f1, fv1 = entries[i]
                v1 = getattr(fv1, "value", None)
                d1 = getattr(fv1, "decimals", None)
                for j in range(i + 1, len(entries)):
                    _f2, fv2 = entries[j]
                    v2 = getattr(fv2, "value", None)
                    d2 = getattr(fv2, "decimals", None)
                    if policy == "complete duplicates":
                        # Require value AND decimals match
                        if v1 != v2 or d1 != d2:
                            violates = True
                            break
                    elif policy == "consistent duplicates":
                        # Require values consistent at lower precision; allow
                        # complete duplicates (subset) too.
                        if not _isConsistentValuePair(v1, d1, v2, d2):
                            violates = True
                            break
                if violates:
                    break
        if violates:
            factNames = sorted({getattr(f, "name", None) for f, _fv in entries})
            compMdl.error(
                "oime:disallowedDuplicateFacts",
                _("Cube %(cube)s with duplicateFacts policy '%(policy)s' has prohibited "
                  "duplicate facts %(facts)s at cell %(cell)s."),
                xbrlObject=cubeObj,
                cube=cubeObj.name, policy=policy,
                facts=", ".join(str(n) for n in factNames if n is not None),
                cell=str(cellKey))



# ---------------------------------------------------------------------------------------------
# Period constraint membership
#
# tavi.md "Period constraint object": the period constraints of a cube's period dimension
# "select those facts whose periods match ... If a facts period dimension matches all the
# defined properties then it is included in the cube."  Properties of one period constraint
# object AND; separate period constraint objects OR.
#
# This is MEMBERSHIP (which facts a cube holds: completeness, duplicates, calculations, formula
# cube queries), not FACT SPACE. A fact excluded from a cube by its period constraints still lies
# in the cube's dimensional space, so matchFactToCube -- which decides oimte:noFactSpaceForFact --
# ignores period constraints (conformance CUBE-PeriodConstraintInstant-Valid: a duration fact is
# "excluded" from an instant-only cube and the report is still valid).
#
# Periods are read from the fact's period string as tavi.md "Period" resolves it: a date-only
# start is T00:00:00 of its day; a date-only end, or a date-only instant, is T00:00:00 of the
# following day (so "2024-12-31" is the instant 2025-01-01T00:00:00, and "2023-01-01/2023-01-01"
# is 24 hours). The parsed _periodValue cannot be used for this: it reads a date-only end as
# midnight at the START of its day. Dates are then compared as calendar days, an end or instant
# at midnight naming the day it closes.
# ---------------------------------------------------------------------------------------------

import calendar as _calendar
import datetime as _datetime
import re as _re

_isoDurationPattern = _re.compile(
    r"^(-)?P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def factMatchesPeriodConstraints(compMdl, fact, cubeObj) -> bool:
    """True if the fact is included in the cube by the period constraints of its period
    dimension: the cube has none, or the fact's period matches every property of at least one
    period constraint object. A fact with no period matches no period constraint."""
    for cubeDimObj in cubeObj.cubeDimensions or ():
        if cubeDimObj.dimension != periodCoreDim:
            continue
        constraints = cubeDimObj.periodConstraints or ()
        if not constraints:
            return True
        period = _factPeriod(fact)
        if period is None:
            return False
        return any(_periodConstraintMatches(compMdl, perConstObj, period, fact)
                   for perConstObj in constraints)
    return True


class _Period:
    """A fact period resolved per tavi.md: start and end points, and the calendar days they name."""
    __slots__ = ("isInstant", "startPoint", "endPoint", "startDay", "endDay")

    def __init__(self, startPoint, endPoint):
        self.isInstant = startPoint is None
        self.startPoint = startPoint
        self.endPoint = endPoint
        self.endDay = _pointEndDay(endPoint)
        self.startDay = startPoint.date() if startPoint is not None else self.endDay

    @property
    def isDuration(self):
        return not self.isInstant


def _parsePeriod(perStr):
    """A period string as a _Period, or None if it is not a period."""
    startStr, _sep, endStr = str(perStr).strip().rpartition("/")
    try:
        endPoint = _parsePoint(endStr, isEnd=True)
        startPoint = _parsePoint(startStr, isEnd=False) if startStr else None
    except ValueError:
        return None
    return _Period(startPoint, endPoint)


def _parsePoint(text, isEnd):
    """A start, end or instant value as a point in time; a date-only end or instant is midnight of
    the following day."""
    if "T" in text:
        return _datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    day = _datetime.date.fromisoformat(text)
    point = _datetime.datetime(day.year, day.month, day.day)
    return point + _datetime.timedelta(days=1) if isEnd else point


def _pointEndDay(point):
    """The calendar day an end or instant point names: midnight names the day it closes."""
    if point.time() == _datetime.time(0):
        return (point - _datetime.timedelta(days=1)).date()
    return point.date()


def _periodConstraintMatches(compMdl, perConstObj, period, fact) -> bool:
    """All defined properties of one period constraint object match the fact's period."""
    periodType = perConstObj.periodType
    if periodType == "instant" and not period.isInstant:
        return False
    if periodType == "duration" and not period.isDuration:
        return False
    if perConstObj.timeSpan:
        if not period.isDuration:
            return False
        if _addDuration(period.startPoint, perConstObj.timeSpan) != period.endPoint:
            return False
    # periodPattern matches the lexical period (XbrlPeriodConstraint.periodPatternMatch)
    if perConstObj.periodPattern and perConstObj.periodPatternMatch(fact.factDimensions.get(periodCoreDim)) is False:
        return False
    # endDate: a duration's end, an instant's date; startDate: a duration's start, an instant's date
    # onOrAfter: an instant's date, a duration's start; onOrBefore: an instant's date, a duration's end
    endDay = period.endDay
    startDay = period.startDay
    for dateResObj, factDay, test in ((perConstObj.endDate, endDay, "eq"),
                                      (perConstObj.startDate, startDay, "eq"),
                                      (perConstObj.onOrAfter, startDay, "ge"),
                                      (perConstObj.onOrBefore, endDay, "le")):
        if dateResObj is None:
            continue
        days = resolveDateResolution(compMdl, dateResObj)
        if days is None:
            continue  # resolves to nothing: the property is ignored (tavi.md "Date resolution")
        if test == "eq" and factDay not in days:
            return False
        if test == "ge" and not any(factDay >= d for d in days):
            return False
        if test == "le" and not any(factDay <= d for d in days):
            return False
    return True


def resolveDateResolution(compMdl, dateResObj):
    """The set of calendar days a date resolution object resolves to in this report, or None
    when it resolves to none (then the property using it is ignored). Cached per model."""
    cache = getattr(compMdl, "_dateResolutionCache", None)
    if cache is None:
        cache = compMdl._dateResolutionCache = {}
    key = id(dateResObj)
    if key in cache:
        return cache[key]
    days = set()
    if dateResObj.conceptName is not None:
        for fact in _factsOfConcept(compMdl, dateResObj.conceptName):
            for fv in fact.factValues or ():
                # the lexical value (a date names its day); the typed value if no lexical one is kept
                day = _valueDay(fv.value if fv.value is not None else getattr(fv, "_xValue", None))
                if day is not None:
                    days.add(day)
    elif dateResObj.context is not None:
        atStart = getattr(dateResObj.context, "atSuffix", "end") == "start"
        for fact in _factsOfConcept(compMdl, dateResObj.context):
            period = _factPeriod(fact)
            if period is not None:
                days.add(period.startDay if atStart else period.endDay)
    elif dateResObj.value is not None:
        day = _valueDay(dateResObj.value)
        if day is not None:
            days.add(day)
    elif dateResObj.dateProperty:
        days.update(_datePropertyDays(compMdl, dateResObj))
    if days and dateResObj.timeShift:
        days = {_addDuration(_datetime.datetime.combine(d, _datetime.time()), dateResObj.timeShift).date()
                for d in days}
    result = days or None
    cache[key] = result
    return result


def _factsOfConcept(compMdl, conceptQn):
    """Facts reporting the concept (QName or QNameAt), indexed once per model."""
    index = getattr(compMdl, "_factsByConceptCache", None)
    if index is None:
        index = compMdl._factsByConceptCache = {}
        for fact in compMdl.filterNamedObjects(XbrlFact):
            qn = (fact.factDimensions or {}).get(conceptCoreDim)
            if isinstance(qn, str) and ":" in qn:
                qn = qname(qn, fact.module._prefixNamespaces)
            if qn is not None:
                index.setdefault((qn.namespaceURI, qn.localName), []).append(fact)
    return index.get((conceptQn.namespaceURI, conceptQn.localName), ())


def _factPeriod(fact):
    """The fact's period as a _Period, from its period dimension's lexical value."""
    perStr = fact.factDimensions.get(periodCoreDim)
    return _parsePeriod(perStr) if perStr is not None else None


def _datePropertyDays(compMdl, dateResObj):
    """Days named by a dateProperty "objectQName.propertyQName@start|@end": the property's
    value is a date or a period."""
    ref, _sep, suffix = str(dateResObj.dateProperty).partition("@")
    objPart, _sep, propPart = ref.rpartition(".")
    prefixes = getattr(getattr(dateResObj, "module", None), "_prefixNamespaces", None)
    objQn, propQn = qname(objPart, prefixes), qname(propPart, prefixes)
    obj = compMdl.namedObjects.get(objQn) if objQn is not None else None
    for prop in getattr(obj, "properties", None) or ():
        if prop.property == propQn:
            value = str(prop.value)
            if "/" in value:
                period = _parsePeriod(value)
                if period is None:
                    return set()
                return {period.startDay if suffix == "start" else period.endDay}
            day = _valueDay(value)
            return {day} if day is not None else set()
    return set()


def _valueDay(value):
    """A date or dateTime value, by its lexical form, as the calendar day it names: a date names
    its day, a dateTime at midnight the day it closes."""
    if value is None:
        return None
    text = str(value).strip()
    try:
        return _pointEndDay(_parsePoint(text, isEnd=True))
    except ValueError:
        return None


def _addDuration(point, duration):
    """point + an xs:duration, calendar-wise: years and months first (clamping the day to the
    month's length), then weeks, days and time. Returns None for an unparseable duration."""
    m = _isoDurationPattern.match(str(duration).strip())
    if not m:
        return None
    neg, years, months, weeks, days, hours, minutes, seconds = m.groups()
    sign = -1 if neg else 1
    totalMonths = point.month - 1 + sign * (int(years or 0) * 12 + int(months or 0))
    year, month = point.year + totalMonths // 12, totalMonths % 12 + 1
    day = min(point.day, _calendar.monthrange(year, month)[1])
    shifted = point.replace(year=year, month=month, day=day)
    return shifted + sign * _datetime.timedelta(weeks=int(weeks or 0), days=int(days or 0),
                                                hours=int(hours or 0), minutes=int(minutes or 0),
                                                seconds=float(seconds or 0))
