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
from .XbrlLayout import XbrlTableTemplate
from .XbrlUnit import parseUnitString, XbrlUnit
from .ValidateTaxonomyModel import validateValue
from .ValidateCubes import validateCubes

dimPropPattern = re.compile(r"^_[A-Za-z0-9]+$")

def validateFactspace(factspace, reportQn, reportObj, txmyMdl):
    def error(code, msg, **kwargs):
         txmyMdl.error(code, msg, xbrlObject=factspace, name=getattr(factspace,"name"), **kwargs)
    initialValidation = not hasattr(factspace, "_valid")
    name = factspace.name
    cQn = factspace.factDimensions.get(conceptCoreDim)
    if isinstance(cQn, str) and ":" in cQn:
        cQn = factspace.factDimensions[conceptCoreDim] = qname(cQn, reportObj._prefixNamespaces)
    cObj = txmyMdl.namedObjects.get(cQn)
    if cObj is None or not isinstance(cObj, XbrlConcept):
        error("oime:missingConceptDimension", _("The concept core dimension MUST be present on factspace: %(name)s and must be a taxonomy concept."))
        return
    cDataType = txmyMdl.namedObjects.get(cObj.dataType)
    if cDataType is None or not isinstance(cDataType, XbrlDataType):
        # presume this error would have been reported on validating loaded taxonomy model
        return
    for factValue in factspace.factValues:
        _valid, _value = validateValue(txmyMdl, reportObj, factValue, factValue.value, cDataType, f"/value", "oime:invalidFactValue")
        factspace._valid = _valid
        factspace._value = _value
        if factValue.language and concept.type.isOimTextFactType:
            if not factValue.language.islower():
                error("xbrlje:invalidLanguageCodeCase",
                      _("Language MUST be lower case: \"%(lang)s\", factspace %(name)s, concept %(concept)s."),
                      concept=cQn, lang=factValue.language)

    if not name:
        error("oime:missingFactId", _("The name (name) MUST be present on factspace."))
    if periodCoreDim in factspace.factDimensions:
        per = factspace.factDimensions[periodCoreDim]
        if isinstance(per, str):
            if not PeriodPattern.match(per):
                error("oimce:invalidPeriodRepresentation",
                              _("The factspace %(name)s, concept %(element)s has a lexically invalid period dateTime %(periodError)s"),
                              element=cQn, periodError=per)
                return
            _start, _sep, _end = per.rpartition('/')
            if ((cObj.periodType == "duration" and (not _start or _start == _end)) or
                  (cObj.periodType == "instant" and _start and _start != _end)):
                error("oime:invalidPeriodDimension",
                              _("Invalid period for %(periodType)s factspace %(name)s period %(period)s."),
                              name=name, periodType=cObj.periodType, period=per)
                return # skip creating factspace because context would be bad
            per = factspace.factDimensions["_periodValue"] = timeInterval(per)
    elif cObj.periodType != "none":
        error("oime:missingPeriodDimension",
                       _("Missing period for %(periodType)s factspace %(name)s."),
                       periodType=cObj.periodType)
    uStr = factspace.factDimensions.get(unitCoreDim)
    if isinstance(uStr, str):
        if cDataType.isNumeric(txmyMdl):
            if uStr == "xbrli:pure":
                error("oime:illegalPureUnit",
                      _("Unit MUST NOT have single numerator measure xbrli:pure with no denominators: %(unit)s"),
                      unit=uStr)
            elif not UnitPattern.match( PrefixedQName.sub(UnitPrefixedQNameSubstitutionChar, uStr) ):
                error("oimce:invalidUnitStringRepresentation",
                      _("Unit string representation is lexically invalid, %(unit)s, factspace id %(name)s"),
                      unit=uStr)
            else:
                factspace.factDimensions[unitCoreDim] = parseUnitString(uStr, factspace, reportObj, txmyMdl)
        else:
            error("oime:misplacedUnitDimension",
                          _("The unit core dimension MUST NOT be present on non-numeric facts: %(concept)s, unit %(unit)s."),
                          concept=cQn, unit=uStr)
    updateDimVals = {} # compiled values
    for dimName, dimVal in factspace.factDimensions.items():
        if not isinstance(dimName, QName):
            if not dimPropPattern.match(dimName):
                error("oime:unknownDimension",
                              _("Factspace %(name)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                              qname=dimName)
        '''
        if isinstance(dimName, QName):
            dimObj = txmyMdl.namedObjects.get(dimName)
            if dimName not in coreDimensions:
                if not isinstance(dimObj, XbrlDimension):
                    error("oime:unknownDimension",
                                  _("Factspace %(name)s taxonomy-defined dimension QName not be resolved to a dimension object with available DTS: %(qname)s."),
                                  qname=dimName)
                elif dimObj.isExplicitDimension:
                    if initialValidation and isinstance(dimVal, str) and ":" in dimVal:
                        memQn = factspace.factDimensions[dimName] = qname(dimVal, reportObj._prefixNamespaces)
                        if memQn:
                            updateDimVals[dimName] = memQn
                    else: # already compiled into QName
                        memQn = dimVal
                    if memQn is None:
                        error("oime:invalidDimensionValue",
                                      _("Factspace %(name)s taxonomy-defined explicit dimension value is invalid: %(memberQName)s."),
                                      memberQName=memQn)
                        return
                    memObj = txmyMdl.namedObjects.get(memQn)
                    if not isinstance(memObj, XbrlMember):
                        error("oime:invalidDimensionValue",
                                      _("Factspace %(name)s taxonomy-defined explicit dimension value must not be the default member: %(memberQName)s."),
                                      memberQName=memQn)
                        return
                elif dimObj.isTypedDimension:
                    domDataTypeObj = txmyMdl.namedObjects.get(dimObj.domainDataType)
                    if domDataTypeObj is None or domDataTypeObj.xsBaseType in unsupportedTypedDimensionDataTypes or (
                       domDataTypeObj.instanceOfType(XbrlConst.dtrPrefixedContentTypes, txmyMdl) and not dimObj.domainDataType.instanceOfType(XbrlConst.dtrSQNameNamesTypes, txmyMdl)):
                        error("oime:unsupportedDimensionDataType",
                                      _("Factspace %(name)s taxonomy-defined typed dimension value is not supported: %(memberQName)s."),
                                      memberQName=dimVal)
                        return
                    #if (canonicalValuesFeature and dimVal is not None and
                    #    not CanonicalXmlTypePattern.get(domDataTypeObj.xsBaseType, NoCanonicalPattern).match(dimVal)):
                    #    txmyMdl.error("xbrlje:nonCanonicalValue",
                    #                  _("Numeric typed dimension must have canonical %(type)s value \"%(value)s\": %(concept)s."),
                    #                  xbrlObject=obj, type=dimConcept.typedDomainElement.baseXsdType, concept=dimConcept, value=dimVal)
                    if initialValidation:
                        _valid, _value = validateValue(txmyMdl, reportObj, dimObj, dimVal, domDataTypeObj, f"/value", "oime:invalidDimensionValue")
                        if _valid < VALID and factspace._valid >= VALID:
                            factspace._valid = _valid # invalidate dimensionally invalid factspace
                        if _valid >= VALID:
                            updateDimVals[dimName] = _value
            elif dimName == unitCoreDim:
                for unitNumDenom in dimVal:
                    for unitQn in unitNumDenom:
                        unitObj = txmyMdl.namedObjects.get(unitQn)
                        if not isinstance(unitObj, XbrlUnit):
                            error("oime:unknownDimension",
                                          _("Factspace %(name)s unit dimension QName not be resolved to an xbrl Unit object with available DTS: %(qname)s."),
                                          qname=dimName)
                        elif not cDataType.instanceOfType(unitObj.dataType, txmyMdl):
                            error("oimte:invalidPropertyValue",
                                          _("Factspace %(name)s unit dimension data type %(unitDataType)s does not correspond to concept data type %(factDataType)s."),
                                          unitDataType=unitObj.dataType, factDataType=cObj.dataType)
        '''
    for dimName, dimVal in updateDimVals.items():
        factspace.factDimensions[dimName] = dimVal

    # find cubes which factspace is valid for
    factspace._cubes = validateCubes(factspace, txmyMdl)
    if not factspace._cubes:
        error("oimte:noFactSpaceForFact",
              _("Factspace %(name)s is not dimensionally valid in any cube."))

def validateTable(table, reportQn, reportObj, txmyMdl):
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


def validateReport(reportQn, reportObj, txmyMdl):
    for table in reportObj.tables.values():
        validateTable(table, reportQn, reportObj, txmyMdl)
    for factspace in reportObj.facts.values():
        validateFact(factspace, reportQn, reportObj, txmyMdl)

