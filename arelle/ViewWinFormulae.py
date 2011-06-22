'''
Created on Dec 6, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import os
from arelle import (ViewWinTree, ModelObject, XbrlConst)
from arelle.ModelFormulaObject import (ModelVariable)

def viewFormulae(modelXbrl, tabWin):
    modelXbrl.modelManager.showStatus(_("viewing formulas"))
    view = ViewFormulae(modelXbrl, tabWin)
    view.view()
    
class ViewFormulae(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin):
        super().__init__(modelXbrl, tabWin, "Formulae", True)
        
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

        # relationship set based on linkrole parameter, to determine applicable linkroles
        relationshipSet = self.modelXbrl.relationshipSet("XBRL-formulae")
        if relationshipSet is None or len(relationshipSet.modelRelationships) == 0:
            self.modelXbrl.modelManager.addToLog(_("no relationships for XBRL formulae"))
            return

        rootObjects = set( self.modelXbrl.modelVariableSets )
        
        # remove formulae under consistency assertions from root objects
        consisAsserFormulaRelSet = self.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula)
        for modelRel in consisAsserFormulaRelSet.modelRelationships:
            if modelRel.fromModelObject is not None and modelRel.toModelObject is not None:
                rootObjects.add(modelRel.fromModelObject)   # display consis assertion
                rootObjects.discard(modelRel.toModelObject) # remove formula from root objects
                
        # remove assertions under assertion sets from root objects
        assertionSetRelSet = self.modelXbrl.relationshipSet(XbrlConst.assertionSet)
        for modelRel in assertionSetRelSet.modelRelationships:
            if modelRel.fromModelObject is not None and modelRel.toModelObject is not None:
                rootObjects.add(modelRel.fromModelObject)   # display assertion set
                rootObjects.discard(modelRel.toModelObject) # remove assertion from root objects
                
        # root node for tree view
        self.id = 1
        for rootObject in rootObjects:
            self.viewFormulaObjects("", rootObject, None, relationshipSet, set())
        for cfQname in sorted(self.modelXbrl.modelCustomFunctionSignatures.keys()):
            cfObject = self.modelXbrl.modelCustomFunctionSignatures[cfQname]
            self.viewFormulaObjects("", cfObject, None, relationshipSet, set())
        self.treeView.bind("<<TreeviewSelect>>", self.treeviewSelect, '+')
        self.treeView.bind("<Enter>", self.treeviewEnter, '+')
        self.treeView.bind("<Leave>", self.treeviewLeave, '+')

        # pop up menu
        menu = self.contextMenu()
        menu.add_cascade(label=_("Expand"), underline=0, command=self.expand)
        menu.add_cascade(label=_("Collapse"), underline=0, command=self.collapse)
        self.menuAddClipboard()

    def viewFormulaObjects(self, parentNode, fromObject, fromRel, relationshipSet, visited):
        if fromObject is None:
            return
        if isinstance(fromObject, ModelVariable) and fromRel is not None:
            text = "{0} ${1}".format(fromObject.localName, fromRel.variableQname)
        else:
            text = fromObject.localName
        childnode = self.treeView.insert(parentNode, "end", fromObject.objectId(self.id), text=text)
        self.treeView.set(childnode, "label", fromObject.xlinkLabel)
        if fromRel is not None and fromRel.arcrole == XbrlConst.variableFilter:
            self.treeView.set(childnode, "cover", "true" if fromRel.isCovered else "false")
            self.treeView.set(childnode, "complement", "true" if fromRel.isComplemented else "false")
        if isinstance(fromObject, ModelVariable):
            self.treeView.set(childnode, "bindAsSequence", fromObject.bindAsSequence)
        if hasattr(fromObject, "viewExpression"):
            self.treeView.set(childnode, "expression", fromObject.viewExpression)
        self.id += 1
        if fromObject not in visited:
            visited.add(fromObject)
            for modelRel in relationshipSet.fromModelObject(fromObject):
                toObject = modelRel.toModelObject
                self.viewFormulaObjects(childnode, toObject, modelRel, relationshipSet, visited)
            visited.remove(fromObject)
            
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

    