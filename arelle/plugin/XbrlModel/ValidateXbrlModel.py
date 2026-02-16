'''
See COPYRIGHT.md for copyright information.
'''

import regex as re, dateutil
from collections import defaultdict
from decimal import Decimal
from typing import GenericAlias, _UnionGenericAlias
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
from .XbrlImportTaxonomy import XbrlImportTaxonomy, XbrlFinalTaxonomy
from .XbrlLabel import XbrlLabel, XbrlLabelType, preferredLabel
from .XbrlLayout import XbrlLayout, XbrlDataTable, XbrlAxis
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlObject import XbrlReferencableModelObject
from .XbrlProperty import XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlReport import XbrlFact, XbrlFootnote, XbrlTableTemplate
from .XbrlModule import XbrlModule, XbrlModelType, xbrlObjectTypes, referencableObjectTypes, xbrlObjectQNames
from .XbrlUnit import XbrlUnit, parseUnitString
from .XbrlConst import qnXsQName, qnXsDate, qnXsDateTime, qnXsDuration, objectsWithProperties
from arelle.FunctionFn import true
resolveFact = validateFactPosition = None

perCnstrtFmtStartEndPattern = re.compile(r".*@(start|end)")
def validateCompiledModel(compMdl):

    mdlLvlChecks = attrdict(
        labelsCt = defaultdict(list), # count of duplicated labels by relatedName, labelType and language
    )

    for module in compMdl.xbrlModels.values():
        validateXbrlModule(compMdl, module, mdlLvlChecks)

    validateCompletedModel(compMdl)

    # model lavel checks
    for lblKey, lblObjs in mdlLvlChecks.labelsCt.items():
        if len(lblObjs) > 1:
            compMdl.error("oimte:duplicateLabelObject",
                      _("The labels are duplicated for relatedName %(name)s type %(type)s language %(language)s"),
                      xbrlObject=lblObjs, name=lblKey[0], type=lblKey[1], language=lblKey[2])

def objType(obj):
    clsName = type(obj).__name__
    if clsName.startswith("Xbrl"):
        return clsName[4:]
    return clsName

def assertObjectType(compMdl, obj, objType):
    if not isinstance(obj, objType):
        compMdl.error("oimte:invalidObjectType",
                  _("This %(thisType)s object was included where an %(expectedType)s object was expected."),
                  xbrlObject=obj, thisType=obj.__class__.__name__, expectedType=objType.__name__)

def validateQNameReference(compMdl, contextObj, propName, objType, msgCode=None, qnDefault=None):
    """Validate a QName reference and return resolved object or raise error.
    
    Args:
        compMdl: compiled model
        contextObj: object containing the reference (for error context)
        propName: property name where reference appears (for error message)
        objType: expected type of resolved object (XbrlConcept, XbrlDimension, etc.)
        msgCode: optional message code for error, default is "oimte:invalidQNameReference"
    
    Returns:
        Resolved object if valid and correct type, None if error raised
    """
    qnRef = getattr(contextObj, propName, None)
    if not qnRef and qnDefault:
        qnRef = qnDefault
    if not qnRef:
        compMdl.error("oime:invalidJSONStructureMissingRequiredProperty",
                      _("%(objType)s %(name)s is missing required QName reference property '%(prop)s'"),
                      xbrlObject=contextObj, objType=objType.__name__, name=getattr(contextObj, 'name', '?'), 
                      prop=propName)
        return None
    
    # Resolve QName to object
    resolvedObj = compMdl.namedObjects.get(qnRef)
    
    if not resolvedObj:
        compMdl.error(msgCode or "oimte:invalidQNameReference",
                      _("%(parentType)s %(parentName)s property %(propName)s references undefined QName '%(qnRef)s'"),
                      xbrlObject=contextObj, parentType=type(contextObj).__name__, 
                      parentName=getattr(contextObj, 'name', '?'), propName=propName, qnRef=qnRef)
        return None
    
    # Check resolved object is correct type
    if not isinstance(resolvedObj, objType):
        compMdl.error(msgCode or "oimte:invalidQNameReference",
                      _("%(parentType)s %(parentName)s property %(propName)s references '%(qnRef)s' which is %(actualType)s, expected %(expectedType)s"),
                      xbrlObject=contextObj, parentType=type(contextObj).__name__, 
                      parentName=getattr(contextObj, 'name', '?'), propName=propName, 
                      qnRef=qnRef, actualType=type(resolvedObj).__name__, expectedType=objType.__name__)
        return None
    
    return resolvedObj

def validateValue(compMdl, module, obj, value, dataTypeQn, pathElt, msgCode):
    if isinstance(dataTypeQn, QName):
        dataTypeObj = compMdl.namedObjects.get(dataTypeQn)
        if not isinstance(dataTypeObj, XbrlDataType): # validity checked in owner object validations
            return
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
    if relQn == reqQn:
        return True
    concept = compMdl.namedObjects.get(relQn)
    if isinstance(concept, XbrlConcept):
        if concept.dataType == reqQn:
            return True
    return False

def validateProperties(compMdl, oimFile, module, obj):
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
            propObj._xValid, propObj._xValue = validateValue(compMdl, module, obj, propObj.value, propTypeObj.dataType, f"/properties[{i}]", "oimte:invalidPropertyValue")

            propTypeQns[propTypeQn].add(propObj._xValue)
    if any(len(vals) > 1 for qn, vals in propTypeQns.items()):
        compMdl.error("oimte:conflictingPropertyValues",
                  _("%(parentObjName)s %(parentName)s has conflicting values for properties %(names)s"),
                  file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                  names=", ".join(str(qn) for qn, vals in propTypeQns.items() if len(vals) > 1))


