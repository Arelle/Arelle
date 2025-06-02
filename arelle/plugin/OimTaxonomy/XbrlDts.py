"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union, cast, Any, ClassVar
from collections import OrderedDict, defaultdict # OrderedDict is not same as dict, has additional key order features
import sys, traceback
from arelle.ModelValue import QName, AnyURI
from arelle.ModelXbrl import ModelXbrl, create as modelXbrlCreate, XbrlConst
from arelle.oim.Load import EMPTY_DICT
from arelle.PythonUtil import OrderedSet
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlGroup import XbrlGroupContent
from .XbrlReport import addReportProperties, XbrlFact, XbrlReportObject
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType, XbrlLabelType, XbrlPropertyType
from .XbrlTaxonomyObject import XbrlObject, XbrlReferencableTaxonomyObject, XbrlTaxonomyTagObject

def castToDts(modelXbrl, isReport=False):
    if not isinstance(modelXbrl, XbrlDts) and isinstance(modelXbrl, ModelXbrl):
        modelXbrl.__class__ = XbrlDts
        modelXbrl.taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType] = OrderedDict()
        modelXbrl.dtsObjectIndex = 0
        modelXbrl.xbrlObjects: list[XbrlObject] = []
        modelXbrl.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] = OrderedDict() # not visible metadata
        modelXbrl.tagObjects: defaultdict[QName, list[XbrlReferencableTaxonomyObject]] = defaultdict(list) # labels and references
        if isReport:
            addReportProperties(modelXbrl)
    return modelXbrl


class XbrlDts(ModelXbrl): # complete wrapper for ModelXbrl
    taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType]
    xbrlObjects: list[XbrlObject] # not visible metadata
    # objects only present for XbrlReports
    linkTypes: dict[str, AnyURI]
    linkGroups: dict[str, AnyURI]
    facts: dict[str, XbrlFact]

    def __init__(self, isReport:bool = False, *args: Any, **kwargs: Any) -> None:
        super(XbrlDts, self).__init__(*args, **kwargs)
        self.dtsObjectIndex = 0
        self.xbrlObjects: list[XbrlObject] = []
        self.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] = OrderedDict() # not visible metadata
        self.tagObjects: defaultdict[QName, list[XbrlReferencableTaxonomyObject]] = defaultdict(list) # labels and references
        if isReport:
            addReportProperties(self)


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
        if lang is None:
            lang = self.modelXbrl.modelManager.defaultLang
        for tagObj in self.tagObjects.get(name, ()):
            tagLang = getattr(tagObj, "language", None) or lang
            refType = getattr(tagObj, "referenceType", None)
            if (refType is not None and (not referenceType or referenceType == refType) and # causes skipping of label objects
                (not lang or tagLang.startswith(lang) or lang.startswith(tagLang))): # TBD replace with 2.1 language detection
                refProperties[refType].extend(getattr(tagObj, "properties", []))
        return refProperties


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
        if issubclass(_class, XbrlReferencableTaxonomyObject):
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
        elif issubclass(_class, XbrlReportObject):
            for obj in getattr(self, "facts", EMPTY_DICT).values():
                yield obj

    def error(self, *args, **kwargs):
        if "xbrlObject" in kwargs:
            argValue = kwargs["xbrlObject"]
            if isinstance(argValue, (tuple,list,set,OrderedSet)):
                kwargs["sourceFileLines"] = [a.entryLoadingUrl for a in argValue]
            else:
                kwargs["sourceFileLine"] = argValue.entryLoadingUrl
        elif "modelObject" in kwargs:
            modelObject = kwargs["modelObject"]
            if hasattr(modelObject, "entryLoadingUrl"):
                kwargs["sourceFileLine"] = modelObject.entryLoadingUrl
        super(XbrlDts, self).error(*args, **kwargs)

    def warning(self, *args, **kwargs):
        if "xbrlObject" in kwargs:
            argValue = kwargs["xbrlObject"]
            if isinstance(argValue, (tuple,list)):
                kwargs["sourceFileLines"] = [a.entryLoadingUrl for a in argValue]
            else:
                kwargs["sourceFileLine"] = argValue.entryLoadingUrl
        super(XbrlDts, self).warning(*args, **kwargs)


def create(*args: Any, **kwargs: Any) -> XbrlDts:
    return cast(XbrlDts, modelXbrlCreate(*args, **kwargs))
