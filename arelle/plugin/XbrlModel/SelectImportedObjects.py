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
        # properties may be present-but-None (not just absent); guard the iteration
        for i, propObj in enumerate(getattr(obj, "properties", None) or ()):
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

def validateImportSelections(txmyMdl, newTxmy, impTxObj):
    """Validate selection syntax on an import entry during loading.
       Sets impTxObj._hasSelError = True if any selection has invalid syntax.
       Does NOT perform any object selection or pruning.
    """
    name = impTxObj.xbrlModelName
    importObjectTypes = impTxObj.importObjectTypes or ()
    selections = impTxObj.selections or ()

    for impObjTp in importObjectTypes:
        if impObjTp == qnXbrlImportTaxonomyObj:
            txmyMdl.error("oimte:invalidReferenceToImportTaxonomyObject",
                      _("The importTaxonomy %(name)s importObjectType %(qname)s must identify a referencable taxonomy component object, excluding importTaxonomyObj."),
                      xbrlObject=impTxObj, name=name, qname=impObjTp)
        elif impObjTp not in xbrlObjectTypes.keys():
            txmyMdl.error("oimte:invalidImportObjectType",
                      _("The importTaxonomy %(name)s importObjectType %(qname)s must identify a referencable taxonomy component object, excluding importTaxonomyObj."),
                      xbrlObject=impTxObj, name=name, qname=impObjTp)

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
                propTypeArgs = getattr(propAnn, "__args__", ())
                isBool = (propAnn is bool) or any(a is bool for a in propTypeArgs) or \
                    any(getattr(a, "__name__", "") in ("DefaultTrue", "DefaultFalse") for a in propTypeArgs)
                isStr = (propAnn is str) or any(a is str for a in propTypeArgs)
                isQName = (propAnn is QName) or any(isinstance(a, type) and issubclass(a, QName) for a in propTypeArgs)
                if op in STRING_ONLY_OPERATORS and not isStr:
                    txmyMdl.error("oimte:invalidSelectionExpression",
                              _("The importTaxonomy %(name)s selection[%(selNbr)s]/where[%(whNbr)s] operator %(operator)s is only valid for string properties; property %(prop)s is not a string."),
                              xbrlObject=impTxObj, name=name, selNbr=iSel, whNbr=iWh, operator=op, prop=propLocalName)
                    hasSelError = True
                    continue
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
    impTxObj._hasSelError = hasSelError


def applyDeferredImportPruning(txmyMdl):
    """After the entire import graph is resolved, compute the union of all
       import selections per module and prune once per module.
    """
    for moduleName, importEntries in txmyMdl._pendingImportEntries.items():
        moduleObj = importEntries[0]._txmyModule

        unionImportObjects = set()
        unionImportObjectTypes = set()
        unionSelections = []
        allExcludeLabels = True
        allExcludeGroupContents = True
        anyUnfiltered = False

        for entry in importEntries:
            hasFilter = bool(entry.importObjects) or bool(entry.importObjectTypes) or bool(entry.selections)
            if not hasFilter:
                anyUnfiltered = True
            unionImportObjects |= entry.importObjects or set()
            unionImportObjectTypes |= entry.importObjectTypes or set()
            if entry.selections and not getattr(entry, "_hasSelError", False):
                unionSelections.extend(entry.selections)
            if not entry.excludeLabels:
                allExcludeLabels = False
            if not getattr(entry, "excludeGroupContents", False):
                allExcludeGroupContents = False

        if anyUnfiltered:
            if allExcludeLabels:
                _excludeLabelsOnly(txmyMdl, moduleObj)
            continue

        _pruneModuleObjects(txmyMdl, moduleObj,
                           unionImportObjects, unionImportObjectTypes, unionSelections,
                           allExcludeLabels, allExcludeGroupContents)

    del txmyMdl._pendingImportEntries


def _excludeLabelsOnly(txmyMdl, moduleObj):
    """Exclude label objects from a module without pruning other objects."""
    i0 = moduleObj.xbrlMdlObjIndex
    iL = moduleObj._lastMdlObjIndex
    for obj in [o for o in txmyMdl.namedObjects.values()]:
        if i0 <= obj.xbrlMdlObjIndex <= iL:
            if isinstance(obj, XbrlLabel):
                if obj.forObject in txmyMdl.tagObjects:
                    del txmyMdl.tagObjects[obj.forObject]
                del obj


