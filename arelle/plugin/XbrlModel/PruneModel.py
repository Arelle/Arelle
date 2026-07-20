'''
See COPYRIGHT.md for copyright information.

Reachability pruning for SaveModel (PRUNE / REPORT save modes).

A serialized compiled model may legitimately be a *partial* model: only the taxonomy
objects required to interpret the reported facts (their concepts, dimensions, members,
units and the datatype closure of those), plus the labels/references attached to the
retained objects. See oim-taxonomy/documentation/COMPILED_MODEL_SERIALIZATION_SCOPE.md
for why (fact-set export, licensing of copyrighted base taxonomies such as US-GAAP/IFRS).

`pruneClosure(model)` returns the set of retained object QNames (the fact-reachability
closure). `pruneSkip(obj, retained)` classifies a single serialized object as keep/drop so
SaveModel's serializer can filter module object collections. When `retained is None`
(FULL mode) nothing is pruned.
'''
from arelle.ModelValue import qname, QName

# Object classes filtered by fact-reachability closure membership (kept iff name in closure).
_CLOSURE_CLASSES = frozenset({
    "XbrlConcept", "XbrlMember", "XbrlDimension", "XbrlUnit",
    "XbrlDataType", "XbrlTransform", "XbrlDomainClass"})

# Tag objects kept iff their target object (forObject / forObjects) is in the closure.
_FOROBJECT_CLASSES = frozenset({"XbrlLabel", "XbrlReference"})

# Presentation / structure objects dropped in a partial model: they organise or lay out the
# taxonomy but are not needed to interpret a self-describing fact (which carries its full
# factDimensions). Networks touching retained concepts are re-added by REPORT mode (decision 4a).
_DROP_CLASSES = frozenset({
    "XbrlDomainNetwork", "XbrlNetwork", "XbrlCube", "XbrlGroup",
    "XbrlGroupContent", "XbrlGroupTree", "XbrlHeading"})

# Everything else (facts, footnotes, factMaps/factSources/factLocatorTypes, and the small
# type-definition collections: collectionTypes, cubeTypes, modelTypes, propertyTypes,
# relationshipTypes, labelTypes, referenceTypes, entities, ...) is always kept.


def pruneClosure(txmyMdl):
    """ Build the fact-reachability closure: the set of object QNames a consumer needs to
        interpret the reported facts. Seeded from each fact's factDimensions / factQualifier
        (dimensions + their concept/member/unit values) and factValue transforms, then expanded
        transitively over datatype, domain-class and unit-datatype references to a fixpoint.
    """
    named = txmyMdl.namedObjects
    pfxns = txmyMdl.prefixedNamespaces
    retained = set()
    frontier = []

    def add(qn):
        if isinstance(qn, str):
            qn = qname(qn, pfxns)
        if isinstance(qn, QName) and qn not in retained:
            retained.add(qn)
            frontier.append(qn)

    # ---- seed from the reported facts ----
    for module in txmyMdl.xbrlModels.values():
        for fact in getattr(module, "facts", None) or ():
            for dims in (fact.factDimensions, getattr(fact, "factQualifier", None)):
                for dimKey, dimVal in (dims or {}).items():
                    add(dimKey) # the dimension object (core or explicit)
                    if isinstance(dimVal, str):
                        vq = qname(dimVal, pfxns)
                        if isinstance(vq, QName) and vq in named:
                            add(vq) # concept / member / unit value
                    elif isinstance(dimVal, QName) and dimVal in named:
                        add(dimVal)
            for factValue in getattr(fact, "factValues", None) or ():
                add(getattr(factValue, "transformation", None))

    # ---- transitive expansion to a fixpoint ----
    while frontier:
        obj = named.get(frontier.pop())
        if obj is None:
            continue
        cls = type(obj).__name__
        if cls == "XbrlConcept":
            add(obj.dataType)
        elif cls == "XbrlDataType":
            add(getattr(obj, "baseType", None))
        elif cls == "XbrlDimension":
            add(getattr(obj, "domainClass", None))
            for ct in getattr(obj, "cubeTypes", None) or ():
                add(ct)
        elif cls == "XbrlMember":
            for dc in getattr(obj, "domainClasses", None) or ():
                add(dc)
        elif cls == "XbrlDomainClass":
            add(getattr(obj, "allowedDomainItem", None))
        elif cls == "XbrlUnit":
            add(getattr(obj, "dataType", None))
    return retained


def pruneSkip(obj, retained):
    """ Return True if a serialized module-collection object should be dropped for the current
        prune closure. retained is None for FULL mode (never drops). Facts/footnotes and the
        always-keep type-definition collections fall through to False.
    """
    if retained is None:
        return False
    cls = type(obj).__name__
    if cls in _DROP_CLASSES:
        return True
    if cls in _CLOSURE_CLASSES:
        return getattr(obj, "name", None) not in retained
    if cls in _FOROBJECT_CLASSES:
        forObject = getattr(obj, "forObject", None)
        if forObject is not None:
            return forObject not in retained
        return not any(fo in retained for fo in getattr(obj, "forObjects", None) or ())
    return False
