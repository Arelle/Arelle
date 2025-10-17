'''
See COPYRIGHT.md for copyright information.

Saves OIM Taxonomy Model into json, cbor and Excel

'''
import os
import tkinter
from collections import OrderedDict
from typing import GenericAlias
from arelle.PythonUtil import  OrderedSet
from .ViewXbrlTaxonomyObject import ViewXbrlTxmyObj
from .XbrlObject import XbrlObject
from .XbrlTaxonomyModel import XbrlTaxonomyModel
from .XbrlTaxonomyModule import XbrlTaxonomyModule
from arelle.plugin.xule.XuleServer import sep


def saveableObjects(mdlObj, **kwargs):
    saveableObj = OrderedDict()
    # fpr taxonomyModel, combine the objects of taxonomyModules and possibly sort by namespace
    for propName, propType in type(mdlObj).propertyNameTypes():
        propVal = getattr(mdlObj, propName, ())
        if isinstance(propVal, (set, list, dict)):
            saveVal = []
            saveableObj[propName] = saveVal
            for setObj in (propVal.values() if hasattr(propVal,"values") else propVal):
                if isinstance(setObj, XbrlObject):
                    saveVal.append(saveableObjects(setObj, **kwargs))
                else:
                    saveVal.append(setObj)
        elif propName not in ("txmyMdl", "layout"):
            if isinstance(propVal, XbrlObject):
                saveableObj[propName] = saveableObjects(propVal, **kwargs)
            else:
                saveableObj[propName] = propVal
    print(f"obj {type(mdlObj)} val {saveableObj}")
    return saveableObj
    
def saveXlsx(cntlr, txmyMdl, fileName):
    # nested sheet for each OrderedSet of XbrlTaxonomyModule object
    objs = saveableObjects(txmyMdl, isXlsx=True)

def saveJson(cntlr, txmyMdl, fileName, **kwargs):
    # nested sheet for each OrderedSet of XbrlTaxonomyModule object
    objs = saveableObjects(txmyMdl, isJson=True, **kwargs)

def saveCbor(cntlr, txmyMdl, fileName, sparateNamespaces):
    # nested sheet for each OrderedSet of XbrlTaxonomyModule object
    objs = saveableObjects(txmyMdl, isCbor=True, **kwargs)

    
    
def oimTaxonomySave(cntlr, view, fileType=None, fileName=None, *args, **kwargs):
    if not isinstance(view, ViewXbrlTxmyObj):
        return False # not an OIM Taxonomy View
    txmyMdl = view.xbrlTxmyMdl
    # for GUI always ask file name and type to save
    if cntlr.hasGui and not fileName:
        filenName = self.uiFileDialog("save",
                title="Save OIM Taxonomy",
                initialdir=initialdir,
                filetypes=[(_("OIM Taxonomy json"), "*.json"), (_("OIM Taxonomy cbor .cbor"), "*.cbor"), (_("Excel .xlsx"), "*.xlsx"), (_("HTML table .html"), "*.html"), (_("HTML table .htm"), "*.htm")],
                defaultextension=".xlsx")
    if fileName is not None:
        fileExt = os.path.splitext(fileName)[1].lower()
        if fileExt == ".xlsx":
            saveModelXlsx(cntlr, txmyMdl, filename)
            return True
        # ask if namespaces are to be separated
        if cntlr.hasGui:
            sparateNamespaces = True # tkinter.messagebox.askyesnocancel(_("Save OIM Taxonomy"), _("Combine all namespaces into single reloadable model file?"))
        else:
            sparateNamespaces = True
        if sparateNamespaces is None:
            return False
        elif fileExt == ".xlsx":
            saveXlsx(cntlr, txmyMdl, fileName)
            return True
        elif fileExt == ".json":
            saveJson(cntlr, txmyMdl, fileName, sparateNamespaces=sparateNamespaces)
            return True
        elif fileExt == ".cbor":
            saveCbor(cntlr, txmyMdl, fileName, sparateNamespaces=sparateNamespaces)
            return True
    return False # no action by this plugin
