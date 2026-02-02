'''
See COPYRIGHT.md for copyright information.

Saves OIM Taxonomy Model into json, cbor and Excel

Formula parameters:
   oimTaxonomySaveSeparateNamespaces = true | yes means to save namespaces in separate files

'''
import os, io, json, cbor2, pandas as pd
from decimal import Decimal
import tkinter
from collections import OrderedDict
from typing import GenericAlias, Optional, Union, _UnionGenericAlias, get_origin
from arelle.ModelValue import qname, QName, timeInterval
from arelle.PythonUtil import  OrderedSet
from .ViewXbrlTaxonomyObject import ViewXbrlTxmyObj
from .XbrlConst import qnBuiltInCoreObjectsTaxonomy
from .XbrlObject import XbrlModelClass, XbrlObject
from .XbrlModel import XbrlCompiledModel
from .XbrlModule import XbrlModule
from .XbrlTypes import QNameKeyType, XbrlModuleType, DefaultTrue, DefaultFalse, DefaultZero

DOCINFO = {
        "documentType": "https://xbrl.org/2025/taxonomy",
        "namespaces": {
        }
    }


def saveableValue(val, mdlPropName, **kwargs):
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
    return str(val)

def saveableObjects(mdlObj, mdlName, **kwargs):
    if "visited" not in kwargs:
        kwargs["visited"] = set()
    if mdlObj in kwargs["visited"]:
        return # cycle
    kwargs["visited"].add(mdlObj)
    saveableObj = OrderedDict()
    if isinstance(mdlObj, XbrlModule):
        kwargs["txmyModuleName"] = mdlObj.name
    # fpr taxonomyModel, combine the objects of taxonomyModules and possibly sort by namespace
    for propName, propType in type(mdlObj).propertyNameTypes():
        mdlPropName = f"{mdlName}.{propName}" if mdlName else propName
        propVal = getattr(mdlObj, propName, ())
        if propType == XbrlModuleType: # first prop which references parent
            continue
        if isinstance(propVal, OrderedSet) and not propVal:
            continue # empty OrderedSet, skip it
        if isinstance(propVal, (set, list, OrderedSet)):
            if propVal:  # not empty
                saveVal = []
                saveableObj[propName] = saveVal
                for setObj in propVal:
                    if isinstance(setObj, XbrlModelClass):
                        saveVal.append(saveableObjects(setObj, mdlPropName, **kwargs))
                    else:
                        saveVal.append(saveableValue(setObj, mdlPropName, **kwargs))
        elif isinstance(propVal, (dict, OrderedDict)):
            saveVal = []
            saveableObj[propName] = saveVal
            for objName, objVal in propVal.items():
                if objName != qnBuiltInCoreObjectsTaxonomy:
                    if isinstance(objVal, XbrlModelClass):
                        saveVal.append(saveableObjects(objVal, mdlPropName, **kwargs))
                    else:
                        saveVal.append(saveableValue(objVal, mdlPropName, **kwargs))
        elif propName not in ("txmyMdl", "layout"):
            if isinstance(propVal, XbrlModelClass):
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

def saveFiles(cntlr, txmyMdl, fileName, **kwargs):
    fileExt = os.path.splitext(fileName)[1].lower()
    # nested sheet for each OrderedSet of XbrlModule object
    txmyPrefixes = {} # dict by taxonomy name by prefix
    objs = saveableObjects(txmyMdl, "", txmyPrefixes=txmyPrefixes, fileExt=fileExt, **kwargs)
    txmys = objs.get("taxonomies",())
    if kwargs.get("separateNamespaces") and txmys:
        # entry point taxonomy is last in set
        txmy = txmys[-1]
        oimTxmy = {"documentInfo": DOCINFO.copy(), "taxonomy": txmy}
        for prefix, ns in txmyPrefixes.get(txmy.get("name"),{}).items():
            oimTxmy["documentInfo"]["namespaces"][prefix] = ns
        if fileExt == ".json":
            with io.open(fileName, "w") as fp:
                json.dump(oimTxmy, fp, indent=3)
        elif fileExt == ".cbor":
            with io.open(fileName, "wb") as fp:
                cbor2.dump(oimTxmy, fp, value_sharing=True, string_referencing=True)
        # imported taxonomies
        for txmy in txmys[:-1]:
            suffix = txmy.get("name").replace(":","_")
            oimTxmy = {"documentInfo": DOCINFO.copy(),"taxonomy": txmy}
            for prefix, ns in txmyPrefixes.get(txmy.get("name"),{}).items():
                oimTxmy["documentInfo"]["namespaces"][prefix] = ns
            if fileExt == ".json":
                with io.open(f"{fileName[:-5]}_{suffix}.json", "w") as fp:
                    json.dump(oimTxmy, fp, indent=3)
            elif fileExt == ".cbor":
                with io.open(fileName, "wb") as fp:
                    cbor2.dump(oimTxmy, fp, value_sharing=True, string_referencing=True)
    else:
        combinedObjs = {"documentInfo": DOCINFO.copy(),"taxonomy": OrderedDict()}
        combinedTxmy = combinedObjs["taxonomy"]
        for txmy in txmys:
            for key, val in txmy.items():
                if isinstance(val, (set, OrderedSet)):
                    combinedTxmy.setdefault(key, OrderedSet()).update(val)
                elif isinstance(val, (list, tuple)):
                    combinedTxmy.setdefault(key, []).extend(val)
                else:
                    combinedTxmy[key] = val
            for prefix, ns in txmyPrefixes.get(txmy.get("name"),{}).items():
                combinedObjs["documentInfo"]["namespaces"][prefix] = ns
        if fileExt == ".json":
            with io.open(fileName, "w") as fp:
                json.dump(combinedObjs, fp, indent=3)
        elif fileExt == ".cbor":
            with io.open(fileName, "wb") as fp:
                cbor2.dump(combinedObjs, fp, value_sharing=True, string_referencing=True)
        elif fileExt == ".xlsx":
            with pd.ExcelWriter(fileName, mode='w', engine="openpyxl") as writer:
                for key, val in combinedTxmy.items():
                    if isinstance(val, (list, set, OrderedSet, OrderedDict)):
                        df = pd.json_normalize(val, max_level=8)
                        df.to_excel(writer, sheet_name=key, index=False)
            print("trace")



def xbrlModelSave(cntlr, view, fileType=None, fileName=None, *args, **kwargs):
    if not isinstance(view, ViewXbrlTxmyObj):
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
        fileExt = os.path.splitext(fileName)[1].lower()
        # ask if namespaces are to be separated
        separateNamespaces = bool(parameters.get(qname("oimTaxonomySaveSeparateNamespaces",noPrefixIsNoNamespace=True),('',''))[1] in ("true","yes"))
        saveFiles(cntlr, txmyMdl, fileName, separateNamespaces=separateNamespaces)
        return True
    return False # no action by this plugin
