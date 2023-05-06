'''
This module is an example Arelle controller in non-interactive mode

See COPYRIGHT.md for copyright information.
'''
from arelle import Cntlr
from arelle.ValidateXbrlCalcs import ValidateCalcsMode

# this is the controller class
class CntlrValidateExample(Cntlr.Cntlr):

    # init sets up the default controller for logging to a file (instead of to terminal window)
    def __init__(self):
        # initialize superclass with default file logger
        super().__init__(logFileName="c:\\temp\\test-log.txt", logFileMode="w")

    def run(self):
        # create the modelXbrl by load instance and discover DTS
        modelXbrl = self.modelManager.load("c:\\temp\\test.xbrl")

        # select validation of calculation linkbase using infer decimals option
        self.modelManager.validateCalcs = ValidateCalcsMode.XBRL_v2_1

        # perfrom XBRL 2.1, dimensions, calculation
        self.modelManager.validate()

        # close the loaded instance
        self.modelManager.close()

        # close controller and application
        self.close()

# if python is initiated as a main program, start the controller
if __name__ == "__main__":
    # create the controller and start it running
    CntlrValidateExample().run()
