'''
See COPYRIGHT.md for copyright information.
'''

import regex as re, dateutil
from collections import defaultdict
from decimal import Decimal
from typing import GenericAlias, _GenericAlias, _UnionGenericAlias
from arelle.ModelValue import QName, timeInterval, qname
from arelle.PythonUtil import attrdict
from arelle.XmlValidate import languagePattern, validateValue as validateXmlValue,\
    INVALID, VALID, NONE
from arelle.XbrlConst import isNumericXsdType
from ordered_set import OrderedSet
from arelle.oim.Load import EMPTY_DICT, csvPeriod
from .ValidateCubes import validateCompleteCube
from .XbrlHeading import XbrlHeading
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlCollectionType, XbrlUnitType
from .XbrlConst import (xbrl, qnXbrlReferenceObj, qnXbrlLabelObj, qnXbrlHeadingObj, qnXbrlConceptObj,
                        qnXbrlMemberObj, qnXbrlEntityObj, qnXbrlUnitObj, qnXbrlImportTaxonomyObj,
                        reservedPrefixNamespaces, qnXbrlLabelObj, qnXbrlPropertyObj,
                        qnXbrlDimensionObj, qnXbrlRootSource, EMPTY_FROZENSET)
from .XbrlCube import (XbrlCube, XbrlCubeType, baseCubeTypes, XbrlCubeDimension,
                       periodCoreDim, conceptCoreDim, entityCoreDim, unitCoreDim, languageCoreDim, coreDimensions,
                    conceptDomainClass, entityDomainClass, unitDomainClass, languageDomainClass, periodDomainClass,
                    defaultCubeType, reportCubeType, timeSeriesCubeType,
                    timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, excludedIntervalsPropType,
                    completeTimeSeriesPropType, aggregationPropType,
                    periodConstraintPeriodPattern)
from .XbrlDimension import XbrlDimension, XbrlDomainNetwork, XbrlDomainClass, XbrlMember, xbrlMemberObj
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent
from .XbrlLayout import XbrlLayout
from .XbrlImportTaxonomy import XbrlImportTaxonomy, XbrlFinalTaxonomy
from .XbrlLabel import XbrlLabel, XbrlLabelType, preferredLabel
from .XbrlLayout import XbrlLayout, XbrlDataTable, XbrlAxis
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlObject import XbrlReferencableModelObject
from .XbrlProperty import XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlFact import XbrlFact, XbrlFootnote, XbrlFactSource, XbrlTableTemplate
from .XbrlModule import XbrlModule, XbrlModelType, xbrlObjectTypes, referencableObjectTypes, xbrlObjectQNames
from .XbrlUnit import XbrlUnit, parseUnitString
from .XbrlConst import qnXsQName, qnXsDate, qnXsDateTime, qnXsDuration, objectsWithProperties
from .ValidateConceptObjects import validateConceptFamily
from .ValidateCubeTypeObjects import validateCubeTypeFamily
from .ValidateImportObjects import validateImportFamily
from .ValidateNamespaceObjects import validateNamespaceFamily
from .ValidateNetworkObjects import validateNetworkFamily
from arelle.FunctionFn import true
from .ErrorCatalog import emit_error, get_error_catalog
resolveFact = validateFactPosition = None

qnConceptRefDimension = qname(xbrl, "xbrl:concept-refDimension")
qnReferenceCubeName = qname(xbrl, "xbrl:referenceCubeName")

def validateRefDimensions(compMdl, module):
    """Validate xbrl:concept-refDimension relationships carrying an xbrl:referenceCubeName property
       (oim-taxonomy.md §concept-refDimension). When referenceCubeName is present the reference dimension
       MUST exist on that cube (oimte:missingRefDimension); if it exists, every fact value of the source
       concept MUST be a valid foreign key — an explicit-domain member of the reference dimension, or (for a
       typed reference dimension) a value carried on some fact in the reference cube (oimte:missingForeignKey)."""
    from .ValidateCubes import matchFactToCube
    prefixNs = getattr(module, "_prefixNamespaces", None)
    for ntwkObj in module.networks or ():
        if getattr(ntwkObj, "relationshipTypeName", None) != qnConceptRefDimension:
            continue
        for relObj in ntwkObj.relationships or ():
            if relObj.source == qnXbrlRootSource:
                continue
            refCubeVal = next((p.value for p in getattr(relObj, "properties", None) or ()
                               if p.property == qnReferenceCubeName), None)
            if not refCubeVal:
                continue  # referenceCubeName absent → relationship is documentation-only, no validation
            refCubeQn = qname(refCubeVal, prefixNs) if isinstance(refCubeVal, str) else refCubeVal
            refCube = compMdl.namedObjects.get(refCubeQn)
            if not isinstance(refCube, XbrlCube):
                continue
            targetDim = relObj.target
            if targetDim in coreDimensions:
                continue  # core-dimension targets (e.g. xbrl:period) have separate rules
            refCubeDim = next((cd for cd in refCube.cubeDimensions or () if cd.dimension == targetDim), None)
            if refCubeDim is None:
                compMdl.error("oimte:missingRefDimension",
                          _("The concept-refDimension relationship %(src)s→%(tgt)s references cube %(cube)s which does not define the reference dimension %(tgt)s."),
                          xbrlObject=(ntwkObj, relObj), src=relObj.source, tgt=targetDim, cube=refCubeQn)
                continue
            sourceConcept = relObj.source
            srcFactValues = []  # (fact, factValue.value) for facts of the source concept
            for fact in module.facts or ():
                fd = getattr(fact, "factDimensions", None)
                if not fd:
                    continue
                cQn = fd.get(conceptCoreDim)
                if isinstance(cQn, str) and ":" in cQn:
                    cQn = qname(cQn, prefixNs)
                if cQn != sourceConcept:
                    continue
                for fv in getattr(fact, "factValues", None) or ():
                    srcFactValues.append((fact, getattr(fv, "value", None)))
            if bool(refCubeDim.domainDataType):  # typed reference dimension
                refTypedValues = set()
                for fact in module.facts or ():
                    fd = getattr(fact, "factDimensions", None)
                    if fd and targetDim in fd and matchFactToCube(compMdl, fact, refCube):
                        refTypedValues.add(fd.get(targetDim))
                for fact, val in srcFactValues:
                    if val not in refTypedValues:
                        compMdl.error("oimte:missingForeignKey",
                                  _("The concept-refDimension source concept %(src)s fact value %(val)s has no matching fact with dimension %(tgt)s in reference cube %(cube)s."),
                                  xbrlObject=(ntwkObj, relObj, fact), src=sourceConcept, val=val, tgt=targetDim, cube=refCubeQn)
            else:  # explicit reference dimension — value must be a domain member
                validMembers = refCubeDim.allowedMembers(compMdl)
                for fact, val in srcFactValues:
                    valQn = qname(val, prefixNs) if isinstance(val, str) and ":" in val else val
                    if valQn not in validMembers:
                        compMdl.error("oimte:missingForeignKey",
                                  _("The concept-refDimension source concept %(src)s fact value %(val)s is not a member of reference dimension %(tgt)s in cube %(cube)s."),
                                  xbrlObject=(ntwkObj, relObj, fact), src=sourceConcept, val=val, tgt=targetDim, cube=refCubeQn)

def validateFactQualifiers(compMdl, module):
    """Validate factQualifier objects (oim-taxonomy.md §factQualifier object):
       (1) a dimension named in a fact's factQualifier MUST NOT also appear in that fact's factDimensions
           (oimte:invalidFactQualifierDimensionMember); and
       (2) facts whose effective dimensions (factDimensions merged with factQualifier) coincide MUST report
           the same value where at least one participates via a factQualifier (oimte:factInconsistentWithFactQualifier)."""
    byEffKey = defaultdict(list)  # effective-dimension key -> list of (fact, frozenset(values), hasQualifier)
    for fact in module.facts or ():
        factDims = getattr(fact, "factDimensions", None)
        if not factDims:
            continue
        factQual = getattr(fact, "factQualifier", None)
        if factQual:
            overlap = set(factQual) & set(factDims)
            if overlap:
                compMdl.error("oimte:invalidFactQualifierDimensionMember",
                          _("The fact %(name)s defines dimension(s) %(dims)s in both its factDimensions and factQualifier."),
                          xbrlObject=fact, name=getattr(fact, "name", None),
                          dims=", ".join(sorted(str(d) for d in overlap)))
        eff = dict(factDims)
        if factQual:
            eff.update(factQual)
        # internal helper keys (e.g. _periodValue) are derived from real dimensions and identical across
        # facts with the same period, so exclude them to compare on the declared dimensional pairs only
        effKey = frozenset((str(k), str(v)) for k, v in eff.items() if not str(k).startswith("_"))
        vals = frozenset(str(getattr(fv, "value", None)) for fv in getattr(fact, "factValues", None) or ())
        byEffKey[effKey].append((fact, vals, bool(factQual)))
    for effKey, entries in byEffKey.items():
        if len(entries) < 2:
            continue
        if not any(hasQual for _f, _v, hasQual in entries):
            continue  # not a factQualifier consistency case (plain duplicates handled elsewhere)
        allValues = set()
        for _f, vals, _hq in entries:
            allValues |= vals
        if len(allValues) > 1:
            compMdl.error("oimte:factInconsistentWithFactQualifier",
                      _("Facts %(names)s share the same effective dimensions (via factQualifier) but report conflicting values %(values)s."),
                      xbrlObject=[f for f, _v, _hq in entries],
                      names=", ".join(str(getattr(f, "name", None)) for f, _v, _hq in entries),
                      values=", ".join(sorted(allValues)))

perCnstrtFmtStartEndPattern = re.compile(r".*@(start|end)")


def _isBaseCubeType(cubeType, targetLocalName, compMdl):
    """Walk the baseCubeType inheritance chain to check if cubeType or any ancestor has the given localName."""
    ct = cubeType
    seen = set()
    while ct is not None and isinstance(ct, XbrlCubeType) and ct.name not in seen:
        if ct.name.localName == targetLocalName:
            return True
        seen.add(ct.name)
        ct = compMdl.namedObjects.get(ct.baseCubeType) if ct.baseCubeType else None
    return False


def _qname_key(value):
    if isinstance(value, QName):
        return (value.namespaceURI, value.localName)
    return None


def _qname_in_set(value, candidates):
    if value in candidates:
        return True
    value_key = _qname_key(value)
    if value_key is None:
        return False
    return any(_qname_key(candidate) == value_key for candidate in candidates)


def _hashable_value(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _hashable_value(val)) for key, val in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_hashable_value(val) for val in value)
    if isinstance(value, set):
        return frozenset(_hashable_value(val) for val in value)
    return value


def cleanOrphanedForObjects(compMdl):
    """Automatically clean orphaned QName references in labels, references and groupContents using the final
       compiled-model object set (oim-taxonomy.md, model-compilation orphan cleanup). This runs after all
       imports are merged: a `forObject`/`forObjects` entry that does not resolve to an object in the compiled
       model is removed; a label whose `forObject` is unresolved is dropped; and a reference or groupContent
       whose `forObjects` becomes empty after cleanup is dropped. A forObject that resolves to an object of the
       wrong type is NOT orphaned and is left for the type-specific validations to report."""
    def resolves(qn):
        return qn is not None and (qn in compMdl.namedObjects or qn in xbrlObjectTypes or compMdl.isImpliedObject(qn))
    def dropTag(qn, tagObj):
        lst = compMdl.tagObjects.get(qn)
        if lst and tagObj in lst:
            lst.remove(tagObj)
            if not lst:
                del compMdl.tagObjects[qn]
    for module in compMdl.xbrlModels.values():
        # A standalone (entry-point) bundle validates its labels against its referenced model: an
        # unresolved forObject is a genuine error (reported by the label-object validation), so its
        # labels are NOT orphan-cleaned here. Bundle labels bound into a host model via import still go
        # through normal orphan cleanup below (unresolved ones are dropped, not errored).
        if module.labels and not getattr(module, "_isEntryBundle", False):
            keptLabels = OrderedSet()
            for lblObj in module.labels:
                if resolves(lblObj.forObject):
                    keptLabels.add(lblObj)
                else:  # forObject cannot be resolved — drop the label
                    dropTag(lblObj.forObject, lblObj)
            module.labels = keptLabels or None
        # A reference object holds a set of forObjects: unresolved entries are removed and the reference
        # is dropped only if none remain.
        if module.references:
            keptRefs = OrderedSet()
            for refObj in module.references:
                forObjs = getattr(refObj, "forObjects", None)
                if forObjs is not None:
                    for qn in [q for q in forObjs if not resolves(q)]:
                        forObjs.discard(qn)
                        dropTag(qn, refObj)
                    if not forObjs:  # no remaining forObjects after cleanup — drop the object
                        continue
                keptRefs.add(refObj)
            module.references = keptRefs or None
        # A group content object references a single forObject: drop it when the forObject is unresolved
        # (oim-taxonomy §group content object — orphan values are dropped on object resolution).
        if module.groupContents:
            module.groupContents = OrderedSet(
                gc for gc in module.groupContents if resolves(getattr(gc, "forObject", None))) or None


# Each key of a conformance test's RESOLVED:{...} expected-object-count block (declared in the module
# documentInfo.description) names a compiled-module object collection. The collection attribute is the
# key with a lowercased initial (Concepts->concepts, DomainNetworks->domainNetworks, GroupContents->
# groupContents, ...), so no explicit map is needed.
_RESOLVED_COUNT_KEYS = frozenset((
    "Concepts", "Headings", "Members", "Cubes", "Dimensions", "DomainNetworks", "DomainClasses",
    "Networks", "Labels", "References", "PropertyTypes", "ModelTypes", "LabelTypes", "ReferenceTypes",
    "RelationshipTypes", "CubeTypes", "DataTypes", "Units", "Entities", "Groups", "GroupContents",
    "Facts", "Transforms", "FactMaps", "FactSources", "Layouts", "TableTemplates", "CollectionTypes",
    "ImpliedObjects", "Footnotes"))
_RESOLVED_COUNT_RE = re.compile(r"RESOLVED:\s*\{([^}]*)\}")

def _importClosureModules(compMdl, module):
    """Return the module and all of its transitively imported modules (the import sub-tree)."""
    closure = {}
    pending = [module]
    while pending:
        mod = pending.pop()
        if id(mod) in closure:
            continue
        closure[id(mod)] = mod
        for impTx in getattr(mod, "importedTaxonomies", None) or ():
            impMod = getattr(impTx, "_txmyModule", None) or compMdl.xbrlModels.get(getattr(impTx, "xbrlModelName", None))
            if impMod is not None:
                pending.append(impMod)
    return list(closure.values())

