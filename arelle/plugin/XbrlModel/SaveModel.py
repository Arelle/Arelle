'''
See COPYRIGHT.md for copyright information.

Saves a loaded model (taxonomy objects + facts) as a single OIM compiled model
(documentType https://xbrl.org/2026/compiled) into json, cbor or Excel. The modules in
xbrlModels are merged into one xbrlModel object owning the whole closure.

Save mode (GUI: modal on Save; CLI/scripts: --saveOIMmodel + --oimSaveMode, or formula parameter
oimSaveMode which overrides the modal):
   full (default) | prune | report
      full   -- every discovered object and all facts, as loaded.
      prune  -- partial model: only the fact-reachability closure (PruneModel.pruneClosure),
                dropping taxonomy objects (incl. all networks/cubes) not needed to interpret the
                reported facts.
      report -- prune closure + presentation networks + cubes (those whose concept-domain lists a
                reported concept) + facts rewritten to Form B (value + valueAnchors; value resolved
                from source via FactValueResolver when needed).

See the plugin header (XbrlModel/__init__.py) and SAVEMODEL_IMPLEMENTATION_PLAN.md for details.
'''
import os, io, json, cbor2, pandas as pd
from decimal import Decimal
import tkinter
from collections import OrderedDict
from typing import GenericAlias, Optional, Union, _UnionGenericAlias, get_origin
from arelle.ModelValue import qname, QName, timeInterval
from ordered_set import OrderedSet
from .ViewXbrlTaxonomyObject import ViewXbrlTxmyObj
from .XbrlConst import qnBuiltInCoreObjectsTaxonomy
from .XbrlObject import XbrlModelClass
from .XbrlModel import XbrlCompiledModel
from .XbrlModule import XbrlModule
from .XbrlTypes import DefaultTrue, DefaultFalse, DefaultZero
from .PruneModel import pruneClosure, pruneSkip

# A serialized full model is emitted as a compiled model (documentType .../2026/compiled):
# it owns the entire discovered closure across namespaces and therefore MUST NOT carry
# importedTaxonomies / importMapping / documentNamespacePrefix (the import closure is
# assembled into the single model, not imported). See XbrlModel/__init__.py load checks.
COMPILED_DOCTYPE = "https://xbrl.org/2026/compiled"

# Module-object keys a compiled model MUST NOT carry; dropped when serializing/merging
# modules into a single compiled xbrlModel object.
_COMPILED_STRIP_KEYS = frozenset({"importedTaxonomies", "referenceModel"})

# Scalar module metadata carried onto the merged compiled model from the entry module.
_MODULE_SCALAR_KEYS = ("frameworkName", "version", "modelType", "duplicateFactsInModel")


def _jsonDefault(o):
    """json.dump fallback for any value saveableValue did not already reduce to a JSON-native type
    (defence-in-depth: json has no native Decimal emitter). A Decimal serializes as a number -- a
    whole value as an int (order 1, not 1.0) -- and anything else as its string form."""
    if isinstance(o, Decimal):
        return int(o) if o.is_finite() and o == o.to_integral_value() else float(o)
    return str(o)


def saveableValue(val, mdlPropName, **kwargs):
    """ Convert a value into a saveable form.
        For QName, convert to string and track namespaces.
        For Decimal, convert to float for json but not cbor.
        For bool, keep as bool for cbor but convert to string for json.
        For other types, convert to string.
    """
    if isinstance(val, QName):
        if "txmyModuleName" in kwargs and "txmyPrefixes" in kwargs and val.prefix:
            txmyPrefixes = kwargs["txmyPrefixes"]
            txmyModuleName = str(kwargs["txmyModuleName"])
            if txmyModuleName not in txmyPrefixes: txmyPrefixes[txmyModuleName] = {}
            txmyPrefixes[txmyModuleName][val.prefix] = val.namespaceURI
        return str(val)
    elif isinstance(val, (Decimal, int, float, bool)) and kwargs["fileExt"] == ".cbor":
        return val # CBOR needs binary objects
    elif isinstance(val, bool):
        return val
    elif isinstance(val, Decimal):
        if kwargs["fileExt"] == ".json":
            return float(val)
        return val
    elif isinstance(val, int): # order etc
        return val
    elif isinstance(val, float): # a numeric value (e.g. a relationship order) must stay a number
        return int(val) if val.is_integer() else val
    return str(val)

