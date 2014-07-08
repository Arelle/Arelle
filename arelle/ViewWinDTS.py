'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
try:
    from tkinter.ttk import *
except ImportError:
    from ttk import *
import os
from arelle import ViewWinTree

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
        node = self.treeView.insert(parentNode, "end", 
                    text="{0} - {1}".format(
                        os.path.basename(modelDocument.uri),
                        modelDocument.gettype()), 
                    tags=("odd" if n & 1 else "even",))
        children = modelDocument.referencesDocument.keys()
        childFamily = parents | siblings
        for i, referencedDocument in enumerate(children):
            if referencedDocument not in parents:
                self.viewDtsElement(referencedDocument, node, n + i + 1, childFamily, children)
                
    def viewModelObject(self, modelObject):
        pass
