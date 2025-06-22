'''
See COPYRIGHT.md for copyright information.
'''

from .XbrlCube import XbrlCube, conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim
from arelle.XmlValidateConst import VALID, INVALID

coreToFactDim = {conceptCoreDim: "concept", entityCoreDim: "entity", unitCoreDim: "unit"}

def validateCubes(fact, txmyMdl):
    usableCubes = []
    for cubeObj in txmyMdl.filterNamedObjects(XbrlCube):
        hasCoreDims = True
        hasDims = True
        for cubeDimObj in cubeObj.cubeDimensions:
            dimName = cubeDimObj.dimensionName
            if dimName in coreToFactDim:
                mems = cubeDimObj.allowedMembers(txmyMdl)
                if mems and fact.dimensions.get(coreToFactDim[dimName]) not in mems:
                    hasDims = False # skip this cube
                    break
            elif dimName == periodCoreDim:
                factPerVal = fact.dimensions.get("_periodValue")
                if timeInterval is None and not cubeDimObj.allowDomainFacts:
                    continue # skip forever/missing period and not allowDomainFacts
                hasAnyPerMatch = True
                for perConstObj in cubeDimObj.periodConstraints:
                    if ((perConstObj.periodType == "none" and timeInterval is not None) or
                        (perConstObj.periodType == "instant" != timeInterval.isInstant)):
                        continue # skip this perCnstrt
                    if (getattr(perConstObj, "_timeSpanValid", 0) == VALID and
                        (factPerVal.start is None or factPerVal.end is None or
                        factPerVal.start + perConstObj._timeSpanValue != factPerVal.end)):
                        continue # skip this perCnstrt
                    if (getattr(perConstObj, "_periodFormatValid", 0) == VALID and
                        perConstObj._periodFormatValue != factPerVal):
                        continue # skip this perCnstrt
                    hasPerMatch = True
                    for dtResProp in ("monthDay", "endDate", "startDate", "onOrAfter", "onOrBefore"):
                        dtResObj = getattr(perConstObj, dtResProp, None)
                        if dtResObj is not None:
                            resPreVals = ()
                            if getattr(dtResObj, "_valueValid", 0) == VALID:
                                resPerVal = (dtResObj._valueValue,)
                            elif dtResObj.conceptName:
                                resPerVal = set(f.dimensions.get("_periodValue")
                                                for f in txmyMdl.factsByName.get(dtResObj.conceptName, ())
                                                if "_periodValue" in f.dimensions)
                            elif dtResObj.context:
                                resPerVal = set(f.dimensions.get("_periodValue")[dtResObj.context.atSuffix == "end"]
                                                for f in txmyMdl.factsByName.get(dtResObj.conceptName, ())
                                                if "_periodValue" in f.dimensions)
                        if getattr(dtResObj, "_timeShiftValid", 0) == VALID:
                            timeShift = dtResObj._timeShiftValue
                            resPerVals = set(r + timeShift for r in resPerVals)
                        if ((dtResProp == "monthDay" and not any(r.month == factPerVal.end.month and r.day == factPerVal.end.day for r in resPerVals)) or
                            (dtResProp == "endDate" and not any(r == factPerVal.end for r in resPerVals)) or
                             (dtResProp == "startDate" and not any(r == factPerVal.start for r in resPerVals)) or
                             (dtResProp == "onOrAfter" and not any(r >= factPerVal.start for r in resPerVals)) or
                             (dtResProp == "onOrBefore" and not any(r <= factPerVal.end for r in resPerVals))):
                            hasPerMatch = False
                            break
                    if not hasPerMatch:
                        hasAnyPerMatch = False
                        break
                if not hasAnyPerMatch:
                    hasDims = False # skip this cube
                    break
            elif dimName not in fact.dimensions:
                if not cubeDimObj.allowDomainFacts:
                    hasDims = False # skip this cube
                    break
            else: # taxonomy defined dim
                if fact.dimensions.get(dimName) not in cubeDimObj.allowedMembers(txmyMdl):
                    hasDims = False # skip this cube
                    break
        if hasDims:
            usableCubes.append(cubeObj)
    return usableCubes
        
