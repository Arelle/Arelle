'''
See COPYRIGHT.md for copyright information.
'''

import regex as re
from collections import defaultdict
from arelle.ModelValue import QName, timeInterval
from arelle.XmlValidate import languagePattern, validateValue as validateXmlValue,\
    INVALID, VALID
from arelle.PythonUtil import attrdict, OrderedSet
from arelle.oim.Load import EMPTY_DICT, csvPeriod
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlConst import xbrl
from .XbrlCube import (XbrlCube, XbrlCubeType, baseCubeTypes, XbrlCubeDimension,
                       periodCoreDim, conceptCoreDim, entityCoreDim, unitCoreDim, languageCoreDim, coreDimensions,
                    conceptDomainRoot, entityDomainRoot, unitDomainRoot, languageDomainRoot,
                    defaultCubeType, reportCubeType)
from .XbrlDimension import XbrlDimension, XbrlDomain, XbrlDomainRoot, XbrlMember
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent
from .XbrlImportTaxonomy import XbrlImportTaxonomy
from .XbrlLabel import XbrlLabel, XbrlLabelType, preferredLabel
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlTableTemplate import XbrlTableTemplate
from .XbrlTaxonomyModule import XbrlTaxonomyModule, xbrlObjectTypes, xbrlObjectQNames
from .XbrlUnit import XbrlUnit, parseUnitString
from .XbrlConst import qnXsQName, qnXsDate, qnXsDateTime, qnXsDuration, objectsWithProperties
from numpy._core._simd import targets
validateFact = None
from arelle.FunctionFn import true

perCnstrtFmtStartEndPattern = re.compile(r".*@(start|end)")

def validateTaxonomyModel(txmyMdl):

    for txmy in txmyMdl.taxonomies.values():
        validateTaxonomy(txmyMdl, txmy)

def objType(obj):
    clsName = type(obj).__name__
    if clsName.startswith("Xbrl"):
        return clsName[4:]
    return clsName

def validateValue(txmyMdl, txmy, obj, value, dataTypeQn, pathElt, msgCode):
    if isinstance(dataTypeQn, QName):
        dataTypeObj = txmyMdl.namedObjects.get(dataTypeQn)
        if not isinstance(dataTypeObj, XbrlDataType): # validity checked in owner object validations
            return
        dataTypeLn = dataTypeObj.xsBaseType(txmyMdl)
        facets = dataTypeObj.xsFacets()
    elif isinstance(dataTypeQn, XbrlDataType):
        dataTypeLn = dataTypeQn.xsBaseType(txmyMdl)
        facets = dataTypeQn.xsFacets()
    else: # string data type
        dataTypeLn = dataTypeQn
        facets = EMPTY_DICT
    prototypeElt = attrdict(elementQname=dataTypeQn,
                            entryLoadingUrl=obj.entryLoadingUrl + pathElt,
                            nsmap=txmy._prefixNamespaces)
    if not isinstance(value, str): # HF - is this right?  xml value validation can only work on string input
        value = str(value)
    validateXmlValue(txmyMdl, prototypeElt, None, dataTypeLn, value, False, False, facets, msgCode)
    return (prototypeElt.xValid, prototypeElt.xValue)

def reqRelMatch(relQn, reqQn, txmyMdl):
    if relQn == reqQn:
        return True
    concept = txmyMdl.namedObjects.get(relQn)
    if isinstance(concept, XbrlConcept):
        if concept.dataType == reqQn:
            return True
    return False

def validateProperties(txmyMdl, oimFile, txmy, obj):
    propTypeQns = {}
    for i, propObj in enumerate(getattr(obj, "properties", ())):
        propTypeQn = propObj.property
        propTypeObj = txmyMdl.namedObjects.get(propTypeQn)
        if not isinstance(propTypeObj, XbrlPropertyType):
            # identify parent object
            if hasattr(obj, "name"):
                parentName = obj.name
            elif hasattr(obj, "source") and hasattr(obj, "target"): # relationship
                parentName = f"{obj.source}\u2192{obj.target}"
            else:
                parentName = ""
            txmyMdl.error("oimte:missingQNameReference",
                      _("%(parentObjName)s %(parentName)s property %(name)s has undefined dataType %(dataType)s"),
                      file=oimFile, parentObjName=objType(obj), parentName=parentName,
                      name=propTypeQn, dataType=propTypeQn)
        else: # have property type object
            if propTypeObj.allowedObjects:
                if xbrlObjectQNames.get(type(obj)) not in propTypeObj.allowedObjects:
                    txmyMdl.error("oimte:invalidObjectProperty",
                              _("%(parentObjName)s %(parentName)s property %(name)s not an allowed property type for the object."),
                              file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                              name=propTypeQn)
            propObj._xValid, propObj._xValue = validateValue(txmyMdl, txmy, obj, propObj.value, propTypeObj.dataType, f"/properties[{i}]", "oimte:invalidPropertyValue")
            
        propTypeQns[propTypeQn] = propTypeQns.get(propTypeQn, 0) + 1
    if any(ct > 1 for qn, ct in propTypeQns.items()):
        txmyMdl.error("oimte:duplicateObjects",
                  _("%(parentObjName)s %(parentName)s has duplicated properties %(names)s"),
                  file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                  names=", ".join(str(qn) for qn, ct in propTypeQns.items() if ct > 1))
            

