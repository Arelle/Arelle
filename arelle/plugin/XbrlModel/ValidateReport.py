'''
See COPYRIGHT.md for copyright information.
'''

from isodate import isodatetime
import regex as re
from arelle.oim.Load import (PeriodPattern, UnitPrefixedQNameSubstitutionChar, UnitPattern,
                             PrefixedQName)
from arelle.ModelValue import QName, qname, timeInterval
from arelle import XbrlConst
from arelle.XmlValidateConst import VALID, INVALID
from .XbrlConst import unsupportedTypedDimensionDataTypes
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlCube import conceptCoreDim, languageCoreDim, periodCoreDim, unitCoreDim, coreDimensions
from .XbrlDimension import XbrlDimension, XbrlMember
from .XbrlReport import XbrlFact
from .XbrlUnit import parseUnitString, XbrlUnit
from .ValidateXbrlModel import validateValue
from .ValidateCubes import validateCubes

dimPropPattern = re.compile(r"^_[A-Za-z0-9]+$")

def resolveFact(txmyMdl, txmyObj, fact):
    # resolve QNames and other container-dependent values in fact
    name = fact.name
    cQn = fact.factDimensions.get(conceptCoreDim)
    if isinstance(cQn, str) and ":" in cQn:
        cQn = fact.factDimensions[conceptCoreDim] = qname(cQn, txmyObj._prefixNamespaces)
    cObj = txmyMdl.namedObjects.get(cQn)
    if cObj is None or not isinstance(cObj, XbrlConcept):
        txmyMdl.error("oime:missingConceptDimension", 
                      _("The concept core dimension MUST be present on fact: %(name)s and must be a taxonomy concept."),
                      xbrlObject=fact, name=fact.name)
        return
    cDataType = txmyMdl.namedObjects.get(cObj.dataType)
    if cDataType is None or not isinstance(cDataType, XbrlDataType):
        # presume this error would have been reported on validating loaded taxonomy model
        return
    for factValue in fact.factValues:
        _valid, _value = validateValue(txmyMdl, txmyObj, factValue, factValue.value, cDataType, f"/value", "oimte:factValueDataTypeMismatch")
        fact._valid = _valid
        fact._value = _value
        if factValue.language and concept.type.isOimTextFactType:
            if not factValue.language.islower():
                txmyMdl.error("xbrlje:invalidLanguageCodeCase",
                              _("Language MUST be lower case: \"%(lang)s\", fact %(name)s, concept %(concept)s."),
                              xbrlObject=fact, name=fact.name, lang=factValue.language)

    if not name:
        error("oime:missingFactId", _("The name (name) MUST be present on fact."))

    uStr = fact.factDimensions.get(unitCoreDim)
    if isinstance(uStr, str):
        if cDataType.isNumeric(txmyMdl):
            if uStr == "xbrli:pure":
                txmyMdl.error("oime:illegalPureUnit",
                              _("Unit MUST NOT have single numerator measure xbrli:pure with no denominators: %(unit)s"),
                              xbrlObject=fact, unit=uStr)
            elif not UnitPattern.match( PrefixedQName.sub(UnitPrefixedQNameSubstitutionChar, uStr) ):
                txmyMdl.error("oimce:invalidUnitStringRepresentation",
                              _("Unit string representation is lexically invalid, %(unit)s, fact id %(name)s"),
                              xbrlObject=fact, unit=uStr)
            else:
                fact.factDimensions[unitCoreDim] = parseUnitString(uStr, fact, txmyObj, txmyMdl)
        else:
            txmyMdl.error("oime:misplacedUnitDimension",
                          _("The unit core dimension MUST NOT be present on non-numeric facts: %(concept)s, unit %(unit)s."),
                          xbrlObject=fact, concept=cQn, unit=uStr)
    updateDimVals = {} # compiled values
    for dimName, dimVal in fact.factDimensions.items():
        if not isinstance(dimName, QName):
            if not dimPropPattern.match(dimName):
                txmyMdl.error("oime:unknownDimension",
                              _("Factspace %(name)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                              xbrlObject=fact, qname=dimName)
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
                        if _valid < VALID and fact._valid >= VALID:
                            fact._valid = _valid # invalidate dimensionally invalid fact
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
    def error(code, msg, **kwargs):
         txmyMdl.error(code, msg, xbrlObject=fact, name=getattr(fact,"name"), **kwargs)
    cQn = fact.factDimensions.get(conceptCoreDim)
    cObj = txmyMdl.namedObjects.get(cQn)
    if cObj is None or not isinstance(cObj, XbrlConcept):
        return

    fact._cubes = None # cubes which fact complies with

    # if period is provided statically, validate and then fit to cubes.

    if periodCoreDim in fact.factDimensions:
        per = fact.factDimensions[periodCoreDim]
        if isinstance(per, str):
            if not PeriodPattern.match(per):
                error("oimce:invalidPeriodRepresentation",
                              _("The fact %(name)s, concept %(element)s has a lexically invalid period dateTime %(periodError)s"),
                              element=cQn, periodError=per)
                return
            _start, _sep, _end = per.rpartition('/')
            if ((cObj.periodType == "duration" and (not _start or _start == _end)) or
                  (cObj.periodType == "instant" and _start and _start != _end)):
                error("oime:invalidPeriodDimension",
                              _("Invalid period for %(periodType)s fact %(name)s period %(period)s."),
                              name=name, periodType=cObj.periodType, period=per)
                return # skip creating fact because context would be bad
            per = fact.factDimensions["_periodValue"] = timeInterval(per)
    elif cObj.periodType != "none":
        error("oime:missingPeriodDimension",
                       _("Missing period for %(periodType)s fact %(name)s."),
                       periodType=cObj.periodType)

    # find cubes which fact is valid for
    fact._cubes = validateCubes(txmyMdl, fact)
    if not fact._cubes:
        error("oimte:noFactSpaceForFact",
              _("Factspace %(name)s is not dimensionally valid in any cube."))
    else:
        for cubeObj in fact._cubes:
            if not hasattr(cubeObj, "_factspaces"):
                cubeObj._factspaces = set()
            cubeObj._factspaces.add(fact)

def validateTable(reportObj, txmyMdl, table):
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
    # validate facts whose values represent dateResolution concepts first
    for qn in txmyMdl.dateResolutionConceptNames:
        f = txmyMdl.namedObjects.get(qn)
        if isinstance(f, XbrlFact):
            validateFact(f, reportQn, reportObj, txmyMdl)

def validateReport(txmyMdl, reportObj):
    for table in reportObj.tables.values():
        validateTable(table, reportQn, reportObj, txmyMdl)
    # validate facts not involved in dateResolution
    for qn, f in reportObj.facts.items():
        if qn not in txmyMdl.dateResolutionConceptNames:
            # check for possible cubes using vector search
            validateFact(f, reportQn, reportObj, txmyMdl)

