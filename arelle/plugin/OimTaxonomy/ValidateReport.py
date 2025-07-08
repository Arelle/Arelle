'''
See COPYRIGHT.md for copyright information.
'''

from isodate import isodatetime
import regex as re
from arelle.oim.Load import (PeriodPattern, UnitPrefixedQNameSubstitutionChar, UnitPattern,
                             PrefixedQName, OIMException)
from arelle.ModelValue import QName, qname, timeInterval
from arelle import XbrlConst
from arelle.XmlValidateConst import VALID, INVALID
from .XbrlConst import unsupportedTypedDimensionDataTypes
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlDimension import XbrlDimension, XbrlMember
from .XbrlTableTemplate import XbrlTableTemplate
from .ValidateTaxonomyModel import validateValue
from .ValidateCubes import validateCubes

dimPropPattern = re.compile(r"^_[A-Za-z0-9]+$")

def validateFact(fact, reportQn, reportObj, txmyMdl):
    def error(code, msg, **kwargs):
         txmyMdl.error(code, msg, xbrlObject=fact, id=getattr(fact,"id"), **kwargs)
    initialValidation = not hasattr(fact, "_valid")
    name = fact.name
    cQn = fact.dimensions.get("concept")
    if isinstance(cQn, str) and ":" in cQn:
        cQn = fact.dimensions["concept"] = qname(cQn, reportObj._prefixNamespaces)
    cObj = txmyMdl.namedObjects.get(cQn)
    if cObj is None or not isinstance(cObj, XbrlConcept):
        error("oime:missingConceptDimension", _("The concept core dimension MUST be present on fact: %(id)s and must be a taxonomy concept."))
        return
    cDataType = txmyMdl.namedObjects.get(cObj.dataType)
    if cDataType is None or not isinstance(cDataType, XbrlDataType):
        # presume this error would have been reported on validating loaded taxonomy model
        return
    _valid, _value = validateValue(txmyMdl, fact, fact.value, cDataType, f"/value")
    fact._valid = _valid
    fact._value = _value
    if not name:
        error("oime:missingFactId", _("The name (id) MUST be present on fact."))
    if "language" in fact.dimensions:
        lang = fact.dimensions["language"]
        if concept.type.isOimTextFactType:
            if not lang.islower():
                error("xbrlje:invalidLanguageCodeCase",
                      _("Language MUST be lower case: \"%(lang)s\", fact %(name)s, concept %(concept)s."),
                      concept=cQn, name=name, lang=lang)
    if "period" in fact.dimensions:
        per = fact.dimensions["period"]
        if isinstance(per, str):
            if not PeriodPattern.match(per):
                error("oimce:invalidPeriodRepresentation",
                              _("The fact %(name)s, concept %(element)s has a lexically invalid period dateTime %(periodError)s"),
                              element=cQn, name=name, periodError=per)
                return
            _start, _sep, _end = per.rpartition('/')
            if ((cObj.periodType == "duration" and (not _start or _start == _end)) or
                  (cObj.periodType == "instant" and _start and _start != _end)):
                error("oime:invalidPeriodDimension",
                              _("Invalid period for %(periodType)s fact %(name)s period %(period)s."),
                              name=name, periodType=cObj.periodType, period=per)
                return # skip creating fact because context would be bad
            per = fact.dimensions["_periodValue"] = timeInterval(per)
    elif cObj.periodType != "duration":
        error("oime:missingPeriodDimension",
                       _("Missing period for %(periodType)s fact %(name)s."),
                       name=name, periodType=cObj.periodType, period=per)
    uStr = fact.dimensions.get("unit")
    if isinstance(uStr, str):
        if cDataType.isNumeric(txmyMdl):
            if uStr == "xbrli:pure":
                error("oime:illegalPureUnit",
                      _("Unit MUST NOT have single numerator measure xbrli:pure with no denominators: %(unit)s"),
                      unit=uStr)
            elif not UnitPattern.match( PrefixedQName.sub(UnitPrefixedQNameSubstitutionChar, uStr) ):
                error("oimce:invalidUnitStringRepresentation",
                      _("Unit string representation is lexically invalid, %(unit)s, fact id %(name)s"),
                      name=name, unit=uStr)
            else:
                _mul, _sep, _div = uStr.partition('/')
                if _mul.startswith('('):
                    _mul = _mul[1:-1]
                _muls = [u for u in _mul.split('*') if u]
                if _div.startswith('('):
                    _div = _div[1:-1]
                _divs = [u for u in _div.split('*') if u]
                if _muls != sorted(_muls) or _divs != sorted(_divs):
                    error("oimce:invalidUnitStringRepresentation",
                          _("Unit string representation measures are not in alphabetical order, %(unit)s, fact id %(name)s"),
                          name=name, unit=uStr)
                try:
                    mulQns = tuple(qname(u, reportObj._prefixNamespaces, prefixException=OIMException("oimce:unboundPrefix",
                                                                              _("Unit prefix is not declared: %(unit)s"),
                                                                              unit=u))
                                   for u in _muls)
                    divQns = tuple(qname(u, reportObj._prefixNamespaces, prefixException=OIMException("oimce:unboundPrefix",
                                                                              _("Unit prefix is not declared: %(unit)s"),
                                                                              unit=u))
                                   for u in _divs)
                    fact.dimensions["unit"] = (mulQns,divQns)
                except OIMException as ex:
                    error(ex.code, ex.message, modelObject=fact, **ex.msgArgs)
        else:
            error("oime:misplacedUnitDimension",
                          _("The unit core dimension MUST NOT be present on non-numeric facts: %(concept)s, unit %(unit)s."),
                          concept=cQn, unit=uStr)
    updateDimVals = {} # compiled values
    for dimName, dimVal in fact.dimensions.items():
        if not isinstance(dimName, QName):
            if dimName not in {"concept", "entity", "period", "unit", "language"} and not dimPropPattern.match(dimName):
                error("oime:unknownDimension",
                              _("Fact %(name)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                              name=name, qname=dimName)
        if isinstance(dimName, QName):
            dimObj = txmyMdl.namedObjects.get(dimName)
            if not isinstance(dimObj, XbrlDimension):
                error("oime:unknownDimension",
                              _("Fact %(name)s taxonomy-defined dimension QName not be resolved with available DTS: %(qname)s."),
                              name=name, qname=dimName)
                return
            if dimObj.isExplicitDimension:
                if initialValidation and isinstance(dimVal, str) and ":" in dimVal:
                    memQn = fact.dimensions[dimName] = qname(dimVal, reportObj._prefixNamespaces)
                    if memQn:
                        updateDimVals[dimName] = memQn
                else: # already compiled into QName
                    memQn = dimVal
                if memQn is None:
                    error("oime:invalidDimensionValue",
                                  _("Fact %(name)s taxonomy-defined explicit dimension value is invalid: %(memberQName)s."),
                                  name=name, memberQName=memQn)
                    return
                memObj = txmyMdl.namedObjects.get(memQn)
                if not isinstance(memObj, XbrlMember):
                    error("oime:invalidDimensionValue",
                                  _("Fact %(name)s taxonomy-defined explicit dimension value must not be the default member: %(memberQName)s."),
                                  name=name, memberQName=memQn)
                    return
            elif dimObj.isTypedDimension:
                domDataTypeObj = txmyMdl.namedObjects.get(dimObj.domainDataType)
                if domDataTypeObj is None or domDataTypeObj.xsBaseType in unsupportedTypedDimensionDataTypes or (
                   domDataTypeObj.instanceOfType(XbrlConst.dtrPrefixedContentTypes, txmyMdl) and not dimObj.domainDataType.instanceOfType(XbrlConst.dtrSQNameNamesTypes, txmyMdl)):
                    error("oime:unsupportedDimensionDataType",
                                  _("Fact %(name)s taxonomy-defined typed dimension value is not supported: %(memberQName)s."),
                                  name=name, memberQName=dimVal)
                    return
                #if (canonicalValuesFeature and dimVal is not None and
                #    not CanonicalXmlTypePattern.get(domDataTypeObj.xsBaseType, NoCanonicalPattern).match(dimVal)):
                #    txmyMdl.error("xbrlje:nonCanonicalValue",
                #                  _("Numeric typed dimension must have canonical %(type)s value \"%(value)s\": %(concept)s."),
                #                  xbrlObject=obj, type=dimConcept.typedDomainElement.baseXsdType, concept=dimConcept, value=dimVal)
                if initialValidation:
                    _valid, _value = validateValue(txmyMdl, dimObj, dimVal, domDataTypeObj, f"/value")
                    if _valid < VALID and fact._valid >= VALID:
                        fact._valid = _valid # invalidate dimensionally invalid fact
                    if _valid >= VALID:
                        updateDimVals[dimName] = _value
    for dimName, dimVal in updateDimVals.items():
        fact.dimensions[dimName] = dimVal

    # find cubes which fact is valid for
    fact._cubes = validateCubes(fact, txmyMdl)
    if not fact._cubes:
        error("xbrlce:invalidDimensionValue",
              _("Fact %(name)s is not dimensionally valid in any cube."),
              name=name)

def validateTable(table, reportQn, reportObj, txmyMdl):
    # ensure template exists
    url = table.url
    if not txmyMdl.fileSource.exists(url) and not table.optional:
        error("xbrlce:missingRequiredCSVFile",
              _("The url %(url)s MUST be an existing file for non-optional table %(table)s."),
              table=table.name, url=table.url)

    tmplObj = txmyMdl.namedObjects.get(table.template)
    if tmplObj is None or not isinstance(cObj, XbrlTableTemplate):
        error("xbrlce:unknownTableTemplate",
              _("The table %(table) template, %(name)s MUST be the identifier of a table template present in the OIM Taxonomy Model."),
              table=table.name, name=table.template)


def validateReport(reportQn, reportObj, txmyMdl):
    for table in reportObj.tables.values():
        validateReport(table, reportQn, reportObj, txmyMdl)
    for fact in reportObj.facts.values():
        validateFact(fact, reportQn, reportObj, txmyMdl)