def checkExpectedObjectCounts(compMdl):
    """If a module's documentInfo.description declares a RESOLVED:{Key:count,...} block of expected
    object counts, compare it against the objects remaining (after pruning) in the compilation of that
    module's import sub-tree — the module itself plus its transitively imported taxonomies — and emit a
    (non-fatal) warning listing any per-type mismatch. This surfaces stale or incorrect expected-count
    metadata in the conformance tests without affecting the pass/fail error codes.
    """
    for module in compMdl.xbrlModels.values():
        description = getattr(module, "_description", None) or ""
        m = _RESOLVED_COUNT_RE.search(description)
        if not m:
            continue
        expected = {}
        for pair in m.group(1).split(","):
            key, _sep, val = pair.partition(":")
            key, val = key.strip(), val.strip()
            if key and val.lstrip("-").isdigit():
                expected[key] = int(val)
        closureModules = _importClosureModules(compMdl, module)
        mismatches = []
        for key, expCt in expected.items():
            if key not in _RESOLVED_COUNT_KEYS:
                continue # unknown key in the RESOLVED block — ignore rather than mis-report
            collAttr = key[0].lower() + key[1:]
            actCt = sum(len(getattr(mod, collAttr, None) or ()) for mod in closureModules)
            if actCt != expCt:
                mismatches.append((key, expCt, actCt))
        if mismatches:
            compMdl.warning("arelle:expectedObjectCountMismatch",
                        _("Compiled object counts differ from the RESOLVED expectation in %(module)s: %(mismatches)s."),
                        xbrlObject=module, module=module.name,
                        mismatches="; ".join(f"{k} expected {e} got {a}" for k, e, a in mismatches))

def checkConsistentTaxonomyURLs(compMdl):
    """oim-taxonomy §import: the importMapping objects of all modules comprising a model MUST map each
    xbrlModelName to the same URL (oimte:inconsistentTaxonomyURL). Collect every module's resolved
    importMapping and report any xbrlModelName mapped to more than one URL across the modules.
    """
    urlsByModelName = defaultdict(dict) # xbrlModelName -> {url: firstModule}
    for module in compMdl.xbrlModels.values():
        for modelName, url in (getattr(module, "_importMapping", None) or {}).items():
            urlsByModelName[modelName].setdefault(url, module)
    for modelName, urlModules in urlsByModelName.items():
        if len(urlModules) > 1:
            compMdl.error("oimte:inconsistentTaxonomyURL",
                      _("The importMapping for %(modelName)s maps to inconsistent URLs across modules: %(urls)s."),
                      xbrlObject=list(urlModules.values()), modelName=modelName,
                      urls=", ".join(sorted(urlModules)))

def validateBundleModules(compMdl):
    """Validate the bundle-module constraints (oim-taxonomy §46, §239, §1005-1006): a bundle module
    (documentType https://xbrl.org/2026/bundle) MUST define only label objects and MUST define a
    referenceModel property naming the model whose objects its labels annotate."""
    for module in compMdl.xbrlModels.values():
        if not getattr(module, "_isBundle", False):
            continue
        # A bundle may define only label objects; any other populated top-level object collection
        # (concepts, cubes, references, …) is disallowed.
        for key in _RESOLVED_COUNT_KEYS:
            if key == "Labels":
                continue
            collAttr = key[0].lower() + key[1:]
            if getattr(module, collAttr, None):
                compMdl.error("oimte:invalidBundleModuleContent",
                          _("The bundle module %(name)s MUST contain only label objects, but also defines a %(objectType)s array."),
                          xbrlObject=module, name=module.name, objectType=key)
        if getattr(module, "referenceModel", None) is None:
            compMdl.error("oimte:missingBundleModuleReferenceModel",
                      _("The bundle module %(name)s MUST define a referenceModel property."),
                      xbrlObject=module, name=module.name)

def validateCompiledModel(compMdl):
    """Validate the compiled model as a whole, after all modules have been validated and combined into the compiled model.
        This is for checks that require the whole model to be available, such as checking for duplicate labels across modules.
    """

    compMdl.errorCatalog = get_error_catalog()

    checkConsistentTaxonomyURLs(compMdl)

    validateBundleModules(compMdl)

    # Automatic orphan cleanup MUST run over the final merged object set before validation so that
    # orphaned label/reference/groupContent forObjects are not reported as invalid QName references.
    cleanOrphanedForObjects(compMdl)

    # Object-count check runs after orphan cleanup so the counts reflect the final compiled model
    # (e.g. bundle/imported labels dropped when their forObject is unresolved).
    checkExpectedObjectCounts(compMdl)

    mdlLvlChecks = attrdict(
        labelsCt = defaultdict(list), # count of duplicated labels by forObject, labelType and language
    )

    for module in compMdl.xbrlModels.values():
        validateXbrlModule(compMdl, module, mdlLvlChecks)

    validateCompletedModel(compMdl)

    # model lavel checks
    for lblKey, lblObjs in mdlLvlChecks.labelsCt.items():
        if len(lblObjs) > 1:
            emit_error(compMdl, "oimte:duplicateLabelObject",
                       _("The labels are duplicated for forObject %(name)s type %(type)s language %(language)s"),
                       xbrlObject=lblObjs, name=lblKey[0], type=lblKey[1], language=lblKey[2])

def objType(obj):
    clsName = type(obj).__name__
    if clsName.startswith("Xbrl"):
        return clsName[4:]
    return clsName

def assertObjectType(compMdl, obj, objType):
    if not isinstance(obj, objType):
        emit_error(compMdl, "oimte:invalidObjectType",
                   _("This %(thisType)s object was included where an %(expectedType)s object was expected."),
                   xbrlObject=obj, thisType=obj.__class__.__name__, expectedType=objType.__name__)

def _expectedTypeName(objType):
    if isinstance(objType, tuple):
        return " or ".join(getattr(tp, "__name__", str(tp)) for tp in objType)
    return getattr(objType, "__name__", str(objType))

_LEI_NAMESPACE = "http://standards.iso.org/iso/17442"

def _validateImpliedObjectLocalName(compMdl, contextObj, qnRef):
    """Validate the local name of an implied object QName (e.g. LEI checksum)."""
    if qnRef.namespaceURI == _LEI_NAMESPACE:
        from arelle.LeiUtil import checkLei, LEI_VALID
        result = checkLei(qnRef.localName)
        if result is not LEI_VALID:
            compMdl.error("oimte:invalidLEILocalName",
                          _("LEI local name %(lei)s is not a valid LEI identifier (%(reason)s)."),
                          xbrlObject=contextObj, lei=qnRef.localName, reason=result.description())


def validateQNameReference(compMdl, contextObj, propName, objType=None, msgCode=None,
                           undefinedMsgCode=None, invalidTypeMsgCode=None,
                           undefinedMessage=None, invalidTypeMessage=None,
                           errorArgs=None, qnDefault=None, qnRef=None, isOptional=False):
    """Validate a QName reference and return resolved object or raise error.

    Args:
        compMdl: compiled model
        contextObj: object containing the reference (for error context)
        propName: property name where reference appears (for error message)
        objType: expected type of resolved object (XbrlConcept, XbrlDimension, etc.)
        msgCode: optional shared message code for undefined and wrong-type errors
        undefinedMsgCode: optional message code when the QName does not resolve
        invalidTypeMsgCode: optional message code when the QName resolves to the wrong object type
        undefinedMessage: optional message text when the QName does not resolve
        invalidTypeMessage: optional message text when the QName resolves to the wrong object type
        errorArgs: optional dict of additional message arguments

    Returns:
        Resolved object if valid and correct type, None if error raised
    """
    if qnRef is None:
        qnRef = getattr(contextObj, propName, None)
        if qnRef is None and isOptional:
            return None # absent optional property is valid
    if not qnRef and qnDefault:
        qnRef = qnDefault
    if not qnRef:
        emit_error(compMdl, "oimte:invalidJSONStructureMissingRequiredProperty",
                   _("%(objType)s %(name)s is missing required QName reference property '%(prop)s'"),
                   xbrlObject=contextObj, objType=contextObj.__class__.__name__, name=getattr(contextObj, 'name', '?'),
                   prop=propName)
        return None

    messageArgs = {
        "xbrlObject": contextObj,
        "parentType": type(contextObj).__name__,
        "parentName": getattr(contextObj, 'name', ''),
        "propName": propName,
        "qnRef": qnRef,
    }
    if errorArgs:
        messageArgs.update(errorArgs)

    # Resolve QName to object
    resolvedObj = compMdl.namedObjects.get(qnRef)

    if not resolvedObj:
        if compMdl.isImpliedObject(qnRef):
            _validateImpliedObjectLocalName(compMdl, contextObj, qnRef)
            return None  # implied objects are valid but not in namedObjects
        emit_error(compMdl, undefinedMsgCode or msgCode or "oimte:invalidQNameReference",
                   undefinedMessage or _("%(parentType)s %(parentName)s property %(propName)s references undefined QName '%(qnRef)s'"),
                   **messageArgs)
        return None

    # Check resolved object is correct type
    if objType is not None and not isinstance(resolvedObj, objType):
        messageArgs.update({
            "actualType": type(resolvedObj).__name__,
            "expectedType": _expectedTypeName(objType),
        })
        emit_error(compMdl, invalidTypeMsgCode or msgCode or "oimte:invalidQNameReference",
                   invalidTypeMessage or _("%(parentType)s %(parentName)s property %(propName)s references '%(qnRef)s' which is %(actualType)s, expected %(expectedType)s"),
                   **messageArgs)
        return None

    return resolvedObj

def validateValue(compMdl, module, obj, value, dataTypeQn, pathElt, msgCode):
    """Validate a value against a data type, including facets. Return (xValid, xValue) where xValid is VALID, INVALID or NONE and xValue is the converted value if valid or None if invalid.
        Args:
            compMdl: compiled model
            module: the module containing the object
            obj: the object being validated
            value: the value to validate
            dataTypeQn: the data type QName, or collectionType QName
            pathElt: the path element for error messages
            msgCode: the message code for error messages
        Returns:
            A tuple of (xValid, xValue)
    """
    if isinstance(dataTypeQn, QName):
        dataTypeObj = compMdl.namedObjects.get(dataTypeQn)
        if isinstance(dataTypeObj, XbrlCollectionType):
            if not isinstance(value, list):
                emit_error(compMdl, msgCode,
                    _("Collection value is not a collection %(value)s for collectionType %(collectionType)s."),
                    xbrlObject=obj, value=value, collectionType=dataTypeObj.name,)
                return (INVALID, None)

            minItems = getattr(dataTypeObj, "minItems", None)
            maxItems = getattr(dataTypeObj, "maxItems", None)
            itemCount = len(value)
            if ((minItems is not None and itemCount < minItems) or
                (maxItems is not None and itemCount > maxItems)):
                emit_error(compMdl, "oimte:invalidNumberOfItemsInCollection",
                           _("Value has %(itemCount)s item(s) but collectionType %(collectionType)s allows minItems %(minItems)s and maxItems %(maxItems)s."),
                           xbrlObject=obj, collectionType=dataTypeObj.name,
                           itemCount=itemCount, minItems=minItems, maxItems=maxItems)
                return (INVALID, None)

            if getattr(dataTypeObj, "uniqueValues", True):
                uniqueValues = set()
                hasDuplicate = False
                for item in value:
                    key = item if isinstance(item, (str, int, float, bool, Decimal, type(None), QName)) else repr(item)
                    if key in uniqueValues:
                        hasDuplicate = True
                        break
                    uniqueValues.add(key)
                if hasDuplicate:
                    emit_error(compMdl, "oimte:duplicateItemsInCollection",
                               _("CollectionType %(collectionType)s requires unique values but duplicate items were found."),
                               xbrlObject=obj, collectionType=dataTypeObj.name)
                    return (INVALID, None)

            validatedItems = []
            for i, item in enumerate(value):
                itemValid, itemXValue = validateValue(compMdl, module, obj, item, dataTypeObj.dataType, f"{pathElt}[{i}]", msgCode)
                if itemValid != VALID:
                    return (INVALID, None)
                validatedItems.append(itemXValue)
            return (VALID, validatedItems)

        if not isinstance(dataTypeObj, XbrlDataType): # validity checked in owner object validations
            return (NONE, None)
        dataTypeLn = dataTypeObj.xsBaseType(compMdl)
        facets = dataTypeObj.xsFacets()
    elif isinstance(dataTypeQn, XbrlDataType):
        dataTypeLn = dataTypeQn.xsBaseType(compMdl)
        facets = dataTypeQn.xsFacets()
    else: # string data type
        dataTypeLn = dataTypeQn
        facets = EMPTY_DICT
    prototypeElt = attrdict(elementQname=dataTypeQn,
                            entryLoadingUrl=obj.entryLoadingUrl + pathElt,
                            nsmap=module._prefixNamespaces)
    if dataTypeLn == "boolean":
        if isinstance(value, bool) and not facets:
            return (VALID, value) # no conversion or facets test
        else:
            value = str(value).lower() # convert True to true
    elif isinstance(value, (int, float, Decimal)):
        if isNumericXsdType(dataTypeLn):
            if not facets:
                return (VALID, value) # no conversion or facets test
        else:
            modelXbrl.error(msgCode,
                _("Element %(element)s type %(typeName)s value error: %(value)s, %(error)s"),
                modelObject=prototypeElt,
                element=errElt,
                typeName=baseXsdType,
                value=value,
                error="numeric value for non-numeric data type")
    elif isinstance(value, list) and dataTypeLn == "string" and all(isinstance(e, str) for e in value):
        # specially allowed list type
        return (VALID, value)
    if not isinstance(value, str):
        value = str(value) # xml validation is only applicable to string source
    validateXmlValue(compMdl, prototypeElt, None, dataTypeLn, value, False, False, facets, msgCode)
    return (prototypeElt.xValid, prototypeElt.xValue)

def reqRelMatch(relQn, reqQn, compMdl):
    """Check if a relationship QName matches a required relationship QName, either by direct match or by matching the required relationship's data type.
        Args:
            relQn: the relationship QName
            reqQn: the required relationship QName
            compMdl: the compiled model
        Returns:
            True if the relationship matches the required relationship, False otherwise
    """
    if relQn == reqQn:
        return True
    concept = compMdl.namedObjects.get(relQn)
    if isinstance(concept, XbrlConcept):
        if concept.dataType == reqQn:
            return True
    return False

