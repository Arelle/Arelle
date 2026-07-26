'''
See COPYRIGHT.md for copyright information.
'''

from arelle.ModelValue import qname, QName
from .XbrlConcept import XbrlConcept
from .XbrlCube import XbrlCube, conceptCoreDim, periodCoreDim, entityCoreDim, unitCoreDim
from .XbrlDimension import XbrlDimension, XbrlDomainNetwork
from .XbrlFact import XbrlFact
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
            if mems and factDimVal not in mems:
                hasDims = False # skip this cube
                break
        elif dimName == periodCoreDim:
            factPerVal = factspace.factDimensions.get("_periodValue")
            if factPerVal is None and not cubeDimObj.optional:
                hasDims = False # period required but fact has no period (e.g. periodType:none concept)
                break
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

