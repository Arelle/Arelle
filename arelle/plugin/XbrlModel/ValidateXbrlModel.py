'''
See COPYRIGHT.md for copyright information.
'''

import regex as re, dateutil
from collections import defaultdict
from decimal import Decimal
from typing import GenericAlias, _GenericAlias, _UnionGenericAlias
from arelle.ModelValue import QName, timeInterval
from arelle.XmlValidate import languagePattern, validateValue as validateXmlValue,\
    INVALID, VALID, NONE
from arelle.XbrlConst import isNumericXsdType
from arelle.PythonUtil import attrdict, OrderedSet
from arelle.oim.Load import EMPTY_DICT, csvPeriod
from .ValidateCubes import validateCompleteCube
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlCollectionType, XbrlUnitType
from .XbrlConst import (xbrl, qnXbrlReferenceObj, qnXbrlLabelObj, qnXbrlAbstractObj, qnXbrlConceptObj,
                        qnXbrlMemberObj, qnXbrlEntityObj, qnXbrlUnitObj, qnXbrlImportTaxonomyObj,
                        qnXbrliCollection, reservedPrefixNamespaces, qnXbrlLabelObj, qnXbrlPropertyObj,
                        qnXbrlDimensionObj)
from .XbrlCube import (XbrlCube, XbrlCubeType, baseCubeTypes, XbrlCubeDimension,
                       periodCoreDim, conceptCoreDim, entityCoreDim, unitCoreDim, languageCoreDim, coreDimensions,
                    conceptDomainClass, entityDomainClass, unitDomainClass, languageDomainClass,
                    defaultCubeType, reportCubeType, timeSeriesCubeType,
                    timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, excludedIntervalsPropType,
                    periodConstraintPeriodPattern)
from .XbrlDimension import XbrlDimension, XbrlDomain, XbrlDomainClass, XbrlMember, xbrlMemberObj
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
from .XbrlFact import XbrlFact, XbrlFootnote, XbrlTableTemplate
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

