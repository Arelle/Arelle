'''
Created on Nov 28, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from gettext import gettext as _

from arelle import (ModelDocument, ViewCsv)

def viewTests(modelXbrl, csvfile):
    modelXbrl.modelManager.showStatus(_("viewing Tests"))
    view = ViewTests(modelXbrl, csvfile)
    view.write(["Index","Testcase","ID","Name", "ReadMeFirst","Status","Expected","Actual"])
    if modelXbrl.modelDocument is not None:
        view.viewTestcaseIndexElement(modelXbrl.modelDocument)
    view.close()
    
class ViewTests(ViewCsv.View):
    def __init__(self, modelXbrl, csvfile):
        super(ViewTests, self).__init__(modelXbrl, csvfile)
        
    def viewTestcaseIndexElement(self, modelDocument):
        if modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.REGISTRY):
            self.write([os.path.basename(modelDocument.uri)])
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
        self.write(["",os.path.basename(modelDocument.uri)])
        if hasattr(modelDocument, "testcaseVariations"):
            for modelTestcaseVariation in modelDocument.testcaseVariations:
                self.viewTestcaseVariation(modelTestcaseVariation)
                
    def viewTestcaseVariation(self, modelTestcaseVariation):
        tid = modelTestcaseVariation.id
        if tid is None:
            tid = ""
        self.write(["","",tid,
                    modelTestcaseVariation.name,
                    " ".join(modelTestcaseVariation.readMeFirstUris),
                    modelTestcaseVariation.status,
                    modelTestcaseVariation.expected,
                    " ".join(str(code) for code in modelTestcaseVariation.actual)])
