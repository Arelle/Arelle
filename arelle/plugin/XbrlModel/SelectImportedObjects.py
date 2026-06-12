'''
See COPYRIGHT.md for copyright information.
'''

import regex as re, inspect
from bitarray import bitarray
from arelle.oim.Load import EMPTY_DICT
from arelle.ModelValue import QName
from .XbrlConst import qnXbrlImportTaxonomyObj
from .XbrlLabel import XbrlLabel
from .XbrlModule import xbrlObjectTypes, xbrlObjectQNames
from .XbrlObject import DEREFERENCE_OBJECT

def eval(obj, whereObj):
    """Evaluate a where condition for an object.
       Return True if the condition is satisfied, False if not satisfied, or None if cannot be evaluated.
    """
    qn = whereObj.property
    v1 = None
    if qn.namespaceURI is None:
        v1 = getattr(obj, qn.localName, None)
    else:
        for i, propObj in enumerate(getattr(obj, "properties", ())):
            if getattr(propObj, "property", None) == qn:
                v1 = propObj.value # should use _xValue if _xValid >- VALID
                break
    op = whereObj.operator
    v2 = whereObj.value
    try:
        if op == "==":
            return v1 == v2
        elif op == "!=":
            return v1 != v2
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
    except TypeError:
        return None
    return None

