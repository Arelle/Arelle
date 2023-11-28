'''
This module is an example Arelle controller in non-interactive mode

See COPYRIGHT.md for copyright information.
'''
from arelle import Cntlr
from arelle.ValidateXbrlCalcs import ValidateCalcsMode

class CntlrEfmValidateExample(Cntlr.Cntlr):

    def __init__(self):
        super().__init__(logFileName="c:\\temp\\test-log.txt")

    def run(self):
        # select SEC Edgar Filer Manual validation before validation (causes file name and contents checking
        self.modelManager.validateDisclosureSystem = True
        self.modelManager.disclosureSystem.select("efm")

        modelXbrl = self.modelManager.load("c:\\temp\\test.xbrl")

        self.modelManager.validateCalcs = ValidateCalcsMode.XBRL_v2_1

        # perfrom XBRL 2.1, dimensions, calculation and SEC EFM validation
        self.modelManager.validate()

        # close the loaded instance
        self.modelManager.close()

        self.close()

if __name__ == "__main__":
    CntlrEfmValidateExample().run()
