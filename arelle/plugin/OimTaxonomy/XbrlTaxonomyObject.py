"""
See COPYRIGHT.md for copyright information.
"""
from typing import GenericAlias, Any

EMPTY_DICT = {}

class XbrlTaxonomyObject:

    def __init__(self, dtsObjectIndex=0, **kwargs):
        self.dtsObjectIndex = dtsObjectIndex

    @property
    def propertyView(self):
        objClass = type(self)
        objName = objClass.__name__[0].lower() + objClass.__name__[1:]
        propVals = []
        initialParentObjProp = True
        for propName, propType in getattr(objClass, "__annotations__", EMPTY_DICT).items():
            if initialParentObjProp:
                initialParentProp = False
                if isinstance(propType, str) or propType.__name__.startswith("Xbrl"): # skip taxonomy alias type
                    continue
            if hasattr(self, propName):
                val = getattr(self, propName)
                if propName == "properties":
                    for propObj in val:
                        propVals.append( ( str(propObj.propertyTypeName), str(propObj.propertyValue) ) )
                    continue
                if isinstance(propType, GenericAlias): # set, dict, etc
                    propValueClass = propType.__args__[-1]
                    if hasattr(propValueClass, "propertyView"):
                        propVal = [propName, f"({len(val)})", [o.propertyView for o in val]]
                    elif len(val) > 0:
                        propVal = ", ".join(str(v) for v in val)
                    else:
                        continue # omit this property
                else:
                    propVal = (propName, f"{val}")
                propVals.append(propVal)
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
                if isinstance(propType, str) or propType.__name__.startswith("Xbrl"): # skip taxonomy alias type
                    continue
            if hasattr(self, propName):
                val = getattr(self, propName)
                if isinstance(propType, GenericAlias): # set, dict, etc
                    val = f"({len(val)})"
                propVals.append(f"{propName}: {val}")
        return f"{objName}[{', '.join(propVals)}]"

class XbrlReferencableTaxonomyObject(XbrlTaxonomyObject):

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlReferencableTaxonomyObject, self).__init__(*args, **kwargs)
