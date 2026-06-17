'''
See COPYRIGHT.md for copyright information.
'''

from .ErrorCatalog import emit_error
from .XbrlHeading import XbrlHeading
from .XbrlConcept import XbrlCollectionType, XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlConst import qnXbrlConceptObj
from .XbrlDimension import XbrlDomainNetwork


def validateConceptFamily(compMdl, module, oimFile, *, assertObjectType, validateQNameReference, validateProperties):
    """Validate the object family centered on XbrlConcept.py.

    This groups headings, concepts, datatypes, and collection types together so
    refactoring can follow the object-family structure used by the error catalog.
    """

    for heading in module.headings:
        assertObjectType(compMdl, heading, XbrlHeading)
        validateProperties(compMdl, oimFile, module, heading)

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
            validateQNameReference(compMdl, cncpt, "enumerationDomain", XbrlDomainNetwork)
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
                validateQNameReference(compMdl, utObj, utProp, XbrlDataType, isOptional=True)
        _validateFacetRestrictions(compMdl, dtObj)

    for collObj in module.collectionTypes:
        assertObjectType(compMdl, collObj, XbrlCollectionType)
        validateQNameReference(compMdl, collObj, "dataType", (XbrlDataType, XbrlCollectionType))
        minItems = getattr(collObj, "minItems", None)
        maxItems = getattr(collObj, "maxItems", None)
        if minItems is not None and maxItems is not None and maxItems < minItems:
            emit_error(compMdl, "oimte:invalidCollectionType",
                       _("CollectionType %(name)s has maxItems %(maxItems)s less than minItems %(minItems)s."),
                       xbrlObject=collObj, name=collObj.name, minItems=minItems, maxItems=maxItems)
        validateProperties(compMdl, oimFile, module, collObj)


# whitespace restriction order: derived facet MUST NOT be less restrictive than base
_WHITESPACE_RANK = {"preserve": 0, "replace": 1, "collapse": 2}


def _baseDataTypeChain(compMdl, dtObj):
    """Yield successive base XbrlDataType objects in restriction order (does not include dtObj)."""
    visited = set()
    cur = dtObj
    while True:
        btQn = getattr(cur, "baseType", None)
        if btQn is None:
            return
        baseObj = compMdl.namedObjects.get(btQn)
        if not isinstance(baseObj, XbrlDataType):
            return
        if id(baseObj) in visited:
            return
        visited.add(id(baseObj))
        yield baseObj
        cur = baseObj


def _validateFacetRestrictions(compMdl, dtObj):
    """Validate that derived dataType facets are restrictions (not relaxations) of base dataType facets."""
    name = dtObj.name
    for baseObj in _baseDataTypeChain(compMdl, dtObj):
        baseName = baseObj.name
        # enumeration: derived MUST be subset of base
        derivedEnum = getattr(dtObj, "enumeration", None) or ()
        baseEnum = getattr(baseObj, "enumeration", None) or ()
        if derivedEnum and baseEnum:
            extra = set(derivedEnum) - set(baseEnum)
            if extra:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s enumeration includes values %(extra)s not in base dataType %(baseName)s enumeration."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           extra=", ".join(repr(v) for v in sorted(extra, key=str)))
        # fractionDigits: derived <= base
        if dtObj.fractionDigits is not None and baseObj.fractionDigits is not None:
            if dtObj.fractionDigits > baseObj.fractionDigits:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s fractionDigits %(d)s exceeds base dataType %(baseName)s fractionDigits %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.fractionDigits, b=baseObj.fractionDigits)
        # totalDigits: derived <= base
        if dtObj.totalDigits is not None and baseObj.totalDigits is not None:
            if dtObj.totalDigits > baseObj.totalDigits:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s totalDigits %(d)s exceeds base dataType %(baseName)s totalDigits %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.totalDigits, b=baseObj.totalDigits)
        # length: derived must equal base.length when base specifies length
        if baseObj.length is not None and dtObj.length is not None:
            if dtObj.length != baseObj.length:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s length %(d)s differs from base dataType %(baseName)s length %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.length, b=baseObj.length)
        # length must also not violate base.minLength / base.maxLength
        if baseObj.minLength is not None and dtObj.length is not None and dtObj.length < baseObj.minLength:
            emit_error(compMdl, "oimte:illegalConstraint",
                       _("Derived dataType %(name)s length %(d)s is less than base dataType %(baseName)s minLength %(b)s."),
                       xbrlObject=dtObj, name=name, baseName=baseName,
                       d=dtObj.length, b=baseObj.minLength)
        if baseObj.maxLength is not None and dtObj.length is not None and dtObj.length > baseObj.maxLength:
            emit_error(compMdl, "oimte:illegalConstraint",
                       _("Derived dataType %(name)s length %(d)s exceeds base dataType %(baseName)s maxLength %(b)s."),
                       xbrlObject=dtObj, name=name, baseName=baseName,
                       d=dtObj.length, b=baseObj.maxLength)
        # minLength: derived >= base
        if dtObj.minLength is not None and baseObj.minLength is not None:
            if dtObj.minLength < baseObj.minLength:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s minLength %(d)s is less than base dataType %(baseName)s minLength %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.minLength, b=baseObj.minLength)
        # maxLength: derived <= base
        if dtObj.maxLength is not None and baseObj.maxLength is not None:
            if dtObj.maxLength > baseObj.maxLength:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s maxLength %(d)s exceeds base dataType %(baseName)s maxLength %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.maxLength, b=baseObj.maxLength)
        # minInclusive: derived >= base
        if dtObj.minInclusive is not None and baseObj.minInclusive is not None:
            if dtObj.minInclusive < baseObj.minInclusive:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s minInclusive %(d)s is less than base dataType %(baseName)s minInclusive %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.minInclusive, b=baseObj.minInclusive)
        # maxInclusive: derived <= base
        if dtObj.maxInclusive is not None and baseObj.maxInclusive is not None:
            if dtObj.maxInclusive > baseObj.maxInclusive:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s maxInclusive %(d)s exceeds base dataType %(baseName)s maxInclusive %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.maxInclusive, b=baseObj.maxInclusive)
        # minExclusive: derived >= base
        if dtObj.minExclusive is not None and baseObj.minExclusive is not None:
            if dtObj.minExclusive < baseObj.minExclusive:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s minExclusive %(d)s is less than base dataType %(baseName)s minExclusive %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.minExclusive, b=baseObj.minExclusive)
        # maxExclusive: derived <= base
        if dtObj.maxExclusive is not None and baseObj.maxExclusive is not None:
            if dtObj.maxExclusive > baseObj.maxExclusive:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s maxExclusive %(d)s exceeds base dataType %(baseName)s maxExclusive %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.maxExclusive, b=baseObj.maxExclusive)
        # whiteSpace: derived must be >= base in restriction order
        if dtObj.whiteSpace is not None and baseObj.whiteSpace is not None:
            dRank = _WHITESPACE_RANK.get(dtObj.whiteSpace)
            bRank = _WHITESPACE_RANK.get(baseObj.whiteSpace)
            if dRank is not None and bRank is not None and dRank < bRank:
                emit_error(compMdl, "oimte:illegalConstraint",
                           _("Derived dataType %(name)s whiteSpace %(d)s is less restrictive than base dataType %(baseName)s whiteSpace %(b)s."),
                           xbrlObject=dtObj, name=name, baseName=baseName,
                           d=dtObj.whiteSpace, b=baseObj.whiteSpace)
