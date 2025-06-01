"""
See COPYRIGHT.md for copyright information.
"""
from typing import GenericAlias, _UnionGenericAlias, Any
import os
from .XbrlConst import qnStdLabel
XbrlTaxonomyObject = None # class forward reference

EMPTY_DICT = {}

class XbrlObject:

    def __init__(self, dtsObjectIndex=0, **kwargs):
        self.dtsObjectIndex = dtsObjectIndex

    @property
    def xbrlDts(self):
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

    def getProperty(self, propertyName, propertyClass=None, propertyType=None, language=None, defaultValue=None):
        return getattr(self, propertyName, defaultValue)

    @property
    def propertyView(self):
        objClass = type(self)
        isTaxonomyObject = isinstance(self, XbrlTaxonomyObject)
        objName = objClass.__name__[0].lower() + objClass.__name__[1:]
        propVals = []
        initialParentObjProp = True
        referenceProperties = None
        for propName, propType in getattr(objClass, "__annotations__", EMPTY_DICT).items():
            if initialParentObjProp:
                initialParentObjProp = False
                if isinstance(propType, str) or propType.__name__.startswith("Xbrl"): # skip taxonomy alias type
                    continue
            if hasattr(self, propName):
                val = getattr(self, propName)
                if isTaxonomyObject: # for Taxonomy objects, not used by OIM Instance objects
                    if propName == "properties":
                        for propObj in val:
                            propVals.append( (str(getattr(propObj, "property", "")), str(getattr(propObj, "value", ""))) )
                        continue
                    if propName in ("name", "groupName") and val and issubclass(objClass, XbrlReferencableTaxonomyObject):
                        # insert label first if any
                        label = self.xbrlDts.labelValue(val, qnStdLabel, fallbackToName=False)
                        if label:
                            propVals.append( ("label", label) )
                        referenceProperties = self.xbrlDts.referenceProperties(val, None)
                elif propName == "dimensions" and isinstance(val, dict):
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
                        nestedPropvals = [o.propertyView for o in val]
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
        propVals = [f"{self.dtsObjectIndex}"]
        initialParentObjProp = True
        for propName, propType in getattr(objClass, "__annotations__", EMPTY_DICT).items():
            if initialParentObjProp:
                initialParentProp = False
                if isinstance(propType, str) or getattr(propType, "__name__", "").startswith("Xbrl"): # skip taxonomy alias type
                    continue
            if hasattr(self, propName):
                val = getattr(self, propName)
                if isinstance(propType, GenericAlias): # set, dict, etc
                    val = f"({len(val)})"
                propVals.append(f"{propName}: {val}")
        return f"{objName}[{', '.join(propVals)}]"

class XbrlTaxonomyObject(XbrlObject):
    pass

class XbrlReportObject(XbrlObject):
    pass

class XbrlReferencableTaxonomyObject(XbrlTaxonomyObject):

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlReferencableTaxonomyObject, self).__init__(*args, **kwargs)

    @property
    def xbrlDts(self):
        if hasattr(self, "taxonomy"):
            return self.taxonomy.dts
        return None

    def getProperty(self, propertyName, propertyType=None, language=None, defaultValue=None):
        if propertyName == "label" and hasattr(self, "name"):
            return self.xbrlDts.labelValue(self.name, propertyType or qnStdLabel, language)
        return getattr(self, propertyName, defaultValue)

class XbrlTaxonomyTagObject(XbrlTaxonomyObject):

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlTaxonomyTagObject, self).__init__(*args, **kwargs)

    @property
    def xbrlDts(self):
        if hasattr(self, "taxonomy"):
            return self.taxonomy.dts
        return None

    def getProperty(self, propertyName, propertyType=None, language=None, defaultValue=None):
        return getattr(self, propertyName, defaultValue)
