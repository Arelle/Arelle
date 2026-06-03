'''
See COPYRIGHT.md for copyright information.
'''
from arelle.PythonUtil import OrderedSet
from arelle.ModelValue import QName, qname
from .ErrorCatalog import emit_error
from .XbrlConcept import XbrlCollectionType, XbrlDataType, XbrlConcept
from .XbrlConst import objectsWithProperties, xbrl
from .XbrlDimension import XbrlDomain
from .XbrlLabel import XbrlLabelType
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlPropertyType

qnXbrlClassSubclass = qname(xbrl, "xbrl:class-subclass")


def _qname_key(value):
    if isinstance(value, QName):
        return (value.namespaceURI, value.localName)
    if isinstance(value, str):
        qn = qname(value, {"xbrl": xbrl})
        if isinstance(qn, QName):
            return (qn.namespaceURI, qn.localName)
    return None


_OBJECTS_WITH_PROPERTIES_KEYS = {
    _qname_key(qn) for qn in objectsWithProperties if _qname_key(qn) is not None
}


def _is_allowed_property_object_qname(value):
    if value in objectsWithProperties:
        return True
    return _qname_key(value) in _OBJECTS_WITH_PROPERTIES_KEYS


def validateNetworkFamily(compMdl, module, oimFile, *, assertObjectType, validateQNameReference, validateProperties):
    """Validate networks, propertyTypes and relationshipTypes within a module."""
    # Network Objects
    for ntwkObj in module.networks:
        assertObjectType(compMdl, ntwkObj, XbrlNetwork)
        extendTargetObj = None
        relTypeObj = None
        if ntwkObj.extendTargetName:
            extendTargetObj = validateQNameReference(compMdl, ntwkObj, "extendTargetName", XbrlNetwork)
            if extendTargetObj is not None:
                relTypeObj = validateQNameReference(compMdl, extendTargetObj, "relationshipTypeName", XbrlRelationshipType)
                if getattr(ntwkObj, "_extendResolved", False):
                    extendTargetObj = None  # don't extend, already been extended
                else:
                    ntwkObj._extendResolved = True
                    # Check for conflicting property values between extending network and target network
                    if getattr(ntwkObj, "properties", None) and getattr(extendTargetObj, "properties", None):
                        targetPropMap = {p.property: p.value for p in extendTargetObj.properties}
                        for propObj in ntwkObj.properties:
                            if propObj.property in targetPropMap and targetPropMap[propObj.property] != propObj.value:
                                emit_error(compMdl, "oimte:conflictingPropertyValues",
                                           _("The network %(name)s extending %(target)s defines property %(prop)s with value %(value)s conflicting with target value %(targetValue)s."),
                                           xbrlObject=ntwkObj, name=ntwkObj.extendTargetName, target=extendTargetObj.name,
                                           prop=propObj.property, value=propObj.value, targetValue=targetPropMap[propObj.property])
        elif ntwkObj.name:
            relTypeObj = validateQNameReference(compMdl, ntwkObj, "relationshipTypeName", XbrlRelationshipType)
        if not relTypeObj:
            continue

        ntwkCt = {}
        for rootQn in ntwkObj.roots:
            validateQNameReference(compMdl, ntwkObj, "roots", qnRef=rootQn,
                                   undefinedMessage=_("The network %(name)s root %(qname)s must be defined in the taxonomy model."),
                                   errorArgs={"name": ntwkObj.name, "qname": rootQn})
            ntwkCt[rootQn] = ntwkCt.get(rootQn, 0) + 1
        if any(ct > 1 for root, ct in ntwkCt.items()):
            emit_error(compMdl, "oimte:duplicateItemsInSet",
                       _("The network %(name)s has duplicated roots %(roots)s"),
                       xbrlObject=ntwkObj, roots=", ".join(str(root) for root, ct in ntwkCt.items() if ct > 1))

        ntwkCt = {}
        sources = OrderedSet()
        targets = OrderedSet()
        for i, relObj in enumerate(ntwkObj.relationships):
            assertObjectType(compMdl, relObj, XbrlRelationship)
            if relObj.source not in compMdl.namedObjects or relObj.target not in compMdl.namedObjects:
                validateQNameReference(compMdl, relObj, "source", qnRef=relObj.source,
                                       undefinedMessage=_("The network %(name)s relationship[%(nbr)s] source %(qname)s must be defined in the taxonomy model."),
                                       errorArgs={"name": ntwkObj.name, "nbr": i, "qname": relObj.source})
                validateQNameReference(compMdl, relObj, "target", qnRef=relObj.target,
                                       undefinedMessage=_("The network %(name)s relationship[%(nbr)s] target %(qname)s must be defined in the taxonomy model."),
                                       errorArgs={"name": ntwkObj.name, "nbr": i, "qname": relObj.target})
            else:
                sources.add(relObj.source)
                targets.add(relObj.target)
                if extendTargetObj is not None:
                    extendTargetObj.relationships.add(relObj)
            validateProperties(compMdl, oimFile, module, relObj)
            relObjPrefLbl = validateQNameReference(compMdl, relObj, "preferredLabel", XbrlLabelType, isOptional=True)
            relKey = (relObj.source, relObj.target, relObjPrefLbl, relObj.order)
            ntwkCt[relKey] = ntwkCt.get(relKey, 0) + 1
        if any(ct > 1 for relKey, ct in ntwkCt.items()):
            emit_error(compMdl, "oimte:duplicateItemsInSet",
                       _("The network %(name)s has duplicated relationships %(names)s"),
                       xbrlObject=ntwkObj, name=ntwkObj.name,
                       names=", ".join(f"{relFrom}\u2192{relTo}{f' [{str(prefLbl)}]' if prefLbl else ''} ord {str(ordr)}"
                                       for (relFrom, relTo, prefLbl, ordr), ct in ntwkCt.items() if ct > 1))
        ntwkObj._rootsFound = sources - targets
        if ntwkObj.roots:
            undeclaredRoots = ntwkObj._rootsFound - ntwkObj.roots
            if undeclaredRoots:
                emit_error(compMdl, "oimte:invalidNetworkRoot",
                           _("The network %(name)s network object roots property does not include these undeclared relationship roots: %(undeclaredRoots)s"),
                           xbrlObject=ntwkObj, name=ntwkObj.name,
                           undeclaredRoots=", ".join(sorted(str(r) for r in undeclaredRoots)))
            rootsAsTargets = ntwkObj.roots & targets
            if rootsAsTargets:
                emit_error(compMdl, "oimte:networkCyclic",
                           _("The network %(name)s has root(s) %(roots)s appearing as relationship targets."),
                           xbrlObject=ntwkObj, name=ntwkObj.name,
                           roots=", ".join(sorted(str(r) for r in rootsAsTargets)))
        else:
            ntwkObj.roots = ntwkObj._rootsFound  # not specified so use actual roots
        validateProperties(compMdl, oimFile, module, ntwkObj)

    # PropertyType Objects
    for i, propTpObj in enumerate(module.propertyTypes):
        assertObjectType(compMdl, propTpObj, XbrlPropertyType)
        dataTypeObj = validateQNameReference(compMdl, propTpObj, "dataType", (XbrlDataType, XbrlCollectionType))
        if not dataTypeObj:
            continue
        if dataTypeObj and propTpObj.enumerationDomain:
            if dataTypeObj.xsBaseType(compMdl) != "QName":
                emit_error(compMdl, "oimte:invalidQNameReference",
                           _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                           xbrlObject=propTpObj, name=propTpObj.name, qname=propTpObj.dataType)
            validateQNameReference(compMdl, propTpObj, "enumerationDomain", XbrlDomain)
        for allowedObjQn in (propTpObj.allowedObjects or ()):
            if not _is_allowed_property_object_qname(allowedObjQn):
                emit_error(compMdl, "oimte:invalidAllowedObject",
                           _("The property %(name)s has an invalid allowed object %(allowedObj)s"),
                           xbrlObject=propTpObj, name=propTpObj.name, allowedObj=allowedObjQn)

    # RelationshipType Objects
    for relTpObj in module.relationshipTypes:
        assertObjectType(compMdl, relTpObj, XbrlRelationshipType)
        for prop in ("allowedLinkProperties", "requiredLinkProperties"):
            for propTpQn in (getattr(relTpObj, prop) or ()):
                validateQNameReference(compMdl, relTpObj, prop, XbrlPropertyType, qnRef=propTpQn)
        if relTpObj.allowedLinkProperties:
            reqdNotAllowed = (relTpObj.requiredLinkProperties or set()) - relTpObj.allowedLinkProperties
            if reqdNotAllowed:
                emit_error(compMdl, "oimte:requiredPropertyNotAllowed",
                           _("The relationshipType %(name)s has required properties which are not allowed %(propTypes)s"),
                           xbrlObject=relTpObj, name=relTpObj.name,
                           propTypes=", ".join(str(q) for q in reqdNotAllowed))

    _validateClassSubclassConsistency(compMdl, module)


