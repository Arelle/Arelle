'''
Created on Jan 10, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewCsv, XbrlConst, XmlUtil
from collections import defaultdict

def viewFacts(modelXbrl, csvfile, lang=None, cols=None):
    modelXbrl.modelManager.showStatus(_("viewing facts"))
    view = ViewFacts(modelXbrl, csvfile, lang, cols)
    view.view(modelXbrl.modelDocument)
    view.close()
    
class ViewFacts(ViewCsv.View):
    def __init__(self, modelXbrl, csvfile, lang, cols):
        super().__init__(modelXbrl, csvfile, "Fact List", lang)
        self.cols = cols

    def view(self, modelDocument):
        if self.cols:
            if isinstance(self.cols,str): self.cols = self.cols.replace(',',' ').split()
            unrecognizedCols = []
            for col in self.cols:
                if col not in ("Label","Name","contextRef","unitRef","Dec","Prec","Lang","Value","EntityScheme","EntityIdentifier","Period","Dimensions"):
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedCsvFactListColumn",
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=','.join(unrecognizedCols))
            if "Period" in self.cols:
                i = self.cols.index("Period")
                self.cols[i:i] = ["Start", "End/Instant"]
        else:
            self.cols = ("Label","contextRef","unitRef","Dec","Prec","Lang","Value")
        col0 = self.cols[0]
        if col0 not in ("Label", "Name"):
            self.modelXbrl.error("arelle:firstCsvFactListColumn",
                                 _("First column must be Label or Name: %(col1)s"),
                                 modelXbrl=self.modelXbrl, col1=col0)
        self.isCol0Label = col0 == "Label"
        heading = [col0]
        self.treeCols = 0
        self.tupleDepth(self.modelXbrl.facts, 0)
        for i in range(self.treeCols - 1):
            heading.append(None)
        heading.extend(self.cols[1:])
        self.write(heading)
        self.viewFacts(self.modelXbrl.facts, [])
        
    def tupleDepth(self, modelFacts, indentedCol):
        if indentedCol > self.treeCols: self.treeCols = indentedCol
        for modelFact in modelFacts:
            self.tupleDepth(modelFact.modelTupleFacts, indentedCol + 1)
        
    def viewFacts(self, modelFacts, indent):
        for modelFact in modelFacts:
            concept = modelFact.concept
            if concept is not None and self.isCol0Label:
                lbl = concept.label(lang=self.lang)
            else:
                lbl = modelFact.qname
            cols = indent + [lbl]
            for i in range(self.treeCols - len(cols)):
                cols.append(None)
            if concept is not None and not modelFact.concept.isTuple:
                for col in self.cols[1:]:
                    if col == "contextRef":
                        cols.append( modelFact.contextID )
                    elif col == "unitRef":
                        cols.append( modelFact.unitID )
                    elif col == "Dec":
                        cols.append( modelFact.decimals )
                    elif col == "Prec":
                        cols.append( modelFact.precision )
                    elif col == "Lang":
                        cols.append( modelFact.xmlLang )
                    elif col == "Value":
                        cols.append( "(nil)" if modelFact.xsiNil == "true" else modelFact.effectiveValue.strip() )
                    elif col == "EntityScheme":
                        cols.append( modelFact.context.entityIdentifier[0] )
                    elif col == "EntityIdentifier":
                        cols.append( modelFact.context.entityIdentifier[1] )
                    elif col == "Start":
                        cols.append( XmlUtil.text(XmlUtil.child(modelFact.context.period, XbrlConst.xbrli, "startDate")) )
                    elif col == "End/Instant":
                        cols.append( XmlUtil.text(XmlUtil.child(modelFact.context.period, XbrlConst.xbrli, ("endDate","instant"))) )
                    elif col == "Dimensions":
                        for dimQname in sorted(modelFact.context.qnameDims.keys()):
                            cols.append( str(dimQname) )
                            cols.append( str(modelFact.context.dimMemberQname(dimQname)) )
            self.write(cols)
            self.viewFacts(modelFact.modelTupleFacts, indent + [None])
