'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
from decimal import Decimal
from ordered_set import OrderedSet
from arelle.ModelValue import QName, qname
from .ErrorCatalog import emit_error
from .XbrlConcept import XbrlCollectionType, XbrlDataType, XbrlConcept
from .XbrlConst import objectsWithProperties, qnXbrlRootSource, xbrl, xbrla
from .XbrlCube import XbrlCube, conceptCoreDim
from .XbrlDimension import XbrlDomainNetwork
from .XbrlLabel import XbrlLabelType
from .XbrlModule import xbrlObjectQNames
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlPropertyType

qnXbrlClassSubclass = qname(xbrl, "xbrl:class-subclass")
qnPreferredLabel = qname(xbrl, "xbrl:preferredLabel")
qnXbrlTaxonomyGroup = qname(xbrl, "xbrl:taxonomy-group")
qnXbrlaBalance = qname(xbrla, "xbrla:balance")
qnXbrlSummationItem = qname(xbrl, "xbrl:summation-item")
qnXbrlWeight = qname(xbrl, "xbrl:weight")
# The calculation proposal (summation-item-relationship-proposal.md 5.4) moves the
# reconciliation property to the accounting namespace, as xbrla:reconciliation, because it
# is defined entirely in terms of xbrla:balance. That rename is not ratified and core.json
# still declares xbrl:reconciliation, so the property is named in one place here and the
# move is a one-line change once the working group rules on it.
qnReconciliation = qname(xbrl, "xbrl:reconciliation")
qnTolerance = qname(xbrl, "xbrl:tolerance")
qnSummationRelation = qname(xbrl, "xbrl:summationRelation")

# Error codes for the summation-item definition-time checks, from section 10 of the
# proposal. They are kept in one table so the namespace can be changed in one place.
_CALC_ERROR = {
    "nonNumericConcept": "oimtc:nonNumericConcept",
    "periodTypeMismatch": "oimtc:summationItemPeriodTypeMismatch",
    "balanceInconsistent": "oimtc:summationItemBalanceInconsistent",
    "duplicateRelationship": "oimtc:duplicateSummationItemRelationship",
    "conceptNotInCube": "oimtc:summationItemConceptNotInCube",
    "invalidTolerance": "oimtc:invalidTolerance",
    "conflictingSummationRelation": "oimtc:conflictingSummationRelation",
}

# Section 5.1 admits only concepts whose datatype derives from xs:decimal. xs:float and
# xs:double are numeric but are excluded: the interval arithmetic of section 7 is defined
# over decimal values and the decimals property, neither of which applies to binary
# floating point.
_DECIMAL_DERIVED_XSD_TYPES = frozenset((
    "decimal", "integer", "long", "int", "short", "byte",
    "nonPositiveInteger", "negativeInteger", "nonNegativeInteger", "positiveInteger",
    "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte",
))

# Flow relationship-type constraints from oim-taxonomy.md (§instant-inflow/outflow/accrual/contra).
# Each entry: (required source periodType, required target periodType, balance rule) where the balance
# rule is one of: "sameIfBoth" (equal if both define balance), "diffIfBoth" (differ if both define),
# "bothRequired" (both MUST define balance), "bothRequiredDiff" (both MUST define AND differ).
_FLOW_RULES = {
    qname(xbrla, "xbrla:instant-inflow"):  ("instant", "duration", "sameIfBoth"),
    qname(xbrla, "xbrla:instant-outflow"): ("instant", "duration", "diffIfBoth"),
    qname(xbrla, "xbrla:instant-accrual"): ("instant", "duration", "bothRequired"),
    qname(xbrla, "xbrla:instant-contra"):  ("instant", "instant",  "bothRequiredDiff"),
}

def _conceptBalance(conceptObj):
    """Return the raw xbrla:balance property value of a concept, or None if not defined."""
    for propObj in getattr(conceptObj, "properties", None) or ():
        if propObj.property == qnXbrlaBalance:
            return getattr(propObj, "value", None)
    return None