def unitDimensionString(unitQnTuple, mdlPropName, **kwargs):
    """The OIM unit string for a parsed xbrl:unit dimension value, or None if there is none.

    Fact validation REPLACES the xbrl:unit dimension's string with the parsed
    (numeratorQNames, denominatorQNames) tuple it checked (ValidateFacts, parseUnitString), so a
    model serialized after validation would otherwise emit a Python tuple repr --
    "((iso4217:USD,), ())" -- in place of "iso4217:USD". Consumers read the unit as a QName
    string, and a repr is silently not one.

    Inverse of parseUnitString: measures joined by "*", a group of more than one parenthesized,
    numerator and denominator separated by "/". Each QName goes through saveableValue so its
    prefix is registered in the emitted documentInfo.namespaces.
    """
    numeratorQns, denominatorQns = unitQnTuple
    def group(qns):
        measures = "*".join(saveableValue(qn, mdlPropName, **kwargs) for qn in qns)
        return "({})".format(measures) if len(qns) > 1 else measures
    numerator = group(numeratorQns)
    if not numerator:
        return None  # ((),()) is what parseUnitString returns for a unit it could not resolve
    denominator = group(denominatorQns)
    return "{}/{}".format(numerator, denominator) if denominator else numerator


def saveableObjects(mdlObj, mdlName, **kwargs):
    """ Recursively convert XbrlModelClass objects into saveable dicts, skipping properties with default values.
        Track visited objects to avoid cycles. Skip empty OrderedSet properties.
        Skip txmyMdl and layout properties which are not needed to save.
    """
    if "visited" not in kwargs:
        kwargs["visited"] = set()
    if mdlObj in kwargs["visited"]:
        return # cycle
    kwargs["visited"].add(mdlObj)
    saveableObj = OrderedDict()
    if isinstance(mdlObj, XbrlModule):
        kwargs["txmyModuleName"] = mdlObj.name
    # Skip the first (parent back-reference) property generically -- every child object
    # names its owner as its first annotation (module/factValue/fact/compiledModel ...);
    # serializing it would recurse back up the ownership chain.
    for propName, propType in type(mdlObj).propertyNameTypes(skipParentProperty=True):
        mdlPropName = f"{mdlName}.{propName}" if mdlName else propName
        propVal = getattr(mdlObj, propName, ())
        if propVal is None:
            continue # absent optional property -- omit per OIM present/absent convention
        if isinstance(propVal, OrderedSet) and not propVal:
            continue # empty OrderedSet, skip it
        if isinstance(propVal, (set, list, OrderedSet)):
            if propVal:  # not empty
                retained = kwargs.get("retained") # None for FULL mode -> pruneSkip never drops
                reportMode = kwargs.get("reportMode", False)
                saveVal = []
                for setObj in propVal:
                    if isinstance(setObj, XbrlModelClass):
                        if pruneSkip(setObj, retained, reportMode):
                            continue # outside the prune closure
                        saveVal.append(saveableObjects(setObj, mdlPropName, **kwargs))
                    else:
                        saveVal.append(saveableValue(setObj, mdlPropName, **kwargs))
                if saveVal: # omit a collection emptied entirely by pruning
                    saveableObj[propName] = saveVal
        elif isinstance(propVal, (dict, OrderedDict)):
            # Map-typed property (factDimensions, factQualifier, template columns ...) --
            # serialize as a JSON object preserving keys; QName keys/values track namespaces.
            if propVal: # skip empty map (absent convention)
                saveVal = OrderedDict()
                saveableObj[propName] = saveVal
                for objName, objVal in propVal.items():
                    if objName == qnBuiltInCoreObjectsTaxonomy:
                        continue
                    # Validation caches derived values back into factDimensions under
                    # underscore-prefixed keys (_periodValue, the parsed form of xbrl:period).
                    # They are working state, not model content: emitting them puts a key no
                    # consumer knows beside the real dimension, and a consumer that treats
                    # unrecognized keys as taxonomy-defined dimensions -- as the ixbrl-viewer
                    # adapter does -- gives every fact a dimension it does not have.
                    if isinstance(objName, str) and objName.startswith("_"):
                        continue
                    keyStr = (saveableValue(objName, mdlPropName, **kwargs)
                              if isinstance(objName, QName) else str(objName))
                    if keyStr == "xbrl:unit" and isinstance(objVal, tuple):
                        unitStr = unitDimensionString(objVal, mdlPropName, **kwargs)
                        if unitStr is not None:
                            saveVal[keyStr] = unitStr
                    elif isinstance(objVal, XbrlModelClass):
                        saveVal[keyStr] = saveableObjects(objVal, mdlPropName, **kwargs)
                    else:
                        saveVal[keyStr] = saveableValue(objVal, mdlPropName, **kwargs)
        elif propName not in ("txmyMdl", "layout"):
            if isinstance(propVal, XbrlModelClass):
                # Singleton object property (e.g. the groupTree). Honour the prune closure
                # like collection members do, so a partial model does not emit a groupTree
                # whose target groups were pruned away (dangling references).
                if pruneSkip(propVal, kwargs.get("retained"), kwargs.get("reportMode", False)):
                    continue
                saveableObj[propName] = saveableObjects(propVal, mdlPropName, **kwargs)
            elif (((get_origin(propType) is Union) or isinstance(get_origin(propType), type(Union))) and # Optional[ ] type
                   ((propType.__args__[-1] == type(None) and propVal is None) or
                    (propType.__args__[-1] == DefaultTrue and propVal == True) or
                    (propType.__args__[-1] == DefaultFalse and propVal == False) or
                    (propType.__args__[-1] == DefaultZero and propVal == 0))):
                continue # skip this property
            else:
                saveableObj[propName] = saveableValue(propVal, mdlPropName,  **kwargs)
    if isinstance(mdlObj, XbrlModule):
        del kwargs["txmyModuleName"]
    kwargs["visited"].discard(mdlObj)
    return saveableObj

