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
from .XbrlConst import unsupportedTypedDimensionDataTypes, qnXbrlMemberObj, xbrl as xbrlNs

# xbrl:nil property marks a fact whose value is absent (e.g. mapped from an
# xBRL-XML xsi:nil="true" fact). Such facts carry no value to type-validate.
qnFactNilProperty = QName("xbrl", xbrlNs, "nil")
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlCube import XbrlCube, conceptCoreDim, entityCoreDim, languageCoreDim, periodCoreDim, unitCoreDim, coreDimensions
from .XbrlDimension import XbrlDimension, XbrlDomainClass, XbrlMember
from .XbrlEntity import XbrlEntity
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
        emit_error(txmyMdl, code, msg, xbrlObject=fact, name=fact.name, **kwargs)

    # Extension facts (extends) inherit dimensions from the target fact
    extends = fact.extends
    if extends is not None:
        targetFact = txmyMdl.namedObjects.get(extends)
        if targetFact is not None and not targetFact.isExtensible:
            txmyMdl.error("oimte:illegalExtensionOfNonExtensibleObject",
                          _("Fact %(target)s is not extensible (isExtensible=false) and cannot be extended."),
                          xbrlObject=fact, name=extends, target=extends)
        return  # extension facts inherit dimensions; skip further resolution
    if fact.factDimensions is None:
        return  # skip facts without dimensions

    name = fact.name
    cQn = fact.factDimensions.get(conceptCoreDim)
    if isinstance(cQn, str) and ":" in cQn:
        cQn = fact.factDimensions[conceptCoreDim] = qname(cQn, txmyObj._prefixNamespaces)
    cObj = txmyMdl.namedObjects.get(cQn)
    if cObj is None:
        txmyMdl.error("oime:missingConceptDimension",
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
    factIsNil = any(getattr(p, "property", None) == qnFactNilProperty
                    for p in (fact.properties or ()))
    for factValue in fact.factValues:
        # A nil fact carries no value in its factValue object; there is nothing to
        # type-validate. (An explicit value or valueSource still validates below.)
        if factIsNil and factValue.value is None and not factValue.valueSources:
            factValue._xValid = VALID
            factValue._xValue = None
            continue
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
        if factValue.valueSources:
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
        # When the factValue's text came from a valueSource (rather than a
        # literal `value` field), mirror the resolved/transformed text into
        # `factValue.value` so downstream consumers (e.g. Formula's
        # FormulaValue.fromFact) that read `.value` see the same value they
        # would for a literally-specified fact.
        if factValue.value is None and resolvedText is not None:
            factValue.value = resolvedText
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
                              xbrlObject=fact, unit=uStr, name=fact.name)
                fact._xValid = INVALID
            else:
                unitQnTuple = parseUnitString(uStr, fact, txmyObj, txmyMdl)
                fact.factDimensions[unitCoreDim] = unitQnTuple
                # Each unit measure's dataType must be the same as or a supertype of
                # the concept's dataType (concept's type must be an instance of the
                # unit's declared dataType).
                for unitMeasures in unitQnTuple:
                    for unitQn in unitMeasures:
                        unitObj = txmyMdl.namedObjects.get(unitQn)
                        if isinstance(unitObj, XbrlUnit) and not cDataType.instanceOfType(unitObj.dataType, txmyMdl):
                            txmyMdl.error("oimte:factUnitDatatypeMismatch",
                                          _("Unit %(unit)s is not valid for concept %(concept)s with dataType %(dataType)s."),
                                          xbrlObject=fact, name=fact.name,
                                          unit=unitQn, concept=cQn, dataType=cObj.dataType)
                            fact._xValid = INVALID
        else:
            txmyMdl.error("oime:misplacedUnitDimension",
                          _("The unit core dimension MUST NOT be present on non-numeric facts: %(concept)s, unit %(unit)s."),
                          xbrlObject=fact, concept=cQn, unit=uStr)
            fact._xValid = INVALID
    elif uStr is None and cDataType.isNumeric(txmyMdl):
        # No unit present; check if the concept's dataType requires one.
        # Build and cache the set of dataType QNames that have at least one unit defined.
        if not hasattr(txmyMdl, '_unitDataTypes'):
            txmyMdl._unitDataTypes = frozenset(
                obj.dataType for obj in txmyMdl.namedObjects.values()
                if isinstance(obj, XbrlUnit)
            )
        if any(cDataType.instanceOfType(unitDt, txmyMdl) for unitDt in txmyMdl._unitDataTypes):
            txmyMdl.error("oimte:factMissingUnitDimension",
                          _("Fact %(name)s requires a unit dimension for concept %(concept)s with dataType %(dataType)s."),
                          xbrlObject=fact, name=fact.name, concept=cQn, dataType=cObj.dataType)
            fact._xValid = INVALID
    updateDimVals = {} # compiled values
    for dimName, dimVal in fact.factDimensions.items():
        if not isinstance(dimName, QName):
            if not dimPropPattern.match(dimName):
                txmyMdl.error("oime:unknownDimension",
                              _("Factspace %(name)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                              xbrlObject=fact, qname=dimName)
                fact._xValid = INVALID
        elif dimName not in coreDimensions:
            # dimName resolved to a QName (so oime:unknownDimension didn't fire)
            # but the named object may not be an XbrlDimension — e.g. a mistyped
            # QName that happens to match a concept or network.
            dimObj = txmyMdl.namedObjects.get(dimName)
            if not isinstance(dimObj, XbrlDimension):
                txmyMdl.error("oimte:invalidQNameReference",
                              _("Fact %(name)s uses dimension %(qname)s which is not defined as a dimension object in the taxonomy."),
                              xbrlObject=fact, name=fact.name, qname=dimName)
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
            emit_error(txmyMdl, code, msg, xbrlObject=fact, name=fact.name, **kwargs)
    if not fact.factDimensions:
        return
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

    # Validate dimension member types and domain class membership.
    # Per spec, only member objects may be used as members on taxonomy-defined dimensions,
    # only entity objects on xbrl:entity, and members must belong to the dimension's domain class.
    _prefixNS = getattr(getattr(fact, "module", None), "_prefixNamespaces", None)
    hasInvalidDimMember = False
    for dimName, dimVal in list(fact.factDimensions.items()):
        if not isinstance(dimName, QName) or dimName in (conceptCoreDim, periodCoreDim, unitCoreDim):
            continue
        if dimName == entityCoreDim:
            eQn = dimVal if isinstance(dimVal, QName) else (
                qname(dimVal, _prefixNS) if isinstance(dimVal, str) and ":" in dimVal else None)
            if eQn is not None:
                eObj = txmyMdl.namedObjects.get(eQn)
                if eObj is not None and not isinstance(eObj, XbrlEntity):
                    error("oimte:invalidFactDimensionMember",
                          _("The object %(memberName)s used as member on the xbrl:entity dimension is not an entity object. "
                            "Only entity objects are permitted as the xbrl:entity dimension member on a fact."),
                          memberName=eQn, dimensionName=dimName)
                    hasInvalidDimMember = True
        else:
            dimObj = txmyMdl.namedObjects.get(dimName)
            if not isinstance(dimObj, XbrlDimension):
                continue
            mQn = dimVal if isinstance(dimVal, QName) else (
                qname(dimVal, _prefixNS) if isinstance(dimVal, str) and ":" in dimVal else None)
            if mQn is not None:
                mObj = txmyMdl.namedObjects.get(mQn)
                if mObj is not None:
                    if not isinstance(mObj, XbrlMember):
                        error("oimte:invalidFactDimensionMember",
                              _("The object %(memberName)s used as a member on dimension %(dimensionName)s is not appropriate. "
                                "Only member objects are permitted as dimension members on a fact."),
                              memberName=mQn, dimensionName=dimName)
                        hasInvalidDimMember = True
                    # domainClasses is empty/None when the member carries no domain-class restriction.
                    elif mObj.domainClasses and dimObj.domainClass not in mObj.domainClasses:
                        error("oimte:invalidFactDimensionMember",
                              _("The object %(memberName)s used as member on dimension %(dimensionName)s is not part of "
                                "the dimension domain %(domainClass)s."),
                              memberName=mQn, dimensionName=dimName, domainClass=dimObj.domainClass)
                        hasInvalidDimMember = True
            elif isinstance(dimVal, str):
                # Unqualified string value: explicit dimensions use QName members (handled above);
                # a plain string here signals a typed dimension whose allowedDomainItem is a
                # data type rather than xbrl:memberObject, so validate the value against that type.
                domClassObj = txmyMdl.namedObjects.get(dimObj.domainClass)
                if isinstance(domClassObj, XbrlDomainClass):
                    allowedItem = domClassObj.allowedDomainItem
                    if allowedItem and allowedItem != qnXbrlMemberObj:
                        _valid, _dimVal = validateValue(txmyMdl, fact.module, fact, dimVal, allowedItem,
                                                       "", "oimte:invalidFactDimensionMember")
                        if _valid == INVALID:
                            hasInvalidDimMember = True
    if hasInvalidDimMember:
        return  # suppress noFactSpaceForFact when a more-specific member error was already raised

    # find cubes which fact is valid for (negative cubes don't provide valid fact space)
    matchedCubes = validateCubes(txmyMdl, fact)
    nonNegativeCubes = [c for c in matchedCubes
                        if getattr(txmyMdl.namedObjects.get(getattr(c, "cubeType", None)), "name", None) is None
                        or txmyMdl.namedObjects.get(c.cubeType).name.localName != "negativeCube"]
    if not nonNegativeCubes:
        error("oimte:noFactSpaceForFact",
              _("The fact %(name)s with concept %(conceptName)s does not fit within any defined cube fact space."),
              conceptName=cQn)
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
                (cubeDimObj.dimension, fact.factDimensions.get(cubeDimObj.dimension))
                for cubeDimObj in cubeObj.cubeDimensions
            )
            bucket = cellFacts.setdefault(cellKey, [])
            for fv in (fact.factValues or ()):
                bucket.append((fact, fv))


def validateCompleteReportCubes(txmyMdl):
    """Validate complete cubes after facts have been matched to their effective cubes.

    A cube's ``requiredCubes`` lists cubes whose dimensional space must be
    covered by facts.  The check differs by how the declaring cube is defined:

    - **Named declaring cube** (e.g. ``exp:SaleEventCube``): ``validateCompleteCube``
      is called on each required cube and fires ``oimte:factMissingFromCube`` for
      every concept in the required cube's domain that has no matching fact.
    - **Anonymous extension cube** (``extends`` with no ``name``): the requirement
      is satisfied when the model contains *any* facts at all.  If the model has
      zero facts, ``oimte:factMissingFromCube`` fires; if it has at least one fact,
      no error is raised even if none land in the required cube's domain.

    Taxonomy-only models (every module with a ``modelType`` set to ``xbrl:taxonomy``,
    with no co-loaded report module) are wholly exempt from completeness checks.
    """
    from .ValidateCubes import validateCompleteCube, validateCubeDuplicates
    from .XbrlConst import xbrl

    qnTaxonomyModelType = qname(xbrl, "xbrl:taxonomy")
    hasFacts = any(True for _ in txmyMdl.filterNamedObjects(XbrlFact))
    # isReportModel: any module has an explicit non-taxonomy modelType (e.g. xbrl:report)
    isReportModel = any(
        getattr(mod, "modelType", None) is not None and getattr(mod, "modelType", None) != qnTaxonomyModelType
        for mod in txmyMdl.xbrlModels.values()
    )
    # isTaxonomyModel: all modules with a modelType are xbrl:taxonomy (none are report)
    isTaxonomyModel = not isReportModel and any(
        getattr(mod, "modelType", None) == qnTaxonomyModelType
        for mod in txmyMdl.xbrlModels.values()
    )
    if isTaxonomyModel:
        return  # taxonomy-only models are exempt from cube completeness checks
    # Collect all cubes including anonymous extension cubes (not in namedObjects).
    allCubes = [cubeObj for mod in txmyMdl.xbrlModels.values() for cubeObj in (mod.cubes or ())]
    # Only anonymous extension cubes (no name) with requiredCubes bypass the hasFacts guard;
    # named cubes in taxonomy modules may declare requiredCubes for future report imports.
    hasAnonymousRequiredCubes = any(
        bool(txmyMdl.effectiveRequiredCubes(c))
        for c in allCubes
        if not getattr(c, 'name', None)
    )
    if not hasFacts and not isReportModel and not hasAnonymousRequiredCubes:
        return

    validated = set()
    for cubeObj in allCubes:
        isAnonymousExtCube = not getattr(cubeObj, 'name', None)
        for reqCubeQn in txmyMdl.effectiveRequiredCubes(cubeObj):
            if reqCubeQn not in validated:
                reqCubeObj = txmyMdl.namedObjects.get(reqCubeQn)
                if isinstance(reqCubeObj, XbrlCube):
                    # For anonymous extension cubes the requirement is satisfied
                    # when the model has any facts at all (even if none fall in
                    # the required cube's dimensional space).  Per-concept
                    # coverage is only checked for named declaring cubes.
                    if not (isAnonymousExtCube and hasFacts
                            and not getattr(reqCubeObj, '_cellFacts', None)):
                        validateCompleteCube(txmyMdl, reqCubeObj)
                    validated.add(reqCubeQn)
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
            resolveFact(txmyMdl, f.module, f)
            validateFactPosition(txmyMdl, f)

# NOTE: The legacy `validateReport(reportQn, reportObj, txmyMdl)` function has been
# removed along with the XbrlReport object. Cube completeness is now invoked directly
# via `validateCompleteReportCubes(txmyMdl)`. The per-fact resolution loop will be
# reintroduced in the streaming fact-pipeline refactor (step 2).

