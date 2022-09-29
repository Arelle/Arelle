'''
This module is an example Arelle controller in non-interactive mode

See COPYRIGHT.md for copyright information.
'''
from arelle import Cntlr
from arelle.ViewCsvRelationshipSet import viewRelationshipSet

class CntlrCsvPreLbExample(Cntlr.Cntlr):

    def __init__(self):
        super().__init__(logFileName="c:\\temp\\test-log.txt")

    def run(self):
        modelXbrl = self.modelManager.load("c:\\temp\\test.xbrl")

        # output presentation linkbase tree as a csv file
        viewRelationshipSet(modelXbrl, "c:\\temp\\test-pre.csv", "Presentation", "http://www.xbrl.org/2003/arcrole/parent-child")

        # close the loaded instance
        self.modelManager.close()

        self.close()

if __name__ == "__main__":
    CntlrCsvPreLbExample().run()