def mergeModulesToCompiled(moduleDicts):
    """ Merge the serialized per-module dicts into a single compiled xbrlModel object.
        Object-collection lists are unioned per key; compiled-forbidden keys (importedTaxonomies,
        referenceModel) are dropped; the entry module (last in the model's xbrlModels order)
        supplies name + scalar metadata. For a single already-compiled module this is an identity
        merge (the common case: a compiled model owns its whole closure in one module).
    """
    if not moduleDicts:
        return OrderedDict()
    entryDict = moduleDicts[-1] # entry point taxonomy is last in the model's module order
    merged = OrderedDict()
    merged["name"] = entryDict.get("name")
    for k in _MODULE_SCALAR_KEYS:
        if k in entryDict:
            merged[k] = entryDict[k]
    for md in moduleDicts:
        for key, val in md.items():
            if key in _COMPILED_STRIP_KEYS or key in ("name", "modelForm") or key in _MODULE_SCALAR_KEYS:
                continue
            if isinstance(val, list):
                merged.setdefault(key, []).extend(val)
            else:
                merged.setdefault(key, val) # scalar / single nested object: first module wins
    # modelForm is not a serialized schema property -- the compiled documentType conveys it.
    return merged

def collectSourceMappings(txmyMdl, sourceUrlRewrite=None):
    """ Re-emit documentInfo.sourceMappings from each module's parsed _sourceMappings
        (SimpleNamespace(sourceName=QName, url=absoluteUrl), built at load time). Must-retain:
        the sourceName -> document-file URL binding a consumer needs to locate fact-value text.

        The url as loaded is absolute, and for an entry point inside an archive it is the
        archive's own path -- neither of which a consumer of the saved model can fetch.
        sourceUrlRewrite, when given, is called as rewrite(sourceName, url) and returns the URL
        to emit (or None to emit the url unchanged); ViewerLaunch uses it to name the document
        it staged beside the model.
    """
    seen = set()
    out = []
    for module in txmyMdl.xbrlModels.values():
        for sm in getattr(module, "_sourceMappings", None) or ():
            sn = str(sm.sourceName) if getattr(sm, "sourceName", None) is not None else None
            url = getattr(sm, "url", None)
            if sourceUrlRewrite is not None:
                url = sourceUrlRewrite(sn, url) or url
            key = (sn, url)
            if key in seen:
                continue
            seen.add(key)
            entry = OrderedDict()
            if sn is not None:
                entry["sourceName"] = sn
            if url:
                entry["url"] = url
            out.append(entry)
    return out

