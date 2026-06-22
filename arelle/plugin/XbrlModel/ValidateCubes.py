'''
See COPYRIGHT.md for copyright information.
'''

from arelle.ModelValue import qname, QName
from .XbrlCube import XbrlCube, conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim
from .XbrlDimension import XbrlDimension
from .XbrlFact import XbrlFact
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
        dimName = cubeDimObj.dimension
        if dimName in coreToFactDim:
            mems = cubeDimObj.allowedMembers(compMdl)
            factDimVal = factspace.factDimensions.get(dimName)
            # Entity (and other core) dimension values may still be carried as
            # strings (e.g. "exp:ExampleCo") rather than resolved QNames, while
            # `mems` is a set of QName objects. Resolve on the fly so that
            # matching does not spuriously fail.
            if (mems and not isinstance(factDimVal, QName) and isinstance(factDimVal, str)
                    and ":" in factDimVal):
                resolved = qname(factDimVal, getattr(factspace.parent, "_prefixNamespaces", None))
                if resolved is not None:
                    factDimVal = resolved
            if mems and factDimVal not in mems:
                hasDims = False # skip this cube
                break
        elif dimName == periodCoreDim:
            factPerVal = factspace.factDimensions.get("_periodValue")
            if factPerVal is None and not cubeDimObj.optional:
                continue # skip forever/missing period and not allowDomainFacts
            # periodConstraints are content selectors (they filter facts INTO
            # the cube for query/reporting views) and do NOT gate dimensional
            # validity. A fact whose period does not satisfy a periodConstraint
            # still shares the cube's dimensional space for purposes of
            # oimte:noFactSpaceForFact. See oim-taxonomy spec
            # "Period constraint object" section.
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
    # replace with vectorized search
    cellFacts = getattr(cubeObj, "_cellFacts", None)
    if not any(True for _ in compMdl.filterNamedObjects(XbrlFact)):
        return
    if not cellFacts:
        compMdl.error("oimte:factMissingFromCube",
                     _("The complete cube %(name)s has no facts."),
                      xbrlObject=cubeObj, name=cubeObj.name)


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

