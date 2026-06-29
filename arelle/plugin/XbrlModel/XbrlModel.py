"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union, cast, Any, ClassVar
from collections import OrderedDict, defaultdict # OrderedDict is not same as dict, has additional key order features
import inspect
import sys, traceback
from arelle.ModelValue import QName, AnyURI
from arelle.ModelXbrl import ModelXbrl, create as modelXbrlCreate, XbrlConst
from arelle.oim.Load import EMPTY_DICT
from ordered_set import OrderedSet
from .XbrlCube import XbrlCube
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlDimension import XbrlDomainNetwork
from .XbrlGroup import XbrlGroupContent
from .XbrlNetwork import XbrlNetwork
from .XbrlReference import XbrlReference
from .XbrlFact import XbrlFact, XbrlFootnote
from .XbrlTypes import XbrlModuleAlias, XbrlLayoutAlias, QNameKeyType, XbrlLabelAlias, XbrlPropertyAlias
from .XbrlObject import XbrlObject, XbrlReferencableModelObject, XbrlTaxonomyTagObject, XbrlReportObject

def castToXbrlCompiledModel(modelXbrl, isReport=False):
    if not isinstance(modelXbrl, XbrlCompiledModel) and isinstance(modelXbrl, ModelXbrl):
        modelXbrl.__class__ = XbrlCompiledModel
        modelXbrl.xbrlModels: OrderedDict[QNameKeyType, XbrlModuleAlias] = OrderedDict()
        modelXbrl.dtsObjectIndex = 0
        modelXbrl.xbrlObjects: list[XbrlObject] = []
        modelXbrl.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableModelObject] = OrderedDict() # not visible metadata
        modelXbrl.tagObjects: defaultdict[QName, list[XbrlReferencableModelObject]] = defaultdict(list) # labels and references
        modelXbrl.dateResolutionConceptNames: OrderedSet[QName] = OrderedSet()
        modelXbrl._pendingImportEntries = defaultdict(list)
        modelXbrl._effectiveRelationshipSetCache = {}
        modelXbrl._effectiveReferenceRelatedNamesCache = {}
        modelXbrl._effectiveCubeExtensionCache = {}
        modelXbrl._referenceObjectsByNameCache = None
        modelXbrl._impliedObjectNamespaces = None
    return modelXbrl


