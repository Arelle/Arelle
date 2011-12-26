#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Nov 27, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelObject, XbrlConst, ViewCsv
from arelle.ModelDtsObject import ModelRelationship
from arelle.ModelFormulaObject import ModelVariable
from arelle.ViewUtilFormulae import rootFormulaObjects, formulaObjSortKey
import os

def viewFormulae(modelXbrl, csvfile, header, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing formulae"))
    view = ViewFormulae(modelXbrl, csvfile, header, lang)
    view.view()
    view.close()
    
class ViewFormulae(ViewCsv.View):
    def __init__(self, modelXbrl, csvfile, header, lang):
        super().__init__(modelXbrl, csvfile, header, lang)
        
    def view(self):
        # determine relationships indent depth
        rootObjects = rootFormulaObjects(self)
        self.treeCols = 0
        for rootObject in rootObjects:
            self.treeDepth(rootObject, 1, set())
        heading = (["Formula object"] + [None for i in range(self.treeCols)] + 
                   ["Label", "Cover", "Complement", "Bind as sequence", "Expression"])
        self.write(heading)
        for rootObject in sorted(rootObjects, key=formulaObjSortKey):
            self.viewFormulaObjects(rootObject, None, [None], set())
        for cfQname in sorted(self.modelXbrl.modelCustomFunctionSignatures.keys()):
            cfObject = self.modelXbrl.modelCustomFunctionSignatures[cfQname]
            self.viewFormulaObjects(cfObject, None,[None], set())

    def treeDepth(self, fromObject, indentedCol, visited):
        if fromObject is None:
            return
        if indentedCol > self.treeCols: self.treeCols = indentedCol
        if fromObject not in visited:
            visited.add(fromObject)
            relationshipArcsShown = set()
            for relationshipSet in (self.varSetFilterRelationshipSet,
                                    self.allFormulaRelationshipsSet):
                for modelRel in relationshipSet.fromModelObject(fromObject):
                    if modelRel.arcElement not in relationshipArcsShown:
                        relationshipArcsShown.add(modelRel.arcElement)
                        toObject = modelRel.toModelObject
                        self.treeDepth(toObject, indentedCol + 1, visited)
            visited.remove(fromObject)
            
    def viewFormulaObjects(self, fromObject, fromRel, indent, visited):
        if fromObject is None:
            return
        if isinstance(fromObject, ModelVariable) and fromRel is not None:
            text = "{0} ${1}".format(fromObject.localName, fromRel.variableQname)
        else:
            text = fromObject.localName
        cols = indent + [text]
        for i in range(self.treeCols - len(indent)):
            cols.append(None)
        cols.append(fromObject.xlinkLabel) # label
        if fromRel is not None and fromRel.arcrole == XbrlConst.variableFilter:
            cols.append("true" if fromRel.isCovered else "false") # cover
            cols.append("true" if fromRel.isComplemented else "false") #complement
        else:
            cols.append(None) # cover
            cols.append(None) # compelement
        if isinstance(fromObject, ModelVariable):
            cols.append(fromObject.bindAsSequence) # bind as sequence
        else:
            cols.append(None) # bind as sequence
        if hasattr(fromObject, "viewExpression"):
            cols.append(fromObject.viewExpression) # expression
        else:            
            cols.append(None) # expression
        self.write(cols)
        if fromObject not in visited:
            visited.add(fromObject)
            relationshipArcsShown = set()
            for relationshipSet in (self.varSetFilterRelationshipSet,
                                    self.allFormulaRelationshipsSet):
                for modelRel in relationshipSet.fromModelObject(fromObject):
                    if modelRel.arcElement not in relationshipArcsShown:
                        relationshipArcsShown.add(modelRel.arcElement)
                        toObject = modelRel.toModelObject
                        self.viewFormulaObjects(toObject, modelRel, indent + [None], visited)
            visited.remove(fromObject)