def _rawPropertyValue(obj, propertyQn):
    """A property's value, whether or not its owning object has been property-validated.

    propertyObjectValue returns only the validated typed value, which is absent on an object
    whose module has not been through validateProperties -- a module compiled on demand, for
    instance. Falling back to the raw value keeps these checks independent of that ordering.
    """
    value = obj.propertyObjectValue(propertyQn)
    if value is not None:
        return value
    for propObj in getattr(obj, "properties", None) or ():
        if propObj.property == propertyQn:
            return getattr(propObj, "value", None)
    return None


def _validateTolerance(compMdl, obj, objName):
    """A declared xbrl:tolerance MUST be a non-negative decimal (proposal 5.7)."""
    value = _rawPropertyValue(obj, qnTolerance)
    if value is None:
        return
    try:
        isNegative = Decimal(str(value)) < 0
    except (ArithmeticError, ValueError):
        return  # a non-decimal value is reported as a property value error
    if isNegative:
        emit_error(compMdl, _CALC_ERROR["invalidTolerance"],
                   _("The xbrl:tolerance %(tolerance)s declared on %(object)s MUST be a non-negative decimal; a tolerance widens the calculated total interval."),
                   xbrlObject=obj, tolerance=value, object=objName)


def _isDecimalDerived(compMdl, conceptObj):
    """True if the concept's datatype is, or derives from, xs:decimal (proposal 5.1)."""
    dtObj = compMdl.namedObjects.get(conceptObj.dataType)
    if not isinstance(dtObj, XbrlDataType):
        return True  # unresolved datatype is reported by the concept checks, not here
    return dtObj.xsBaseType(compMdl) in _DECIMAL_DERIVED_XSD_TYPES


def _effectiveReconciliation(ntwkObj, relObj):
    """Effective reconciliation for a relationship (proposal 3.2: relationship, then network).

    The model level of the precedence chain is not consulted: reconciliation is not
    declared on the XBRL model object.
    """
    for obj in (relObj, ntwkObj):
        value = obj.propertyObjectValue(qnReconciliation)
        if value is not None:
            return str(value).strip().lower() in ("true", "1")
    return False


def _cubeConceptDomains(compMdl, ntwkQn):
    """Concept-domain members of each cube that lists this network in its cubeNetworks.

    Returns a list of (cubeName, frozenset of concept QNames). A cube whose concept
    dimension declares no domainNetwork is unconstrained and is omitted, since every
    concept satisfies it (proposal 5.6).
    """
    domainsByNetwork = getattr(compMdl, "_calcCubeConceptDomains", None)
    if domainsByNetwork is None:
        domainsByNetwork = defaultdict(list)
        for cubeObj in compMdl.namedObjects.values():
            if not isinstance(cubeObj, XbrlCube) or not cubeObj.cubeNetworks:
                continue
            members = None
            for cubeDimObj in cubeObj.cubeDimensions or ():
                if cubeDimObj.dimension == conceptCoreDim and cubeDimObj.domainNetwork:
                    domNwkObj = compMdl.namedObjects.get(cubeDimObj.domainNetwork)
                    if isinstance(domNwkObj, XbrlDomainNetwork):
                        members = frozenset(relObj.target for relObj in compMdl.effectiveRelationships(domNwkObj))
                    break
            if members is not None:
                for networkQn in cubeObj.cubeNetworks:
                    domainsByNetwork[networkQn].append((cubeObj.name, members))
        setattr(compMdl, "_calcCubeConceptDomains", domainsByNetwork)
    return domainsByNetwork.get(ntwkQn, ())


