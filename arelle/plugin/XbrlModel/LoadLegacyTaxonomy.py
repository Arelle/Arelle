"""
See COPYRIGHT.md for copyright information.

Legacy (XML schema + linkbase) taxonomy loader.

Dynamically transforms a legacy XBRL 2.1 DTS -- already discovered and resolved by
Arelle's ModelXbrl / relationship engine -- into an in-memory OIM Taxonomy *module
dict* of the same shape a xBRL-JSON taxonomy would have, then hands that dict to the
existing ``loadXbrlModule`` hydrator (``createModelObjects``). Construction, QName
binding, the initDefaults present/absent contract, ``namedObjects`` registration and
all downstream validation are therefore reused unchanged -- this module only performs
the *inference* (groups / cubes / domains) that a legacy taxonomy leaves implicit.

This is the same transform the abandoned ``converted-taxonomies`` pre-compilation would
have performed, but done transiently at load time and never persisted -- so it does not
publish a derivative of a licensed source taxonomy (e.g. US-GAAP / IFRS).

Two inference sources, in preference order per linkrole:
  * the definition linkbase (xbrldt dimensional arcs) when present;
  * otherwise the presentation linkbase (parent-child), classifying nodes by their
    *schema-level* nature (concept.isDimensionItem / isDomainMember). This is the common
    SEC case, where dimension / member concepts exist in the schema but are wired into no
    dimensional relationships -- only the presentation tree gives their containment.

The output is fed to ``loadXbrlModule(cntlr, error, warning, None, moduleDict, url)``.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, Optional

from arelle import XbrlConst

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelValue import QName
    from arelle.ModelDtsObject import ModelConcept

# OIM namespaces that every emitted module needs bound (documentInfo.namespaces).
_OIM_NAMESPACES = {
    "xbrl":  "https://xbrl.org/2026",
    "xbrlm": "https://xbrl.org/2026/model",
    "xbrlr": "https://xbrl.org/2026/report",
    "xbrla": "http://xbrl.org/accounting",
    "xs":    "http://www.w3.org/2001/XMLSchema",
}
# A fully-resolved legacy DTS is the import *closure*, so it is emitted as a compiled
# model (not a single-namespace module): documentType compiled is permitted to own
# objects across multiple namespaces (dei:, us-gaap:, the company namespace, ...), which
# is exactly what a legacy DTS is. The loader auto-sets modelForm="compiled".
_MODULE_DOCTYPE = "https://xbrl.org/2026/compiled"

# Reserved OIM aliases -- never re-bind these to a legacy URI when seeding prefixes from
# the DTS (would trip oimce:invalidURIForReservedAlias / multipleURIsForAlias).
_RESERVED_ALIASES = {"xbrl", "xbrli", "xbrlm", "xbrlr", "xs", "ref", "utr", "iso4217",
                     "oimce", "oime", "oimte", "dtr-type", "xbrltt", "link", "xlink"}

# XBRL 2.1 item types -> OIM datatype, per the oim-taxonomy-conversion.md mapping table.
# Keyed by the item-type local name (ModelConcept/ModelType.baseXbrliType returns these).
_ITEM_TYPE_MAP = {
    "anyURIItemType": "xs:anyURI", "base64BinaryItemType": "xs:base64Binary",
    "booleanItemType": "xs:boolean", "byteItemType": "xs:byte",
    "dateItemType": "xs:date", "dateTimeItemType": "xs:dateTime",
    "decimalItemType": "xs:decimal", "doubleItemType": "xs:double",
    "durationItemType": "xs:duration", "floatItemType": "xs:float",
    "gDayItemType": "xs:gDay", "gMonthDayItemType": "xs:gMonthDay",
    "gMonthItemType": "xs:gMonth", "gYearItemType": "xs:gYear",
    "gYearMonthItemType": "xs:gYearMonth", "hexBinaryItemType": "xs:hexBinary",
    "intItemType": "xs:int", "integerItemType": "xs:integer",
    "languageItemType": "xs:language", "longItemType": "xs:long",
    "monetaryItemType": "xbrlr:monetary", "NameItemType": "xs:Name",
    "NCNameItemType": "xs:NCName", "negativeIntegerItemType": "xs:negativeInteger",
    "nonNegativeIntegerItemType": "xs:nonNegativeInteger",
    "nonPositiveIntegerItemType": "xs:nonPositiveInteger",
    "normalizedStringItemType": "xs:normalizedString",
    "positiveIntegerItemType": "xs:positiveInteger", "pureItemType": "xbrlr:pureType",
    "QNameItemType": "xs:QName", "sharesItemType": "xbrla:sharesType",
    "perShareItemType": "xbrla:MonetaryPerShare",
    "shortItemType": "xs:short", "stringItemType": "xs:string",
    "timeItemType": "xs:time", "tokenItemType": "xs:token",
    "unsignedByteItemType": "xs:unsignedByte", "unsignedIntItemType": "xs:unsignedInt",
    "unsignedLongItemType": "xs:unsignedLong", "unsignedShortItemType": "xs:unsignedShort",
}

# Namespaces whose types are standard (folded to a base type, never emitted as objects).
_STD_TYPE_NS = {"http://www.xbrl.org/2003/instance", "http://www.w3.org/2001/XMLSchema"}


class _NsPrefixer:
    """Serialise QNames as ``prefix:local`` strings whose prefixes are all bound in the
    emitted module's documentInfo.namespaces, minting synthetic prefixes as needed."""
    def __init__(self, modelXbrl):
        self.nsToPrefix = {}
        self.namespaces = dict(_OIM_NAMESPACES)
        for p, ns in _OIM_NAMESPACES.items():
            self.nsToPrefix.setdefault(ns, p)
        # seed from the DTS's own prefix bindings, skipping reserved OIM aliases so a
        # legacy URI never collides with a reserved one (oimce:invalidURIForReservedAlias).
        for p, ns in (getattr(modelXbrl, "prefixedNamespaces", None) or {}).items():
            if ns and p and p not in _RESERVED_ALIASES and ns not in self.nsToPrefix:
                self.nsToPrefix[ns] = p
                self.namespaces.setdefault(p, ns)
        self._synth = 0

    def prefixFor(self, ns: str) -> str:
        p = self.nsToPrefix.get(ns)
        if p is None:
            while f"ns{self._synth}" in self.namespaces:
                self._synth += 1
            p = f"ns{self._synth}"
            self.nsToPrefix[ns] = p
            self.namespaces[p] = ns
        return p

    def pn(self, qn) -> str:
        return f"{self.prefixFor(qn.namespaceURI)}:{qn.localName}"