def _pruneModuleObjects(txmyMdl, moduleObj,
                        importObjects, importObjectTypes, selections,
                        excludeLabels, excludeGroupContents):
    """Core pruning logic: select objects matching the unioned filters,
       transitively select referenced objects, then delete everything else.
    """
    i0 = moduleObj.xbrlMdlObjIndex
    iL = moduleObj._lastMdlObjIndex
    selObjs = bitarray(iL - i0 + 1)
    hasSel = False

    if importObjects:
        hasSel = True
        for impObjQn in importObjects:
            obj = txmyMdl.namedObjects.get(impObjQn)
            if obj is not None:
                if i0 <= obj.xbrlMdlObjIndex <= iL:
                    selObjs[obj.xbrlMdlObjIndex - i0] = True
                for obj in txmyMdl.tagObjects.get(impObjQn, ()):
                    if i0 <= obj.xbrlMdlObjIndex <= iL and (not excludeLabels or type(obj) != XbrlLabel):
                        selObjs[obj.xbrlMdlObjIndex - i0] = True
            else:
                # A named reference object carries its own name but, being a tag
                # object, is registered neither in namedObjects nor (reliably) in
                # tagObjects by that name. Scan this module's object range for a
                # matching name before reporting the importObject as unresolved.
                # (excludeLabels still suppresses label tag objects.)
                found = False
                for candObj in txmyMdl.xbrlObjects[i0:iL + 1]:
                    if (getattr(candObj, "name", None) == impObjQn
                            and (not excludeLabels or type(candObj) != XbrlLabel)):
                        selObjs[candObj.xbrlMdlObjIndex - i0] = True
                        found = True
                if not found:
                    txmyMdl.error("oimte:invalidQNameReference",
                              _("The importTaxonomy %(name)s importObject %(qname)s must identify a taxonomy object."),
                              xbrlObject=moduleObj, name=moduleObj.name, qname=impObjQn)

    if importObjectTypes:
        hasSel = True
        for obj in txmyMdl.namedObjects.values():
            if i0 <= obj.xbrlMdlObjIndex <= iL:
                if xbrlObjectQNames[type(obj)] in importObjectTypes:
                    selObjs[obj.xbrlMdlObjIndex - i0] = True
        for objs in txmyMdl.tagObjects.values():
            for obj in objs:
                if i0 <= obj.xbrlMdlObjIndex <= iL:
                    if xbrlObjectQNames[type(obj)] in importObjectTypes:
                        selObjs[obj.xbrlMdlObjIndex - i0] = True

    if selections:
        hasSel = True
        for obj in txmyMdl.namedObjects.values():
            if i0 <= obj.xbrlMdlObjIndex <= iL:
                for selObj in selections:
                    if xbrlObjectQNames[type(obj)] == selObj.objectType and (
                        all((eval(obj, whereObj) for whereObj in (selObj.where or ())))):
                        selObjs[obj.xbrlMdlObjIndex - i0] = True
                        break

    if hasSel:
        moreRefObjsToSelect = [True]
        def selectReferencedObjects(obj):
            if i0 <= obj.xbrlMdlObjIndex <= iL:
                if not selObjs[obj.xbrlMdlObjIndex - i0] and (
                            not isinstance(obj, XbrlLabel) or not excludeLabels):
                    selObjs[obj.xbrlMdlObjIndex - i0] = True
                    moreRefObjsToSelect[0] = True
                # An inline nested object (e.g. a relationship in a network or
                # domain network) has no name of its own, so the top-level
                # namedObjects walk below never visits it to follow its QName
                # references. Descend here so a selected network's relationship
                # source/target members are transitively selected too; the named
                # objects it reaches are handled by the outer walk, so recursion
                # terminates at the (unnamed) inline object.
                if getattr(obj, "name", None) is None:
                    obj.referencedObjectsAction(txmyMdl, selectReferencedObjects)
            return None
        while moreRefObjsToSelect[0]:
            moreRefObjsToSelect[0] = False
            for obj in [o for o in txmyMdl.namedObjects.values()]:
                if i0 <= obj.xbrlMdlObjIndex <= iL:
                    if selObjs[obj.xbrlMdlObjIndex - i0]:
                        obj.referencedObjectsAction(txmyMdl, selectReferencedObjects)
                        objName = getattr(obj,"name")
                        if not excludeLabels and objName in txmyMdl.tagObjects:
                            for tagObj in txmyMdl.tagObjects[objName]:
                                if i0 <= tagObj.xbrlMdlObjIndex <= iL:
                                    selObjs[tagObj.xbrlMdlObjIndex - i0] = True
            # Tag objects (labels, references) are not in namedObjects, so the
            # walk above never follows their own QName references. A selected
            # label pulled in for a selected object still points at e.g. its
            # labelType object, which must be selected too or it is pruned and
            # later reported as a dangling QName reference. Follow them here.
            for tagObjs in [list(v) for v in txmyMdl.tagObjects.values()]:
                for tagObj in tagObjs:
                    if i0 <= tagObj.xbrlMdlObjIndex <= iL and selObjs[tagObj.xbrlMdlObjIndex - i0]:
                        tagObj.referencedObjectsAction(txmyMdl, selectReferencedObjects)

        # Collect the QNames of in-range objects that are about to be pruned
        # (not selected), before dereferencing removes them from namedObjects.
        prunedNames = [o.name for o in txmyMdl.namedObjects.values()
                       if i0 <= o.xbrlMdlObjIndex <= iL
                       and not selObjs[o.xbrlMdlObjIndex - i0]
                       and getattr(o, "name", None) is not None]

        def derefNonSelection(obj):
            if i0 <= obj.xbrlMdlObjIndex <= iL:
                if not selObjs[obj.xbrlMdlObjIndex - i0]:
                    return DEREFERENCE_OBJECT
            return None
        moduleObj.referencedObjectsAction(txmyMdl, derefNonSelection)

        for obj in [o for o in txmyMdl.namedObjects.values()]:
            if i0 <= obj.xbrlMdlObjIndex <= iL:
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

        # A label whose sole forObject was pruned above is now orphaned. Drop it early so the tag index
        # stays consistent for selective import. (Orphaned labels/references/groupContents are also cleaned
        # comprehensively over the final merged model by cleanOrphanedForObjects — oim-taxonomy orphan
        # cleanup — so references and multi-target cases are handled there rather than per-import.)
        for prunedName in prunedNames:
            tagObjs = txmyMdl.tagObjects.get(prunedName)
            if not tagObjs:
                continue
            for tagObj in list(tagObjs):
                if isinstance(tagObj, XbrlLabel):
                    tagObjs.remove(tagObj)
                    refMod = getattr(tagObj, "module", None)
                    if refMod is not None and refMod.labels and tagObj in refMod.labels:
                        refMod.labels.remove(tagObj)
            if not tagObjs:
                del txmyMdl.tagObjects[prunedName]
    elif excludeLabels:
        _excludeLabelsOnly(txmyMdl, moduleObj)
