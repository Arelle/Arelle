'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import *
try:
    from tkinter.ttk import *
except ImportError:
    from ttk import *
import os
from arelle import (ViewWinTree, ModelDocument, XmlUtil)
from arelle.ViewUtil import sortCountExpected

def viewTests(modelXbrl, tabWin):
    view = ViewTests(modelXbrl, tabWin)
    modelXbrl.modelManager.showStatus(_("viewing Tests"))
    view.treeView["columns"] = ("name", "readMeFirst", "infoset", "status", "call", "test", "expected", "actual")
    view.treeView.column("#0", width=150, anchor="w")
    view.treeView.heading("#0", text="ID")
    view.treeView.column("name", width=150, anchor="w")
    view.treeView.heading("name", text="Name")
    view.treeView.column("readMeFirst", width=75, anchor="w")
    view.treeView.heading("readMeFirst", text="ReadMeFirst")
    view.treeView.column("infoset", width=75, anchor="w")
    view.treeView.heading("infoset", text="Infoset File")
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
    modelDocument = modelXbrl.modelDocument
    if modelXbrl.modelDocument.type in (ModelDocument.Type.REGISTRY, ModelDocument.Type.REGISTRYTESTCASE):
        if modelXbrl.modelDocument.xmlRootElement.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms":
            view.treeView["displaycolumns"] = ("status", "call", "test", "expected", "actual")
            view.isTransformRegistry = True
        else:
            view.treeView["displaycolumns"] = ("name", "readMeFirst", "status", "call", "test", "expected", "actual")
    elif modelXbrl.modelDocument.type == ModelDocument.Type.XPATHTESTSUITE:
        view.treeView["displaycolumns"] = ("name", "readMeFirst", "status", "call", "test", "expected", "actual")
    else:
        # check if infoset needed
        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            hasInfoset = any(getattr(refDoc, "outpath", None)  for refDoc in modelDocument.referencesDocument)
        else:
            hasInfoset = bool(getattr(modelDocument, "outpath", None))
        view.treeView["displaycolumns"] = (("name", "readMeFirst") +
                                           ( ("infoset",) if hasInfoset else () ) +
                                           ( "status", "expected", "actual"))

    menu = view.contextMenu()
    view.menuAddExpandCollapse()
    view.menuAddClipboard()
    view.id = 0
    view.viewTestcaseIndexElement(modelDocument, "")
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')

class ViewTests(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin):
        super(ViewTests, self).__init__(modelXbrl, tabWin, "Tests", True)

    def viewTestcaseIndexElement(self, modelDocument, parentNode, parentNodeText=None):
        self.id += 1
        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            nodeText = os.path.basename(modelDocument.uri)
            if nodeText == parentNodeText: # may be same name, index.xml, use directory name instead
                nodeText = os.path.basename(os.path.dirname(modelDocument.uri))
            node = self.treeView.insert(parentNode, "end", modelDocument.objectId(self.id),
                                        text=nodeText, tags=("odd",))
            self.id += 1;
            # sort test cases by uri
            testcases = []
            for referencedDocument, _ref in sorted(modelDocument.referencesDocument.items(),
                                                   key=lambda i:i[1].referringModelObject.objectIndex if i[1] else 0):
                if referencedDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
                    self.viewTestcaseIndexElement(referencedDocument, node, nodeText)
                else:
                    testcases.append((referencedDocument.uri, referencedDocument.objectId()))
            testcases.sort()
            for i, testcaseTuple in enumerate(testcases):
                self.viewTestcase(self.modelXbrl.modelObject(testcaseTuple[1]), node, i)
        elif modelDocument.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
            self.viewTestcase(modelDocument, parentNode, 1)
        elif modelDocument.type == ModelDocument.Type.XPATHTESTSUITE:
            for i, elt in enumerate(modelDocument.xmlRootElement.iterchildren(tag="{http://www.w3.org/2005/02/query-test-XQTSCatalog}test-group")):
                self.viewTestGroup(elt, parentNode, i)
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

    def viewTestGroup(self, group, parentNode, n):
        node = self.treeView.insert(parentNode, "end", group.objectId(),
                                    text=group.get("name"),
                                    tags=("odd" if n & 1 else "even",))
        titleElt = XmlUtil.child(group, None, "title")
        if titleElt is not None:
            self.treeView.set(node, "name", titleElt.text)
        self.id += 1;
        i = -1
        for elt in group.iterchildren(tag="{http://www.w3.org/2005/02/query-test-XQTSCatalog}test-group"):
            i = i + 1
            self.viewTestGroup(elt, node, n + i + 1)
        for elt in group.iterchildren(tag="{http://www.w3.org/2005/02/query-test-XQTSCatalog}test-case"):
            if elt.get("is-XPath2") == "true":
                i = i + 1
                self.viewTestcaseVariation(elt, node, n + i + 1)

    def viewTestcaseVariation(self, modelTestcaseVariation, parentNode, n):
        if self.isTransformRegistry or modelTestcaseVariation.localName in ("testGroup", "test-case"):
            id = modelTestcaseVariation.name
        else:
            id = modelTestcaseVariation.id
            if id is None:
                id = ""
        node = self.treeView.insert(parentNode, "end", modelTestcaseVariation.objectId(),
                                    text=id,
                                    tags=("odd" if n & 1 else "even",))
        self.treeView.set(node, "name", (modelTestcaseVariation.description or modelTestcaseVariation.name))
        self.treeView.set(node, "readMeFirst", ",".join(str(uri) for uri in modelTestcaseVariation.readMeFirstUris))
        self.treeView.set(node, "status", modelTestcaseVariation.status)
        call = modelTestcaseVariation.cfcnCall
        if call: self.treeView.set(node, "call", call[0])
        test = modelTestcaseVariation.cfcnTest
        if test:
            self.treeView.set(node, "test", test[0])
        if getattr(self.modelXbrl.modelDocument, "outpath", None) and modelTestcaseVariation.resultIsInfoset:
            self.treeView.set(node, "infoset", modelTestcaseVariation.resultInfosetUri)
        _exp = sortCountExpected(modelTestcaseVariation.expected)
        self.treeView.set(node, "expected",
                          ", ".join(str(e) for e in _exp) if isinstance(_exp, list) else _exp)
        self.treeView.set(node, "actual", ", ".join(modelTestcaseVariation.actual))
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
                    self.treeView.set(testcaseVariationId, "actual", ", ".join(
                          str(code) for code in modelObject.actual))
                self.treeView.see(testcaseVariationId)
                self.treeView.selection_set(testcaseVariationId)
            self.blockViewModelObject -= 1
