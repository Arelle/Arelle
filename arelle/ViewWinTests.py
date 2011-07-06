'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
from tkinter.ttk import *
import os
from arelle import (ViewWinTree, ModelDocument)

def viewTests(modelXbrl, tabWin):
    view = ViewTests(modelXbrl, tabWin)
    modelXbrl.modelManager.showStatus(_("viewing Tests"))
    view.treeView["columns"] = ("name", "readMeFirst", "status", "call", "test", "expected", "actual")
    view.treeView.column("#0", width=150, anchor="w")
    view.treeView.heading("#0", text="ID")
    view.treeView.column("name", width=150, anchor="w")
    view.treeView.heading("name", text="Name")
    view.treeView.column("readMeFirst", width=75, anchor="w")
    view.treeView.heading("readMeFirst", text="ReadMeFirst")
    view.treeView.column("status", width=80, anchor="w")
    view.treeView.heading("status", text="Status")
    view.treeView.column("call", width=150, anchor="w")
    view.treeView.heading("call", text="Call")
    view.treeView.column("test", width=100, anchor="w")
    view.treeView.heading("test", text="Test")
    view.treeView.column("expected", width=100, anchor="w")
    view.treeView.heading("expected", text="Expected")
    view.treeView.column("actual", width=100, anchor="w")
    view.treeView.heading("actual",  text="Actual")
    view.isTransformRegistry = False
    if modelXbrl.modelDocument.type in (ModelDocument.Type.REGISTRY, ModelDocument.Type.REGISTRYTESTCASE):
        if modelXbrl.modelDocument.xmlRootElement.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms":
            view.treeView["displaycolumns"] = ("status", "call", "test", "expected", "actual")
            view.isTransformRegistry = True
        else:
            view.treeView["displaycolumns"] = ("name", "readMeFirst", "status", "call", "test", "expected", "actual")
    else:
        view.treeView["displaycolumns"] = ("name", "readMeFirst", "status", "expected", "actual")
    view.viewTestcaseIndexElement(modelXbrl.modelDocument, "")
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')
    
class ViewTests(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin):
        super().__init__(modelXbrl, tabWin, "Tests", True)
        
    def viewTestcaseIndexElement(self, modelDocument, parentNode):
        self.id = 1
        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            node = self.treeView.insert(parentNode, "end", modelDocument.objectId(self.id),
                                        text=os.path.basename(modelDocument.uri), tags=("odd",))
            self.id += 1;
            # sort test cases by uri
            testcases = []
            for referencedDocument in modelDocument.referencesDocument.keys():
                testcases.append((referencedDocument.uri, referencedDocument.objectId()))
            testcases.sort()
            for i, testcaseTuple in enumerate(testcases):
                self.viewTestcase(self.modelXbrl.modelObject(testcaseTuple[1]), node, i)
        elif modelDocument.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
            self.viewTestcase(modelDocument, parentNode, 1)
        else:
            pass
                
    def viewTestcase(self, modelDocument, parentNode, n):
        node = self.treeView.insert(parentNode, "end", modelDocument.objectId(),
                                    text=os.path.basename(modelDocument.uri), 
                                    tags=("odd" if n & 1 else "even",))
        self.id += 1;
        if hasattr(modelDocument, "testcaseVariations"):
            for i, modelTestcaseVariation in enumerate(modelDocument.testcaseVariations):
                self.viewTestcaseVariation(modelTestcaseVariation, node, n + i + 1)
                
    def viewTestcaseVariation(self, modelTestcaseVariation, parentNode, n):
        if self.isTransformRegistry:
            id = modelTestcaseVariation.name
        else:
            id = modelTestcaseVariation.id
            if id is None:
                id = ""
        node = self.treeView.insert(parentNode, "end", modelTestcaseVariation.objectId(), 
                                    text=id, 
                                    tags=("odd" if n & 1 else "even",))
        self.treeView.set(node, "name", modelTestcaseVariation.name)
        self.treeView.set(node, "readMeFirst", ",".join(str(uri) for uri in modelTestcaseVariation.readMeFirstUris))
        self.treeView.set(node, "status", modelTestcaseVariation.status)
        call = modelTestcaseVariation.cfcnCall
        if call: self.treeView.set(node, "call", call[0])
        test = modelTestcaseVariation.cfcnTest
        if test: self.treeView.set(node, "test", test[0])
        self.treeView.set(node, "expected", modelTestcaseVariation.expected)
        self.treeView.set(node, "actual", " ".join(modelTestcaseVariation.actual))
        self.id += 1;
                
    def treeviewEnter(self, *args):
        self.blockSelectEvent = 0

    def treeviewLeave(self, *args):
        self.blockSelectEvent = 1

    def treeviewSelect(self, *args):
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            self.modelXbrl.viewModelObject(self.treeView.selection()[0])
            self.blockViewModelObject -= 1

    def viewModelObject(self, modelObject):
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            testcaseVariationId = modelObject.objectId()
            if self.treeView.exists(testcaseVariationId):
                if hasattr(modelObject, "status"):
                    self.treeView.set(testcaseVariationId, "status", modelObject.status)
                if hasattr(modelObject, "actual"):
                    self.treeView.set(testcaseVariationId, "actual", " ".join(
                          str(code) for code in modelObject.actual))
                self.treeView.see(testcaseVariationId)
                self.treeView.selection_set(testcaseVariationId)
            self.blockViewModelObject -= 1
