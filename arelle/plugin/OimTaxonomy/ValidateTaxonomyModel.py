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
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlConst import xbrl, qnXbrlReferenceObj, qnXbrlLabelObj, qnXbrlAbstractObj, qnXbrlConceptObj, qnXbrlMemberObj, qnXbrlEntityObj, qnXbrlUnitObj, qnXbrlImportTaxonomyObj, reservedPrefixNamespaces
from .XbrlCube import (XbrlCube, XbrlCubeType, baseCubeTypes, XbrlCubeDimension,
                       periodCoreDim, conceptCoreDim, entityCoreDim, unitCoreDim, languageCoreDim, coreDimensions,
                    conceptDomainRoot, entityDomainRoot, unitDomainRoot, languageDomainRoot,
                    defaultCubeType, reportCubeType, timeSeriesCubeType,
                    timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, excludedIntervalsPropType)
from .XbrlDimension import XbrlDimension, XbrlDomain, XbrlDomainRoot, XbrlMember, xbrlMemberObj
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent
from .XbrlImportTaxonomy import XbrlImportTaxonomy, XbrlExportProfile, XbrlFinalTaxonomy
from .XbrlLabel import XbrlLabel, XbrlLabelType, preferredLabel
from .XbrlLayout import XbrlLayout, XbrlTableTemplate, XbrlDataTable
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlObject import XbrlReferencableTaxonomyObject
from .XbrlProperty import XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlReport import XbrlFactspace, XbrlFootnote
from .XbrlTaxonomyModule import XbrlTaxonomyModule, xbrlObjectTypes, referencableObjectTypes, xbrlObjectQNames
from .XbrlUnit import XbrlUnit, parseUnitString
from .XbrlConst import qnXsQName, qnXsDate, qnXsDateTime, qnXsDuration, objectsWithProperties
from arelle.FunctionFn import true
validateFactspace = None

perCnstrtFmtStartEndPattern = re.compile(r".*@(start|end)")

def validateTaxonomyModel(txmyMdl):

    mdlLvlChecks = attrdict(
        labelsCt = defaultdict(list), # count of duplicated labels by relatedName, labelType and language
    )

    for txmy in txmyMdl.taxonomies.values():
        validateTaxonomy(txmyMdl, txmy, mdlLvlChecks)
    for layout in txmyMdl.layouts.values():
        validateLayout(txmyMdl, layout)

    # model lavel checks
    for lblKey, lblObjs in mdlLvlChecks.labelsCt.items():
        if len(lblObjs) > 1:
            txmyMdl.error("oimte:duplicateLabelObject",
                      _("The labels are duplicated for relatedName %(name)s type %(type)s language %(language)s"),
                      xbrlObject=lblObjs, name=lblKey[0], type=lblKey[1], language=lblKey[2])

def objType(obj):
    clsName = type(obj).__name__
    if clsName.startswith("Xbrl"):
        return clsName[4:]
    return clsName

def assertObjectType(txmyMdl, obj, objType):
    if not isinstance(obj, objType):
        txmyMdl.error("oimte:invalidObjectType",
                  _("This %(thisType)s object was included where an %(expectedType)s object was expected."),
                  xbrlObject=obj, thisType=obj.__class__.__name__, expectedType=objType.__name__)

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
    propTypeQns = defaultdict(set)
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
            if propTypeObj is None:
                txmyMdl.error("oimte:missingQNameReference",
                          _("%(parentObjName)s %(parentName)s property %(name)s has undefined dataType %(dataType)s"),
                          file=oimFile, parentObjName=objType(obj), parentName=parentName,
                          name=propTypeQn, dataType=propTypeQn)
            else:
                txmyMdl.error("invalidObjectType",
                          _("%(parentObjName)s %(parentName)s property %(name)s has invalid property type object %(dataType)s"),
                          file=oimFile, parentObjName=objType(obj), parentName=parentName,
                          name=propTypeQn, dataType=propTypeQn)
        else: # have property type object
            if propTypeObj.allowedObjects:
                if xbrlObjectQNames.get(type(obj)) not in propTypeObj.allowedObjects:
                    txmyMdl.error("oimte:disallowedObjectProperty",
                              _("%(parentObjName)s %(parentName)s property %(name)s not an allowed property type for the object."),
                              file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                              name=propTypeQn)
            propObj._xValid, propObj._xValue = validateValue(txmyMdl, txmy, obj, propObj.value, propTypeObj.dataType, f"/properties[{i}]", "oimte:invalidPropertyValue")

            propTypeQns[propTypeQn].add(propObj._xValue)
    if any(len(vals) > 1 for qn, vals in propTypeQns.items()):
        txmyMdl.error("oimte:conflictingPropertyValues",
                  _("%(parentObjName)s %(parentName)s has conflicting values for properties %(names)s"),
                  file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                  names=", ".join(str(qn) for qn, vals in propTypeQns.items() if len(vals) > 1))