def _baseTypeFor(obj) -> str:
    """The OIM base datatype for a concept or ModelType: its XBRL 2.1 item-type mapped via
    the canonical table, else its xsd base (xs:...), else xs:string."""
    base = getattr(obj, "baseXbrliType", None)
    if base in _ITEM_TYPE_MAP:
        return _ITEM_TYPE_MAP[base]
    bx = getattr(obj, "baseXsdType", None)
    if bx:
        return f"xs:{bx}"
    return "xs:string"


def _conceptDataType(concept, pfx: _NsPrefixer, emit) -> str:
    """OIM datatype QName for a concept. Standard (xsd/xbrli) types fold to a base type;
    a custom (taxonomy-defined) type is referenced by its own QName and emitted as an
    XbrlDataType object (baseType + enumeration), so facts keep their real type."""
    tq = getattr(concept, "typeQname", None)
    if tq is None:
        return "xs:string"
    if tq.namespaceURI in _STD_TYPE_NS or tq.namespaceURI in _OIM_NAMESPACES.values():
        return _baseTypeFor(concept)
    # Data Type Registry (dtr-types) types whose localName is a canonical XBRL item type
    # fold to their OIM equivalent (e.g. dtr-types:perShareItemType -> xbrla:MonetaryPerShare),
    # so the concept carries the proper unitType / ratio semantics instead of being emitted
    # as an opaque custom type. baseXbrliType is often None for these registry types, so the
    # fold keys on the type's own localName.
    if tq.localName in _ITEM_TYPE_MAP:
        return _ITEM_TYPE_MAP[tq.localName]
    modelType = getattr(concept, "type", None)
    if modelType is None:
        return _baseTypeFor(concept)
    name = pfx.pn(tq)
    emit.dataType(name, lambda: _dataTypeObject(name, modelType))
    return name


def _dataTypeObject(name: str, modelType) -> dict:
    """An XbrlDataType object for a custom type: name, baseType (flattened to a standard
    base), and an enumeration facet when the type restricts one."""
    obj = {"name": name, "baseType": _baseTypeFor(modelType)}
    facets = getattr(modelType, "facets", None) or {}
    enum = facets.get("enumeration")
    if enum:
        obj["enumeration"] = list(enum.keys()) if isinstance(enum, dict) else list(enum)
    return obj


