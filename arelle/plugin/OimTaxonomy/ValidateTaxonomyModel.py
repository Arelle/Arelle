'''
See COPYRIGHT.md for copyright information.
'''

import regex as re
from collections import defaultdict
from arelle.ModelValue import QName
from arelle.XmlValidate import languagePattern, validateValue as validateXmlValue
from arelle.PythonUtil import attrdict
from arelle.oim.Load import EMPTY_DICT, periodForms
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlCube import (XbrlCube, XbrlCubeType, baseCubeTypes, XbrlCubeDimension,
                       periodCoreDim, conceptCoreDim, entityCoreDim, unitCoreDim, languageCoreDim, coreDimensions,
                    conceptDomainRoot, entityDomainRoot, unitDomainRoot)
from .XbrlDimension import XbrlDimension, XbrlDomain, XbrlDomainRoot, XbrlMember
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent
from .XbrlImportTaxonomy import XbrlImportTaxonomy
from .XbrlLabel import XbrlLabel
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlPropertyType
from .XbrlReference import XbrlReference
from .XbrlTableTemplate import XbrlTableTemplate
from .XbrlTaxonomyModule import XbrlTaxonomyModule, xbrlObjectTypes, xbrlObjectQNames
from .XbrlUnit import XbrlUnit
from .XbrlConst import qnXsQName, qnXsDateTime, qnXsDuration, objectsWithProperties

perCnstrtFmtStartEndPattern = re.compile(r".*@(start|end)")

def validateTaxonomyModel(txmyMdl):

    for txmy in txmyMdl.taxonomies.values():
        validateTaxonomy(txmyMdl, txmy)

def objType(obj):
    clsName = type(obj).__name__
    if clsName.startswith("Xbrl"):
        return clsName[4:]
    return clsName

def validateValue(txmyMdl, obj, value, dataTypeQn, pathElt):
    if isinstance(dataTypeQn, QName):
        dataTypeObj = txmyMdl.namedObjects.get(dataTypeQn)
        if not isinstance(dataTypeObj, XbrlDataType): # validity checked in owner object validations
            return
        dataTypeLn = dataTypeObj.xsBaseType(txmyMdl)
        facets = dataTypeObj.xsFacets()
    else: # string data type
        dataTypeLn = dataTypeQn
        facets = EMPTY_DICT
    prototypeElt = attrdict(elementQname=dataTypeQn,
                            entryLoadingUrl=obj.entryLoadingUrl + pathElt)
    validateXmlValue(txmyMdl, prototypeElt, None, dataTypeLn, value, False, False, facets)



