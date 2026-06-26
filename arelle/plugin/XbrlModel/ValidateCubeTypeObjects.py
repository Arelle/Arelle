'''
See COPYRIGHT.md for copyright information.
'''
from .ErrorCatalog import emit_error
from .XbrlConcept import XbrlDataType
from .XbrlConst import qnXbrlDimensionObj, EMPTY_FROZENSET
from .XbrlCube import XbrlCubeType, coreDimensions, conceptDomainClass, entityDomainClass, unitDomainClass
from .XbrlDimension import XbrlDimension
from .XbrlModule import referencableObjectTypes
from .XbrlNetwork import XbrlRelationshipType
from .XbrlProperty import XbrlPropertyType


def validateCubeTypeFamily(compMdl, module, oimFile, *, assertObjectType, validateQNameReference, validateProperties):
    """Validate XbrlCubeType objects: core dimensions, dimension constraints, network constraints,
       cube properties, and base-cube-type restriction rules."""
    for cubeType in module.cubeTypes or ():
        assertObjectType(compMdl, cubeType, XbrlCubeType)
        name = cubeType.name
        if (cubeType.coreDimensions or EMPTY_FROZENSET) - coreDimensions:
            emit_error(compMdl, "oimte:invalidCoreDimension",
                       _("The cube type %(name)s, specifies QNames which are not core dimensions: %(qnames)s."),
                       xbrlObject=cubeType, name=name,
                       qnames=", ".join(str(qn) for qn in (cubeType.coreDimensions - coreDimensions)))

        validCoreDomainClasses = {conceptDomainClass, entityDomainClass, unitDomainClass}
        for coreDomClass in cubeType.coreDomainClasses or ():
            if coreDomClass not in validCoreDomainClasses:
                emit_error(compMdl, "oimte:invalidCoreDomainClass",
                           _("The cube type %(name)s coreDomainClasses contains invalid core domain class %(domainClass)s."),
                           xbrlObject=cubeType, name=name, domainClass=coreDomClass)

        dConstrNames = {}
        if cubeType.cubeDimensionConstraints:
            for i, dConstr in enumerate(cubeType.cubeDimensionConstraints.allowed or ()):
                if dConstr.dimensionName:
                    validateQNameReference(compMdl, dConstr, "dimensionName", XbrlDimension,
                                           undefinedMsgCode="oimte:invalidDimensionConstraintDimensionName",
                                           invalidTypeMsgCode="oimte:invalidDimensionConstraintDimensionName")
                    if dConstr.dimensionName in coreDimensions:
                        emit_error(compMdl, "oimte:invalidDimensionConstraintDimensionName",
                                   _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] dimensionName %(dimName)s MUST NOT be a core dimension."),
                                   xbrlObject=cubeType, name=name, i=i, dimName=dConstr.dimensionName)
                if dConstr.minDimensions is not None and dConstr.maxDimensions is not None and dConstr.minDimensions > dConstr.maxDimensions:
                    emit_error(compMdl, "oimte:invalidCubeConstraints",
                               _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] minDimensions %(minDimensions)s MUST NOT be greater than maxDimensions %(maxDimensions)s."),
                               xbrlObject=cubeType, name=name, i=i,
                               minDimensions=dConstr.minDimensions, maxDimensions=dConstr.maxDimensions)
                if dConstr.dimensionName is not None:
                    if dConstr.dimensionName in dConstrNames:
                        emit_error(compMdl, "oimte:duplicateDimension",
                                   _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] dimensionName %(dimName)s duplicates cubeDimensionConstraints[%(i2)s]."),
                                   xbrlObject=cubeType, name=name, i=i,
                                   dimName=dConstr.dimensionName, i2=dConstrNames[dConstr.dimensionName])
                    else:
                        dConstrNames[dConstr.dimensionName] = i
                if dConstr.dataType:
                    dtObj = validateQNameReference(compMdl, dConstr, "dataType", XbrlDataType,
                                                  invalidTypeMsgCode="oimte:invalidObjectType")
                    if dtObj and dtObj.allowedObjects and qnXbrlDimensionObj not in dtObj.allowedObjects:
                        emit_error(compMdl, "oimte:unallowedDataTypeObject",
                                   _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] dataType %(dataType)s is not allowed on a dimension object."),
                                   xbrlObject=cubeType, name=name, i=i, dataType=dConstr.dataType)
                if dConstr.dataType and dConstr.type != "typed":
                    emit_error(compMdl, "oimte:invalidDimensionDataTypeProperty",
                               _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] has a dataType which requires type must be \"typed\" but is: %(typed)s."),
                               xbrlObject=cubeType, name=name, i=i, typed=dConstr.type)
        if cubeType.cubeNetworkConstraints:
            cnc = cubeType.cubeNetworkConstraints
            if cubeType.cubeNetworkConstraints.cubeNetworks:
                for cubeNtwkCnstrObj in cubeType.cubeNetworkConstraints.cubeNetworks:
                    validateQNameReference(compMdl, cubeNtwkCnstrObj, "relationshipType", XbrlRelationshipType,
                                           invalidTypeMsgCode="oimte:invalidObjectType")
                    if (cubeNtwkCnstrObj.minNetworks is not None and cubeNtwkCnstrObj.maxNetworks is not None and
                            cubeNtwkCnstrObj.minNetworks > cubeNtwkCnstrObj.maxNetworks):
                        emit_error(compMdl, "oimte:invalidCubeConstraints",
                                   _("The cube type %(name)s, cubeNetworkConstraints/cubeNetworks relationshipType %(relType)s has minNetworks %(minNetworks)s greater than maxNetworks %(maxNetworks)s."),
                                   xbrlObject=cubeType, name=name, relType=cubeNtwkCnstrObj.relationshipType,
                                   minNetworks=cubeNtwkCnstrObj.minNetworks, maxNetworks=cubeNtwkCnstrObj.maxNetworks)
                    for endPtCnstrObj in (cubeNtwkCnstrObj.source, cubeNtwkCnstrObj.target):
                        if endPtCnstrObj is not None:
                            if endPtCnstrObj.qname:
                                validateQNameReference(compMdl, endPtCnstrObj, "qname", None)
                            if endPtCnstrObj.objectType:
                                if endPtCnstrObj.objectType not in referencableObjectTypes:
                                    if compMdl.namedObjects.get(endPtCnstrObj.objectType) is None:
                                        emit_error(compMdl, "oimte:invalidQNameReference",
                                                   _("The cube type %(name)s, cubeNetworkConstraints/cubeNetworks/relationshipType %(relType)s endpoint objectType %(objType)s is not defined."),
                                                   xbrlObject=cubeType, name=name,
                                                   relType=cubeNtwkCnstrObj.relationshipType, objType=endPtCnstrObj.objectType)
                                    else:
                                        emit_error(compMdl, "oimte:invalidObjectType",
                                                   _("The cube type %(name)s, cubeNetworkConstraints/cubeNetworks/relationshipType %(relType)s endpoint objectType %(objType)s is not a referencable model component object type."),
                                                   xbrlObject=cubeType, name=name,
                                                   relType=cubeNtwkCnstrObj.relationshipType, objType=endPtCnstrObj.objectType)
                            if endPtCnstrObj.dataType:
                                validateQNameReference(compMdl, endPtCnstrObj, "dataType", XbrlDataType,
                                                       invalidTypeMsgCode="oimte:invalidObjectType")
        if cubeType.cubeProperties:
            for ra in ("requiredProperties", "allowedProperties"):
                for i, propTpQn in enumerate(getattr(cubeType.cubeProperties, ra) or ()):
                    propTypeObj = compMdl.namedObjects.get(propTpQn)
                    if propTypeObj is None:
                        emit_error(compMdl, "oimte:invalidQNameReference",
                                   _("The cube type %(name)s, cubeProperties/%(ra)s[%(i)s], references undefined propertyType %(qname)s."),
                                   xbrlObject=cubeType, name=name, ra=ra, i=i, qname=propTpQn)
                    elif not isinstance(propTypeObj, XbrlPropertyType):
                        emit_error(compMdl, "oimte:invalidObjectType",
                                   _("The cube type %(name)s, cubeProperties/%(ra)s[%(i)s], references %(qname)s which is not a propertyType object."),
                                   xbrlObject=cubeType, name=name, ra=ra, i=i, qname=propTpQn)
        if cubeType.baseCubeType is not None:
            if cubeType.baseCubeType not in compMdl.namedObjects:
                emit_error(compMdl, "oimte:invalidQNameReference",
                           _("The cube type %(name)s, specifies base cube type %(base)s which is not defined."),
                           xbrlObject=cubeType, name=name, base=cubeType.baseCubeType)
            else:
                baseCubeType = compMdl.namedObjects.get(cubeType.baseCubeType)
                if not isinstance(baseCubeType, XbrlCubeType):
                    emit_error(compMdl, "oimte:invalidObjectType",
                               _("The cube type %(name)s, specifies base cube type %(base)s which is not a cube type object."),
                               xbrlObject=cubeType, name=name, base=cubeType.baseCubeType)
                else:
                    baseCoreDims = baseCubeType.effectivePropVal(compMdl, "coreDimensions")
                    if baseCoreDims and ((cubeType.coreDimensions or EMPTY_FROZENSET) - baseCoreDims):
                        emit_error(compMdl, "oimte:coreDimensionsExpansion",
                                   _("The cube type %(name)s, expands base cube type core dimensions by %(qnames)s."),
                                   xbrlObject=cubeType, name=name,
                                   qnames=", ".join(str(qn) for qn in (cubeType.coreDimensions - baseCoreDims)))
                    baseDimConstrClosed = baseCubeType.effectivePropVal(compMdl, "cubeDimensionConstraints", "closed")
                    if cubeType.cubeDimensionConstraints:
                        if baseDimConstrClosed == True and cubeType.cubeDimensionConstraints.closed == False:
                            emit_error(compMdl, "oimte:invalidDimensionClosedExpansion",
                                       _("The cube type %(name)s, must not set cubeDimensionConstraints.closed \"false\" where base cube type is \"true\"."),
                                       xbrlObject=cubeType, name=name)
                        baseDimConstrs = baseCubeType.effectivePropVal(compMdl, "cubeDimensionConstraints", "allowed") or ()
                        for i, dimConstr in enumerate(cubeType.cubeDimensionConstraints.allowed or ()): 
                            matchingBaseDimFound = False
                            matchedBaseDimConst = None
                            for baseDimConst in baseDimConstrs:
                                if ((dimConstr.dimensionName and dimConstr.dimensionName == baseDimConst.dimensionName) or
                                    (dimConstr.dataType and baseDimConst.dataType and dimConstr.dataType == baseDimConst.dataType) or
                                    (dimConstr.type == "typed" and baseDimConst.type == "typed" and
                                     not dimConstr.dimensionName and not baseDimConst.dimensionName and
                                     not dimConstr.dataType and not baseDimConst.dataType)):
                                    matchingBaseDimFound = True
                                    matchedBaseDimConst = baseDimConst
                                    if dimConstr.minDimensions is not None and baseDimConst.minDimensions is not None and dimConstr.minDimensions < baseDimConst.minDimensions:
                                        emit_error(compMdl, "oimte:invalidDimensionRequirementRelaxation",
                                                   _("The cube type %(name)s, must not set cubeDimensionConstraints/allowed[%(i)s].minDimensions to %(minDimensions)s when derived base required for the dimension is %(baseMinDimensions)s."),
                                                   xbrlObject=cubeType, name=name, i=i,
                                                   minDimensions=dimConstr.minDimensions, baseMinDimensions=baseDimConst.minDimensions)
                                    if dimConstr.dataType and baseDimConst.dataType:
                                        dataTypeObj = compMdl.namedObjects.get(dimConstr.dataType)
                                        if isinstance(dataTypeObj, XbrlDataType) and not dataTypeObj.instanceOfType(baseDimConst.dataType, compMdl):
                                            emit_error(compMdl, "oimte:invalidDataTypeExpansion",
                                                       _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s].dataType %(dataType)s must not be an expansion of the base data type %(baseDataType)s"),
                                                       xbrlObject=cubeType, name=name, i=i,
                                                       dataType=dimConstr.dataType, baseDataType=baseDimConst.dataType)
                                    if baseDimConst.domainClassProperties and baseDimConst.domainClassProperties.requiredProperties:
                                        if dimConstr.domainClassProperties:
                                            removedPropsReqd = baseDimConst.domainClassProperties.requiredProperties - dimConstr.domainClassProperties.requiredProperties
                                            if removedPropsReqd:
                                                emit_error(compMdl, "oimte:missingRequiredDimensionProperty",
                                                           _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s].domainClassProperties must include all properties required by the baseCubeType, these are missing: %(domainClassProperties)s"),
                                                           xbrlObject=cubeType, name=name, i=i,
                                                           domainClassProperties=", ".join(sorted(str(p) for p in removedPropsReqd)))
                            if not matchingBaseDimFound and dimConstr.type == "typed" and not dimConstr.dimensionName:
                                baseTypedUnnamed = [b for b in baseDimConstrs if b.type == "typed" and not b.dimensionName]
                                if len(baseTypedUnnamed) == 1:
                                    matchedBaseDimConst = baseTypedUnnamed[0]
                                    matchingBaseDimFound = True
                                    if dimConstr.dataType and matchedBaseDimConst.dataType:
                                        dataTypeObj = compMdl.namedObjects.get(dimConstr.dataType)
                                        if isinstance(dataTypeObj, XbrlDataType) and not dataTypeObj.instanceOfType(matchedBaseDimConst.dataType, compMdl):
                                            emit_error(compMdl, "oimte:invalidDataTypeExpansion",
                                                       _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s].dataType %(dataType)s must not be an expansion of the base data type %(baseDataType)s"),
                                                       xbrlObject=cubeType, name=name, i=i,
                                                       dataType=dimConstr.dataType, baseDataType=matchedBaseDimConst.dataType)
                            if baseDimConstrClosed and not matchingBaseDimFound:
                                emit_error(compMdl, "oimte:invalidDimensionAddition",
                                           _("The cube type %(name)s, must not set cubeDimensionConstraints/allowed[%(i)s] must not be added a closed base type"),
                                           xbrlObject=cubeType, name=name, i=i)
                    if cubeType.cubeNetworkConstraints and baseCubeType.cubeNetworkConstraints:
                        baseNtwkClosed = baseCubeType.effectivePropVal(compMdl, "cubeNetworkConstraints", "closed")
                        if baseNtwkClosed == True and cubeType.cubeNetworkConstraints.closed == False:
                            emit_error(compMdl, "oimte:invalidNetworkClosedExpansion",
                                       _("The cube type %(name)s, must not set cubeNetworkConstraints.closed \"false\" where base cube type is \"true\"."),
                                       xbrlObject=cubeType, name=name)
                    if cubeType.cubeNetworkConstraints and cubeType.cubeNetworkConstraints.cubeNetworks and baseCubeType.cubeNetworkConstraints:
                        
                        for i, cubeNtwkCnstrObj in enumerate(cubeType.cubeNetworkConstraints.cubeNetworks):
                            matchingBaseNtwkCnstrFound = False
                            for baseCubeNtwkCnstrObj in baseCubeType.effectivePropVal(compMdl, "cubeNetworkConstraints", "cubeNetworks") or ():
                                if cubeNtwkCnstrObj.relationshipType == baseCubeNtwkCnstrObj.relationshipType:
                                    matchingBaseNtwkCnstrFound = True
                                    if (cubeNtwkCnstrObj.minNetworks is not None and baseCubeNtwkCnstrObj.minNetworks is not None and
                                            cubeNtwkCnstrObj.minNetworks < baseCubeNtwkCnstrObj.minNetworks):
                                        emit_error(compMdl, "oimte:invalidRelationshipConstraintRelaxation",
                                                   _("The cube type %(name)s, must not relax cubeNetworkConstraints/cubeNetworks[%(i)s].minNetworks below base value."),
                                                   xbrlObject=cubeType, name=name, i=i)
                                    if (cubeNtwkCnstrObj.source and baseCubeNtwkCnstrObj.source and
                                            (cubeNtwkCnstrObj.source.qname != baseCubeNtwkCnstrObj.source.qname or
                                             cubeNtwkCnstrObj.source.objectType != baseCubeNtwkCnstrObj.source.objectType or
                                             cubeNtwkCnstrObj.source.dataType != baseCubeNtwkCnstrObj.source.dataType)):
                                        emit_error(compMdl, "oimte:invalidRelationshipConstraintRelaxation",
                                                   _("The cube type %(name)s, must not relax cubeNetworkConstraints/cubeNetworks[%(i)s].source constraint from base cube type."),
                                                   xbrlObject=cubeType, name=name, i=i)
                                    if (cubeNtwkCnstrObj.target and baseCubeNtwkCnstrObj.target and
                                            (cubeNtwkCnstrObj.target.qname != baseCubeNtwkCnstrObj.target.qname or
                                             cubeNtwkCnstrObj.target.objectType != baseCubeNtwkCnstrObj.target.objectType or
                                             cubeNtwkCnstrObj.target.dataType != baseCubeNtwkCnstrObj.target.dataType)):
                                        emit_error(compMdl, "oimte:invalidRelationshipConstraintRelaxation",
                                                   _("The cube type %(name)s, must not relax cubeNetworkConstraints/cubeNetworks[%(i)s].target constraint from base cube type."),
                                                   xbrlObject=cubeType, name=name, i=i)
                            if not matchingBaseNtwkCnstrFound:
                                emit_error(compMdl, "oimte:invalidRelationshipExpansion",
                                           _("The cube type %(name)s, must not set cubeNetworkConstraints/cubeNetworks[%(i)s] must not be added when base does not have that network constraint"),
                                           xbrlObject=cubeType, name=name, i=i)
                    if cubeType.cubeProperties:
                        basePropertiesAllowed = baseCubeType.effectivePropVal(compMdl, "cubeProperties", "allowedProperties")
                        basePropertiesRequired = baseCubeType.effectivePropVal(compMdl, "cubeProperties", "requiredProperties")
                        if basePropertiesRequired:
                            removedPropsReqd = basePropertiesRequired - (cubeType.cubeProperties.requiredProperties or EMPTY_FROZENSET)
                            if removedPropsReqd:
                                emit_error(compMdl, "oimte:invalidPropertyRequirementRelaxation",
                                           _("The cube type %(name)s, must not remove property types required by the base type: %(qnames)s"),
                                           xbrlObject=cubeType, name=name,
                                           qnames=", ".join(sorted(str(qn) for qn in removedPropsReqd)))
                        if basePropertiesAllowed and cubeType.cubeProperties.allowedProperties:
                            unallowedAddedProps = cubeType.cubeProperties.allowedProperties - basePropertiesAllowed
                            if unallowedAddedProps:
                                emit_error(compMdl, "oimte:invalidPropertyExpansion",
                                           _("The cube type %(name)s, must not add property types not permitted by the base type: %(qnames)s"),
                                           xbrlObject=cubeType, name=name,
                                           qnames=", ".join(sorted(str(qn) for qn in unallowedAddedProps)))