def _typedDataType(axis, pfx: _NsPrefixer, emit) -> str:
    """The OIM datatype of a typed dimension: the mapped data type of its typed-domain
    element (xbrldt:typedDomainRef target), defaulting to xs:string."""
    tde = getattr(axis, "typedDomainElement", None)
    if tde is not None:
        return _conceptDataType(tde, pfx, emit)
    return "xs:string"


def _classify(concept) -> str:
    """'dimension' | 'member' | 'hypercube' | 'concept' from schema-level nature."""
    if getattr(concept, "isDimensionItem", False):
        return "dimension"
    if getattr(concept, "isHypercubeItem", False):
        return "hypercube"
    if getattr(concept, "isDomainMember", False) and getattr(concept, "isAbstract", False):
        # a domain-member-typed abstract concept is a member/domain, not a line item
        return "member"
    return "concept"


class _Emit:
    """Shared view over the object collections, so inference helpers can (re)classify a
    concept as member vs. domainClass and link a dimension to its discovered domain root
    without every collection being threaded through every call."""
    def __init__(self, concepts, dimensions, members, domainClasses, dataTypes):
        self.concepts, self.dimensions = concepts, dimensions
        self.members, self.domainClasses, self.dataTypes = members, domainClasses, dataTypes

    def dataType(self, name, factory):
        if name not in self.dataTypes:
            self.dataTypes[name] = factory()

    def member(self, name):
        if name not in self.domainClasses:
            self.members.setdefault(name, {"name": name})

    def domainClass(self, name):
        self.members.pop(name, None)
        self.concepts.pop(name, None)
        self.domainClasses.setdefault(name, {"name": name, "allowedDomainItem": "xbrl:memberObject"})

    def domainClassTyped(self, name, allowedDataType):
        # a typed dimension's domain class allows a data type rather than members; its
        # allowedDomainItem MUST equal (or be a supertype of) the cube's domainDataType.
        self.members.pop(name, None)
        self.concepts.pop(name, None)
        self.domainClasses[name] = {"name": name, "allowedDomainItem": allowedDataType}

    def setDimensionDomain(self, dimName, domName):
        dim = self.dimensions.get(dimName)
        if dim is not None and domName:
            dim["domainClass"] = domName

    def emitted(self):
        return set(self.concepts) | set(self.dimensions) | set(self.members) | set(self.domainClasses)


