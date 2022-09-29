'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
import os
from arelle import ViewWinTree, ModelObject, XbrlConst
from arelle.ModelFormulaObject import (ModelParameter, ModelVariable, ModelVariableSet,
                                       ModelVariableSetAssertion, ModelConsistencyAssertion)
from arelle.ModelDtsObject import ModelRelationship
from arelle.ViewUtilFormulae import rootFormulaObjects, formulaObjSortKey

def viewFormulae(modelXbrl, tabWin):
    modelXbrl.modelManager.showStatus(_("viewing formulas"))
    view = ViewFormulae(modelXbrl, tabWin)
    view.view()

class ViewFormulae(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin):
        super(ViewFormulae, self).__init__(modelXbrl, tabWin, "Formulae", True)

    def view(self):
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.tag_has = defaultdict(list) # temporary until Tk 8.6

        self.treeView["columns"] = ("label", "cover", "complement", "bindAsSequence", "expression", "value")
        self.treeView.column("#0", width=200, anchor="w")
        self.treeView.heading("#0", text="Formula object")
        self.treeView.column("label", width=150, anchor="w", stretch=False)
        self.treeView.heading("label", text="Label")
        self.treeView.column("cover", width=36, anchor="center", stretch=False)
        self.treeView.heading("cover", text="Cvr.")
        self.treeView.column("complement", width=36, anchor="center", stretch=False)
        self.treeView.heading("complement", text="Cmp.")
        self.treeView.column("bindAsSequence", width=36, anchor="center", stretch=False)
        self.treeView.heading("bindAsSequence", text="Seq.")
        self.treeView.column("expression", width=350, anchor="w")
        self.treeView.heading("expression", text="Expression")


        # root node for tree view
        self.id = 1
        self.clearTreeView()
        n = 1
        for rootObject in sorted(rootFormulaObjects(self), key=formulaObjSortKey):
            self.viewFormulaObjects("", rootObject, None, n, set())
            n += 1
        for cfQnameArity in sorted(qnameArity
                                   for qnameArity in self.modelXbrl.modelCustomFunctionSignatures.keys()
                                   if isinstance(qnameArity, (tuple,list))):
            cfObject = self.modelXbrl.modelCustomFunctionSignatures[cfQnameArity]
            self.viewFormulaObjects("", cfObject, None, n, set())
            n += 1
        self.treeView.bind("<<TreeviewSelect>>", self.treeviewSelect, '+')
        self.treeView.bind("<Enter>", self.treeviewEnter, '+')
        self.treeView.bind("<Leave>", self.treeviewLeave, '+')

        # pop up menu
        menu = self.contextMenu()
        self.menuAddExpandCollapse()
        self.menuAddClipboard()

    def viewFormulaObjects(self, parentNode, fromObject, fromRel, n, visited):
        if fromObject is None:
            return
        if isinstance(fromObject, (ModelVariable, ModelParameter)) and fromRel is not None:
            text = "{0} ${1}".format(fromObject.localName, fromRel.variableQname)
        elif isinstance(fromObject, (ModelVariableSetAssertion, ModelConsistencyAssertion)):
            text = "{0} {1}".format(fromObject.localName, fromObject.id)
        else:
            text = fromObject.localName
        childnode = self.treeView.insert(parentNode, "end", fromObject.objectId(self.id), text=text, tags=("odd" if n & 1 else "even",))
        self.treeView.set(childnode, "label", fromObject.xlinkLabel)
        if fromRel is not None and fromRel.elementQname == XbrlConst.qnVariableFilterArc:
            self.treeView.set(childnode, "cover", "true" if fromRel.isCovered else "false")
            self.treeView.set(childnode, "complement", "true" if fromRel.isComplemented else "false")
        if isinstance(fromObject, ModelVariable):
            self.treeView.set(childnode, "bindAsSequence", fromObject.bindAsSequence)
        if hasattr(fromObject, "viewExpression"):
            self.treeView.set(childnode, "expression", fromObject.viewExpression)
        self.id += 1
        if fromObject not in visited:
            visited.add(fromObject)
            relationshipArcsShown = set()  # don't show group filters twice (in allFormulaRelSet secondly
            for i, relationshipSet in enumerate((self.varSetFilterRelationshipSet,
                                                 self.allFormulaRelationshipsSet)):
                for modelRel in relationshipSet.fromModelObject(fromObject):
                    if i == 0 or modelRel.arcElement not in relationshipArcsShown:
                        toObject = modelRel.toModelObject
                        n += 1 # child has opposite row style of parent
                        self.viewFormulaObjects(childnode, toObject, modelRel, n, visited)
                        if i == 0:
                            relationshipArcsShown.add(modelRel.arcElement)
            visited.remove(fromObject)

    def getToolTip(self, tvRowId, tvColId):
        # override tool tip when appropriate
        if tvColId == "#0":
            try:
                modelObject = self.modelXbrl.modelObject(tvRowId)
                if isinstance(modelObject, ModelRelationship):
                    modelObject = modelObject.toModelObject
                return modelObject.xmlElementView
            except (AttributeError, KeyError):
                pass
        return None

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
            try:
                # get concept of fact or toConcept of relationship, role obj if roleType
                conceptId = modelObject.viewConcept.objectId()
                items = self.tag_has.get(conceptId)
                if items is not None and self.treeView.exists(items[0]):
                    self.treeView.see(items[0])
                    self.treeView.selection_set(items[0])
            except (AttributeError, KeyError):
                self.treeView.selection_set(())
            self.blockViewModelObject -= 1
