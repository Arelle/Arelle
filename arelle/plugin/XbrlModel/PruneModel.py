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


# Relationship-bearing collections walked for REPORT-mode network inclusion (decision 4a).
_NETWORK_COLLECTIONS = ("networks", "domainNetworks", "groups", "cubes", "groupContents")


def pruneClosure(txmyMdl, includeNetworks=False):
    """ Build the fact-reachability closure: the set of object QNames a consumer needs to
        interpret the reported facts. Seeded from each fact's factDimensions / factQualifier
        (dimensions + their concept/member/unit values) and factValue transforms, then expanded
        transitively over datatype, domain-class and unit-datatype references to a fixpoint.

        includeNetworks (REPORT mode, decision 4a): additionally retain any presentation /
        definition network (network, domainNetwork, group, groupContent) whose relationships touch
        a retained object, pulling in ALL that network's relationship endpoints (concepts, members,
        headings) so the network is complete and self-consistent (no dangling references). Cubes are
        handled separately (cubeTouches / retainCube): a cube carries no flat relationships list, so
        it is retained iff its concept dimension's domain lists a retained (reported) concept -- or,
        for an open concept dimension, any of its explicit dimensions / domain networks / cube
        networks is retained -- and retaining it pulls in its cube dimensions, their domain networks
        and its cube networks (whose endpoints the network loop then follows to a fixpoint).
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

    def drain():
        # transitive expansion over object references to a fixpoint
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
    drain()

    # ---- REPORT: include networks touching retained objects (+ their full endpoint set) ----
    if includeNetworks:
        networkObjs = [net for module in txmyMdl.xbrlModels.values()
                       for coll in _NETWORK_COLLECTIONS
                       for net in getattr(module, coll, None) or ()]
        cubeObjs = [cube for module in txmyMdl.xbrlModels.values()
                    for cube in getattr(module, "cubes", None) or ()]

        def cubeTouches(cube):
            # A cube is relevant to the reported facts iff its concept dimension's domain lists a
            # retained (reported) concept -- or, when its concept dimension is open (no domainNetwork),
            # any of its explicit dimensions / domainNetworks / cubeNetworks is already retained. Cubes
            # carry no flat `relationships` list, so the relationship-based test above cannot see them.
            hasConceptDomain = False
            for cd in getattr(cube, "cubeDimensions", None) or ():
                dn = getattr(cd, "domainNetwork", None)
                if getattr(cd, "dimension", None) == qname("xbrl:concept", pfxns) and dn is not None:
                    hasConceptDomain = True
                    dnObj = named.get(dn)
                    for rel in getattr(dnObj, "relationships", None) or ():
                        if getattr(rel, "source", None) in retained or getattr(rel, "target", None) in retained:
                            return True
                elif dn is not None and dn in retained:
                    return True
            if not hasConceptDomain: # open concept dimension -- fall back to any retained reference
                for cn in getattr(cube, "cubeNetworks", None) or ():
                    if cn in retained:
                        return True
            return False

        def retainCube(cube):
            # Pull the cube and everything a consumer needs to render it: its name, each cube
            # dimension + its domain network, and any directly-related networks. The domain/network
            # endpoints (members, concepts) are pulled by the relationship loop below on the next
            # iteration once the network name is retained.
            add(getattr(cube, "name", None))
            for cd in getattr(cube, "cubeDimensions", None) or ():
                add(getattr(cd, "dimension", None))
                add(getattr(cd, "domainNetwork", None))
            for cn in getattr(cube, "cubeNetworks", None) or ():
                add(cn)
            drain()

        changed = True
        while changed:
            changed = False
            for net in networkObjs:
                netName = getattr(net, "name", None)
                if netName is not None and netName in retained:
                    continue
                endpoints = set()
                touches = False
                for rel in getattr(net, "relationships", None) or ():
                    src = getattr(rel, "source", None)
                    tgt = getattr(rel, "target", None)
                    if src is not None:
                        endpoints.add(src)
                    if tgt is not None:
                        endpoints.add(tgt)
                    if src in retained or tgt in retained:
                        touches = True
                if touches:
                    if netName is not None:
                        add(netName)
                    for endpoint in endpoints:
                        add(endpoint)
                    drain()
                    changed = True
            for cube in cubeObjs:
                cubeName = getattr(cube, "name", None)
                if cubeName is not None and cubeName in retained:
                    continue
                if cubeTouches(cube):
                    retainCube(cube)
                    changed = True
    return retained


def pruneSkip(obj, retained, reportMode=False):
    """ Return True if a serialized module-collection object should be dropped for the current
        prune closure. retained is None for FULL mode (never drops). In REPORT mode the
        presentation/structure classes are retained by closure membership (networks included via
        pruneClosure) rather than dropped outright. Facts/footnotes and the always-keep
        type-definition collections fall through to False.
    """
    if retained is None:
        return False
    cls = type(obj).__name__
    if cls in _DROP_CLASSES:
        if reportMode: # networks/groups/headings kept iff in the (network-expanded) closure
            return getattr(obj, "name", None) not in retained
        return True
    if cls in _CLOSURE_CLASSES:
        return getattr(obj, "name", None) not in retained
    if cls in _FOROBJECT_CLASSES:
        forObject = getattr(obj, "forObject", None)
        if forObject is not None:
            return forObject not in retained
        return not any(fo in retained for fo in getattr(obj, "forObjects", None) or ())
    return False