def legacyTaxonomyToOimModule(modelXbrl, moduleName: Optional[str] = None,
                              inlineBase: bool = True) -> OrderedDict:
    """Transform a loaded legacy DTS ``modelXbrl`` into an OIM Taxonomy module dict.

    ``inlineBase`` folds the base spec closure (xs:/xbrl:/xbrlr: objects and their
    labels) into the compiled model so it is standalone-valid. Set False when the
    model will be *imported* into a host that already provides those base objects
    (e.g. via xbrlm:base) -- inlining them there duplicates the base labels."""
    pfx = _NsPrefixer(modelXbrl)

    concepts: dict[str, dict] = {}
    dimensions: dict[str, dict] = {}
    domainClasses: dict[str, dict] = {}
    members: dict[str, dict] = {}
    dataTypes: dict[str, dict] = {}
    domainNetworks: list[dict] = []
    cubes: list[dict] = []
    groups: list[dict] = []
    groupContents: list[dict] = []
    networks: list[dict] = []
    labels: list[dict] = []
    emit = _Emit(concepts, dimensions, members, domainClasses, dataTypes)

    # domain roots = dimension-domain targets: these MUST be emitted as domainClass
    # objects (a dimension's domainClass and its domain network's root reference them),
    # not as plain members.
    domainRootQNs = {r.toModelObject.qname
                     for r in modelXbrl.relationshipSet(XbrlConst.dimensionDomain).modelRelationships
                     if r.toModelObject is not None}

    # ---- 1. concepts / dimensions / members from the SCHEMA ----
    # A dimension's domainClass is deferred: it is set to the actual domain root discovered
    # in the definition/presentation linkbase (below), with a synthetic fallback afterward.
    for qn, concept in modelXbrl.qnameConcepts.items():
        if qn is None or not getattr(concept, "isItem", False):
            continue
        if concept.qname.namespaceURI in _OIM_NAMESPACES.values():
            continue  # don't re-declare xbrli/xbrl built-ins
        name = pfx.pn(concept.qname)
        kind = _classify(concept)
        lbl = concept.label(fallbackToQname=False) if hasattr(concept, "label") else None
        if concept.qname in domainRootQNs:
            domainClasses[name] = {"name": name, "allowedDomainItem": "xbrl:memberObject"}
        elif kind == "dimension":
            dimensions[name] = {"name": name}  # domainClass filled in below
        elif kind == "member":
            members[name] = {"name": name}
        elif kind == "hypercube":
            continue  # hypercubes become cubes via linkroles, not standalone objects
        else:
            concepts[name] = {"name": name,
                              "dataType": _conceptDataType(concept, pfx, emit),
                              "periodType": getattr(concept, "periodType", None) or "duration"}
        if lbl:
            labels.append({"forObject": name, "language": "en",
                           "value": lbl, "labelType": "xbrl:label"})

    # ---- 2. one group + cube + network per linkrole ----
    # A linkrole is inferred from its DEFINITION (xbrldt) arcs when it declares a
    # hasHypercube; otherwise it falls back to the PRESENTATION tree (the common SEC case
    # with no definition linkbase). dimension-default is typically defined once, globally.
    presAll = modelXbrl.relationshipSet(XbrlConst.parentChild)
    hasHcRoles = set(modelXbrl.relationshipSet(XbrlConst.all).linkRoleUris) | \
                 set(modelXbrl.relationshipSet(XbrlConst.notAll).linkRoleUris)
    dimDefault: dict[str, str] = {}
    for r in modelXbrl.relationshipSet(XbrlConst.dimensionDefault).modelRelationships:
        if r.fromModelObject is not None and r.toModelObject is not None:
            dimDefault[pfx.pn(r.fromModelObject.qname)] = pfx.pn(r.toModelObject.qname)

    for roleUri in sorted(set(presAll.linkRoleUris) | hasHcRoles):
        grpLocal = _safeLocal(roleUri)
        grpName = pfx.prefixFor(_documentNs(modelXbrl)) + ":group_" + grpLocal
        groups.append({"name": grpName, "groupURI": roleUri})

        cubeName = grpName + "_Cube"
        primaryItems: list[str] = []
        axisDims: list[dict] = []
        if roleUri in hasHcRoles:  # definition-linkbase (dimensional) inference
            _inferCubeFromDefinition(modelXbrl, roleUri, pfx, domainNetworks, emit,
                                     cubeName, dimDefault, primaryItems, axisDims)
        else:                      # presentation-linkbase fallback
            presRel = modelXbrl.relationshipSet(XbrlConst.parentChild, roleUri)
            for root in presRel.rootConcepts:
                _walk(root, presRel, None, pfx, primaryItems, axisDims, domainNetworks,
                      emit, cubeName, seen=set())

        # concept core dimension: the line items become its domain
        cubeDims: list[dict] = []
        if primaryItems:
            conceptDomName = cubeName + "_ConceptDom"
            domainNetworks.append({"name": conceptDomName, "root": "xbrl:conceptDomain",
                                   "relationships": [{"source": "xbrl:conceptDomain", "target": c}
                                                     for c in primaryItems]})
            cubeDims.append({"dimension": "xbrl:concept", "domainNetwork": conceptDomName})
        else:
            cubeDims.append({"dimension": "xbrl:concept"})
        cubeDims.extend(axisDims)
        for coreDim in ("xbrl:period", "xbrl:entity", "xbrl:unit"):
            cubeDims.append({"dimension": coreDim, "optional": True})
        cubes.append({"name": cubeName, "cubeType": "xbrl:reportCube", "cubeDimensions": cubeDims})

        # capture the presentation network (if any): filter to modeled objects (drops arcs
        # to/from hypercubes, which are not emitted as objects), then mark the filtered
        # graph's roots (sources that are never targets) via the xbrl:rootSource origin.
        presRel = modelXbrl.relationshipSet(XbrlConst.parentChild, roleUri)
        emitted = emit.emitted()
        frels, srcs, tgts = [], set(), set()
        for r in presRel.modelRelationships:
            if r.fromModelObject is None or r.toModelObject is None:
                continue
            s, t = pfx.pn(r.fromModelObject.qname), pfx.pn(r.toModelObject.qname)
            if s in emitted and t in emitted:
                frels.append({"source": s, "target": t, "order": r.order})
                srcs.add(s); tgts.add(t)
        if frels:
            netName = grpName + "_PreNet"
            rels = [{"source": "xbrl:rootSource", "target": n} for n in srcs if n not in tgts]
            rels += frels
            networks.append({"name": netName, "relationshipTypeName": "xbrl:parent-child",
                             "relationships": rels})
            groupContents.append({"groupName": grpName, "forObject": netName})
        groupContents.append({"groupName": grpName, "forObject": cubeName})

    # dimensions with no domain discovered in any linkbase get a synthetic domainClass.
    for name, dim in dimensions.items():
        if "domainClass" not in dim:
            synth = name + "DomainClass"
            dim["domainClass"] = synth
            domainClasses.setdefault(synth, {"name": synth, "allowedDomainItem": "xbrl:memberObject"})

    # ---- 3. assemble the module ----
    # A compiled model owns the full closure across namespaces: it MUST NOT declare a
    # documentNamespacePrefix or importedTaxonomies (the base spec objects are assembled
    # into the same model, not imported).
    oim = OrderedDict()
    oim["documentInfo"] = {"documentType": _MODULE_DOCTYPE,
                           "namespaces": pfx.namespaces}
    m = oim["xbrlModel"] = OrderedDict()
    m["name"] = moduleName or (pfx.prefixFor(_documentNs(modelXbrl)) + ":legacyModule")
    if concepts:      m["concepts"] = list(concepts.values())
    if dataTypes:     m["dataTypes"] = list(dataTypes.values())
    if dimensions:    m["dimensions"] = list(dimensions.values())
    if domainClasses: m["domainClasses"] = list(domainClasses.values())
    if members:       m["members"] = list(members.values())
    if domainNetworks: m["domainNetworks"] = domainNetworks
    if cubes:         m["cubes"] = cubes
    if groups:        m["groups"] = groups
    if groupContents: m["groupContents"] = groupContents
    if networks:      m["networks"] = networks
    if labels:        m["labels"] = labels
    if inlineBase:
        _inlineBaseSpecObjects(oim)
    return oim


