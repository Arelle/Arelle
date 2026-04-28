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
from arelle.PythonUtil import OrderedSet
from .XbrlCube import XbrlCube
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlDimension import XbrlDomain
from .XbrlGroup import XbrlGroupContent
from .XbrlNetwork import XbrlNetwork
from .XbrlReference import XbrlReference
from .XbrlReport import XbrlFact, XbrlFootnote, XbrlReport
from .XbrlTypes import XbrlModuleType, XbrlLayoutType, QNameKeyType, XbrlLabelType, XbrlPropertyType
from .XbrlObject import XbrlObject, XbrlReferencableModelObject, XbrlTaxonomyTagObject, XbrlReportObject

def castToXbrlCompiledModel(modelXbrl, isReport=False):
    if not isinstance(modelXbrl, XbrlCompiledModel) and isinstance(modelXbrl, ModelXbrl):
        modelXbrl.__class__ = XbrlCompiledModel
        modelXbrl.xbrlModels: OrderedDict[QNameKeyType, XbrlModuleType] = OrderedDict()
        modelXbrl.dtsObjectIndex = 0
        modelXbrl.xbrlObjects: list[XbrlObject] = []
        modelXbrl.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableModelObject] = OrderedDict() # not visible metadata
        modelXbrl.tagObjects: defaultdict[QName, list[XbrlReferencableModelObject]] = defaultdict(list) # labels and references
        modelXbrl.reports: OrderedDict[QNameKeyType, XbrlReport] = OrderedDict()
        modelXbrl.dateResolutionConceptNames: OrderedSet[QName] = OrderedSet()
        modelXbrl._effectiveRelationshipSetCache = {}
        modelXbrl._effectiveReferenceRelatedNamesCache = {}
        modelXbrl._effectiveCubeExtensionCache = {}
        modelXbrl._referenceObjectsByNameCache = None
    return modelXbrl


class XbrlCompiledModel(ModelXbrl): # complete wrapper for ModelXbrl
    """Compiled XBRL model with additional properties and methods for use in XBRL report generation and analysis.
        This class extends the base ModelXbrl class (for Arelle 2.1 XBRL) to include additional properties for
        managing XBRL taxonomies, layouts, and report-specific data such as facts and footnotes.
        It also provides methods for retrieving labels and reference properties, as well as a method for viewing
        taxonomy objects in the user interface. The class is designed to be used in both taxonomy and report contexts,
        with properties that are relevant to each context.
    """
    xbrlModels: OrderedDict[QNameKeyType, XbrlModuleType]
    xbrlObjects: list[XbrlObject] # not visible metadata
    # objects only present for XbrlReports
    factspaces: dict[str, XbrlFact] # constant factspaces in taxonomy
    footnotes: dict[str, XbrlFootnote] # constant footnotes in taxonomy
    reports: OrderedDict[QNameKeyType, XbrlReport] = OrderedDict()

    @classmethod
    def propertyNameTypes(cls):
        for propName, propType in inspect.get_annotations(cls).items():
            if propName in ("taxonomies", "layouts"):
                yield propName, propType

    def __init__(self, isReport:bool = False, *args: Any, **kwargs: Any) -> None:
        super(XbrlCompiledModel, self).__init__(*args, **kwargs)
        self.dtsObjectIndex = 0
        self.xbrlObjects: list[XbrlObject] = []
        self.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableModelObject] = OrderedDict() # not visible metadata
        self.tagObjects: defaultdict[QName, list[XbrlReferencableModelObject]] = defaultdict(list) # labels and references
        self.dateResolutionConceptNames: OrderedSet[QName] = OrderedSet()
        self._effectiveRelationshipSetCache: dict[int, dict[str, Any]] = {}
        self._effectiveReferenceRelatedNamesCache: dict[int, OrderedSet[QName]] = {}
        self._effectiveCubeExtensionCache: dict[int, dict[str, OrderedSet[Any]]] = {}
        self._referenceObjectsByNameCache: Optional[defaultdict[QName, list[XbrlReference]]] = None


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

    def referenceProperties(self, name: QName, referenceType: Optional[QName], lang: Optional[str] = None) -> list[XbrlPropertyType]:
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
        extendTargetName = getattr(refObj, "extendTargetName", None)
        if extendTargetName is not None:
            refType = getattr(refObj, "referenceType", None)
            for targetRefObj in self._referenceObjectsByName().get(extendTargetName, ()):
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
            if isinstance(obj, (XbrlDomain, XbrlNetwork)):
                for attrName in ("_relationshipsFrom", "_relationshipsTo", "_roots"):
                    if hasattr(obj, attrName):
                        delattr(obj, attrName)
        for obj in self.xbrlObjects:
            if hasattr(obj, "_allowedMembers"):
                delattr(obj, "_allowedMembers")

    def clearDerivedCaches(self):
        """Alias for future cache invalidation expansion beyond relationships."""
        self.clearEffectiveCaches()

    def _effectiveRelationshipSet(self, obj, visiting: Optional[set[int]] = None):
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
            }

        visiting.add(cacheKey)

        relationships = OrderedSet()
        explicitRoots = OrderedSet()
        extendTargetName = getattr(obj, "extendTargetName", None)
        if extendTargetName is not None:
            targetObj = self.namedObjects.get(extendTargetName)
            if isinstance(obj, XbrlDomain) and isinstance(targetObj, XbrlDomain) and not getattr(targetObj, "completeDomain", False):
                baseSet = self._effectiveRelationshipSet(targetObj, visiting)
                relationships.update(baseSet["relationships"])
                explicitRoots.update(baseSet["roots"])
            elif isinstance(obj, XbrlNetwork) and isinstance(targetObj, XbrlNetwork):
                baseSet = self._effectiveRelationshipSet(targetObj, visiting)
                relationships.update(baseSet["relationships"])
                explicitRoots.update(baseSet["roots"])

        objectRoots = getattr(obj, "roots", None)
        if objectRoots:
            explicitRoots.update(objectRoots)
        relationships.update(getattr(obj, "relationships", ()) or ())

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

        extendTargetName = getattr(cubeObj, "extendTargetName", None)
        if extendTargetName is not None:
            targetObj = self.namedObjects.get(extendTargetName)
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
                            err, traceback.format_tb(sys.exc_info()[2])))

    # dts-wide object accumulator properties
    def filterNamedObjects(self, _class, _type=None, _lang=None):
        if (issubclass(_class, XbrlReferencableModelObject) or # taxpmp,u-pwmed referemcab;e pbkect
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
        elif issubclass(_class, XbrlReportObject) and isinstance(self, (XbrlCompiledModel, XbrlReport)): # report facts
            if issubclass(_class, XbrlReport):
                objs = self.reports.values()
            else:
                facts = getattr(self, "facts", EMPTY_DICT).values()
            for obj in objs:
                yield obj

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