def buildDocumentInfo(documentType, namespaces, sourceMappings):
    """ Build the documentInfo object for a serialized compiled model. namespaces is trimmed
        to prefixes actually referenced by the emitted objects; sourceMappings retained when present.
    """
    docInfo = OrderedDict()
    docInfo["documentType"] = documentType
    docInfo["namespaces"] = namespaces
    if sourceMappings:
        docInfo["sourceMappings"] = sourceMappings
    return docInfo

def resolveMissingFactValues(txmyMdl):
    """ REPORT tailoring pre-pass: for factValues that carry valueSources but no computed value,
        resolve the source-document text via FactValueResolver so a pre-computed value can be
        emitted (both ixbrl-viewer and SEC ixviewer-plus read a pre-computed value; neither runs
        ix transforms). Returns {str(factValue.name): resolvedText}; unresolvable ones are omitted.
    """
    from .FactValueResolver import validateAndResolveValueSources
    resolved = {}
    for module in txmyMdl.xbrlModels.values():
        for fact in getattr(module, "facts", None) or ():
            for factValue in getattr(fact, "factValues", None) or ():
                if getattr(factValue, "value", None) is None and (getattr(factValue, "valueSources", None)):
                    try:
                        deferred, text = validateAndResolveValueSources(txmyMdl, fact, factValue)
                        if not deferred and text is not None:
                            resolved[str(factValue.name)] = text
                    except Exception:
                        pass # unresolvable in this context -> leave the value absent
    return resolved

def tailorFactsToFormB(moduleDict, resolvedValues):
    """ REPORT tailoring: rewrite each factValue to the single-source-of-truth Form B
        (value + valueAnchors). The document text is no longer the source of truth, so valueSources
        are dropped; any non-empty locator (htmlElementId, pdf page/mcid) moves to valueAnchors so
        the value stays locatable. A value absent but resolved in the pre-pass is filled in.
    """
    for fact in moduleDict.get("facts", []):
        for factValue in fact.get("factValues", []):
            if "value" not in factValue:
                resolved = resolvedValues.get(factValue.get("name"))
                if resolved is not None:
                    factValue["value"] = resolved
            # Only convert to Form B when a value is present -- dropping valueSources without a
            # value would leave an invalid (value-less, source-less) factValue. Unresolvable
            # factValues are left as Form A (valueSources) so they remain interpretable.
            if "value" in factValue:
                valueSources = factValue.pop("valueSources", None)
                if valueSources:
                    anchors = factValue.get("valueAnchors") or []
                    for locator in valueSources:
                        if locator: # non-empty locator properties become an anchor
                            anchors.append(locator)
                    if anchors:
                        factValue["valueAnchors"] = anchors

def collectCubeContents(txmyMdl):
    """derivedContent.cubeContents: the fact objects whose dimensions match each cube.

    Derived content is content a processor COMPUTES from a compiled model and publishes
    alongside it -- a checkable, regenerable cache of a derivation the model already implies,
    carrying no authority of its own (oim-taxonomy-derived.md). It is a document-level sibling
    of documentInfo and xbrlModel, NOT part of the XBRL model, because it is not the filer's
    content: the model stays exactly what was reported, and what processing added sits beside it.

    The association is taken from each cube's _cellFacts, which fact validation populates by
    the normative dimensional rule as it resolves each fact -- so this publishes what this
    processor actually matched, which is the thing a consumer would want to check. An
    unvalidated model has no _cellFacts and yields no cube contents, which is correct: absence
    means "not published, derive it yourself", never "no fact matches this cube".

    Facts are grouped as an array per cube rather than one object per (cube, fact) pair: on a
    1.3 MB compiled 10-K that is ~12.6 kB against ~76 kB, and only the former scales to a
    66,000-fact filing.
    """
    cubeContents = []
    for module in txmyMdl.xbrlModels.values():
        for cubeObj in getattr(module, "cubes", None) or ():
            cellFacts = getattr(cubeObj, "_cellFacts", None)
            if not cellFacts:
                continue
            factNames = OrderedSet()
            for bucket in cellFacts.values():
                for fact, _factValue in bucket:
                    name = getattr(fact, "name", None)
                    if name is not None:
                        factNames.add(str(name))
            if factNames:
                cubeContents.append(OrderedDict((("cubeName", str(cubeObj.name)),
                                                 ("facts", list(factNames)))))
    return cubeContents