# Base spec resource modules whose objects a compiled model must contain (rather than
# import). Mirrors the import closure of xbrlm:base -- the "similar import" a compiled
# conformance example (CompiledApple.json) inlines. Order is not significant; objects are
# merged by their key (name / forObject) so re-declares are idempotent.
_BASE_SPEC_RESOURCES = ("xs-types.json", "xbrlSpec.json", "xbrlModel.json",
                        "types.json", "xbrla.json", "ref.json", "utr.json", "iso4217.json")

# Module-assembly keys that must not be folded from a base resource module into the
# compiled model (a compiled model MUST NOT carry importedTaxonomies / importMapping).
_MERGE_SKIP_KEYS = frozenset({"importedTaxonomies", "importMapping"})


def _inlineBaseSpecObjects(oim: OrderedDict) -> None:
    """Fold the base spec resource modules' objects and namespaces into the compiled
    model, so xs:/xbrlr:/xbrl: datatypes and base objects (xbrl:conceptDomain,
    xbrl:parent-child, xbrl:reportCube, ...) resolve without an import."""
    import os, json
    m = oim["xbrlModel"]
    namespaces = oim["documentInfo"]["namespaces"]
    resourcesDir = os.path.join(os.path.dirname(__file__), "resources")
    seenKeys: dict[str, set] = {}
    for fname in _BASE_SPEC_RESOURCES:
        path = os.path.join(resourcesDir, fname)
        try:
            with open(path) as fh:
                base = json.load(fh)
        except (OSError, ValueError):
            continue
        for p, ns in (base.get("documentInfo", {}).get("namespaces", {}) or {}).items():
            namespaces.setdefault(p, ns)
        for key, val in (base.get("xbrlModel", {}) or {}).items():
            if not isinstance(val, list) or key in _MERGE_SKIP_KEYS:
                continue
            target = m.setdefault(key, [])
            if not isinstance(target, list):
                continue
            keyset = seenKeys.setdefault(key, {_objKey(o) for o in target})
            for obj in val:
                k = _objKey(obj)
                if k is None or k not in keyset:
                    target.append(obj)
                    if k is not None:
                        keyset.add(k)


def _objKey(obj):
    """Dedup key for a merged object: its name (referencable) or forObject (tag)."""
    if not isinstance(obj, dict):
        return None
    return obj.get("name") or obj.get("forObject")


