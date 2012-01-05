'''
Created on Nov 28, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelDocument, ViewFile
import os

def viewTests(modelXbrl, outfile):
    modelXbrl.modelManager.showStatus(_("viewing Tests"))
    view = ViewTests(modelXbrl, outfile)
    view.addRow(["Index","Testcase","ID","Name", "ReadMeFirst","Status","Expected","Actual"], asHeader=True)
    view.viewTestcaseIndexElement(modelXbrl.modelDocument)
    view.close()
    
class ViewTests(ViewFile.View):
    def __init__(self, modelXbrl, outfile):
        super().__init__(modelXbrl, outfile, "Tests")
        
    def viewTestcaseIndexElement(self, modelDocument):
        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            self.addRow([os.path.basename(modelDocument.uri)])
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
        self.addRow(["",os.path.basename(modelDocument.uri)], xmlRowElementName="testcase")
        if hasattr(modelDocument, "testcaseVariations"):
            for modelTestcaseVariation in modelDocument.testcaseVariations:
                self.viewTestcaseVariation(modelTestcaseVariation)
                
    def viewTestcaseVariation(self, modelTestcaseVariation):
        id = modelTestcaseVariation.id
        if id is None:
            id = ""
        self.addRow(["","",id,
                     (modelTestcaseVariation.name or modelTestcaseVariation.description),
                     " ".join(str(uri) for uri in modelTestcaseVariation.readMeFirstUris),
                     modelTestcaseVariation.status,
                     modelTestcaseVariation.expected,
                     " ".join(str(code) for code in modelTestcaseVariation.actual)],
                    xmlRowElementName="variation")
