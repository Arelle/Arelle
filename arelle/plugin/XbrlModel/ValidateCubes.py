'''
See COPYRIGHT.md for copyright information.
'''

from arelle.ModelValue import qname, QName
from .XbrlCube import XbrlCube, conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim
from .XbrlDimension import XbrlDimension
from .VectorSearch import buildXbrlVectors, searchXbrl, searchXbrlBatchTopk, SEARCH_CUBES, SEARCH_FACTPOSITIONS, SEARCH_BOTH
from arelle.XmlValidateConst import VALID, INVALID

coreToFactDim = {conceptCoreDim: "concept", entityCoreDim: "entity", unitCoreDim: "unit"}

def matchFactToCube(compMdl, factspace, cubeObj):
    """Check if the factspace dimensions match the cube dimensions and allowed members.
        Return True if the factspace matches the cube, False otherwise. 

        The factspace matches the cube if for each dimension of the cube, there is a corresponding dimension 
        in the factspace with a value that matches one of the allowed members of the cube dimension. 

        For core dimensions (concept, entity, unit), the factspace dimension value must match one of the 
        allowed members of the cube dimension. 

        For period dimension, the factspace period value must match one of the period constraints of the cube dimension. 

        For taxonomy-defined dimensions, the factspace dimension value must match one of the allowed members of the cube dimension. 

        If any cube dimension does not have a matching factspace dimension with a matching value, then the factspace 
        does not match the cube and the function returns False. 
    """
    hasCoreDims = True
    hasDims = True
    for cubeDimObj in cubeObj.cubeDimensions:
        dimName = cubeDimObj.dimensionName
        if dimName in coreToFactDim:
            mems = cubeDimObj.allowedMembers(compMdl)
            if mems and factspace.factDimensions.get(dimName) not in mems:
                hasDims = False # skip this cube
                break
        elif dimName == periodCoreDim:
            factPerVal = factspace.factDimensions.get("_periodValue")
            if factPerVal is None and not cubeDimObj.allowDomainFacts:
                continue # skip forever/missing period and not allowDomainFacts
            hasAnyPerMatch = True
            for perConstObj in cubeDimObj.periodConstraints:
                #if perConstObj.conceptName:
                #
                # context = get facts
                timeSpan = getattr(perConstObj, "_timeSpanValue", None)
                #if ((perConstObj.periodType == "none" and timeSpan is not None) or
                #    (perConstObj.periodType == "instant" != timeSpan.isInstant)):
                #    continue # skip this perCnstrt
                if (timeSpan is not None and
                    (factPerVal.start is None or factPerVal.end is None or
                    factPerVal.start + timeSpan != factPerVal.end)):
                    continue # skip this perCnstrt
                if perConstObj.periodPatternMatch(factPerVal) == False:
                    continue # skip this perCnstrt
                hasPerMatch = True
                for dtResProp in ("monthDay", "endDate", "startDate", "onOrAfter", "onOrBefore"):
                    dtResObj = getattr(perConstObj, dtResProp, None)
                    resPerVals = ()
                    if dtResObj is not None:
                        if getattr(dtResObj, "_valueValid", 0) == VALID:
                            resPerVal = (dtResObj._valueValue,)
                        elif dtResObj.conceptName:
                            resPerVal = set(f.dimensions.get("_periodValue")
                                            for f in compMdl.factsByName.get(dtResObj.conceptName, ())
                                            if "_periodValue" in f.dimensions)
                        elif dtResObj.context:
                            resPerVal = set(f.dimensions.get("_periodValue")[dtResObj.context.atSuffix == "end"]
                                            for f in compMdl.factsByName.get(dtResObj.conceptName, ())
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
        elif dimName not in factspace.factDimensions:
            if not cubeDimObj.allowDomainFacts:
                hasDims = False # skip this cube
                break
        else: # taxonomy defined dim
            dimObj = compMdl.namedObjects.get(dimName)
            isTyped = bool(cubeDimObj.domainDataType)
            if not isTyped:
                dimMbrQn = qname(factspace.factDimensions.get(dimName), factspace.parent._prefixNamespaces)
            if (isinstance(dimObj, XbrlDimension) and not isTyped and
                dimMbrQn not in cubeDimObj.allowedMembers(compMdl)):
                hasDims = False # skip this cube
                break
    return hasDims

def validateCubes(compMdl, factspace):
    """Find cubes that match the dimensions of the factspace, and validate the factspace against those cubes. 
        Return list of cubes that match the factspace dimensions. 

        This is a first step toward validating the factspace against the cubes, and then validating the facts against the cubes. 

        The cube fit scores are used to find likely cubes, and then the factspace is validated against those cubes. 

        The factspace is validated against a cube by checking that the dimensions of the factspace match the dimensions of the cube, 
        and that the values of the dimensions of the factspace match the allowed members of the cube dimensions.

        The factspace is validated against a cube by checking that for each dimension of the cube, there is a corresponding dimension 
        in the factspace with a value that matches one of the allowed members of the cube dimension. 

        If all dimensions of the cube are matched by dimensions in the factspace with matching values, 
        then the factspace is considered to match the cube. The function returns a list of cubes that match the 
        factspace dimensions and values.
    """
    # find likely cubes
    cubeFitQuery = [(dimQn, value) for dimQn,value in factspace.factDimensions.items() if isinstance(dimQn, QName)]
    results = searchXbrl(compMdl, cubeFitQuery, SEARCH_CUBES, 50) # allow sufficient return scores
    print(f"Cube fit scores for factspace {factspace.name} {[(r[0],r[1].name) for r in results]}")

    usableCubes = []
    for score, cubeObj in results:
        if score < .1 : # find right value here
            break
        if matchFactToCube(compMdl, factspace, cubeObj):
            usableCubes.append(cubeObj)
    return usableCubes

def validateCompleteCube(compMdl, cubeObj):
    # replace with vectorized search
    factspaces = getattr(cubeObj, "_factspaces", None)
    if not factspaces:
        compMdl.error("oimte:factMissingFromCube",
                     _("The complete cube %(name)s has no facts."),
                      xbrlObject=cubeObj, name=cubeObj.name)