def validateXbrlModule(compMdl, module, mdlLvlChecks):
    oimFile = str(module.name)
    txmyNamespace = module.name.namespaceURI
    isCompiledModel = module.modelForm == "compiled"

    # Taxonomy object
    assertObjectType(compMdl, module, XbrlModule)

    # taxonomy namespace for objects
    if module.modelType:
        modelTpObj = validateQNameReference(compMdl, module, "modelType", XbrlModelType)
        if modelTpObj:
            if modelTpObj.allowedObjects:
                allowedMdObjTypes = set(xbrlObjectTypes.get(qn) for qn in modelTpObj.allowedObjects if qn in xbrlObjectTypes)
                disallowedProps = modelTpObj.allowedObjects - set(p.property for p in module.properties)
                if disallowedProps:
                    compMdl.error("oimte:disallowedModelProperties",
                              _("The modelType %(moduleType)s does not allow properties %(propNames)s."),
                              xbrlObject=module, moduleType=module.modelType, propNames=", ".join(str(p) for p in disallowedProps))
            if modelTpObj.requiredProperties:
                missingReqProps = modelTpObj.requiredProperties - set(p.property for p in module.properties)
                if missingReqProps:
                    compMdl.error("oimte:missingRequiredModelTypeProperty",
                              _("The modelType %(moduleType)s requires properties %(propNames)s."),
                              xbrlObject=module, moduleType=module.modelType, propNames=", ".join(str(p) for p in missingReqProps))
    else:
        modelTpObj = None
    for txMdlPropName, propType in XbrlModule.propertyNameTypes():
        if isinstance(propType, GenericAlias) and issubclass(propType.__origin__, OrderedSet):
            isFirstObj = True
            for txMdlObj in getattr(module, txMdlPropName, ()):
                if isFirstObj:
                    isFirstObj = False
                    if modelTpObj and modelTpObj.allowedObjects and not isinstance(txMdlObj, tuple(allowedMdObjTypes)):
                        compMdl.error("oimte:disallowedObjectModelType",
                                  _("The modelType %(modelType)s does not allow objects of type %(objType)s in property %(propName)s."),
                                xbrlObject=module, modelType=module.modelType, objType=type(txMdlObj).__name__, propName=txMdlPropName)
                        break # forget all these object types
                # for Optional OrderedSets where the jsonValue exists, handle as propType, _keyClass and eltClass
                name = getattr(txMdlObj, "name", None)
                if isinstance(name, QName):
                    ns = name.namespaceURI
                    if ns != txmyNamespace:
                        if ns in reservedPrefixNamespaces.values():
                            compMdl.error("oimte:invalidObjectNamespacePrefix",
                                      _("The taxonomy module object %(name)s cannot have a reserved namespace URI."),
                                      xbrlObject=txMdlObj, name=name)
                        if not isCompiledModel:
                            compMdl.error("oimte:objectNamespaceMismatch",
                                      _("The taxonomy module object %(name)s does not match the namespace %(nsPrefix)s: of the module."),
                                      xbrlObject=txMdlObj, name=name, nsPrefix=module.name.prefix)
    validateProperties(compMdl, oimFile, module, module)

    for impTxObj in module.importedTaxonomies:
        assertObjectType(compMdl, impTxObj, XbrlImportTaxonomy)
        impMdlName = impTxObj.xbrlModelName
        for qnObjType in impTxObj.importObjectTypes:
            if qnObjType in xbrlObjectTypes:
                if xbrlObjectTypes[qnObjType] == XbrlLabel:
                    compMdl.error("oimte:invalidImportObjectType",
                              _("The importObjectTypes property MUST not include the label object."),
                              xbrlObject=impTxObj)
            else:
                compMdl.error("oimte:invalidQNameReference",
                          _("The importObjectTypes property MUST specify valid OIM object types, %(qname)s is not valid."),
                          xbrlObject=impTxObj, qname=qnObjType)
        if impTxObj.profiles and (impTxObj.selections or impTxObj.importObjects or impTxObj.importObjectTypes):
            compMdl.error("oimte:invalidImportTaxonomy",
                      _("The importTaxonomy %(moduleName)s profiles must only be used without selectons, importObjects or importObjectTypes."),
                      xbrlObject=impTxObj, moduleName=impMdlName)
        finalTxObj = compMdl.namedObjects.get(impMdlName)
        if isinstance(finalTxObj, XbrlFinalTaxonomy):
            def extendsFinalTaxonomy(obj):
                # check for extended objects
                if finalTxObj.finalTaxonomyFlag:
                    if isinstance(obj, XbrlReferencableModelObject) and not isinstance(obj, (XbrlFact, XbrlFootnote, XbrlEntity)):
                        compMdl.error("oimte:invalidFinalTaxonomyModification",
                                  _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due to a finalTaxonomyFlag."),
                                  xbrlObject=impTxObj, moduleName=impMdlName, qname=obj.name)
                elif finalTxObj.finalObjectTypes and xbrlObjectQNames[type(obj)] in finalTxObj.finalObjectTypes:
                    compMdl.error("oimte:invalidFinalTaxonomyObjectType",
                              _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due to it's type, %(type)s, being in finalObjectTypes."),
                              xbrlObject=impTxObj, moduleName=impMdlName, qname=obj.name, type=xbrlObjectQNames[type(obj)] )
                elif finalTxObj.finalObjects and getattr(obj, "extendTargetName", None) in finalTxObj.finalObjects:
                    compMdl.error("oimte:invalidFinalTaxonomyObject",
                              _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due to having %(name)s in finalObjects."),
                              xbrlObject=impTxObj, moduleName=impMdlName, qname=xbrlObjectQNames[type(obj)], name=obj.extendTargetName)
                elif finalTxObj.selections:
                    for i, selObj in enumerate(impTxObj.selections):
                        if xbrlObjectQNames[type(obj)] == selObj.objectType and (
                            all((eval(obj, whereObj) for whereObj in selObj.where))):
                            compMdl.error("oimte:invalidFinalTaxonomyObject",
                                      _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due matching selection %(i)s."),
                                      xbrlObject=impTxObj, moduleName=impMdlName, qname=xbrlObjectQNames[type(obj)], i=i)
                            break # selections are or'ed, don't need to try more
            module.referencedObjectsAction(compMdl, extendsFinalTaxonomy)

    # Concept Objects
    for cncpt in module.concepts:
        assertObjectType(compMdl, cncpt, XbrlConcept)
        perType = getattr(cncpt, "periodType", None)
        if perType not in ("instant", "duration", "none"):
            compMdl.error("oime:invalidPropertyValue",
                      _("Concept %(name)s has invalid period type %(perType)s"),
                      xbrlObject=cncpt, name=cncpt.name, perType=perType)
        dtObj = validateQNameReference(compMdl, cncpt, "dataType", XbrlDataType)
        if dtObj and not dtObj.isAllowedFor(cncpt):
            compMdl.error("oimte:unallowedDataTypeObject",
                      _("Concept %(name)s is not allowed for dataType %(dataType)s"),
                    xbrlObject=cncpt, name=cncpt.name, dataType=dtObj.name)
        enumDomQn = getattr(cncpt, "enumerationDomain", None)
        if enumDomQn and (enumDomQn not in compMdl.namedObjects or not isinstance(compMdl.namedObjects[enumDomQn], XbrlDomain)):
            compMdl.error("oime:invalidEnumerationDomainObject",
                      _("Concept %(name)s has invalid enumeration domain reference %(enumDomain)s"),
                      xbrlObject=cncpt, name=cncpt.name, enumDomain=enumDomQn)
        validateProperties(compMdl, oimFile, module, cncpt)

    # CubeType Objects
    for cubeType in module.cubeTypes:
        assertObjectType(compMdl, cubeType, XbrlCubeType)
        name = cubeType.name
        if cubeType.coreDimensions - coreDimensions:
            compMdl.error("oimte:invalidCoreDimension",
                      _("The cube type %(name)s, specifies QNames which are not core dimensions: %(qnames)s."),
                      xbrlObject=cubeType, name=name, qnames=", ".join(str(qn) for qn in (cubeType.coreDimensions - coreDimensions)))
        dConstrNames = {}
        if cubeType.cubeDimensionConstraints:
            for i, dConstr in enumerate(cubeType.cubeDimensionConstraints.allowed):
                if dConstr.dimensionName and not isinstance(compMdl.namedObjects.get(dConstr.dimensionName), XbrlDimension):
                    compMdl.error("oimte:invalidDimensionReference",
                              _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] dimensionName %(dimName)s does not resolve to a dimension object."),
                              xbrlObject=cubeType, name=name, i=i, dimName=dConstr.dimensionName)
                if dConstr.dimensionName in dConstrNames:
                    compMdl.error("oimte:duplicateDimension",
                              _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] dimensionName %(dimName)s duplicates cubeDimensionConstraints[%(i2)s]."),
                              xbrlObject=cubeType, name=name, i=i, dimName=dConstr.dimensionName, i2=dConstrNames[dConstr.dimensionName])
                else:
                    dConstrNames[dConstr.dimensionName] = i
                if dConstr.dataType:
                    dtObj = compMdl.namedObjects.get(dConstr.dataType)
                    if not isinstance(dtObj, XbrlDataType):
                        compMdl.error("oimte:invalidDimensionTypeReference",
                                  _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] dataType %(dataType)s does not resolve to a dataType object."),
                                  xbrlObject=cubeType, name=name, i=i, dataType=dConstr.dataType)
                    elif not dtObj.isAllowedFor(qnXbrlDimensionObj):
                        compMdl.error("oimte:unallowedDataTypeObject",
                                  _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] dataType %(dataType)s is not allowed on a dimension object."),
                                  xbrlObject=cubeType, name=name, i=i, dataType=dConstr.dataType)
                if dConstr.dataType and dConstr.type != "typed":
                    compMdl.error("oimte:invalidDimensionDataTypeProperty",
                              _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s] has a dataType which requires type must be \"typed\" but is: %(typed)s."),
                              xbrlObject=cubeType, name=name, i=i, typed=dConstr.type)
        if cubeType.cubeRelationships:
            for ra in ("required", "allowed"):
                for i, rConstr in enumerate(getattr(cubeType.cubeRelationships, ra) or ()):
                    if rConstr.type and not isinstance(compMdl.namedObjects.get(rConstr.type), XbrlRelationshipType):
                            compMdl.error(f"oimte:invalidRelationshipTypeReference",
                                      _("The cube type %(name)s, cubeRelationships/%(ra)s[%(i)s]/type, does not specify an relationshipType object: %(qname)s."),
                                      xbrlObject=cubeType, name=name, ra=ra, i=i, qname=rConstr.type)
                    for st in ("source", "target"):
                        vConstr = getattr(rConstr, st)
                        if vConstr.qname and vConstr.qname not in compMdl.namedObjects:
                            compMdl.error(f"oimte:invalid{st.title()}QName",
                                      _("The cube type %(name)s, cubeRelationships/%(ra)s[%(i)s]/%(st)s/qname, does not specify a referencable model object: %(qname)s."),
                                      xbrlObject=cubeType, name=name, ra=ra, i=i, st=st, qname=vConstr.qname)
                        if vConstr.objectType and vConstr.objectType not in referencableObjectTypes:
                            compMdl.error(f"oimte:invalid{st.title()}ObjectType",
                                      _("The cube type %(name)s, cubeRelationships/%(ra)s[%(i)s]/%(st)s/objectType, does not specify a referencable model component object: %(qname)s."),
                                      xbrlObject=cubeType, name=name, ra=ra, i=i, st=st, qname=vConstr.objectType)
                        if vConstr.dataType and not isinstance(compMdl.namedObjects.get(vConstr.dataType), XbrlDataType):
                            compMdl.error(f"oimte:invalid{st.title()}DataType",
                                      _("The cube type %(name)s, cubeRelationships/%(ra)s[%(i)s]/%(st)s/dataType, does not specify a data type object: %(qname)s."),
                                      xbrlObject=cubeType, name=name, ra=ra, i=i, st=st, qname=vConstr.dataType)
        if cubeType.cubeProperties:
            for ra in ("required", "allowed"):
                for i, propTpQn in enumerate(getattr(cubeType.cubeProperties, ra)):
                    if  not isinstance(compMdl.namedObjects.get(propTpQn), XbrlPropertyType):
                        compMdl.error(f"oimte:invalidPropertyTypeReference",
                                  _("The cube type %(name)s, cubeProperties/%(ra)s[%(i)s], does not specify valid propertyType reference: %(qname)s."),
                                  xbrlObject=cubeType, name=name, ra=ra, i=i, qname=propTpQn)
        if cubeType.baseCubeType is not None:
            if cubeType.baseCubeType not in compMdl.namedObjects:
                compMdl.error("oimte:missingQNameReference",
                          _("The cube type %(name)s, specifies base cube type %(base)s which is not defined."),
                          xbrlObject=cubeType, name=name, base=cubeType.baseCubeType)
            else:
                baseCubeType = compMdl.namedObjects.get(cubeType.baseCubeType)
                if not isinstance(baseCubeType, XbrlCubeType):
                    compMdl.error("oimte:invalidQNameReference",
                              _("The cube type %(name)s, specifies base cube type %(base)s which is not a cube type object."),
                              xbrlObject=cubeType, name=name, base=cubeType.baseCubeType)
                else:
                    # TBD: oimte:invalidCubeTypeRestriction
                    baseCoreDims = baseCubeType.effectivePropVal(compMdl, "coreDimensions")
                    if baseCoreDims and (cubeType.coreDimensions - baseCoreDims):
                        compMdl.error("oimte:coreDimensionsExpansion",
                                  _("The cube type %(name)s, expands base cube type core dimensions by %(qnames)s."),
                                  xbrlObject=cubeType, name=name, qnames=", ".join(str(qn) for qn in (cubeType.coreDimensions - baseCoreDims)))
                    baseDimConstrClosed = baseCubeType.effectivePropVal(compMdl, "cubeDimensionConstraints", "closed")
                    if cubeType.cubeDimensionConstraints:
                        if baseDimConstrClosed == True and cubeType.cubeDimensionConstraints.closed == False:
                            compMdl.error("oimte:invalidDimensionClosedExpansion",
                                      _("The cube type %(name)s, must not set cubeDimensionConstraints.closed \"false\" where base cube type is \"true\"."),
                                      xbrlObject=cubeType, name=name)
                        baseDimConstrs = baseCubeType.effectivePropVal(compMdl, "cubeDimensionConstraints", "allowed")
                        for i, dimConstr in enumerate(cubeType.cubeDimensionConstraints.allowed):
                            matchingBaseDimFound = False
                            for baseDimConst in baseDimConstrs:
                                if ((dimConstr.dimensionName and dimConstr.dimensionName == baseDimConst.dimensionName) or
                                    (dimConstr.dataType and dimConstr.dataType == baseDimConst.dataType)):
                                    matchingBaseDimFound = True
                                    if dimConstr.required == False and baseDimConst.required == True:
                                        compMdl.error("oimte:invalidDimensionRequirementRelaxation",
                                                  _("The cube type %(name)s, must not set cubeDimensionConstraints/allowed[%(i)s].required to \"false\" when derived base required for the dimension is \"true\""),
                                                  xbrlObject=cubeType, name=name, i=i)
                                    # check if a base type has a more restricted type for same dimension
                                    if dimConstr.dataType and baseDimConst.dataType:
                                        dataTypeObj = compMdl.namedObjects.get(dimConstr.dataType)
                                        if isinstance(dataTypeObj, XbrlDataType) and not dataTypeObj.instanceOfType(baseDimConst.dataType, compMdl):
                                            compMdl.error("oimte:invalidDataTypeExpansion",
                                                      _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s].dataType %(dataType)s must not be an expansion of the base data type %(baseDataType)s"),
                                                      xbrlObject=cubeType, name=name, i=i, dataType=dimConstr.dataType, baseDataType=baseDimConst.dataType)
                                    # check properties required
                                    if baseDimConst.dimensionProperties and baseDimConst.dimensionProperties.required:
                                        if dimConstr.dimensionProperties:
                                            removedPropsReqd = baseDimConst.dimensionProperties.required - dimConstr.dimensionProperties.required
                                            if removedPropsReqd:
                                                compMdl.error("oimte:missingRequiredDimensionProperty",
                                                          _("The cube type %(name)s, cubeDimensionConstraints/allowed[%(i)s].dimensionProperties must include all properties required by the baseCubeType, these are missing: %(dimensionProperties)s"),
                                                          xbrlObject=cubeType, name=name, i=i, dimensionProperties=", ".join(sorted(str(p) for p in removedPropsReqd)))
                            if baseDimConstrClosed and not matchingBaseDimFound:
                                compMdl.error("oimte:invalidDimensionAddition",
                                              _("The cube type %(name)s, must not set cubeDimensionConstraints/allowed[%(i)s] must not be added a closed base type"),
                                              xbrlObject=cubeType, name=name, i=i)
                    if cubeType.cubeRelationships:
                        baseRelReqdConstrs = baseCubeType.effectivePropVal(compMdl, "cubeRelationships", "required")
                        baseRelAlwdConstrs = baseCubeType.effectivePropVal(compMdl, "cubeRelationships", "allowed")
                        for i, relConstr in enumerate(cubeType.cubeRelationships.allowed or ()):
                            for baseConstr in baseRelReqdConstrs:
                                if relConstr == baseConstr:
                                    compMdl.error("oimte:invalidRelationshipConstraintRelaxation",
                                                  _("The cube type %(name)s, cubeRelationships/allowed[%(i)s] must not relax base relationship constraint %(constraint)s"),
                                                  xbrlObject=cubeType, name=name, i=i, constraint=relConstr.propertyView)
                        for i, relConstr in enumerate(cubeType.cubeRelationships.allowed or ()):
                            matchingBaseRelConstrFound = False
                            for baseConstr in baseRelAlwdConstrs:
                                if relConstr == baseConstr:
                                    matchingBaseRelConstrFound = True
                            if not matchingBaseRelConstrFound:
                                compMdl.error("oimte:invalidRelationshipExpansion",
                                              _("The cube type %(name)s, cubeRelationships/allowed[%(i)s] must not add relationship constraint not permitted by base %(constraint)s"),
                                              xbrlObject=cubeType, name=name, i=i, constraint=relConstr.propertyView)
                        for baseConstr in baseRelReqdConstrs:
                            matchingRelConstrFound = False
                            for relConstr in cubeType.cubeRelationships.required:
                                if relConstr == baseConstr:
                                    matchingRelConstrFound = True
                            if not matchingRelConstrFound:
                                compMdl.error("oimte:missingRequiredRelationship",
                                              _("The cube type %(name)s, cubeRelationships/required[%(i)s] is missing required constriant of base %(constraint)s"),
                                              xbrlObject=cubeType, name=name, i=i, constraint=baseConstr.propertyView)


                    if cubeType.cubeProperties:
                        basePropertiesAllowed = baseCubeType.effectivePropVal(compMdl, "cubeProperties", "allowed")
                        basePropertiesRequired = baseCubeType.effectivePropVal(compMdl, "cubeProperties", "required")
                        if basePropertiesRequired:
                            removedPropsReqd = basePropertiesRequired - cubeType.cubeProperties.required
                            if removedPropsReqd:
                                compMdl.error("oimte:missingRequiredCubeProperty",
                                              _("The cube type %(name)s, must not remove property types required by the base type: %(qnames)s"),
                                              xbrlObject=cubeType, name=name, qnames=", ".join(sorted(str(qn) for qn in removedPropsReqd)))
                        if basePropertiesAllowed and cubeType.cubeProperties.allowed:
                            unallowedAddedProps = cubeType.cubeProperties.allowed - basePropertiesAllowed
                            if unallowedAddedProps:
                                compMdl.error("oimte:invalidPropertyExpansion",
                                              _("The cube type %(name)s, must not add property types not permitted by the base type: %(qnames)s"),
                                              xbrlObject=cubeType, name=name, qnames=", ".join(sorted(str(qn) for qn in unallowedAddedProps)))

    # Cube Objects
    for cubeObj in module.cubes:
        assertObjectType(compMdl, cubeObj, XbrlCube)
        name = cubeObj.name
        cubeType = compMdl.namedObjects.get(cubeObj.cubeType or reportCubeType)
        if cubeType is None:
            print("DEBUG: cubeType not found for cube", cubeObj.cubeType, "in cube", name)
        isTimeSeriesCubeType = cubeType and cubeType.name == timeSeriesCubeType
        ntwks = set()
        for ntwrkQn in cubeObj.cubeNetworks:
            ntwk = compMdl.namedObjects.get(ntwrkQn)
            if ntwk is None:
                compMdl.error("oimte:missingQNameReference",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s an object in the model."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            elif not isinstance(ntwk, XbrlNetwork):
                compMdl.error("oimte:invalidQNameReference",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s to a network object."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            else:
                 ntwks.add(ntwk)
        dimQnCounts = {}
        for cubeDimObj in cubeObj.cubeDimensions:
            dimQn = cubeDimObj.dimensionName
            dimObj = validateQNameReference(compMdl, cubeDimObj, "dimensionName", XbrlDimension)
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
                    else:
                        dimDomDTQn = dimObj.domainDataType
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
        if not isinstance(cubeType, XbrlCubeType):
            compMdl.error("oimte:invalidQNameReference",
                      _("The cube %(name)s  cubeType %(qname)s must be a valid cube type."),
                      xbrlObject=cubeObj, name=name, qname=(cubeObj.cubeType or reportCubeType))
        else:
            if cubeType.basemostCubeType != defaultCubeType and conceptCoreDim not in dimQnCounts.keys():
                compMdl.error("oimte:cubeMissingConceptDimension",
                          _("The cubeDimensions of cube %(name)s, type %(cubeType)s, must have a concept core dimension"),
                          xbrlObject=cubeObj, name=name, cubeType=cubeType.name)
            for prop, coreDim in (("periodDimension", periodCoreDim),
                                  ("entityDimension", entityCoreDim),
                                  ("unitDimension", unitCoreDim)):
                if coreDim in dimQnCounts.keys() and coreDim not in cubeType.effectivePropVal(compMdl, "coreDimensions"):
                    compMdl.error("oimte:cubeDimensionNotAllowed",
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
                        if ((not allwdDimConstr.dimensionName or dim.name == allwdDim.dimensionName)):
                            matchedDim = dim
                            matchedDimQNs.add(dim.name)
                            break
                    if not matchedDim and allwdDim.required:
                        compMdl.error("oimte:cubeMissingDimension",
                                  _("The cube %(name)s, type %(cubeType)s, taxonomy defined dimensions %(dimension)s is missing"),
                                  xbrlObject=cubeObj, name=name, cubeType=cubeType.name,
                                  dimension=', '.join(str(getattr(allwdDim,p)) for p in ("dimensionName", "dimensionType", "dimensionDataType") if getattr(allwdDim,p)))
                disallowedDims = txmyDefDimsQNs - matchedDimQNs
                if cubeDimsClosed and disallowedDims:
                    compMdl.error("oimte:cubeDimensionNotAllowed",
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
                    compMdl.error("oimte:cubeMissingRelationships",
                              _("The cube %(name)s, type %(cubeType)s, requiredCubeRelationships %(reqRel)s is missing"),
                              xbrlObject=cubeObj, name=name, cubeType=cubeType.name, reqRel=reqRelStr)


        for exclCubeQn in cubeObj.excludeCubes:
            if exclCubeQn == cubeObj.name:
                compMdl.error("oimte:excludeCubeSelfReference",
                          _("The cube %(name)s must not be defined in the excludeCubes property of itself."),
                          xbrlObject=cubeObj, name=name)
            if exclCubeQn not in compMdl.namedObjects:
                compMdl.error("oimte:invalidQNameReference",
                          _("The excludeCubes property on cube %(name)s, %(qname)s, must be defined in the taxonomy model."),
                          xbrlObject=cubeObj, name=name, qname=exclCubeQn)
            elif not isinstance(compMdl.namedObjects.get(exclCubeQn), XbrlCube):
                compMdl.error("oimte:invalidCubeName",
                          _("The excludeCubes property on cube %(name)s MUST resolve %(qname)s to a cube object."),
                          xbrlObject=cubeObj, name=name, qname=exclCubeQn)
        validateProperties(compMdl, oimFile, module, cubeObj)
        unitDataTypeQNs = set()
        cncptDataTypeQNs = set()
        hasConcpeptDimension = False
        hasTimeseriesDimension = False
        for iCubeDim, cubeDimObj in enumerate(cubeObj.cubeDimensions):
            assertObjectType(compMdl, cubeDimObj, XbrlCubeDimension)
            dimName = cubeDimObj.dimensionName
            dimObj = compMdl.namedObjects.get(dimName)
            isTyped = False
            if not isinstance(dimObj, XbrlDimension):
                compMdl.error("oimte:dimensionNameNotDimensionObject",
                          _("Cube %(name)s dimensionName property MUST be a dimension object %(dimensionName)s."),
                          xbrlObject=cubeObj, name=name, dimensionName=dimName)
                continue # not worth going further with this cube dimension
            domClass = compMdl.namedObjects.get(dimObj.domainClass)
            if not isinstance(domClass, XbrlDomainClass):
                continue # not worth continuing, domain object missing root will be reported elsewhere
            elif domClass.allowedDomainItems and all(
                    isinstance(compMdl.namedObjects.get(dt), XbrlDataType)
                    for dt in domClass.allowedDomainItems):
                isTyped = True
            if isTyped and qnXsDateTime in domClass.allowedDomainItems:
                hasTimeseriesDimension = True
            cubeDimDT = cubeDimObj.domainDataType
            if cubeDimDT:
                if isinstance(compMdl.namedObjects.get(cubeDimDT), XbrlDataType):
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
                else:
                    compMdl.error("oimte:invalidPropertyValue",
                                  _("Cube %(name)s dimension %(dimensionName)s domainDataType must be a dataType object %(dataType)s."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT)
            if cubeDimObj.typedSort not in (None, "asc", "desc"):
                compMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s typedSort property MUST be asc or desc, not %(typedSort)s."),
                          xbrlObject=cubeObj, name=name, typedSort=cubeDimObj.typedSort)
            hasValidDomainName = False
            if cubeDimObj.domainName:
                if isTyped:
                    if dimName == periodCoreDim:
                        compMdl.error("oimte:domainUsedOnPeriodDimension",
                                  _("Cube %(name)s dimension %(dimensionName)s domain objects MUST NOT be defined with a domainName property."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                    else:
                        compMdl.error("oimte:domainClassMismatchWithDomain",
                                  _("Cube %(name)s dimension %(dimensionName)s domain objects MUST NOT be defined with a typed domainClass object."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                cubeDomObj = compMdl.namedObjects.get(cubeDimObj.domainName)
                if isinstance(cubeDomObj, XbrlDomain):
                    hasValidDomainName = True
                else:
                    compMdl.error("oimte:invalidCubeDimensionDomainName",
                              _("Cube %(name)s domainName property MUST identify a domain object: %(domainName)s."),
                              xbrlObject=cubeObj, name=name, domainName=cubeDimObj.domainName)
            if cubeDimObj.periodConstraints and dimName != periodCoreDim:
                compMdl.error("oimte:invalidPeriodConstraintDimension",
                          _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)
            if dimName == conceptCoreDim:
                hasConcpeptDimension = True
            if dimName == conceptCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), (XbrlConcept, XbrlAbstract)) and relObj.source != conceptDomainClass:
                        compMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s conceptConstraints domain relationships must be from concepts, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if isinstance(compMdl.namedObjects.get(relObj.target,None), XbrlConcept):
                        cncptDataTypeQNs.add(compMdl.namedObjects[relObj.target].dataType)
                if cubeDimObj.allowDomainFacts:
                    compMdl.error("oimte:invalidAllowDomainFactsPropertyOnConceptDimension",
                              _("Cube %(name)s conceptConstraints property MUST NOT specify allowDomainFacts."),
                              xbrlObject=(cubeObj,cubeDimObj), name=name)
            if dimName == entityCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), XbrlEntity) and relObj.source != entityDomainClass:
                        compMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s entityConstraints domain relationships must be from entities, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
            if dimName == unitCoreDim and hasValidDomainName:
                for relObj in compMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(compMdl.namedObjects.get(relObj.source,None), XbrlUnit) and relObj.source != unitDomainClass:
                        compMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s unitConstraints domain relationships must be from units, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
            if dimName in (periodCoreDim, languageCoreDim) and hasValidDomainName:
                compMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s dimension %(qname)s must not specify domain %(domain)s."),
                          xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName, domain=cubeDimObj.domainName)
            if dimName not in coreDimensions and isinstance(compMdl.namedObjects.get(dimName), XbrlDimension):
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
                    compMdl.error("oimte:invalidCubeDimensionProperty",
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
                                if isinstance(cncpt, XbrlConcept) and isinstance(compMdl.namedObjects.get(cncpt.dataType), XbrlDataType) and compMdl.namedObjects[cncpt.dataType].xsBaseType(compMdl) in ("date", "dateTime"):
                                    compMdl.dateResolutionConceptNames.add(dtResObj.conceptName)
                                else:
                                    compMdl.error("oimte:invalidQNameReference",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a date or dateTime."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                            if dtResObj.context:
                                cncpt = compMdl.namedObjects.get(dtResObj.context)
                                if isinstance(cncpt, XbrlConcept) and (dtResObj.context.atSuffix in ("start","end")):
                                    compMdl.dateResolutionConceptNames.add(dtResObj.context)
                                else:
                                    compMdl.error("oimte:invalidQNameReference",
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

        if not hasConcpeptDimension:
                compMdl.error("oimte:cubeMissingConceptDimension",
                          _("Cube %(name)s is missing a concept dimension."),
                          xbrlObject=(cubeObj,cubeDimObj), name=name)

        for unitDataTypeQN in unitDataTypeQNs:
            if unitDataTypeQN not in cncptDataTypeQNs:
                compMdl.error("oimte:invalidDataTypeObject",
                          _("Cube %(name)s unitConstraints data Type %(dataType)s MUST have at least one associated concept object on the concept core dimension with the same datatype as the unit object."),
                          xbrlObject=(cubeObj,cubeDimObj), name=name, dataType=unitDataTypeQN)

        if isTimeSeriesCubeType and not hasTimeseriesDimension:
            compMdl.error("oimte:timeseriesCubeMissingTimeseriesDimension",
                      _("Timeseries cube %(name)s MUST have a timeseries dimension."),
                      xbrlObject=(cubeObj,cubeDimObj), name=name)

    # DataType Objects
    for dtObj in module.dataTypes:
        assertObjectType(compMdl, dtObj, XbrlDataType)
        btQn = dtObj.baseType
        if btQn and btQn.namespaceURI != "http://www.w3.org/2001/XMLSchema" and not isinstance(compMdl.namedObjects.get(btQn), XbrlDataType):
            compMdl.error("oimte:invalidPropertyValue",
                      _("The dataType object %(name)s MUST define a valid baseType which must be a dataType object in the taxonomy model"),
                      xbrlObject=dtObj, name=dtObj.name)
        if dtObj.unitType is not None:
            utObj = dtObj.unitType
            assertObjectType(compMdl, utObj, XbrlUnitType)
            for utProp in ("dataTypeNumerator", "dataTypeDenominator", "dataTypeMultiplier"):
                utPropQn = getattr(utObj, utProp)
                if utPropQn and not isinstance(compMdl.namedObjects.get(utPropQn), XbrlDataType):
                    compMdl.error("oimte:invalidPropertyValue",
                              _("The dataType object unitType %(name)s MUST define a valid dataType object in the taxonomy model"),
                              xbrlObject=dtObj, name=dtObj.name)
        if isinstance(dtObj.collectionType, XbrlCollectionType):
            if btQn != qnXbrliCollection:
                compMdl.error("oimte:collectionTypeWithoutCollectionBaseType",
                          _("The set dataType object %(name)s MUST define a valid baseType xbrli:collection"),
                          xbrlObject=dtObj, name=dtObj.name)
            for dtQn in dtObj.collectionType.dataTypesAllowed:
                dtObj = compMdl.namedObjects.get(dtQn)
                if not isinstance(dtObj, XbrlDataType):
                    compMdl.error("oimte:invalidQNameReference",
                              _("Datatype %(name)s has invalid collection dataTypesAllowed QName %(dataType)s"),
                              xbrlObject=dtObj, name=dtObj.name, dataType=dtQn)

    # Dimension Objects
    for dimObj in module.dimensions:
        assertObjectType(compMdl, dimObj, XbrlDimension)
        for cubeTypeQn in dimObj.cubeTypes:
            if cubeTypeQn not in compMdl.namedObjects:
                compMdl.error("oimte:missingQNameReference",
                          _("The dimension cubeType QName %(name)s MUST exist in the taxonomy model"),
                          xbrlObject=dimObj, name=cubeTypeQn)
            elif not isinstance(compMdl.namedObjects.get(cubeTypeQn), XbrlCubeType):
                compMdl.error("oimte:invalidCubeType",
                          _("The dimension cubeType QName %(name)s MUST be a valid cubeType object in the taxonomy model"),
                          xbrlObject=dimObj, name=cubeTypeQn)
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
            extendTargetObj = compMdl.namedObjects.get(domObj.extendTargetName)
            if domObj.name:
                compMdl.error("oimte:invalidObjectProperty",
                          _("The domain %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=domObj, name=domObj.name)
            elif not isinstance(extendTargetObj, XbrlDomain):
                compMdl.error("oimte:missingQNameReference",
                          _("The domain %(name)s MUST be a valid domain object in the taxonomy model"),
                          xbrlObject=domObj, name=domObj.name or domObj.extendTargetName)
            elif getattr(domObj, "_extendResolved", False):
                extendTargetObj = None # don't extend, already been extended
            elif extendTargetObj.completeDomain:
                compMdl.error("oimte:cannotExtendCompleteDomain",
                          _("The domain %(name)s cannot be extended because it is a completeDomain."),
                          xbrlObject=domObj, name=extendTargetObj.name)
                continue
            else:
                domObj._extendResolved = True
                extendedDomClassQn = extendTargetObj.domainClass
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
                    compMdl.error("oimte:missingQNameReference",
                              _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=domObj.name, nbr=i, source=src)
                if tgt not in compMdl.namedObjects:
                    compMdl.error("oimte:missingQNameReference",
                              _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=domObj.name, nbr=i, target=tgt)
            else:
                if domRtQn == conceptDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], (XbrlConcept, XbrlAbstract)):
                        compMdl.error("oimte:invalidConceptDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s MUST be a concept object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                if domRtQn == entityDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], XbrlEntity):
                        compMdl.error("oimte:invalidEntityDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the entity root or an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(compMdl.namedObjects[relObj.target], XbrlEntity):
                        compMdl.error("oimte:invalidEntityDomainTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                if domRtQn == unitDomainClass:
                    if relObj.source != domRtQn and not isinstance(compMdl.namedObjects[relObj.source], XbrlUnit):
                        compMdl.error("oimte:invalidUnitDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the unit root or an unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(compMdl.namedObjects[relObj.target], XbrlUnit):
                        compMdl.error("oimte:invalidUnitDomainTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be a unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                elif isinstance(compMdl.namedObjects[relObj.source], XbrlUnit) or isinstance(compMdl.namedObjects[relObj.target], XbrlUnit):
                    compMdl.error("oimte:unitInNonUnitDomain",
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
                compMdl.error("oimte:invalidDomainClassTarget",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domainClass object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            elif isinstance(compMdl.namedObjects.get(tgt), XbrlDomain):
                compMdl.error("oimte:invalidObjectType",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domain object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            elif extendTargetObj is not None:
                extendTargetObj.relationships.add(relObj)
            if tgt == domRtQn:
                compMdl.error("oimte:invalidDomainTarget",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be the domain root object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            if domRtQn == src:
                domClassSourceInRel = True
            relKey = (src, tgt)
            domRelCts[relKey] = domRelCts.get(relKey, 0) + 1
            domRelRoots.discard(tgt) # remove any target from roots
        if any(ct > 1 for relKey, ct in domRelCts.items()):
            compMdl.error("oimte:duplicateObjects",
                      _("The domain %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=domObj, name=domObj.name,
                      names=", ".join(f"{relKey[0]}\u2192{relKey[1]}" for relKey, ct in domRelCts.items() if ct > 1))
        if domRtObj and not domClassSourceInRel:
            compMdl.error("oimte:missingDomainClassSource",
                      _("The domain %(name)s root %(qname)s MUST be a source in a relationship"),
                      xbrlObject=domObj, name=domObj.name, qname=domObj.root)
        if len(domRelRoots) > 1:
            compMdl.error("oimte:multipleDomainClasss",
                      _("The domain %(name)s relationship must resolve to a single root object, multiple found: %(roots)s"),
                      xbrlObject=domObj, name=domObj.name, roots=", ".join(sorted(str(r) for r in domRelRoots)))
        validateProperties(compMdl, oimFile, module, domObj)


    # DomainClass Objects
    for domRtObj in module.domainClasses:
        assertObjectType(compMdl, domRtObj, XbrlDomainClass)
        name = domRtObj.name
        for allwdDomItemQn in domRtObj.allowedDomainItems:
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
        if grpQn not in compMdl.namedObjects or type(compMdl.namedObjects[grpQn]) != XbrlGroup:
            compMdl.error("oimte:invalidGroupObject",
                      _("The groupContent object groupName QName %(name)s MUST be a valid group object in the taxonomy model"),
                      xbrlObject=grpCntObj, name=grpQn)
        for relName in grpCntObj.relatedNames:
            if relName not in compMdl.namedObjects or not isinstance(compMdl.namedObjects.get(relName), (XbrlNetwork, XbrlCube, XbrlTableTemplate, XbrlDomain)):
                compMdl.error("oimte:invalidGroupObject",
                          _("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects or table template objects."),
                          xbrlObject=grpCntObj, name=grpQn, relName=relName)

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
            compMdl.error("oimte:unresolvedRelatedName",
                      _("Label has invalid related object %(relatedName)s"),
                      xbrlObject=lblObj, relatedName=relatedName)
        lblTpObj = validateQNameReference(compMdl, lblObj, "labelType", XbrlLabelType)
        if lblTpObj:
            if lblTpObj.allowedObjects and relatedObj is not None and not any(
                type(relatedObj) == xbrlObjectTypes[allowedObj] for allowedObj in lblTpObj.allowedObjects):
                compMdl.error("oimte:invalidAllowedObject",
                          _("Label has disallowed related object %(relatedName)s"),
                          xbrlObject=lblObj, relatedName=relatedName)
            lblObj._xValid, lblObj._xValue = validateValue(compMdl, module, lblObj, lblObj.value, lblTpObj.dataType, "", "oimte:invalidPropertyValue")
        validateProperties(compMdl, oimFile, module, lblObj)
        lblKey = (relatedName, lblObj.labelType, lblObj.language)
        mdlLvlChecks.labelsCt[lblKey].append(lblObj)

    # Network Objects
    ntwkCt = {}
    for ntwkObj in module.networks:
        assertObjectType(compMdl, ntwkObj, XbrlNetwork)
        extendTargetObj = None
        relTypeObj = None
        if ntwkObj.extendTargetName:
            extendTargetObj = compMdl.namedObjects.get(ntwkObj.extendTargetName)
            if ntwkObj.name:
                compMdl.error("oimte:invalidObjectProperty",
                          _("The network %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=ntwkObj, name=ntwkObj.name)
            elif not isinstance(extendTargetObj, XbrlNetwork):
                compMdl.error("oimte:missingTargetObject",
                          _("The network extendTargetName %(name)s MUST be a valid network object in the taxonomy model"),
                          xbrlObject=ntwkObj, name=ntwkObj.name or ntwkObj.extendTargetName)
            else:
                relTypeObj = compMdl.namedObjects.get(extendTargetObj.relationshipTypeName)
                if not isinstance(relTypeObj, XbrlRelationshipType):
                    relTypeObj = None
                    compMdl.warning("oimte:missingQNameReference",
                              _("The network %(name)s relationshipTypeName %(relationshipTypeName)s SHOULD specify a relationship type in the taxonomy model."),
                              xbrlObject=ntwkObj, name=ntwkObj.name, relationshipTypeName=ntwkObj.relationshipTypeName)
                if getattr(ntwkObj, "_extendResolved", False):
                    extendTargetObj = None # don't extend, already been extended
                else:
                    ntwkObj._extendResolved = True
        else:
            if not ntwkObj.name:
                compMdl.error("oimte:missingRequiredProperty",
                          _("The network object MUST have either a name or an extendTargetName, not neither."),
                          xbrlObject=ntwkObj)
            relTypeObj = compMdl.namedObjects.get(ntwkObj.relationshipTypeName)
            if not isinstance(relTypeObj, XbrlRelationshipType):
                relTypeObj = None
                compMdl.error("oimte:missingQNameReference",
                          _("The network %(name)s relationshipTypeName %(relationshipTypeName)s MUST specify a relationship type in the taxonomy model."),
                          xbrlObject=ntwkObj, name=ntwkObj.name, relationshipTypeName=ntwkObj.relationshipTypeName)
        ntwkCt = {}
        for rootQn in ntwkObj.roots:
            if rootQn not in compMdl.namedObjects:
                compMdl.error("oimte:missingQNameReference",
                          _("The network %(name)s root %(qname)s MUST be a valid object in the taxonomy model"),
                          xbrlObject=ntwkObj, name=ntwkObj.name, qname=rootQn)
            ntwkCt[rootQn] = ntwkCt.get(rootQn, 0) + 1
        if any(ct > 1 for root, ct in ntwkCt.items()):
            compMdl.error("oimte:duplicateObjects",
                          _("The network %(name)s has duplicated roots %(roots)s"),
                          xbrlObject=ntwkObj, roots=", ".join(str(root) for root, ct in ntwkCt.items() if ct > 1))

        ntwkCt = {}
        sources = OrderedSet()
        targets = OrderedSet()
        for i, relObj in enumerate(ntwkObj.relationships):
            assertObjectType(compMdl, relObj, XbrlRelationship)
            if  relObj.source not in compMdl.namedObjects or relObj.target not in compMdl.namedObjects:
                if relObj.source not in compMdl.namedObjects:
                    compMdl.error("oimte:missingQNameReference",
                              _("The network %(name)s relationship[%(nbr)s] source, %(source)s MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=ntwkObj.name, nbr=i, source=relObj.source)
                if relObj.target not in compMdl.namedObjects:
                    compMdl.error("oimte:missingQNameReference",
                              _("The network %(name)s relationship[%(nbr)s] target, %(target)s MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=ntwkObj.name, nbr=i, target=relObj.target)
            else:
                sources.add(relObj.source)
                targets.add(relObj.target)
                if extendTargetObj is not None:
                    extendTargetObj.relationships.add(relObj)
                if relTypeObj is not None:
                    if relTypeObj.sourceObjects and xbrlObjectQNames.get(type(compMdl.namedObjects[relObj.source])) not in relTypeObj.sourceObjects:
                        compMdl.error("oimte:invalidObjectType",
                                  _("The network %(name)s relationship[%(nbr)s] source, %(source)s MUST be an object type allowed for the relationship type %(relationshipType)s."),
                                  xbrlObject=relObj, name=ntwkObj.name, nbr=i, source=relObj.source, relationshipType=ntwkObj.relationshipTypeName)
                    if relTypeObj.targetObjects and xbrlObjectQNames.get(type(compMdl.namedObjects[relObj.target])) not in relTypeObj.targetObjects:
                        compMdl.error("oimte:invalidObjectType",
                                  _("The network %(name)s relationship[%(nbr)s] target, %(target)s MUST be an object type allowed for the relationship type %(relationshipType)s."),
                                  xbrlObject=relObj, name=ntwkObj.name, nbr=i, target=relObj.target, relationshipType=ntwkObj.relationshipTypeName)
            validateProperties(compMdl, oimFile, module, relObj)
            relObjPrefLbl = relObj.propertyObjectValue(preferredLabel)
            if relObjPrefLbl and  not isinstance(compMdl.namedObjects.get(relObjPrefLbl), XbrlLabelType):
                compMdl.error("oimte:missingQNameReference",
                          _("The network %(name)s relationship[%(nbr)s] preferredLabel, %(preferredLabel)s MUST be a label type object."),
                          xbrlObject=relObj, name=ntwkObj.name, nbr=i, preferredLabel=relObjPrefLbl)
            relKey = (relObj.source, relObj.target, relObjPrefLbl, relObj.order)
            ntwkCt[relKey] = ntwkCt.get(relKey, 0) + 1
        if any(ct > 1 for relKey, ct in ntwkCt.items()):
            compMdl.error("oimte:duplicateObjects",
                      _("The network %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=ntwkObj, name=ntwkObj.name,
                      names=", ".join(f"{relFrom}\u2192{relTo}{f' [{str(prefLbl)}]' if prefLbl else ''} ord {str(ordr)}"
                                      for (relFrom, relTo, prefLbl, ordr), ct in ntwkCt.items() if ct > 1))
        ntwkObj._rootsFound = sources - targets
        if ntwkObj.roots:
            undeclaredRoots = ntwkObj._rootsFound - ntwkObj.roots
            if undeclaredRoots:
                compMdl.error("oimte:invalidNetworkRoot",
                          _("The network %(name)s network object roots property does not include these undeclared relationship roots: %(undeclaredRoots)s"),
                          xbrlObject=ntwkObj, name=ntwkObj.name, undeclaredRoots=", ".join(sorted(str(r) for r in undeclaredRoots)))
        else:
            ntwkObj.roots = ntwkObj._rootsFound # not specified so use actual roots
        validateProperties(compMdl, oimFile, module, ntwkObj)
        del ntwkCt

    # PropertyType Objects
    for i, propTpObj in enumerate(module.propertyTypes):
        assertObjectType(compMdl, propTpObj, XbrlPropertyType)
        dataTypeObj = validateQNameReference(compMdl, propTpObj, "dataType", XbrlDataType)
        if not dataTypeObj:
            continue
        if dataTypeObj and propTpObj.enumerationDomain:
            if dataTypeObj.xsBaseType(compMdl) != "QName":
                compMdl.error("oimte:missingQNameReference",
                          _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                          xbrlObject=propTpObj, name=propTpObj.name, qname=propTpObj.dataType)
            elif not isinstance(compMdl.namedObjects.get(propTpObj.enumerationDomain), XbrlDomain):
                compMdl.error("oime:invalidEnumerationDomainObject",
                          _("The propertyType %(name)s has invalid enumeration domain reference %(enumDomain)s"),
                          xbrlObject=propTpObj, name=propTpObj.name, enumDomain=propTpObj.enumerationDomain)
        for allowedObjQn in propTpObj.allowedObjects:
            if allowedObjQn not in objectsWithProperties:
                compMdl.error("oimte:invalidAllowedObject",
                          _("The property %(name)s has an invalid allowed object %(allowedObj)s"),
                          xbrlObject=propTpObj, name=propTpObj.name, allowedObj=allowedObjQn)

    # RelationshipType Objects
    for relTpObj in module.relationshipTypes:
        assertObjectType(compMdl, relTpObj, XbrlRelationshipType)
        for prop in ("allowedLinkProperties", "requiredLinkProperties"):
            for propTpQn in getattr(relTpObj, prop):
                if not isinstance(compMdl.namedObjects.get(propTpQn), XbrlPropertyType):
                    compMdl.error("oimte:missingQNameReference",
                              _("The relationshipType %(name)s %(property)s has an invalid propertyType reference %(propType)s"),
                              xbrlObject=relTpObj, name=relTpObj.name, property=prop, propType=propTpQn)
        reqdNotAllowed = relTpObj.requiredLinkProperties - relTpObj.allowedLinkProperties
        if reqdNotAllowed:
            compMdl.error("oimte:invalidPropertyValue",
                      _("The relationshipType %(name)s has an required properties which are not allowed %(propTypes)s"),
                      xbrlObject=propTpObj, name=relTpObj.name, property=prop, propTypes=", ".join(str(q) for q in reqdNotAllowed))

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
        if not isinstance(compMdl.namedObjects.get(refTp), XbrlReferenceType) and (refTp or not extName):
                compMdl.error("oimte:missingQNameReference",
                          _("The reference %(name)s reference %(qname)s MUST be a referenceType object."),
                          xbrlObject=refObj, name=name, qname=refTp)
        if extName:
            if name:
                compMdl.error("oimte:referenceNameRedefined",
                          _("Referencehas both extendTargetName and name %(name)s"),
                          xbrlObject=refObj, name=extName)
            else:
                extRefObjs = compMdl.tagObjects.get(extName) or ()
                if not all(isinstance(extRefObj, XbrlReference) for extRefObj in extRefObjs):
                    compMdl.error("oimte:missingQNameReference",
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
        compMdl.error("oimte:missingQNameReference",
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
        #elif not dataTypeObj.isAllowedFor(qnXbrlLabelObj):
        #    compMdl.error("oimte:unallowedDataTypeObject",
        #              _("The labelType %(name)s is not allowed for dataType %(qname)s"),
        #              xbrlObject=lblObj, name=lblObj.name, qname=lblObj.dataType)
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
        for allowedObj in refObj.allowedObjects:
            if allowedObj not in referencableObjectTypes:
                compMdl.error("oimte:invalidObjectType",
                          _("The referenceType %(name)s allowedObject %(allowedObject)s MUST be a referenceable taxonomy model object."),
                          xbrlObject=refObj, name=refObj.name, allowedObject=allowedObj)
        for prop, msgCode in (("orderedProperties","oimte:invalidOrderedProperty"),
                              ("requiredProperties","oimte:invalidRequiredProperty")):
            for propTpQn in getattr(refObj, prop):
                propTpObj = compMdl.namedObjects.get(propTpQn)
                if not isinstance(propTpObj, XbrlPropertyType):
                    compMdl.error("oimte:missingQNameReference",
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
            dtObj = compMdl.namedObjects.get(dtQn)
            if not isinstance(dtObj, XbrlDataType):
                compMdl.error("oimte:unknownDataType",
                          _("The unit %(name)s dataType %(qname)s MUST be a dataType object."),
                          xbrlObject=unitObj, name=unitObj.name, qname=dtQn)
            elif not dtObj.isAllowedFor(unitObj):
                compMdl.error("oimte:unallowedDataTypeObject",
                              _("The unit %(name)s is not allowed for dataType %(dataType)s."),
                          xbrlObject=unitObj, name=unitObj.name, dataType=dtQn)

        unitObj._unitsMeasures = [parseUnitString(uStr, unitObj, module, compMdl) for uStr in unitObj.stringRepresentations]
        for uMeas in unitObj._unitsMeasures:
            if any(m == name for md in uMeas for m in md):
                compMdl.error("oimte:invalidPropertyValue",
                          _("The unit %(name)s must not contain itself as a measure."),
                          xbrlObject=unitObj, name=unitObj.name)
            for md in uMeas:
                for m in md:
                    if m not in compMdl.namedObjects:
                        compMdl.error("oimte:missingQNameReference",
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
            if not validateQNameReference(compMdl, mdlTpObj, f"requiredProperties[{i+1}]", XbrlPropertyType, qnDefault=reqPropQn):
                compMdl.error("oimte:invalidRequiredObject",
                          _("The modelType %(name)s has a required object %(requiredObj)s which is not an allowed object."),
                          xbrlObject=mdlTpObj, name=mdlTpObj.name, requiredObj=reqPropQn)

    # Facts in taxonomy
    if module.facts:
        global resolveFact, validateFactPosition
        if resolveFact is None:
            from .ValidateReport import resolveFact, validateFactPosition
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

        for dim in tblTmpl.dimensions:
            if dim.startswith('$'):
                colName = dim[1:]
                if colName not in tblTmpl.columns:
                    compMdl.error("oimte:tableTemplateDimensionColumnReference",
                              _("The table template dimension %(dimension)s is missing from the table template columns."),
                              xbrlObject=tblTmpl, dimension=dim)

def validateCompletedModel(compMdl):
    # Facts in taxonomy
    if any(module.facts for module in compMdl.xbrlModels.values()):

        # build search vocabulary to support cube construction (after date resolution concepts validated)
        from .VectorSearch import buildXbrlVectors, searchXbrl, searchXbrlBatchTopk, SEARCH_CUBES, SEARCH_FACTPOSITIONS, SEARCH_BOTH
        buildXbrlVectors(compMdl)

        dateResolutionQuery = [(conceptCoreDim, qn) for qn in compMdl.dateResolutionConceptNames]

        if dateResolutionQuery:

            results = searchXbrl(compMdl, dateResolutionQuery, SEARCH_FACTPOSITIONS, 5 * len(dateResolutionQuery)) # allow sufficient return scores
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

            # validate facts not of date resolution objects
            for f in compMdl.filterNamedObjects(XbrlFact):
                if f.factDimensions.get(conceptCoreDim) not in compMdl.dateResolutionConceptNames:
                    validateFactPosition(compMdl, f)
        else:
            # validate all facts
            for f in compMdl.filterNamedObjects(XbrlFact):
                validateFactPosition(compMdl, f)

    # check complete cubes
    for cubeObj in compMdl.filterNamedObjects(XbrlCube):
        if cubeObj.cubeComplete:
            validateCompleteCube(compMdl, cubeObj)
