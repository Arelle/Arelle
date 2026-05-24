'''
See COPYRIGHT.md for copyright information.
'''

from isodate import isodatetime
import regex as re
from arelle.oim.Load import (UnitPrefixedQNameSubstitutionChar, UnitPattern,
                             PrefixedQName)
from arelle.ModelValue import QName, qname, timeInterval
from arelle import XbrlConst
from arelle.XmlValidateConst import VALID, INVALID
from .XbrlConst import unsupportedTypedDimensionDataTypes
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlCube import XbrlCube, conceptCoreDim, languageCoreDim, periodCoreDim, unitCoreDim, coreDimensions
from .XbrlDimension import XbrlDimension, XbrlMember
from .XbrlFact import XbrlFact, XbrlTableTemplate
from .XbrlUnit import parseUnitString, XbrlUnit
from .ValidateXbrlModel import validateValue
from .ValidateCubes import validateCubes
from .ErrorCatalog import emit_error

periodPattern = re.compile( # regex for xs:dateTime or xs:date with optional end dateTime or date separated by "/" and optional "Z" timezone designator
    r"^-?[0-9]{4}-[0-9]{2}-[0-9]{2}(T([01][0-9]|20|21|22|23):[0-9]{2}:[0-9]{2}(\.[0-9]([0-9]*[1-9])?)?Z?)?"
    r"(/-?[0-9]{4}-[0-9]{2}-[0-9]{2}(T([01][0-9]|20|21|22|23):[0-9]{2}:[0-9]{2}(\.[0-9]([0-9]*[1-9])?)?Z?)?)?$"
    )
dimPropPattern = re.compile(r"^_[A-Za-z0-9]+$")

