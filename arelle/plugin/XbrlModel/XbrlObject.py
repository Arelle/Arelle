"""
See COPYRIGHT.md for copyright information.
"""
from typing import GenericAlias, _UnionGenericAlias, Any, _GenericAlias, ClassVar, ForwardRef
import os
from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from arelle.XmlValidate import INVALID, VALID
from .XbrlConst import qnStdLabel
XbrlModelObject = None # class forward reference

EMPTY_DICT = {}
DEREFERENCE_OBJECT = "dereferenceObject" # singleton to remove referenced object

def deleteCollectionMembers(txmyMdl, deletions, collection=None):
    if isinstance(collection, list):
        for deletion in deletions:
            while deletion in deletions:
                collection.remove(deletion)
    elif isinstance(collection, (set, OrderedSet)):
        for deletion in deletions:
            collection.discard(deletion)
    # remove from taxonomy model indices
    for deletion in deletions:
        objQn = deletion
        if hasattr(deletion, "name"):
            objQn = deletion.name
        if objQn in txmyMdl.namedObjects:
            del txmyMdl.namedObjects[objQn]
        if objQn in txmyMdl.tagObjects:
            for tagObj in txmyMdl.tagObjects[objQn].copy():
                if tagObj in deletions:
                    txmyMdl.tagObjects[objQn].remove(tagObj)
    deletions.clear() # dereference and prepare set for reuse

class XbrlModelClass:
    @classmethod
    def propertyNameTypes(cls, skipParentProperty=False):
        initialParentObjProp = skipParentProperty # true when the parent (xbrlModel or report) is to be skipped
        for propName, propType in getattr(cls, "__annotations__", EMPTY_DICT).items():
            if initialParentObjProp:
                initialParentObjProp = False
                if (isinstance(propType, str) or propType.__name__.startswith("Xbrl") or # skip taxonomy alias type
                    (isinstance(propType, _UnionGenericAlias) and
                     any((isinstance(t.__forward_arg__, str) or t.__forward_arg__.__name__.startswith("Xbrl")) for t in propType.__args__ if isinstance(t,ForwardRef)))): # Union of TypeAliases are ForwardArgs
                    continue
            if not isinstance(propType, _GenericAlias) or propType.__origin__ != ClassVar:
                yield propName, propType

