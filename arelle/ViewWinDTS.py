'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import *
try:
    from tkinter.ttk import *
except ImportError:
    from ttk import *
import os
from arelle import ModelDocument, ViewWinTree

def viewDTS(modelXbrl, tabWin, altTabWin=None):
    view = ViewDTS(modelXbrl, tabWin)
    modelXbrl.modelManager.showStatus(_("viewing DTS"))
    view.view()

    menu = view.contextMenu()
    view.menuAddExpandCollapse()
    view.menuAddClipboard()
    view.menuAddViews(addClose=False, tabWin=altTabWin)

class ViewDTS(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin):
        super(ViewDTS, self).__init__(modelXbrl, tabWin, "DTS", True)

    def view(self):
        self.clearTreeView()
        self.viewDtsElement(self.modelXbrl.modelDocument, "", 1, set(), {self.modelXbrl.modelDocument})


    def viewDtsElement(self, modelDocument, parentNode, n, parents, siblings):
        if modelDocument.type == ModelDocument.Type.INLINEXBRLDOCUMENTSET:
            if modelDocument.entrypoint is not None and "id" in modelDocument.entrypoint:
                text = f"{modelDocument.entrypoint['id']} (IXDS)"
            else:
                text = "Inline XBRL Document Set" # no file name or ID to display
        else:
            text = "{0} - {1}".format(os.path.basename(modelDocument.uri), modelDocument.gettype())
        node = self.treeView.insert(parentNode, "end",
                    text=text,
                    tags=("odd" if n & 1 else "even",))
        children = modelDocument.referencesDocument.keys()
        childFamily = parents | siblings
        for i, referencedDocument in enumerate(sorted(children, key=lambda d: d.objectIndex)): # provide consistent order
            if referencedDocument not in parents:
                self.viewDtsElement(referencedDocument, node, n + i + 1, childFamily, children)

    def viewModelObject(self, modelObject):
        pass