def validateTaxonomy(txmyMdl, txmy):
    oimFile = str(txmy.name)

    def assertObjectType(obj, objType):
        if not isinstance(obj, objType):
            txmyMdl.error("oimte:invalidObjectType",
                      _("This %(thisType)s object was included where an %(expectedType)s object was expected."),
                      xbrlObject=obj, thisType=obj.__class__.__name__, expectedType=objType.__name__)

    # Taxonomy object
    assertObjectType(txmy, XbrlTaxonomyModule)

    for impTxmyObj in txmy.importedTaxonomies:
        assertObjectType(impTxmyObj, XbrlImportTaxonomy)
        for qnObjType in impTxmyObj.importObjectTypes:
            if qnObjType in xbrlObjectTypes:
                if xbrlObjectTypes[qnObjType] == XbrlLabel:
                    txmyMdl.error("oimte:invalidObjectType",
                              _("The importObjectTypes property MUST not include the label object."),
                              xbrlObject=qnObjType)
            else:
                txmyMdl.error("oimte:invalidObjectType",
                          _("The importObjectTypes property MUST specify valid OIM object types, %(qname)s is not valid."),
                          xbrlObject=qnObjType, qname=qnObjType)

    # Concept Objects
    for cncpt in txmy.concepts:
        assertObjectType(cncpt, XbrlConcept)
        perType = getattr(cncpt, "periodType", None)
        if perType not in ("instant", "duration", "none"):
            txmyMdl.error("oime:invalidPropertyValue",
                      _("Concept %(name)s has invalid period type %(perType)s"),
                      xbrlObject=cncpt, name=cncpt.name, perType=perType)
        dataTypeQn = getattr(cncpt, "dataType", None)
        if dataTypeQn not in txmyMdl.namedObjects or not isinstance(txmyMdl.namedObjects[dataTypeQn], XbrlDataType):
            txmyMdl.error("oimte:unknownDataType",
                      _("Concept %(name)s has invalid dataType %(dataType)s"),
                      xbrlObject=cncpt, name=cncpt.name, dataType=dataTypeQn)
        enumDomQn = getattr(cncpt, "enumerationDomain", None)
        if enumDomQn and (enumDomQn not in txmyMdl.namedObjects or not isinstance(txmyMdl.namedObjects[enumDomQn], XbrlDomain)):
            txmyMdl.error("oime:invalidEnumerationDomainObject",
                      _("Concept %(name)s has invalid enumeration domain reference %(enumDomain)s"),
                      xbrlObject=cncpt, name=cncpt.name, enumDomain=enumDomQn)
        validateProperties(txmyMdl, oimFile, txmy, cncpt)

    # CubeType Objects
    for cubeType in txmy.cubeTypes:
        assertObjectType(cubeType, XbrlCubeType)
        name = cubeType.name
        allowedCubeDims = cubeType.effectivePropVal("allowedCubeDimensions", txmyMdl) # gets inherited property
        _derivedAlwdDims = cubeType.allowedCubeDimensions # gets this cubeType property
        if _derivedAlwdDims and _derivedAlwdDims != allowedCubeDims:
            txmyMdl.error("oimte:cubeTypeAllowedDimensionsConflict",
                      _("The cubeType %(name)s, must not specify allowedCubeDimensions overriding base cue allowedCubeDimensions"),
                      xbrlObject=cubeType, name=name)
        if allowedCubeDims is not None:
            if not allowedCubeDims:
                txmyMdl.error("oimte:invalidEmptySet",
                          _("The cube %(name)s, type %(cubeType)s, allowedCubeDimensions must not be empty"),
                          xbrlObject=cubeType, name=name, cubeType=cubeType.name)
            elif not cubeType.effectivePropVal("taxonomyDefinedDimension", txmyMdl):
                txmyMdl.error("oimte:cubeTypeAllowedDimensionsConflict",
                          _("The cube %(name)s, type %(cubeType)s, must not specify allowedCubeDimensions if the cube does not permit taxonomyDefinedDimensions"),
                          xbrlObject=cubeType, name=name, cubeType=cubeType.name)
            for i, allwdDim in enumerate(allowedCubeDims):
                _dimName = allwdDim.dimensionName
                _dimType = allwdDim.dimensionType
                _typedDimType = allwdDim.dimensionDataType
                if not _dimName and not _dimType and not_typedDimType:
                    txmyMdl.error("oimte:cubeTypeAllowedDimensionProperties",
                              _("The cube type %(name)s, allowedCubeDimension[%(i)s] object must specify one of dimensionName, dimensionType or dimensionDataType."),
                              xbrlObject=cubeType, name=name, i=i, dimName=_dimName)
                if _dimName and not isinstance(txmyMdl.namedObjects.get(_dimName), XbrlDimension):
                    txmyMdl.error("oimte:cubeTypeAllowedDimensionName",
                              _("The cube type %(name)s, allowedCubeDimension[%(i)s] dimensionName %(dimName)s does not resolve to a dimension object."),
                              xbrlObject=cubeType, name=name, i=i, dimName=_dimName)
                if _dimType not in (None, "typed", "explicit"):
                    txmyMdl.error("oimte:cubeTypeAllowedDimensionType",
                              _("The cube type %(name)s, allowedCubeDimension[%(i)s] dimensionType %(dimType)s is invalid."),
                              xbrlObject=cubeType, name=name, i=i, dimType=_dimType)
                if _typedDimType and not isinstance(txmyMdl.namedObjects.get(_typedDimType), XbrlDataType):
                    txmyMdl.error("oimte:cubeTypeAllowedDimensionDataType",
                              _("The cube type %(name)s, allowedCubeDimension dimensionDataType %(typedDimType)s does not resolve to a dataType object."),
                              xbrlObject=cubeType, name=name, i=i, typedDimType=_typedDimType)
        for i, reqdRelshp in enumerate(getattr(cubeType, "requiredCubeRelationships", ())):
            relType = getattr(reqdRelshp, "relationshipTypeName", None)
            if not isinstance(txmyMdl.namedObjects.get(relType), XbrlRelationshipType):
                txmyMdl.error("oimte:cubeTypeRequiredRelationshipType",
                          _("The cube type %(name)s, requiredCubeRelationship[%(i)s] relationshipTypeName %(relTypeName)s does not resolve to a relationshipType object."),
                          xbrlObject=cubeType, name=name, i=i, relTypeName=relType)

    # Cube Objects
    for cubeObj in txmy.cubes:
        assertObjectType(cubeObj, XbrlCube)
        name = cubeObj.name
        ntwks = set()
        for ntwrkQn in cubeObj.cubeNetworks:
            ntwk = txmyMdl.namedObjects.get(ntwrkQn)
            if ntwk is None:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s an object in the model."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            elif not isinstance(ntwk, XbrlNetwork):
                txmyMdl.error("oimte:invalidCubeNetwork",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s to a network object."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            else:
                 ntwks.add(ntwk)
        dimQnCounts = {}
        for allowedCubeDimObj in cubeObj.cubeDimensions:
            dimQn = allowedCubeDimObj.dimensionName
            if dimQn not in coreDimensions and not isinstance(txmyMdl.namedObjects.get(dimQn), XbrlDimension):
                txmyMdl.error("oimte:invalidTaxonomyDefinedDimension",
                          _("The allowedCubeDimensions property on cube %(name)s MUST resolve to a dimension object: %(dimension)s"),
                          xbrlObject=cubeObj, name=name, dimension=dimQn)
            dimQnCounts[dimQn] = dimQnCounts.get(dimQn, 0) + 1
        if any(c > 1 for c in dimQnCounts.values()):
            txmyMdl.error("oimte:duplicateObjects",
                      _("The cubeDimensions of cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      xbrlObject=cubeObj, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items() if ct > 1))
        # check cube dims against cube type
        cubeType = txmyMdl.namedObjects.get(cubeObj.cubeType or reportCubeType)
        if not isinstance(cubeType, XbrlCubeType):
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The cube %(name)s  cubeType %(qname)s must be a valid cube type."),
                      xbrlObject=cubeObj, name=name, qname=cubeType)
        else:
            if cubeType.basemostCubeType != defaultCubeType and conceptCoreDim not in dimQnCounts.keys():
                txmyMdl.error("oimte:cubeMissingDimension",
                          _("The cubeDimensions of cube %(name)s, type %(cubeType)s, must have a concept core dimension"),
                          xbrlObject=cubeObj, name=name, cubeType=cubeType.name)
            for prop, coreDim in (("periodDimension", periodCoreDim),
                                  ("entityDimension", entityCoreDim),
                                  ("unitDimension", unitCoreDim)):
                if not cubeType.effectivePropVal(prop, txmyMdl) and coreDim in dimQnCounts.keys():
                    txmyMdl.error("oimte:cubeDimensionNotAllowed",
                              _("The cube %(name)s, type %(cubeType)s, dimension %(dimension)s is not allowed"),
                              xbrlObject=cubeObj, name=name, cubeType=cubeType.name, dimension=coreDim)
            allowedCubeDims = cubeType.effectivePropVal("allowedCubeDimensions", txmyMdl)
            txmyDefDimsQNs = set(dim for dim in dimQnCounts.keys() if dim.namespaceURI != xbrl)
            if not cubeType.effectivePropVal("taxonomyDefinedDimension", txmyMdl):
                if txmyDefDimsQNs:
                    txmyMdl.error("oimte:cubeDimensionNotAllowed",
                              _("The cube %(name)s, type %(cubeType)s, taxonomy defined dimensions %(dimension)s are not allowed"),
                              xbrlObject=cubeObj, name=name, cubeType=cubeType.name, dimension=", ".join(sorted(str(d) for d in txmyDefDimsQNs)))
            elif allowedCubeDims is not None: # absent allows any dimensions
                txmyDefDims = set()
                for dimQn in txmyDefDimsQNs:
                    dim = txmyMdl.namedObjects.get(dimQn)
                    if isinstance(dim, XbrlDimension):
                        txmyDefDims.add(dim)
                matchedDimQNs = set()
                for allwdDim in allowedCubeDims:
                    matchedDim = None
                    for dim in txmyDefDims:
                        if ((not allwdDim.dimensionName or dim.name == allwdDim.dimensionName) and
                            (not allwdDim.dimensionType or dim.dimensionType == allwdDim.dimensionType) and
                            (not allwdDim.dimensionDataType or dim.domainDataType == allwdDim.dimensionDataType)):
                            matchedDim = dim
                            matchedDimQNs.add(dim.name)
                            break
                    if not matchedDim and allwdDim.required:
                        txmyMdl.error("oimte:cubeMissingDimension",
                                  _("The cube %(name)s, type %(cubeType)s, taxonomy defined dimensions %(dimension)s is missing"),
                                  xbrlObject=cubeObj, name=name, cubeType=cubeType.name,
                                  dimension=','.join(str(getattr(allwdDim,p)) for p in ("dimensionName", "dimensionType", "dimensionDataType") if getattr(allwdDim,p)))
                disallowedDims = txmyDefDimsQNs - matchedDimQNs
                if disallowedDims:
                    txmyMdl.error("oimte:cubeDimensionNotAllowed",
                              _("The cube %(name)s, type %(cubeType)s allowedDimensions do not allow dimension(s) %(dimension)s"),
                              xbrlObject=cubeObj, name=name, cubeType=cubeType.name, dimension=", ".join(str(d) for d in disallowedDims))
            for reqRel in cubeType.effectivePropVal("requiredCubeRelationships", txmyMdl):
                reqRelSatisfied = False
                for ntwk in ntwks:
                    if (ntwk.relationshipTypeName == reqRel.relationshipTypeName and
                        any(((not reqRel.source or reqRelMatch(r.source, reqRel.source, txmyMdl)) and
                             (not reqRel.target or reqRelMatch(r.target, reqRel.target, txmyMdl)))
                            for r in ntwk.relationships)):
                        reqRelSatisfied = True
                        break
                if not reqRelSatisfied:
                    reqRelStr = f"{reqRel.relationshipTypeName}"
                    if reqRel.source: reqRelStr += f" source {reqRel.source}"
                    if reqRel.target: reqRelStr += f" target {reqRel.target}"
                    txmyMdl.error("oimte:cubeMissingRelationships",
                              _("The cube %(name)s, type %(cubeType)s, requiredCubeRelationships %(reqRel)s is missing"),
                              xbrlObject=cubeObj, name=name, cubeType=cubeType.name, reqRel=reqRelStr)

        for exclCubeQn in cubeObj.excludeCubes:
            if exclCubeQn == cubeObj.name:
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The cube %(name)s must not be defined in the excludeCubes property of itself."),
                          xbrlObject=cubeObj, name=name)
            if not isinstance(txmyMdl.namedObjects.get(exclCubeQn), XbrlCube):
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The excludeCubes property on cube %(name)s MUST resolve %(qname)s to a cube object."),
                          xbrlObject=cubeObj, name=name, qname=exclCubeQn)
        validateProperties(txmyMdl, oimFile, txmy, cubeObj)
        unitDataTypeQNs = set()
        cncptDataTypeQNs = set()
        for iCubeDim, cubeDimObj in enumerate(cubeObj.cubeDimensions):
            assertObjectType(cubeDimObj, XbrlCubeDimension)
            dimName = cubeDimObj.dimensionName
            dimObj = txmyMdl.namedObjects[dimName]
            isTyped = False
            if isinstance(dimObj, XbrlDimension):
                isTyped = dimObj.domainDataType is not None
            else:
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("Cube %(name)s dimensionName property MUST be a dimension object %(dimensionName)s."),
                          xbrlObject=cubeObj, name=name, dimensionName=dimName)
                continue # not worth going further with this cube dimension
            hasValidDomainName = False
            if cubeDimObj.typedSort not in (None, "asc", "desc"):
                txmyMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s typedSort property MUST be asc or desc, not %(typedSort)s."),
                          xbrlObject=cubeObj, name=name, typedSort=cubeDimObj.typedSort)
            if cubeDimObj.domainName:
                if isinstance(txmyMdl.namedObjects.get(cubeDimObj.domainName), XbrlDomain):
                    hasValidDomainName = True
                else:
                    txmyMdl.error("oimte:invalidCubeDimensionDomainName",
                              _("Cube %(name)s domainName property MUST identify a domain object: %(domainName)s."),
                              xbrlObject=cubeObj, name=name, domainName=cubeDimObj.domainName)
            if cubeDimObj.periodConstraints and dimName != periodCoreDim:
                txmyMdl.error("oimte:invalidDimensionConstraint",
                          _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)
            if dimName == conceptCoreDim and hasValidDomainName:
                for relObj in txmyMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(txmyMdl.namedObjects.get(relObj.source,None), (XbrlConcept, XbrlAbstract)) and relObj.source != conceptDomainRoot:
                        txmyMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s conceptConstraints domain relationships must be from concepts, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if isinstance(txmyMdl.namedObjects.get(relObj.target,None), XbrlConcept):
                        cncptDataTypeQNs.add(txmyMdl.namedObjects[relObj.target].dataType)
                    elif not isinstance(txmyMdl.namedObjects.get(relObj.target,None), XbrlAbstract):
                        txmyMdl.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s conceptConstraints domain relationships must be to concepts, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
                if cubeDimObj.allowDomainFacts:
                    txmyMdl.error("oimte:invalidCubeDimensionProperty",
                              _("Cube %(name)s conceptConstraints property MUST NOT specify allowDomainFacts."),
                              xbrlObject=(cubeObj,cubeDimObj), name=name)
            if dimName == entityCoreDim and hasValidDomainName:
                for relObj in txmyMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(txmyMdl.namedObjects.get(relObj.source,None), XbrlEntity) and relObj.source != entityDomainRoot:
                        txmyMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s entityConstraints domain relationships must be from entities, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects.get(relObj.target,None), XbrlEntity):
                        txmyMdl.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s entityConstraints domain relationships must be to entities, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
            if dimName == unitCoreDim and hasValidDomainName:
                for relObj in txmyMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(txmyMdl.namedObjects.get(relObj.source,None), XbrlUnit) and relObj.source != unitDomainRoot:
                        txmyMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s unitConstraints domain relationships must be from units, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects.get(relObj.target,None), XbrlUnit):
                        txmyMdl.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s unitConstraints domain relationships must be to units, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
            if dimName in (periodCoreDim, languageCoreDim) and hasValidDomainName:
                txmyMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s dimension %(qname)s must not specify domain %(domain)s."),
                          xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName, domain=cubeDimObj.domainName)
            if dimName not in coreDimensions and isinstance(txmyMdl.namedObjects.get(dimName), XbrlDimension):
                if isTyped:
                    if dimObj.domainRoot:
                        txmyMdl.error("oimte:invalidQNameReference",
                                  _("Cube %(name)s typed dimension %(qname)s must not specify a domain root."),
                                  xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName)
                    if hasValidDomainName:
                        txmyMdl.error("oimte:invalidCubeDimensionProperty",
                                  _("Cube %(name)s typed dimension %(qname)s must not specify a domain %(domain)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName, domain=cubeDimObj.domainName)
                else: # explicit dim
                    domObj = txmyMdl.namedObjects.get(cubeDimObj.domainName)
                    if isinstance(domObj, XbrlDomain):
                        for relObj in domObj.relationships:
                            if not isinstance(txmyMdl.namedObjects.get(getattr(relObj, "target", None),None), XbrlMember):
                                txmyMdl.error("oimte:invalidRelationshipTarget",
                                          _("Cube %(name)s explicit dimension domain relationships must be to members."),
                                          xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName)
            if not isTyped: # explicit dimension
                if dimName in (periodCoreDim, languageCoreDim):
                    txmyMdl.error("oimte:invalidCubeDimensionProperty",
                              _("Cube %(name)s domainName property MUST NOT be used where the dimensionName property has a QName value %(qname)s."),
                              xbrlObject=cubeObj, name=name, qname=dimName)
                if cubeDimObj.typedSort is not None:
                    txmyMdl.error("oimte:invalidCubeDimensionProperty",
                              _("Cube %(name)s typedSort property MUST not be used on an explicit dimension."),
                              xbrlObject=cubeObj, name=name)
            if dimName == periodCoreDim:
                for iPerConst, perConstObj in enumerate(cubeDimObj.periodConstraints):
                    if perConstObj.periodType not in ("instant", "duration", "none"):
                        txmyMdl.error("oimte:invalidPeriodRepresentation",
                                  _("Cube %(name)s period constraint periodType property MUST be \"instant\" or \"duration\"."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    if perConstObj.timeSpan:
                        if perConstObj.endDate and perConstObj.startDate:
                            txmyMdl.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s period constraint timeSpan property MUST NOT be used with both the endDate and startDate properties."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        perConstObj._timeSpanValid, perConstObj._timeSpanValue = validateValue(txmyMdl, txmy, cubeObj, perConstObj.timeSpan, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/timeSpan", "oimte:invalidPeriodRepresentation")
                    if perConstObj.periodFormat:
                        if perConstObj.timeSpan or perConstObj.endDate or perConstObj.startDate:
                            txmyMdl.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s period constraint periodFormat property MUST NOT be used with the timeSpan, endDate or startDate properties."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        perStr, _sep, perAttr = perConstObj.periodFormat.partition("@")
                        isoPer = csvPeriod(perStr, perAttr)
                        if isoPer is None or isoPer == "referenceTargetNotDuration":
                            txmyMdl.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s periodConstraint[%(perConstNbr)s] periodFormat property, %(periodFormat)s, MUST be a valid period format per xbrl-csv specification."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name, perConstNbr=iPerConst, periodFormat=perConstObj.periodFormat)
                            perConstObj._periodFormatValid = INVALID
                            perConstObj._periodFormatValue = None
                        else:
                            perConstObj._periodFormatValid = VALID
                            perConstObj._periodFormatValue = timeInterval(isoPer)
                    if perConstObj.periodType != "instant" and perConstObj.periodFormat and perCnstrtFmtStartEndPattern.match(perConstObj.periodFormat):
                        txmyMdl.error("oimte:invalidPeriodRepresentation",
                                  _("Cube %(name)s period constraint periodFormat the suffix of @start or @end MUST only be used with periodType of instant."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    if perConstObj.periodType == "instant" and (perConstObj.timeSpan or perConstObj.startDate):
                        txmyMdl.error("oimte:invalidPeriodRepresentation",
                              _("Cube %(name)s period constraint periodType instant MUST NOT define timeSpan or startDate."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    for dtResProp in ("monthDay", "endDate", "startDate", "onOrAfter", "onOrBefore"):
                        dtResObj = getattr(perConstObj, dtResProp, None)
                        if dtResObj is not None:
                            if dtResObj.conceptName:
                                cncpt = txmyMdl.namedObjects.get(dtResObj.conceptName)
                                if not isinstance(cncpt, XbrlConcept) or not isinstance(txmyMdl.namedObjects.get(cncpt.dataType), XbrlDataType) or txmyMdl.namedObjects[cncpt.dataType].baseType not in (qnXsDate, qnXsDateTime):
                                    txmyMdl.error("oimte:invalidObjectType",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a date or dateTime."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                            if dtResObj.context:
                                cncpt = txmyMdl.namedObjects.get(dtResObj.context)
                                if not cncpt or not isinstance(cncpt, XbrlConcept) or (dtResObj.context.atSuffix not in ("start","end")):
                                    txmyMdl.error("oimte:invalidObjectType",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a concept and any suffix MUST be start or end."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                            if dtResObj.timeShift:
                                if dtResObj.value or (dtResObj.conceptName and dtResObj.context):
                                    txmyMdl.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s timeShift MUST be used with only one of the properties name, or context."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                                dtResObj._timeShiftValid, dtResObj._timeShiftValue = validateValue(txmyMdl, txmy, cubeObj, dtResObj.timeShift, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/timeShift", "oimte:invalidPeriodRepresentation")
                            if dtResObj.value:
                                dtResObj._valueValid, dtResObj._valueValue = validateValue(txmyMdl, txmy, cubeObj, dtResObj.value, "XBRLI_DATEUNION", f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/value", "oimte:invalidPeriodRepresentation")

            else:
                if cubeDimObj.periodConstraints:
                    txmyMdl.error("oimte:invalidDimensionConstraint",
                              _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                              xbrlObject=cubeObj, name=name, qname=dimName)
        for unitDataTypeQN in unitDataTypeQNs:
            if unitDataTypeQN not in cncptDataTypeQNs:
                txmyMdl.error("oimte:invalidDataTypeObject",
                          _("Cube %(name)s unitConstraints data Type %(dataType)s MUST have at least one associated concept object on the concept core dimension with the same datatype as the unit object."),
                          xbrlObject=(cubeObj,cubeDimObj), name=name, dataType=unitDataTypeQN)

    # DataType Objects
    for dtObj in txmy.dataTypes:
        assertObjectType(dtObj, XbrlDataType)
        btQn = dtObj.baseType
        if btQn and btQn.namespaceURI != "http://www.w3.org/2001/XMLSchema" and not isinstance(txmyMdl.namedObjects.get(btQn), XbrlDataType):
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The dataType object %(name)s MUST define a valid baseType which must be a dataType object in the taxonomy model"),
                      xbrlObject=dtObj, name=dt.name)
        if dtObj.unitType is not None:
            utObj = dtObj.unitType
            assertObjectType(utObj, XbrlUnitType)
            for utProp in ("dataTypeNumerator", "dataTypeDenominator", "dataTypeMutiplier"):
                utPropQn = getattr(utObj, utProp)
                if utPropQn and not isinstance(txmyMdl.namedObjects.get(utPropQn), XbrlDataType):
                    txmyMdl.error("oimte:invalidPropertyValue",
                              _("The dataType object unitType %(name)s MUST define a valid dataType object in the taxonomy model"),
                              xbrlObject=dtObj, name=dt.name)

    # Dimension Objects
    for dimObj in txmy.dimensions:
        assertObjectType(dimObj, XbrlDimension)
        for cubeTypeQn in dimObj.cubeTypes:
            if not isinstance(txmyMdl.namedObjects.get(cubeTypeQn), XbrlCubeType):
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The dimension cubeType QName %(name)s MUST be a valid cubeType object in the taxonomy model"),
                          xbrlObject=dimObj, name=cubeTypeQn)
        if dimObj.domainDataType and not isinstance(txmyMdl.namedObjects.get(dimObj.domainDataType), XbrlDataType):
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The dimension domain dataType object QName %(name)s MUST be a valid dataType object in the taxonomy model"),
                      xbrlObject=dimObj, name=dimObj.domainDataType)
        if dimObj.domainRoot:
            domRtObj = txmyMdl.namedObjects.get(dimObj.domainRoot)
            if not isinstance(domRtObj, XbrlDomainRoot):
                txmyMdl.error("oimte:missingQNameReference",
                          _("The dimension domainRoot object QName %(name)s MUST be a valid domainRoot object in the taxonomy model"),
                          xbrlObject=dimObj, name=dimObj.domainRoot)
            if dimObj.name.namespaceURI != xbrl and dimObj.domainRoot in (conceptDomainRoot, unitDomainRoot, languageDomainRoot):
                txmyMdl.error("oimte:invalidDomainRoot",
                          _("The dimension domainRoot object QName MUST not be %(name)s."),
                          xbrlObject=dimObj, name=dimObj.domainRoot)

    # Domain Objects
    for domObj in txmy.domains:
        assertObjectType(domObj, XbrlDomain)
        extendTargetObj = None
        if domObj.extendTargetName:
            extendTargetObj = txmyMdl.namedObjects.get(domObj.extendTargetName)
            if domObj.name:
                txmyMdl.error("oimte:invalidObjectProperty",
                          _("The domain %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=domObj, name=domObj.name)
            elif not isinstance(extendTargetObj, XbrlDomain):
                txmyMdl.error("oimte:missingQNameReference",
                          _("The domain %(name)s MUST be a valid domain object in the taxonomy model"),
                          xbrlObject=domObj, name=domObj.name or domObj.extendTargetName)
            elif getattr(domObj, "_extendResolved", False):
                extendTargetObj = None # don't extend, already been extended
            else:
                domObj._extendResolved = True
        elif not domObj.name:
            txmyMdl.error("oimte:missingRequiredProperty",
                      _("The domain object MUST have either a name or an extendTargetName, not neither."),
                      xbrlObject=domObj)

        if not domObj.extendTargetName and not isinstance(txmyMdl.namedObjects.get(domObj.root), XbrlDomainRoot):
            txmyMdl.error("oimte:missingQNameReference",
                      _("The domain %(name)s root %(qname)s MUST be a valid domainRoot object in the taxonomy model"),
                      xbrlObject=domObj, name=domObj.name, qname=domObj.root)
        domRelCts = {}
        domRt = domObj.root
        domRootSourceInRel = domRt is not None # only check if there are any relationships
        for i, relObj in enumerate(domObj.relationships):
            if i == 0:
                domRootSourceInRel = False
            assertObjectType(relObj, XbrlRelationship)
            src = getattr(relObj, "source", None)
            tgt = getattr(relObj, "target", None)
            if src not in txmyMdl.namedObjects or tgt not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, and target, %(target)s, MUST be objects in the taxonomy model."),
                          xbrlObject=relObj, name=domObj.name, nbr=i, source=src, target=tgt)
            else:
                if domRt == conceptDomainRoot:
                    if not isinstance(txmyMdl.namedObjects[relObj.source], XbrlConcept):
                        txmyMdl.error("oimte:invalidObjectType",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s MUST be a concept object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects[relObj.target], XbrlConcept):
                        txmyMdl.error("oimte:invalidDomainTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be a concept object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                if domRt == entityDomainRoot:
                    if relObj.source != domRt and not isinstance(txmyMdl.namedObjects[relObj.source], XbrlEntity):
                        txmyMdl.error("oimte:invalidDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the entity root or an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects[relObj.target], XbrlEntity):
                        txmyMdl.error("oimte:invalidDomainTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                if domRt == unitDomainRoot:
                    if relObj.source != domRt and not isinstance(txmyMdl.namedObjects[relObj.source], XbrlUnit):
                        txmyMdl.error("oimte:invalidDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the unit root or an unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects[relObj.target], XbrlUnit):
                        txmyMdl.error("oimte:domainIncludesNonUnitTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be a unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                elif isinstance(txmyMdl.namedObjects[relObj.source], XbrlUnit) or isinstance(txmyMdl.namedObjects[relObj.target], XbrlUnit):
                    txmyMdl.error("oimte:unitInNonUnitDomain",
                              _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, or target, %(target)s, MUST be not be unit objects in the taxonomy model."),
                              xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source, target=relObj.target)

            if isinstance(txmyMdl.namedObjects.get(tgt), (XbrlDomain, XbrlDomainRoot)):
                txmyMdl.error("oimte:invalidObjectType",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domain or domainRoot object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            elif extendTargetObj is not None:
                extendTargetObj.relationships.add(relObj)
            if tgt == domRt:
                txmyMdl.error("oimte:invalidDomainTarget",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be the domain root object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            if domRt == src:
                domRootSourceInRel = True
            relKey = (src, tgt)
            domRelCts[relKey] = domRelCts.get(relKey, 0) + 1
        if any(ct > 1 for relKey, ct in domRelCts.items()):
            txmyMdl.error("oimte:duplicateObjects",
                      _("The domain %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=domObj, name=domObj.name,
                      names=", ".join(f"{relKey[0]}\u2192{relKey[1]}" for relKey, ct in domRelCts.items() if ct > 1))
        if not domRootSourceInRel:
            txmyMdl.error("oimte:missingDomainRootSource",
                      _("The domain %(name)s root %(qname)s MUST be a source in a relationship"),
                      xbrlObject=domObj, name=domObj.name, qname=domObj.root)

        validateProperties(txmyMdl, oimFile, txmy, domObj)


    # DomainRoot Objects
    for domRtObj in txmy.domainRoots:
        assertObjectType(domRtObj, XbrlDomainRoot)
        validateProperties(txmyMdl, oimFile, txmy, domRtObj)

    # Entity Objects
    for entityObj in txmy.entities:
        assertObjectType(entityObj, XbrlEntity)
        validateProperties(txmyMdl, oimFile, txmy, entityObj)

    # GroupContent Objects
    for grpCntObj in txmy.groupContents:
        assertObjectType(grpCntObj, XbrlGroupContent)
        grpQn = grpCntObj.groupName
        if grpQn not in txmyMdl.namedObjects or type(txmyMdl.namedObjects[grpQn]) != XbrlGroup:
            txmyMdl.error("oimte:invalidGroupObject",
                      _("The groupContent object groupName QName %(name)s MUST be a valid group object in the taxonomy model"),
                      xbrlObject=grpCntObj, name=grpQn)
        for relName in grpCntObj.relatedNames:
            if relName not in txmyMdl.namedObjects or not isinstance(txmyMdl.namedObjects.get(relName), (XbrlNetwork, XbrlCube, XbrlTableTemplate)):
                txmyMdl.error("oimte:invalidGroupObject",
                          _("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects or table template objects."),
                          xbrlObject=grpCntObj, name=grpQn, relName=relName)

    # Label Objects
    labelsCt = defaultdict(list)
    for lblObj in txmy.labels:
        assertObjectType(lblObj, XbrlLabel)
        relatedName = lblObj.relatedName
        lang = lblObj.language
        if not languagePattern.match(lang):
            txmyMdl.error("oime:invalidLanguage",
                      _("Label %(relatedName)s has invalid language %(lang)s"),
                      xbrlObject=lblObj, relatedName=relatedName, lang=lang)
        relatedObj = None
        if relatedName not in txmyMdl.namedObjects:
            txmyMdl.error("oimte:unresolvedRelatedName",
                      _("Label has invalid related object %(relatedName)s"),
                      xbrlObject=lblObj, relatedName=relatedName)
        else:
            relatedObj = txmyMdl.namedObjects.get(relatedName)
        lblTpObj = txmyMdl.namedObjects.get(lblObj.labelType)
        if isinstance(lblTpObj, XbrlLabelType):
            if lblTpObj.allowedObjects and relatedObj is not None and not any(
                type(relatedObj) == xbrlObjectTypes[allowedObj] for allowedObj in lblTpObj.allowedObjects):
                txmyMdl.error("oimte:invalidAllowedObject",
                          _("Label has disallowed related object %(relatedName)s"),
                          xbrlObject=lblObj, relatedName=relatedName)                
            lblObj._xValid, lblObj._xValue = validateValue(txmyMdl, txmy, lblObj, lblObj.value, lblTpObj.dataType, "", "oimte:invalidPropertyValue")
        else:
            txmyMdl.error("oimte:missingQNameReference",
                      _("Label has invalid labelType %(labelType)s"),
                      xbrlObject=lblObj, labelType=lblObj.labelType)
        validateProperties(txmyMdl, oimFile, txmy, lblObj)
        lblKey = (relatedName, lblObj.labelType, lang)
        labelsCt[lblKey].append(lblObj)
    for lblKey, lblObjs in labelsCt.items():
        if len(lblObjs) > 1:
            txmyMdl.error("oimte:duplicateLabelObject",
                      _("The labels are duplicated for relatedName %(name)s type %(type)s language %(language)s"),
                      xbrlObject=lblObjs, name=lblKey[0], type=lblKey[1], language=lblKey[2])

    # Network Objects
    ntwkCt = {}
    for ntwkObj in txmy.networks:
        assertObjectType(ntwkObj, XbrlNetwork)
        extendTargetObj = None
        relTypeObj = None
        if ntwkObj.extendTargetName:
            extendTargetObj = txmyMdl.namedObjects.get(ntwkObj.extendTargetName)
            if ntwkObj.name:
                txmyMdl.error("oimte:invalidObjectProperty",
                          _("The network %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=ntwkObj, name=ntwkObj.name)
            elif not isinstance(extendTargetObj, XbrlNetwork):
                txmyMdl.error("oimte:missingTargetObject",
                          _("The network extendTargetName %(name)s MUST be a valid network object in the taxonomy model"),
                          xbrlObject=ntwkObj, name=ntwkObj.name or ntwkObj.extendTargetName)
            elif getattr(ntwkObj, "_extendResolved", False):
                extendTargetObj = None # don't extend, already been extended
            else:
                ntwkObj._extendResolved = True
            relTypeObj = txmyMdl.namedObjects.get(ntwkObj.relationshipTypeName)
            if not isinstance(relTypeObj, XbrlRelationshipType):
                relTypeObj = None
                txmyMdl.warning("oimte:missingQNameReference",
                          _("The network %(name)s relationshipTypeName %(relationshipTypeName)s SHOULD specify a relationship type in the taxonomy model."),
                          xbrlObject=ntwkObj, name=ntwkObj.name, relationshipTypeName=ntwkObj.relationshipTypeName)
        else:
            if not ntwkObj.name:
                txmyMdl.error("oimte:missingRequiredProperty",
                          _("The network object MUST have either a name or an extendTargetName, not neither."),
                          xbrlObject=ntwkObj)
            relTypeObj = txmyMdl.namedObjects.get(ntwkObj.relationshipTypeName)
            if not isinstance(relTypeObj, XbrlRelationshipType):
                relTypeObj = None
                txmyMdl.error("oimte:missingQNameReference",
                          _("The network %(name)s relationshipTypeName %(relationshipTypeName)s MUST specify a relationship type in the taxonomy model."),
                          xbrlObject=ntwkObj, name=ntwkObj.name, relationshipTypeName=ntwkObj.relationshipTypeName)
        ntwkCt = {}
        for rootQn in ntwkObj.roots:
            if rootQn not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The network %(name)s root %(qname)s MUST be a valid object in the taxonomy model"),
                          xbrlObject=ntwkObj, name=ntwkObj.name, qname=rootQn)
            ntwkCt[rootQn] = ntwkCt.get(rootQn, 0) + 1
        if any(ct > 1 for root, ct in ntwkCt.items()):
            txmyMdl.error("oimte:duplicateObjects",
                          _("The network %(name)s has duplicated roots %(roots)s"),
                          xbrlObject=ntwkObj, roots=", ".join(str(root) for root, ct in ntwkCt.items() if ct > 1))

        ntwkCt = {}
        sources = OrderedSet()
        targets = OrderedSet()
        for i, relObj in enumerate(ntwkObj.relationships):
            assertObjectType(relObj, XbrlRelationship)
            if  relObj.source not in txmyMdl.namedObjects or relObj.target not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The network %(name)s relationship[%(nbr)s] source, %(source)s, and target, %(target)s, MUST be objects in the taxonomy model."),
                          xbrlObject=relObj, name=ntwkObj.name, nbr=i, source=relObj.source, target=relObj.target)
            else:
                sources.add(relObj.source)
                targets.add(relObj.target)
                if extendTargetObj is not None:
                    extendTargetObj.relationships.add(relObj)
                if relTypeObj is not None:
                    if relTypeObj.sourceObjects and xbrlObjectQNames.get(type(txmyMdl.namedObjects[relObj.source])) not in relTypeObj.sourceObjects:
                        txmyMdl.error("oimte:invalidObjectType",
                                  _("The network %(name)s relationship[%(nbr)s] source, %(source)s MUST be an object type allowed for the relationship type %(relationshipType)s."),
                                  xbrlObject=relObj, name=ntwkObj.name, nbr=i, source=relObj.source, relationshipType=ntwkObj.relationshipTypeName)
                    if relTypeObj.targetObjects and xbrlObjectQNames.get(type(txmyMdl.namedObjects[relObj.target])) not in relTypeObj.targetObjects:
                        txmyMdl.error("oimte:invalidObjectType",
                                  _("The network %(name)s relationship[%(nbr)s] target, %(target)s MUST be an object type allowed for the relationship type %(relationshipType)s."),
                                  xbrlObject=relObj, name=ntwkObj.name, nbr=i, target=relObj.target, relationshipType=ntwkObj.relationshipTypeName)
            validateProperties(txmyMdl, oimFile, txmy, relObj)
            for propObj in relObj.properties:
                if propObj.property == preferredLabel and getattr(propObj, "_xValid", INVALID) >= VALID:
                    if not isinstance(txmyMdl.namedObjects.get(propObj._xValue), XbrlLabelType):
                        txmyMdl.error("oimte:missingQNameReference",
                                  _("The network %(name)s relationship[%(nbr)s] preferredLabel, %(preferredLabel)s MUST be a label type object."),
                                  xbrlObject=relObj, name=ntwkObj.name, nbr=i, preferredLabel=propObj._xValue)
            relKey = (relObj.source, relObj.target)
            ntwkCt[relKey] = ntwkCt.get(relKey, 0) + 1
        if any(ct > 1 for relKey, ct in ntwkCt.items()):
            txmyMdl.error("oimte:duplicateObjects",
                      _("The network %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=ntwkObj, name=ntwkObj.name,
                      names=", ".join(f"{relKey[0]}\u2192{relKey[1]}" for relKey, ct in ntwkCt.items() if ct > 1))
        ntwkObj._roots = sources - targets
        if ntwkObj.roots:
            if ntwkObj.roots != ntwkObj._roots:
                txmyMdl.error("oimte:invalidNetworkRoot",
                          _("The network %(name)s network object roots property does not match actual relationship roots: %(roots)s"),
                          xbrlObject=ntwkObj, name=ntwkObj.name, roots=", ".join(str(r) for r in ntwkObj._roots))
        else:
            ntwkObj.roots = ntwkObj._roots # not specified so use actual roots
        validateProperties(txmyMdl, oimFile, txmy, ntwkObj)
        del ntwkCt

    # PropertyType Objects
    for propTpObj in txmy.propertyTypes:
        assertObjectType(propTpObj, XbrlPropertyType)
        dataTypeObj = txmyMdl.namedObjects.get(propTpObj.dataType)
        if not isinstance(dataTypeObj, XbrlDataType):
            txmyMdl.error("oimte:invalidObjectType",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                      xbrlObject=propTpObj, name=propTpObj.name, qname=propTpObj.dataType)
        elif propTpObj.enumerationDomain and txmyMdl.namedObjects[dataTypeObj.baseType] != qnXsQName:
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                      xbrlObject=propTpObj, name=propTpObj.name, qname=propTpObj.dataType)
        for allowedObjQn in propTpObj.allowedObjects:
            if allowedObjQn not in objectsWithProperties:
                txmyMdl.error("oimte:invalidAllowedObject",
                          _("The property %(name)s has an invalid allowed object %(allowedObj)s"),
                          xbrlObject=propTpObj, name=propTpObj.name, allowedObj=allowedObjQn)

    # RelationshipType Objects
    for relTpObj in txmy.relationshipTypes:
        assertObjectType(relTpObj, XbrlRelationshipType)
        for prop in ("allowedLinkProperties", "requiredLinkProperties"):
            for propTypeQn in getattr(relTpObj, prop):
                if not isinstance(txmyMdl.namedObjects.get(propTypeQn), XbrlPropertyType):
                    txmyMdl.error("oimte:missingQNameReference",
                              _("The relationshipType %(name)s %(property)s has an invalid propertyType reference %(propType)s"),
                              xbrlObject=propTpObj, name=relTpObj.name, property=prop, propType=propTypeQn)
        reqdNotAllowed = relTpObj.requiredLinkProperties - relTpObj.allowedLinkProperties
        if reqdNotAllowed:
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The relationshipType %(name)s has an required properties which are not allowed %(propTypes)s"),
                      xbrlObject=propTpObj, name=relTpObj.name, property=prop, propTypes=", ".join(str(q) for q in reqdNotAllowed))

    # Reference Objects
    refsWithInvalidLang = defaultdict(list)
    refsWithInvalidRelName = []
    refInvalidNames = []
    refsDup = defaultdict(list)
    for refObj in txmy.references:
        assertObjectType(refObj, XbrlReference)
        name = refObj.name
        lang = refObj.language
        refTp = refObj.referenceType
        extName = refObj.extendTargetName
        if lang is not None and not languagePattern.match(lang):
            refsWithInvalidLang[lang].append(refObj)
        for relName in refObj.relatedNames:
            if relName not in txmyMdl.namedObjects:
                refsWithInvalidRelName.append(refObj)
                refInvalidNames.append(relName)
        if not isinstance(txmyMdl.namedObjects.get(refTp), XbrlReferenceType) and (refTp or not extName):
                txmyMdl.error("oimte:missingQNameReference",
                          _("The reference %(name)s reference %(qname)s MUST be a referenceType object."),
                          xbrlObject=refObj, name=name, qname=refTp)
        if extName:
            if name:
                txmyMdl.error("oimte:referenceNameRedefined",
                          _("Referencehas both extendTargetName and name %(name)s"),
                          xbrlObject=refObj, name=extName)
            else:
                extRefObjs = txmyMdl.tagObjects.get(extName) or ()
                if not all(isinstance(extRefObj, XbrlReference) for extRefObj in extRefObjs):
                    txmyMdl.error("oimte:missingQNameReference",
                              _("Reference extendTargetName must be a reference object %(name)s"),
                              xbrlObject=refObj, name=extName)
                elif not any(extRefObj.referenceType == refTp for extRefObj in extRefObjs):
                    txmyMdl.error("oimte:referenceTypeRedefined",
                              _("Reference extendTargetName reference object %(name)s must have same referenceType %(referenceType)s"),
                              xbrlObject=refObj, name=extName, referenceType=refTp)
            if lang:
                txmyMdl.error("oimte:referenceLanguageRedefined",
                          _("Referencehas both extendTargetName and language: %(name)s"),
                          xbrlObject=refObj, name=extName)
        validateProperties(txmyMdl, oimFile, txmy, refObj)
        refsDup[name].append(refObj)
    if refsWithInvalidRelName:
        txmyMdl.warning("oimte:unresolvedRelatedNameWarning",
                  _("References have invalid related object names %(relNames)s"),
                  xbrlObject=refsWithInvalidRelName, name=name, relNames=", ".join(str(qn) for qn in refInvalidNames))
    for lang, refObjs in refsWithInvalidLang:
        txmyMdl.warning("oime:invalidLanguageWarning",
                  _("Reference object(s) have invalid language %(lang)s"),
                  xbrlObject=refObjs, lang=lang)
    for name, refsDups in refsDup.items():
        if len(refsDups) > 1:
            txmyMdl.error("oimte:duplicateObjects",
                          _("The referenceType %(name)s is duplicated."),
                          xbrlObject=refsDups, name=name)
    del refsWithInvalidLang, refsWithInvalidRelName, refInvalidNames, refsDup # dereference

    # Label Objects
    lblTpCt = {}
    for lblObj in txmy.labelTypes:
        assertObjectType(lblObj, XbrlLabelType)
        dataTypeObj = txmyMdl.namedObjects.get(lblObj.dataType)
        if not isinstance(dataTypeObj, XbrlDataType):
            txmyMdl.error("oimte:invalidDataTypeObject",
                      _("The labelType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                      xbrlObject=lblObj, name=lblObj.name, qname=lblObj.dataType)
        if lblObj.allowedObjects is not None:
            if not lblObj.allowedObjects:
                txmyMdl.error("oimte:invalidEmptySet",
                          _("The labelType %(name)s allowedObjects MUST not be empty."),
                          xbrlObject=lblObj, name=lblObj.name)
            else:
                for allowedObj in lblObj.allowedObjects:
                    if allowedObj not in xbrlObjectTypes:
                        txmyMdl.error("oimte:invalidAllowedObject",
                                  _("The labelType %(name)s allowedObject %(allowedObject)s MUST be a taxonomy model object."),
                                  xbrlObject=lblObj, name=lblObj.name, allowedObject=allowedObj)
        

    # Unit Objects
    for unitObj in txmy.units:
        assertObjectType(unitObj, XbrlUnit)
        name = unitObj.name
        dtQn = getattr(unitObj, "dataType", None)
        if dtQn:
            if not isinstance(txmyMdl.namedObjects.get(dtQn), XbrlDataType):
                txmyMdl.error("oimte:unknownDataType",
                          _("The unit %(name)s dataType %(qname)s MUST be a dataType object."),
                          xbrlObject=unitObj, name=unitObj.name, qname=dtQn)
        unitObj._unitsMeasures = [parseUnitString(uStr, unitObj, txmy, txmyMdl) for uStr in unitObj.stringRepresentations]
        for uMeas in unitObj._unitsMeasures:
            if any(m == name for md in uMeas for m in md):
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The unit %(name)s must not contain itself as a measure."),
                          xbrlObject=unitObj, name=unitObj.name)

    # Facts in taxonomy
    if txmy.facts:
        global validateFact
        if validateFact is None:
            from .ValidateReport import validateFact
        for fact in txmy.facts:
            validateFact(fact, txmy.name, txmy, txmyMdl)
