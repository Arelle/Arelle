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
from .XbrlImportedTaxonomy import XbrlImportedTaxonomy
from .XbrlLabel import XbrlLabel
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlPropertyType
from .XbrlReference import XbrlReference
from .XbrlTableTemplate import XbrlTableTemplate
from .XbrlTaxonomy import XbrlTaxonomy, xbrlObjectTypes, xbrlObjectQNames
from .XbrlUnit import XbrlUnit
from .XbrlConst import qnXsQName, qnXsDateTime, qnXsDuration, objectsWithProperties

perCnstrtFmtStartEndPattern = re.compile(r".*@(start|end)")

def validateDTS(dts):

    for txmy in dts.taxonomies.values():
        validateTaxonomy(dts, txmy)

def objType(obj):
    clsName = type(obj).__name__
    if clsName.startswith("Xbrl"):
        return clsName[4:]
    return clsName

def validateValue(dts, obj, value, dataTypeQn, pathElt):
    if isinstance(dataTypeQn, QName):
        dataTypeObj = dts.namedObjects.get(dataTypeQn)
        if not isinstance(dataTypeObj, XbrlDataType): # validity checked in owner object validations
            return
        dataTypeLn = dataTypeObj.xsBaseType(dts)
        facets = dataTypeObj.xsFacets()
    else: # string data type
        dataTypeLn = dataTypeQn
        facets = EMPTY_DICT
    prototypeElt = attrdict(elementQname=dataTypeQn,
                            entryLoadingUrl=obj.entryLoadingUrl + pathElt)
    validateXmlValue(dts, prototypeElt, None, dataTypeLn, value, False, False, facets)



def validateProperties(dts, oimFile, txmy, obj):
    for i, propObj in enumerate(obj.properties):
        propTypeQn = propObj.property
        propTypeObj = dts.namedObjects.get(propTypeQn)
        if not isinstance(propTypeObj, XbrlPropertyType):
            dts.error("oime:invalidPropertyTypeObject",
                      _("%(parentObjName)s %(parentName)s property %(name)s has undefined dataType %(dataType)s"),
                      file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                      name=propTypeQn, dataType=propTypeQn)
        else: # have property type object
            if propTypeObj.allowedObjects:
                if xbrlObjectQNames.get(type(obj)) not in propTypeObj.allowedObjects:
                    dts.error("oime:disallowedObjectProperty",
                              _("%(parentObjName)s %(parentName)s property %(name)s not an allowed property type for the object."),
                              file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                              name=propTypeQn)
            validateValue(dts, obj, propObj.value, propTypeObj.dataType, f"/properties[{i}]")