# Scalar concept properties that participate in class-subclass inheritance consistency checks
_CLASS_SUBCLASS_SCALAR_PROPS = ("dataType", "periodType", "nillable")


def _dataTypesRelated(compMdl, qn1, qn2):
    """Return True if qn1 and qn2 are in the same dataType inheritance chain
    (one is the other's baseType ancestor)."""
    if qn1 == qn2:
        return True

    def _ancestors(start):
        visited = set()
        cur = start
        while True:
            obj = compMdl.namedObjects.get(cur)
            base = getattr(obj, "baseType", None) if obj is not None else None
            if base is None:
                return
            if base in visited:
                return
            visited.add(base)
            yield base
            cur = base

    if qn2 in _ancestors(qn1):
        return True
    if qn1 in _ancestors(qn2):
        return True
    return False


def _conceptOwnPropertyMap(concept):
    """Return a dict {propertyQName: value} for the concept's properties list."""
    result = {}
    for prop in (getattr(concept, "properties", None) or ()):
        pq = getattr(prop, "property", None)
        if pq is not None and pq not in result:
            result[pq] = getattr(prop, "value", None)
    return result


def _validateClassSubclassConsistency(compMdl, module):
    """For each class-subclass relationship (source=subclass, target=class), ensure that scalar
    concept properties (dataType, periodType, nillable) and named properties defined on both the
    subclass and on any ancestor class in the inheritance chain agree. Emit
    oimte:conflictingPropertyValues otherwise."""
    # Collect class-subclass edges across all networks in this module
    edges = {}  # subclass concept QName -> list of class concept QNames
    for ntwkObj in getattr(module, "networks", ()):
        if getattr(ntwkObj, "relationshipTypeName", None) != qnXbrlClassSubclass:
            continue
        for rel in getattr(ntwkObj, "relationships", ()) or ():
            src = getattr(rel, "source", None)
            tgt = getattr(rel, "target", None)
            if src is None or tgt is None:
                continue
            edges.setdefault(src, []).append(tgt)
    if not edges:
        return

    def _walkAncestors(start):
        """Yield ancestor concepts (class side) of `start` in BFS order, skipping cycles."""
        seen = {start}
        queue = list(edges.get(start, ()))
        while queue:
            nextQn = queue.pop(0)
            if nextQn in seen:
                continue
            seen.add(nextQn)
            ancObj = compMdl.namedObjects.get(nextQn)
            if ancObj is not None:
                yield ancObj
            queue.extend(edges.get(nextQn, ()))

    for subQn in edges.keys():
        subObj = compMdl.namedObjects.get(subQn)
        if not isinstance(subObj, XbrlConcept):
            continue
        subPropMap = _conceptOwnPropertyMap(subObj)
        # For each scalar property, find first ancestor that defines it
        ancestorScalarDefs = {p: None for p in _CLASS_SUBCLASS_SCALAR_PROPS}
        ancestorPropDefs = {}  # propertyQName -> (ancestorObj, value)
        for ancObj in _walkAncestors(subQn):
            if not isinstance(ancObj, XbrlConcept):
                continue
            for scalarProp in _CLASS_SUBCLASS_SCALAR_PROPS:
                if ancestorScalarDefs[scalarProp] is None:
                    av = getattr(ancObj, scalarProp, None)
                    if av is not None:
                        ancestorScalarDefs[scalarProp] = (ancObj, av)
            for pq, pv in _conceptOwnPropertyMap(ancObj).items():
                if pq not in ancestorPropDefs:
                    ancestorPropDefs[pq] = (ancObj, pv)
        # Compare scalars
        for scalarProp in _CLASS_SUBCLASS_SCALAR_PROPS:
            subVal = getattr(subObj, scalarProp, None)
            anc = ancestorScalarDefs[scalarProp]
            if subVal is not None and anc is not None and subVal != anc[1]:
                if scalarProp == "dataType" and _dataTypesRelated(compMdl, subVal, anc[1]):
                    continue  # subtype/supertype relationship is consistent
                emit_error(compMdl, "oimte:conflictingPropertyValues",
                           _("Concept %(name)s %(prop)s value %(subVal)s conflicts with inherited value %(ancVal)s from class %(ancName)s."),
                           xbrlObject=subObj, name=subObj.name, prop=scalarProp,
                           subVal=subVal, ancVal=anc[1], ancName=anc[0].name)
        # Compare named properties
        for pq, subVal in subPropMap.items():
            anc = ancestorPropDefs.get(pq)
            if anc is not None and subVal != anc[1]:
                emit_error(compMdl, "oimte:conflictingPropertyValues",
                           _("Concept %(name)s property %(prop)s value %(subVal)r conflicts with inherited value %(ancVal)r from class %(ancName)s."),
                           xbrlObject=subObj, name=subObj.name, prop=pq,
                           subVal=subVal, ancVal=anc[1], ancName=anc[0].name)
