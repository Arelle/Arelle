"""
See COPYRIGHT.md for copyright information.
"""
from typing import GenericAlias

EMPTY_DICT = {}

class XbrlTaxonomyObject:

    def __init__(self, dtsObjectIndex=0, **kwargs):
        self.dtsObjectIndex = dtsObjectIndex

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