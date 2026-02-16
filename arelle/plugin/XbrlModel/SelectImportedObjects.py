'''
See COPYRIGHT.md for copyright information.
'''

import regex as re
from bitarray import bitarray
from arelle.oim.Load import EMPTY_DICT
from .XbrlConst import qnXbrlImportTaxonomyObj, qnXbrlLabelObj
from .XbrlModule import xbrlObjectTypes, xbrlObjectQNames
from .XbrlObject import DEREFERENCE_OBJECT

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
    impTxModuleObj = impTxObj._txmyModule
    i0 = impTxModuleObj.xbrlMdlObjIndex # object index range of imported objects
    iL = impTxModuleObj._lastMdlObjIndex
    selObjs = bitarray(iL - i0 + 1) # True if object is selected
    exclObjs = bitarray(iL - i0 + 1) # True if object is excluded
    hasSel = False # has anything selecting
    hasExcl = False # has anything excluding
    exclLbls = impTxObj.excludeLabels
    name = impTxObj.xbrlModelName
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
                txmyMdl.error("oimte:invalidQNameReference",
                          _("The importTaxonomy %(name)s importObject %(qname)s must identify an taxonomy object."),
                          xbrlObject=impTxObj, name=name, qname=impObjQn)
    for impObjTp in importObjectTypes:
        if impObjTp == qnXbrlImportTaxonomyObj:
            txmyMdl.error("oimte:invalidReferenceToImportTaxonomyObject",
                      _("The importTaxonomy %(name)s importObjectType %(qname)s must identify a referencable taxonomy component object, excluding importTaxonomyObj."),
                      xbrlObject=impTxObj, name=name, qname=impObjTp)
        elif impObjTp not in xbrlObjectTypes.keys():
            txmyMdl.error("oimte:invalidImportedObjectType",
                      _("The importTaxonomy %(name)s importObjectType %(qname)s must identify a referencable taxonomy component object, excluding importTaxonomyObj."),
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
        if selObj.objectType == qnXbrlImportTaxonomyObj:
            txmyMdl.error("oimte:invalidReferenceToImportTaxonomyObject",
                      _("The importTaxonomy %(name)s selection[%(nbr)s] must identify a referencable taxonomy component object: %(qname)s."),
                      xbrlObject=impTxObj, name=name, nbr=iSel, qname=selObj.objectType)
            hasSelError = True
        elif selObj.objectType not in xbrlObjectTypes.keys():
            txmyMdl.error("oimte:invalidSelectionObjectType",
                      _("The importTaxonomy %(name)s selection[%(nbr)s] must identify a referencable taxonomy component object: %(qname)s."),
                      xbrlObject=impTxObj, name=name, nbr=iSel, qname=selObj.objectType)
            hasSelError = True
        for iWh, whereObj in enumerate(selObj.where):
            if whereObj.property is None or whereObj.operator is None or whereObj.value is None:
                txmyMdl.error("oimte:invalidSelection",
                          _("The importTaxonomy %(name)s selection[%(nbr)s] is incomplete."),
                          xbrlObject=impTxObj, name=name, nbr=iSel)
                hasSelError = True
            else:
                if whereObj.property.namespaceURI is None: # object property
                    if whereObj.property.localName not in getattr(xbrlObjectTypes[selObj.objectType], "__annotations__", EMPTY_DICT):
                        txmyMdl.error("oimte:invalidSelectorOperator",
                                  _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] property %(qname)s does not exist for object %(objType)s."),
                                  xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, qname=whereObj.property, objType=selObj.objectType)
                        hasSelError = True
    if selections and not hasSelError:
        hasSel = True
        for obj in txmyMdl.namedObjects.values():
            if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                for selObj in impTxObj.selections:
                    if xbrlObjectQNames[type(obj)] == selObj.objectType and (
                        all((eval(obj, whereObj) for whereObj in selObj.where))):
                        selObjs[obj.xbrlMdlObjIndex - i0] = True
                        break # selections are or'ed, don't need to try more
    if hasSel:
        # select referenced objects
        moreRefObjsToSelect = [True]
        def selectReferencedObjects(obj):
            if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                if not selObjs[obj.xbrlMdlObjIndex - i0] and (
                            not isinstance(obj, XbrlLabelObj) or not exclLbls):
                    selObjs[obj.xbrlMdlObjIndex - i0] = True
                    moreRefObjsToSelect[0] = True
            return None # no further action
        while moreRefObjsToSelect[0]:
            moreRefObjsToSelect[0] = False
            for obj in [o for o in txmyMdl.namedObjects.values()]:
                if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                    if selObjs[obj.xbrlMdlObjIndex - i0]:
                        obj.referencedObjectsAction(txmyMdl, selectReferencedObjects)
                        # select labels of objects
                        objName = getattr(obj,"name")
                        if not exclLbls and objName in txmyMdl.tagObjects:
                            for tagObj in txmyMdl.tagObjects[objName]:
                                if i0 <= tagObj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                                    selObjs[tagObj.xbrlMdlObjIndex - i0] = True

        # dereference non-selection references
        def derefNonSelection(obj):
            if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                if not selObjs[obj.xbrlMdlObjIndex - i0]:
                    return DEREFERENCE_OBJECT # remove reference from the model
            return None # no further action
        impTxModuleObj.referencedObjectsAction(txmyMdl, derefNonSelection)

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
    elif exclLbls:
        for obj in [o for o in txmyMdl.namedObjects.values()]:
            if i0 <= obj.xbrlMdlObjIndex <= iL: # applies to this taxonomy import
                if isinstance(obj, XbrlLabelObj):
                    if obj.relatedName in txmyMdl.tagObjects:
                        del txmyMdl.tagObjects[name]
                        del obj