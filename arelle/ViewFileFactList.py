'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ViewFile, XbrlConst, XmlUtil
from collections import defaultdict

def viewFacts(modelXbrl, outfile, lang=None, labelrole=None, cols=None):
    modelXbrl.modelManager.showStatus(_("viewing facts"))
    view = ViewFacts(modelXbrl, outfile, labelrole, lang, cols)
    view.view(modelXbrl.modelDocument)
    view.close()

COL_WIDTHS = {
    "Concept": 80, # same as label
    "Label": 80,
    "Name":  40,
    "LocalName":  40,
    "Namespace":  40,
    "contextRef": 40,
    "unitRef": 40,
    "Dec": 5,
    "Prec": 5,
    "Lang": 6,
    "Value": 40,
    "EntityScheme": 40,
    "EntityIdentifier": 40,
    "Period": 40,
    "Dimensions": 60,
    # concept properties
    "ID": 40,
    "Type": 32,
    "PeriodType": 16,
    "Balance": 16,
    "Documentation": 100
    }
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
                if col not in COL_WIDTHS:
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
        if col0 not in ("Concept", "Label", "Name", "LocalName"):
            self.modelXbrl.error("arelle:firstFactListColumn",
                                 _("First column must be Concept, Label, Name or LocalName: %(col1)s"),
                                 modelXbrl=self.modelXbrl, col1=col0)
        self.isCol0Label = col0 in ("Concept", "Label")
        self.maxNumDims = 1
        self.tupleDepth(self.modelXbrl.facts, 0)
        if "Dimensions" == self.cols[-1]:
            lastColSpan = self.maxNumDims
        else:
            lastColSpan = None
        self.addRow(self.cols, asHeader=True, lastColSpan=lastColSpan)
        self.setColWidths([COL_WIDTHS.get(col, 8) for col in self.cols])
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
            lang = ""
            if concept is not None and self.isCol0Label:
                lbl = concept.label(preferredLabel=self.labelrole, lang=self.lang, linkroleHint=XbrlConst.defaultLinkRole)
                xmlCol0skipElt = False # provide label as a row element
                if concept.baseXsdType in ("string", "normalizedString"):
                    lang = modelFact.xmlLang
            else:
                lbl = (modelFact.qname or modelFact.prefixedName) # defective inline facts may have no qname
                xmlCol0skipElt = True # name is an attribute, don't do it also as an element
            cols = [lbl]
            if concept is not None:
                if modelFact.isItem:
                    for col in self.cols[1:]:
                        if col in ("Concept", "Label"): # label or name may be 2nd to nth col if name or label is 1st col
                            cols.append( concept.label(preferredLabel=self.labelrole, lang=self.lang) )
                        elif col == "Name":
                            cols.append( modelFact.qname )
                        elif col == "LocalName":
                            cols.append( modelFact.qname.localName )
                        elif col == "Namespace":
                            cols.append( modelFact.qname.namespaceURI )
                        elif col == "contextRef":
                            cols.append( modelFact.contextID )
                        elif col == "unitRef":
                            cols.append( modelFact.unitID )
                        elif col == "Dec":
                            cols.append( modelFact.decimals )
                        elif col == "Prec":
                            cols.append( modelFact.precision )
                        elif col == "Lang":
                            cols.append( lang )
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
                        elif col == "ID":
                            cols.append( concept.id )
                        elif col == "Type":
                            cols.append( concept.typeQname )
                        elif col == "PeriodType":
                            cols.append( concept.periodType )
                        elif col == "Balance":
                            cols.append( concept.balance )
                        elif col == "Documentation":
                            cols.append( concept.label(preferredLabel=XbrlConst.documentationLabel, fallbackToQname=False, lang=self.lang, strip=True, linkroleHint=XbrlConst.defaultLinkRole) )
                elif modelFact.isTuple:
                    xmlRowElementName = 'tuple'
            self.addRow(cols, treeIndent=indent, xmlRowElementName=xmlRowElementName, xmlRowEltAttr=attr, xmlCol0skipElt=xmlCol0skipElt)
            self.viewFacts(modelFact.modelTupleFacts, indent + 1)
