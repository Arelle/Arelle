'''
See COPYRIGHT.md for copyright information.
'''

from arelle.XmlValidate import languagePattern
from arelle.oim.Load import EMPTY_DICT
from .XbrlConcept import XbrlDataType
from .XbrlCube import XbrlCube
from .XbrlDimension import XbrlDomain
from .XbrlGroup import XbrlGroup
from .XbrlLabel import XbrlLabel
from .XbrlNetwork import XbrlNetwork
from .XbrlReference import XbrlReference
from .XbrlTableTemplate import XbrlTableTemplate
from .XbrlConst import qnXbrlLabel

def validateDTS(dts):

    for txmy in dts.taxonomies.values():
        validateTaxonomy(dts, txmy)

def objType(obj):
    clsName = type(obj).__name__
    if clsName.startswith("Xbrl"):
        return clsName[4:]
    return clsName

def validateProperties(dts, oimFile, txmy, obj):
    for propObj in getattr(obj, "properties", ()):
        propTypeQn = getattr(propObj, "property", None)
        if propTypeQn not in dts.namedObjects or not isinstance(dts.namedObjects[propTypeQn], XbrlPropertyType):
            dts.error("oime:invalidPropertyTypeObject",
                      _("%(parentObjName)s %(parentName)s property %(name)s has undefined dataType %(dataType)s"),
                      file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                      name=propTypeQn, dataType=propTypeQn)
        for allowedObjQn in getattr(obj, "allowedObjects", ()):
            if allowedObjQn not in objectsWithProperties:
                dts.error("oime:invalidAllowedObject",
                          _("%(parentObjName)s %(parentName)s property %(name)s has invalid allowed object %(allowedObj)s"),
                          file=oimFile, parentObjName=objType(obj), parentName=getattr(obj,"name","(n/a)"),
                          name=obj.name, allowedObj=allowedObjQn)

def validateTaxonomy(dts, txmy):
    oimFile = getattr(txmy, "entryPoint", "")

    # Taxonomy object
    if qnXbrlLabel in getattr(txmy, "includeObjectTypes", ()):
        dts.error("oimte:invalidObjectType",
                  _("The includeObjectTypes property MUST not include the label object."),
                  xbrlObject=txmy)

    # Concept Objects
    for cncpt in getattr(txmy, "concepts", EMPTY_DICT):
        perType = getattr(cncpt, "periodType", None)
        if perType not in ("instant", "duration"):
            dts.error("oime:invalidPropertyValue",
                      _("Concept %(name)s has invalid period type %(perType)s"),
                      xbrlObject=cncpt, name=cncpt.name, perType=perType)
        dataTypeQn = getattr(cncpt, "dataType", "(absent)")
        if dataTypeQn not in dts.namedObjects or not isinstance(dts.namedObjects[dataTypeQn], XbrlDataType):
            dts.error("oime:invalidDataTypeObject",
                      _("Concept %(name)s has invalid dataType %(dataType)s"),
                      xbrlObject=cncpt, name=cncpt.name, dataType=dataTypeQn)
        enumDomQn = getattr(cncpt, "enumerationDomain", None)
        if enumDomQn and (enumDomQn not in dts.namedObjects or not isinstance(dts.namedObjects[enumDomQn], XbrlDomain)):
            dts.error("oime:invalidEnumerationDomainObject",
                      _("Concept %(name)s has invalid enumeration domain reference %(enumDomain)s"),
                      xbrlObject=cncpt, name=cncpt.name, enumDomain=enumDomQn)
        validateProperties(dts, oimFile, txmy, cncpt)

    # Label Objects
    for labelObj in getattr(txmy, "labels", EMPTY_DICT):
        relatedName = getattr(labelObj, "relatedName", "(missing)")
        lang = getattr(labelObj, "language", "(missing)")
        if not languagePattern.match(lang):
            dts.error("oime:invalidLanguage",
                      _("Label %(relatedName)s has invalid language %(lang)s"),
                      xbrlObject=labelObj, relatedName=relatedName, lang=lang)
        relName = getattr(labelObj, "relatedName", "(missing)")
        if relName not in dts.namedObjects:
            dts.error("oime:unresolvedRelatedName",
                      _("Label %(name)s has invalid related object %(relName)s"),
                      xbrlObject=labelObj, name=name, relName=relName)
        validateProperties(dts, oimFile, txmy, labelObj)

    # Reference Objects
    for refObj in getattr(txmy, "references", EMPTY_DICT):
        name = getattr(refObj, "name", getattr(refObj, "extendTargetName", "(missing)"))
        lang = getattr(refObj, "language", "(missing)")
        if not languagePattern.match(lang):
            dts.error("oime:invalidLanguage",
                      _("Reference %(name)s has invalid language %(lang)s"),
                      xbrlObject=refObj, name=name, lang=lang)
        for relName in getattr(refObj, "relatedNames", ()):
            if relName not in dts.namedObjects:
                dts.error("oime:unresolvedRelatedName",
                          _("Reference %(name)s has invalid related object %(relName)s"),
                          xbrlObject=refObj, name=name, relName=relName)
        validateProperties(dts, oimFile, txmy, refObj)

    # Cube Objects
    for cubeObj in getattr(txmy, "cubes", EMPTY_DICT):
        if getattr(cubeObj, "taxonomyDefinedDimension", True) and getattr(cubeObj, "allowedCubeDimensions", ()):
            dts.error("oimte:inconsistentTaxonomyDefinedDimensionProperty",
                      _("The allowedCubeDimensions property on cube %(name)s MUST only be used when the taxonomyDefinedDimension value is true"),
                      xbrlObject=cubeObj, name=name)
        dimQnCounts = {}
        for allowedCubeDimObj in getattr(cubeObj, "allowedCubeDimensions", ()):
            dimQn = getattr(allowedCubeDimObj, "dimensionName", "(absent)")
            if dimQn not in dts.namedObjects or type(dts.namedObjects[dim]) != XbrlDimension:
                dts.error("oimte:invalidTaxonomyDefinedDimension",
                          _("The allowedCubeDimensions property on cube %(name)s MUST resolve to a dimension object: %(dimension)s"),
                          xbrlObject=cubeObj, name=name, dimension=dimQn)
            dimQnCounts[dimQn] = dimQnCounts.get(dimQn, 0) + 1
        if any(c > 1 for c in dimQnCounts.values()):
            dts.error("oimte:duplicateTaxonomyDefinedDimensions",
                      _("The allowedCubeDimensions property on cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      xbrlObject=cubeObj, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items if ct > 1))
        validateProperties(dts, oimFile, txmy, cubeObj)

    # GroupContent Objects
    for grpCntObj in getattr(txmy, "groupContents", EMPTY_DICT):
        grpQn = getattr(grpCntObj, "groupName", "(absent)")
        if grpQn not in dts.namedObjects or type(dts.namedObjects[grpQn]) != XbrlGroup:
            dts.error("oimte:invalidGroupObject",
                      _("The groupContent object groupName QName %(name)s MUST be a valid group object in the dts"),
                      xbrlObject=grpCntObj, name=grpQn)
        for relName in getattr(grpCntObj, "relatedNames", ()):
            if relName not in dts.namedObjects or type(dts.namedObjects[relName]) not in (XbrlNetwork, XbrlCube, XbrlTableTemplate):
                dts.error("oimte:invalidGroupObject",
                          _("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects or table template objects."),
                          xbrlObject=grpCntObj, name=grpCntObj.groupName, relName=relName)
        validateProperties(dts, oimFile, txmy, grpCntObj)