def selectImportedObjects(txmyMdl, newTxmy, impTxObj):
    """Select imported objects based on importTaxonomy selection, importObjects and importObjectTypes, and exportProfile selections.
        Exclude objects not selected. Exclude labels if excludeLabels is true. Select referenced objects of selected objects.
        Exclude non-selected objects from the model.
    """
    impTxModuleObj = impTxObj._txmyModule
    i0 = impTxModuleObj.xbrlMdlObjIndex # object index range of imported objects
    iL = impTxModuleObj._lastMdlObjIndex
    selObjs = bitarray(iL - i0 + 1) # True if object is selected
    exclObjs = bitarray(iL - i0 + 1) # True if object is excluded
    hasSel = False # has anything selecting
    hasExcl = False # has anything excluding
    exclLbls = impTxObj.excludeLabels
    name = impTxObj.xbrlModelName
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
            txmyMdl.error("oimte:invalidImportObjectType",
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
    VALID_OPERATORS = {"==", "!=", "in", "not in", "contains", "not contains", ">", "<", ">=", "<="}
    ARRAY_OPERATORS = {"in", "not in"}
    ORDERED_OPERATORS = {">", "<", ">=", "<="}
    STRING_ONLY_OPERATORS = {"contains", "not contains"}
    for iSel, selObj in enumerate(selections):
        selObjTypeValid = False
        if selObj.objectType is None:
            txmyMdl.error("oimte:invalidSelectionExpression",
                      _("The importTaxonomy %(name)s selection[%(nbr)s] is missing the required objectType."),
                      xbrlObject=impTxObj, name=name, nbr=iSel)
            hasSelError = True
        elif selObj.objectType == qnXbrlImportTaxonomyObj:
            txmyMdl.error("oimte:invalidReferenceToImportTaxonomyObject",
                      _("The importTaxonomy %(name)s selection[%(nbr)s] must identify a referencable taxonomy component object: %(qname)s."),
                      xbrlObject=impTxObj, name=name, nbr=iSel, qname=selObj.objectType)
            hasSelError = True
        elif selObj.objectType not in xbrlObjectTypes.keys():
            txmyMdl.error("oimte:invalidSelectionExpression",
                      _("The importTaxonomy %(name)s selection[%(nbr)s] objectType is not a recognised taxonomy object type: %(qname)s."),
                      xbrlObject=impTxObj, name=name, nbr=iSel, qname=selObj.objectType)
            hasSelError = True
        else:
            selObjTypeValid = True
        annotations = inspect.get_annotations(xbrlObjectTypes[selObj.objectType]) if selObjTypeValid else {}
        for iWh, whereObj in enumerate(selObj.where):
            if whereObj.property is None or whereObj.operator is None or whereObj.value is None:
                txmyMdl.error("oimte:invalidSelectionExpression",
                          _("The importTaxonomy %(name)s selection[%(nbr)s] is incomplete."),
                          xbrlObject=impTxObj, name=name, nbr=iSel)
                hasSelError = True
                continue
            op = whereObj.operator
            val = whereObj.value
            if op not in VALID_OPERATORS:
                txmyMdl.error("oimte:invalidSelectionExpression",
                          _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] operator %(operator)s is not a valid operator."),
                          xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, operator=op)
                hasSelError = True
                continue
            # array-operator: value must be a non-empty list
            if op in ARRAY_OPERATORS:
                if not isinstance(val, list):
                    txmyMdl.error("oimte:invalidSelectionExpression",
                              _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] operator %(operator)s requires an array value."),
                              xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, operator=op)
                    hasSelError = True
                    continue
                elif len(val) == 0:
                    txmyMdl.error("oimte:invalidSelectionExpression",
                              _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] operator %(operator)s requires a non-empty array value."),
                              xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, operator=op)
                    hasSelError = True
                    continue
            if not selObjTypeValid:
                continue
            if whereObj.property.namespaceURI is None: # object property
                propLocalName = whereObj.property.localName
                if propLocalName not in annotations:
                    txmyMdl.error("oimte:invalidSelectionExpression",
                              _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] property %(qname)s does not exist for object %(objType)s."),
                              xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, qname=whereObj.property, objType=selObj.objectType)
                    hasSelError = True
                    continue
                propAnn = annotations[propLocalName]
                # unwrap Optional / Union / DefaultTrue/DefaultFalse — best-effort: detect bool
                propTypeArgs = getattr(propAnn, "__args__", ())
                isBool = (propAnn is bool) or any(a is bool for a in propTypeArgs) or \
                    any(getattr(a, "__name__", "") in ("DefaultTrue", "DefaultFalse") for a in propTypeArgs)
                isStr = (propAnn is str) or any(a is str for a in propTypeArgs)
                isQName = (propAnn is QName) or any(isinstance(a, type) and issubclass(a, QName) for a in propTypeArgs)
                # contains/not contains are string-only operators
                if op in STRING_ONLY_OPERATORS and not isStr:
                    txmyMdl.error("oimte:invalidSelectionExpression",
                              _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] operator %(operator)s is only valid for string properties; property %(prop)s is not a string."),
                              xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, operator=op, prop=propLocalName)
                    hasSelError = True
                    continue
                # operator/value compatibility checks
                if isBool:
                    if op in ORDERED_OPERATORS or op in STRING_ONLY_OPERATORS or op in ARRAY_OPERATORS:
                        txmyMdl.error("oimte:invalidSelectionExpression",
                                  _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] operator %(operator)s is not compatible with boolean property %(prop)s."),
                                  xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, operator=op, prop=propLocalName)
                        hasSelError = True
                        continue
                    if not isinstance(val, bool):
                        txmyMdl.error("oimte:invalidSelectionExpression",
                                  _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] value %(value)r is not a boolean for property %(prop)s."),
                                  xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, value=val, prop=propLocalName)
                        hasSelError = True
                        continue
                elif isQName:
                    # QName-typed property: value must look like a QName (string with optional prefix:localName)
                    def _isQNameString(v):
                        return isinstance(v, str) and ":" in v
                    if op in ARRAY_OPERATORS:
                        if not all(_isQNameString(x) for x in val):
                            txmyMdl.error("oimte:invalidSelectionExpression",
                                      _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] array values must be QName strings for property %(prop)s."),
                                      xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, prop=propLocalName)
                            hasSelError = True
                            continue
                    elif not _isQNameString(val):
                        txmyMdl.error("oimte:invalidSelectionExpression",
                                  _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] value %(value)r is not a QName for property %(prop)s."),
                                  xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, value=val, prop=propLocalName)
                        hasSelError = True
                        continue
                elif isStr:
                    if op in ORDERED_OPERATORS:
                        txmyMdl.error("oimte:invalidSelectionExpression",
                                  _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] operator %(operator)s is not compatible with string property %(prop)s."),
                                  xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, operator=op, prop=propLocalName)
                        hasSelError = True
                        continue
                    # value must be string (for non-array operators) or list of strings (for array)
                    if op in ARRAY_OPERATORS:
                        if not all(isinstance(x, str) for x in val):
                            txmyMdl.error("oimte:invalidSelectionExpression",
                                      _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] array values must be strings for property %(prop)s."),
                                      xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, prop=propLocalName)
                            hasSelError = True
                            continue
                    elif not isinstance(val, str):
                        txmyMdl.error("oimte:invalidSelectionExpression",
                                  _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] value %(value)r is not a string for property %(prop)s."),
                                  xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, value=val, prop=propLocalName)
                        hasSelError = True
                        continue
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
                            not isinstance(obj, XbrlLabel) or not exclLbls):
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
                if isinstance(obj, XbrlLabel):
                    if obj.relatedName in txmyMdl.tagObjects:
                        del txmyMdl.tagObjects[name]
                        del obj