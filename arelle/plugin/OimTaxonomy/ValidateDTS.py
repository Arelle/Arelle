'''
See COPYRIGHT.md for copyright information.
'''

from arelle.XmlValidate import languagePattern
from .XbrlConcept import XbrlDataType
from .XbrlCube import XbrlCube
from .XbrlGroup import XbrlGroup
from .XbrlLabel import XbrlLabel
from .XbrlNetwork import XbrlNetwork
from .XbrlReference import XbrlReference
from .XbrlTableTemplate import XbrlTableTemplate

def validateDTS(dts):
    
    for txmy in dts.taxonomies.values():
        validateTaxonomy(dts, txmy)
        
def validateTaxonomy(dts, txmy):
    oimFile = txmy.entryPoint
    
    # Concept Objects
    for cncpt in txmy.concepts:
        perType = getattr(cncpt, "periodType", None)
        if perType not in ("instant", "duration"):
            dts.error("oime:invalidPropertyValue",
                      _("Concept %(name)s has invalid period type %(perType)s"),
                      file=oimFile, name=cncpt.name, perType=perType)
        dataTypeQn = getattr(cncpt, "dataType", "(absent)")
        if dataTypeQn not in dts.namedObjects or type(dts.namedObjects[dataTypeQn]) != XbrlDataType:
            dts.error("oime:invalidDataTypeObject",
                      _("Concept %(name)s has invalid dataType %(dataType)s"),
                      file=oimFile, name=cncpt.name, dataType=dataTypeQn)
            

    # Label Objects
    for labelObj in txmy.labels:
        name = getattr(labelObj, "name", "(missing)")
        lang = getattr(labelObj, "language", "(missing)")
        if not languagePattern.match(lang):
            dts.error("oime:invalidLanguage",
                      _("Label %(name)s has invalid language %(lang)s"),
                      file=oimFile, name=name, lang=lang)
        relName = getattr(labelObj, "relatedName", "(missing)")
        if relName not in dts.namedObjects:
            dts.error("oime:unresolvedRelatedName",
                      _("Label %(name)s has invalid related object %(relName)s"),
                      file=oimFile, name=name, relName=relName)
            
    # Reference Objects
    for refObj in txmy.references:
        name = getattr(refObj, "name", "(missing)")
        lang = getattr(refObj, "language", "(missing)")
        if not languagePattern.match(lang):
            dts.error("oime:invalidLanguage",
                      _("Reference %(name)s has invalid language %(lang)s"),
                      file=oimFile, name=name, lang=lang)
        for relName in getattr(refObj, "relatedNames", ()):
            if relName not in dts.namedObjects:
                dts.error("oime:unresolvedRelatedName",
                          _("Reference %(name)s has invalid related object %(relName)s"),
                          file=oimFile, name=name, relName=relName)
                
    # Cube Objects
    for cubeObj in txmy.cubes:
        if getattr(cubeObj, "taxonomyDefinedDimension", True) and getattr(cubeObj, "allowedCubeDimensions", ()):
            dts.error("oimte:inconsistentTaxonomyDefinedDimensionProperty",
                      _("The allowedCubeDimensions property on cube %(name)s MUST only be used when the taxonomyDefinedDimension value is true"),
                      file=oimFile, name=name)
        dimQnCounts = {}
        for allowedCubeDimObj in getattr(cubeObj, "allowedCubeDimensions", ()):
            dimQn = getattr(allowedCubeDimObj, "dimensionName", "(absent)")
            if dimQn not in dts.namedObjects or type(dts.namedObjects[dim]) != XbrlDimension:
                dts.error("oimte:invalidTaxonomyDefinedDimension",
                          _("The allowedCubeDimensions property on cube %(name)s MUST resolve to a dimension object: %(dimension)s"),
                          file=oimFile, name=name, dimension=dimQn)
            dimQnCounts[dimQn] = dimQnCounts.get(dimQn, 0) + 1
        if any(c > 1 for c in dimQnCounts.values()):
            dts.error("oimte:duplicateTaxonomyDefinedDimensions",
                      _("The allowedCubeDimensions property on cube %(name)s duplicate these dimension object(s): %(dimensions)s"),
                      file=oimFile, name=name, dimensions=", ".join(str(qn) for qn, ct in dimQnCounts.items if ct > 1))
            
    # GroupContent Objects
    for grpCntObj in txmy.groupContents:
        grpQn = getattr(grpCntObj, "groupName", "(absent)")
        if grpQn not in dts.namedObjects or type(dts.namedObjects[grpQn]) != XbrlGroup:
            dts.error("oimte:invalidGroupObject",
                      _("The groupContent object groupName QName %(name)s MUST be a valid group object in the dts"),
                      file=oimFile, name=grpQn)
        for relName in getattr(grpCntObj, "relatedNames", ()):
            if relName not in dts.namedObjects or type(dts.namedObjects[relName]) not in (XbrlNetwork, XbrlCube, XbrlTableTemplate):
                dts.error("oimte:invalidGroupObject",
                          _("The groupContent object %(name)s relatedName %(relName)s MUST only include QNames associated with network objects, cube objects or table template objects."),
                          file=oimFile, name=grpCntObj.groupName, relName=relName)
