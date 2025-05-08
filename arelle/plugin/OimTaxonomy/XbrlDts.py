"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, cast, Any, ClassVar
from collections import OrderedDict, defaultdict # OrderedDict is not same as dict, has additional key order features

from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl, create as modelXbrlCreate, XbrlConst
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType, XbrlLabelType, XbrlPropertyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject, XbrlTaxonomyTagObject

def castToDts(modelXbrl):
    if not isinstance(modelXbrl, XbrlDts) and isinstance(modelXbrl, ModelXbrl):
        modelXbrl.__class__ = XbrlDts
        modelXbrl.taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType] = OrderedDict()
        modelXbrl.dtsObjectIndex = 0
        modelXbrl.taxonomyObjects: list[XbrlTaxonomyObject] = []
        modelXbrl.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] = OrderedDict() # not visible metadata
        modelXbrl.tagObjects: defaultdict[QName, list[XbrlReferencableTaxonomyObject]] = defaultdict(list) # labels and references
    return modelXbrl


class XbrlDts(ModelXbrl): # complete wrapper for ModelXbrl
    taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType]
    taxonomyObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] # not visible metadata

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlDts, self).__init__(*args, **kwargs)
        self.taxonomyObjects: list[XbrlTaxonomyObject] = []
        self.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] = OrderedDict() # not visible metadata
        self.tagObjects: defaultdict[QName, list[XbrlReferencableTaxonomyObject]] = defaultdict(list) # labels and references

    @property
    def xbrlTaxonomy(self):
        return cast(XbrlTaxonomy, self.modelDocument)

    @property
    def labelTypes(self):
        return set(obj.labelType for l in self.tagObjects.values() for obj in l if hasattr(obj, "labelType"))

    @property
    def referenceTypes(self):
        return set(obj.referenceType for l in self.tagObjects.values() for obj in l if hasattr(obj, "referenceType"))

    def labelValue(self, name: QName, labelType: QName, lang: str | None = None, fallbackToName: bool = True) -> str | None:
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

    def referenceProperties(self, name: QName, referenceType: QName | None, lang: str | None = None) -> list[XbrlPropertyType]:
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
    def viewTaxonomyObject(self, objectId: str | int) -> None:
        """Finds taxonomy object, if any, and synchronizes any views displaying it to bring the model object into scrollable view region and highlight it
        :param objectId: string which includes _ordinalNumber, produced by ModelObject.objectId(), or integer object index
        """
        txmyObj: XbrlTaxonomyObject | str | int = ""
        try:
            if isinstance(objectId, XbrlTaxonomyObject):
                txmyObj = objectId
            elif isinstance(objectId, str) and objectId.startswith("_"):
                txmyObj = cast('XbrlTaxonomyObject', self.taxonomyObjects[int(objectId.rpartition("_")[2])])
            if txmyObj is not None:
                for view in self.views:
                    view.viewModelObject(txmyObj)
        except (IndexError, ValueError, AttributeError)as err:
            self.modelManager.addToLog(_("Exception viewing properties {0} {1} at {2}").format(
                            modelObject,
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

    def error(self, *args, **kwargs):
        if "xbrlObject" in kwargs:
            argValue = kwargs["xbrlObject"].entryLoadingUrl
            if isinstance(argValue, (tuple,list)):
                kwargs["sourceFileLines"] = argValue
            else:
                kwargs["sourceFileLine"] = argValue
            super(XbrlDts, self).error(*args, **kwargs)

    def warning(self, *args, **kwargs):
        if "xbrlObject" in kwargs:
            argValue = kwargs["xbrlObject"].entryLoadingUrl
            if isinstance(argValue, (tuple,list)):
                kwargs["sourceFileLines"] = argValue
            else:
                kwargs["sourceFileLine"] = argValue
            super(XbrlDts, self).warning(*args, **kwargs)


def create(*args: Any, **kwargs: Any) -> XbrlDts:
    return cast(XbrlDts, modelXbrlCreate(*args, **kwargs))