def _walk(concept, presRel, parentAxis, pfx, primaryItems, axisDims, domainNetworks,
          emit, cubeName, seen) -> None:
    """Preorder walk of a presentation subtree, classifying nodes into the cube."""
    if concept in seen:
        return
    seen.add(concept)
    isAxis = getattr(concept, "isDimensionItem", False)
    if isAxis:
        axisName = pfx.pn(concept.qname)
        if getattr(concept, "isTypedDimension", False):
            typedDT = _typedDataType(concept, pfx, emit)
            domCls = axisName + "DomainClass"
            emit.setDimensionDomain(axisName, domCls)
            emit.domainClassTyped(domCls, typedDT)
            axisDims.append({"dimension": axisName, "domainDataType": typedDT, "optional": True})
            return
        memberQNs: list[str] = []
        domRoot = None
        for rel in presRel.fromModelObject(concept):
            child = rel.toModelObject
            if child is None:
                continue
            childName = pfx.pn(child.qname)
            if domRoot is None:
                domRoot = childName  # first child under the axis is the domain root
                emit.domainClass(domRoot)
            else:
                memberQNs.append(childName)
                emit.member(childName)
        if domRoot is None:  # axis with no children: open dimension, no domain network
            axisDims.append({"dimension": axisName, "optional": True})
            return
        emit.setDimensionDomain(axisName, domRoot)
        domNetName = f"{cubeName}_{concept.qname.localName}_Dom"
        dn = {"name": domNetName, "root": domRoot}
        if memberQNs:
            dn["relationships"] = [{"source": domRoot, "target": mQn} for mQn in memberQNs]
        domainNetworks.append(dn)
        axisDims.append({"dimension": axisName, "domainNetwork": domNetName, "optional": True})
        return  # members already consumed; don't descend further as line items
    # primary line item (non-abstract concept under no axis)
    if not getattr(concept, "isAbstract", False) and parentAxis is None:
        nm = pfx.pn(concept.qname)
        if nm not in primaryItems:
            primaryItems.append(nm)
    for rel in presRel.fromModelObject(concept):
        if rel.toModelObject is not None:
            _walk(rel.toModelObject, presRel, parentAxis, pfx, primaryItems, axisDims,
                  domainNetworks, emit, cubeName, seen)


def _inferCubeFromDefinition(modelXbrl, roleUri, pfx, domainNetworks, emit, cubeName,
                             dimDefault, primaryItems, axisDims) -> None:
    """Infer a cube from a linkrole's DEFINITION (xbrldt) arcs:

      primaryItem --all/notAll--> hypercube --hypercube-dimension--> axis
      axis --dimension-domain--> domain --domain-member*--> members

    Primary line items are the hasHypercube source and its domain-member descendants; each
    explicit axis contributes a cubeDimension backed by a domainNetwork of its members. A
    dimension carrying a dimension-default is emitted optional (undimensioned facts are
    included in the cube as the default member)."""
    hasHc = modelXbrl.relationshipSet(XbrlConst.all, roleUri)
    notAll = modelXbrl.relationshipSet(XbrlConst.notAll, roleUri)
    hcDimSet = modelXbrl.relationshipSet(XbrlConst.hypercubeDimension, roleUri)
    dimDomSet = modelXbrl.relationshipSet(XbrlConst.dimensionDomain, roleUri)
    domMemSet = modelXbrl.relationshipSet(XbrlConst.domainMember, roleUri)
    seenAxis = set()
    for hasRel in list(hasHc.modelRelationships) + list(notAll.modelRelationships):
        prim, hc = hasRel.fromModelObject, hasRel.toModelObject
        if prim is None or hc is None:
            continue
        for node in [prim] + _descend(domMemSet, prim):
            if not getattr(node, "isAbstract", False):
                nm = pfx.pn(node.qname)
                if nm not in primaryItems:
                    primaryItems.append(nm)
        for hd in hcDimSet.fromModelObject(hc):
            axis = hd.toModelObject
            if axis is None or axis in seenAxis:
                continue
            seenAxis.add(axis)
            axisName = pfx.pn(axis.qname)
            optional = axisName in dimDefault
            if getattr(axis, "isTypedDimension", False):
                typedDT = _typedDataType(axis, pfx, emit)
                domCls = axisName + "DomainClass"
                emit.setDimensionDomain(axisName, domCls)
                emit.domainClassTyped(domCls, typedDT)
                axisDims.append({"dimension": axisName, "domainDataType": typedDT, "optional": optional})
                continue
            domRoot = None
            edges: list[tuple] = []
            seenDom: set = set()
            for dd in dimDomSet.fromModelObject(axis):
                dom = dd.toModelObject
                if dom is None:
                    continue
                domName = pfx.pn(dom.qname)
                emit.domainClass(domName)
                if domRoot is None:
                    domRoot = domName
                _walkDomain(domMemSet, dom, pfx, emit, edges, seenDom)
            if domRoot is None:  # no dimension-domain: open dimension, no domain network
                axisDims.append({"dimension": axisName, "optional": optional})
                continue
            emit.setDimensionDomain(axisName, domRoot)
            domNetName = f"{cubeName}_{axis.qname.localName}_Dom"
            dn = {"name": domNetName, "root": domRoot}
            if edges:
                dn["relationships"] = [{"source": s, "target": t} for s, t in edges]
            domainNetworks.append(dn)
            axisDims.append({"dimension": axisName, "domainNetwork": domNetName, "optional": optional})