def validateProperties(txmyMdl, oimFile, txmy, obj):
    for i, propObj in enumerate(obj.properties):
        propTypeQn = propObj.property
        propTypeObj = txmyMdl.namedObjects.get(propTypeQn)
        if not isinstance(propTypeObj, XbrlPropertyType):
            txmyMdl.error("oime:invalidPropertyTypeObject",
                      _("%(parentObjName)s %(parentName)s property %(name)s has undefined dataType %(dataType)s"),
                      file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                      name=propTypeQn, dataType=propTypeQn)
        else: # have property type object
            if propTypeObj.allowedObjects:
                if xbrlObjectQNames.get(type(obj)) not in propTypeObj.allowedObjects:
                    txmyMdl.error("oime:disallowedObjectProperty",
                              _("%(parentObjName)s %(parentName)s property %(name)s not an allowed property type for the object."),
                              file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                              name=propTypeQn)
            validateValue(txmyMdl, obj, propObj.value, propTypeObj.dataType, f"/properties[{i}]")

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
        perType = cncpt.periodType
        if perType not in ("instant", "duration"):
            txmyMdl.error("oime:invalidPropertyValue",
                      _("Concept %(name)s has invalid period type %(perType)s"),
                      xbrlObject=cncpt, name=cncpt.name, perType=perType)
        dataTypeQn = cncpt.dataType
        if dataTypeQn not in txmyMdl.namedObjects or not isinstance(txmyMdl.namedObjects[dataTypeQn], XbrlDataType):
            txmyMdl.error("oime:invalidDataTypeObject",
                      _("Concept %(name)s has invalid dataType %(dataType)s"),
                      xbrlObject=cncpt, name=cncpt.name, dataType=dataTypeQn)
        enumDomQn = cncpt.enumerationDomain
        if enumDomQn and (enumDomQn not in txmyMdl.namedObjects or not isinstance(txmyMdl.namedObjects[enumDomQn], XbrlDomain)):
            txmyMdl.error("oime:invalidEnumerationDomainObject",
                      _("Concept %(name)s has invalid enumeration domain reference %(enumDomain)s"),
                      xbrlObject=cncpt, name=cncpt.name, enumDomain=enumDomQn)
        validateProperties(txmyMdl, oimFile, txmy, cncpt)


    # Cube Objects
    for cubeObj in txmy.cubes:
        assertObjectType(cubeObj, XbrlCube)
        name = cubeObj.name
        if cubeObj.cubeType and cubeObj.cubeType not in baseCubeTypes:
            if not isinstance(txmyMdl.namedObjects.get(cubeObj.cubeType), XbrlCubeType):
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The cube %(name)s  cubeType %(qname)s must be a valid cube type."),
                          xbrlObject=cubeObj, name=name, qname=cubeObj.cubeType)
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
                      _("The cubeDimensions property on cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      xbrlObject=cubeObj, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items if ct > 1))
        for ntwrkQn in cubeObj.cubeNetworks:
            if not isinstance(txmyMdl.namedObjects.get(ntwrkQn), XbrlNetwork):
                txmyMdl.error("oimte:invalidCubeNetwork",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s to a network object."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
        for exclCubeQn in cubeObj.excludeCubes:
            if exclCubeQn == cubeObj.name:
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The cube %(name)s must not be defined in the excludeCubes property of itself."),
                          xbrlObject=cubeObj, name=name)
            if not isinstance(txmyMdl.namedObjects.get(exclCubeQn), XbrlCube):
                txmyMdl.error("oimte:missingQNameReference",
                          _("The excludeCubes property on cube %(name)s MUST resolve %(qname)s to a cube object."),
                          xbrlObject=cubeObj, name=name, qname=exclCubeQn)
        validateProperties(txmyMdl, oimFile, txmy, cubeObj)
        unitDataTypeQNs = set()
        cncptDataTypeQNs = set()
        for iCubeDim, cubeDimObj in enumerate(cubeObj.cubeDimensions):
            assertObjectType(cubeDimObj, XbrlCubeDimension)
            dimName = cubeDimObj.dimensionName
            if cubeDimObj.domainSort not in (None, "asc", "desc"):
                txmyMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s domainSort property MUST be asc or desc, not %(domainSort)s."),
                          xbrlObject=cubeObj, name=name, domainSort=cubeDimObj.domainSort)
            if cubeDimObj.periodConstraints and dimName != periodCoreDim:
                txmyMdl.error("oimte:invalidDimensionConstraint",
                          _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)
            if dimName == conceptCoreDim and isinstance(txmyMdl.namedObjects.get(cubeDimObj.domainName), XbrlDomain):
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
            if dimName == entityCoreDim and isinstance(txmyMdl.namedObjects.get(cubeDimObj.domainName), XbrlDomain):
                for relObj in txmyMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(txmyMdl.namedObjects.get(relObj.source,None), XbrlEntity) and relObj.source != entityDomainRoot:
                        txmyMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s entityConstraints domain relationships must be from entities, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects.get(relObj.target,None), XbrlEntity):
                        txmyMdl.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s entityConstraints domain relationships must be to entities, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
            if dimName == unitCoreDim and isinstance(txmyMdl.namedObjects.get(cubeDimObj.domainName), XbrlDomain):
                for relObj in txmyMdl.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(txmyMdl.namedObjects.get(relObj.source,None), XbrlUnit) and relObj.source != unitDomainRoot:
                        txmyMdl.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s unitConstraints domain relationships must be from units, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if not isinstance(txmyMdl.namedObjects.get(relObj.target,None), XbrlUnit):
                        txmyMdl.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s unitConstraints domain relationships must be to units, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
            if dimName not in coreDimensions and isinstance(txmyMdl.namedObjects.get(dimName), XbrlDimension):
                dimObj = txmyMdl.namedObjects[dimName]
                if dimObj.domainDataType: # typed
                    if dimObj.domainRoot:
                        txmyMdl.error("oimte:invalidQNameReference",
                                  _("Cube %(name)s typed dimension %(qname)s must not specify a domain root."),
                                  xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName)
                else: # explicit dim
                    domObj = txmyMdl.namedObjects.get(cubeDimObj.domainName)
                    if domObj:
                        for relObj in domObj.relationships:
                            if not isinstance(txmyMdl.namedObjects.get(getattr(relObj, "target", None),None), XbrlMember):
                                txmyMdl.error("oimte:invalidRelationshipTarget",
                                          _("Cube %(name)s explicit dimension domain relationships must be to members."),
                                          xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName)
            if cubeDimObj.domainName and dimName in (periodCoreDim, languageCoreDim):
                txmyMdl.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s domainName property MUST NOT be used where the dimensionName property has a QName value %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)

            if dimName == periodCoreDim:
                for iPerConst, perConstObj in enumerate(cubeDimObj.periodConstraints):
                    if perConstObj.periodType not in ("instant", "duration"):
                        txmyMdl.error("oimte:invalidPeriodRepresentation",
                                  _("Cube %(name)s period constraint periodType property MUST be \"instant\" or \"duration\"."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    if perConstObj.timeSpan:
                        if perConstObj.endDate and perConstObj.startDate:
                            txmyMdl.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s period constraint timeSpan property MUST NOT be used with both the endDate and startDate properties."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        validateValue(txmyMdl, cubeObj, perConstObj.timeSpan, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/timeSpan")
                    if perConstObj.periodFormat:
                        if perConstObj.timeSpan or perConstObj.endDate or perConstObj.startDate:
                            txmyMdl.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s period constraint periodFormat property MUST NOT be used with the timeSpan, endDate or startDate properties."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        if not any(perFormMatch.match(perConstObj.periodFormat) for _perType, perFormMatch in periodForms):
                            txmyMdl.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s periodConstraint[%(perConstNbr)s] periodFormat property, %(periodFormat)s, MUST be a valid period format per xbrl-csv specification."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name, perConstNbr=iPerConst, periodFormat=perConstObj.periodFormat)
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
                                if not cncpt or not isinstance(txmyMdl.namedObjects.get(cncpt.dataType), XbrlDataType) or txmyMdl.namedObjects[cncpt.dataType].baseType != qnXsDateTime:
                                    txmyMdl.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a date."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                            if dtResObj.context:
                                cncpt = txmyMdl.namedObjects.get(dtResObj.context)
                                if not cncpt or not isinstance(cncpt, XbrlConcept) or (dtResObj.context.atSuffix not in ("start","end")):
                                    txmyMdl.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a concept and any suffix MUST be start or end."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                            if dtResObj.timeShift:
                                if dtResObj.value or (dtResObj.conceptName and dtResObj.context):
                                    txmyMdl.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s timeShift MUST be used with only one of the properties name, or context."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                                validateValue(txmyMdl, cubeObj, dtResObj.timeShift, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/timeShift")
                            if dtResObj.value:
                                validateValue(txmyMdl, cubeObj, dtResObj.value, "XBRLI_DATEUNION", f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/value")
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
                      _("The dataType object %(name)s MUST define a valid baseType which must be a dataType object in the txmyMdl"),
                      xbrlObject=dtObj, name=dt.name)
        for unitTpObj in dtObj.unitTypes:
            assertObjectType(utObj, XbrlUnitType)
            for utProp in ("dataTypeNumerator", "dataTypeDenominator", "dataTypeMutiplier"):
                utPropQn = getattr(utObj, utProp)
                if utPropQn and not isinstance(txmyMdl.namedObjects.get(utPropQn), XbrlDataType):
                    txmyMdl.error("oimte:invalidPropertyValue",
                              _("The dataType object unitType %(name)s MUST define a valid dataType object in the txmyMdl"),
                              xbrlObject=dtObj, name=dt.name)

    # Dimension Objects
    for dimObj in txmy.dimensions:
        assertObjectType(dimObj, XbrlDimension)
        for cubeTypeQn in dimObj.cubeTypes:
            if not isinstance(txmyMdl.namedObjects.get(cubeTypeQn), XbrlCubeType):
                txmyMdl.error("oimte:invalidPropertyValue",
                          _("The dimension cubeType QName %(name)s MUST be a valid cubeType object in the txmyMdl"),
                          xbrlObject=dimObj, name=cubeTypeQn)
        if dimObj.domainDataType and not isinstance(txmyMdl.namedObjects.get(dimObj.domainDataType), XbrlDataType):
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The dimension domain dataType object QName %(name)s MUST be a valid dataType object in the txmyMdl"),
                      xbrlObject=dimObj, name=dimObj.domainDataType)
        if dimObj.domainRoot and not isinstance(txmyMdl.namedObjects.get(dimObj.domainRoot), XbrlDomainRoot):
            txmyMdl.error("oimte:invalidPropertyValue",
                      _("The dimension domainRoot object QName %(name)s MUST be a valid domainRoot object in the txmyMdl"),
                      xbrlObject=dimObj, name=dimObj.domainRoot)

    # Domain Objects
    for domObj in txmy.domains:
        assertObjectType(domObj, XbrlDomain)
        if domObj.extendTargetName:
            if domObj.name:
                txmyMdl.error("oimte:invalidObjectProperty",
                          _("The domain %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=domObj, name=domObj.name)
            elif not isinstance(txmyMdl.namedObjects.get(domObj.extendTargetName), XbrlDomain):
                txmyMdl.error("oimte:missingTargetObject",
                          _("The domain %(name)s MUST be a valid domain object in the txmyMdl"),
                          xbrlObject=domObj, name=domObj.name or domObj.extendTargetName)
        elif not domObj.name:
            txmyMdl.error("oimte:missingRequiredProperty",
                      _("The domain object MUST have either a name or an extendTargetName, not neither."),
                      xbrlObject=domObj)

        if not domObj.extendTargetName and not isinstance(txmyMdl.namedObjects.get(domObj.root), XbrlDomainRoot):
            txmyMdl.error("oimte:missingTargetObject",
                      _("The domain %(name)s root %(qname)s MUST be a valid domainRoot object in the txmyMdl"),
                      xbrlObject=domObj, name=domObj.name, qname=domObj.root)
        for relObj in domObj.relationships:
            assertObjectType(relObj, XbrlRelationship)
            if isinstance(txmyMdl.namedObjects.get(relObj.target), (XbrlDomain, XbrlDomainRoot)):
                txmyMdl.error("oimte:invalidFactMember",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domain or domainRoot object."),
                          xbrlObject=domObj, name=domObj.name, qname=relObj.target)
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
                      _("The groupContent object groupName QName %(name)s MUST be a valid group object in the txmyMdl"),
                      xbrlObject=grpCntObj, name=grpQn)
        for relName in grpCntObj.relatedNames:
            if relName not in txmyMdl.namedObjects or not isinstance(txmyMdl.namedObjects.get(relName), (XbrlNetwork, XbrlCube, XbrlTableTemplate)):
                txmyMdl.error("oimte:invalidGroupObject",
                          _("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects or table template objects."),
                          xbrlObject=grpCntObj, name=grpQn, relName=relName)

    # Label Objects
    for labelObj in txmy.labels:
        assertObjectType(labelObj, XbrlLabel)
        relatedName = labelObj.relatedName
        lang = labelObj.language
        if not languagePattern.match(lang):
            txmyMdl.error("oime:invalidLanguage",
                      _("Label %(relatedName)s has invalid language %(lang)s"),
                      xbrlObject=labelObj, relatedName=relatedName, lang=lang)
        if relatedName not in txmyMdl.namedObjects:
            txmyMdl.error("oime:unresolvedRelatedName",
                      _("Label has invalid related object %(relatedName)s"),
                      xbrlObject=labelObj, relatedName=relatedName)
        validateProperties(txmyMdl, oimFile, txmy, labelObj)

    # Network Objects
    for ntwkObj in txmy.networks:
        assertObjectType(ntwkObj, XbrlNetwork)
        if ntwkObj.extendTargetName:
            if ntwkObj.name:
                txmyMdl.error("oimte:invalidObjectProperty",
                          _("The network %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=ntwkObj, name=ntwkObj.name)
            elif not isinstance(txmyMdl.namedObjects.get(ntwkObj.extendTargetName), XbrlNetwork):
                txmyMdl.error("oimte:missingTargetObject",
                          _("The network extendTargetName %(name)s MUST be a valid network object in the txmyMdl"),
                          xbrlObject=ntwkObj, name=ntwkObj.name or ntwkObj.extendTargetName)
        elif not ntwkObj.name:
            txmyMdl.error("oimte:missingRequiredProperty",
                      _("The network object MUST have either a name or an extendTargetName, not neither."),
                      xbrlObject=ntwkObj)

        for rootQn in ntwkObj.roots:
            if rootQn not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingTargetObject",
                          _("The network %(name)s root %(qname)s MUST be a valid object in the txmyMdl"),
                          xbrlObject=ntwkObj, name=ntwkObj.name, qname=rootQn)
        for i, relObj in enumerate(domObj.relationships):
            assertObjectType(relObj, XbrlRelationship)
            if  relObj.source not in txmyMdl.namedObjects or relObj.target not in txmyMdl.namedObjects:
                txmyMdl.error("oimte:missingTargetObject",
                          _("The network %(name)s relationship[%(nbr)s] source, %(source)s, and target, %(target)s, MUST be objects in the txmyMdl."),
                          xbrlObject=domObj, name=ntwkObj.name, nbr=i, source=relObj.source, target=relObj.target)
            validateProperties(txmyMdl, oimFile, txmy, relObj)
        validateProperties(txmyMdl, oimFile, txmy, ntwkObj)

    # PropertyType Objects
    for propTpObj in txmy.propertyTypes:
        assertObjectType(propTpObj, XbrlPropertyType)
        if not isinstance(txmyMdl.namedObjects.get(propTpObj.dataType), XbrlDataType):
            txmyMdl.error("oimte:invalidDataTypeObject",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the txmyMdl"),
                      xbrlObject=ntwkObj, name=propTpObj.name, qname=propTpObj.dataType)
        elif propTpObj.enumerationDomain and txmyMdl.namedObjects[propTpObj.dataType.baseType] != qnXsQName:
            txmyMdl.error("oimte:invalidDataTypeObject",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the txmyMdl"),
                      xbrlObject=ntwkObj, name=propTpObj.name, qname=propTpObj.dataType)
        for allowedObjQn in propTpObj.allowedObjects:
            if allowedObjQn not in objectsWithProperties:
                txmyMdl.error("oime:invalidAllowedObject",
                          _("The property %(name)s has an invalid allowed object %(allowedObj)s"),
                          file=oimFile, name=propTpObj.name, allowedObj=allowedObjQn)

    # RelationshipType Objects
    for relTpObj in txmy.relationshipTypes:
        assertObjectType(relTpObj, XbrlRelationshipType)

    # Reference Objects
    refsWithInvalidLang = defaultdict(list)
    refsWithInvalidRelName = []
    refInvalidNames = []
    for refObj in txmy.references:
        assertObjectType(refObj, XbrlReference)
        name = refObj.name
        lang = refObj.language
        if lang is not None and not languagePattern.match(lang):
            refsWithInvalidLang[lang].append(refObj)
        for relName in refObj.relatedNames:
            if relName not in txmyMdl.namedObjects:
                refsWithInvalidRelName.append(refObj)
                refInvalidNames.append(relName)
        validateProperties(txmyMdl, oimFile, txmy, refObj)
    if refsWithInvalidRelName:
        txmyMdl.warning("oime:unresolvedRelatedNameWarning",
                  _("References have invalid related object names %(relNames)s"),
                  xbrlObject=refsWithInvalidRelName, name=name, relNames=", ".join(str(qn) for qn in refInvalidNames))
    for lang, refObjs in refsWithInvalidLang:
        txmyMdl.warning("oime:invalidLanguageWarning",
                  _("Reference object(s) have invalid language %(lang)s"),
                  xbrlObject=refObjs, lang=lang)
    del refsWithInvalidLang, refsWithInvalidRelName, refInvalidNames # dereference

    # Unit Objects
    for unitObj in txmy.units:
        assertObjectType(unitObj, XbrlUnit)
        usedDataTypes = set()

        for dtProp in ("dataType", "dataTypeNumerator", "aTypeDenominator"):
            dtQn = getattr(unitObj, dtProp, None)
            if dtQn:
                if not isinstance(txmyMdl.namedObjects.get(dtQn), XbrlDataType):
                    txmyMdl.error("oimte:invalidUnitDataType",
                              _("The unit %(name)s %(property)s %(qname)s MUST be a dataType object."),
                              xbrlObject=unitObj, name=unitObj.name, property=dtProp, qname=dtQn)
                else:
                    if dtQn in usedDataTypes:
                        txmyMdl.error("oimte:invalidUnitDataType",
                                  _("The unit %(name)s %(qname)s MUST only be used once in the unit object."),
                                  xbrlObject=unitObj, name=unitObj.name, qname=dtQn)
                    usedDataTypes.add(dtQn)
        del usedDataTypes