perCnstrtFmtStartEndPattern = re.compile(r".*@(start|end)")
def validateCompiledModel(compMdl):
    """Validate the compiled model as a whole, after all modules have been validated and combined into the compiled model.
        This is for checks that require the whole model to be available, such as checking for duplicate labels across modules.
    """

    compMdl.errorCatalog = get_error_catalog()

    mdlLvlChecks = attrdict(
        labelsCt = defaultdict(list), # count of duplicated labels by relatedName, labelType and language
    )

    for module in compMdl.xbrlModels.values():
        validateXbrlModule(compMdl, module, mdlLvlChecks)

    validateCompletedModel(compMdl)

    # model lavel checks
    for lblKey, lblObjs in mdlLvlChecks.labelsCt.items():
        if len(lblObjs) > 1:
            emit_error(compMdl, "oimte:duplicateLabelObject",
                       _("The labels are duplicated for relatedName %(name)s type %(type)s language %(language)s"),
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
        "parentName": getattr(contextObj, 'name', '?'),
        "propName": propName,
        "qnRef": qnRef,
    }
    if errorArgs:
        messageArgs.update(errorArgs)

    # Resolve QName to object
    resolvedObj = compMdl.namedObjects.get(qnRef)

    if not resolvedObj:
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
    for i, propObj in enumerate(getattr(obj, "properties", ())):
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
                compMdl.error("oimte:invalidQNameReference",
                          _("%(parentObjName)s %(parentName)s property %(name)s has invalid property type object %(propertyType)s"),
                          file=oimFile, parentObjName=objType(obj), parentName=parentName,
                          name=propTypeQn, propertyType=propTypeQn)
        else: # have property type object
            if propTypeObj.allowedObjects:
                if xbrlObjectQNames.get(type(obj)) not in propTypeObj.allowedObjects:
                    compMdl.error("oimte:disallowedObjectProperty",
                              _("%(parentObjName)s %(parentName)s property %(name)s not an allowed property type for the object."),
                              file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                              name=propTypeQn)
            propObj._xValid, propObj._xValue = validateValue(compMdl, module, obj, propObj.value, propTypeObj.dataType, f"/properties[{i}]", "oimte:propertyValueDataTypeMismatch")

            propTypeQns[propTypeQn].add(propObj._xValue)
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
    for cubeObj in module.cubes:
        assertObjectType(compMdl, cubeObj, XbrlCube)
        name = cubeObj.name
        cubeType = validateQNameReference(compMdl, cubeObj, "cubeType", XbrlCubeType,
                                         invalidTypeMsgCode="oimte:invalidObjectType",
                                         qnRef=(cubeObj.cubeType or reportCubeType))
        if cubeType is None:
            continue # can't do further checks without cube type
        isTimeSeriesCubeType = cubeType and cubeType.name == timeSeriesCubeType
        isNegativeCubeType = cubeType and cubeType.name.localName == "negativeCube"
        isReferenceCubeType = cubeType and cubeType.name.localName == "referenceCube"

        if cubeObj.extendTargetName:
            extendCubeObj = validateQNameReference(compMdl, cubeObj, "extendTargetName", XbrlCube,
                                                   invalidTypeMsgCode="oimte:invalidObjectType")
            if isinstance(extendCubeObj, XbrlCube) and not extendCubeObj.isExtensible:
                compMdl.error("oimte:cannotExtendObject",
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
            relConstraintNetworkMatches = defaultdict(int)
            for ntwk in ntwks:
                matchingConstrs = [c for c in cubeNtwkConstrs if c.relationshipType == ntwk.relationshipTypeName]
                ntwkMatchedConstraints = set()
                for relObj in ntwk.relationships:
                    if not matchingConstrs:
                        if getattr(cubeNtwkConstrObj, "closed", False):
                            compMdl.error("oimte:invalidCubeNetworkRelationship",
                                          _("Cube %(name)s has network %(network)s with relationship type %(relationshipType)s which is not allowed by cubeNetworkConstraints."),
                                          xbrlObject=(cubeObj, ntwk, relObj), name=name, network=ntwk.name, relationshipType=ntwk.relationshipTypeName)
                        continue
                    if all(cnst.maxNetworks == 0 for cnst in matchingConstrs):
                        continue
                    relSObj = compMdl.namedObjects.get(relObj.source)
                    relTObj = compMdl.namedObjects.get(relObj.target)
                    relMatched = False
                    for cnst in matchingConstrs:
                        # Endpoint checks are irrelevant when maxNetworks is explicitly 0.
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

                if isReferenceCubeType and ntwk.relationshipTypeName.namespaceURI == xbrl and ntwk.relationshipTypeName.localName == "period-refDimension":
                    compMdl.error("oimte:invalidCubeRelationship",
                                  _("Reference cube %(name)s MUST NOT use period-refDimension networks."),
                                  xbrlObject=(cubeObj, ntwk), name=name)

            for cnst in cubeNtwkConstrs:
                if cnst.maxNetworks == 0:
                    continue
                matchedNtws = relConstraintNetworkMatches.get(cnst, 0)
                if cnst.minNetworks is not None and matchedNtws < cnst.minNetworks:
                    compMdl.error("oimte:missingRequiredRelationship",
                                  _("Cube %(name)s is missing required relationships for relationshipType %(relationshipType)s."),
                                  xbrlObject=cubeObj, name=name, relationshipType=cnst.relationshipType)

        dimQnCounts = {}
        for cubeDimObj in cubeObj.cubeDimensions:
            dimQn = cubeDimObj.dimensionName
            dimObj = validateQNameReference(compMdl, cubeDimObj, "dimensionName", XbrlDimension,
                                            invalidTypeMsgCode="oimte:invalidObjectType")
            if dimObj:
                # specific cubeType dimension property validations
                tsProps = {timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, excludedIntervalsPropType} & set(p.property for p in dimObj.properties)
                if tsProps:
                    if cubeType and cubeType.name != timeSeriesCubeType:
                        compMdl.error("oimte:timeSeriesTypeOnNonTimeSeriesDimension" if timeSeriesPropType in tsProps else
                                      "oimte:intervalConventionOnNonTimeSeriesDimension" if intervalConventionPropType in tsProps else
                                      "oimte:intervalOfMeasurementOnNonTimeSeriesDimension",
                                  _("The dimension %(dimension)s properties %(tsProps)s on cube %(name)s type %(cubeType)s MUST only be used on a timeSeries cubeType."),
                                  xbrlObject=cubeObj, name=name, dimension=dimQn, cubeType=cubeType.name, tsProps=", ".join(sorted(str(p) for p in tsProps)))
                    elif cubeDimObj.domainDataType:
                        dimDomDTQn = cubeDimObj.domainDataType
                        domDTobj = compMdl.namedObjects.get(dimDomDTQn)
                        if not (isinstance(compMdl.namedObjects.get(dimDomDTQn), XbrlDataType) or
                                domDTobj.instanceOfType(qnXsDateTime, compMdl)):
                            compMdl.error("oimte:timeSeriesTypeOnNonTimeSeriesDimension",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s properties %(tsProps)s on cube %(name)s MUST only be used on a date-time typed dimension."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn, tsProps=", ".join(sorted(str(p) for p in tsProps)))
                        if len(tsProps & {intervalOfMeasurementPropType, intervalConventionPropType}) == 1:
                            compMdl.error("oimte:missingIntervalOfMeasurementForConvention",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s on cube %(name)s MUST also have property %(tsProp)s."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn,
                                      tsProp=next(iter({intervalOfMeasurementPropType, intervalConventionPropType} - tsProps)))
            dimQnCounts[dimQn] = dimQnCounts.get(dimQn, 0) + 1
        if any(c > 1 for c in dimQnCounts.values()):
            compMdl.error("oimte:duplicateDimensionsInCube",
                      _("The cubeDimensions of cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      xbrlObject=cubeObj, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items() if ct > 1))
        # check cube dims against cube type
        if cubeType.basemostCubeType != defaultCubeType and conceptCoreDim not in dimQnCounts.keys():
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
        txmyDefDimsQNs = set(dim for dim in dimQnCounts.keys() if dim.namespaceURI != xbrl)
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
                for dim in txmyDefDims:
                    if ((not allwdDimConstr.dimensionName or dim.name == allwdDimConstr.dimensionName)):
                        matchedDim = dim
                        matchedDimQNs.add(dim.name)
                        break
                if not matchedDim and allwdDimConstr.required:
                    compMdl.error("oimte:requiredCubeDimensionalSpaceMissingFromCube",
                                _("The cube %(name)s, type %(cubeType)s, taxonomy defined dimensions %(dimension)s is missing"),
                                xbrlObject=cubeObj, name=name, cubeType=cubeType.name,
                                dimension=', '.join(str(getattr(allwdDim,p)) for p in ("dimensionName", "dimensionType", "dimensionDataType") if getattr(allwdDim,p)))
            disallowedDims = txmyDefDimsQNs - matchedDimQNs
            if cubeDimsClosed and disallowedDims:
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
                        for r in ntwk.relationships)):
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

        validateProperties(compMdl, oimFile, module, cubeObj)
        unitDataTypeQNs = set()
        conceptDataTypeQNs = set()
        hasConceptDimension = False
        hasTimeseriesDimension = False
        timeSeriesTaxonomyDims = []
        for iCubeDim, cubeDimObj in enumerate(cubeObj.cubeDimensions):
            assertObjectType(compMdl, cubeDimObj, XbrlCubeDimension)
            dimName = cubeDimObj.dimensionName
            dimObj = validateQNameReference(compMdl, cubeDimObj, "dimensionName", XbrlDimension,
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
            if allowedCubeDimConstrs and not isTimeSeriesCubeType:
                matchedConstr = None
                for dimConstr in allowedCubeDimConstrs:
                    if dimConstr.dimensionName and dimConstr.dimensionName != dimName:
                        continue
                    if dimConstr.type:
                        dimConstrIsTyped = dimConstr.type == "typed"
                        dimObjIsTyped = bool(domClass.allowedDomainItems and all(
                            isinstance(compMdl.namedObjects.get(dt), XbrlDataType)
                            for dt in domClass.allowedDomainItems))
                        if dimConstrIsTyped != dimObjIsTyped:
                            continue
                    if dimConstr.dataType:
                        if cubeDimObj.domainDataType and dimConstr.dataType != cubeDimObj.domainDataType:
                            continue
                    matchedConstr = dimConstr
                    break
                reqProps = getattr(getattr(matchedConstr, "domainClassProperties", None), "requiredProperties", None)
                if reqProps:
                    domainPropQNs = set(p.property for p in getattr(domClass, "properties", ()))
                    missingReqProps = [p for p in reqProps if p not in domainPropQNs]
                    if missingReqProps:
                        compMdl.error("oimte:missingRequiredDimensionProperty",
                                      _("Cube %(name)s taxonomy-defined dimension %(dimensionName)s domainClass %(domainClass)s is missing required properties %(requiredProperties)s."),
                                      xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name,
                                      dimensionName=cubeDimObj.dimensionName, domainClass=domClass.name,
                                      requiredProperties=", ".join(str(p) for p in missingReqProps))
            if domClass.allowedDomainItems and all(
                    isinstance(compMdl.namedObjects.get(dt), XbrlDataType)
                    for dt in domClass.allowedDomainItems):
                isTyped = True
            if isTyped and qnXsDateTime in domClass.allowedDomainItems:
                hasTimeseriesDimension = True
            cubeDimDT = cubeDimObj.domainDataType
            if cubeDimDT:
                domDtObj = validateQNameReference(compMdl, cubeDimObj, "domainDataType", XbrlDataType,
                                              msgCode="oimte:propertyValueDataTypeMismatch", qnRef=cubeDimDT)
                if domDtObj is not None:
                    isTyped = True
                    if domClass.allowedDomainItems and cubeDimDT not in domClass.allowedDomainItems:
                        compMdl.error("oimte:invalidDataTypeForDomainClass",
                                      _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST be included in the set of allowedDomainItems defined as a property of the domain root object: %(allowedDataItems)s."),
                                      xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT, allowedDataItems=", ".join(str(qn) for qn in domClass.allowedDomainItems))
                    if dimName == periodCoreDim:
                        compMdl.error("oimte:domainUsedOnPeriodDimension",
                                      _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST not be used on a period dimension."),
                                      xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT)
                    elif dimName == conceptCoreDim:
                        compMdl.error("oimte:invalidConceptDomain",
                                      _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST not be used on a concept dimension."),
                                      xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT)
            hasValidDomainName = False
            if cubeDimObj.domainName:
                if isTyped:
                    if dimName == periodCoreDim:
                        compMdl.error("oimte:domainUsedOnPeriodDimension",
                                  _("Cube %(name)s dimension %(dimensionName)s domain objects MUST NOT be defined with a domainName property."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                    else:
                        compMdl.error("oimte:invalidCubeDimensionDomainName",
                                  _("Cube %(name)s dimension %(dimensionName)s domain objects MUST NOT be defined with a typed domainClass object."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                cubeDomObj = compMdl.namedObjects.get(cubeDimObj.domainName)
                if isinstance(cubeDomObj, XbrlDomain):
                    hasValidDomainName = True
                else:
                    if dimName not in coreDimensions and allowedCubeDimConstrs:
                        compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                                  _("Cube %(name)s taxonomy-defined dimension %(dimensionName)s does not satisfy cubeType dimension constraints."),
                                  xbrlObject=(cubeObj, cubeDimObj), name=name, dimensionName=dimName)
                    else:
                        compMdl.error("oimte:invalidCubeDimensionDomainName",
                                  _("Cube %(name)s domainName property MUST identify a domain object: %(domainName)s."),
                                  xbrlObject=cubeObj, name=name, domainName=cubeDimObj.domainName)
            if cubeDimObj.periodConstraints and dimName != periodCoreDim:
                compMdl.error("oimte:invalidPeriodConstraintDimension",
                          _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)
            if dimName == conceptCoreDim:
                hasConceptDimension = True
            if dimName == conceptCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), (XbrlConcept, XbrlAbstract)) and relObj.source != conceptDomainClass:
                        compMdl.error("oimte:invalidRelationshipSourceObject",
                                  _("Cube %(name)s conceptConstraints domain relationships must be from concepts, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if isinstance(compMdl.namedObjects.get(relObj.target,None), XbrlConcept):
                        conceptDataTypeQNs.add(compMdl.namedObjects[relObj.target].dataType)
                if cubeDimObj.allowDomainFacts:
                    compMdl.error("oimte:invalidAllowDomainFactsPropertyOnConceptDimension",
                              _("Cube %(name)s conceptConstraints property MUST NOT specify allowDomainFacts."),
                              xbrlObject=(cubeObj,cubeDimObj), name=name)
            if dimName == entityCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), XbrlEntity) and relObj.source != entityDomainClass:
                        compMdl.error("oimte:invalidRelationshipSourceObject",
                                  _("Cube %(name)s entityConstraints domain relationships must be from entities, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
            if dimName == unitCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), XbrlUnit) and relObj.source != unitDomainClass:
                        compMdl.error("oimte:invalidRelationshipSourceObject",
                                  _("Cube %(name)s unitConstraints domain relationships must be from units, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
            if dimName in (periodCoreDim, languageCoreDim) and hasValidDomainName:
                compMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s dimension %(qname)s must not specify domain %(domain)s."),
                          xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName, domain=cubeDimObj.domainName)
            if dimName not in coreDimensions and isinstance(compMdl.namedObjects.get(dimName), XbrlDimension):
                timeSeriesTaxonomyDims.append((cubeDimObj, dimObj, isTyped, cubeDimDT, domClass))
                if not isTyped: # explicit
                    domObj = compMdl.namedObjects.get(cubeDimObj.domainName)
                    if isinstance(domObj, XbrlDomain):
                        for relObj in domObj.relationships:
                            if not isinstance(compMdl.namedObjects.get(getattr(relObj, "target", None),None), (XbrlConcept, XbrlAbstract, XbrlUnit, XbrlMember)):
                                compMdl.error("oimte:invalidDomainRelationshipTarget",
                                          _("Cube %(name)s explicit dimension domain relationships must be to members."),
                                          xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName)
                        if dimObj.domainClass and domObj.root and dimObj.domainClass != domObj.root:
                            compMdl.error("oimte:invalidCubeDimensionDomainName",
                                      _("Cube %(name)s explicit dimension domain root %(domClass)s does not match dimension domainClass %(dimRoot)s."),
                                      xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName, domClass=domObj.root, dimRoot=dimObj.domainClass)
            if not isTyped: # explicit dimension
                if cubeDimObj.typedSort is not None:
                    compMdl.error("oimte:invalidTypedSortOnExplicitDomain",
                              _("Cube %(name)s typedSort property MUST not be used on an explicit dimension."),
                              xbrlObject=cubeObj, name=name)
            if dimName == periodCoreDim:
                for iPerConst, perConstObj in enumerate(cubeDimObj.periodConstraints):
                    if perConstObj.periodType not in ("instant", "duration", "none"):
                        compMdl.error("oimte:invalidPeriodRepresentation",
                                  _("Cube %(name)s period constraint periodType property MUST be \"instant\" or \"duration\"."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
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
                        compMdl.error("oimte:invalidPeriodRepresentation",
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
        if not hasConceptDimension and not getattr(cubeObj, 'extendTargetName', None):
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
            cubeDimByName = {cd.dimensionName: cd for cd in cubeObj.cubeDimensions}
            for reqDim, reqDomClass in coreDomainClassByDimension.items():
                if reqDomClass in coreDomainClasses:
                    cubeDimObj = cubeDimByName.get(reqDim)
                    if cubeDimObj is not None and not cubeDimObj.domainName:
                        compMdl.error("oimte:missingCoreDomainNameFromCubeDimension",
                                      _("Cube %(name)s dimension %(dimensionName)s MUST specify domainName because cubeType %(cubeType)s requires coreDomainClass %(domainClass)s."),
                                      xbrlObject=(cubeObj, cubeDimObj), name=name, dimensionName=reqDim, cubeType=cubeType.name, domainClass=reqDomClass)

        if isTimeSeriesCubeType:
            typedDateTimeDims = []
            for cubeDimObj, dimObj, isTyped, cubeDimDT, domClass in timeSeriesTaxonomyDims:
                hasDateTimeType = cubeDimDT == qnXsDateTime or qnXsDateTime in getattr(domClass, "allowedDomainItems", ())
                if isTyped and hasDateTimeType:
                    typedDateTimeDims.append((cubeDimObj, dimObj))
                else:
                    compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                                  _("Timeseries cube %(name)s taxonomy-defined dimension %(dimensionName)s MUST be typed xs:dateTime."),
                                  xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name, dimensionName=cubeDimObj.dimensionName)
            if len(typedDateTimeDims) != 1:
                compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                              _("Timeseries cube %(name)s MUST have exactly one typed taxonomy-defined dimension."),
                              xbrlObject=cubeObj, name=name)

            if allowedCubeDimConstrs:
                for cubeDimObj, dimObj, _isTyped, _cubeDimDT, domClass in timeSeriesTaxonomyDims:
                    matchedConstr = None
                    for dimConstr in allowedCubeDimConstrs:
                        if dimConstr.dimensionName and dimConstr.dimensionName != cubeDimObj.dimensionName:
                            continue
                        if dimConstr.type:
                            isTypedConstr = dimConstr.type == "typed"
                            if isTypedConstr != _isTyped:
                                continue
                        if dimConstr.dataType:
                            actualDataType = cubeDimObj.domainDataType
                            if actualDataType is None and _isTyped and qnXsDateTime in getattr(domClass, "allowedDomainItems", ()):
                                actualDataType = qnXsDateTime
                            if dimConstr.dataType != actualDataType:
                                continue
                        matchedConstr = dimConstr
                        break
                    if matchedConstr is None:
                        compMdl.error("oimte:invalidTaxonomyDefinedDimension",
                                      _("Cube %(name)s taxonomy-defined dimension %(dimensionName)s does not satisfy cubeType constraints."),
                                      xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name, dimensionName=cubeDimObj.dimensionName)
                    else:
                        reqProps = getattr(getattr(matchedConstr, "domainClassProperties", None), "requiredProperties", None)
                        if reqProps:
                            domainPropQNs = set(p.property for p in getattr(domClass, "properties", ()))
                            missingReqProps = [p for p in reqProps if p not in domainPropQNs]
                            if missingReqProps:
                                compMdl.error("oimte:missingRequiredDimensionProperty",
                                              _("Cube %(name)s taxonomy-defined dimension %(dimensionName)s domainClass %(domainClass)s is missing required properties %(requiredProperties)s."),
                                              xbrlObject=(cubeObj, cubeDimObj, dimObj), name=name,
                                              dimensionName=cubeDimObj.dimensionName, domainClass=domClass.name,
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
    for dimObj in module.dimensions:
        assertObjectType(compMdl, dimObj, XbrlDimension)
        for cubeTypeQn in dimObj.cubeTypes:
            validateQNameReference(compMdl, dimObj, "cubeTypes", XbrlCubeType, qnRef=cubeTypeQn)
        domRtObj = validateQNameReference(compMdl, dimObj, "domainClass", XbrlDomainClass, msgCode="oimte:invalidDomainClass")
        if (dimObj.domainClass in (conceptDomainClass, entityDomainClass, unitDomainClass, languageDomainClass) and
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
    for domObj in module.domains:
        assertObjectType(compMdl, domObj, XbrlDomain)
        extendTargetObj = None
        extendedDomClassQn = None
        if domObj.extendTargetName:
            extendTargetObj = validateQNameReference(compMdl, domObj, "extendTargetName", XbrlDomain)
            if extendTargetObj is not None:
                if getattr(domObj, "_extendResolved", False):
                    extendTargetObj = None # don't extend, already been extended
                elif not getattr(extendTargetObj, "isExtensible", True):
                    compMdl.error("oimte:cannotExtendCompleteDomain",
                            _("The domain %(name)s cannot be extended because it is a completeDomain."),
                            xbrlObject=domObj, name=extendTargetObj.name)
                    continue
                else:
                    domObj._extendResolved = True
                    extendedDomClassQn = getattr(extendTargetObj, "root", None)
        elif not domObj.name:
            compMdl.error("oimte:missingRequiredProperty",
                      _("The domain object MUST have either a name or an extendTargetName, not neither."),
                      xbrlObject=domObj)
        domRtObj = validateQNameReference(compMdl, domObj, "root", XbrlDomainClass, qnDefault=extendedDomClassQn, msgCode="oimte:invalidDomainClass")
        if not domRtObj:
            continue
        domRtQn = domRtObj.name
        domRelCts = {}
        domRelRoots = set(relObj.source for relObj in domObj.relationships if getattr(relObj, "source", None))
        domClassSourceInRel = domRtObj is not None # only check if there are any relationships
        for i, relObj in enumerate(domObj.relationships):
            if i == 0:
                domClassSourceInRel = False
            assertObjectType(compMdl, relObj, XbrlRelationship)
            src = getattr(relObj, "source", None)
            tgt = getattr(relObj, "target", None)
            if src not in compMdl.namedObjects or tgt not in compMdl.namedObjects:
                if src not in compMdl.namedObjects:
                    validateQNameReference(compMdl, relObj, "source", qnRef=src,
                                           undefinedMessage=_("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be an object in the taxonomy model."),
                                           errorArgs={"name": domObj.name, "nbr": i, "source": src})
                if tgt not in compMdl.namedObjects:
                    validateQNameReference(compMdl, relObj, "target", qnRef=tgt,
                                           undefinedMessage=_("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an object in the taxonomy model."),
                                           errorArgs={"name": domObj.name, "nbr": i, "target": tgt})
            else:
                if domRtQn == conceptDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], (XbrlConcept, XbrlAbstract)):
                        compMdl.error("oimte:invalidDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s MUST be a concept object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                if domRtQn == entityDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], XbrlEntity):
                        compMdl.error("oimte:invalidDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the entity root or an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(compMdl.namedObjects[relObj.target], XbrlEntity):
                        compMdl.error("oimte:invalidDomainRelationshipTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                if domRtQn == unitDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], XbrlUnit):
                        compMdl.error("oimte:invalidDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the unit root or an unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(compMdl.namedObjects[relObj.target], XbrlUnit):
                        compMdl.error("oimte:invalidDomainRelationshipTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be a unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                elif isinstance(compMdl.namedObjects[relObj.source], XbrlUnit) or isinstance(compMdl.namedObjects[relObj.target], XbrlUnit):
                    compMdl.error("oimte:invalidDomainObject",
                              _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, or target, %(target)s, MUST be not be unit objects in the taxonomy model."),
                              xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source, target=relObj.target)
                for prop in ("source", "target"):
                    obj = compMdl.namedObjects[getattr(relObj, prop)]
                    if isinstance(obj, XbrlMember) and domRtQn in (conceptDomainClass, unitDomainClass, entityDomainClass, languageDomainClass):
                        compMdl.error("oimte:invalidDimensionMember",
                                  _("The domain %(name)s relationship[%(nbr)s] %(property)s, %(propQn)s MUST be not be a member object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, property=prop, propQn=getattr(relObj, prop))
                    if domRtObj and domRtObj.allowedDomainItems and (
                        xbrlObjectQNames.get(type(obj)) not in domRtObj.allowedDomainItems
                        and (prop != "source" and obj != domRtObj)):
                        compMdl.error("oimte:invalidDomainObject",
                                  _("The domain %(name)s relationship[%(nbr)s] %(property)s, %(propQn)s MUST be only be objects in the allowedDomainItems."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, property=prop, propQn=getattr(relObj, prop))
            if isinstance(compMdl.namedObjects.get(tgt), XbrlDomainClass):
                compMdl.error("oimte:invalidDomainRelationshipTarget",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domainClass object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            elif isinstance(compMdl.namedObjects.get(tgt), XbrlDomain):
                compMdl.error("oimte:invalidObjectType",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domain object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            elif extendTargetObj is not None:
                extendTargetObj.relationships.add(relObj)
            if tgt == domRtQn:
                compMdl.error("oimte:invalidDomainRelationshipTarget",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be the domain root object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            if domRtQn == src:
                domClassSourceInRel = True
            relKey = (src, tgt)
            domRelCts[relKey] = domRelCts.get(relKey, 0) + 1
            domRelRoots.discard(tgt) # remove any target from roots
        if any(ct > 1 for relKey, ct in domRelCts.items()):
            compMdl.error("oimte:duplicateItemsInSet",
                      _("The domain %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=domObj, name=domObj.name,
                      names=", ".join(f"{relKey[0]}\u2192{relKey[1]}" for relKey, ct in domRelCts.items() if ct > 1))
        if domRtObj and not domClassSourceInRel:
            compMdl.error("oimte:missingDomainClassSource",
                      _("The domain %(name)s root %(qname)s MUST be a source in a relationship"),
                      xbrlObject=domObj, name=domObj.name, qname=domObj.root)
        if len(domRelRoots) > 1:
            compMdl.error("oimte:multipleDomainClasses",
                      _("The domain %(name)s relationship must resolve to a single root object, multiple found: %(roots)s"),
                      xbrlObject=domObj, name=domObj.name, roots=", ".join(sorted(str(r) for r in domRelRoots)))
        validateProperties(compMdl, oimFile, module, domObj)


    # DomainClass Objects
    for domRtObj in module.domainClasses:
        assertObjectType(compMdl, domRtObj, XbrlDomainClass)
        name = domRtObj.name
        for allwdDomItemQn in (domRtObj.allowedDomainItems or ()):
            allwdDomItemObj = compMdl.namedObjects.get(allwdDomItemQn)
            if allwdDomItemQn not in (qnXbrlMemberObj, qnXbrlAbstractObj, qnXbrlConceptObj, qnXbrlEntityObj, qnXbrlUnitObj) and not isinstance(allwdDomItemObj, XbrlDataType):
                compMdl.error("oimte:invalidPropertyValue",
                  _("DomainClass %(name)s allowedDomainItem must be a member, xbrl object, or a dataType object %(allowedDomainItem)s."),
                  xbrlObject=domRtObj, name=name, allowedDomainItem=allwdDomItemQn)
        validateProperties(compMdl, oimFile, module, domRtObj)

    # Entity Objects
    for entityObj in module.entities:
        assertObjectType(compMdl, entityObj, XbrlEntity)
        validateProperties(compMdl, oimFile, module, entityObj)

    # GroupContent Objects
    for grpCntObj in module.groupContents:
        assertObjectType(compMdl, grpCntObj, XbrlGroupContent)
        grpQn = grpCntObj.groupName
        validateQNameReference(compMdl, grpCntObj, "groupName", XbrlGroup,
                               msgCode="oimte:invalidGroupObject",
                               invalidTypeMsgCode="oimte:invalidGroupObject",
                               undefinedMessage=_("The groupContent object groupName QName %(name)s MUST be a valid group object in the taxonomy model"),
                               invalidTypeMessage=_("The groupContent object groupName QName %(name)s MUST be a valid group object in the taxonomy model"),
                               errorArgs={"name": grpQn}, qnRef=grpQn)
        for relName in grpCntObj.relatedNames:
            validateQNameReference(compMdl, grpCntObj, "relatedNames",
                                   (XbrlNetwork, XbrlCube, XbrlTableTemplate, XbrlDomain, XbrlLayout),
                                   msgCode="oimte:invalidGroupObject",
                                   invalidTypeMsgCode="oimte:invalidGroupObject",
                                   undefinedMessage=_("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects, table template objects or layout objects."),
                                   invalidTypeMessage=_("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects, table template objects or layout objects."),
                                   errorArgs={"name": grpQn, "relName": relName}, qnRef=relName)

    # Label Objects
    for lblObj in module.labels:
        assertObjectType(compMdl, lblObj, XbrlLabel)
        relatedName = lblObj.relatedName
        relatedObj = None
        if relatedName in compMdl.namedObjects:
            relatedObj = compMdl.namedObjects.get(relatedName)
        elif relatedName in xbrlObjectTypes:
            relatedObj = relatedName
        else:
            compMdl.error("oimte:invalidQNameReference",
                      _("Label has invalid related object %(relatedName)s"),
                      xbrlObject=lblObj, relatedName=relatedName)
        lblTpObj = validateQNameReference(compMdl, lblObj, "labelType", XbrlLabelType)
        if lblTpObj:
            if lblTpObj.allowedObjects and relatedObj is not None and not any(
                type(relatedObj) == xbrlObjectTypes[allowedObj] for allowedObj in lblTpObj.allowedObjects):
                compMdl.error("oimte:invalidAllowedObject",
                          _("Label has disallowed related object %(relatedName)s"),
                          xbrlObject=lblObj, relatedName=relatedName)
            lblObj._xValid, lblObj._xValue = validateValue(compMdl, module, lblObj, lblObj.value, lblTpObj.dataType, "", "oimte:propertyValueDataTypeMismatch")
        validateProperties(compMdl, oimFile, module, lblObj)
        lblKey = (relatedName, lblObj.labelType, lblObj.language)
        mdlLvlChecks.labelsCt[lblKey].append(lblObj)

    # Network, PropertyType and RelationshipType Objects
    validateNetworkFamily(compMdl, module, oimFile, **familyKwargs)

    # Reference Objects
    refsWithInvalidRelName = []
    refInvalidNames = []
    refsDup = defaultdict(list)
    for refObj in module.references:
        assertObjectType(compMdl, refObj, XbrlReference)
        name = refObj.name
        lang = refObj.language
        refTp = refObj.referenceType
        extName = refObj.extendTargetName
        for relName in refObj.relatedNames:
            if relName not in compMdl.namedObjects:
                refsWithInvalidRelName.append(refObj)
                refInvalidNames.append(relName)
        if refTp or not extName:
            validateQNameReference(compMdl, refObj, "referenceType", XbrlReferenceType,
                                   undefinedMessage=_("The reference %(name)s reference %(qname)s MUST be a referenceType object."),
                                   invalidTypeMessage=_("The reference %(name)s reference %(qname)s MUST be a referenceType object."),
                                   errorArgs={"name": name, "qname": refTp}, qnRef=refTp)
        if extName:
            if name:
                compMdl.error("oimte:referenceNameRedefined",
                          _("Referencehas both extendTargetName and name %(name)s"),
                          xbrlObject=refObj, name=extName)
            else:
                extRefObjs = compMdl.tagObjects.get(extName) or ()
                if not all(isinstance(extRefObj, XbrlReference) for extRefObj in extRefObjs):
                    compMdl.error("oimte:invalidQNameReference",
                              _("Reference extendTargetName must be a reference object %(name)s"),
                              xbrlObject=refObj, name=extName)
                elif not any(extRefObj.referenceType == refTp for extRefObj in extRefObjs):
                    compMdl.error("oimte:referenceTypeRedefined",
                              _("Reference extendTargetName reference object %(name)s must have same referenceType %(referenceType)s"),
                              xbrlObject=refObj, name=extName, referenceType=refTp)
            if lang:
                compMdl.error("oimte:referenceLanguageRedefined",
                          _("Referencehas both extendTargetName and language: %(name)s"),
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
    for lblObj in module.labelTypes:
        assertObjectType(compMdl, lblObj, XbrlLabelType)
        dataTypeObj = compMdl.namedObjects.get(lblObj.dataType)
        if not isinstance(dataTypeObj, XbrlDataType):
            compMdl.error("oimte:invalidDataTypeObject",
                      _("The labelType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                      xbrlObject=lblObj, name=lblObj.name, qname=lblObj.dataType)
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
    for refObj in module.referenceTypes:
        assertObjectType(compMdl, refObj, XbrlReferenceType)
        for allowedObj in (refObj.allowedObjects or ()):
            if allowedObj not in referencableObjectTypes:
                compMdl.error("oimte:invalidObjectType",
                          _("The referenceType %(name)s allowedObject %(allowedObject)s MUST be a referenceable taxonomy model object."),
                          xbrlObject=refObj, name=refObj.name, allowedObject=allowedObj)
        for prop, msgCode in (("orderedProperties","oimte:invalidOrderedProperty"),
                              ("requiredProperties","oimte:invalidRequiredProperty")):
            for propTpQn in getattr(refObj, prop):
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
    for unitObj in module.units:
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

        unitObj._unitsMeasures = [parseUnitString(uStr, unitObj, module, compMdl) for uStr in unitObj.compositeUnitRepresentation]
        for uMeas in unitObj._unitsMeasures:
            if any(m == name for md in uMeas for m in md):
                compMdl.error("oimte:invalidPropertyValue",
                          _("The unit %(name)s must not contain itself as a measure."),
                          xbrlObject=unitObj, name=unitObj.name)
            for md in uMeas:
                for m in md:
                    if m not in compMdl.namedObjects:
                        compMdl.error("oimte:invalidQNameReference",
                                  _("The unit %(name)s measure %(measure)s must exist in the taxonomy model."),
                                  xbrlObject=unitObj, name=unitObj.name, measure=m)

    # ModelType Objects
    for mdlTpObj in module.modelTypes:
        assertObjectType(compMdl, mdlTpObj, XbrlModelType)
        for allowedObjQn in (mdlTpObj.allowedObjects or ()):
            if allowedObjQn not in xbrlObjectTypes:
                compMdl.error("oimte:invalidAllowedObject",
                          _("The modelType %(name)s has an invalid allowed object %(allowedObj)s"),
                          xbrlObject=mdlTpObj, name=mdlTpObj.name, allowedObj=allowedObjQn)
        for i, reqPropQn in enumerate(mdlTpObj.requiredProperties or ()):
            validateQNameReference(compMdl, mdlTpObj, f"requiredProperties[{i+1}]", XbrlPropertyType, qnDefault=reqPropQn)

    # Facts in taxonomy
    if module.facts:
        global resolveFact, validateFactPosition
        if resolveFact is None:
            from .ValidateFacts import resolveFact, validateFactPosition
        for factPosition in module.facts:
            resolveFact(compMdl, module, factPosition)

    # Layouts in XbrlModel
    for layout in module.layouts:
        assertObjectType(compMdl, layout, XbrlLayout)

        for dataTbl in layout.dataTables:
            assertObjectType(compMdl, dataTbl, XbrlDataTable)

            for axisName, axis in (("xAxis", dataTbl.xAxis), ("yAxis", dataTbl.yAxis)):
                assertObjectType(compMdl, axis, XbrlAxis)
            if dataTbl.zAxis is not None:
                assertObjectType(compMdl, dataTbl.zAxis, XbrlAxis)

    for tblTmpl in module.tableTemplates:
        assertObjectType(compMdl, tblTmpl, XbrlTableTemplate)

        for dim in tblTmpl.factDimensions:
            if dim.localName.startswith('$'):
                colName = dim[1:]
                if colName not in tblTmpl.columns:
                    compMdl.error("oimte:tableTemplateDimensionColumnReference",
                              _("The table template dimension %(dimension)s is missing from the table template columns."),
                              xbrlObject=tblTmpl, dimension=dim)

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

    # check complete cubes
    for cubeObj in compMdl.filterNamedObjects(XbrlCube):
        if compMdl.effectiveRequiredCubes(cubeObj):
            validateCompleteCube(compMdl, cubeObj)
        # Duplicate-fact validation applies to every cube.
        from .ValidateCubes import validateCubeDuplicates
        validateCubeDuplicates(compMdl, cubeObj)