def validateProperties(compMdl, oimFile, module, obj):
    """Validate the properties of an object, including checking that property types are valid and allowed for the object,
        and that property values are valid for their property type. Also check for conflicting property values for the
        same property type.

        Args:
            compMdl: the compiled model
            oimFile: the OIM file
            module: the module containing the object
            obj: the object being validated
        Returns:
            None
    """
    propTypeQns = defaultdict(set)
    for i, propObj in enumerate(getattr(obj, "properties", None) or ()):
        propTypeQn = propObj.property
        propTypeObj = compMdl.namedObjects.get(propTypeQn)
        if not isinstance(propTypeObj, XbrlPropertyType):
            # identify parent object
            if hasattr(obj, "name"):
                parentName = obj.name
            elif hasattr(obj, "source") and hasattr(obj, "target"): # relationship
                parentName = f"{obj.source}\u2192{obj.target}"
            else:
                parentName = ""
            if propTypeObj is None:
                compMdl.error("oimte:invalidQNameReference",
                          _("%(parentObjName)s %(parentName)s property %(name)s has undefined propertyType %(propertyType)s"),
                          file=oimFile, parentObjName=objType(obj), parentName=parentName,
                          name=propTypeQn, propertyType=propTypeQn)
            else:
                compMdl.error("oimte:invalidObjectType",
                          _("%(parentObjName)s %(parentName)s property %(name)s has invalid property type object %(propertyType)s"),
                          file=oimFile, parentObjName=objType(obj), parentName=parentName,
                          name=propTypeQn, propertyType=propTypeQn)
        else: # have property type object
            if propTypeObj.allowedObjects:
                if not _qname_in_set(xbrlObjectQNames.get(type(obj)), propTypeObj.allowedObjects):
                    compMdl.error("oimte:disallowedObjectProperty",
                              _("%(parentObjName)s %(parentName)s property %(name)s not an allowed property type for the object."),
                              file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                              name=propTypeQn)
            propObj._xValid, propObj._xValue = validateValue(compMdl, module, obj, propObj.value, propTypeObj.dataType, f"/properties[{i}]", "oimte:propertyValueDataTypeMismatch")

            propTypeQns[propTypeQn].add(_hashable_value(propObj._xValue))
    if any(len(vals) > 1 for qn, vals in propTypeQns.items()):
        compMdl.error("oimte:conflictingPropertyValues",
                  _("%(parentObjName)s %(parentName)s has conflicting values for properties %(names)s"),
                  file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                  names=", ".join(str(qn) for qn, vals in propTypeQns.items() if len(vals) > 1))