class XbrlCompiledModel(ModelXbrl): # complete wrapper for ModelXbrl
    """Compiled XBRL model with additional properties and methods for use in XBRL report generation and analysis.
        This class extends the base ModelXbrl class (for Arelle 2.1 XBRL) to include additional properties for
        managing XBRL taxonomies, layouts, and report-specific data such as facts and footnotes.
        It also provides methods for retrieving labels and reference properties, as well as a method for viewing
        taxonomy objects in the user interface. The class is designed to be used in both taxonomy and report contexts,
        with properties that are relevant to each context.
    """
    xbrlModels: OrderedDict[QNameKeyType, XbrlModuleAlias]
    xbrlObjects: list[XbrlObject] # not visible metadata
    # objects only present for XbrlReports
    factspaces: dict[str, XbrlFact] # constant factspaces in taxonomy
    footnotes: dict[str, XbrlFootnote] # constant footnotes in taxonomy

    @classmethod
    def propertyNameTypes(cls):
        for propName, propType in inspect.get_annotations(cls).items():
            if propName in ("taxonomies", "layouts"):
                yield propName, propType

    @classmethod
    def parentNameType(cls):
        return None, None

    def __init__(self, isReport:bool = False, *args: Any, **kwargs: Any) -> None:
        super(XbrlCompiledModel, self).__init__(*args, **kwargs)
        self.dtsObjectIndex = 0
        self.xbrlObjects: list[XbrlObject] = []
        self.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableModelObject] = OrderedDict() # not visible metadata
        self.tagObjects: defaultdict[QName, list[XbrlReferencableModelObject]] = defaultdict(list) # labels and references
        self.dateResolutionConceptNames: OrderedSet[QName] = OrderedSet()
        self._pendingImportEntries: defaultdict[QName, list] = defaultdict(list)
        self._effectiveRelationshipSetCache: dict[int, dict[str, Any]] = {}
        self._effectiveReferenceRelatedNamesCache: dict[int, OrderedSet[QName]] = {}
        self._effectiveCubeExtensionCache: dict[int, dict[str, OrderedSet[Any]]] = {}
        self._referenceObjectsByNameCache: Optional[defaultdict[QName, list[XbrlReference]]] = None
        self._impliedObjectNamespaces: Optional[dict[str, Any]] = None  # built lazily


    @property
    def xbrlTaxonomy(self):
        return cast(XbrlTaxonomy, self.modelDocument)

    @property
    def labelTypes(self):
        return set(obj.labelType for l in self.tagObjects.values() for obj in l if hasattr(obj, "labelType"))

    @property
    def referenceTypes(self):
        return set(obj.referenceType for l in self.tagObjects.values() for obj in l if hasattr(obj, "referenceType"))

    def labelValue(self, name: QName, labelType: QName, lang: Optional[str] = None, fallbackToName: bool = True) -> Optional[str]:
        if labelType == XbrlConst.conceptNameLabelRole:
            return str(name)
        if lang is None:
            lang = self.modelXbrl.modelManager.defaultLang
        for tagObj in self.tagObjects.get(name, ()):
            tagLang = getattr(tagObj, "language", lang)
            if (getattr(tagObj, "labelType", None) == labelType and # causes skipping of reference objects
                (not lang or tagLang.startswith(lang) or lang.startswith(tagLang))): # TBD replace with 2.1 language detection
                if hasattr(tagObj, "value"):
                    return tagObj.value
                elif len(getattr(tagObj, "properties", ())) > 0:
                    return tagObj.propertyView
        # give up
        if fallbackToName:
            return str(name)
        return None

    # ── Implied Object Resolution ──────────────────────────────────────
    #
    # An implied object is one whose existence is determined by its namespace
    # URI alone, without an explicit definition in any imported module.
    # For example, LEI entity identifiers (namespace http://standards.iso.org/iso/17442)
    # are valid entity objects identified solely by their namespace.
    #
    # The implied object registry maps namespace URIs to their implied object
    # definitions (domain class, object type). It is built lazily from the
    # impliedObjects property of loaded modules.
    # ──────────────────────────────────────────────────────────────────

    def _buildImpliedObjectRegistry(self):
        if self._impliedObjectNamespaces is not None:
            return
        self._impliedObjectNamespaces = {}
        for module in self.xbrlModels.values():
            for implObj in getattr(module, "impliedObjects", None) or ():
                ns = getattr(implObj, "namespace", None)
                if ns:
                    self._impliedObjectNamespaces[str(ns)] = implObj

    def isImpliedObject(self, qname: QName) -> bool:
        """Return True if the QName's namespace is an implied object namespace."""
        self._buildImpliedObjectRegistry()
        return qname.namespaceURI in self._impliedObjectNamespaces if qname else False

    def impliedObjectDefinition(self, qname: QName):
        """Return the implied object definition for a QName, or None."""
        self._buildImpliedObjectRegistry()
        return self._impliedObjectNamespaces.get(qname.namespaceURI) if qname else None

    def referenceProperties(self, name: QName, referenceType: Optional[QName], lang: Optional[str] = None) -> list[XbrlPropertyAlias]:
        refProperties = defaultdict(list)
        for tagObj in self.effectiveReferenceObjects(name, referenceType=referenceType, lang=lang):
            refProperties[tagObj.referenceType].extend(getattr(tagObj, "properties", []))
        return refProperties

    def _referenceObjectsByName(self):
        if self._referenceObjectsByNameCache is None:
            refsByName = defaultdict(list)
            for obj in self.xbrlObjects:
                if isinstance(obj, XbrlReference) and getattr(obj, "name", None) is not None:
                    refsByName[obj.name].append(obj)
            self._referenceObjectsByNameCache = refsByName
        return self._referenceObjectsByNameCache

    def _effectiveReferenceRelatedNames(self, refObj, visiting: Optional[set[int]] = None):
        cacheKey = getattr(refObj, "xbrlMdlObjIndex", None)
        if cacheKey is None:
            cacheKey = id(refObj)
        cached = self._effectiveReferenceRelatedNamesCache.get(cacheKey)
        if cached is not None:
            return cached

        if visiting is None:
            visiting = set()
        if cacheKey in visiting:
            return OrderedSet(getattr(refObj, "relatedNames", ()) or ())

        visiting.add(cacheKey)
        relatedNames = OrderedSet()
        extends = refObj.extends
        if extends is not None:
            refType = getattr(refObj, "referenceType", None)
            for targetRefObj in self._referenceObjectsByName().get(extends, ()):
                if refType is None or getattr(targetRefObj, "referenceType", None) == refType:
                    relatedNames.update(self._effectiveReferenceRelatedNames(targetRefObj, visiting))

        relatedNames.update(getattr(refObj, "relatedNames", ()) or ())
        self._effectiveReferenceRelatedNamesCache[cacheKey] = relatedNames
        visiting.discard(cacheKey)
        return relatedNames

    def effectiveReferenceRelatedNames(self, refObj):
        return self._effectiveReferenceRelatedNames(refObj)

    def effectiveReferenceObjects(self, name: QName, referenceType: Optional[QName] = None, lang: Optional[str] = None):
        if lang is None:
            lang = self.modelXbrl.modelManager.defaultLang
        for obj in self.xbrlObjects:
            if isinstance(obj, XbrlReference):
                tagLang = getattr(obj, "language", None) or lang
                refType = getattr(obj, "referenceType", None)
                if (name in self._effectiveReferenceRelatedNames(obj) and
                    refType is not None and
                    (not referenceType or referenceType == refType) and
                    (not lang or tagLang.startswith(lang) or lang.startswith(tagLang))):
                    yield obj

    def clearEffectiveCaches(self):
        """Clear lazily recomputed caches derived from loaded taxonomy objects.

        GUI sessions may add labels, references, or extension objects to an
        already loaded compiled model. Clearing these caches allows effective
        products to be recomputed on demand against the updated model state.
        """
        self._effectiveRelationshipSetCache.clear()
        self._effectiveReferenceRelatedNamesCache.clear()
        self._effectiveCubeExtensionCache.clear()
        self._referenceObjectsByNameCache = None
        for obj in self.namedObjects.values():
            if isinstance(obj, (XbrlDomainNetwork, XbrlNetwork)):
                for attrName in ("_relationshipsFrom", "_relationshipsTo", "_roots"):
                    if hasattr(obj, attrName):
                        delattr(obj, attrName)
        for obj in self.xbrlObjects:
            if hasattr(obj, "_allowedMembers"):
                delattr(obj, "_allowedMembers")

    def clearDerivedCaches(self):
        """Alias for future cache invalidation expansion beyond relationships."""
        self.clearEffectiveCaches()

    # ── Extends Mechanism ──────────────────────────────────────────────
    #
    # Several taxonomy object types support an ``extends`` property that
    # allows one object to contribute relationships, properties, or set
    # members to another (the "base" object).  During compilation the
    # extending object's contributions are merged into the base, yielding
    # a single "effective" result that includes everything from both.
    #
    # Object types that support extends:
    #   XbrlNetwork / XbrlDomainNetwork  – merges relationships and roots
    #   XbrlCube                         – merges cubeNetworks, excludeCubes,
    #                                      requiredCubes, properties
    #   XbrlReference                    – merges relatedNames
    #   XbrlFact                         – merges factValues, properties
    #   XbrlMember                       – merges properties
    #   XbrlTableTemplate               – merges columns
    #
    # Resolution is recursive (an extending object may itself be extended)
    # with cycle detection via a ``visiting`` set.  Results are cached per
    # object in ``_effectiveRelationshipSetCache`` (networks/domains) and
    # ``_effectiveCubeExtensionCache`` (cubes).  Both caches are cleared by
    # ``clearEffectiveCaches()`` when the model is mutated.
    #
    # Validation code should use the ``effective*`` accessors below rather
    # than reading an object's own properties directly, so that extensions
    # are transparently included.
    # ──────────────────────────────────────────────────────────────────

    def _effectiveRelationshipSet(self, obj, visiting: Optional[set[int]] = None):
        """Build the effective (merged) relationship set for a network or domain,
        resolving the ``extends`` chain recursively.

        Relationships and roots from the base and all extensions are merged into
        a single set, sorted by the ``order`` property.  Duplicate roots and
        duplicate relationships (same source, target, order, and properties) in
        the merged set are tracked for validation.
        """
        cacheKey = getattr(obj, "xbrlMdlObjIndex", None)
        if cacheKey is None:
            cacheKey = id(obj)
        cached = self._effectiveRelationshipSetCache.get(cacheKey)
        if cached is not None:
            return cached

        if visiting is None:
            visiting = set()
        if cacheKey in visiting:
            return {
                "relationships": OrderedSet(getattr(obj, "relationships", ()) or ()),
                "relationshipsFrom": defaultdict(list),
                "relationshipsTo": defaultdict(list),
                "roots": OrderedSet(),
                "duplicateRoots": OrderedSet(),
                "duplicateRelationships": [],
            }

        visiting.add(cacheKey)

        # Collect all roots as (qname, order) tuples for sorting and dedup
        rootList = []   # [(qname, order, rootObj)]
        relList = []    # [(relObj)]
        extends = obj.extends
        if extends is not None:
            targetObj = self.namedObjects.get(extends)
            if isinstance(obj, XbrlDomainNetwork) and isinstance(targetObj, XbrlDomainNetwork) and getattr(targetObj, "isExtensible", True):
                baseSet = self._effectiveRelationshipSet(targetObj, visiting)
                relList.extend(baseSet["relationships"])
                rootList.extend((qn, None, None) for qn in baseSet["roots"])
            elif isinstance(obj, XbrlNetwork) and isinstance(targetObj, XbrlNetwork):
                baseSet = self._effectiveRelationshipSet(targetObj, visiting)
                relList.extend(baseSet["relationships"])
                rootList.extend((qn, None, None) for qn in baseSet["roots"])

        # Add this object's own roots and relationships
        objectRoots = getattr(obj, "roots", None)
        if objectRoots:
            for r in objectRoots:
                rootQn = r.root if hasattr(r, "root") else r
                rootOrder = getattr(r, "order", None) if hasattr(r, "root") else None
                rootList.append((rootQn, rootOrder, r))
        relList.extend(getattr(obj, "relationships", ()) or ())

        # Sort by order (None sorts last)
        def _orderKey(item):
            order = item[1] if isinstance(item, tuple) else getattr(item, "order", None)
            return (0, order) if order is not None else (1, 0)

        rootList.sort(key=_orderKey)
        relList.sort(key=lambda r: _orderKey(r))

        # Detect duplicate roots
        seenRoots = set()
        duplicateRoots = OrderedSet()
        explicitRoots = OrderedSet()
        for rootQn, _order, _rootObj in rootList:
            if rootQn in seenRoots:
                duplicateRoots.add(rootQn)
            else:
                seenRoots.add(rootQn)
            explicitRoots.add(rootQn)

        # Detect duplicate relationships (same source, target, order, properties)
        relationships = OrderedSet()
        duplicateRelationships = []
        relKeys = {}
        for relObj in relList:
            relKey = getattr(relObj, "_relKey", None)
            if relKey is None:
                relKey = (getattr(relObj, "source", None),
                          getattr(relObj, "target", None),
                          getattr(relObj, "order", None))
            if relKey in relKeys:
                duplicateRelationships.append((relKey, relObj))
            else:
                relKeys[relKey] = relObj
            relationships.add(relObj)

        relationshipsFrom = defaultdict(list)
        relationshipsTo = defaultdict(list)
        for relObj in relationships:
            if getattr(relObj, "source", None) is not None:
                relationshipsFrom[relObj.source].append(relObj)
            if getattr(relObj, "target", None) is not None:
                relationshipsTo[relObj.target].append(relObj)

        if explicitRoots:
            roots = OrderedSet(explicitRoots)
        else:
            roots = OrderedSet(
                qnFrom
                for qnFrom, relsFrom in relationshipsFrom.items()
                if qnFrom not in relationshipsTo or
                (len(relsFrom) == 1 and
                 len(relationshipsTo[qnFrom]) == 1 and
                 relsFrom[0].source == relsFrom[0].target)
            )

        effectiveSet = {
            "relationships": relationships,
            "relationshipsFrom": relationshipsFrom,
            "relationshipsTo": relationshipsTo,
            "roots": roots,
            "duplicateRoots": duplicateRoots,
            "duplicateRelationships": duplicateRelationships,
        }
        self._effectiveRelationshipSetCache[cacheKey] = effectiveSet
        visiting.discard(cacheKey)
        return effectiveSet

    def effectiveRelationships(self, obj):
        return self._effectiveRelationshipSet(obj)["relationships"]

    def effectiveRelationshipsFrom(self, obj):
        return self._effectiveRelationshipSet(obj)["relationshipsFrom"]

    def effectiveRelationshipRoots(self, obj):
        return self._effectiveRelationshipSet(obj)["roots"]

    def _effectiveCubeExtensionSet(self, cubeObj, visiting: Optional[set[int]] = None):
        cacheKey = getattr(cubeObj, "xbrlMdlObjIndex", None)
        if cacheKey is None:
            cacheKey = id(cubeObj)
        cached = self._effectiveCubeExtensionCache.get(cacheKey)
        if cached is not None:
            return cached

        if visiting is None:
            visiting = set()
        if cacheKey in visiting:
            return {
                "cubeNetworks": OrderedSet(getattr(cubeObj, "cubeNetworks", ()) or ()),
                "excludeCubes": OrderedSet(getattr(cubeObj, "excludeCubes", ()) or ()),
                "requiredCubes": OrderedSet(getattr(cubeObj, "requiredCubes", ()) or ()),
                "properties": OrderedSet(getattr(cubeObj, "properties", ()) or ()),
            }

        visiting.add(cacheKey)
        effectiveSet = {
            "cubeNetworks": OrderedSet(),
            "excludeCubes": OrderedSet(),
            "requiredCubes": OrderedSet(),
            "properties": OrderedSet(),
        }

        extends = cubeObj.extends
        if extends is not None:
            targetObj = self.namedObjects.get(extends)
            if isinstance(targetObj, XbrlCube):
                baseSet = self._effectiveCubeExtensionSet(targetObj, visiting)
                for propName, propVals in baseSet.items():
                    effectiveSet[propName].update(propVals)

        for propName in effectiveSet:
            effectiveSet[propName].update(getattr(cubeObj, propName, ()) or ())

        self._effectiveCubeExtensionCache[cacheKey] = effectiveSet
        visiting.discard(cacheKey)
        return effectiveSet

    def effectiveCubeNetworks(self, cubeObj):
        return self._effectiveCubeExtensionSet(cubeObj)["cubeNetworks"]

    def effectiveExcludeCubes(self, cubeObj):
        return self._effectiveCubeExtensionSet(cubeObj)["excludeCubes"]

    def effectiveRequiredCubes(self, cubeObj):
        return self._effectiveCubeExtensionSet(cubeObj)["requiredCubes"]

    def effectiveCubeProperties(self, cubeObj):
        return self._effectiveCubeExtensionSet(cubeObj)["properties"]


    # UI thread viewTaxonomyObject
    def viewTaxonomyObject(self, objectId: Union[str, int]) -> None:
        """Finds taxonomy object, if any, and synchronizes any views displaying it to bring the model object into scrollable view region and highlight it
        :param objectId: string which includes _ordinalNumber, produced by ModelObject.objectId(), or integer object index
        """
        xbrlObj: Union[XbrlObject, str, int] = ""
        try:
            if isinstance(objectId, XbrlObject):
                xbrlObj = objectId
            elif isinstance(objectId, str) and objectId.startswith("_"):
                xbrlObj = cast('XbrlObject', self.xbrlObjects[int(objectId.rpartition("_")[2])])
            if xbrlObj is not None:
                for view in self.views:
                    view.viewModelObject(xbrlObj)
        except (IndexError, ValueError, AttributeError)as err:
            self.modelManager.addToLog(_("Exception viewing properties {0} {1} at {2}").format(
                            xbrlObj,
                            err, traceback.format_exc()))

    # DTS-wide object enumerators. For network-specific selection by arcrole or
    # role URI, prefer filterNetworks() over the generic filterNamedObjects().
    def filterNamedObjects(self, _class, _type=None, _lang=None):
        if (issubclass(_class, XbrlReferencableModelObject) or
            (issubclass(_class, (XbrlFact,XbrlFootnote)) and isinstance(self, XbrlCompiledModel))):  # taxonomy-owned fact
            for obj in self.namedObjects.values():
                if isinstance(obj, _class):
                    yield obj
        elif issubclass(_class, XbrlTaxonomyTagObject):
            for objs in self.tagObjects.values():
                for obj in objs:
                    if (isinstance(obj, _class) and
                        (not _type or _type == obj._type) and
                        (not _lang or not obj.language or _lang.startswith(obj.language) or obj.language.startswith(lang))):
                        yield obj

    def filterNetworks(self, arcrole=None, role=None):
        """Yield XbrlNetwork objects optionally filtered by arcrole and/or role.

        arcrole: may be a QName (matched against relationshipTypeName by exact
            equality, or — for the Xule shorthand convention — by localName),
            a non-empty string equal to a relationship type local-name shorthand
            (e.g. "parent-child"), or a full arcrole URI string matched against
            XbrlRelationshipType.uri.
        role: a string compared to each network's roleUri (XbrlGroup.groupURI).
        """
        arcQn = arcrole if isinstance(arcrole, QName) else None
        arcStr = arcrole if isinstance(arcrole, str) and arcrole else None
        roleStr = role if isinstance(role, str) and role else None
        for n in self.filterNamedObjects(XbrlNetwork):
            if arcQn is not None:
                rtn = getattr(n, "relationshipTypeName", None)
                if rtn != arcQn:
                    # shorthand: also accept by localName alone
                    if getattr(rtn, "localName", None) != arcQn.localName:
                        continue
            elif arcStr is not None:
                rtn = getattr(n, "relationshipTypeName", None)
                if rtn is None:
                    continue
                # match by local-name shorthand or by full arcrole URI
                if arcStr != getattr(rtn, "localName", None):
                    rt = n.relationshipType
                    if rt is None or getattr(rt, "uri", None) != arcStr:
                        continue
            if roleStr is not None and n.roleUri != roleStr:
                continue
            yield n


    def error(self, *args, **kwargs):
        if "xbrlObject" in kwargs:
            argValue = kwargs["xbrlObject"]
            if isinstance(argValue, (tuple,list,set,OrderedSet)):
                kwargs["sourceFileLines"] = [a.entryLoadingUrl for a in argValue if a is not None]
            elif isinstance(argValue, XbrlObject):
                kwargs["sourceFileLine"] = argValue.entryLoadingUrl
        elif "modelObject" in kwargs:
            modelObject = kwargs["modelObject"]
            if hasattr(modelObject, "entryLoadingUrl"):
                kwargs["sourceFileLine"] = modelObject.entryLoadingUrl
        super(XbrlCompiledModel, self).error(*args, **kwargs)

    def warning(self, *args, **kwargs):
        if "xbrlObject" in kwargs:
            argValue = kwargs["xbrlObject"]
            if isinstance(argValue, (tuple,list)):
                kwargs["sourceFileLines"] = [a.entryLoadingUrl for a in argValue if a is not None]
            else:
                kwargs["sourceFileLine"] = argValue.entryLoadingUrl
        super(XbrlCompiledModel, self).warning(*args, **kwargs)


def create(*args: Any, **kwargs: Any) -> XbrlCompiledModel:
    return cast(XbrlCompiledModel, modelXbrlCreate(*args, **kwargs))
