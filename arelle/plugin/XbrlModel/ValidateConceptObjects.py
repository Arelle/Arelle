'''
See COPYRIGHT.md for copyright information.
'''

from .ErrorCatalog import emit_error
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlCollectionType, XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlConst import qnXbrlConceptObj
from .XbrlDimension import XbrlDomain


def validateConceptFamily(compMdl, module, oimFile, *, assertObjectType, validateQNameReference, validateProperties):
    """Validate the object family centered on XbrlConcept.py.

    This groups abstracts, concepts, datatypes, and collection types together so
    refactoring can follow the object-family structure used by the error catalog.
    """

    for absObj in module.abstracts:
        assertObjectType(compMdl, absObj, XbrlAbstract)
        validateProperties(compMdl, oimFile, module, absObj)

    for cncpt in module.concepts:
        assertObjectType(compMdl, cncpt, XbrlConcept)
        perType = getattr(cncpt, "periodType", None)
        if perType not in ("instant", "duration", "none"):
            emit_error(compMdl, "oimte:invalidPeriodType",
                       _("Concept %(name)s has invalid period type %(perType)s"),
                       xbrlObject=cncpt, name=cncpt.name, perType=perType)
        dtObj = validateQNameReference(compMdl, cncpt, "dataType", (XbrlDataType, XbrlCollectionType))
        if isinstance(dtObj, XbrlDataType) and dtObj.allowedObjects and qnXbrlConceptObj not in dtObj.allowedObjects:
            emit_error(compMdl, "oimte:disallowedObjectDataType",
                       _("Concept %(name)s is not allowed for dataType %(dataType)s"),
                       xbrlObject=cncpt, name=cncpt.name, dataType=dtObj.name)
        if getattr(cncpt, "enumerationDomain", None):
            validateQNameReference(compMdl, cncpt, "enumerationDomain", XbrlDomain)
        validateProperties(compMdl, oimFile, module, cncpt)

    for dtObj in module.dataTypes:
        assertObjectType(compMdl, dtObj, XbrlDataType)
        btQn = dtObj.baseType
        if btQn and btQn.namespaceURI != "http://www.w3.org/2001/XMLSchema":
            validateQNameReference(compMdl, dtObj, "baseType", XbrlDataType)
        if dtObj.unitType is not None:
            utObj = dtObj.unitType
            assertObjectType(compMdl, utObj, XbrlUnitType)
            for utProp in ("dataTypeNumerator", "dataTypeDenominator", "dataTypeMultiplier"):
                validateQNameReference(compMdl, utObj, utProp, XbrlDataType)

    for collObj in module.collectionTypes:
        assertObjectType(compMdl, collObj, XbrlCollectionType)
        validateQNameReference(compMdl, collObj, "dataType", XbrlDataType)
        validateProperties(compMdl, oimFile, module, collObj)