def buildDerivedContent(txmyMdl):
    """The derivedContent object for a saved compiled model, or None when nothing was derived.

    Returns None rather than an empty object: a derived content object that records nothing is
    indistinguishable from one whose producer derived nothing, and the spec is explicit that
    absence means "derive it yourself".
    """
    cubeContents = collectCubeContents(txmyMdl)
    if not cubeContents:
        return None
    derived = OrderedDict()
    derived["cubeContents"] = cubeContents
    return derived


def saveFiles(cntlr, txmyMdl, fileName, saveMode="full", sourceUrlRewrite=None, **kwargs):
    """ Save a loaded XbrlCompiledModel (taxonomy objects + facts) to json, cbor or Excel.
        FULL mode: the entire model as a single compiled document -- every discovered object
        and all facts, serialized as loaded. The model's modules (txmyMdl.xbrlModels) are merged
        into one compiled xbrlModel object. For GUI, file name/type is chosen in the dialog;
        for command line they are provided as arguments.
    """
    fileExt = os.path.splitext(fileName)[1].lower()
    reportMode = saveMode == "report"
    # PRUNE / REPORT modes serialize only the fact-reachability closure; FULL keeps everything
    # (retained=None). REPORT additionally includes presentation networks (decision 4a). Namespaces
    # trim automatically -- only QNames of emitted objects are tracked during serialization.
    retained = (pruneClosure(txmyMdl, includeNetworks=reportMode)
                if saveMode in ("prune", "report") else None)
    resolvedValues = resolveMissingFactValues(txmyMdl) if reportMode else {}
    txmyPrefixes = {} # module name (str) -> {prefix: namespaceURI}, populated during serialization
    moduleObjs = list(txmyMdl.xbrlModels.values())
    moduleDicts = [saveableObjects(m, "", txmyPrefixes=txmyPrefixes, fileExt=fileExt,
                                   retained=retained, reportMode=reportMode, **kwargs)
                   for m in moduleObjs]
    if reportMode: # rewrite facts to Form B (value + valueAnchors) before merging
        for moduleDict in moduleDicts:
            tailorFactsToFormB(moduleDict, resolvedValues)
    mergedModel = mergeModulesToCompiled(moduleDicts)
    namespaces = OrderedDict()
    for m in moduleObjs:
        for prefix, ns in txmyPrefixes.get(str(m.name), {}).items():
            namespaces.setdefault(prefix, ns)
    docInfo = buildDocumentInfo(COMPILED_DOCTYPE, namespaces,
                                collectSourceMappings(txmyMdl, sourceUrlRewrite))
    oimModel = OrderedDict((("documentInfo", docInfo), ("xbrlModel", mergedModel)))
    # derivedContent is a document-level SIBLING of documentInfo and xbrlModel, not part of the
    # model: it carries what this processor computed (which facts matched which cube, and in
    # later steps the values it derived and the verdicts it reached), so the model itself stays
    # the filer's content. Emitted only where there is something to record.
    derivedContent = buildDerivedContent(txmyMdl)
    if derivedContent is not None:
        oimModel["derivedContent"] = derivedContent
    if fileExt == ".json":
        with io.open(fileName, "w") as fp:
            json.dump(oimModel, fp, indent=3, default=_jsonDefault)
    elif fileExt == ".cbor":
        with io.open(fileName, "wb") as fp:
            cbor2.dump(oimModel, fp, value_sharing=True, string_referencing=True)
    elif fileExt == ".xlsx":
        with pd.ExcelWriter(fileName, mode='w', engine="openpyxl") as writer:
            for key, val in mergedModel.items():
                if isinstance(val, (list, set, OrderedSet, OrderedDict)):
                    df = pd.json_normalize(val, max_level=8)
                    df.to_excel(writer, sheet_name=key[:31], index=False) # Excel sheet-name limit