def _validateSummationItemNetwork(compMdl, ntwkObj):
    """Definition-time checks for a summation-item (calculation) network.

    Implements sections 5.1 and 5.3 to 5.6 of the calculation relationships proposal
    (oim/specifications/oim-taxonomy/summation-item-relationship-proposal.md). Section 5.2,
    that a weight is 1 or -1, needs no check here: xbrl:weight is typed xbrlr:weightType,
    whose enumeration is ("1", "-1"), so a weight of any other value is already reported as
    oimte:propertyValueDataTypeMismatch by the property value validation.
    """
    # 5.7 tolerance, wherever it is declared for this network
    _validateTolerance(compMdl, ntwkObj, f"network {ntwkObj.name}")
    if not getattr(compMdl, "_calcModelToleranceChecked", False):
        compMdl._calcModelToleranceChecked = True
        for mdlObj in compMdl.xbrlModels.values():
            _validateTolerance(compMdl, mdlObj, f"model {getattr(mdlObj, 'name', None)}")

    conceptsUsed = OrderedSet()
    relsByEndpoints = defaultdict(list)
    relationsByTotal = defaultdict(set)
    for relObj in ntwkObj.relationships or ():
        if relObj.source == qnXbrlRootSource:
            continue  # virtual origin, not a total-to-contributing relationship
        srcObj = compMdl.namedObjects.get(relObj.source)
        tgtObj = compMdl.namedObjects.get(relObj.target)
        if not isinstance(srcObj, XbrlConcept) or not isinstance(tgtObj, XbrlConcept):
            continue  # non-concept endpoints reported by the generic source/target checks
        relName = f"{relObj.source}\u2192{relObj.target}"
        conceptsUsed.add(relObj.source)
        conceptsUsed.add(relObj.target)
        relsByEndpoints[(relObj.source, relObj.target)].append(relObj)
        # 5.8: the effective relation for a relationship is its own value, else the network's,
        # else the specification default. It describes how the sum of ALL the contributions
        # compares with the total, so every relationship of one calculation must agree.
        relation = _rawPropertyValue(relObj, qnSummationRelation)
        if relation is None:
            relation = _rawPropertyValue(ntwkObj, qnSummationRelation)
        relationsByTotal[relObj.source].add(str(relation) if relation is not None else "equal")

        # 5.1 the total and every contributing concept MUST be decimal-derived
        for conceptQn, conceptObj in ((relObj.source, srcObj), (relObj.target, tgtObj)):
            if not _isDecimalDerived(compMdl, conceptObj):
                emit_error(compMdl, _CALC_ERROR["nonNumericConcept"],
                           _("The summation-item network %(name)s relationship %(rel)s uses concept %(concept)s whose dataType %(dataType)s does not derive from xs:decimal; calculation consistency is defined only over decimal numeric values."),
                           xbrlObject=relObj, name=ntwkObj.name, rel=relName,
                           concept=conceptQn, dataType=conceptObj.dataType)

        # 5.3 the total and every contributing concept MUST share a periodType
        if srcObj.periodType != tgtObj.periodType:
            emit_error(compMdl, _CALC_ERROR["periodTypeMismatch"],
                       _("The summation-item network %(name)s relationship %(rel)s relates concepts with different periodTypes, %(sourcePeriodType)s and %(targetPeriodType)s; a summation-item relationship MUST relate concepts of the same periodType."),
                       xbrlObject=relObj, name=ntwkObj.name, rel=relName,
                       sourcePeriodType=srcObj.periodType, targetPeriodType=tgtObj.periodType)

        # 5.4 balance, weight and reconciliation
        srcBal = _conceptBalance(srcObj)
        tgtBal = _conceptBalance(tgtObj)
        if srcBal is not None and tgtBal is not None:
            weight = relObj.propertyObjectValue(qnXbrlWeight)
            try:
                weightIsPositive = int(str(weight)) > 0
            except (TypeError, ValueError):
                continue  # an unusable weight is reported as a property value error
            reconciliation = _effectiveReconciliation(ntwkObj, relObj)
            # Without reconciliation, a weight of 1 keeps the balance side and -1 flips it
            # (XBRL v2.1 5.1.1.2); reconciliation inverts the rule so that a calculation may
            # deliberately cross the debit/credit divide.
            balancesMustMatch = weightIsPositive != reconciliation
            if (srcBal == tgtBal) != balancesMustMatch:
                emit_error(compMdl, _CALC_ERROR["balanceInconsistent"],
                           _("The summation-item network %(name)s relationship %(rel)s has weight %(weight)s with reconciliation %(reconciliation)s, which requires the total and contributing concept to have %(requirement)s xbrla:balance, but they are %(sourceBalance)s and %(targetBalance)s."),
                           xbrlObject=relObj, name=ntwkObj.name, rel=relName, weight=weight,
                           reconciliation=str(reconciliation).lower(),
                           requirement="the same" if balancesMustMatch else "different",
                           sourceBalance=srcBal, targetBalance=tgtBal)

    # 5.5 a concept contributes to a given total exactly once, whatever the weight or order
    for (sourceQn, targetQn), relObjs in relsByEndpoints.items():
        if len(relObjs) > 1:
            emit_error(compMdl, _CALC_ERROR["duplicateRelationship"],
                       _("The summation-item network %(name)s defines the relationship %(rel)s %(count)s times; a concept MUST contribute to a given total exactly once."),
                       xbrlObject=relObjs[0], name=ntwkObj.name,
                       rel=f"{sourceQn}\u2192{targetQn}", count=len(relObjs))

    # 5.8 every relationship of one calculation MUST resolve to the same summation relation
    for totalQn, relations in relationsByTotal.items():
        if len(relations) > 1:
            emit_error(compMdl, _CALC_ERROR["conflictingSummationRelation"],
                       _("The calculation of %(total)s in network %(name)s resolves to more than one xbrl:summationRelation (%(relations)s); the relation describes how the sum of all the contributions compares with the total, so it cannot differ between them."),
                       xbrlObject=ntwkObj, total=totalQn, name=ntwkObj.name,
                       relations=", ".join(sorted(relations)))

    # 5.6 every concept used by a cube-associated calculation MUST be in the cube's domain
    for cubeQn, domainMembers in _cubeConceptDomains(compMdl, ntwkObj.name):
        for conceptQn in conceptsUsed:
            if conceptQn not in domainMembers:
                emit_error(compMdl, _CALC_ERROR["conceptNotInCube"],
                           _("The summation-item network %(name)s uses concept %(concept)s which is not a member of the concept dimension domain of cube %(cube)s; a calculation cannot constrain facts for a concept the cube does not admit."),
                           xbrlObject=ntwkObj, name=ntwkObj.name, concept=conceptQn, cube=cubeQn)


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
    for ntwkObj in module.networks or ():
        assertObjectType(compMdl, ntwkObj, XbrlNetwork)
        extendTargetObj = None
        relTypeObj = None
        if ntwkObj.extends:
            extendTargetObj = validateQNameReference(compMdl, ntwkObj, "extends", XbrlNetwork,
                                                     invalidTypeMsgCode="oimte:invalidObjectType")
            if extendTargetObj is not None:
                relTypeObj = validateQNameReference(compMdl, extendTargetObj, "relationshipTypeName", XbrlRelationshipType)
                if not getattr(extendTargetObj, "isExtensible", True):
                    emit_error(compMdl, "oimte:illegalExtensionOfNonExtensibleObject",
                               _("The network %(target)s cannot be extended because it is non-extensible."),
                               xbrlObject=ntwkObj, target=extendTargetObj.name)
                    extendTargetObj = None
                elif getattr(ntwkObj, "_extendResolved", False):
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
                                           xbrlObject=ntwkObj, name=ntwkObj.extends, target=extendTargetObj.name,
                                           prop=propObj.property, value=propObj.value, targetValue=targetPropMap[propObj.property])
        elif ntwkObj.name:
            relTypeObj = validateQNameReference(compMdl, ntwkObj, "relationshipTypeName", XbrlRelationshipType)
        if not relTypeObj:
            continue
        if getattr(relTypeObj, "name", None) == qnXbrlTaxonomyGroup:
            emit_error(compMdl, "oimte:taxonomyGroupInNetwork",
                       _("The network %(name)s uses relationship type xbrl:taxonomy-group which MUST NOT be used in network objects."),
                       xbrlObject=ntwkObj, name=ntwkObj.name)
            continue

        flowRule = _FLOW_RULES.get(getattr(relTypeObj, "name", None))
        if flowRule is not None:
            reqSrcPeriod, reqTgtPeriod, balanceRule = flowRule
            for relObj in ntwkObj.relationships or ():
                if relObj.source == qnXbrlRootSource:
                    continue  # virtual origin, not a concept-to-concept flow relationship
                srcObj = compMdl.namedObjects.get(relObj.source)
                tgtObj = compMdl.namedObjects.get(relObj.target)
                if not isinstance(srcObj, XbrlConcept) or not isinstance(tgtObj, XbrlConcept):
                    continue  # non-concept endpoints reported by generic source/target checks
                relName = f"{relObj.source}→{relObj.target}"
                if getattr(srcObj, "periodType", None) != reqSrcPeriod:
                    emit_error(compMdl, "oimte:conceptPropertiesInconsistentWithRelationship",
                               _("The %(relType)s network %(name)s relationship %(rel)s source concept %(concept)s MUST have periodType '%(req)s'."),
                               xbrlObject=ntwkObj, relType=relTypeObj.name, name=ntwkObj.name, rel=relName, concept=relObj.source, req=reqSrcPeriod)
                if getattr(tgtObj, "periodType", None) != reqTgtPeriod:
                    emit_error(compMdl, "oimte:conceptPropertiesInconsistentWithRelationship",
                               _("The %(relType)s network %(name)s relationship %(rel)s target concept %(concept)s MUST have periodType '%(req)s'."),
                               xbrlObject=ntwkObj, relType=relTypeObj.name, name=ntwkObj.name, rel=relName, concept=relObj.target, req=reqTgtPeriod)
                srcBal = _conceptBalance(srcObj)
                tgtBal = _conceptBalance(tgtObj)
                if balanceRule in ("bothRequired", "bothRequiredDiff") and (srcBal is None or tgtBal is None):
                    emit_error(compMdl, "oimte:conceptPropertiesInconsistentWithRelationship",
                               _("The %(relType)s network %(name)s relationship %(rel)s source and target concepts MUST both define an xbrla:balance property."),
                               xbrlObject=ntwkObj, relType=relTypeObj.name, name=ntwkObj.name, rel=relName)
                if srcBal is not None and tgtBal is not None:
                    if balanceRule == "sameIfBoth" and srcBal != tgtBal:
                        emit_error(compMdl, "oimte:conceptPropertiesInconsistentWithRelationship",
                                   _("The %(relType)s network %(name)s relationship %(rel)s source and target xbrla:balance MUST be the same value."),
                                   xbrlObject=ntwkObj, relType=relTypeObj.name, name=ntwkObj.name, rel=relName)
                    elif balanceRule in ("diffIfBoth", "bothRequiredDiff") and srcBal == tgtBal:
                        emit_error(compMdl, "oimte:conceptPropertiesInconsistentWithRelationship",
                                   _("The %(relType)s network %(name)s relationship %(rel)s source and target xbrla:balance MUST have different values."),
                                   xbrlObject=ntwkObj, relType=relTypeObj.name, name=ntwkObj.name, rel=relName)

        # Snapshot base relationships before mutation so extends-duplicate check can compare cleanly
        if extendTargetObj is not None:
            _baseRelKeys = frozenset((r.source, r.target, getattr(r, "order", None)) for r in getattr(extendTargetObj, "relationships", None) or ())
            # The extended relationships are appended to extendTargetObj.relationships
            # below; a base network that declared no relationships carries None, so
            # initialise it to an empty set before extension.
            if extendTargetObj.relationships is None:
                extendTargetObj.relationships = OrderedSet()
        else:
            _baseRelKeys = frozenset()

        ntwkCt = {}
        sources = OrderedSet()
        targets = OrderedSet()
        hasRootSourceRel = False
        for i, relObj in enumerate(ntwkObj.relationships or ()):
            assertObjectType(compMdl, relObj, XbrlRelationship)
            isRootSourceRel = relObj.source == qnXbrlRootSource
            if isRootSourceRel:
                hasRootSourceRel = True
                # xbrl:rootSource is a virtual origin; validate only the target.
                # A rootSource→rootSource self-reference is also invalid.
                if relObj.target == qnXbrlRootSource:
                    emit_error(compMdl, "oimte:invalidRootSourceReference",
                               _("The network %(name)s relationship[%(nbr)s] uses xbrl:rootSource as a target; xbrl:rootSource MUST only appear as a relationship source."),
                               xbrlObject=relObj, name=ntwkObj.name, nbr=i)
                elif relObj.target not in compMdl.namedObjects:
                    validateQNameReference(compMdl, relObj, "target", qnRef=relObj.target,
                                           undefinedMessage=_("The network %(name)s rootSource relationship[%(nbr)s] target %(qname)s must be defined in the taxonomy model."),
                                           errorArgs={"name": ntwkObj.name, "nbr": i, "qname": relObj.target})
                else:
                    if extendTargetObj is not None:
                        extendTargetObj.relationships.add(relObj)
            elif relObj.target == qnXbrlRootSource:
                # xbrl:rootSource must never appear as a relationship target
                emit_error(compMdl, "oimte:invalidRootSourceReference",
                           _("The network %(name)s relationship[%(nbr)s] uses xbrl:rootSource as a target; xbrl:rootSource MUST only appear as a relationship source."),
                           xbrlObject=relObj, name=ntwkObj.name, nbr=i)
            elif relObj.source not in compMdl.namedObjects or relObj.target not in compMdl.namedObjects:
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
                srcObj = compMdl.namedObjects[relObj.source]
                tgtObj = compMdl.namedObjects[relObj.target]
                srcObjTypeQn = xbrlObjectQNames.get(type(srcObj))
                tgtObjTypeQn = xbrlObjectQNames.get(type(tgtObj))
                if getattr(relTypeObj, "sourceObjects", None) and srcObjTypeQn not in relTypeObj.sourceObjects:
                    emit_error(compMdl, "oimte:invalidRelationshipSourceObject",
                               _("The network %(name)s relationship[%(nbr)s] source %(source)s is %(sourceType)s which is not allowed by the relationship type sourceObjects."),
                               xbrlObject=relObj, name=ntwkObj.name, nbr=i, source=relObj.source, sourceType=srcObjTypeQn)
                if getattr(relTypeObj, "targetObjects", None) and tgtObjTypeQn not in relTypeObj.targetObjects:
                    emit_error(compMdl, "oimte:invalidRelationshipTargetObject",
                               _("The network %(name)s relationship[%(nbr)s] target %(target)s is %(targetType)s which is not allowed by the relationship type targetObjects."),
                               xbrlObject=relObj, name=ntwkObj.name, nbr=i, target=relObj.target, targetType=tgtObjTypeQn)
            validateProperties(compMdl, oimFile, module, relObj)
            if not isRootSourceRel:
                reqLinkProps = getattr(relTypeObj, "requiredLinkProperties", None)
                if reqLinkProps:
                    relPropQNs = set(p.property for p in getattr(relObj, "properties", None) or ())
                    missingProps = reqLinkProps - relPropQNs
                    if missingProps:
                        emit_error(compMdl, "oimte:missingRequiredRelationshipProperty",
                                   _("The network %(name)s relationship[%(nbr)s] is missing required properties %(properties)s defined by relationship type %(relType)s."),
                                   xbrlObject=relObj, name=ntwkObj.name, nbr=i,
                                   properties=", ".join(str(p) for p in missingProps), relType=ntwkObj.relationshipTypeName)
            relObjPrefLbl = relObj.propertyObjectValue(qnPreferredLabel)
            if relObjPrefLbl is not None:
                validateQNameReference(compMdl, relObj, qnPreferredLabel, XbrlLabelType,
                                       invalidTypeMsgCode="oimte:invalidObjectType", qnRef=relObjPrefLbl)
            relKey = (relObj.source, relObj.target, relObjPrefLbl, relObj.order)
            ntwkCt[relKey] = ntwkCt.get(relKey, 0) + 1
        if any(ct > 1 for relKey, ct in ntwkCt.items()):
            emit_error(compMdl, "oimte:duplicateItemsInSet",
                       _("The network %(name)s has duplicated relationships %(names)s"),
                       xbrlObject=ntwkObj, name=ntwkObj.name,
                       names=", ".join(f"{relFrom}\u2192{relTo}{f' [{str(prefLbl)}]' if prefLbl else ''} ord {str(ordr)}"
                                       for (relFrom, relTo, prefLbl, ordr), ct in ntwkCt.items() if ct > 1))

        # Summation-item checks run after the loop above, because they read link property
        # values through propertyObjectValue, which returns the validated typed value that
        # validateProperties sets on each relationship inside that loop.
        if getattr(relTypeObj, "name", None) == qnXbrlSummationItem:
            _validateSummationItemNetwork(compMdl, ntwkObj)
        ntwkObj._rootsFound = sources - targets

        # Non-extending networks with relationships must have at least one xbrl:rootSource relationship.
        # Extending networks inherit the base's rootSource and are not required to add their own.
        if ntwkObj.extends is None and ntwkObj.relationships and not hasRootSourceRel:
            emit_error(compMdl, "oimte:missingRootSource",
                       _("The network %(name)s has relationships but no xbrl:rootSource relationship; every network with relationships MUST define at least one xbrl:rootSource relationship."),
                       xbrlObject=ntwkObj, name=ntwkObj.name)

        # Collect explicit roots from xbrl:rootSource relationships
        rootSourceTargets = OrderedSet(
            relObj.target for relObj in (ntwkObj.relationships or ())
            if getattr(relObj, "source", None) == qnXbrlRootSource
        )

        # Check for duplicate relationships introduced by extends (including rootSource ones).
        # Identical (source, target, order) triples are duplicates; different orders are not.
        if ntwkObj.extends and extendTargetObj is not None:
            for relObj in ntwkObj.relationships or ():
                relKey = (relObj.source, relObj.target, getattr(relObj, "order", None))
                if relKey in _baseRelKeys:
                    emit_error(compMdl, "oimte:duplicateItemsInSet",
                               _("The network %(name)s has duplicated relationship after extends merge: %(rel)s"),
                               xbrlObject=ntwkObj, name=ntwkObj.extends,
                               rel=f"{relObj.source}→{relObj.target}")

        # Cycle detection: self-loops are always invalid; directed cycles are
        # checked based on the relationship type's cycles property.
        _cyclesVal = getattr(relTypeObj, "cycles", None)
        cyclesProp = _cyclesVal.localName if isinstance(_cyclesVal, QName) else str(_cyclesVal) if _cyclesVal else "none"

        if rootSourceTargets:
            undeclaredRoots = ntwkObj._rootsFound - rootSourceTargets
            if undeclaredRoots:
                emit_error(compMdl, "oimte:invalidNetworkRoot",
                           _("The network %(name)s has undeclared relationship roots not covered by rootSource relationships: %(undeclaredRoots)s"),
                           xbrlObject=ntwkObj, name=ntwkObj.name,
                           undeclaredRoots=", ".join(sorted(str(r) for r in undeclaredRoots)))
            # A declared root appearing as a target means it's in a cycle.
            # This is only an error if the relationship type does not permit cycles.
            if cyclesProp != "any":
                rootsAsTargets = rootSourceTargets & targets
                if rootsAsTargets:
                    emit_error(compMdl, "oimte:networkCyclic",
                               _("The network %(name)s has root(s) %(roots)s appearing as relationship targets."),
                               xbrlObject=ntwkObj, name=ntwkObj.name,
                               roots=", ".join(sorted(str(r) for r in rootsAsTargets)))

        hasSelfLoop = False
        for relObj in ntwkObj.relationships or ():
            if relObj.source == qnXbrlRootSource:
                continue  # virtual origin; not subject to cycle detection
            if relObj.source == relObj.target:
                emit_error(compMdl, "oimte:networkCyclic",
                           _("The network %(name)s has a self-loop: %(node)s → %(node)s."),
                           xbrlObject=ntwkObj, name=ntwkObj.name, node=relObj.source)
                hasSelfLoop = True
        if not hasSelfLoop and cyclesProp != "any" and sources:
            graph = defaultdict(set)
            for relObj in ntwkObj.relationships or ():
                if relObj.source == qnXbrlRootSource:
                    continue
                graph[relObj.source].add(relObj.target)
            visited = set()
            inStack = set()
            def _hasCycle(node):
                if node in inStack:
                    return True
                if node in visited:
                    return False
                visited.add(node)
                inStack.add(node)
                for child in graph.get(node, ()):
                    if _hasCycle(child):
                        return True
                inStack.discard(node)
                return False
            for root in (sources - targets) or sources:
                if _hasCycle(root):
                    emit_error(compMdl, "oimte:networkCyclic",
                               _("The network %(name)s contains a directed cycle."),
                               xbrlObject=ntwkObj, name=ntwkObj.name)
                    break

        validateProperties(compMdl, oimFile, module, ntwkObj)

    # PropertyType Objects
    for i, propTpObj in enumerate(module.propertyTypes or ()):
        assertObjectType(compMdl, propTpObj, XbrlPropertyType)
        dataTypeObj = validateQNameReference(compMdl, propTpObj, "dataType", (XbrlDataType, XbrlCollectionType))
        if not dataTypeObj:
            continue
        if dataTypeObj and propTpObj.enumerationDomain:
            if dataTypeObj.xsBaseType(compMdl) != "QName":
                emit_error(compMdl, "oimte:invalidQNameReference",
                           _("The propertyType %(name)s dataType %(qname)s MUST be a valid dataType object in the taxonomy model"),
                           xbrlObject=propTpObj, name=propTpObj.name, qname=propTpObj.dataType)
            validateQNameReference(compMdl, propTpObj, "enumerationDomain", XbrlDomainNetwork)
        for allowedObjQn in (propTpObj.allowedObjects or ()):
            if not _is_allowed_property_object_qname(allowedObjQn):
                emit_error(compMdl, "oimte:invalidAllowedObject",
                           _("The property %(name)s has an invalid allowed object %(allowedObj)s"),
                           xbrlObject=propTpObj, name=propTpObj.name, allowedObj=allowedObjQn)

    # RelationshipType Objects
    for relTpObj in module.relationshipTypes or ():
        assertObjectType(compMdl, relTpObj, XbrlRelationshipType)
        for prop in ("allowedLinkProperties", "requiredLinkProperties"):
            for propTpQn in (getattr(relTpObj, prop, None) or ()):
                validateQNameReference(compMdl, relTpObj, prop, XbrlPropertyType, qnRef=propTpQn)
        if getattr(relTpObj, "allowedLinkProperties", None):
            reqdNotAllowed = (getattr(relTpObj, "requiredLinkProperties", None) or set()) - relTpObj.allowedLinkProperties
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
    for ntwkObj in module.networks or ():
        if ntwkObj.relationshipTypeName != qnXbrlClassSubclass:
            continue
        for rel in ntwkObj.relationships or ():
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
        # Compare named properties. Only *definitional* properties are inherited by a subclass and
        # therefore subject to the conflict rule (oim-taxonomy §property-inheritance / §4113-4122); a
        # non-definitional property may be overridden with a different value on the subclass.
        for pq, subVal in subPropMap.items():
            propTpObj = compMdl.namedObjects.get(pq)
            if not (isinstance(propTpObj, XbrlPropertyType) and getattr(propTpObj, "definitional", False)):
                continue
            anc = ancestorPropDefs.get(pq)
            if anc is not None and subVal != anc[1]:
                emit_error(compMdl, "oimte:conflictingPropertyValues",
                           _("Concept %(name)s property %(prop)s value %(subVal)r conflicts with inherited value %(ancVal)r from class %(ancName)s."),
                           xbrlObject=subObj, name=subObj.name, prop=pq,
                           subVal=subVal, ancVal=anc[1], ancName=anc[0].name)
