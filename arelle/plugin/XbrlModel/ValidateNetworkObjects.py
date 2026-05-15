'''
See COPYRIGHT.md for copyright information.
'''
from arelle.PythonUtil import OrderedSet
from .ErrorCatalog import emit_error
from .XbrlConcept import XbrlCollectionType, XbrlDataType
from .XbrlConst import objectsWithProperties
from .XbrlDimension import XbrlDomain
from .XbrlLabel import XbrlLabelType
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlPropertyType


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
        for allowedObjQn in propTpObj.allowedObjects:
            if allowedObjQn not in objectsWithProperties:
                emit_error(compMdl, "oimte:invalidAllowedObject",
                           _("The property %(name)s has an invalid allowed object %(allowedObj)s"),
                           xbrlObject=propTpObj, name=propTpObj.name, allowedObj=allowedObjQn)

    # RelationshipType Objects
    for relTpObj in module.relationshipTypes:
        assertObjectType(compMdl, relTpObj, XbrlRelationshipType)
        for prop in ("allowedLinkProperties", "requiredLinkProperties"):
            for propTpQn in getattr(relTpObj, prop):
                validateQNameReference(compMdl, relTpObj, prop, XbrlPropertyType, qnRef=propTpQn)
        if relTpObj.allowedLinkProperties:
            reqdNotAllowed = relTpObj.requiredLinkProperties - relTpObj.allowedLinkProperties
            if reqdNotAllowed:
                emit_error(compMdl, "oimte:requiredPropertyNotAllowed",
                           _("The relationshipType %(name)s has required properties which are not allowed %(propTypes)s"),
                           xbrlObject=relTpObj, name=relTpObj.name,
                           propTypes=", ".join(str(q) for q in reqdNotAllowed))
