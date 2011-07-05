'''
Created on Jan 10, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from gettext import gettext as _

from arelle import (ViewCsv, XbrlConst)
from collections import defaultdict

def viewFacts(modelXbrl, csvfile, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing facts"))
    view = ViewFacts(modelXbrl, csvfile, lang)
    view.view(modelXbrl.modelDocument)
    view.close()
    
class ViewFacts(ViewCsv.View):
    def __init__(self, modelXbrl, csvfile, lang):
        super(ViewFacts, self).__init__(modelXbrl, csvfile, "Fact List", lang)

    def view(self, modelDocument):
        
        heading = ["Label"]
        self.treeCols = 0
        self.tupleDepth(self.modelXbrl.facts, 0)
        for i in range(self.treeCols - 1):
            heading.append(None)
        heading.extend(["contextRef","unitRef","Dec","Prec","Lang","Value"])
        self.write(heading)
        self.viewFacts(self.modelXbrl.facts, [])
        
    def tupleDepth(self, modelFacts, indentedCol):
        if indentedCol > self.treeCols: self.treeCols = indentedCol
        for modelFact in modelFacts:
            self.tupleDepth(modelFact.modelTupleFacts, indentedCol + 1)
        
    def viewFacts(self, modelFacts, indent):
        for modelFact in modelFacts:
            concept = modelFact.concept
            if concept:
                lbl = concept.label(lang=self.lang)
            else:
                lbl = modelFact.qname
            cols = indent + [lbl]
            for i in range(self.treeCols - len(cols)):
                cols.append(None)
            if concept and not modelFact.concept.isTuple:
                cols.append( modelFact.contextID )
                cols.append( modelFact.unitID )
                cols.append( modelFact.decimals )
                cols.append( modelFact.precision )
                cols.append( modelFact.xmlLang )
                cols.append( "(nil)" if modelFact.xsiNil == "true" else modelFact.effectiveValue.strip() )
            self.write(cols)
            self.viewFacts(modelFact.modelTupleFacts, indent + [None])