def validateXbrlModule(compMdl, module, mdlLvlChecks):
    """Validate an XBRL module within an assembled compiled model, including validating all objects within the module and
        checking for consistency with the module's modelType.

        Args:
            compMdl: the compiled model
            module: the module to validate
            mdlLvlChecks: level of checks to perform
        Returns:
            None
    """
    oimFile = str(module.name)

    familyKwargs = dict(
        assertObjectType=assertObjectType,
        validateQNameReference=validateQNameReference,
        validateProperties=validateProperties,
    )

    validateNamespaceFamily(compMdl, module, oimFile, **familyKwargs)

    validateImportFamily(compMdl, module, oimFile, **familyKwargs)

    validateConceptFamily(
        compMdl,
        module,
        oimFile,
        assertObjectType=assertObjectType,
        validateQNameReference=validateQNameReference,
        validateProperties=validateProperties,
    )

    validateCubeTypeFamily(compMdl, module, oimFile, **familyKwargs)

    # Cube Objects
    for cubeObj in module.cubes or ():
        assertObjectType(compMdl, cubeObj, XbrlCube)
        name = cubeObj.name
        cubeType = validateQNameReference(compMdl, cubeObj, "cubeType", XbrlCubeType,
                                         invalidTypeMsgCode="oimte:invalidObjectType",
                                         qnRef=(cubeObj.cubeType or reportCubeType))
        if cubeType is None:
            continue # can't do further checks without cube type
        isTimeSeriesCubeType = cubeType and _isBaseCubeType(cubeType, "timeSeriesCube", compMdl)
        isNegativeCubeType = cubeType and cubeType.name.localName == "negativeCube"
        isReferenceCubeType = cubeType and _isBaseCubeType(cubeType, "referenceCube", compMdl)

        if cubeObj.extends:
            extendCubeObj = validateQNameReference(compMdl, cubeObj, "extends", XbrlCube,
                                                   invalidTypeMsgCode="oimte:invalidObjectType")
            if isinstance(extendCubeObj, XbrlCube) and not extendCubeObj.isExtensible:
                compMdl.error("oimte:illegalExtensionOfNonExtensibleObject",
                              _("The cube %(name)s cannot be extended because it is non-extensible."),
                              xbrlObject=cubeObj, name=extendCubeObj.name)

        ntwks = set()
        for ntwrkQn in compMdl.effectiveCubeNetworks(cubeObj):
            ntwk = compMdl.namedObjects.get(ntwrkQn)
            if ntwk is None:
                compMdl.error("oimte:invalidQNameReference",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s an object in the model."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            elif not isinstance(ntwk, XbrlNetwork):
                compMdl.error("oimte:invalidObjectType",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s to a network object."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            else:
                 ntwks.add(ntwk)

        cubeNtwkConstrObj = cubeType.effectivePropVal(compMdl, "cubeNetworkConstraints")
        cubeNtwkConstrs = cubeType.effectivePropVal(compMdl, "cubeNetworkConstraints", "cubeNetworks")
        if cubeNtwkConstrs:
            relConstraintNetworkPresent = defaultdict(int)  # networks present by relationshipType (missing vs. wrong)
            relConstraintNetworkMatches = defaultdict(int)  # networks whose endpoints satisfy the constraint
            maxZeroViolatedConstrs = set()
            for ntwk in ntwks:
                matchingConstrs = [c for c in cubeNtwkConstrs if c.relationshipType == ntwk.relationshipTypeName]
                for cnst in matchingConstrs:
                    relConstraintNetworkPresent[cnst] += 1
                ntwkMatchedConstraints = set()
                for relObj in ntwk.relationships or ():
                    if relObj.source == qnXbrlRootSource:
                        continue  # rootSource is a virtual origin, not subject to constraints
                    if not matchingConstrs:
                        if getattr(cubeNtwkConstrObj, "closed", False):
                            compMdl.error("oimte:invalidCubeNetworkRelationship",
                                          _("Cube %(name)s has network %(network)s with relationship type %(relationshipType)s which is not allowed by cubeNetworkConstraints."),
                                          xbrlObject=(cubeObj, ntwk, relObj), name=name, network=ntwk.name, relationshipType=ntwk.relationshipTypeName)
                        continue
                    relSObj = compMdl.namedObjects.get(relObj.source)
                    relTObj = compMdl.namedObjects.get(relObj.target)
                    # Check for maxNetworks==0 violations (forbidden endpoint combinations)
                    for cnst in matchingConstrs:
                        if cnst.maxNetworks != 0:
                            continue
                        srcOk = True
                        tgtOk = True
                        if cnst.source is not None:
                            if cnst.source.qname and relObj.source != cnst.source.qname:
                                srcOk = False
                            if srcOk and cnst.source.objectType:
                                expectedSrcType = xbrlObjectTypes.get(cnst.source.objectType)
                                if expectedSrcType is not None and not isinstance(relSObj, expectedSrcType):
                                    srcOk = False
                            if srcOk and cnst.source.dataType:
                                if getattr(relSObj, "dataType", None) != cnst.source.dataType:
                                    srcOk = False
                        if cnst.target is not None:
                            if cnst.target.qname and relObj.target != cnst.target.qname:
                                tgtOk = False
                            if tgtOk and cnst.target.objectType:
                                expectedTgtType = xbrlObjectTypes.get(cnst.target.objectType)
                                if expectedTgtType is not None and not isinstance(relTObj, expectedTgtType):
                                    tgtOk = False
                            if tgtOk and cnst.target.dataType:
                                if getattr(relTObj, "dataType", None) != cnst.target.dataType:
                                    tgtOk = False
                        if srcOk and tgtOk and cnst not in maxZeroViolatedConstrs:
                            compMdl.error("oimte:invalidCubeRelationship",
                                          _("Cube %(name)s network %(network)s has relationship %(source)s -> %(target)s forbidden by cubeType maxNetworks=0 constraint."),
                                          xbrlObject=(cubeObj, ntwk, relObj), name=name, network=ntwk.name, source=relObj.source, target=relObj.target)
                            maxZeroViolatedConstrs.add(cnst)
                    if all(cnst.maxNetworks == 0 for cnst in matchingConstrs):
                        continue
                    relMatched = False
                    for cnst in matchingConstrs:
                        if cnst.maxNetworks == 0:
                            continue
                        srcOk = True
                        tgtOk = True
                        if cnst.source is not None:
                            if cnst.source.qname and relObj.source != cnst.source.qname:
                                srcOk = False
                            if srcOk and cnst.source.objectType:
                                expectedSrcType = xbrlObjectTypes.get(cnst.source.objectType)
                                if expectedSrcType is not None and not isinstance(relSObj, expectedSrcType):
                                    srcOk = False
                            if srcOk and cnst.source.dataType:
                                if getattr(relSObj, "dataType", None) != cnst.source.dataType:
                                    srcOk = False
                        if cnst.target is not None:
                            if cnst.target.qname and relObj.target != cnst.target.qname:
                                tgtOk = False
                            if tgtOk and cnst.target.objectType:
                                expectedTgtType = xbrlObjectTypes.get(cnst.target.objectType)
                                if expectedTgtType is not None and not isinstance(relTObj, expectedTgtType):
                                    tgtOk = False
                            if tgtOk and cnst.target.dataType:
                                if getattr(relTObj, "dataType", None) != cnst.target.dataType:
                                    tgtOk = False
                        if srcOk and tgtOk:
                            relMatched = True
                            ntwkMatchedConstraints.add(cnst)
                            break
                    if not relMatched:
                        compMdl.error("oimte:invalidCubeNetworkRelationship",
                                      _("Cube %(name)s network %(network)s relationship %(source)s -> %(target)s violates cubeNetworkConstraints."),
                                      xbrlObject=(cubeObj, ntwk, relObj), name=name, network=ntwk.name, source=relObj.source, target=relObj.target)

                for cnst in ntwkMatchedConstraints:
                    relConstraintNetworkMatches[cnst] += 1

            for cnst in cubeNtwkConstrs:
                if cnst.maxNetworks == 0:
                    continue
                # A constraint requires minNetworks networks of its relationshipType whose endpoints satisfy it.
                matchedNtws = relConstraintNetworkMatches.get(cnst, 0)
                if cnst.minNetworks is not None and matchedNtws < cnst.minNetworks:
                    # Distinguish *missing* (no network of this relationshipType is present at all) from a
                    # network that is present but whose endpoints don't satisfy this constraint. The former is
                    # a missing required relationship; the latter is an invalid cube-network relationship (e.g.
                    # a second same-relationshipType constraint with different source/target that no network meets).
                    if relConstraintNetworkPresent.get(cnst, 0) == 0:
                        errCode = "oimte:missingRequiredRelationship"
                    else:
                        errCode = "oimte:invalidCubeNetworkRelationship"
                    compMdl.error(errCode,
                                  _("Cube %(name)s has %(matchedNtws)s networks for relationshipType %(relationshipType)s but cubeType requires minNetworks %(minNetworks)s."),
                                  xbrlObject=cubeObj, name=name, relationshipType=cnst.relationshipType,
                                  matchedNtws=matchedNtws, minNetworks=cnst.minNetworks)

        dimQnCounts = {}
        for cubeDimObj in cubeObj.cubeDimensions or ():
            dimQn = cubeDimObj.dimension
            dimObj = validateQNameReference(compMdl, cubeDimObj, "dimension", XbrlDimension,
                                            invalidTypeMsgCode="oimte:invalidObjectType")
            if dimObj:
                # specific cubeType dimension property validations
                tsProps = {timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, excludedIntervalsPropType, completeTimeSeriesPropType} & set(p.property for p in (dimObj.properties or EMPTY_FROZENSET))
                if tsProps:
                    if cubeType and not isTimeSeriesCubeType:
                        compMdl.error("oimte:invalidTaxonomyDefinedDimension" if timeSeriesPropType in tsProps else
                                      "oimte:intervalConventionOnNonTimeSeriesDimension" if intervalConventionPropType in tsProps else
                                      "oimte:intervalOfMeasurementOnNonTimeSeriesDimension" if intervalOfMeasurementPropType in tsProps else
                                      "oimte:completeTimeSeriesOnNonTimeSeriesDimension" if completeTimeSeriesPropType in tsProps else
                                      "oimte:intervalOfMeasurementOnNonTimeSeriesDimension",
                                  _("The dimension %(dimension)s properties %(tsProps)s on cube %(name)s type %(cubeType)s MUST only be used on a timeSeries cubeType."),
                                  xbrlObject=cubeObj, name=name, dimension=dimQn, cubeType=cubeType.name, tsProps=", ".join(sorted(str(p) for p in tsProps)))
                    elif cubeDimObj.domainDataType:
                        dimDomDTQn = cubeDimObj.domainDataType
                        domDTobj = compMdl.namedObjects.get(dimDomDTQn)
                        if not (isinstance(compMdl.namedObjects.get(dimDomDTQn), XbrlDataType) or
                                domDTobj.instanceOfType(qnXsDateTime, compMdl)):
                            compMdl.error("oimte:invalidTaxonomyDefinedDimension" if timeSeriesPropType in tsProps else
                                      "oimte:intervalConventionOnNonTimeSeriesDimension" if intervalConventionPropType in tsProps else
                                      "oimte:intervalOfMeasurementOnNonTimeSeriesDimension" if intervalOfMeasurementPropType in tsProps else
                                      "oimte:completeTimeSeriesOnNonTimeSeriesDimension" if completeTimeSeriesPropType in tsProps else
                                      "oimte:intervalOfMeasurementOnNonTimeSeriesDimension",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s properties %(tsProps)s on cube %(name)s MUST only be used on a date-time typed dimension."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn, tsProps=", ".join(sorted(str(p) for p in tsProps)))
                        if len(tsProps & {intervalOfMeasurementPropType, intervalConventionPropType}) == 1:
                            compMdl.error("oimte:missingDependentPropertyType",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s on cube %(name)s MUST also have property %(tsProp)s."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn,
                                      tsProp=next(iter({intervalOfMeasurementPropType, intervalConventionPropType} - tsProps)))
                        if dimObj.propertyObjectValue(timeSeriesPropType) == "Aggregated" and dimObj.propertyObjectValue(aggregationPropType) is None:
                            compMdl.error("oimte:missingDependentPropertyType",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s on cube %(name)s with xbrla:timeSeriesType Aggregated MUST also have xbrl:aggregation."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn)
                        if intervalConventionPropType in tsProps and dimObj.propertyObjectValue(intervalOfMeasurementPropType) is None:
                            compMdl.error("oimte:missingDependentPropertyType",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s on cube %(name)s with xbrla:intervalConvention MUST also have xbrla:intervalOfMeasurement."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn)
                        if dimObj.propertyObjectValue(completeTimeSeriesPropType) is True and dimObj.propertyObjectValue(intervalOfMeasurementPropType) is None:
                            compMdl.error("oimte:missingDependentPropertyType",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s on cube %(name)s with xbrl:completeTimeSeries true MUST also have xbrla:intervalOfMeasurement."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn)
                
                # Validate dependent properties on domain class (for time-series typed dimensions)
                domClass = compMdl.namedObjects.get(dimObj.domainClass)
                if isTimeSeriesCubeType and isinstance(domClass, XbrlDomainClass) and domClass.allowedDomainItem:
                    isDateTimeType = domClass.allowedDomainItem == qnXsDateTime or cubeDimObj.domainDataType == qnXsDateTime
                    if isDateTimeType:
                        # Get all domain class property QNames for existence checks
                        allDomClassPropQns = set(p.property for p in getattr(domClass, 'properties', None) or ())
                        domClassTsProps = {timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, completeTimeSeriesPropType} & allDomClassPropQns
                        if domClassTsProps:
                            # Use raw property value lookup for value-dependent checks
                            domClassPropVals = {p.property: p.value for p in getattr(domClass, 'properties', None) or ()}
                            tsTypeVal = domClassPropVals.get(timeSeriesPropType)
                            ctsVal = domClassPropVals.get(completeTimeSeriesPropType)
                            hasIom = intervalOfMeasurementPropType in allDomClassPropQns
                            hasAgg = aggregationPropType in allDomClassPropQns

                            # Rule 1: timeSeriesType="Aggregated" requires xbrl:aggregation
                            if tsTypeVal == "Aggregated" and not hasAgg:
                                compMdl.error("oimte:missingDependentPropertyType",
                                          _("Domain class %(domainClass)s with xbrla:timeSeriesType Aggregated on cube %(name)s dimension %(dimension)s MUST also have xbrl:aggregation."),
                                          xbrlObject=(cubeObj, domClass), name=name, domainClass=domClass.name, dimension=dimQn)

                            # Rule 2: intervalConvention requires intervalOfMeasurement
                            if intervalConventionPropType in domClassTsProps and not hasIom:
                                compMdl.error("oimte:missingDependentPropertyType",
                                          _("Domain class %(domainClass)s with xbrla:intervalConvention on cube %(name)s dimension %(dimension)s MUST also have xbrla:intervalOfMeasurement."),
                                          xbrlObject=(cubeObj, domClass), name=name, domainClass=domClass.name, dimension=dimQn)

                            # Rule 3: completeTimeSeries=true requires intervalOfMeasurement
                            if ctsVal is True and not hasIom:
                                compMdl.error("oimte:missingDependentPropertyType",
                                          _("Domain class %(domainClass)s with xbrl:completeTimeSeries true on cube %(name)s dimension %(dimension)s MUST also have xbrla:intervalOfMeasurement."),
                                          xbrlObject=(cubeObj, domClass), name=name, domainClass=domClass.name, dimension=dimQn)
            dimQnCounts[dimQn] = dimQnCounts.get(dimQn, 0) + 1
        if any(c > 1 for c in dimQnCounts.values()):
            compMdl.error("oimte:duplicateDimensionsInCube",
                      _("The cubeDimensions of cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      xbrlObject=cubeObj, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items() if ct > 1))
        # check cube dims against cube type; extension cubes inherit concept dim from target
        if (cubeObj.cubeDimensions  # empty cubeDimensions already reported as invalidEmptySet at load
                and cubeType.basemostCubeType(compMdl) != defaultCubeType
                and conceptCoreDim not in dimQnCounts.keys()
                and not getattr(cubeObj, 'extends', None)):
            compMdl.error("oimte:cubeMissingConceptDimension",
                        _("The cubeDimensions of cube %(name)s, type %(cubeType)s, must have a concept core dimension"),
                        xbrlObject=cubeObj, name=name, cubeType=cubeType.name)
        cubeCoreDims = cubeType.effectivePropVal(compMdl, "coreDimensions")
        # Per spec: if coreDimensions is not specified (empty), all core dimensions are allowed.
        for prop, coreDim in (("periodDimension", periodCoreDim),
                                ("entityDimension", entityCoreDim),
                                ("unitDimension", unitCoreDim)):
            if coreDim in dimQnCounts.keys() and cubeCoreDims and coreDim not in cubeCoreDims:
                compMdl.error("oimte:invalidCubeCoreDimension",
                            _("The cube %(name)s, type %(cubeType)s, dimension %(dimension)s is not allowed"),
                            xbrlObject=cubeObj, name=name, cubeType=cubeType.name, dimension=coreDim)
        allowedCubeDimConstrs = cubeType.effectivePropVal(compMdl, "cubeDimensionConstraints", "allowed")
        cubeDimsClosed = cubeType.effectivePropVal(compMdl, "cubeDimensionConstraints", "closed")
        # Invalid test cases may carry unresolved dimension names (None); skip them here and let QName-reference checks report errors.
        txmyDefDimsQNs = set(dim for dim in dimQnCounts.keys() if isinstance(dim, QName) and dim.namespaceURI != xbrl)
        if cubeDimsClosed and not allowedCubeDimConstrs:
            if txmyDefDimsQNs:
                compMdl.error("oimte:cubeDimensionNotAllowed",
                            _("The cube %(name)s, type %(cubeType)s, taxonomy defined dimensions %(dimension)s are not allowed"),
                            xbrlObject=cubeObj, name=name, cubeType=cubeType.name, dimension=", ".join(sorted(sorted(str(d) for d in txmyDefDimsQNs))))
        elif allowedCubeDimConstrs is not None: # absent allows any dimensions
            txmyDefDims = set()
            for dimQn in txmyDefDimsQNs:
                dim = compMdl.namedObjects.get(dimQn)
                if isinstance(dim, XbrlDimension):
                    txmyDefDims.add(dim)
            matchedDimQNs = set()
            for allwdDimConstr in allowedCubeDimConstrs:
                matchedDim = None
                if allwdDimConstr is None:
                    continue
                for dim in txmyDefDims:
                    if getattr(allwdDimConstr, "dimensionName", None) and dim.name != allwdDimConstr.dimensionName:
                        continue
                    # Spec: a taxonomy defined dimension must match the dimension, or (type and datatype)
                    # of an allowed constraint. When the constraint fixes an explicit/typed kind, an
                    # explicit dimension (domainClass whose allowedDomainItem is not a datatype) must not
                    # match a "typed" constraint, and vice versa.
                    if getattr(allwdDimConstr, "type", None):
                        dimDomClass = compMdl.namedObjects.get(dim.domainClass)
                        dimIsTyped = (isinstance(dimDomClass, XbrlDomainClass) and dimDomClass.allowedDomainItem and
                                      isinstance(compMdl.namedObjects.get(dimDomClass.allowedDomainItem), XbrlDataType))
                        if (allwdDimConstr.type == "typed") != bool(dimIsTyped):
                            continue
                    matchedDim = dim
                    matchedDimQNs.add(dim.name)
                    break
                if not matchedDim and getattr(allwdDimConstr, "required", False):
                    compMdl.error("oimte:requiredCubeDimensionalSpaceMissingFromCube",
                                _("The cube %(name)s, type %(cubeType)s, taxonomy defined dimensions %(dimension)s is missing"),
                                xbrlObject=cubeObj, name=name, cubeType=cubeType.name,
                                dimension=', '.join(str(getattr(allwdDimConstr, p)) for p in ("dimensionName", "dimensionType", "dimensionDataType") if getattr(allwdDimConstr, p, None)))
            disallowedDims = txmyDefDimsQNs - matchedDimQNs
            if cubeDimsClosed and disallowedDims and not isTimeSeriesCubeType:
                compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                            _("The cube %(name)s, type %(cubeType)s allowedDimensions do not allow dimension(s) %(dimension)s"),
                            xbrlObject=cubeObj, name=name, cubeType=cubeType.name, dimension=", ".join(sorted(str(d) for d in disallowedDims)))
        for reqRel in cubeType.effectivePropVal(compMdl, "requiredCubeRelationships"):
            reqRelSatisfied = False
            for ntwk in ntwks:
                if (ntwk.relationshipTypeName == reqRel.relationshipTypeName and
                    any(((not reqRel.source or reqRelMatch(r.source, reqRel.source, compMdl)) and
                            (not reqRel.target or reqRelMatch(r.target, reqRel.target, compMdl)) and
                            (not reqRel.sourceObject or isinstance(type(compMdl.namedObjects.get(r.source)), xbrlObjectTypes.get(reqRel.sourceObject))) and
                            (not reqRel.targetObject or isinstance(type(compMdl.namedObjects.get(r.target)), xbrlObjectTypes.get(reqRel.targetObject))))
                        for r in ntwk.relationships or ())):
                    reqRelSatisfied = True
                    break
            if not reqRelSatisfied:
                reqRelStr = f"{reqRel.relationshipTypeName}"
                if reqRel.source: reqRelStr += f" source {reqRel.source}"
                if reqRel.target: reqRelStr += f" target {reqRel.target}"
                compMdl.error("oimte:cubeMissingRelationship",
                            _("The cube %(name)s, type %(cubeType)s, requiredCubeRelationships %(reqRel)s is missing"),
                            xbrlObject=cubeObj, name=name, cubeType=cubeType.name, reqRel=reqRelStr)

        requiredCubeProps = cubeType.effectivePropVal(compMdl, "cubeProperties", "requiredProperties")
        if requiredCubeProps:
            cubePropQNs = set()
            for propObj in compMdl.effectiveCubeProperties(cubeObj):
                if hasattr(propObj, "property"):
                    cubePropQNs.add(propObj.property)
            missingRequiredProps = [p for p in requiredCubeProps if p not in cubePropQNs]
            if missingRequiredProps:
                compMdl.error("oimte:missingRequiredCubeProperty",
                              _("Cube %(name)s is missing required cube properties %(properties)s defined by cubeType %(cubeType)s."),
                              xbrlObject=cubeObj, name=name, cubeType=cubeType.name,
                              properties=", ".join(str(p) for p in missingRequiredProps))


        for exclCubeQn in compMdl.effectiveExcludeCubes(cubeObj):
            if exclCubeQn == cubeObj.name:
                compMdl.error("oimte:excludeCubeSelfReference",
                          _("The cube %(name)s must not be defined in the excludeCubes property of itself."),
                          xbrlObject=cubeObj, name=name)
            exclCubeObj = validateQNameReference(compMdl, cubeObj, "excludeCubes", XbrlCube,
                                   undefinedMsgCode="oimte:invalidQNameReference",
                                   invalidTypeMsgCode="oimte:invalidObjectType",
                                   qnRef=exclCubeQn)
            if isinstance(exclCubeObj, XbrlCube):
                exclCubeType = validateQNameReference(compMdl, exclCubeObj, "cubeType", XbrlCubeType,
                                                      invalidTypeMsgCode="oimte:invalidObjectType",
                                                      qnRef=(exclCubeObj.cubeType or reportCubeType),
                                                      isOptional=True)
                if exclCubeType is not None and exclCubeType.name.localName != "negativeCube":
                    compMdl.error("oimte:invalidNegativeCubeReference",
                                  _("The cube %(name)s excludeCubes reference %(referenceName)s MUST have cubeType xbrl:negativeCube."),
                                  xbrlObject=cubeObj, name=name, referenceName=exclCubeQn)
                if isNegativeCubeType:
                    compMdl.error("oimte:excludeCubesOnNegativeCube",
                                  _("The cube %(name)s has cubeType xbrl:negativeCube and MUST NOT specify excludeCubes."),
                                  xbrlObject=cubeObj, name=name)

        for reqCubeQn in compMdl.effectiveRequiredCubes(cubeObj):
            validateQNameReference(compMdl, cubeObj, "requiredCubes", XbrlCube,
                                   invalidTypeMsgCode="oimte:invalidObjectType",
                                   qnRef=reqCubeQn)

        # Check exclude/required cube dimensional space overlap
        exclCubeQns = compMdl.effectiveExcludeCubes(cubeObj)
        reqCubeQns = compMdl.effectiveRequiredCubes(cubeObj)
        if exclCubeQns and reqCubeQns:
            for exclQn in exclCubeQns:
                exclObj = compMdl.namedObjects.get(exclQn)
                if not isinstance(exclObj, XbrlCube):
                    continue
                exclDims = frozenset(cd.dimension for cd in exclObj.cubeDimensions or ())
                for reqQn in reqCubeQns:
                    reqObj = compMdl.namedObjects.get(reqQn)
                    if not isinstance(reqObj, XbrlCube):
                        continue
                    reqDims = frozenset(cd.dimension for cd in reqObj.cubeDimensions or ())
                    if exclDims == reqDims:
                        compMdl.error("oimte:excludeCubeSharesDimensionalSpaceWithRequiredCube",
                                      _("Cube %(name)s excludeCube %(excludeCube)s shares the same dimensional space as requiredCube %(requiredCube)s."),
                                      xbrlObject=cubeObj, name=name, excludeCube=exclQn, requiredCube=reqQn)

        validateProperties(compMdl, oimFile, module, cubeObj)
        unitDataTypeQNs = set()
        conceptDataTypeQNs = set()
        hasConceptDimension = False
        hasTimeseriesDimension = False
        timeSeriesTaxonomyDims = []
        for iCubeDim, cubeDimObj in enumerate(cubeObj.cubeDimensions or ()):
            assertObjectType(compMdl, cubeDimObj, XbrlCubeDimension)
            dimName = cubeDimObj.dimension
            dimObj = validateQNameReference(compMdl, cubeDimObj, "dimension", XbrlDimension,
                                            invalidTypeMsgCode="oimte:invalidObjectType")
            if dimObj is None:
                continue # not worth going further with this cube dimension
            if dimObj.cubeTypes and cubeType.name not in dimObj.cubeTypes:
                compMdl.error("oimte:dimensionCubeTypeMismatch",
                              _("Cube %(name)s type %(cubeType)s MUST match one of dimension %(dimension)s cubeTypes %(cubeTypes)s."),
                              xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name, cubeType=cubeType.name,
                              dimension=dimName, cubeTypes=", ".join(str(qn) for qn in dimObj.cubeTypes))
            isTyped = False
            domClass = compMdl.namedObjects.get(dimObj.domainClass)
            if not isinstance(domClass, XbrlDomainClass):
                continue # not worth continuing, domain object missing root will be reported elsewhere
            if allowedCubeDimConstrs and not isTimeSeriesCubeType and dimName not in coreDimensions:
                # cubeDimensionConstraints/allowed constrains taxonomy-defined dimensions only; core
                # dimensions (xbrl:concept/period/entity/unit) are governed by coreDimensions, not these.
                matchedConstr = None
                for dimConstr in allowedCubeDimConstrs:
                    if dimConstr.dimensionName and dimConstr.dimensionName != dimName:
                        continue
                    if dimConstr.type:
                        dimConstrIsTyped = dimConstr.type == "typed"
                        dimObjIsTyped = isinstance(compMdl.namedObjects.get(domClass.allowedDomainItem), XbrlDataType) if domClass.allowedDomainItem else False
                        if dimConstrIsTyped != dimObjIsTyped:
                            continue
                    if dimConstr.dataType:
                        if cubeDimObj.domainDataType and dimConstr.dataType != cubeDimObj.domainDataType:
                            continue
                    matchedConstr = dimConstr
                    break
                reqProps = getattr(getattr(matchedConstr, "domainClassProperties", None), "requiredProperties", None)
                if reqProps:
                    domainPropQNs = set(p.property for p in getattr(domClass, "properties", None) or ())
                    missingReqProps = [p for p in reqProps if p not in domainPropQNs]
                    if missingReqProps:
                        compMdl.error("oimte:missingRequiredDimensionProperty",
                                      _("Cube %(name)s taxonomy-defined dimension %(dimensionName)s domainClass %(domainClass)s is missing required properties %(requiredProperties)s."),
                                      xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name,
                                      dimensionName=cubeDimObj.dimension, domainClass=domClass.name,
                                      requiredProperties=", ".join(str(p) for p in missingReqProps))
            if domClass.allowedDomainItem and isinstance(compMdl.namedObjects.get(domClass.allowedDomainItem), XbrlDataType):
                isTyped = True
            if isTyped and domClass.allowedDomainItem == qnXsDateTime:
                hasTimeseriesDimension = True
            cubeDimDT = cubeDimObj.domainDataType
            if cubeDimDT:
                domDtObj = validateQNameReference(compMdl, cubeDimObj, "domainDataType", XbrlDataType,
                                              msgCode="oimte:propertyValueDataTypeMismatch", qnRef=cubeDimDT)
                if domDtObj is not None:
                    isTyped = True
                    if domClass.allowedDomainItem and cubeDimDT != domClass.allowedDomainItem:
                        if not domDtObj.instanceOfType(domClass.allowedDomainItem, compMdl):
                            compMdl.error("oimte:invalidDataTypeForDomainClass",
                                          _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST be the same as or derived from the allowedDomainItem defined on the domain class: %(allowedDomainItem)s."),
                                          xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT, allowedDomainItem=domClass.allowedDomainItem)
                    if dimName == periodCoreDim:
                        compMdl.error("oimte:domainNetworkUsedOnPeriodDimension",
                                      _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST not be used on a period dimension."),
                                      xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT)
                    elif dimName == conceptCoreDim:
                        compMdl.error("oimte:invalidConceptDomain",
                                      _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST not be used on a concept dimension."),
                                      xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT)
            hasValidDomainName = False
            if cubeDimObj.domainNetwork:
                if isTyped:
                    if dimName == periodCoreDim:
                        compMdl.error("oimte:domainNetworkUsedOnPeriodDimension",
                                  _("Cube %(name)s dimension %(dimensionName)s domain objects MUST NOT be defined with a domainName property."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                    else:
                        compMdl.error("oimte:invalidCubeDimensionDomainName",
                                  _("Cube %(name)s dimension %(dimensionName)s domainNetwork MUST NOT be used with a typed dimension."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                cubeDomNwkObj = compMdl.namedObjects.get(cubeDimObj.domainNetwork)
                if isinstance(cubeDomNwkObj, XbrlDomainNetwork):
                    hasValidDomainName = True
                elif cubeDomNwkObj is not None:
                    compMdl.error("oimte:invalidObjectType",
                              _("Cube %(name)s domainNetwork property %(domainNetwork)s MUST reference a domain network object, not %(actualType)s."),
                              xbrlObject=cubeObj, name=name, domainNetwork=cubeDimObj.domainNetwork, actualType=type(cubeDomNwkObj).__name__)
                else:
                    compMdl.error("oimte:invalidQNameReference",
                              _("Cube %(name)s domainNetwork property %(domainNetwork)s does not resolve to an object in the taxonomy model."),
                              xbrlObject=cubeObj, name=name, domainNetwork=cubeDimObj.domainNetwork)
            if cubeDimObj.periodConstraints and dimName != periodCoreDim:
                compMdl.error("oimte:invalidPeriodConstraintDimension",
                          _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)
            if dimName == conceptCoreDim:
                hasConceptDimension = True
            if dimName == conceptCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainNetwork].relationships or ():
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), (XbrlConcept, XbrlHeading)) and relObj.source != conceptDomainClass:
                        compMdl.error("oimte:invalidRelationshipSourceObject",
                                  _("Cube %(name)s conceptConstraints domain relationships must be from concepts, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if isinstance(compMdl.namedObjects.get(relObj.target,None), XbrlConcept):
                        conceptDataTypeQNs.add(compMdl.namedObjects[relObj.target].dataType)
                if cubeDimObj.optional:
                    compMdl.error("oimte:invalidOptionalPropertyOnConceptDimension",
                              _("Cube %(name)s conceptConstraints property MUST NOT specify allowDomainFacts."),
                              xbrlObject=(cubeObj,cubeDimObj), name=name)
            if dimName == entityCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainNetwork].relationships or ():
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), XbrlEntity) and relObj.source != entityDomainClass:
                        compMdl.error("oimte:invalidRelationshipSourceObject",
                                  _("Cube %(name)s entityConstraints domain relationships must be from entities, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
            if dimName == unitCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainNetwork].relationships or ():
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), XbrlUnit) and relObj.source != unitDomainClass:
                        compMdl.error("oimte:invalidRelationshipSourceObject",
                                  _("Cube %(name)s unitConstraints domain relationships must be from units, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
            if dimName in (periodCoreDim, languageCoreDim) and hasValidDomainName:
                compMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s dimension %(qname)s must not specify domain network %(domainNetwork)s."),
                          xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName, domainNetwork=cubeDimObj.domainNetwork)
            if dimName not in coreDimensions and isinstance(compMdl.namedObjects.get(dimName), XbrlDimension):
                timeSeriesTaxonomyDims.append((cubeDimObj, dimObj, isTyped, cubeDimDT, domClass))
                if not isTyped: # explicit
                    domNwkObj = compMdl.namedObjects.get(cubeDimObj.domainNetwork)
                    if isinstance(domNwkObj, XbrlDomainNetwork):
                        for relObj in domNwkObj.relationships or ():
                            if not isinstance(compMdl.namedObjects.get(getattr(relObj, "target", None),None), (XbrlConcept, XbrlHeading, XbrlUnit, XbrlMember)):
                                compMdl.error("oimte:invalidDomainRelationshipTarget",
                                          _("Cube %(name)s explicit dimension domain network relationships must be to members."),
                                          xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName)
                        if dimObj.domainClass and domNwkObj.root and dimObj.domainClass != domNwkObj.root:
                            compMdl.error("oimte:invalidCubeDimensionDomainName",
                                      _("Cube %(name)s explicit dimension domain network root %(domClass)s does not match dimension domainClass %(dimRoot)s."),
                                      xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName, domClass=domNwkObj.root, dimRoot=dimObj.domainClass)
            if not isTyped: # explicit dimension
                if cubeDimObj.typedSort is not None:
                    compMdl.error("oimte:invalidTypedSortOnExplicitDomain",
                              _("Cube %(name)s typedSort property MUST not be used on an explicit dimension."),
                              xbrlObject=cubeObj, name=name)
            if dimName == periodCoreDim:
                for iPerConst, perConstObj in enumerate(cubeDimObj.periodConstraints):
                    if perConstObj.timeSpan:
                        if perConstObj.endDate and perConstObj.startDate:
                            compMdl.error("oimte:redundantTimeSpanProperty",
                                      _("Cube %(name)s period constraint timeSpan property MUST NOT be used with both the endDate and startDate properties."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        perConstObj._timeSpanValid, perConstObj._timeSpanValue = validateValue(compMdl, module, cubeObj, perConstObj.timeSpan, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/timeSpan", "oimte:invalidPeriodRepresentation")
                    if perConstObj.periodPattern:
                        perStr, _sep, perAttr = perConstObj.periodPattern.partition("@")
                        isInstPerPat = perAttr in ("start", "end")
                        perConstObj._periodPatternDict = None
                        if not isInstPerPat and (perConstObj.timeSpan or perConstObj.endDate or perConstObj.startDate):
                            compMdl.error("oimte:redundantPeriodPatternProperty",
                                      _("Cube %(name)s period constraint periodPattern property MUST NOT be used with the timeSpan, endDate or startDate properties if it represents a duration."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        else:
                            m = periodConstraintPeriodPattern.match(perStr)
                            if m:
                                perConstObj._periodPatternDict = m.groupdict()
                            else:
                                compMdl.error("oimte:invalidPeriodRepresentation",
                                          _("Cube %(name)s periodConstraint[%(perConstNbr)s] periodFormat property, %(periodPattern)s, MUST be a valid period pattern per xbrl-csv specification."),
                                          xbrlObject=(cubeObj,cubeDimObj), name=name, perConstNbr=iPerConst, periodPattern=perConstObj.periodPattern)
                    if perConstObj.periodType == "instant" and (perConstObj.timeSpan or perConstObj.startDate):
                        compMdl.error("oimte:instantWithDurationProperties",
                              _("Cube %(name)s period constraint periodType instant MUST NOT define timeSpan or startDate."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    for dtResProp in ("monthDay", "endDate", "startDate", "onOrAfter", "onOrBefore"):
                        dtResObj = getattr(perConstObj, dtResProp, None)
                        if dtResObj is not None:
                            if dtResObj.conceptName:
                                cncpt = compMdl.namedObjects.get(dtResObj.conceptName)
                                if cncpt is None:
                                    compMdl.error("oimte:invalidQNameReference",
                                              _("Cube %(name)s period constraint concept %(qname)s MUST resolve to an object in the model."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                                elif not isinstance(cncpt, XbrlConcept):
                                    compMdl.error("oimte:invalidObjectType",
                                              _("Cube %(name)s period constraint concept %(qname)s MUST be a concept object."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                                elif isinstance(compMdl.namedObjects.get(cncpt.dataType), XbrlDataType) and compMdl.namedObjects[cncpt.dataType].xsBaseType(compMdl) in ("date", "dateTime"):
                                    compMdl.dateResolutionConceptNames.add(dtResObj.conceptName)
                                else:
                                    compMdl.error("oimte:invalidConceptDataType",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a date or dateTime."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                            if dtResObj.context:
                                cncpt = compMdl.namedObjects.get(dtResObj.context)
                                if isinstance(cncpt, XbrlConcept) and (dtResObj.context.atSuffix in ("start","end")):
                                    compMdl.dateResolutionConceptNames.add(dtResObj.context)
                                else:
                                    compMdl.error("oimte:invalidObjectType",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a concept and any suffix MUST be start or end."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                            if dtResObj.timeShift:
                                if dtResObj.value or (dtResObj.conceptName and dtResObj.context):
                                    compMdl.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s timeShift MUST be used with only one of the properties name, or context."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                                dtResObj._timeShiftValid, dtResObj._timeShiftValue = validateValue(compMdl, module, cubeObj, dtResObj.timeShift, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/timeShift", "oimte:invalidPeriodRepresentation")
                            if dtResObj.value:
                                dtResObj._valueValid, dtResObj._valueValue = validateValue(compMdl, module, cubeObj, dtResObj.value, "XBRLI_DATEUNION", f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/value", "oimte:invalidPeriodRepresentation")

        # Extension cubes inherit concept dimension from target; only check non-extension cubes
        # (skip empty cubeDimensions — already reported as invalidEmptySet at load)
        if cubeObj.cubeDimensions and not hasConceptDimension and not getattr(cubeObj, 'extends', None):
                compMdl.error("oimte:cubeMissingConceptDimension",
                          _("The cubeDimensions of cube %(name)s, type %(cubeType)s, must have a concept core dimension"),
                          xbrlObject=cubeObj, name=name, cubeType=getattr(cubeType,'name',None))

        coreDomainClassByDimension = {
            conceptCoreDim: conceptDomainClass,
            entityCoreDim: entityDomainClass,
            unitCoreDim: unitDomainClass,
        }
        coreDomainClasses = set(cubeType.effectivePropVal(compMdl, "coreDomainClasses"))
        if coreDomainClasses:
            cubeDimByName = {cd.dimension: cd for cd in cubeObj.cubeDimensions or ()}
            for reqDim, reqDomClass in coreDomainClassByDimension.items():
                if reqDomClass in coreDomainClasses:
                    cubeDimObj = cubeDimByName.get(reqDim)
                    if cubeDimObj is not None and not cubeDimObj.domainNetwork:
                        compMdl.error("oimte:missingCoreDomainNameFromCubeDimension",
                                      _("Cube %(name)s dimension %(dimensionName)s MUST specify domainNetworkName because cubeType %(cubeType)s requires coreDomainClass %(domainClass)s."),
                                      xbrlObject=(cubeObj, cubeDimObj), name=name, dimensionName=reqDim, cubeType=cubeType.name, domainClass=reqDomClass)

        if isTimeSeriesCubeType:
            if timeSeriesTaxonomyDims:
                hasTimeseriesDimension = True
            typedDateTimeDims = []
            for cubeDimObj, dimObj, isTyped, cubeDimDT, domClass in timeSeriesTaxonomyDims:
                hasDateTimeType = cubeDimDT == qnXsDateTime or getattr(domClass, "allowedDomainItem", None) == qnXsDateTime
                if isTyped and hasDateTimeType:
                    typedDateTimeDims.append((cubeDimObj, dimObj, isTyped, cubeDimDT, domClass))
                else:
                    compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                                  _("Timeseries cube %(name)s taxonomy-defined dimension %(dimensionName)s MUST be typed xs:dateTime."),
                                  xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name, dimensionName=cubeDimObj.dimension)
            if len(typedDateTimeDims) != 1:
                compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                              _("Timeseries cube %(name)s MUST have exactly one typed taxonomy-defined dimension."),
                              xbrlObject=cubeObj, name=name)

            if allowedCubeDimConstrs:
                for cubeDimObj, dimObj, _isTyped, _cubeDimDT, domClass in typedDateTimeDims:
                    matchedConstr = None
                    for dimConstr in allowedCubeDimConstrs:
                        if dimConstr.dimensionName and dimConstr.dimensionName != cubeDimObj.dimension:
                            continue
                        if dimConstr.type:
                            isTypedConstr = dimConstr.type == "typed"
                            if isTypedConstr != _isTyped:
                                continue
                        if dimConstr.dataType:
                            actualDataType = cubeDimObj.domainDataType
                            if actualDataType is None and _isTyped and getattr(domClass, "allowedDomainItem", None) == qnXsDateTime:
                                actualDataType = qnXsDateTime
                            if dimConstr.dataType != actualDataType:
                                continue
                        matchedConstr = dimConstr
                        break
                    if matchedConstr is None:
                        compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                                      _("Cube %(name)s taxonomy-defined dimension %(dimensionName)s does not satisfy cubeType constraints."),
                                      xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name, dimensionName=cubeDimObj.dimension)
                    else:
                        reqProps = getattr(getattr(matchedConstr, "domainClassProperties", None), "requiredProperties", None)
                        if reqProps:
                            domainPropQNs = set(p.property for p in getattr(domClass, "properties", None) or ())
                            missingReqProps = [p for p in reqProps if p not in domainPropQNs]
                            if missingReqProps:
                                compMdl.error("oimte:missingRequiredDimensionProperty",
                                              _("Cube %(name)s taxonomy-defined dimension %(dimensionName)s domainClass %(domainClass)s is missing required properties %(requiredProperties)s."),
                                              xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name,
                                              dimensionName=cubeDimObj.dimension, domainClass=domClass.name,
                                              requiredProperties=", ".join(str(p) for p in missingReqProps))

        for unitDataTypeQN in unitDataTypeQNs:
            if unitDataTypeQN not in conceptDataTypeQNs:
                compMdl.error("oimte:invalidDataTypeObject",
                          _("Cube %(name)s unitConstraints data Type %(dataType)s MUST have at least one associated concept object on the concept core dimension with the same datatype as the unit object."),
                          xbrlObject=(cubeObj,cubeDimObj), name=name, dataType=unitDataTypeQN)

        if isTimeSeriesCubeType and not hasTimeseriesDimension:
            compMdl.error("oimte:timeseriesCubeMissingTimeseriesDimension",
                      _("Timeseries cube %(name)s MUST have a timeseries dimension."),
                      xbrlObject=(cubeObj,cubeDimObj), name=name)

    # Dimension Objects
    for dimObj in getattr(module, "dimensions", None) or ():
        assertObjectType(compMdl, dimObj, XbrlDimension)
        for cubeTypeQn in dimObj.cubeTypes or ():
            validateQNameReference(compMdl, dimObj, "cubeTypes", XbrlCubeType, qnRef=cubeTypeQn,
                                   invalidTypeMsgCode="oimte:invalidObjectType")
        domRtObj = validateQNameReference(compMdl, dimObj, "domainClass", XbrlDomainClass, msgCode="oimte:invalidDomainClass")
        # Only xbrl:conceptDomain and xbrl:languageDomain are restricted to their matching core
        # dimension (oim-taxonomy §1266/§1334/§1338). xbrl:entityDomain and xbrl:unitDomain MAY be
        # used on taxonomy-defined dimensions (§1184, e.g. a legal-entity dimension).
        if (dimObj.domainClass in (conceptDomainClass, languageDomainClass) and
                                   (dimObj.name.namespaceURI != xbrl or not dimObj.domainClass.localName.startswith(dimObj.name.localName))):
            compMdl.error(f"oimte:invalid{dimObj.domainClass.localName[:-6].title()}DomainClass",
                        _("The dimension domainClass object QName MUST not be %(name)s."),
                        xbrlObject=dimObj, name=dimObj.domainClass)
        validateProperties(compMdl, oimFile, module, dimObj)
        exclIntPropStr = dimObj.propertyObjectValue(excludedIntervalsPropType)
        if exclIntPropStr is not None:
            try:
                if isinstance(exclIntPropStr, list): # allow list of strings
                    exclIntPropStr = "\n".join(exclIntPropStr)
                dimObj._excludedIntervals = dateutil.rrule.rrulestr(exclIntPropStr.replace("\\n", "\n"))
            except dateutil.parser._parser.ParserError as ex:
                compMdl.error("oimte:invalidExcludedIntervals",
                          _("The dimension %(name)s excludedIntervals property error %(error)s, value %(excludedIntervals)s."),
                          xbrlObject=dimObj, name=dimObj.name, error=str(ex), excludedIntervals=exclIntPropStr)

    # Domain Objects
    for domNwkObj in module.domainNetworks or ():
        assertObjectType(compMdl, domNwkObj, XbrlDomainNetwork)
        extendTargetObj = None
        extendedDomClassQn = None
        if domNwkObj.extends:
            extendTargetObj = validateQNameReference(compMdl, domNwkObj, "extends", XbrlDomainNetwork,
                                                     invalidTypeMsgCode="oimte:invalidObjectType")
            if extendTargetObj is not None:
                if getattr(domNwkObj, "_extendResolved", False):
                    extendTargetObj = None # don't extend, already been extended
                elif not getattr(extendTargetObj, "isExtensible", True):
                    compMdl.error("oimte:illegalExtensionOfNonExtensibleObject",
                            _("The domain network %(name)s cannot be extended because it is non-extensible."),
                            xbrlObject=domNwkObj, name=extendTargetObj.name)
                    continue
                else:
                    domNwkObj._extendResolved = True
                    extendedDomClassQn = getattr(extendTargetObj, "root", None)
        elif not domNwkObj.name:
            compMdl.error("oimte:missingRequiredProperty",
                      _("The domain network object MUST have either a name or an extends, not neither."),
                      xbrlObject=domNwkObj)
        domRtObj = validateQNameReference(compMdl, domNwkObj, "root", XbrlDomainClass, qnDefault=extendedDomClassQn, msgCode="oimte:invalidDomainClass")
        if not domRtObj:
            continue
        domRtQn = domRtObj.name
        domRelCts = {}
        domRelRoots = set(relObj.source for relObj in domNwkObj.relationships or () if getattr(relObj, "source", None))
        domClassSourceInRel = domRtObj is not None # only check if there are any relationships
        for i, relObj in enumerate(domNwkObj.relationships or ()):
            if i == 0:
                domClassSourceInRel = False
            assertObjectType(compMdl, relObj, XbrlRelationship)
            src = getattr(relObj, "source", None)
            tgt = getattr(relObj, "target", None)
            if src not in compMdl.namedObjects or tgt not in compMdl.namedObjects:
                if src not in compMdl.namedObjects:
                    validateQNameReference(compMdl, relObj, "source", qnRef=src,
                                           undefinedMessage=_("The domain network %(name)s relationship[%(nbr)s] source, %(source)s, MUST be an object in the taxonomy model."),
                                           errorArgs={"name": domNwkObj.name, "nbr": i, "source": src})
                if tgt not in compMdl.namedObjects:
                    validateQNameReference(compMdl, relObj, "target", qnRef=tgt,
                                           undefinedMessage=_("The domain network %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an object in the taxonomy model."),
                                           errorArgs={"name": domNwkObj.name, "nbr": i, "target": tgt})
            else:
                if domRtQn == conceptDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], (XbrlConcept, XbrlHeading)):
                        compMdl.error("oimte:invalidDomainSource",
                                  _("The domain network %(name)s relationship[%(nbr)s] source, %(source)s MUST be a concept object in the taxonomy model."),
                                  xbrlObject=relObj, name=domNwkObj.name, nbr=i, source=relObj.source)
                if domRtQn == entityDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], XbrlEntity):
                        compMdl.error("oimte:invalidDomainSource",
                                  _("The domain network %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the entity root or an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domNwkObj.name, nbr=i, source=relObj.source)
                    if not isinstance(compMdl.namedObjects[relObj.target], XbrlEntity):
                        compMdl.error("oimte:invalidDomainRelationshipTarget",
                                  _("The domain network %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domNwkObj.name, nbr=i, target=relObj.target)
                if domRtQn == unitDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], XbrlUnit):
                        compMdl.error("oimte:invalidDomainSource",
                                  _("The domain network %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the unit root or an unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domNwkObj.name, nbr=i, source=relObj.source)
                    if not isinstance(compMdl.namedObjects[relObj.target], XbrlUnit):
                        compMdl.error("oimte:invalidDomainRelationshipTarget",
                                  _("The domain network %(name)s relationship[%(nbr)s] target, %(target)s, MUST be a unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domNwkObj.name, nbr=i, target=relObj.target)
                elif isinstance(compMdl.namedObjects[relObj.source], XbrlUnit) or isinstance(compMdl.namedObjects[relObj.target], XbrlUnit):
                    compMdl.error("oimte:invalidDomainObject",
                              _("The domain network %(name)s relationship[%(nbr)s] source, %(source)s, or target, %(target)s, MUST be not be unit objects in the taxonomy model."),
                              xbrlObject=relObj, name=domNwkObj.name, nbr=i, source=relObj.source, target=relObj.target)
                for prop in ("source", "target"):
                    obj = compMdl.namedObjects[getattr(relObj, prop)]
                    if isinstance(obj, XbrlMember) and domRtQn in (conceptDomainClass, unitDomainClass, entityDomainClass, languageDomainClass):
                        compMdl.error("oimte:invalidDimensionMember",
                                  _("The domain network %(name)s relationship[%(nbr)s] %(property)s, %(propQn)s MUST be not be a member object in the taxonomy model."),
                                  xbrlObject=relObj, name=domNwkObj.name, nbr=i, property=prop, propQn=getattr(relObj, prop))
                    if isinstance(obj, XbrlMember) and domRtQn not in (conceptDomainClass, unitDomainClass, entityDomainClass, languageDomainClass):
                        memberDomClasses = getattr(obj, "domainClasses", None) or ()
                        if memberDomClasses and domRtQn not in memberDomClasses:
                            compMdl.error("oimte:invalidDomainClassReference",
                                      _("The domain network %(name)s relationship[%(nbr)s] %(property)s member %(propQn)s has domainClasses %(domainClasses)s which does not include the domain root %(root)s."),
                                      xbrlObject=relObj, name=domNwkObj.name, nbr=i, property=prop, propQn=getattr(relObj, prop),
                                      domainClasses=", ".join(str(dc) for dc in memberDomClasses), root=domRtQn)
                    if domRtObj and domRtObj.allowedDomainItem and (prop != "source" or obj != domRtObj):
                        objTypeQn = xbrlObjectQNames.get(type(obj))
                        allowedTypes = {domRtObj.allowedDomainItem}
                        # §oim-taxonomy: a heading object is always permitted as a target in a
                        # domain network whose root is xbrl:conceptDomain, irrespective of allowedDomainItem.
                        if domRtObj.allowedDomainItem == qnXbrlConceptObj:
                            allowedTypes.add(qnXbrlHeadingObj)
                        if objTypeQn not in allowedTypes and not isinstance(obj, XbrlDataType):
                            compMdl.error("oimte:invalidDomainNetworkObject",
                                      _("The domain network %(name)s relationship[%(nbr)s] %(property)s, %(propQn)s MUST be an object matching the allowedDomainItem %(allowedDomainItem)s."),
                                      xbrlObject=relObj, name=domNwkObj.name, nbr=i, property=prop, propQn=getattr(relObj, prop), allowedDomainItem=domRtObj.allowedDomainItem)
                        # §oim-taxonomy: if the root is NOT a core domain (concept/entity/unit/language),
                        # a target MUST NOT be a concept or unit object unless expressly permitted by the
                        # domain class's allowedDomainItem. (oimte:invalidDomainTarget)
                        if (prop == "target"
                                and domRtQn not in (conceptDomainClass, entityDomainClass, unitDomainClass, languageDomainClass)
                                and isinstance(obj, (XbrlConcept, XbrlUnit))
                                and objTypeQn != domRtObj.allowedDomainItem):
                            compMdl.error("oimte:invalidDomainTarget",
                                      _("The domain network %(name)s relationship[%(nbr)s] target, %(propQn)s, is a %(objType)s which is not permitted by the domain class allowedDomainItem %(allowedDomainItem)s."),
                                      xbrlObject=relObj, name=domNwkObj.name, nbr=i, propQn=getattr(relObj, prop),
                                      objType=objTypeQn, allowedDomainItem=domRtObj.allowedDomainItem)
            if isinstance(compMdl.namedObjects.get(tgt), XbrlDomainClass):
                compMdl.error("oimte:invalidDomainRelationshipTarget",
                          _("The domain network %(name)s relationship target %(qname)s MUST NOT be a domainClass object."),
                          xbrlObject=domNwkObj, name=domNwkObj.name, qname=tgt)
            elif isinstance(compMdl.namedObjects.get(tgt), XbrlDomainNetwork):
                compMdl.error("oimte:invalidObjectType",
                          _("The domain network %(name)s relationship target %(qname)s MUST NOT be a domain object."),
                          xbrlObject=domNwkObj, name=domNwkObj.name, qname=tgt)
            elif extendTargetObj is not None:
                extendTargetObj.relationships.add(relObj)
            if tgt == domRtQn:
                compMdl.error("oimte:invalidDomainRelationshipTarget",
                          _("The domain network %(name)s relationship target %(qname)s MUST NOT be The domain network root object."),
                          xbrlObject=domNwkObj, name=domNwkObj.name, qname=tgt)
            if domRtQn == src:
                domClassSourceInRel = True
            relKey = (src, tgt)
            domRelCts[relKey] = domRelCts.get(relKey, 0) + 1
            domRelRoots.discard(tgt) # remove any target from roots
        if any(ct > 1 for relKey, ct in domRelCts.items()):
            compMdl.error("oimte:duplicateItemsInSet",
                      _("The domain network %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=domNwkObj, name=domNwkObj.name,
                      names=", ".join(f"{relKey[0]}\u2192{relKey[1]}" for relKey, ct in domRelCts.items() if ct > 1))
        if domRtObj and not domClassSourceInRel:
            compMdl.error("oimte:missingDomainClassSource",
                      _("The domain network %(name)s root %(qname)s MUST be a source in a relationship"),
                      xbrlObject=domNwkObj, name=domNwkObj.name, qname=domNwkObj.root)
        if len(domRelRoots) > 1:
            compMdl.error("oimte:multipleDomainClasses",
                      _("The domain network %(name)s relationship must resolve to a single root object, multiple found: %(roots)s"),
                      xbrlObject=domNwkObj, name=domNwkObj.name, roots=", ".join(sorted(str(r) for r in domRelRoots)))
        validateProperties(compMdl, oimFile, module, domNwkObj)


    # DomainClass Objects
    valid_allowedDomainItem_qnames = (qnXbrlMemberObj, qnXbrlConceptObj, qnXbrlEntityObj, qnXbrlUnitObj)
    for implObj in module.impliedObjects or ():
        implObjType = getattr(implObj, "objectType", None)
        if implObjType is not None and implObjType not in (qnXbrlMemberObj, qnXbrlEntityObj):
            compMdl.error("oimte:invalidObjectTypeForImpliedObject",
                      _("The implied object %(name)s objectType %(objectType)s MUST be xbrl:memberObject or xbrl:entityObject."),
                      xbrlObject=implObj, name=getattr(implObj, "name", None), objectType=implObjType)

    reservedCoreDomainClasses = frozenset((conceptDomainClass, entityDomainClass, unitDomainClass,
                                           languageDomainClass, periodDomainClass))
    for mbrObj in module.members or ():
        assertObjectType(compMdl, mbrObj, XbrlMember)
        for domClsQn in mbrObj.domainClasses or ():
            if domClsQn in reservedCoreDomainClasses:
                compMdl.error("oimte:invalidDomainClassReference",
                          _("The member %(name)s domainClass %(domainClass)s is reserved for a core dimension and MUST NOT be referenced by a member object."),
                          xbrlObject=mbrObj, name=mbrObj.name, domainClass=domClsQn)

    for domRtObj in module.domainClasses or ():
        assertObjectType(compMdl, domRtObj, XbrlDomainClass)
        name = domRtObj.name
        allwdDomItemQn = domRtObj.allowedDomainItem
        allwdDomItemObj = compMdl.namedObjects.get(allwdDomItemQn)
        isObjectTypeItem = _qname_in_set(allwdDomItemQn, valid_allowedDomainItem_qnames)
        isDataTypeItem = isinstance(allwdDomItemObj, XbrlDataType)
        if not isObjectTypeItem and not isDataTypeItem:
            compMdl.error("oimte:invalidObjectType",
              _("DomainClass %(name)s allowedDomainItem %(allowedDomainItem)s MUST be xbrl:entityObject, xbrl:unitObject, xbrl:memberObject, xbrl:conceptObject, or a dataType object."),
              xbrlObject=domRtObj, name=name, allowedDomainItem=allwdDomItemQn)
        if domRtObj.baseDomainClass:
            baseDomClassObj = compMdl.namedObjects.get(domRtObj.baseDomainClass)
            if isinstance(baseDomClassObj, XbrlDomainClass):
                baseAllwdItem = baseDomClassObj.allowedDomainItem
                if isObjectTypeItem:
                    if allwdDomItemQn != baseAllwdItem:
                        compMdl.error("oimte:inconsistentBaseDomainClass",
                          _("DomainClass %(name)s allowedDomainItem %(allowedDomainItem)s MUST match base domain class %(base)s allowedDomainItem %(baseItem)s."),
                          xbrlObject=domRtObj, name=name, allowedDomainItem=allwdDomItemQn, base=domRtObj.baseDomainClass, baseItem=baseAllwdItem)
                elif isDataTypeItem:
                    baseIsDataType = isinstance(compMdl.namedObjects.get(baseAllwdItem), XbrlDataType)
                    if not baseIsDataType or not allwdDomItemObj.instanceOfType(baseAllwdItem, compMdl):
                        compMdl.error("oimte:inconsistentBaseDomainClass",
                          _("DomainClass %(name)s allowedDomainItem %(allowedDomainItem)s MUST be the same as or derived from base domain class %(base)s allowedDomainItem %(baseItem)s."),
                          xbrlObject=domRtObj, name=name, allowedDomainItem=allwdDomItemQn, base=domRtObj.baseDomainClass, baseItem=baseAllwdItem)
                else:
                    compMdl.error("oimte:inconsistentBaseDomainClass",
                      _("DomainClass %(name)s allowedDomainItem %(allowedDomainItem)s is incompatible with base domain class %(base)s allowedDomainItem %(baseItem)s."),
                      xbrlObject=domRtObj, name=name, allowedDomainItem=allwdDomItemQn, base=domRtObj.baseDomainClass, baseItem=baseAllwdItem)
        validateProperties(compMdl, oimFile, module, domRtObj)

        isDateTimeType = domRtObj.allowedDomainItem == qnXsDateTime
        if isDateTimeType:
            # Get time-series properties from domain class
            domClassTsProps = {timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, completeTimeSeriesPropType} & set(p.property for p in getattr(domRtObj, 'properties') or EMPTY_FROZENSET)
            if domClassTsProps:
                # Validate dependent properties
                tsTypeVal = domRtObj.propertyObjectValue(timeSeriesPropType)
                iomVal = domRtObj.propertyObjectValue(intervalOfMeasurementPropType)
                icVal = domRtObj.propertyObjectValue(intervalConventionPropType)
                ctsVal = domRtObj.propertyObjectValue(completeTimeSeriesPropType)
                aggVal = domRtObj.propertyObjectValue(aggregationPropType)
                
                # Rule 1: timeSeriesType="Aggregated" requires xbrla:aggregation
                if tsTypeVal == "Aggregated" and aggVal is None:
                    compMdl.error("oimte:missingDependentPropertyType",
                              _("Domain class %(name)s with xbrla:timeSeriesType Aggregated MUST also have xbrla:aggregation."),
                              xbrlObject=domRtObj, name=name)
                
                # Rule 2: intervalConvention requires intervalOfMeasurement
                if intervalConventionPropType in domClassTsProps and iomVal is None:
                    compMdl.error("oimte:missingDependentPropertyType",
                              _("Domain class %(name)s with xbrla:intervalConvention MUST also have xbrla:intervalOfMeasurement."),
                              xbrlObject=domRtObj, name=name)
                
                # Rule 3: completeTimeSeries=true requires intervalOfMeasurement
                if ctsVal is True and iomVal is None:
                    compMdl.error("oimte:missingDependentPropertyType",
                              _("Domain class %(name)s with xbrla:completeTimeSeries true MUST also have xbrla:intervalOfMeasurement."),
                              xbrlObject=domRtObj, name=name)

    # Entity Objects
    for entityObj in module.entities or ():
        assertObjectType(compMdl, entityObj, XbrlEntity)
        validateProperties(compMdl, oimFile, module, entityObj)

    # GroupContent Objects
    for grpCntObj in module.groupContents or ():
        assertObjectType(compMdl, grpCntObj, XbrlGroupContent)
        grpQn = grpCntObj.groupName
        validateQNameReference(compMdl, grpCntObj, "groupName", XbrlGroup,
                               invalidTypeMsgCode="oimte:invalidObjectType",
                               undefinedMessage=_("The groupContent object groupName QName %(name)s MUST be a valid group object in the taxonomy model"),
                               invalidTypeMessage=_("The groupContent object groupName QName %(name)s MUST be a valid group object in the taxonomy model"),
                               errorArgs={"name": grpQn}, qnRef=grpQn)
        relName = grpCntObj.forObject
        if relName is not None:
            validateQNameReference(compMdl, grpCntObj, "forObject",
                                   (XbrlNetwork, XbrlCube, XbrlTableTemplate, XbrlDomainNetwork, XbrlLayout),
                                   invalidTypeMsgCode="oimte:invalidGroupContentForObject",
                                   undefinedMessage=_("The groupContent object %(name)s forObject %(relName)s MUST only include QNames associated with network objects, cube objects, table template objects or layout objects."),
                                   invalidTypeMessage=_("The groupContent object %(name)s forObject %(relName)s MUST only include QNames associated with network objects, cube objects, table template objects or layout objects."),
                                   errorArgs={"name": grpQn, "relName": relName}, qnRef=relName)

    # Label Objects
    for lblObj in module.labels or ():
        assertObjectType(compMdl, lblObj, XbrlLabel)
        forObject = lblObj.forObject
        relatedObj = None
        if forObject in compMdl.namedObjects:
            relatedObj = compMdl.namedObjects.get(forObject)
        elif forObject in xbrlObjectTypes:
            relatedObj = forObject
        elif compMdl.isImpliedObject(forObject):
            _validateImpliedObjectLocalName(compMdl, lblObj, forObject)
            relatedObj = forObject
        else:
            compMdl.error("oimte:invalidQNameReference",
                      _("Label has invalid related object %(forObject)s"),
                      xbrlObject=lblObj, forObject=forObject)
        lblTpObj = validateQNameReference(compMdl, lblObj, "labelType", XbrlLabelType)
        if lblTpObj:
            if lblTpObj.allowedObjects and relatedObj is not None and not any(
                type(relatedObj) == xbrlObjectTypes.get(allowedObj) for allowedObj in lblTpObj.allowedObjects):
                compMdl.error("oimte:disallowedObjectLabelType",
                          _("Label has disallowed related object %(forObject)s"),
                          xbrlObject=lblObj, forObject=forObject)
            lblObj._xValid, lblObj._xValue = validateValue(compMdl, module, lblObj, lblObj.value, lblTpObj.dataType, "", "oimte:invalidLabelValue")
        validateProperties(compMdl, oimFile, module, lblObj)
        lblKey = (forObject, lblObj.labelType, lblObj.language)
        mdlLvlChecks.labelsCt[lblKey].append(lblObj)

    # Network, PropertyType and RelationshipType Objects
    validateNetworkFamily(compMdl, module, oimFile, **familyKwargs)

    # Reference Objects
    refsWithInvalidRelName = []
    refInvalidNames = []
    refsDup = defaultdict(list)
    for refObj in module.references or ():
        assertObjectType(compMdl, refObj, XbrlReference)
        name = refObj.name
        lang = refObj.language
        refTp = refObj.referenceType
        extName = refObj.extends
        for relName in refObj.forObjects or ():
            if relName not in compMdl.namedObjects:
                refsWithInvalidRelName.append(refObj)
                refInvalidNames.append(relName)
        if refTp or not extName:
            validateQNameReference(compMdl, refObj, "referenceType", XbrlReferenceType,
                                   undefinedMessage=_("The reference %(name)s reference %(qname)s MUST be a referenceType object."),
                                   invalidTypeMessage=_("The reference %(name)s reference %(qname)s MUST be a referenceType object."),
                                   errorArgs={"name": name, "qname": refTp}, qnRef=refTp)
        refTypeObj = compMdl.namedObjects.get(refTp) if refTp else None
        if isinstance(refTypeObj, XbrlReferenceType):
            # a reference MUST NOT be defined for an object type not allowed by its referenceType
            if refTypeObj.allowedObjects:
                for relName in refObj.forObjects or ():
                    relatedObj = compMdl.namedObjects.get(relName)
                    if relatedObj is not None and not _qname_in_set(xbrlObjectQNames.get(type(relatedObj)), refTypeObj.allowedObjects):
                        compMdl.error("oimte:disallowedObjectReferenceType",
                                  _("The reference %(name)s forObject %(forObject)s has an object type not permitted by referenceType %(refType)s allowedObjects."),
                                  xbrlObject=refObj, name=name, forObject=relName, refType=refTp)
            # a reference MUST include all properties required by its referenceType
            if refTypeObj.requiredProperties:
                refPropQns = set(p.property for p in refObj.properties or ())
                missingReqProps = [p for p in refTypeObj.requiredProperties if p not in refPropQns]
                if missingReqProps:
                    compMdl.error("oimte:missingRequiredProperty",
                              _("The reference %(name)s is missing required propert(ies) %(props)s defined by referenceType %(refType)s."),
                              xbrlObject=refObj, name=name, props=", ".join(sorted(str(p) for p in missingReqProps)), refType=refTp)
        if extName:
            if name:
                compMdl.error("oimte:referenceNameRedefined",
                          _("Referencehas both extends and name %(name)s"),
                          xbrlObject=refObj, name=extName)
            else:
                extRefObjs = compMdl.tagObjects.get(extName) or ()
                if not all(isinstance(extRefObj, XbrlReference) for extRefObj in extRefObjs):
                    compMdl.error("oimte:invalidQNameReference",
                              _("Reference extends must be a reference object %(name)s"),
                              xbrlObject=refObj, name=extName)
                elif not any(extRefObj.referenceType == refTp for extRefObj in extRefObjs):
                    compMdl.error("oimte:referenceTypeRedefined",
                              _("Reference extends reference object %(name)s must have same referenceType %(referenceType)s"),
                              xbrlObject=refObj, name=extName, referenceType=refTp)
            if lang:
                compMdl.error("oimte:referenceLanguageRedefined",
                          _("Referencehas both extends and language: %(name)s"),
                          xbrlObject=refObj, name=extName)
        validateProperties(compMdl, oimFile, module, refObj)
        refsDup[name].append(refObj)
    if refsWithInvalidRelName:
        compMdl.error("oimte:invalidQNameReference",
                  _("References have invalid related object names %(relNames)s"),
                  xbrlObject=refsWithInvalidRelName, name=name, relNames=", ".join(str(qn) for qn in refInvalidNames))
    for name, refsDups in refsDup.items():
        if len(refsDups) > 1:
            compMdl.error("oimte:duplicateObjects",
                          _("The referenceType %(name)s is duplicated."),
                          xbrlObject=refsDups, name=name)
    del refsWithInvalidRelName, refInvalidNames, refsDup # dereference

    # LabelType Objects
    lblTpCt = {}
    for lblObj in module.labelTypes or ():
        assertObjectType(compMdl, lblObj, XbrlLabelType)
        dataTypeObj = validateQNameReference(compMdl, lblObj, "dataType", (XbrlDataType, XbrlCollectionType),
                                             invalidTypeMsgCode="oimte:invalidObjectType")
        if lblObj.allowedObjects is not None:
            if not lblObj.allowedObjects:
                compMdl.error("oimte:invalidEmptySet",
                          _("The labelType %(name)s allowedObjects MUST not be empty."),
                          xbrlObject=lblObj, name=lblObj.name)
            else:
                for allowedObj in lblObj.allowedObjects:
                    if allowedObj not in xbrlObjectTypes:
                        compMdl.error("oimte:invalidAllowedObject",
                                  _("The labelType %(name)s allowedObject %(allowedObject)s MUST be a taxonomy model object."),
                                  xbrlObject=lblObj, name=lblObj.name, allowedObject=allowedObj)

    # ReferenceType Objects
    refTpCt = {}
    for refObj in module.referenceTypes or ():
        assertObjectType(compMdl, refObj, XbrlReferenceType)
        for allowedObj in (refObj.allowedObjects or ()):
            if allowedObj not in referencableObjectTypes:
                compMdl.error("oimte:invalidAllowedObject",
                          _("The referenceType %(name)s allowedObject %(allowedObject)s MUST be a referenceable taxonomy model object."),
                          xbrlObject=refObj, name=refObj.name, allowedObject=allowedObj)
        for prop, msgCode in (("orderedProperties","oimte:invalidOrderedProperty"),
                              ("requiredProperties","oimte:invalidRequiredProperty")):
            for propTpQn in getattr(refObj, prop) or ():
                propTpObj = compMdl.namedObjects.get(propTpQn)
                if not isinstance(propTpObj, XbrlPropertyType):
                    compMdl.error("oimte:invalidQNameReference",
                              _("The referenceType %(name)s %(property)s has an unresolvable propertyType reference %(propType)s"),
                              xbrlObject=refObj, name=refObj.name, property=prop, propType=propTpQn)
                elif propTpObj.allowedObjects and qnXbrlReferenceObj not in propTpObj.allowedObjects:
                    compMdl.error(msgCode,
                              _("The relationshipType %(name)s %(property)s has a propertyType not usable on reference objects %(propType)s"),
                              xbrlObject=refObj, name=refObj.name, property=prop, propType=propTpQn)

    # Unit Objects
    for unitObj in module.units or ():
        assertObjectType(compMdl, unitObj, XbrlUnit)
        name = unitObj.name
        dtQn = getattr(unitObj, "dataType", None)
        if dtQn:
            dtObj = validateQNameReference(compMdl, unitObj, "dataType", XbrlDataType,
                                           msgCode="oimte:invalidUnitDataType", qnRef=dtQn)
            if dtObj is not None:
                if dtObj.allowedObjects and qnXbrlUnitObj not in dtObj.allowedObjects:
                    compMdl.error("oimte:disallowedObjectDataType",
                                  _("The unit %(name)s is not allowed for dataType %(dataType)s."),
                              xbrlObject=unitObj, name=unitObj.name, dataType=dtQn)
                if not dtObj.isNumeric(compMdl):
                    compMdl.error("oimte:invalidUnitDataType",
                                  _("The unit %(name)s dataType %(dataType)s MUST be a numeric data type."),
                                  xbrlObject=unitObj, name=unitObj.name, dataType=dtQn)
            if dtQn.namespaceURI == "http://www.w3.org/2001/XMLSchema":
                compMdl.error("oimte:invalidUnitDataType",
                              _("The unit %(name)s dataType %(dataType)s MUST NOT be defined in the xs schema namespace."),
                              xbrlObject=unitObj, name=unitObj.name, dataType=dtQn)

        unitObj._unitsMeasures = [parseUnitString(uStr, unitObj, module, compMdl) for uStr in unitObj.compositeUnitRepresentation or ()]
        for uMeas in unitObj._unitsMeasures:
            if any(m == name for md in uMeas for m in md):
                compMdl.error("oimte:unitDataTypeUsedInDefinition",
                          _("The unit %(name)s must not contain itself as a measure."),
                          xbrlObject=unitObj, name=unitObj.name)
            for md in uMeas:
                for m in md:
                    if m not in compMdl.namedObjects:
                        # a measure in a compositeUnitRepresentation string that resolves to no defined
                        # unit is an invalid unit string representation (not a bare QName reference)
                        compMdl.error("oimce:invalidUnitStringRepresentation",
                                  _("The unit %(name)s measure %(measure)s must exist in the taxonomy model."),
                                  xbrlObject=unitObj, name=unitObj.name, measure=m)

    # ModelType Objects
    for mdlTpObj in module.modelTypes or ():
        assertObjectType(compMdl, mdlTpObj, XbrlModelType)
        for allowedObjQn in (mdlTpObj.allowedObjects or ()):
            if allowedObjQn not in xbrlObjectTypes:
                compMdl.error("oimte:invalidAllowedObject",
                          _("The modelType %(name)s has an invalid allowed object %(allowedObj)s"),
                          xbrlObject=mdlTpObj, name=mdlTpObj.name, allowedObj=allowedObjQn)
        for i, reqPropQn in enumerate(mdlTpObj.requiredProperties or ()):
            validateQNameReference(compMdl, mdlTpObj, f"requiredProperties[{i+1}]", XbrlPropertyType, qnDefault=reqPropQn)

    # Materialize facts (and footnotes) from factSources referencing a built-in
    # fact map (xbrl:xBRL-XML, xbrl:OIM-JSON), registering them on the module so
    # they flow through the resolveFact / cube / vector-search passes below.
    if module.factSources:
        from .FactPipeline import materializeFactSourceFacts
        materializeFactSourceFacts(compMdl, module)

    # Facts in taxonomy
    if module.facts:
        global resolveFact, validateFactPosition
        if resolveFact is None:
            from .ValidateFacts import resolveFact, validateFactPosition
        for factPosition in module.facts:
            resolveFact(compMdl, module, factPosition)

    # concept-refDimension foreign-key / reference-dimension validation (needs resolved fact dimensions)
    validateRefDimensions(compMdl, module)
    validateFactQualifiers(compMdl, module)

    # Layouts in XbrlModel
    for layout in module.layouts or ():
        assertObjectType(compMdl, layout, XbrlLayout)

        layoutDataTables = layout.dataTables or ()
        # oimte:inconsistentTableTypes — every dataTable in a layout MUST share a tableType
        tableTypes = {dt.tableType for dt in layoutDataTables if getattr(dt, "tableType", None)}
        if len(tableTypes) > 1:
            compMdl.error("oimte:inconsistentTableTypes",
                _("Layout %(name)s mixes data table types (%(types)s); all dataTable objects in a layout MUST have the same tableType."),
                xbrlObject=layout, name=layout.name, types=", ".join(sorted(tableTypes)))

        for dataTbl in layoutDataTables:
            assertObjectType(compMdl, dataTbl, XbrlDataTable)
            tableType = getattr(dataTbl, "tableType", None)

            axes = [("xAxis", dataTbl.xAxis), ("yAxis", dataTbl.yAxis)]
            if dataTbl.zAxis is not None:
                axes.append(("zAxis", dataTbl.zAxis))
            for axisName, axis in axes:
                assertObjectType(compMdl, axis, XbrlAxis)
                gridHeaders = getattr(axis, "gridHeaders", None)
                axisHeaders = getattr(axis, "axisHeaders", None)
                gridAxis = getattr(axis, "gridAxis", None)

                # oimte:invalidGridAxisTableType — gridHeaders only in a gridLayout table
                if gridHeaders and tableType != "gridLayout":
                    compMdl.error("oimte:invalidGridAxisTableType",
                        _("Data table %(name)s %(axis)s uses a gridHeader but its tableType is %(tableType)s; a gridHeader MUST only be used with a gridLayout table."),
                        xbrlObject=dataTbl, name=dataTbl.name, axis=axisName, tableType=tableType)

                # gridHeader and axisHeader MUST NOT both be defined on one axis
                # (oim-taxonomy §Grid header object constraints).  The spec states this MUST
                # but assigns no oimte code — oimte:gridHeaderWithAxisHeader is proposed.
                if gridHeaders and axisHeaders:
                    compMdl.error("oimte:gridHeaderWithAxisHeader",
                        _("Data table %(name)s %(axis)s defines both gridHeaders and axisHeaders; a gridHeader MUST NOT be defined on an axis that also defines an axisHeader."),
                        xbrlObject=dataTbl, name=dataTbl.name, axis=axisName)

                # NB: "an axis MUST specify either axisHeaders or gridAxis" (oim-taxonomy §Axis
                # object constraints) is already enforced by the JSON schema (an axis with
                # neither fails the schema anyOf → oime:invalidJSONStructure), so no separate
                # semantic check is added here.

                for gh in gridHeaders or ():
                    span = getattr(gh, "span", 1)
                    labelLevel = getattr(gh, "labelLevel", None)
                    # oimte:invalidGridHeaderSpan — span MUST be a positive integer
                    if isinstance(span, int) and span < 1:
                        compMdl.error("oimte:invalidGridHeaderSpan",
                            _("Data table %(name)s %(axis)s gridHeader span %(span)s MUST be a positive integer."),
                            xbrlObject=dataTbl, name=dataTbl.name, axis=axisName, span=span)
                    # oimte:invalidGridHeaderSpanLevel — span MUST NOT be defined at labelLevel 1.
                    # span defaults to 1 (indistinguishable from an explicit 1), so the detectable
                    # and meaningful violation is a spanning (>1) header at level 1.
                    if labelLevel == 1 and isinstance(span, int) and span > 1:
                        compMdl.error("oimte:invalidGridHeaderSpanLevel",
                            _("Data table %(name)s %(axis)s gridHeader spans %(span)s at labelLevel 1; a span MUST NOT be defined where labelLevel is 1."),
                            xbrlObject=dataTbl, name=dataTbl.name, axis=axisName, span=span)

                # oimte:conflictingAxisLabelSources — axisLabelsGroup valueArray and range are exclusive
                alg = getattr(axis, "axisLabelsGroup", None)
                if alg is not None and getattr(alg, "valueArray", None) and getattr(alg, "range", None):
                    compMdl.error("oimte:conflictingAxisLabelSources",
                        _("Data table %(name)s %(axis)s axisLabelsGroup defines both valueArray and range; these are mutually exclusive."),
                        xbrlObject=dataTbl, name=dataTbl.name, axis=axisName)

            # tablePoint constraints (gridLayout explicit-cell positioning)
            for tp in getattr(dataTbl, "tablePoints", None) or ():
                gc = getattr(tp, "gridCoordinates", None)
                # oimte:missingGridCoordinates — at least xAxis and yAxis
                if gc is None or getattr(gc, "xAxis", None) is None or getattr(gc, "yAxis", None) is None:
                    compMdl.error("oimte:missingGridCoordinates",
                        _("Data table %(name)s tablePoint gridCoordinates MUST specify at least xAxis and yAxis."),
                        xbrlObject=dataTbl, name=dataTbl.name)
                # oimte:invalidDimensionInTablePoint — each dimension QName MUST be a model dimension
                for dimQn in (getattr(tp, "dimensions", None) or {}):
                    if dimQn not in coreDimensions and not isinstance(compMdl.namedObjects.get(dimQn), XbrlDimension):
                        compMdl.error("oimte:invalidDimensionInTablePoint",
                            _("Data table %(name)s tablePoint references %(dim)s which is not a dimension defined in the model."),
                            xbrlObject=dataTbl, name=dataTbl.name, dim=dimQn)

    for tblTmpl in module.tableTemplates or ():
        assertObjectType(compMdl, tblTmpl, XbrlTableTemplate)

        if tblTmpl.extends is not None:
            extTmpl = compMdl.namedObjects.get(tblTmpl.extends)
            if isinstance(extTmpl, XbrlTableTemplate) and not getattr(extTmpl, "isExtensible", True):
                compMdl.error("oimte:illegalExtensionOfNonExtensibleObject",
                          _("The tableTemplate cannot extend %(target)s because it is non-extensible."),
                          xbrlObject=tblTmpl, target=extTmpl.name)

        # columnName MUST be a valid NCName and MUST NOT contain the '.' character (oim-taxonomy §columnName)
        cols = getattr(tblTmpl, "columns", None)
        for col in (cols.values() if isinstance(cols, dict) else (cols or ())):
            colName = col.get("columnName") if isinstance(col, dict) else getattr(col, "columnName", None)
            if colName and "." in str(colName):
                compMdl.error("oimte:invalidColumnName",
                          _("The tableTemplate %(name)s columnName %(columnName)s MUST be a valid NCName and MUST NOT contain the '.' character."),
                          xbrlObject=tblTmpl, name=getattr(tblTmpl, "name", None), columnName=colName)

        for dim in tblTmpl.factDimensions:
            if dim.localName.startswith('$'):
                colName = dim[1:]
                if colName not in tblTmpl.columns:
                    compMdl.error("oimte:tableTemplateDimensionColumnReference",
                              _("The table template dimension %(dimension)s is missing from the table template columns."),
                              xbrlObject=tblTmpl, dimension=dim)

    # Group tree object: taxonomy-group relationship source may be an XBRL Model object or a group
    # object; the target MUST be a group object (oim-taxonomy §group tree object).
    # The group tree object is NOT imported (oim-taxonomy §group tree object), so an imported module's
    # groupTree targets may be pruned/remapped and resolve to None here — only flag a source/target that
    # actually resolves to a wrong-type object, not one that is simply unresolved.
    if module.groupTree is not None:
        for rel in getattr(module.groupTree, "relationships", None) or ():
            srcObj = compMdl.namedObjects.get(rel.source)
            if (srcObj is not None and not isinstance(srcObj, (XbrlGroup, XbrlModule))
                    and rel.source != module.name):
                compMdl.error("oimte:invalidTaxonomyGroupSource",
                          _("The groupTree relationship source %(source)s MUST be an XBRL Model object or a group object."),
                          xbrlObject=module.groupTree, source=rel.source)
            tgtObj = compMdl.namedObjects.get(rel.target)
            if tgtObj is not None and not isinstance(tgtObj, XbrlGroup):
                compMdl.error("oimte:invalidTaxonomyGroupTarget",
                          _("The groupTree relationship target %(target)s MUST reference a group object."),
                          xbrlObject=module.groupTree, target=rel.target)

    # A factSource's factIdentifierNamespacePrefix, and any namespaceMap from/toNamespacePrefix, MUST be a
    # namespace prefix declared in documentInfo.namespaces (oim-taxonomy §factSource / namespaceMap), else
    # oimce:unboundPrefix.
    declaredPrefixes = set(getattr(module, "_prefixNamespaces", {}).keys())
    declaredPrefixes.update(
        str(getattr(np, "prefix", None))
        for np in (module.namespacePrefixes or ())
        if getattr(np, "prefix", None) is not None
    )
    def _checkFactSourcePrefix(obj, prefix, propName, srcName):
        if prefix is not None and prefix not in declaredPrefixes:
            compMdl.error("oimce:unboundPrefix",
                          _("The factSource %(name)s %(prop)s '%(prefix)s' is not a namespace prefix declared in documentInfo.namespaces."),
                          xbrlObject=obj, name=srcName, prop=propName, prefix=prefix)
    for factSrc in module.factSources or ():
        assertObjectType(compMdl, factSrc, XbrlFactSource)
        srcName = getattr(factSrc, "name", None)
        _checkFactSourcePrefix(factSrc, getattr(factSrc, "factIdentifierNamespacePrefix", None), "factIdentifierNamespacePrefix", srcName)
        for nsMap in getattr(factSrc, "namespaceMaps", None) or ():
            _checkFactSourcePrefix(nsMap, getattr(nsMap, "fromNamespacePrefix", None), "fromNamespacePrefix", srcName)
            _checkFactSourcePrefix(nsMap, getattr(nsMap, "toNamespacePrefix", None), "toNamespacePrefix", srcName)

def validateCompletedModel(compMdl):
    """ Validate the completed model, including validating facts and complete cubes.
        This should be called after all models have been loaded and all references resolved.
    """
    from .FactPipeline import FactSink, iterModuleFacts

    # Facts in taxonomy
    if any(module.facts for module in compMdl.xbrlModels.values()):

        # build search vocabulary to support cube construction (after date resolution concepts validated)
        from .VectorSearch import buildXbrlVectors, searchXbrl, searchXbrlBatchTopk, SEARCH_CUBES, SEARCH_FACTPOSITIONS, SEARCH_BOTH
        buildXbrlVectors(compMdl)

        global resolveFact, validateFactPosition
        if resolveFact is None:
            from .ValidateFacts import resolveFact, validateFactPosition

        dateResolutionQuery = [(conceptCoreDim, qn) for qn in compMdl.dateResolutionConceptNames]

        if dateResolutionQuery:

            try:
                results = searchXbrl(compMdl, dateResolutionQuery, SEARCH_FACTPOSITIONS, 5 * len(dateResolutionQuery)) # allow sufficient return scores
            except ValueError:
                # None of the queryAspects exist in the model's vector store; fall back to validating all facts
                results = []
            # print(f"first search item {dtResQuery[0]} results {[(r[0],r[1].name) for r in results]}")

            # validate factPosition objects whose scores indicates they represent dateResolution concepts first
            compMdl.dateResolutionConceptFacts = defaultdict(list)
            for score, f in results:
                if score < 0.2:  # arbitrary, what should this be?
                    break
                if isinstance(f, XbrlFact):
                    conceptQn = f.factDimensions.get(conceptCoreDim)
                    if conceptQn in compMdl.dateResolutionConceptNames:
                        validateFactPosition(compMdl, f)
                        compMdl.dateResolutionConceptFacts[conceptQn].append(f)

            # validate remaining facts through the streaming sink, skipping the date-resolution concepts
            sink = FactSink(compMdl, resolveFact, validateFactPosition,
                            skipConcepts=set(compMdl.dateResolutionConceptNames))
            for f in iterModuleFacts(compMdl):
                sink.accept(f)
        else:
            # validate all facts through the streaming sink
            sink = FactSink(compMdl, resolveFact, validateFactPosition)
            for f in iterModuleFacts(compMdl):
                sink.accept(f)

    # Cube completeness and duplicate-fact validation are handled by
    # validateCompleteReportCubes(), called after vector search is built.
