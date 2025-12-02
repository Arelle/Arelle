'''
See COPYRIGHT.md for copyright information.
'''

import regex as re
from bitarray import bitarray
from arelle.oim.Load import EMPTY_DICT
from .XbrlConst import qnXbrlLabelObj
from .XbrlTaxonomyModule import xbrlObjectTypes, xbrlObjectQNames
from pickle import EMPTY_DICT

def eval(obj, whereObj):
    qn = whereObj.property
    if qn.namespaceURI is None:
        v1 = getattr(obj, qn.localName)
    else:
        for i, propObj in enumerate(getattr(obj, "properties", ())):
            if propObj.name == qn:
                v1 = propObj.value # should use _xValue if _xValid >- VALID
                break
    op = whereObj.operator
    v2 = whereObj.value
    if op == "==":
        return v1 == v2
    elif op == "!=":
        return v1 == v2
    elif op == "in":
        return v1 in v2
    elif op == "not in":
        return v1 not in v2
    elif op == "contains":
        return v2 in v1
    elif op == "not contains":
        return v2 not in v1
    elif op == ">":
        return v1 > v2
    elif op == "<":
        return v1 < v2
    elif op == ">=":
        return v1 >= v2
    elif op == "<=":
        return v1 <= v2

def selectImportedObjects(txmyMdl, newTxmy, impTxObj):
    i0 = impTxObj._txmyModule.xbrlMdlObjIndex # object index range of imported objects
    iL = impTxObj._txmyModule._lastMdlObjIndex
    selObjs = bitarray(iL - i0 + 1) # True if object is selected
    exclObjs = bitarray(iL - i0 + 1) # True if object is excluded
    hasSel = False # has anything selecting
    hasExcl = False # has anything excluding
    exclLbls = impTxObj.excludeLabels
    name = impTxObj.taxonomyName
    if impTxObj.profiles:
        selections = set()
        importObjects = set()
        importObjectTypes = set()
        excludeLabels = False
        impExpProfiles = set(expPrflObj.name for expPrflObj in newTxmy.exportProfiles)
        if not (impTxObj.selections or impTxObj.importObjects or impTxObj.importObjectTypes):
            txmyMdl.error("oimte:invalidImportTaxonomy",
                      _("The importTaxonomy %(name)s profiles must only be used without selectons, importObjects or importObjectTypes."),
                      xbrlObject=impTxObj, name=name, qname=impObjQn)
        elif any (impTxObj.profiles - impExpProfiles):
            txmyMdl.error("oimte:invalidProfileFramework",
                      _("The importTaxonomy %(name)s profile %(profiles)s is(Are) not present in the imported taxonomy."),
                      xbrlObject=impTxObj, name=name, profiles=(str(p) for p in (impTxObj.profiles - impExpProfile)))
        else:
            for expPrflObj in newTxmy.exportProfiles:
                if expPrflObj.name in impTxObj.selections:
                    selections |= expPrflObj.selections
                    importObjects |= expPrflObj.importObjects
                    importObjectTypes |= expPrflObj.importObjectTypes
                    excludeLabels |= expPrflObj.excludeLabels
    else:
        importObjects = impTxObj.importObjects
        importObjectTypes = impTxObj.importObjectTypes
        selections = impTxObj.selections
        excludeLabels = impTxObj.excludeLabels
    if importObjects:
        hasSel = True
        for impObjQn in impTxObj.importObjects:
            obj = txmyMdl.namedObjects.get(impObjQn)
            if obj is not None:
                if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                    selObjs[obj.xbrlMdlObjIndex - i0] = True
                for obj in txmyMdl.tagObjects.get(impObjQn, ()):
                    if i0 <= obj.xbrlMdlObjIndex <= iL and (not exclLbls or type(obj) != XbrlLabel):
                        selObjs[obj.xbrlMdlObjIndex - i0] = True
            else:
                txmyMdl.error("oimte:unknownIncludedObject",
                          _("The importTaxonomy %(name)s importObject %(qname)s must identify an taxonomy object."),
                          xbrlObject=impTxObj, name=name, qname=impObjQn)
    for impObjTp in importObjectTypes:
        if impObjTp not in xbrlObjectTypes.keys() - {qnXbrlLabelObj}:
            txmyMdl.error("oimte:invalidImportedObjectType",
                      _("The importTaxonomy %(name)s importObjectType %(qname)s must identify a referencable taxonomy component object, excluding labelObject."),
                      xbrlObject=impTxObj, name=name, qname=impObjTp)
    if importObjectTypes:
        hasSel = True
        for obj in txmyMdl.namedObjects.values():
            if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                if xbrlObjectQNames[type(obj)] in impTxObj.importObjectTypes:
                    selObjs[obj.xbrlMdlObjIndex - i0] = True
        for objs in txmyMdl.tagObjects.values():
            for obj in objs:
                if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                    if xbrlObjectQNames[type(obj)] in impTxObj.importObjectTypes:
                        selObjs[obj.xbrlMdlObjIndex - i0] = True
    hasSelError = False
    for iSel, selObj in enumerate(selections):
        if selObj.objectType not in xbrlObjectTypes.keys():
            txmyMdl.error("oimte:invalidSelectionObjectType",
                      _("The importTaxonomy %(name)s selection[%(nbr)s] must identify a referencable taxonomy component object: %(qname)s."),
                      xbrlObject=impTxObj, name=name, nbr=iSel, qname=selObj.objectType)
            hasSelError = True
        for iWh, whereObj in enumerate(selObj.where):
            if whereObj.property is None or whereObj.operator is None or whereObj.value is None:
                txmyMdl.error("oimte:invalidSelection",
                          _("The importTaxonomy %(name)s selection[%(nbr)s] is incomplete."),
                          xbrlObject=impTxObj, name=name, nbr=iSel)
            else:
                if whereObj.property.namespaceURI is None: # object property
                    if whereObj.property.localName not in getattr(xbrlObjectTypes[selObj.objectType], "__annotations__", EMPTY_DICT):
                        txmyMdl.error("oimte:invalidSelectorOperator",
                                  _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] property %(qname)s does not exist for object %(objType)s."),
                                  xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, qname=whereObj.property, objType=selObj.objectType)
    if selections and not hasSelError:
        hasSel = True
        for obj in txmyMdl.namedObjects.values():
            if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                for selObj in impTxObj.selections:
                    if type(obj) not in xbrlObjectQNames:
                        print("trace")
                    if xbrlObjectQNames[type(obj)] == selObj.objectType and (
                        all((eval(obj, whereObj) for whereObj in selObj.where))):
                        selObjs[obj.xbrlMdlObjIndex - i0] = True
                        break # selections are or'ed, don't need to try more
    if hasSel:
        # exclude non-selections
        for obj in [o for o in txmyMdl.namedObjects.values()]:
            if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                if not selObjs[obj.xbrlMdlObjIndex - i0]:
                    name = obj.name
                    if name in txmyMdl.namedObjects:
                        del txmyMdl.namedObjects[name]
                    if name in txmyMdl.tagObjects:
                        refObjs = txmyMdl.tagObjects[name]
                        del txmyMdl.tagObjects[name]
                        for refObj in refObjs:
                            del refObj
                    del obj