def resolveFact(txmyMdl, txmyObj, fact):
    """ Resolve QNames and other container-dependent values in fact.

        This is done before validating fact values because some of those values are needed for validation,
        such as the concept and unit dimensions. This is also done before validating fact position because
        some of those values are needed for finding the cubes that a fact is valid for, such as the period dimension.
    """
    # resolve QNames and other container-dependent values in fact
    if not hasattr(fact, "_xValid"):
        fact._xValid = VALID

    def error(code, msg, **kwargs):
        emit_error(txmyMdl, code, msg, xbrlObject=fact, name=getattr(fact, "name", None), **kwargs)

    # Extension facts (extendTargetName) inherit dimensions from the target fact
    extendTargetName = getattr(fact, 'extendTargetName', None)
    if extendTargetName is not None:
        targetFact = txmyMdl.namedObjects.get(extendTargetName)
        if targetFact is not None and not getattr(targetFact, 'isExtensible', True):
            txmyMdl.error("oimte:cannotExtendObject",
                          _("Fact %(target)s is not extensible (isExtensible=false) and cannot be extended."),
                          xbrlObject=fact, name=extendTargetName, target=extendTargetName)
        return  # extension facts inherit dimensions; skip further resolution
    if getattr(fact, 'factDimensions', None) is None:
        return  # skip facts without dimensions

    name = fact.name
    cQn = fact.factDimensions.get(conceptCoreDim)
    if isinstance(cQn, str) and ":" in cQn:
        cQn = fact.factDimensions[conceptCoreDim] = qname(cQn, txmyObj._prefixNamespaces)
    cObj = txmyMdl.namedObjects.get(cQn)
    if cObj is None:
        txmyMdl.error("oimte:missingConceptDimension",
                      _("The concept core dimension MUST be present on fact: %(name)s and must be a taxonomy concept."),
                      xbrlObject=fact, name=fact.name)
        fact._xValid = INVALID
        return
    if not isinstance(cObj, XbrlConcept):
        txmyMdl.error("oimte:invalidObjectType",
                      _("The concept core dimension on fact %(name)s MUST reference a concept object, not %(objectType)s."),
                      xbrlObject=fact, name=fact.name, objectType=type(cObj).__name__)
        fact._xValid = INVALID
        return
    cDataType = txmyMdl.namedObjects.get(cObj.dataType)
    if cDataType is None or not isinstance(cDataType, XbrlDataType):
        # presume this error would have been reported on validating loaded taxonomy model
        return
    for factValue in fact.factValues:
        # Step 6: factValue may carry its value either literally (`value` set) or
        # externally via `valueSources` pointing into an HTML/PDF/tabular source.
        # When valueSources are present, validate the locator-property structure
        # (and report `oimte:factValueLocatorRequiredForValueSources`,
        # `oimte:missingRequiredProperty`, `oimte:disallowedObjectProperty`,
        # `oimte:invalidQNameReference` / `oimte:invalidObjectType` as needed)
        # and attempt resolution. When the source document isn't currently
        # accessible the resolution is treated as deferred and we skip data-type
        # validation of the unresolved value -- structural errors have already
        # been emitted.
        deferred = False
        resolvedText = None
        if getattr(factValue, "valueSources", None):
            from .FactValueResolver import validateAndResolveValueSources
            deferred, resolvedText = validateAndResolveValueSources(txmyMdl, fact, factValue)
        if deferred and factValue.value is None:
            factValue._xValid = VALID
            factValue._xValue = resolvedText
        else:
            valueToValidate = factValue.value if factValue.value is not None else resolvedText
            _valid, _value = validateValue(txmyMdl, txmyObj, factValue, valueToValidate, cDataType, f"/value", "oimte:factValueDataTypeMismatch")
            factValue._xValid = _valid
            factValue._xValue = _value
        if factValue.language and cObj.isOimTextFactType(txmyMdl):
            if not factValue.language.islower():
                txmyMdl.error("xbrlje:invalidLanguageCodeCase",
                              _("Language MUST be lower case: \"%(lang)s\", fact %(name)s, concept %(concept)s."),
                              xbrlObject=fact, name=fact.name, lang=factValue.language, concept=cQn)

    if not name:
        error("oime:missingFactId", _("The name (name) MUST be present on fact."))

    uStr = fact.factDimensions.get(unitCoreDim)
    if isinstance(uStr, str):
        if cDataType.isNumeric(txmyMdl):
            if uStr == "xbrli:pure":
                txmyMdl.error("oime:illegalPureUnit",
                              _("Unit MUST NOT have single numerator measure xbrli:pure with no denominators: %(unit)s"),
                              xbrlObject=fact, unit=uStr)
                fact._xValid = INVALID
            elif not UnitPattern.match( PrefixedQName.sub(UnitPrefixedQNameSubstitutionChar, uStr) ):
                txmyMdl.error("oimce:invalidUnitStringRepresentation",
                              _("Unit string representation is lexically invalid, %(unit)s, fact id %(name)s"),
                              xbrlObject=fact, unit=uStr)
                fact._xValid = INVALID
            else:
                fact.factDimensions[unitCoreDim] = parseUnitString(uStr, fact, txmyObj, txmyMdl)
        else:
            txmyMdl.error("oime:misplacedUnitDimension",
                          _("The unit core dimension MUST NOT be present on non-numeric facts: %(concept)s, unit %(unit)s."),
                          xbrlObject=fact, concept=cQn, unit=uStr)
            fact._xValid = INVALID
    updateDimVals = {} # compiled values
    for dimName, dimVal in fact.factDimensions.items():
        if not isinstance(dimName, QName):
            if not dimPropPattern.match(dimName):
                txmyMdl.error("oime:unknownDimension",
                              _("Factspace %(name)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                              xbrlObject=fact, qname=dimName)
                fact._xValid = INVALID
        '''
        if isinstance(dimName, QName):
            dimObj = txmyMdl.namedObjects.get(dimName)
            if dimName not in coreDimensions:
                if not isinstance(dimObj, XbrlDimension):
                    txmyMdl.error("oime:unknownDimension",
                                  _("Factspace %(name)s taxonomy-defined dimension QName not be resolved to a dimension object with available DTS: %(qname)s."),
                                  qname=dimName)
                elif dimObj.isExplicitDimension:
                    if initialValidation and isinstance(dimVal, str) and ":" in dimVal:
                        memQn = fact.factDimensions[dimName] = qname(dimVal, txmyObj._prefixNamespaces)
                        if memQn:
                            updateDimVals[dimName] = memQn
                    else: # already compiled into QName
                        memQn = dimVal
                    if memQn is None:
                        txmyMdl.error("oime:invalidDimensionValue",
                                      _("Factspace %(name)s taxonomy-defined explicit dimension value is invalid: %(memberQName)s."),
                                      memberQName=memQn)
                        return
                    memObj = txmyMdl.namedObjects.get(memQn)
                    if not isinstance(memObj, XbrlMember):
                        txmyMdl.error("oime:invalidDimensionValue",
                                      _("Factspace %(name)s taxonomy-defined explicit dimension value must not be the default member: %(memberQName)s."),
                                      memberQName=memQn)
                        return
                elif dimObj.isTypedDimension:
                    domDataTypeObj = txmyMdl.namedObjects.get(dimObj.domainDataType)
                    if domDataTypeObj is None or domDataTypeObj.xsBaseType in unsupportedTypedDimensionDataTypes or (
                       domDataTypeObj.instanceOfType(XbrlConst.dtrPrefixedContentTypes, txmyMdl) and not dimObj.domainDataType.instanceOfType(XbrlConst.dtrSQNameNamesTypes, txmyMdl)):
                        txmyMdl.error("oime:unsupportedDimensionDataType",
                                      _("Factspace %(name)s taxonomy-defined typed dimension value is not supported: %(memberQName)s."),
                                      memberQName=dimVal)
                        return
                    #if (canonicalValuesFeature and dimVal is not None and
                    #    not CanonicalXmlTypePattern.get(domDataTypeObj.xsBaseType, NoCanonicalPattern).match(dimVal)):
                    #    txmyMdl.error("xbrlje:nonCanonicalValue",
                    #                  _("Numeric typed dimension must have canonical %(type)s value \"%(value)s\": %(concept)s."),
                    #                  xbrlObject=obj, type=dimConcept.typedDomainElement.baseXsdType, concept=dimConcept, value=dimVal)
                    if initialValidation:
                        _valid, _value = validateValue(txmyMdl, txmyObj, dimObj, dimVal, domDataTypeObj, f"/value", "oime:invalidDimensionValue")
                        if _valid < VALID and fact._xValid >= VALID:
                            fact._xValid = _valid # invalidate dimensionally invalid fact
                        if _valid >= VALID:
                            updateDimVals[dimName] = _value
            elif dimName == unitCoreDim:
                for unitNumDenom in dimVal:
                    for unitQn in unitNumDenom:
                        unitObj = txmyMdl.namedObjects.get(unitQn)
                        if not isinstance(unitObj, XbrlUnit):
                            txmyMdl.error("oime:unknownDimension",
                                          _("Factspace %(name)s unit dimension QName not be resolved to an xbrl Unit object with available DTS: %(qname)s."),
                                          qname=dimName)
                        elif not cDataType.instanceOfType(unitObj.dataType, txmyMdl):
                            txmyMdl.error("oime:invalidPropertyValue",
                                          _("Factspace %(name)s unit dimension data type %(unitDataType)s does not correspond to concept data type %(factDataType)s."),
                                          unitDataType=unitObj.dataType, factDataType=cObj.dataType)
        '''
    for dimName, dimVal in updateDimVals.items():
        fact.factDimensions[dimName] = dimVal

def validateFactPosition(txmyMdl, fact):
    """ Validate that fact is valid in at least one cube based on its dimensions.

        This is done after resolving fact dimensions because some of those dimensions are needed for finding the cubes
        that a fact is valid for, such as the period dimension.
    """
    def error(code, msg, **kwargs):
            emit_error(txmyMdl, code, msg, xbrlObject=fact, name=getattr(fact,"name"), **kwargs)
    cQn = fact.factDimensions.get(conceptCoreDim)
    cObj = txmyMdl.namedObjects.get(cQn)
    if cObj is None or not isinstance(cObj, XbrlConcept):
        return

    # cubes which fact complies with -- intentionally NOT retained on the fact.
    # The cube list is consumed immediately to update per-cube cell-coverage
    # state, then discarded. This keeps memory at O(cells) rather than O(facts).

    # if period is provided statically, validate and then fit to cubes.

    if periodCoreDim in fact.factDimensions:
        per = fact.factDimensions[periodCoreDim]
        if isinstance(per, str):
            if not periodPattern.match(per):
                error("oime:invalidPeriodDimension",
                              _("The fact %(name)s, concept %(element)s has a lexically invalid period %(periodError)s"),
                              element=cQn, periodError=per)
                return
            _start, _sep, _end = per.rpartition('/')
            _hasTime = 'T' in (_start or _end or '')  # only treat start==end as error at datetime precision
            if cObj.periodType == "none":
                # periodType=none facts MUST NOT have a period dimension
                error("oime:invalidPeriodDimension",
                              _("The fact %(name)s has concept %(element)s with periodType 'none' but includes a period dimension %(period)s."),
                              element=cQn, period=per)
                return
            elif ((cObj.periodType == "duration" and (not _start or (_hasTime and _start == _end))) or
                  (cObj.periodType == "instant" and _start and _start != _end)):
                error("oime:invalidPeriodDimension",
                              _("Invalid period for %(periodType)s fact %(name)s period %(period)s."),
                                                            periodType=cObj.periodType, period=per)
                return # skip creating fact because context would be bad
            elif cObj.periodType == "duration" and _start and _start > _end:
                error("oime:invalidPeriodDimension",
                              _("Duration period for fact %(name)s has start %(start)s after end %(end)s."),
                              start=_start, end=_end)
                return
            try:
                per = fact.factDimensions["_periodValue"] = timeInterval(per)
            except Exception:
                error("oime:invalidPeriodDimension",
                              _("The fact %(name)s has an unparseable period value %(period)s."),
                              period=per)
                return
    elif cObj.periodType != "none":
        error("oime:missingPeriodDimension",
                       _("Missing period for %(periodType)s fact %(name)s."),
                       periodType=cObj.periodType)

    # find cubes which fact is valid for
    matchedCubes = validateCubes(txmyMdl, fact)
    if not matchedCubes:
        error("oimte:noFactSpaceForFact",
              _("Factspace %(name)s is not dimensionally valid in any cube."))
    else:
        for cubeObj in matchedCubes:
            cellFacts = getattr(cubeObj, "_cellFacts", None)
            if cellFacts is None:
                cellFacts = cubeObj._cellFacts = {}
            # cell signature = the cube's dimension values from this fact.
            # Many facts may collapse to the same cell; we retain per-cell
            # references to fact (and each of its factValues) so that the
            # cube-completion pass can perform duplicate-fact validation.
            cellKey = tuple(
                (cubeDimObj.dimensionName, fact.factDimensions.get(cubeDimObj.dimensionName))
                for cubeDimObj in cubeObj.cubeDimensions
            )
            bucket = cellFacts.setdefault(cellKey, [])
            for fv in (fact.factValues or ()):
                bucket.append((fact, fv))


def validateCompleteReportCubes(txmyMdl):
    """Validate complete cubes after facts have been matched to their effective cubes."""
    from .ValidateCubes import validateCompleteCube, validateCubeDuplicates

    for cubeObj in txmyMdl.filterNamedObjects(XbrlCube):
        if txmyMdl.effectiveRequiredCubes(cubeObj):
            validateCompleteCube(txmyMdl, cubeObj)
        # Duplicate-fact validation applies to every cube (not just required
        # cubes) per oim-taxonomy "Duplicate fact validation".
        validateCubeDuplicates(txmyMdl, cubeObj)

def validateTable(table, reportQn, reportObj, txmyMdl):
    """ Validate table definition.
    """
    # ensure template exists
    url = table.url
    if not txmyMdl.fileSource.exists(url) and not table.optional:
        txmyMdl.error("xbrlce:missingRequiredCSVFile",
              _("The url %(url)s MUST be an existing file for non-optional table %(table)s."),
              table=table.name, url=table.url)

    tmplObj = txmyMdl.namedObjects.get(table.template)
    if tmplObj is None or not isinstance(tmplObj, XbrlTableTemplate):
        txmyMdl.error("xbrlce:unknownTableTemplate",
              _("The table %(table) template, %(name)s MUST be the identifier of a table template present in the OIM Taxonomy Model."),
              table=table.name, name=table.template)

def validateDateResolutionConceptFacts(txmyMdl):
    """ Validate facts whose values represent dateResolution concepts."""
    # validate facts whose values represent dateResolution concepts first
    for qn in txmyMdl.dateResolutionConceptNames:
        f = txmyMdl.namedObjects.get(qn)
        if isinstance(f, XbrlFact):
            resolveFact(txmyMdl, getattr(f, "parent", txmyMdl), f)
            validateFactPosition(txmyMdl, f)

# NOTE: The legacy `validateReport(reportQn, reportObj, txmyMdl)` function has been
# removed along with the XbrlReport object. Cube completeness is now invoked directly
# via `validateCompleteReportCubes(txmyMdl)`. The per-fact resolution loop will be
# reintroduced in the streaming fact-pipeline refactor (step 2).

