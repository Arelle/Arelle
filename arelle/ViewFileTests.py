'''
Created on Nov 28, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelDocument, ViewFile
import os

def viewTests(modelXbrl, outfile, cols):
    modelXbrl.modelManager.showStatus(_("viewing Tests"))
    view = ViewTests(modelXbrl, outfile, cols)
    view.viewTestcaseIndexElement(modelXbrl.modelDocument)
    view.close()
    
class ViewTests(ViewFile.View):
    def __init__(self, modelXbrl, outfile, cols):
        super(ViewTests, self).__init__(modelXbrl, outfile, "Tests")
        self.cols = cols
        
    def viewTestcaseIndexElement(self, modelDocument):
        if self.cols:
            if isinstance(self.cols,str): self.cols = self.cols.replace(',',' ').split()
            unrecognizedCols = []
            for col in self.cols:
                if col not in ("Index", "Testcase", "ID", "Name", "Reference", "ReadMeFirst", "Status", "Expected","Actual"):
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedTestReportColumn",
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=','.join(unrecognizedCols))
            if "Period" in self.cols:
                i = self.cols.index("Period")
                self.cols[i:i+1] = ["Start", "End/Instant"]
        else:
            self.cols = ["Index", "Testcase", "ID", "Name", "ReadMeFirst", "Status", "Expected", "Actual"]
        
        self.addRow(self.cols, asHeader=True)

        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            cols = []
            for col in self.cols:
                if col == "Index":
                    cols.append(os.path.basename(modelDocument.uri))
                    break
                else:
                    cols.append("")
            self.addRow(cols)
            # sort test cases by uri
            testcases = []
            for referencedDocument in modelDocument.referencesDocument.keys():
                testcases.append((referencedDocument.uri, referencedDocument.objectId()))
            testcases.sort()
            for testcaseTuple in testcases:
                self.viewTestcase(self.modelXbrl.modelObject(testcaseTuple[1]))
        elif modelDocument.type in (ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRYTESTCASE):
            self.viewTestcase(modelDocument)
        else:
            pass
                
    def viewTestcase(self, modelDocument):
        cols = []
        for col in self.cols:
            if col == "Testcase":
                cols.append(os.path.basename(modelDocument.uri))
                break
            else:
                cols.append("")
        self.addRow(cols, xmlRowElementName="testcase")
        if hasattr(modelDocument, "testcaseVariations"):
            for modelTestcaseVariation in modelDocument.testcaseVariations:
                self.viewTestcaseVariation(modelTestcaseVariation)
                
    def viewTestcaseVariation(self, modelTestcaseVariation):
        id = modelTestcaseVariation.id
        if id is None:
            id = ""
        cols = []
        for col in self.cols:
            if col == "ID":
                cols.append(id)
            elif col == "Name":
                cols.append(modelTestcaseVariation.name or modelTestcaseVariation.description)
            elif col == "Reference":
                cols.append(modelTestcaseVariation.reference)
            elif col == "ReadMeFirst":
                cols.append(" ".join(str(uri) for uri in modelTestcaseVariation.readMeFirstUris))
            elif col == "Status":
                cols.append(modelTestcaseVariation.status)
            elif col == "Expected":
                cols.append(modelTestcaseVariation.expected)
            elif col == "Actual":
                cols.append(" ".join(str(code) for code in modelTestcaseVariation.actual))
            else:
                cols.append("")
        self.addRow(cols, xmlRowElementName="variation")