def _descend(relSet, node, seen=None) -> list:
    """All descendants of ``node`` in ``relSet`` (preorder, cycle-guarded)."""
    seen = seen if seen is not None else set()
    out = []
    for rel in sorted(relSet.fromModelObject(node), key=lambda r: r.order or 0):
        c = rel.toModelObject
        if c is not None and c not in seen:
            seen.add(c)
            out.append(c)
            out.extend(_descend(relSet, c, seen))
    return out


def _walkDomain(domMemSet, node, pfx, emit, edges, seen) -> None:
    """Collect parent->child domain-member edges (and register members) under ``node``."""
    for rel in sorted(domMemSet.fromModelObject(node), key=lambda r: r.order or 0):
        c = rel.toModelObject
        if c is None or c in seen:
            continue
        seen.add(c)
        cn = pfx.pn(c.qname)
        emit.member(cn)
        edges.append((pfx.pn(node.qname), cn))
        _walkDomain(domMemSet, c, pfx, emit, edges, seen)


def _documentNs(modelXbrl) -> str:
    """The target namespace of the entry schema, used for synthesised group/module names."""
    for doc in getattr(modelXbrl, "urlDocs", {}).values() if hasattr(modelXbrl, "urlDocs") else []:
        tns = getattr(doc, "targetNamespace", None)
        if tns:
            return tns
    md = getattr(modelXbrl, "modelDocument", None)
    return getattr(md, "targetNamespace", None) or "http://example.com/legacy"


def _safeLocal(uri: str) -> str:
    import re
    return re.sub(r"\W+", "_", uri.rpartition("/")[2] or uri)[:60]


# ============================================================================
# ==== PROOF OF CONCEPT: legacy XBRL 2.1 DTS wiring  (grep: POC-LEGACY-DTS) ===
# ============================================================================
# Everything below, plus the two call sites tagged "POC-LEGACY-DTS" in
# __init__.py (importMapping sniff) and FactPipeline.py (factSource DTS
# discovery), is throwaway scaffolding to demonstrate loading a legacy DTS as a
# compiled model alongside OIM objects. To remove: delete this block and the two
# tagged call sites. No other code depends on it.
#
#   Scenario A: a factSource/factMap references an XBRL 2.1 report (xBRL-XML or
#               inline); its schemaRef/linkbaseRef discovery point is compiled to
#               a compiled model presented alongside the loaded facts.
#   Scenario B: an importMapping entry resolves to an .xsd/.xml; it is sniffed as
#               a legacy XBRL 2.1 DTS discovery point and compiled in place of an
#               OIM import.
# ============================================================================

_POC_LEGACY_EXTS = ("xsd", "xml", "xhtml", "htm", "html")

# Reentrancy guard: True while the compiler is re-loading a DTS through the normal 2.1
# infrastructure, so the plugin's pull-loader does NOT re-claim those documents (which
# would recurse). Set only around the internal ModelXbrl.load in the entry-point path.
_pocInLegacyDiscovery = False


def pocIsLegacyEntryPoint(filepath) -> bool:
    """POC: should the plugin claim ``filepath`` as a legacy XBRL 2.1 taxonomy entry
    point to load directly into the XbrlModel model? Only a schema (.xsd), and never
    while the compiler is itself discovering a DTS (the reentrancy guard)."""
    if _pocInLegacyDiscovery or not filepath:
        return False
    return str(filepath).split("?", 1)[0].lower().endswith(".xsd")


