'''
See COPYRIGHT.md for copyright information.

Saves OIM Taxonomy Model into json, cbor and Excel

'''
import os
import tkinter
from typing import GenericAlias
from arelle.PythonUtil import  OrderedSet
from .ViewXbrlTaxonomyObject import ViewXbrlTxmyObj
from .XbrlTaxonomyModel import XbrlTaxonomyModel
from .XbrlTaxonomyModule import XbrlTaxonomyModule
from arelle.plugin.xule.XuleServer import sep


def savableObjects(mdlObj, sparateNamespaces, isXlsx=False, isJson=False, isCbor=False):
    if isinstance(mdlObj, XbrlTaxonomyModel):
        return dict((txmy.name, savableObjects(txmy, sparateNamespaces, isXlsx, isJson, isCbor))
                    for txmy in mdlObj.taxonomies.values())
    objProps = []
    objSets = []
    for propName, propType in type(mdlObj).propertyNameTypes():
        if isinstance(propType, GenericAlias) and propType.__origin__ == OrderedSet:
            objSets.append(propName)
        elif propName not in ("txmyMdl", "layout"):
            objProps.append(propName)
    print(f"obj {type(mdlObj)} props {objProps} sets {objSets}")
    
def saveXlsx(cntlr, txmyMdl, fileName):
    # nested sheet for each OrderedSet of XbrlTaxonomyModule object
    objs = savableObjects(txmyMdl, True, isXlsx=True)

def saveJson(cntlr, txmyMdl, fileName, sparateNamespaces):
    # nested sheet for each OrderedSet of XbrlTaxonomyModule object
    objs = savableObjects(txmyMdl, sparateNamespaces, isJson=True)

def saveCbor(cntlr, txmyMdl, fileName, sparateNamespaces):
    # nested sheet for each OrderedSet of XbrlTaxonomyModule object
    objs = savableObjects(txmyMdl, sparateNamespaces, isCbor=True)

    
    
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
            saveJson(cntlr, txmyMdl, fileName, sparateNamespaces)
            return True
        elif fileExt == ".cbor":
            saveCbor(cntlr, txmyMdl, fileName, sparateNamespaces)
            return True
    return False # no action by this plugin