def validateTaxonomy(dts, txmy):
    oimFile = str(txmy.name)

    def assertObjectType(obj, objType):
        if not isinstance(obj, objType):
            dts.error("oimte:invalidObjectType",
                      _("This %(thisType)s object was included where an %(expectedType)s object was expected."),
                      xbrlObject=obj, thisType=obj.__class__.__name__, expectedType=objType.__name__)

    # Taxonomy object
    assertObjectType(txmy, XbrlTaxonomy)

    for impTxmyObj in txmy.importedTaxonomies:
        assertObjectType(impTxmyObj, XbrlImportedTaxonomy)
        for qnObjType in impTxmyObj.includeObjectTypes:
            if qnObjType in xbrlObjectTypes:
                if xbrlObjectTypes[qnObjType] == XbrlLabel:
                    dts.error("oimte:invalidObjectType",
                              _("The includeObjectTypes property MUST not include the label object."),
                              xbrlObject=qnObjType)
            else:
                dts.error("oimte:invalidObjectType",
                          _("The includeObjectTypes property MUST specify valid OIM object types, %(qname)s is not valid."),
                          xbrlObject=qnObjType, qname=qnObjType)

    # Concept Objects
    for cncpt in txmy.concepts:
        assertObjectType(cncpt, XbrlConcept)
        perType = cncpt.periodType
        if perType not in ("instant", "duration"):
            dts.error("oime:invalidPropertyValue",
                      _("Concept %(name)s has invalid period type %(perType)s"),
                      xbrlObject=cncpt, name=cncpt.name, perType=perType)
        dataTypeQn = cncpt.dataType
        if dataTypeQn not in dts.namedObjects or not isinstance(dts.namedObjects[dataTypeQn], XbrlDataType):
            dts.error("oime:invalidDataTypeObject",
                      _("Concept %(name)s has invalid dataType %(dataType)s"),
                      xbrlObject=cncpt, name=cncpt.name, dataType=dataTypeQn)
        enumDomQn = cncpt.enumerationDomain
        if enumDomQn and (enumDomQn not in dts.namedObjects or not isinstance(dts.namedObjects[enumDomQn], XbrlDomain)):
            dts.error("oime:invalidEnumerationDomainObject",
                      _("Concept %(name)s has invalid enumeration domain reference %(enumDomain)s"),
                      xbrlObject=cncpt, name=cncpt.name, enumDomain=enumDomQn)
        validateProperties(dts, oimFile, txmy, cncpt)


    # Cube Objects
    for cubeObj in txmy.cubes:
        assertObjectType(cubeObj, XbrlCube)
        name = cubeObj.name
        if cubeObj.cubeType and cubeObj.cubeType not in baseCubeTypes:
            if not isinstance(dts.namedObjects.get(cubeObj.cubeType), XbrlCubeType):
                dts.error("oimte:invalidPropertyValue",
                          _("The cube %(name)s  cubeType %(qname)s must be a valid cube type."),
                          xbrlObject=cubeObj, name=name, qname=cubeObj.cubeType)
        dimQnCounts = {}
        for allowedCubeDimObj in cubeObj.cubeDimensions:
            dimQn = allowedCubeDimObj.dimensionName
            if dimQn not in coreDimensions and not isinstance(dts.namedObjects.get(dimQn), XbrlDimension):
                dts.error("oimte:invalidTaxonomyDefinedDimension",
                          _("The allowedCubeDimensions property on cube %(name)s MUST resolve to a dimension object: %(dimension)s"),
                          xbrlObject=cubeObj, name=name, dimension=dimQn)
            dimQnCounts[dimQn] = dimQnCounts.get(dimQn, 0) + 1
        if any(c > 1 for c in dimQnCounts.values()):
            dts.error("oimte:duplicateObjects",
                      _("The cubeDimensions property on cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      xbrlObject=cubeObj, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items if ct > 1))
        for ntwrkQn in cubeObj.cubeNetworks:
            if not isinstance(dts.namedObjects.get(ntwrkQn), XbrlNetwork):
                dts.error("oimte:invalidCubeNetwork",
                          _("The cubeNetworks property on cube %(name)s MUST resolve %(qname)s to a network object."),
                          xbrlObject=cubeObj, name=name, qname=ntwrkQn)
        for exclCubeQn in cubeObj.excludeCubes:
            if exclCubeQn == cubeObj.name:
                dts.error("oimte:invalidPropertyValue",
                          _("The cube %(name)s must not be defined in the excludeCubes property of itself."),
                          xbrlObject=cubeObj, name=name)
            if not isinstance(dts.namedObjects.get(exclCubeQn), XbrlCube):
                dts.error("oimte:missingQNameReference",
                          _("The excludeCubes property on cube %(name)s MUST resolve %(qname)s to a cube object."),
                          xbrlObject=cubeObj, name=name, qname=exclCubeQn)
        validateProperties(dts, oimFile, txmy, cubeObj)
        unitDataTypeQNs = set()
        cncptDataTypeQNs = set()
        for iCubeDim, cubeDimObj in enumerate(cubeObj.cubeDimensions):
            assertObjectType(cubeDimObj, XbrlCubeDimension)
            dimName = cubeDimObj.dimensionName
            if cubeDimObj.domainSort not in (None, "asc", "desc"):
                dts.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s domainSort property MUST be asc or desc, not %(domainSort)s."),
                          xbrlObject=cubeObj, name=name, domainSort=cubeDimObj.domainSort)
            if cubeDimObj.periodConstraints and dimName != periodCoreDim:
                dts.error("oimte:invalidDimensionConstraint",
                          _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)
            if dimName == conceptCoreDim and isinstance(dts.namedObjects.get(cubeDimObj.domainName), XbrlDomain):
                for relObj in dts.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(dts.namedObjects.get(relObj.source,None), (XbrlConcept, XbrlAbstract)) and relObj.source != conceptDomainRoot:
                        dts.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s conceptConstraints domain relationships must be from concepts, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if isinstance(dts.namedObjects.get(relObj.target,None), XbrlConcept):
                        cncptDataTypeQNs.add(dts.namedObjects[relObj.target].dataType)
                    elif not isinstance(dts.namedObjects.get(relObj.target,None), XbrlAbstract):
                        dts.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s conceptConstraints domain relationships must be to concepts, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
            if dimName == entityCoreDim and isinstance(dts.namedObjects.get(cubeDimObj.domainName), XbrlDomain):
                for relObj in dts.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(dts.namedObjects.get(relObj.source,None), XbrlEntity) and relObj.source != entityDomainRoot:
                        dts.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s entityConstraints domain relationships must be from entities, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if not isinstance(dts.namedObjects.get(relObj.target,None), XbrlEntity):
                        dts.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s entityConstraints domain relationships must be to entities, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
            if dimName == unitCoreDim and isinstance(dts.namedObjects.get(cubeDimObj.domainName), XbrlDomain):
                for relObj in dts.namedObjects[cubeDimObj.domainName].relationships:
                    if not isinstance(dts.namedObjects.get(relObj.source,None), XbrlUnit) and relObj.source != unitDomainRoot:
                        dts.error("oimte:invalidRelationshipSource",
                                  _("Cube %(name)s unitConstraints domain relationships must be from units, source: %(source)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, source=relObj.source)
                    if not isinstance(dts.namedObjects.get(relObj.target,None), XbrlUnit):
                        dts.error("oimte:invalidRelationshipTarget",
                                  _("Cube %(name)s unitConstraints domain relationships must be to units, target: %(target)s."),
                                  xbrlObject=(cubeObj,cubeDimObj,relObj), name=name, qname=dimName, target=relObj.target)
            if dimName not in coreDimensions and isinstance(dts.namedObjects.get(dimName), XbrlDimension):
                dimObj = dts.namedObjects[dimName]
                if dimObj.domainDataType: # typed
                    if dimObj.domainRoot:
                        dts.error("oimte:invalidQNameReference",
                                  _("Cube %(name)s typed dimension %(qname)s must not specify a domain root."),
                                  xbrlObject=(cubeObj,cubeDimObj,dimObj), name=name, qname=dimName)
                else: # explicit dim
                    domObj = dts.namedObjects.get(cubeDimObj.domainName)
                    if domObj:
                        for relObj in domObj.relationships:
                            if not isinstance(dts.namedObjects.get(getattr(relObj, "target", None),None), XbrlMember):
                                dts.error("oimte:invalidRelationshipTarget",
                                          _("Cube %(name)s explicit dimension domain relationships must be to members."),
                                          xbrlObject=(cubeObj,dimObj,relObj), name=name, qname=dimName)
            if cubeDimObj.domainName and dimName in (periodCoreDim, languageCoreDim):
                dts.error("oimte:invalidCubeDimensionProperty",
                          _("Cube %(name)s domainName property MUST NOT be used where the dimensionName property has a QName value %(qname)s."),
                          xbrlObject=cubeObj, name=name, qname=dimName)

            if dimName == periodCoreDim:
                for iPerConst, perConstObj in enumerate(cubeDimObj.periodConstraints):
                    if perConstObj.periodType not in ("instant", "duration"):
                        dts.error("oimte:invalidPeriodRepresentation",
                                  _("Cube %(name)s period constraint periodType property MUST be \"instant\" or \"duration\"."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    if perConstObj.timeSpan:
                        if perConstObj.endDate and perConstObj.startDate:
                            dts.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s period constraint timeSpan property MUST NOT be used with both the endDate and startDate properties."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        validateValue(dts, cubeObj, perConstObj.timeSpan, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/timeSpan")
                    if perConstObj.periodFormat:
                        if perConstObj.timeSpan or perConstObj.endDate or perConstObj.startDate:
                            dts.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s period constraint periodFormat property MUST NOT be used with the timeSpan, endDate or startDate properties."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name)
                        if not any(perFormMatch.match(perConstObj.periodFormat) for _perType, perFormMatch in periodForms):
                            dts.error("oimte:invalidPeriodRepresentation",
                                      _("Cube %(name)s periodConstraint[%(perConstNbr)s] periodFormat property, %(periodFormat)s, MUST be a valid period format per xbrl-csv specification."),
                                      xbrlObject=(cubeObj,cubeDimObj), name=name, perConstNbr=iPerConst, periodFormat=perConstObj.periodFormat)
                    if perConstObj.periodType != "instant" and perConstObj.periodFormat and perCnstrtFmtStartEndPattern.match(perConstObj.periodFormat):
                        dts.error("oimte:invalidPeriodRepresentation",
                                  _("Cube %(name)s period constraint periodFormat the suffix of @start or @end MUST only be used with periodType of instant."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    if perConstObj.periodType == "instant" and (perConstObj.timeSpan or perConstObj.startDate):
                        dts.error("oimte:invalidPeriodRepresentation",
                              _("Cube %(name)s period constraint periodType instant MUST NOT define timeSpan or startDate."),
                                  xbrlObject=(cubeObj,cubeDimObj), name=name)
                    for dtResProp in ("monthDay", "endDate", "startDate", "onOrAfter", "onOrBefore"):
                        dtResObj = getattr(perConstObj, dtResProp, None)
                        if dtResObj is not None:
                            if dtResObj.conceptName:
                                cncpt = dts.namedObjects.get(dtResObj.conceptName)
                                if not cncpt or not isinstance(dts.namedObjects.get(cncpt.dataType), XbrlDataType) or dts.namedObjects[cncpt.dataType].baseType != qnXsDateTime:
                                    dts.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a date."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.conceptName)
                            if dtResObj.context:
                                cncpt = dts.namedObjects.get(dtResObj.context)
                                if not cncpt or not isinstance(cncpt, XbrlConcept) or (dtResObj.context.atSuffix not in ("start","end")):
                                    dts.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s base type MUST be a concept and any suffix MUST be start or end."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                            if dtResObj.timeShift:
                                if dtResObj.value or (dtResObj.conceptName and dtResObj.context):
                                    dts.error("oimte:invalidPeriodRepresentation",
                                              _("Cube %(name)s period constraint concept %(qname)s timeShift MUST be used with only one of the properties name, or context."),
                                              xbrlObject=(cubeObj,cubeDimObj), name=name, qname=dtResObj.context)
                                validateValue(dts, cubeObj, dtResObj.timeShift, "duration" ,f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/timeShift")
                            if dtResObj.value:
                                validateValue(dts, cubeObj, dtResObj.value, "XBRLI_DATEUNION", f"/cubeDimensions[{iCubeDim}]/periodConstraints[{iPerConst}]/{dtResProp}/value")
            else:
                if cubeDimObj.periodConstraints:
                    dts.error("oimte:invalidDimensionConstraint",
                              _("Cube %(name)s periodConstraints property MUST only be used where the dimensionName property has a QName value of xbrl:period, not %(qname)s."),
                              xbrlObject=cubeObj, name=name, qname=dimName)
        for unitDataTypeQN in unitDataTypeQNs:
            if unitDataTypeQN not in cncptDataTypeQNs:
                dts.error("oimte:invalidDataTypeObject",
                          _("Cube %(name)s unitConstraints data Type %(dataType)s MUST have at least one associated concept object on the concept core dimension with the same datatype as the unit object."),
                          xbrlObject=(cubeObj,cubeDimObj), name=name, dataType=unitDataTypeQN)

    # DataType Objects
    for dtObj in txmy.dataTypes:
        assertObjectType(dtObj, XbrlDataType)
        btQn = dtObj.baseType
        if btQn and btQn.namespaceURI != "http://www.w3.org/2001/XMLSchema" and not isinstance(dts.namedObjects.get(btQn), XbrlDataType):
            dts.error("oimte:invalidPropertyValue",
                      _("The dataType object %(name)s MUST define a valid baseType which must be a dataType object in the dts"),
                      xbrlObject=dtObj, name=dt.name)
        for unitTpObj in dtObj.unitTypes:
            assertObjectType(utObj, XbrlUnitType)
            for utProp in ("dataTypeNumerator", "dataTypeDenominator", "dataTypeMutiplier"):
                utPropQn = getattr(utObj, utProp)
                if utPropQn and not isinstance(dts.namedObjects.get(utPropQn), XbrlDataType):
                    dts.error("oimte:invalidPropertyValue",
                              _("The dataType object unitType %(name)s MUST define a valid dataType object in the dts"),
                              xbrlObject=dtObj, name=dt.name)

    # Dimension Objects
    for dimObj in txmy.dimensions:
        assertObjectType(dimObj, XbrlDimension)
        for cubeTypeQn in dimObj.cubeTypes:
            if not isinstance(dts.namedObjects.get(cubeTypeQn), XbrlCubeType):
                dts.error("oimte:invalidPropertyValue",
                          _("The dimension cubeType QName %(name)s MUST be a valid cubeType object in the dts"),
                          xbrlObject=dimObj, name=cubeTypeQn)
        if dimObj.domainDataType and not isinstance(dts.namedObjects.get(dimObj.domainDataType), XbrlDataType):
            dts.error("oimte:invalidPropertyValue",
                      _("The dimension domain dataType object QName %(name)s MUST be a valid dataType object in the dts"),
                      xbrlObject=dimObj, name=dimObj.domainDataType)
        if dimObj.domainRoot and not isinstance(dts.namedObjects.get(dimObj.domainRoot), XbrlDomainRoot):
            dts.error("oimte:invalidPropertyValue",
                      _("The dimension domainRoot object QName %(name)s MUST be a valid domainRoot object in the dts"),
                      xbrlObject=dimObj, name=dimObj.domainRoot)

    # Domain Objects
    for domObj in txmy.domains:
        assertObjectType(domObj, XbrlDomain)
        if domObj.extendTargetName:
            if domObj.name:
                dts.error("oimte:invalidObjectProperty",
                          _("The domain %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=domObj, name=domObj.name)
            elif not isinstance(dts.namedObjects.get(domObj.extendTargetName), XbrlDomain):
                dts.error("oimte:missingTargetObject",
                          _("The domain %(name)s MUST be a valid domain object in the dts"),
                          xbrlObject=domObj, name=domObj.name or domObj.extendTargetName)
        elif not domObj.name:
            dts.error("oimte:missingRequiredProperty",
                      _("The domain object MUST have either a name or an extendTargetName, not neither."),
                      xbrlObject=domObj)

        if not domObj.extendTargetName and not isinstance(dts.namedObjects.get(domObj.root), XbrlDomainRoot):
            dts.error("oimte:missingTargetObject",
                      _("The domain %(name)s root %(qname)s MUST be a valid domainRoot object in the dts"),
                      xbrlObject=domObj, name=domObj.name, qname=domObj.root)
        for relObj in domObj.relationships:
            assertObjectType(relObj, XbrlRelationship)
            if isinstance(dts.namedObjects.get(relObj.target), (XbrlDomain, XbrlDomainRoot)):
                dts.error("oimte:invalidFactMember",
                          _("The domain %(name)s relationship target %(qname)s MUST NOT be a domain or domainRoot object."),
                          xbrlObject=domObj, name=domObj.name, qname=relObj.target)
        validateProperties(dts, oimFile, txmy, domObj)


    # DomainRoot Objects
    for domRtObj in txmy.domainRoots:
        assertObjectType(domRtObj, XbrlDomainRoot)
        validateProperties(dts, oimFile, txmy, domRtObj)

    # Entity Objects
    for entityObj in txmy.entities:
        assertObjectType(entityObj, XbrlEntity)
        validateProperties(dts, oimFile, txmy, entityObj)

    # GroupContent Objects
    for grpCntObj in txmy.groupContents:
        assertObjectType(grpCntObj, XbrlGroupContent)
        grpQn = grpCntObj.groupName
        if grpQn not in dts.namedObjects or type(dts.namedObjects[grpQn]) != XbrlGroup:
            dts.error("oimte:invalidGroupObject",
                      _("The groupContent object groupName QName %(name)s MUST be a valid group object in the dts"),
                      xbrlObject=grpCntObj, name=grpQn)
        for relName in grpCntObj.relatedNames:
            if relName not in dts.namedObjects or not isinstance(dts.namedObjects.get(relName), (XbrlNetwork, XbrlCube, XbrlTableTemplate)):
                dts.error("oimte:invalidGroupObject",
                          _("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects or table template objects."),
                          xbrlObject=grpCntObj, name=grpQn, relName=relName)

    # Label Objects
    for labelObj in txmy.labels:
        assertObjectType(labelObj, XbrlLabel)
        relatedName = labelObj.relatedName
        lang = labelObj.language
        if not languagePattern.match(lang):
            dts.error("oime:invalidLanguage",
                      _("Label %(relatedName)s has invalid language %(lang)s"),
                      xbrlObject=labelObj, relatedName=relatedName, lang=lang)
        if relatedName not in dts.namedObjects:
            dts.error("oime:unresolvedRelatedName",
                      _("Label has invalid related object %(relatedName)s"),
                      xbrlObject=labelObj, relatedName=relatedName)
        validateProperties(dts, oimFile, txmy, labelObj)

    # Network Objects
    for ntwkObj in txmy.networks:
        assertObjectType(ntwkObj, XbrlNetwork)
        if ntwkObj.extendTargetName:
            if ntwkObj.name:
                dts.error("oimte:invalidObjectProperty",
                          _("The network %(name)s MUST have only a name or an extendTargetName, not both."),
                          xbrlObject=ntwkObj, name=ntwkObj.name)
            elif not isinstance(dts.namedObjects.get(ntwkObj.extendTargetName), XbrlNetwork):
                dts.error("oimte:missingTargetObject",
                          _("The network extendTargetName %(name)s MUST be a valid network object in the dts"),
                          xbrlObject=ntwkObj, name=ntwkObj.name or ntwkObj.extendTargetName)
        elif not ntwkObj.name:
            dts.error("oimte:missingRequiredProperty",
                      _("The network object MUST have either a name or an extendTargetName, not neither."),
                      xbrlObject=ntwkObj)

        for rootQn in ntwkObj.roots:
            if rootQn not in dts.namedObjects:
                dts.error("oimte:missingTargetObject",
                          _("The network %(name)s root %(qname)s MUST be a valid object in the dts"),
                          xbrlObject=ntwkObj, name=ntwkObj.name, qname=rootQn)
        for i, relObj in enumerate(domObj.relationships):
            assertObjectType(relObj, XbrlRelationship)
            if  relObj.source not in dts.namedObjects or relObj.target not in dts.namedObjects:
                dts.error("oimte:missingTargetObject",
                          _("The network %(name)s relationship[%(nbr)s] source, %(source)s, and target, %(target)s, MUST be objects in the DTS."),
                          xbrlObject=domObj, name=ntwkObj.name, nbr=i, source=relObj.source, target=relObj.target)
            validateProperties(dts, oimFile, txmy, relObj)
        validateProperties(dts, oimFile, txmy, ntwkObj)

    # PropertyType Objects
    for propTpObj in txmy.propertyTypes:
        assertObjectType(propTpObj, XbrlPropertyType)
        if not isinstance(dts.namedObjects.get(propTpObj.dataType), XbrlDataType):
            dts.error("oimte:invalidDataTypeObject",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the dts"),
                      xbrlObject=ntwkObj, name=propTpObj.name, qname=propTpObj.dataType)
        elif propTpObj.enumerationDomain and dts.namedObjects[propTpObj.dataType.baseType] != qnXsQName:
            dts.error("oimte:invalidDataTypeObject",
                      _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the dts"),
                      xbrlObject=ntwkObj, name=propTpObj.name, qname=propTpObj.dataType)
        for allowedObjQn in propTpObj.allowedObjects:
            if allowedObjQn not in objectsWithProperties:
                dts.error("oime:invalidAllowedObject",
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
            if relName not in dts.namedObjects:
                refsWithInvalidRelName.append(refObj)
                refInvalidNames.append(relName)
        validateProperties(dts, oimFile, txmy, refObj)
    if refsWithInvalidRelName:
        dts.warning("oime:unresolvedRelatedNameWarning",
                  _("References have invalid related object names %(relNames)s"),
                  xbrlObject=refsWithInvalidRelName, name=name, relNames=", ".join(str(qn) for qn in refInvalidNames))
    for lang, refObjs in refsWithInvalidLang:
        dts.warning("oime:invalidLanguageWarning",
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
                if not isinstance(dts.namedObjects.get(dtQn), XbrlDataType):
                    dts.error("oimte:invalidUnitDataType",
                              _("The unit %(name)s %(property)s %(qname)s MUST be a dataType object."),
                              xbrlObject=unitObj, name=unitObj.name, property=dtProp, qname=dtQn)
                else:
                    if dtQn in usedDataTypes:
                        dts.error("oimte:invalidUnitDataType",
                                  _("The unit %(name)s %(qname)s MUST only be used once in the unit object."),
                                  xbrlObject=unitObj, name=unitObj.name, qname=dtQn)
                    usedDataTypes.add(dtQn)
        del usedDataTypes