class XbrlObject(XbrlModelClass):
    def __init__(self, xbrlMdlObjIndex=0, **kwargs):
        self.xbrlMdlObjIndex = xbrlMdlObjIndex

    @property
    def xbrlCompMdl(self):
        return None

    @property
    def entryLoadingUrl(self):
        href = str(getattr(getattr(self, 'taxonomy', None), 'name', '(none)'))
        className = type(self).__name__
        if className.startswith("Xbrl"):
            classIndex = getattr(self, "_classIndex", None)
            if classIndex is not None:
                href = f"{href}/{className[4].lower()}{className[5:]}[{classIndex}]"
        return href

    # getProperty returns an object property (e.g. an @property of the object, not object.properties[foo])
    def getProperty(self, propertyName, propertyClass=None, propertyType=None, language=None, defaultValue=None):
        return getattr(self, propertyName, defaultValue)

    # propertyObjectValue returns an object's property object validated typed xValue from .properties
    def propertyObjectValue(self, propertyType, defaultValue=None):
        for propObj in getattr(self, "properties", ()):
            if propObj.property == propertyType and getattr(propObj, "_xValid", INVALID) >= VALID:
                return getattr(propObj, "_xValue", defaultValue)
        return defaultValue

    @property
    def propertyView(self):
        objClass = type(self)
        isTaxonomyObject = isinstance(self, XbrlModelObject)
        objName = objClass.__name__[0].lower() + objClass.__name__[1:]
        propVals = []
        initialParentObjProp = True
        referenceProperties = None
        for propName, propType in self.propertyNameTypes():
            if initialParentObjProp:
                initialParentObjProp = False
                if (isinstance(propType, str) or propType.__name__.startswith("Xbrl") or # skip taxonomy alias type
                    (isinstance(propType, _UnionGenericAlias) and
                     any((isinstance(t.__forward_arg__, str) or t.__forward_arg__.__name__.startswith("Xbrl")) for t in propType.__args__ if isinstance(t,ForwardRef)))): # Union of TypeAliases are ForwardArgs
                    continue
            if hasattr(self, propName):
                val = getattr(self, propName)
                if isTaxonomyObject: # for Taxonomy objects, not used by OIM Instance objects
                    if propName == "properties":
                        for propObj in val:
                            propVals.append( (str(getattr(propObj, "property", "")), str(getattr(propObj, "value", ""))) )
                        continue
                    if propName in ("name", "groupName") and val and issubclass(objClass, XbrlReferencableModelObject):
                        # insert label first if any
                        if self.xbrlCompMdl is not None:
                            label = self.xbrlCompMdl.labelValue(val, qnStdLabel, fallbackToName=False)
                            if label:
                                propVals.append( ("label", label) )
                            referenceProperties = self.xbrlCompMdl.referenceProperties(val, None)
                elif propName == "factDimensions" and isinstance(val, dict):
                    for propKey, propVal in val.items():
                        propVals.append( (str(propKey), str(propVal) ) )
                    continue
                if isinstance(propType, GenericAlias): # set, dict, etc
                    propValueClass = propType.__args__[-1]
                    if hasattr(propValueClass, "propertyView"):
                        # skip empty sets of XBRL objects
                        if isinstance(val, (set,list)) and propValueClass.__name__.startswith("Xbrl"):
                            continue
                        propVal = [propName, f"({len(val)})"]
                        vals = val.values() if isinstance(val, dict) else val
                        nestedPropvals = [o.propertyView for o in vals]
                        if isinstance(nestedPropvals, (list, tuple)):
                            l = len(nestedPropvals)
                            if l == 1:
                                if isinstance(nestedPropvals[0], (list, tuple)):
                                    nestedPropvals = nestedPropvals[0]
                            elif l > 1:
                                if isinstance(nestedPropvals[0], (list, tuple)) and isinstance(nestedPropvals[0][0], (list, tuple)) and len(nestedPropvals[0][0]) == 2:
                                    # flatten properties
                                    flatPropvals = []
                                    for i,subPropval in enumerate(nestedPropvals):
                                        for subPropEnt in subPropval:
                                            flatPropvals.append([f"[{i}] {subPropEnt[0]}"]+[s for s in subPropEnt[1:]])
                                    nestedPropvals = flatPropvals
                        if nestedPropvals:
                            propVal.extend([nestedPropvals])
                    elif len(val) > 0:
                        propVal = ", ".join(str(v) for v in val)
                    else:
                        continue # omit this property
                elif val is None and isinstance(propType, _UnionGenericAlias) and propType.__args__[-1] == type(None):
                    continue # skip showing absent Optional[...] properties
                else:
                    propVal = (propName, f"{val}")
                propVals.append(propVal)
        if referenceProperties:
            for refType, refObjs in sorted(referenceProperties.items(), key=lambda a: str(a[0])):
                propVals.append(
                    ("references", str(refType), tuple(
                    (getattr(rp, "propertyTypeName", ""), getattr(rp, "value", "")) for rp in refObjs)))
        return tuple(propVals)

    def __repr__(self):
        # print object generic string based on class declaration
        objClass = type(self)
        objName = objClass.__name__[0].lower() + objClass.__name__[1:]
        propVals = [f"{self.xbrlMdlObjIndex}"]
        initialParentObjProp = True
        for propName, propType in getattr(objClass, "__annotations__", EMPTY_DICT).items():
            if isinstance(propType, _GenericAlias) and propType.__origin__ == ClassVar:
                continue
            if initialParentObjProp:
                initialParentProp = False
                if isinstance(propType, str) or getattr(propType, "__name__", "").startswith("Xbrl"): # skip taxonomy alias type
                    continue
            if hasattr(self, propName):
                val = getattr(self, propName)
                if val is None:
                    val = "(none)"
                elif isinstance(propType, GenericAlias): # set, dict, etc
                    val = f"({len(val)})"
                propVals.append(f"{propName}: {val}")
        return f"{objName}[{', '.join(propVals)}]"

    def referencedObjectsAction(self, txmyMdl, actionCallback):
        objClass = type(self)
        isTaxonomyObject = isinstance(self, XbrlModelObject)
        objName = objClass.__name__[0].lower() + objClass.__name__[1:]
        deRefs = set()
        propVals = []
        initialParentObjProp = True
        referenceProperties = None
        for propName, propType in self.propertyNameTypes():
            if initialParentObjProp:
                initialParentObjProp = False
                if (isinstance(propType, str) or propType.__name__.startswith("Xbrl") or # skip taxonomy alias type
                    (isinstance(propType, _UnionGenericAlias) and
                     any((isinstance(t.__forward_arg__, str) or t.__forward_arg__.__name__.startswith("Xbrl")) for t in propType.__args__ if isinstance(t,ForwardRef)))): # Union of TypeAliases are ForwardArgs
                    continue
            if propType.__name__ == "QNameKeyType":
                continue
            if hasattr(self, propName):
                val = getattr(self, propName)
                if isTaxonomyObject: # for Taxonomy objects, not used by OIM Instance objects
                    if propName == "properties":
                        continue
                if isinstance(propType, GenericAlias): # set, dict, etc
                    propValueClass = propType.__args__[-1]
                    if hasattr(propValueClass, "referencedObjectsAction"):
                        if isinstance(val, dict):
                            pass # unsure what to do TBD
                        elif isinstance(val, (set, list, OrderedSet)):
                            for v in val: # values are objects themseves vs QNames of  referencable objects
                                obj = v
                                if isinstance(v, QName):
                                    if v in txmyMdl.namedObjects:
                                        obj = txmyMdl.namedObjects[v]
                                if isinstance(obj, XbrlObject):
                                    if actionCallback(obj) is DEREFERENCE_OBJECT:
                                        deRefs.add(obj)
                                        if obj.__class__.__name__ == "XbrlLabel" and getattr(obj, "relatedName", None):
                                            deRefs.add(obj.relatedName)
                                        if isinstance(v, QName):
                                            deRefs.add(v)
                                if obj.__class__.__name__ == "XbrlLabel":
                                    if actionCallback(obj) is DEREFERENCE_OBJECT:
                                        deRefs.add(obj)
                            deleteCollectionMembers(txmyMdl, deRefs, val)
                elif isinstance(val, QName):
                    obj = txmyMdl.namedObjects.get(val)
                    if isinstance(obj, XbrlObject):
                        if actionCallback(obj) is DEREFERENCE_OBJECT:
                            deRefs.add(obj)
                            setattr(self, propName, None)
                    deleteCollectionMembers(txmyMdl, deRefs, val)


class XbrlModelObject(XbrlObject):
    pass

class XbrlReportObject(XbrlObject):
    pass

class XbrlReferencableModelObject(XbrlModelObject):

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlReferencableModelObject, self).__init__(*args, **kwargs)

    @property
    def xbrlCompMdl(self):
        if hasattr(self, "module"):
            return self.module.compiledModel
        return None

    def getProperty(self, propertyName, propertyType=None, language=None, defaultValue=None):
        if propertyName == "label" and hasattr(self, "name") and self.xbrlCompMdl is not None:
            return self.xbrlCompMdl.labelValue(self.name, propertyType or qnStdLabel, language)
        return getattr(self, propertyName, defaultValue)

class XbrlTaxonomyTagObject(XbrlModelObject):

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlTaxonomyTagObject, self).__init__(*args, **kwargs)

    @property
    def xbrlCompMdl(self):
        if hasattr(self, "module"):
            return self.module.compiledModel
        return None

    def getProperty(self, propertyName, propertyType=None, language=None, defaultValue=None):
        return getattr(self, propertyName, defaultValue)

class XbrlObjectType(XbrlObject):

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlObjectType, self).__init__(*args, **kwargs)
        if "name" in kwargs:
            self.name = kwargs["name"]

