'''
See COPYRIGHT.md for copyright information.
'''
import os
from arelle import ViewFile

def viewDTS(modelXbrl, outfile):
    view = ViewDTS(modelXbrl, outfile)
    modelXbrl.modelManager.showStatus(_("viewing DTS"))
    view.treeDepth(modelXbrl.modelDocument, 1, set()) # count of cols starts at 1 because no ELR headers as with relationships
    view.addRow(["DTS"], asHeader=True)
    view.viewDtsElement(modelXbrl.modelDocument, {"entry"}, 0, set())
    view.close()

class ViewDTS(ViewFile.View):
    def __init__(self, modelXbrl, outfile):
        super(ViewDTS, self).__init__(modelXbrl, outfile, "DTS")

    def treeDepth(self, modelDocument, indent, visited):
        visited.add(modelDocument)
        if indent > self.treeCols: self.treeCols = indent
        for referencedDocument in modelDocument.referencesDocument.keys():
            if referencedDocument not in visited:
                self.treeDepth(referencedDocument, indent + 1, visited)
        visited.remove(modelDocument)

    def viewDtsElement(self, modelDocument, referenceTypes, indent, visited):
        visited.add(modelDocument)
        dtsObjectType = modelDocument.gettype()
        attr = {"file": modelDocument.basename, "referenceTypes": sorted(referenceTypes)}
        if not modelDocument.inDTS:
            attr["inDTS"] = "false"
        self.addRow(["{0} - {1}".format(modelDocument.basename, dtsObjectType)], treeIndent=indent,
                    xmlRowElementName=dtsObjectType, xmlRowEltAttr=attr, xmlCol0skipElt=True)
        for referencedDocument, ref in modelDocument.referencesDocument.items():
            if referencedDocument not in visited:
                self.viewDtsElement(referencedDocument, ref.referenceTypes, indent + 1, visited)
        visited.remove(modelDocument)