def pocLoadLegacyAsEntry(cntlr, modelXbrl, filepath, mappedUri):
    """POC: load a legacy XBRL 2.1 entry point directly into ``modelXbrl`` as an OIM
    compiled model (standalone, base inlined), so it appears in the XbrlModel views with
    no shim JSON. Returns the ModelDocument (or None). Discovery of the DTS runs through
    the normal infrastructure under the reentrancy guard."""
    global _pocInLegacyDiscovery
    from arelle import ModelXbrl as _ModelXbrl
    legacyMx = None
    _pocInLegacyDiscovery = True
    try:
        legacyMx = _ModelXbrl.load(cntlr.modelManager, filepath,
                                   _("POC legacy XBRL 2.1 entry-point discovery"))
    finally:
        _pocInLegacyDiscovery = False
    if legacyMx is None or not getattr(legacyMx, "qnameConcepts", None):
        if legacyMx is not None:
            legacyMx.close()
        return None
    try:
        moduleDict = legacyTaxonomyToOimModule(legacyMx, inlineBase=True)
        from . import loadXbrlModule  # lazy: avoid import cycle with the package
        return loadXbrlModule(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl,
                              moduleDict, mappedUri or filepath)
    finally:
        legacyMx.close()


def pocIsLegacyDtsRef(url) -> bool:
    """POC: crude sniff -- treat an .xsd/.xml/.xhtml/.htm(l) reference as a legacy
    XBRL 2.1 DTS discovery point. OIM taxonomy documents (.json/.cbor) never match,
    so they take the normal path."""
    if not url:
        return False
    stem = str(url).split("?", 1)[0].split("#", 1)[0]
    return stem.rsplit(".", 1)[-1].lower() in _POC_LEGACY_EXTS


def pocCompileLegacyDts(cntlr, targetModelXbrl, error, warning, url,
                        moduleName=None):
    """POC: discover the legacy XBRL 2.1 DTS reachable from ``url`` (a schema,
    linkbase, or instance entry point), compile it to a compiled model via
    ``legacyTaxonomyToOimModule``, and load that compiled model into
    ``targetModelXbrl`` as though it had been imported. Returns the ModelDocument
    (or None on failure). The transient DTS ModelXbrl is discarded afterwards."""
    from arelle import ModelXbrl as _ModelXbrl
    global _pocInLegacyDiscovery
    legacyMx = None
    try:
        _pocInLegacyDiscovery = True  # suppress the pull-loader re-claiming this DTS
        try:
            legacyMx = _ModelXbrl.load(cntlr.modelManager, url,
                                       _("POC legacy XBRL 2.1 DTS discovery"))
        finally:
            _pocInLegacyDiscovery = False
        if legacyMx is None or not getattr(legacyMx, "qnameConcepts", None):
            error("arelle:pocLegacyDtsNotDiscovered",
                  _("POC: no XBRL 2.1 DTS could be discovered at %(url)s"), url=url)
            return None
        # inlineBase=False: the host importing model already provides the base spec
        # objects (xbrlm:base), so inlining them here would duplicate the base labels.
        moduleDict = legacyTaxonomyToOimModule(legacyMx, inlineBase=False)
        if moduleName is not None:
            # the importer named this taxonomy (importMapping key): the compiled
            # module MUST carry that exact name, and its prefix MUST be bound so the
            # name QName resolves and matches the resolver's name check.
            moduleDict["xbrlModel"]["name"] = str(moduleName)
            pfx, ns = getattr(moduleName, "prefix", None), getattr(moduleName, "namespaceURI", None)
            if pfx and ns:
                moduleDict["documentInfo"]["namespaces"].setdefault(pfx, ns)
        from . import loadXbrlModule  # lazy: avoid import cycle with the package
        return loadXbrlModule(cntlr, error, warning, targetModelXbrl, moduleDict, url)
    except Exception as ex:  # POC: never let discovery break the host load
        error("arelle:pocLegacyDtsError",
              _("POC: error compiling legacy DTS at %(url)s: %(error)s"),
              url=url, error=str(ex))
        return None
    finally:
        if legacyMx is not None:
            try:
                legacyMx.close()
            except Exception:
                pass
# ==== END POC-LEGACY-DTS ====================================================
