'''
Created on Jan 10, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewFile, XbrlConst, XmlUtil
from collections import defaultdict

def viewFacts(modelXbrl, outfile, lang=None, labelrole=None, cols=None):
    modelXbrl.modelManager.showStatus(_("viewing facts"))
    view = ViewFacts(modelXbrl, outfile, labelrole, lang, cols)
    view.view(modelXbrl.modelDocument)
    view.close()
    
class ViewFacts(ViewFile.View):
    def __init__(self, modelXbrl, outfile, labelrole, lang, cols):
        super(ViewFacts, self).__init__(modelXbrl, outfile, "Fact List", lang)
        self.labelrole = labelrole
        self.cols = cols

    def view(self, modelDocument):
        if self.cols:
            if isinstance(self.cols,str): self.cols = self.cols.replace(',',' ').split()
            unrecognizedCols = []
            for col in self.cols:
                if col not in ("Label","Name","contextRef","unitRef","Dec","Prec","Lang","Value","EntityScheme","EntityIdentifier","Period","Dimensions"):
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedFactListColumn",
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=','.join(unrecognizedCols))
            if "Period" in self.cols:
                i = self.cols.index("Period")
                self.cols[i:i+1] = ["Start", "End/Instant"]
        else:
            self.cols = ["Label","contextRef","unitRef","Dec","Prec","Lang","Value"]
        col0 = self.cols[0]
        if col0 not in ("Label", "Name"):
            self.modelXbrl.error("arelle:firstFactListColumn",
                                 _("First column must be Label or Name: %(col1)s"),
                                 modelXbrl=self.modelXbrl, col1=col0)
        self.isCol0Label = col0 == "Label"
        self.maxNumDims = 1
        self.tupleDepth(self.modelXbrl.facts, 0)
        if "Dimensions" == self.cols[-1]:
            lastColSpan = self.maxNumDims
        else:
            lastColSpan = None
        self.addRow(self.cols, asHeader=True, lastColSpan=lastColSpan)
        self.viewFacts(self.modelXbrl.facts, 0)
        
    def tupleDepth(self, modelFacts, indentedCol):
        if indentedCol > self.treeCols: self.treeCols = indentedCol
        for modelFact in modelFacts:
            if modelFact.context is not None:
                numDims = len(modelFact.context.qnameDims) * 2
                if numDims > self.maxNumDims: self.maxNumDims = numDims
            self.tupleDepth(modelFact.modelTupleFacts, indentedCol + 1)
        
    def viewFacts(self, modelFacts, indent):
        for modelFact in modelFacts:
            concept = modelFact.concept
            xmlRowElementName = 'item'
            attr = {"name": str(modelFact.qname)}
            if concept is not None and self.isCol0Label:
                lbl = concept.label(preferredLabel=self.labelrole, lang=self.lang, linkroleHint=XbrlConst.defaultLinkRole)
                xmlCol0skipElt = False # provide label as a row element
            else:
                lbl = (modelFact.qname or modelFact.prefixedName) # defective inline facts may have no qname
                xmlCol0skipElt = True # name is an attribute, don't do it also as an element
            cols = [lbl]
            if concept is not None:
                if modelFact.isItem:
                    for col in self.cols[1:]:
                        if col == "Label": # label or name may be 2nd to nth col if name or label is 1st col
                            cols.append( concept.label(preferredLabel=self.labelrole, lang=self.lang) )
                        elif col == "Name":
                            cols.append( modelFact.qname )
                        elif col == "contextRef":
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
                elif modelFact.isTuple:
                    xmlRowElementName = 'tuple'
            self.addRow(cols, treeIndent=indent, xmlRowElementName=xmlRowElementName, xmlRowEltAttr=attr, xmlCol0skipElt=xmlCol0skipElt)
            self.viewFacts(modelFact.modelTupleFacts, indent + 1)