_SAVE_MODE_CHOICES = (
    ("full",   "Full — every object and all facts (compiled model)"),
    ("prune",  "Prune — only objects needed to interpret the reported facts"),
    ("report", "Report — pruned + viewer-tailored facts (value + anchors) + presentation networks + cubes"),
)

def askSaveMode(cntlr, default="full"):
    """ GUI modal: choose the save mode (full | prune | report). Returns the chosen mode, or
        None if the user cancelled. Fully defensive -- any tkinter failure falls back to default.
    """
    try:
        from tkinter import Toplevel, StringVar, Radiobutton, Label, Frame, Button, W
        parent = getattr(cntlr, "parent", None) or cntlr
        dlg = Toplevel(parent)
        dlg.title(_("Save model"))
        dlg.transient(parent)
        modeVar = StringVar(dlg, value=default)
        result = {"mode": None}
        Label(dlg, text=_("Choose how much of the model to serialize:"), justify="left"
              ).grid(row=0, column=0, padx=12, pady=(12, 6), sticky=W)
        for i, (val, text) in enumerate(_SAVE_MODE_CHOICES):
            Radiobutton(dlg, text=_(text), variable=modeVar, value=val, justify="left"
                        ).grid(row=1 + i, column=0, padx=16, pady=2, sticky=W)
        def _ok():
            result["mode"] = modeVar.get(); dlg.destroy()
        def _cancel():
            result["mode"] = None; dlg.destroy()
        btns = Frame(dlg); btns.grid(row=1 + len(_SAVE_MODE_CHOICES), column=0, pady=(10, 12))
        Button(btns, text=_("OK"), width=8, command=_ok).grid(row=0, column=0, padx=6)
        Button(btns, text=_("Cancel"), width=8, command=_cancel).grid(row=0, column=1, padx=6)
        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        dlg.grab_set()
        dlg.wait_window(dlg)
        return result["mode"]
    except Exception:
        return default

def xbrlModelSave(cntlr, view, fileType=None, fileName=None, *args, **kwargs):
    """ CntlrWinMain.Xbrl.Save:
        Save OIM Taxonomy Model into json, cbor and Excel files.
        For GUI, always ask file name and type to save. For command line, file name and type must be provided as arguments.
    """
    if not isinstance(view, ViewXbrlTxmyObj): # only save OIM Taxonomy Views
        return False # not an OIM Taxonomy View
    txmyMdl = view.xbrlCompMdl
    parameters = cntlr.modelManager.formulaOptions.typedParameters({})
    # for GUI always ask file name and type to save
    if cntlr.hasGui and not fileName:
        fileName = cntlr.uiFileDialog("save",
                title="Save OIM Taxonomy",
                initialdir=cntlr.config.setdefault("saveOimTaxonomy","."),
                filetypes=[(_("OIM Taxonomy json"), "*.json"), (_("OIM Taxonomy cbor .cbor"), "*.cbor"), (_("Excel .xlsx"), "*.xlsx"), (_("HTML table .html"), "*.html"), (_("HTML table .htm"), "*.htm")],
                defaultextension=".xlsx")
    if fileName is not None:
        # saveMode selects what to serialize: full | prune | report (see SAVEMODEL plan). A formula
        # parameter oimSaveMode overrides (CLI/scripted); otherwise the GUI prompts with a modal.
        saveMode = (parameters.get(qname("oimSaveMode",noPrefixIsNoNamespace=True),('',''))[1] or "").lower()
        if not saveMode:
            if cntlr.hasGui:
                saveMode = askSaveMode(cntlr, default="full")
                if saveMode is None:
                    return False # user cancelled the mode dialog
            else:
                saveMode = "full"
        if saveMode not in ("full", "prune", "report"):
            saveMode = "full"
        saveFiles(cntlr, txmyMdl, fileName, saveMode=saveMode)
        return True
    return False # no action by this plugin