def validateTaxonomy(txmyMdl, txmy, mdlLvlChecks):
    oimFile = str(txmy.name)
    txmyNamespace = txmy.name.namespaceURI

    # Taxonomy object
    assertObjectType(txmyMdl, txmy, XbrlTaxonomyModule)

    # taxonomy namespace for objects
    for txMdlPropName, propType in XbrlTaxonomyModule.propertyNameTypes():
        if isinstance(propType, GenericAlias) and issubclass(propType.__origin__, OrderedSet):
            for txMdlObj in getattr(txmy, txMdlPropName, ()):
                # for Optional OrderedSets where the jsonValue exists, handle as propType, _keyClass and eltClass
                name = getattr(txMdlObj, "name", None)
                if isinstance(name, QName):
                    ns = name.namespaceURI
                    if ns != txmyNamespace and ns in reservedPrefixNamespaces.values():
                        txmyMdl.error("oimte:invalidObjectNamespacePrefix",
                                  _("The taxonomy module object %(name)s cannot have a reserved namespace URI."),
                                  xbrlObject=txMdlObj, name=name)

    for impTxObj in txmy.importedTaxonomies:
        assertObjectType(txmyMdl, impTxObj, XbrlImportTaxonomy)
        impTxName = impTxObj.taxonomyName
        for qnObjType in impTxObj.importObjectTypes:
            if qnObjType in xbrlObjectTypes:
                if xbrlObjectTypes[qnObjType] == XbrlLabel:
                    txmyMdl.error("oimte:invalidObjectType",
                              _("The importObjectTypes property MUST not include the label object."),
                              xbrlObject=impTxObj)
            else:
                txmyMdl.error("oimte:invalidObjectType",
                          _("The importObjectTypes property MUST specify valid OIM object types, %(qname)s is not valid."),
                          xbrlObject=impTxObj, qname=qnObjType)
        if impTxObj.profiles and (impTxObj.selections or impTxObj.importObjects or impTxObj.importObjectTypes):
            txmyMdl.error("oimte:invalidImportTaxonomy",
                      _("The importTaxonomy %(taxonomyName)s profiles must only be used without selectons, importObjects or importObjectTypes."),
                      xbrlObject=impTxObj, taxonomyName=impTxName)
        finalTxObj = txmyMdl.namedObjects.get(impTxName)
        if isinstance(finalTxObj, XbrlFinalTaxonomy):
            def extendsFinalTaxonomy(obj):
                # check for extended objects
                if finalTxObj.finalTaxonomyFlag:
                    if isinstance(obj, XbrlReferencableTaxonomyObject) and not isinstance(obj, (XbrlFactspace, XbrlFootnote, XbrlEntity)):
                        txmyMdl.error("oimte:invalidFinalTaxonomyModification",
                                  _("The importTaxonomy %(taxonomyName)s cannot be extended by object %(qname)s due to a finalTaxonomyFlag."),
                                  xbrlObject=impTxObj, taxonomyName=impTxName, qname=obj.name)
                elif finalTxObj.finalObjectTypes and xbrlObjectQNames[type(obj)] in finalTxObj.finalObjectTypes:
                    txmyMdl.error("oimte:invalidFinalTaxonomyModification",
                              _("The importTaxonomy %(taxonomyName)s cannot be extended by object %(qname)s due to it's type, %(type)s, being in finalObjectTypes."),
                              xbrlObject=impTxObj, taxonomyName=impTxName, qname=obj.name, type=xbrlObjectQNames[type(obj)] )
                elif finalTxObj.finalObjects and getattr(obj, "extendTargetName", None) in finalTxObj.finalObjects:
                    txmyMdl.error("oimte:invalidFinalTaxonomyModification",
                              _("The importTaxonomy %(taxonomyName)s cannot be extended by object %(qname)s due to having %(name)s in finalObjects."),
                              xbrlObject=impTxObj, taxonomyName=impTxName, qname=xbrlObjectQNames[type(obj)], name=obj.extendTargetName)
                elif finalTxObj.selections:
                    for i, selObj in enumerate(impTxObj.selections):
                        if xbrlObjectQNames[type(obj)] == selObj.objectType and (
                            all((eval(obj, whereObj) for whereObj in selObj.where))):
                            txmyMdl.error("oimte:invalidFinalTaxonomyModification",
                                      _("The importTaxonomy %(taxonomyName)s cannot be extended by object %(qname)s due matching selection %(i)s."),
                                      xbrlObject=impTxObj, taxonomyName=impTxName, qname=xbrlObjectQNames[type(obj)], i=i)
                            break # selections are or'ed, don't need to try more            txmy.referencedObjectsAction(txmyMdl, extendsFinalTaxonomy)

    expPrflCt = defaultdict(list)
    for expPrflObj in txmy.exportProfiles:
        assertObjectType(txmyMdl, expPrflObj, XbrlExportProfile)
        name = expPrflObj.name
        for expObjQn in expPrflObj.exportObjects:
            if expObjQn not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:invalidExportObject",
                          _("The exportProfile %(name)s exportObject %(qname)s must identify an taxonomy object."),
                          xbrlObject=expPrflObj, name=name, qname=expObjQn)
        for qnObjType in expPrflObj.exportObjectTypes:
            if qnObjType not in xbrlObjectTypes:
                txmyMdl.error("oimte:invalidExportObjectType",
                          _("The exportProfile %(name)s objectType property MUST specify valid OIM object types, %(qname)s is not valid."),
                          xbrlObject=expPrflObj, name=name, qname=qnObjType)
        for iSel, selObj in enumerate(expPrflObj.selections):
            if selObj.objectType not in xbrlObjectTypes.keys() - {qnXbrlImportTaxonomyObj}:
                txmyMdl.error("oimte:invalidSelectionObjectType",
                          _("The exportProfile %(name)s selection[%(nbr)s] must identify a referencable taxonomy component object, excluding importTaxonomyObjbject: %(qname)s."),
                          xbrlObject=expPrflObj, name=name, nbr=iSel, qname=selObj.objectType)
            for iWh, whereObj in enumerate(selObj.where):
                if whereObj.property is None or whereObj.operator is None or whereObj.value is None:
                    txmyMdl.error("oimte:invalidSelection",
                              _("The exportProfile %(name)s selection[%(nbr)s] is incomplete."),
                              xbrlObject=expPrflObj, name=name, nbr=iSel)
                else:
                    if whereObj.property.namespaceURI is None: # object property
                        if whereObj.property.localName not in getattr(xbrlObjectTypes[selObj.objectType], "__annotations__", EMPTY_DICT):
                            txmyMdl.error("oimte:invalidSelectorOperator",
                                      _("The exportProfile %(name)s selection[%(selNbr)s]/where[%(whNbr)s] property %(qname)s does not exist for object %(objType)s."),
                                      xbrlObject=expPrflObj, name=name, selNbr=iSel, whNbr=iWh, qname=whereObj.property, objType=selObj.objectType)
        expPrflCt[expPrflObj.name].append(expPrflObj)
    for expPrfName, objs in expPrflCt.items():
        if len(objs) > 1:
            txmyMdl.error("oimte:duplicateObjects",
                      _("These exportProfiles are duplicated: %(name)s"),
                      xbrlObject=objs, name=expPrfName)

    # Concept Objects
    for cncpt in txmy.concepts:
        assertObjectType(txmyMdl, cncpt, XbrlConcept)
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
        assertObjectType(txmyMdl, cubeType, XbrlCubeType)
        name = cubeType.name
        if cubeType.baseCubeType is not None:
            if cubeType.baseCubeType not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The cube type %(name)s, specifies base cube type %(base)s which is not defined."),
                          xbrlObject=cubeType, name=name, base=cubeType.baseCubeType)
            else:
                baseCubeType = txmyMdl.namedObjects.get(cubeType.baseCubeType)
                if isinstance(baseCubeType, XbrlCubeType):
                    if cubeType.periodDimension or cubeType.entityDimension or cubeType.unitDimension or cubeType.taxonomyDefinedDimension:
                        txmyMdl.error("oimte:dimensionsInconsistentWithBaseCube",
                                  _("The cube type %(name)s, specifies base cube type %(base)s and periodDimension, entityDimension, unitDimension and taxonomyDefinedDimension MUST be false if defined."),
                                  xbrlObject=cubeType, name=name, base=cubeType.baseCubeType)
                else:
                    txmyMdl.error("oimte:invalidQNameReference",
                              _("The cube type %(name)s, specifies base cube type %(base)s which is not a cube type object."),
                              xbrlObject=cubeType, name=name, base=cubeType.baseCubeType)
        allowedCubeDims = cubeType.effectivePropVal("allowedCubeDimensions", txmyMdl) # gets inherited property
        _derivedAlwdDims = cubeType.allowedCubeDimensions # gets this cubeType property
        if _derivedAlwdDims and _derivedAlwdDims != allowedCubeDims:
            txmyMdl.error("oimte:dimensionsInconsistentWithBaseCube",
                      _("The cubeType %(name)s, must not specify allowedCubeDimensions overriding base cue allowedCubeDimensions"),
                      xbrlObject=cubeType, name=name)
        if allowedCubeDims is not None:
            if not cubeType.effectivePropVal("taxonomyDefinedDimension", txmyMdl):
                txmyMdl.error("oimte:inconsistentTaxonomyDefinedDimensionProperty",
                          _("The cube %(name)s, type %(cubeType)s, allowedCubeDimensions MUST only be specified when taxonomyDefinedDimension is true."),
                          xbrlObject=cubeType, name=name, cubeType=cubeType.name)
            elif not allowedCubeDims:
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
                if _dimName in coreDimensions:
                    txmyMdl.error("oimte:coreDimensionDefinedAsAllowedCubeDimension",
                              _("The cube type %(name)s, allowedCubeDimension[%(i)s] object MUST NOT include a dimensionName property that is xbrl:concept, xbrl:entity, xbrl:unit, xbrl:period or xbrl:language."),
                              xbrlObject=cubeType, name=name, i=i, dimName=_dimName)
                else:
                    if not _dimName and not _dimType and not _typedDimType:
                        txmyMdl.error("oimte:cubeTypeAllowedDimensionProperties",
                                  _("The cube type %(name)s, allowedCubeDimension[%(i)s] object must specify one of dimensionName, dimensionType or dimensionDataType."),
                                  xbrlObject=cubeType, name=name, i=i, dimName=_dimName)
                    if _dimName and not isinstance(txmyMdl.namedObjects.get(_dimName), XbrlDimension):
                        txmyMdl.error("oimte:invalidTaxonomyDefinedDimension",
                                  _("The cube type %(name)s, allowedCubeDimension[%(i)s] dimensionName %(dimName)s does not resolve to a dimension object."),
                                  xbrlObject=cubeType, name=name, i=i, dimName=_dimName)
                    if _dimType not in (None, "typed", "explicit"):
                        txmyMdl.error("oimte:cubeTypeAllowedDimensionType",
                                  _("The cube type %(name)s, allowedCubeDimension[%(i)s] dimensionType %(dimType)s is invalid."),
                                  xbrlObject=cubeType, name=name, i=i, dimType=_dimType)
                    if _typedDimType and not isinstance(txmyMdl.namedObjects.get(_typedDimType), XbrlDataType):
                        txmyMdl.error("oimte:cubeTypeAllowedDimensionDataType",
                                  _("The cube type %(name)s, allowedCubeDimension[%(i)s], dimensionDataType %(typedDimType)s does not resolve to a dataType object."),
                                  xbrlObject=cubeType, name=name, i=i, typedDimType=_typedDimType)
                    if not _dimName and (not _dimType or not _typedDimType):
                        txmyMdl.error("oimte:missingDimensionTypeProperty",
                                  _("The cube type %(name)s, allowedCubeDimension[%(i)s], dimensionName is required if dimensionType or dimensionDataType is not defined."),
                                  xbrlObject=cubeType, name=name, i=i)
                    elif not _dimName and not _dimType:
                        txmyMdl.error("oimte:missingDimensionTypeProperty",
                                  _("The cube type %(name)s, allowedCubeDimension[%(i)s], dimensionType is required if dimensionName is not defined."),
                                  xbrlObject=cubeType, name=name, i=i, dimType=_dimType)
                    if _dimType == "explicit" and _typedDimType:
                        txmyMdl.error("oimte:invalidDimensionDataTypeProperty",
                                  _("The cube type %(name)s, allowedCubeDimension[%(i)s], dimensionType MUST NOT be defined if the dimensionType is explicit."),
                                  xbrlObject=cubeType, name=name, i=i, dimType=_dimType)
                for prop in ("allowedDimensionProperties", "requiredDimensionProperties"):
                    for propTpQn in getattr(allwdDim, prop):
                        if not isinstance(txmyMdl.namedObjects.get(propTpQn), XbrlPropertyType):
                            txmyMdl.error("oimte:missingQNameReference",
                                      _("The cubeType %(name)s %(property)s has an invalid propertyType reference %(propType)s"),
                                      xbrlObject=cubeType, name=cubeType.name, property=prop, propType=propTpQn)
        for i, reqdRelshp in enumerate(getattr(cubeType, "requiredCubeRelationships", ())):
            relType = getattr(reqdRelshp, "relationshipTypeName", None)
            if not isinstance(txmyMdl.namedObjects.get(relType), XbrlRelationshipType):
                txmyMdl.error("oimte:invalidRelationshipTypeName",
                          _("The cube type %(name)s, requiredCubeRelationship[%(i)s] relationshipTypeName %(relTypeName)s does not resolve to a relationshipType object."),
                          xbrlObject=cubeType, name=name, i=i, relTypeName=relType)
            for prop in ("source", "sourceObject", "sourceDatatype", "target", "targetObject", "targetDatatype"):
                compObj = prop.endswith("Object")
                propVal = getattr(reqdRelshp, prop, None)
                if propVal is not None and (
                    (compObj ^ (propVal in xbrlObjectTypes)) or
                    (not compObj and propVal not in txmyMdl.namedObjects)): # note that tag objects aren't referencable by name
                    txmyMdl.error("oimte:invalidSourceOrTargetObjectType" if compObj else "oimte:invalidSourceOrTargetType",
                              _("The cube type %(name)s, requiredCubeRelationship[%(i)s] %(property)s, %(value)s, does not resolve to a %(non)staxonomy component object."),
                              xbrlObject=cubeType, name=name, i=i, property=prop, value=propVal, non=("" if compObj else "non "))
        for propTpQn in cubeType.requiredCubeProperties:
            if not isinstance(txmyMdl.namedObjects.get(propTpQn), XbrlPropertyType):
                txmyMdl.error("oimte:missingQNameReference",
                          _("The cubeType %(name)s requiredCubeProperties has an invalid propertyType reference %(propType)s"),
                          xbrlObject=cubeType, name=cubeType.name, propType=propTpQn)

    # Cube Objects
    for cubeObj in txmy.cubes:
        assertObjectType(txmyMdl, cubeObj, XbrlCube)
        name = cubeObj.name
        cubeType = txmyMdl.namedObjects.get(cubeObj.cubeType or reportCubeType)
        ntwks = set()
        for ntwrkQn in cubeObj.cubeNetworks:
            ntwk = txmyMdl.namedObjects.get(ntwrkQn)
            if ntwk is None:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s an object in the model."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            elif not isinstance(ntwk, XbrlNetwork):
                txmyMdl.error("oimte:invalidQNameReference",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s to a network object."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
            else:
                 ntwks.add(ntwk)
        dimQnCounts = {}
        for cubeDimObj in cubeObj.cubeDimensions:
            dimQn = cubeDimObj.dimensionName
            dimObj = txmyMdl.namedObjects.get(dimQn)
            if dimQn not in coreDimensions and not isinstance(dimObj, XbrlDimension):
                txmyMdl.error("oimte:invalidTaxonomyDefinedDimension",
                          _("The cubeDimensions property on cube %(name)s MUST resolve to a dimension object: %(dimension)s"),
                          xbrlObject=cubeObj, name=name, dimension=dimQn)
            else:
                # specific cubeType dimension property validations
                tsProps = {timeSeriesPropType, intervalOfMeasurementPropType, intervalConventionPropType, excludedIntervalsPropType} & set(p.property for p in dimObj.properties)
                if tsProps:
                    if cubeType.name != timeSeriesCubeType:
                        txmyMdl.error("oimte:timeSeriesTypeOnNonTimeSeriesDimension" if timeSeriesPropType in tsProps else
                                      "oimte:intervalConventionOnNonTimeSeriesDimension" if intervalConventionPropType in tsProps else
                                      "oimte:intervalOfMeasurementOnNonTimeSeriesDimension",
                                  _("The dimension %(dimension)s properties %(tsProps)s on cube %(name)s type %(cubeType)s MUST only be used on a timeSeries cubeType."),
                                  xbrlObject=cubeObj, name=name, dimension=dimQn, cubeType=cubeType.name, tsProps=", ".join(str(p) for p in tsProps))
                    else:
                        dimDomDTQn = dimObj.domainDataType
                        domDTobj = txmyMdl.namedObjects.get(dimDomDTQn)
                        if not (isinstance(txmyMdl.namedObjects.get(dimDomDTQn), XbrlDataType) or
                                domDTobj.instanceOfType(qnXsDateTime, txmyMdl)):
                            txmyMdl.error("oimte:timeSeriesTypeOnNonTimeSeriesDimension",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s properties %(tsProps)s on cube %(name)s MUST only be used on a date-time typed dimension."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn, tsProps=", ".join(str(p) for p in tsProps))
                        if len(tsProps & {intervalOfMeasurementPropType, intervalConventionPropType}) == 1:
                            txmyMdl.error("oimte:missingIntervalOfMeasurementForConvention",
                                      _("The dimension %(dimension)s of domain type %(dimDomType)s on cube %(name)s MUST also have property %(tsProp)s."),
                                      xbrlObject=cubeObj, name=name, dimension=dimQn, dimDomType=dimDomDTQn,
                                      tsProp=next(iter({intervalOfMeasurementPropType, intervalConventionPropType} - tsProps)))
            dimQnCounts[dimQn] = dimQnCounts.get(dimQn, 0) + 1
        if any(c > 1 for c in dimQnCounts.values()):
            txmyMdl.error("oimte:duplicateDimensionsInCube",
                      _("The cubeDimensions of cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      xbrlObject=cubeObj, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items() if ct > 1))
        # check cube dims against cube type
        if not isinstance(cubeType, XbrlCubeType):
            txmyMdl.error("oimte:invalidQNameReference",
                      _("The cube %(name)s  cubeType %(qname)s must be a valid cube type."),
                      xbrlObject=cubeObj, name=name, qname=(cubeObj.cubeType or reportCubeType))
        else:
            if cubeType.basemostCubeType != defaultCubeType and conceptCoreDim not in dimQnCounts.keys():
                txmyMdl.error("oimte:cubeMissingConceptDimension",
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
                        if ((not allwdDim.dimensionName or dim.name == allwdDim.dimensionName)):
                            matchedDim = dim
                            matchedDimQNs.add(dim.name)
                            break
                    if not matchedDim and allwdDim.required:
                        txmyMdl.error("oimte:cubeMissingDimension",
                                  _("The cube %(name)s, type %(cubeType)s, taxonomy defined dimensions %(dimension)s is missing"),
                                  xbrlObject=cubeObj, name=name, cubeType=cubeType.name,
                                  dimension=', '.join(str(getattr(allwdDim,p)) for p in ("dimensionName", "dimensionType", "dimensionDataType") if getattr(allwdDim,p)))
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
                txmyMdl.error("oimte:excludeCubeSelfReference",
                          _("The cube %(name)s must not be defined in the excludeCubes property of itself."),
                          xbrlObject=cubeObj, name=name)
            if exclCubeQn not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The excludeCubes property on cube %(name)s, %(qname)s, must be defined in the taxonomy model."),
                          xbrlObject=cubeObj, name=name, qname=exclCubeQn)
            elif not isinstance(txmyMdl.namedObjects.get(exclCubeQn), XbrlCube):
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The excludeCubes property on cube %(name)s MUST resolve %(qname)s to a cube object."),
                          xbrlObject=cubeObj, name=name, qname=exclCubeQn)
        validateProperties(txmyMdl, oimFile, txmy, cubeObj)
        unitDataTypeQNs = set()
        cncptDataTypeQNs = set()
        for iCubeDim, cubeDimObj in enumerate(cubeObj.cubeDimensions):
            assertObjectType(txmyMdl, cubeDimObj, XbrlCubeDimension)
            dimName = cubeDimObj.dimensionName
            dimObj = txmyMdl.namedObjects.get(dimName)
            isTyped = False
            if not isinstance(dimObj, XbrlDimension):
                txmyMdl.error("oimte:dimensionNameNotDimensionObject",
                          _("Cube %(name)s dimensionName property MUST be a dimension object %(dimensionName)s."),
                          xbrlObject=cubeObj, name=name, dimensionName=dimName)
                continue # not worth going further with this cube dimension
            domRoot = txmyMdl.namedObjects.get(dimObj.domainRoot)
            if not isinstance(domRoot, XbrlDomainRoot):
                continue # not worth continuing, domain object missing root will be reported elsewhere
            elif domRoot.allowedDomainItems and all(
                    isinstance(txmyMdl.namedObjects.get(dt), XbrlDataType)
                    for dt in domRoot.allowedDomainItems):
                isTyped = True
            cubeDimDT = cubeDimObj.domainDataType
            if cubeDimDT:
                if isinstance(txmyMdl.namedObjects.get(cubeDimDT), XbrlDataType):
                    isTyped = True
                    if domRoot.allowedDomainItems and cubeDimDT not in domRoot.allowedDomainItems:
                        txmyMdl.error("oimte:invalidDataTypeForDomainRoot",
                                      _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST be included in the set of allowedDomainItems defined as a property of the domain root object: %(allowedDataItems)s."),
                                      xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT, allowedDataItems=", ".join(str(qn) for qn in domRoot.allowedDomainItems))
                    if dimName == periodCoreDim:
                        txmyMdl.error("oimte:domainUsedOnPeriodDimension",
                                      _("Cube %(name)s dimension %(dimensionName)s domainDataType %(dataType)s MUST not be used on a period dimension."),
                                      xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT, allowedDataItems=", ".join(str(qn) for qn in domRoot.allowedDomainItems))
                else:
                    txmyMdl.error("oimte:invalidPropertyValue",
                                  _("Cube %(name)s dimension %(dimensionName)s domainDataType must be a dataType object %(dataType)s."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName, dataType=cubeDimDT)
            if cubeDimObj.typedSort not in (None, "asc", "desc"):
                txmyMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s typedSort property MUST be asc or desc, not %(typedSort)s."),
                          xbrlObject=cubeObj, name=name, typedSort=cubeDimObj.typedSort)
            hasValidDomainName = False
            if cubeDimObj.domainName:
                if isTyped:
                    if dimName == periodCoreDim:
                        txmyMdl.error("oimte:domainUsedOnPeriodDimension",
                                  _("Cube %(name)s dimension %(dimensionName)s domain objects MUST NOT be defined with a domainName property."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                    else:
                        txmyMdl.error("oimte:domainRootMismatchWithDomain",
                                  _("Cube %(name)s dimension %(dimensionName)s domain objects MUST NOT be defined with a typed domainRoot object."),
                                  xbrlObject=cubeObj, name=name, dimensionName=dimName)
                    continue
                cubeDomObj = txmyMdl.namedObjects.get(cubeDimObj.domainName)
                if isinstance(cubeDomObj, XbrlDomain):
                    hasValidDomainName = True
                else:
                    txmyMdl.error("oimte:invalidCubeDimensionDomainName",
                              _("Cube %(name)s domainName property MUST identify a domain object: %(domainName)s."),
                              xbrlObject=cubeObj, name=name, domainName=cubeDimObj.domainName)
            if cubeDimObj.periodConstraints and dimName != periodCoreDim:
                txmyMdl.error("oimte:invalidPeriodConstraintDimension",
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
                    txmyMdl.error("oimte:invalidAllowDomainFactsPropertyOnConceptDimension",
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
                if not isTyped: # explicit
                    domObj = txmyMdl.namedObjects.get(cubeDimObj.domainName)
                    if isinstance(domObj, XbrlDomain):
                        for relObj in domObj.relationships:
                            if not isinstance(txmyMdl.namedObjects.get(getattr(relObj, "target", None),None), XbrlMember):
                                txmyMdl.error("oimte:invalidRelationshipTarget",
                                          _("Cube %(name)s explicit dimension domain relationships must be to members."),
                                          xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName)
                        if dimObj.domainRoot and domObj.root and dimObj.domainRoot != domObj.root:
                            txmyMdl.error("oimte:invalidCubeDimensionDomainName",
                                      _("Cube %(name)s explicit dimension domain root %(domRoot)s does not match dimension domainRoot %(dimRoot)s."),
                                      xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName, domRoot=domObj.root, dimRoot=dimObj.domainRoot)
            if not isTyped: # explicit dimension
                if cubeDimObj.typedSort is not None:
                    txmyMdl.error("oimte:invalidCubeDimensionProperty",
                              _("Cube %(name)s typedSort property MUST not be used on an explicit dimension."),
                              xbrlObject=cubeObj, name=name)
            if dimName == periodCoreDim:
                if cubeDimObj.domainName:
                    txmyMdl.error("oimte:domainUsedOnPeriodDimension",
                              _("Cube %(name)s domainName property MUST NOT be used where the dimension property has a QName value %(qname)s."),
                              xbrlObject=cubeObj, name=name, qname=dimName)
                for iPerConst, perConstObj in enumerate(cubeDimObj.periodConstraints):
                    if perConstObj.periodType not in ("instant", "duration", "none"):
                        txmyMdl.error("oimte:invalidPeriodRepresentation",
                                  _("Cube %(name)s period constraint periodType property MUST be \"instant\" or \"duration\"."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    if perConstObj.timeSpan:
                        if perConstObj.endDate and perConstObj.startDate:
                            txmyMdl.error("oimte:redundantTimeSpanProperty",
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
                                if not isinstance(cncpt, XbrlConcept) or not isinstance(txmyMdl.namedObjects.get(cncpt.dataType), XbrlDataType) or txmyMdl.namedObjects[cncpt.dataType].xsBaseType(txmyMdl) not in ("date", "dateTime"):
                                    txmyMdl.error("oimte:invalidQNameReference",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a date or dateTime."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                            if dtResObj.context:
                                cncpt = txmyMdl.namedObjects.get(dtResObj.context)
                                if not cncpt or not isinstance(cncpt, XbrlConcept) or (dtResObj.context.atSuffix not in ("start","end")):
                                    txmyMdl.error("oimte:invalidQNameReference",
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
        assertObjectType(txmyMdl, dtObj, XbrlDataType)
        btQn = dtObj.baseType
        if btQn and btQn.namespaceURI != "http://www.w3.org/2001/XMLSchema" and not isinstance(txmyMdl.namedObjects.get(btQn), XbrlDataType):
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The dataType object %(name)s MUST define a valid baseType which must be a dataType object in the taxonomy model"),
                      xbrlObject=dtObj, name=dt.name)
        if dtObj.unitType is not None:
            utObj = dtObj.unitType
            assertObjectType(txmyMdl, utObj, XbrlUnitType)
            for utProp in ("dataTypeNumerator", "dataTypeDenominator", "dataTypeMultiplier"):
                utPropQn = getattr(utObj, utProp)
                if utPropQn and not isinstance(txmyMdl.namedObjects.get(utPropQn), XbrlDataType):
                    txmyMdl.error("oimte:invalidPropertyValue",
                              _("The dataType object unitType %(name)s MUST define a valid dataType object in the taxonomy model"),
                              xbrlObject=dtObj, name=dt.name)

    # Dimension Objects
    for dimObj in txmy.dimensions:
        assertObjectType(txmyMdl, dimObj, XbrlDimension)
        for cubeTypeQn in dimObj.cubeTypes:
            if cubeTypeQn not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The dimension cubeType QName %(name)s MUST exist in the taxonomy model"),
                          xbrlObject=dimObj, name=cubeTypeQn)
            elif not isinstance(txmyMdl.namedObjects.get(cubeTypeQn), XbrlCubeType):
                txmyMdl.error("oimte:invalidCubeType",
                          _("The dimension cubeType QName %(name)s MUST be a valid cubeType object in the taxonomy model"),
                          xbrlObject=dimObj, name=cubeTypeQn)
        dimDomRtQn = dimObj.domainRoot
        if dimDomRtQn:
            domRtObj = txmyMdl.namedObjects.get(dimDomRtQn)
            if domRtObj is None:
                txmyMdl.error("oimte:missingQNameReference",
                          _("The dimension domainRoot object QName %(name)s MUST be a valid domainRoot object in the taxonomy model"),
                          xbrlObject=dimObj, name=dimDomRtQn)
            elif not isinstance(domRtObj, XbrlDomainRoot):
                txmyMdl.error("oimte:invalidDomainRoot",
                          _("The dimension domainRoot object QName %(name)s MUST be a valid domainRoot object in the taxonomy model"),
                          xbrlObject=dimObj, name=dimDomRtQn)

            if (dimDomRtQn in (conceptDomainRoot, entityDomainRoot, unitDomainRoot, languageDomainRoot) and
                              (dimObj.name.namespaceURI != xbrl or not dimDomRtQn.localName.startswith(dimObj.name.localName))):
                txmyMdl.error(f"oimte:invalid{dimDomRtQn.localName[:-6].title()}DomainRoot",
                          _("The dimension domainRoot object QName MUST not be %(name)s."),
                          xbrlObject=dimObj, name=dimDomRtQn)
        validateProperties(txmyMdl, oimFile, txmy, dimObj)
        exclIntPropStr = dimObj.propertyObjectValue(excludedIntervalsPropType)
        if exclIntPropStr is not None:
            try:
                if isinstance(exclIntPropStr, list): # allow list of strings
                    exclIntPropStr = "\n".join(exclIntPropStr)
                dimObj._excludedIntervals = dateutil.rrule.rrulestr(exclIntPropStr.replace("\\n", "\n"))
            except dateutil.parser._parser.ParserError as ex:
                txmyMdl.error("oimte:invalidExcludedIntervals",
                          _("The dimension %(name)s excludedIntervals property error %(error)s, value %(excludedIntervals)s."),
                          xbrlObject=dimObj, name=dimObj.name, error=str(ex), excludedIntervals=exclIntPropStr)

    # Domain Objects
    for domObj in txmy.domains:
        assertObjectType(txmyMdl, domObj, XbrlDomain)
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
            elif extendTargetObj.completeDomain:
                txmyMdl.error("oimte:cannotExtendCompleteDomain",
                          _("The domain %(name)s cannot be extended because it is a completeDomain."),
                          xbrlObject=domObj, name=extendTargetObj.name)
                continue
            else:
                domObj._extendResolved = True
        elif not domObj.name:
            txmyMdl.error("oimte:missingRequiredProperty",
                      _("The domain object MUST have either a name or an extendTargetName, not neither."),
                      xbrlObject=domObj)
        domRtQn = domObj.root
        domRtObj = txmyMdl.namedObjects.get(domRtQn)
        if txmyMdl.namedObjects is None:
            txmyMdl.error("oimte:missingQNameReference",
                      _("The domain %(name)s root %(qname)s MUST exist in the taxonomy model"),
                      xbrlObject=domObj, name=domObj.name, qname=domRtQn)
        if not isinstance(domRtObj, XbrlDomainRoot):
            txmyMdl.error("oimte:invalidDomainRoot",
                      _("The domain %(name)s root %(qname)s MUST be a valid domainRoot object in the taxonomy model"),
                      xbrlObject=domObj, name=domObj.name, qname=domRtQn)
            domRtObj = None
        domRelCts = {}
        domRelRoots = set(relObj.source for relObj in domObj.relationships if getattr(relObj, "source", None))
        domRootSourceInRel = domRtObj is not None # only check if there are any relationships
        for i, relObj in enumerate(domObj.relationships):
            if i == 0:
                domRootSourceInRel = False
            assertObjectType(txmyMdl, relObj, XbrlRelationship)
            src = getattr(relObj, "source", None)
            tgt = getattr(relObj, "target", None)
            if src not in txmyMdl.namedObjects or tgt not in txmyMdl.namedObjects:
                if src not in txmyMdl.namedObjects:
                    txmyMdl.error("oimte:missingQNameReference",
                              _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=domObj.name, nbr=i, source=src)
                if tgt not in txmyMdl.namedObjects:
                    txmyMdl.error("oimte:missingQNameReference",
                              _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=domObj.name, nbr=i, target=tgt)
            else:
                if domRtQn == conceptDomainRoot:
                    if relObj.source != domRtQn and not isinstance(txmyMdl.namedObjects[relObj.source], (XbrlConcept, XbrlAbstract)):
                        txmyMdl.error("oimte:invalidConceptDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s MUST be a concept object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects[relObj.target], (XbrlConcept, XbrlAbstract)):
                        txmyMdl.error("oimte:invalidDomainRelationshipTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be a concept object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                if domRtQn == entityDomainRoot:
                    if relObj.source != domRtQn and not isinstance(txmyMdl.namedObjects[relObj.source], XbrlEntity):
                        txmyMdl.error("oimte:invalidEntityDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the entity root or an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects[relObj.target], XbrlEntity):
                        txmyMdl.error("oimte:invalidEntityDomainTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be an entity object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                if domRtQn == unitDomainRoot:
                    if relObj.source != domRt and not isinstance(txmyMdl.namedObjects[relObj.source], XbrlUnit):
                        txmyMdl.error("oimte:invalidUnitDomainSource",
                                  _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, MUST be the unit root or an unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects[relObj.target], XbrlUnit):
                        txmyMdl.error("oimte:invalidUnitDomainTarget",
                                  _("The domain %(name)s relationship[%(nbr)s] target, %(target)s, MUST be a unit object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, target=relObj.target)
                elif isinstance(txmyMdl.namedObjects[relObj.source], XbrlUnit) or isinstance(txmyMdl.namedObjects[relObj.target], XbrlUnit):
                    txmyMdl.error("oimte:unitInNonUnitDomain",
                              _("The domain %(name)s relationship[%(nbr)s] source, %(source)s, or target, %(target)s, MUST be not be unit objects in the taxonomy model."),
                              xbrlObject=relObj, name=domObj.name, nbr=i, source=relObj.source, target=relObj.target)
                for prop in ("source", "target"):
                    obj = txmyMdl.namedObjects[getattr(relObj, prop)]
                    if isinstance(obj, XbrlMember) and domRtQn in (conceptDomainRoot, unitDomainRoot, entityDomainRoot, languageDomainRoot):
                        txmyMdl.error("oimte:invalidDimensionMember",
                                  _("The domain %(name)s relationship[%(nbr)s] %(property)s, %(propQn)s MUST be not be a member object in the taxonomy model."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, property=prop, propQn=getattr(relObj, prop))
                    if domRtObj and domRtObj.allowedDomainItems and (
                        xbrlObjectQNames.get(obj) not in domRtObj.allowedDomainItems
                        and (prop != "srouce" and obj != domRtObj)):
                        txmyMdl.error("oimte:invalidDomainObject",
                                  _("The domain %(name)s relationship[%(nbr)s] %(property)s, %(propQn)s MUST be only be objects in the allowedDomainItems."),
                                  xbrlObject=relObj, name=domObj.name, nbr=i, property=prop, propQn=getattr(relObj, prop))
            if isinstance(txmyMdl.namedObjects.get(tgt), XbrlDomainRoot):
                txmyMdl.error("oimte:invalidDomainRootTarget",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domainRoot object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            elif isinstance(txmyMdl.namedObjects.get(tgt), XbrlDomain):
                txmyMdl.error("oimte:invalidObjectType",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domain object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            elif extendTargetObj is not None:
                extendTargetObj.relationships.add(relObj)
            if tgt == domRtQn:
                txmyMdl.error("oimte:invalidDomainTarget",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be the domain root object."),
                          xbrlObject=domObj, name=domObj.name, qname=tgt)
            if domRtQn == src:
                domRootSourceInRel = True
            relKey = (src, tgt)
            domRelCts[relKey] = domRelCts.get(relKey, 0) + 1
            domRelRoots.discard(tgt) # remove any target from roots
        if any(ct > 1 for relKey, ct in domRelCts.items()):
            txmyMdl.error("oimte:duplicateObjects",
                      _("The domain %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=domObj, name=domObj.name,
                      names=", ".join(f"{relKey[0]}\u2192{relKey[1]}" for relKey, ct in domRelCts.items() if ct > 1))
        if not domRootSourceInRel:
            txmyMdl.error("oimte:missingDomainRootSource",
                      _("The domain %(name)s root %(qname)s MUST be a source in a relationship"),
                      xbrlObject=domObj, name=domObj.name, qname=domObj.root)
        if len(domRelRoots) > 1:
            txmyMdl.error("oimte:multipleDomainRoots",
                      _("The domain %(name)s relationship must resolve to a single root object, multiple found: %(roots)s"),
                      xbrlObject=domObj, name=domObj.name, roots=", ".join(sorted(str(r) for r in domRelRoots)))
        validateProperties(txmyMdl, oimFile, txmy, domObj)


    # DomainRoot Objects
    for domRtObj in txmy.domainRoots:
        assertObjectType(txmyMdl, domRtObj, XbrlDomainRoot)
        name = domRtObj.name
        for allwdDomItemQn in domRtObj.allowedDomainItems:
            allwdDomItemObj = txmyMdl.namedObjects.get(allwdDomItemQn)
            if allwdDomItemQn not in (qnXbrlMemberObj, qnXbrlAbstractObj, qnXbrlConceptObj, qnXbrlEntityObj, qnXbrlUnitObj) and not isinstance(allwdDomItemObj, XbrlDataType):
                txmyMdl.error("oimte:invalidPropertyValue",
                  _("DomainRoot %(name)s allowedDomainItem must be a member, xbrl object, or a dataType object %(allowedDomainItem)s."),
                  xbrlObject=domRtObj, name=name, allowedDomainItem=allwdDomItemQn)
        validateProperties(txmyMdl, oimFile, txmy, domRtObj)

    # Entity Objects
    for entityObj in txmy.entities:
        assertObjectType(txmyMdl, entityObj, XbrlEntity)
        validateProperties(txmyMdl, oimFile, txmy, entityObj)

    # GroupContent Objects
    for grpCntObj in txmy.groupContents:
        assertObjectType(txmyMdl, grpCntObj, XbrlGroupContent)
        grpQn = grpCntObj.groupName
        if grpQn not in txmyMdl.namedObjects or type(txmyMdl.namedObjects[grpQn]) != XbrlGroup:
            txmyMdl.error("oimte:invalidGroupObject",
                      _("The groupContent object groupName QName %(name)s MUST be a valid group object in the taxonomy model"),
                      xbrlObject=grpCntObj, name=grpQn)
        for relName in grpCntObj.relatedNames:
            if relName not in txmyMdl.namedObjects or not isinstance(txmyMdl.namedObjects.get(relName), (XbrlNetwork, XbrlCube, XbrlTableTemplate, XbrlDomain)):
                txmyMdl.error("oimte:invalidGroupObject",
                          _("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects or table template objects."),
                          xbrlObject=grpCntObj, name=grpQn, relName=relName)

    # Label Objects
    for lblObj in txmy.labels:
        assertObjectType(txmyMdl, lblObj, XbrlLabel)
        relatedName = lblObj.relatedName
        relatedObj = None
        if relatedName in txmyMdl.namedObjects:
            relatedObj = txmyMdl.namedObjects.get(relatedName)
        elif relatedName in xbrlObjectTypes:
            relatedObj = relatedName
        else:
            txmyMdl.error("oimte:unresolvedRelatedName",
                      _("Label has invalid related object %(relatedName)s"),
                      xbrlObject=lblObj, relatedName=relatedName)
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
        lblKey = (relatedName, lblObj.labelType, lblObj.language)
        mdlLvlChecks.labelsCt[lblKey].append(lblObj)

    # Network Objects
    ntwkCt = {}
    for ntwkObj in txmy.networks:
        assertObjectType(txmyMdl, ntwkObj, XbrlNetwork)
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
            else:
                relTypeObj = txmyMdl.namedObjects.get(extendTargetObj.relationshipTypeName)
                if not isinstance(relTypeObj, XbrlRelationshipType):
                    relTypeObj = None
                    txmyMdl.warning("oimte:missingQNameReference",
                              _("The network %(name)s relationshipTypeName %(relationshipTypeName)s SHOULD specify a relationship type in the taxonomy model."),
                              xbrlObject=ntwkObj, name=ntwkObj.name, relationshipTypeName=ntwkObj.relationshipTypeName)
                if getattr(ntwkObj, "_extendResolved", False):
                    extendTargetObj = None # don't extend, already been extended
                else:
                    ntwkObj._extendResolved = True
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
            assertObjectType(txmyMdl, relObj, XbrlRelationship)
            if  relObj.source not in txmyMdl.namedObjects or relObj.target not in txmyMdl.namedObjects:
                if relObj.source not in txmyMdl.namedObjects:
                    txmyMdl.error("oimte:missingQNameReference",
                              _("The network %(name)s relationship[%(nbr)s] source, %(source)s MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=ntwkObj.name, nbr=i, source=relObj.source)
                if relObj.target not in txmyMdl.namedObjects:
                    txmyMdl.error("oimte:missingQNameReference",
                              _("The network %(name)s relationship[%(nbr)s] target, %(target)s MUST be an object in the taxonomy model."),
                              xbrlObject=relObj, name=ntwkObj.name, nbr=i, target=relObj.target)
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
            relObjPrefLbl = relObj.propertyObjectValue(preferredLabel)
            if relObjPrefLbl and  not isinstance(txmyMdl.namedObjects.get(relObjPrefLbl), XbrlLabelType):
                txmyMdl.error("oimte:missingQNameReference",
                          _("The network %(name)s relationship[%(nbr)s] preferredLabel, %(preferredLabel)s MUST be a label type object."),
                          xbrlObject=relObj, name=ntwkObj.name, nbr=i, preferredLabel=relObjPrefLbl)
            relKey = (relObj.source, relObj.target, relObjPrefLbl, relObj.order)
            ntwkCt[relKey] = ntwkCt.get(relKey, 0) + 1
        if any(ct > 1 for relKey, ct in ntwkCt.items()):
            txmyMdl.error("oimte:duplicateObjects",
                      _("The network %(name)s has duplicated relationships %(names)s"),
                      xbrlObject=ntwkObj, name=ntwkObj.name,
                      names=", ".join(f"{relFrom}\u2192{relTo}{f' [{str(prefLbl)}]' if prefLbl else ''} ord {str(ordr)}"
                                      for (relFrom, relTo, prefLbl, ordr), ct in ntwkCt.items() if ct > 1))
        ntwkObj._rootsFound = sources - targets
        if ntwkObj.roots:
            undeclaredRoots = ntwkObj._rootsFound - ntwkObj.roots
            if undeclaredRoots:
                txmyMdl.error("oimte:invalidNetworkRoot",
                          _("The network %(name)s network object roots property does not include these undeclared relationship roots: %(undeclaredRoots)s"),
                          xbrlObject=ntwkObj, name=ntwkObj.name, undeclaredRoots=", ".join(str(r) for r in undeclaredRoots))
        else:
            ntwkObj.roots = ntwkObj._rootsFound # not specified so use actual roots
        validateProperties(txmyMdl, oimFile, txmy, ntwkObj)
        del ntwkCt

    # PropertyType Objects
    for i, propTpObj in enumerate(txmy.propertyTypes):
        assertObjectType(txmyMdl, propTpObj, XbrlPropertyType)
        dataTypeObj = txmyMdl.namedObjects.get(propTpObj.dataType)
        if not isinstance(dataTypeObj, XbrlDataType):
            txmyMdl.error("oimte:missingQNameReference",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                      xbrlObject=propTpObj, name=propTpObj.name, qname=propTpObj.dataType)
        elif propTpObj.enumerationDomain and dataTypeObj.xsBaseType(txmyMdl) != "QName":
            txmyMdl.error("oimte:missingQNameReference",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                      xbrlObject=propTpObj, name=propTpObj.name, qname=propTpObj.dataType)
        for allowedObjQn in propTpObj.allowedObjects:
            if allowedObjQn not in objectsWithProperties:
                txmyMdl.error("oimte:invalidAllowedObject",
                          _("The property %(name)s has an invalid allowed object %(allowedObj)s"),
                          xbrlObject=propTpObj, name=propTpObj.name, allowedObj=allowedObjQn)

    # RelationshipType Objects
    for relTpObj in txmy.relationshipTypes:
        assertObjectType(txmyMdl, relTpObj, XbrlRelationshipType)
        for prop in ("allowedLinkProperties", "requiredLinkProperties"):
            for propTpQn in getattr(relTpObj, prop):
                if not isinstance(txmyMdl.namedObjects.get(propTpQn), XbrlPropertyType):
                    txmyMdl.error("oimte:missingQNameReference",
                              _("The relationshipType %(name)s %(property)s has an invalid propertyType reference %(propType)s"),
                              xbrlObject=relTpObj, name=relTpObj.name, property=prop, propType=propTpQn)
        reqdNotAllowed = relTpObj.requiredLinkProperties - relTpObj.allowedLinkProperties
        if reqdNotAllowed:
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The relationshipType %(name)s has an required properties which are not allowed %(propTypes)s"),
                      xbrlObject=propTpObj, name=relTpObj.name, property=prop, propTypes=", ".join(str(q) for q in reqdNotAllowed))

    # Reference Objects
    refsWithInvalidRelName = []
    refInvalidNames = []
    refsDup = defaultdict(list)
    for refObj in txmy.references:
        assertObjectType(txmyMdl, refObj, XbrlReference)
        name = refObj.name
        lang = refObj.language
        refTp = refObj.referenceType
        extName = refObj.extendTargetName
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
        txmyMdl.error("oimte:missingQNameReference",
                  _("References have invalid related object names %(relNames)s"),
                  xbrlObject=refsWithInvalidRelName, name=name, relNames=", ".join(str(qn) for qn in refInvalidNames))
    for name, refsDups in refsDup.items():
        if len(refsDups) > 1:
            txmyMdl.error("oimte:duplicateObjects",
                          _("The referenceType %(name)s is duplicated."),
                          xbrlObject=refsDups, name=name)
    del refsWithInvalidRelName, refInvalidNames, refsDup # dereference

    # LabelType Objects
    lblTpCt = {}
    for lblObj in txmy.labelTypes:
        assertObjectType(txmyMdl, lblObj, XbrlLabelType)
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

    # ReferenceType Objects
    refTpCt = {}
    for refObj in txmy.referenceTypes:
        assertObjectType(txmyMdl, refObj, XbrlReferenceType)
        for allowedObj in refObj.allowedObjects:
            if allowedObj not in referencableObjectTypes:
                txmyMdl.error("oimte:invalidObjectType",
                          _("The referenceType %(name)s allowedObject %(allowedObject)s MUST be a referenceable taxonomy model object."),
                          xbrlObject=refObj, name=refObj.name, allowedObject=allowedObj)
        for prop, msgCode in (("orderedProperties","oimte:invalidOrderedProperty"),
                              ("requiredProperties","oimte:invalidRequiredProperty")):
            for propTpQn in getattr(refObj, prop):
                propTpObj = txmyMdl.namedObjects.get(propTpQn)
                if not isinstance(propTpObj, XbrlPropertyType):
                    txmyMdl.error("oimte:missingQNameReference",
                              _("The referenceType %(name)s %(property)s has an unresolvable propertyType reference %(propType)s"),
                              xbrlObject=refObj, name=refObj.name, property=prop, propType=propTpQn)
                elif propTpObj.allowedObjects and qnXbrlReferenceObj not in propTpObj.allowedObjects:
                    txmyMdl.error(msgCode,
                              _("The relationshipType %(name)s %(property)s has a propertyType not usable on reference objects %(propType)s"),
                              xbrlObject=refObj, name=refObj.name, property=prop, propType=propTpQn)

    # Unit Objects
    for unitObj in txmy.units:
        assertObjectType(txmyMdl, unitObj, XbrlUnit)
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
            for md in uMeas:
                for m in md:
                    if m not in txmyMdl.namedObjects:
                        txmyMdl.error("oimte:missingQNameReference",
                                  _("The unit %(name)s measure %(measure)s must exist in the taxonomy model."),
                                  xbrlObject=unitObj, name=unitObj.name, measure=m)

    # Facts in taxonomy
    if txmy.factspaces:
        global validateFactspace
        if validateFactspace is None:
            from .ValidateReport import validateFactspace
        for factspace in txmy.factspaces:
            validateFactspace(factspace, txmy.name, txmy, txmyMdl)

def validateLayout(txmyMdl, layout):
    oimFile = str(layout.name)

    # Taxonomy object
    assertObjectType(txmyMdl, layout, XbrlLayout)

    for tblTmpl in txmy.tableTemplates:
        assertObjectType(txmyMdl, tblTmpl, XbrlTableTemplate)

        for dim in tblTmpl.dimensions:
            if dim.startswith('$'):
                colName = dim[1:]
                if colName not in tblTmpl.columns:
                    txmyMdl.error("oimte:tableTemplateDimensionColumnReference",
                              _("The table template dimension %(dimension)s is missing from the table template columns."),
                              xbrlObject=tblTmpl, dimension=dim)

    for dataTbl in txmy.dataTables:
        assertObjectType(txmyMdl, dataTbl, XbrlDataTable)

        for axisName, axis in (("xAxis", dataTbl.xAxis), ("yAxis", dataTbl.yAxis), ("zAxis", dataTbl.zAxis)):
            assertObjectType(txmyMdl, axis, XbrlAxis)
            dimsOnThisAxis = {} # qnames of axis dimensions and counts on axis
            for axisDimName in axis.dimensionNames:
                if axisDimName.dimensionName in (conceptCoreDim, unitCoreDim, periodCoreDim) and axisDimName.showTotal:
                    txmyMdl.error("oimte:invalidShowTotalValue",
                              _("For dimension $(dimension)s, showTotal MUST be absent or false,"),
                              xbrlObject=dataTbl, dimension=axisDimName.dimensionName)
                dimsOnThisAxis[axisDimName.dimensionName] = dimsOnThisAxis.get(axisDimName.dimensionName,0) + 1
            if any(d.value() > 1 for d in dimsOnThisAxis.values()):
                txmyMdl.error("oimte:multipleDimensionsForPresentationNetwork",
                          _("The axes %(axes)s on dataTable %(dataTable)s have more than one of the same dimension."),
                          xbrlObject=dataTbl, axes=", ".join(str(d) for d,c in dimsOnThisAxis.items() if c > 1))
                txmyMdl.error("oimte:invalidObjectType",
                          _("The importObjectTypes property MUST specify valid OIM object types, %(qname)s is not valid."),
                          xbrlObject=impTxObj, qname=qnObjType)
