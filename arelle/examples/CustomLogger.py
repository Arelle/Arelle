'''
This module is an example Arelle controller in non-interactive mode

See COPYRIGHT.md for copyright information.
'''
from __future__ import print_function
from arelle import Cntlr

class CntlrCustomLoggingExample(Cntlr.Cntlr):

    def __init__(self):
        # no logFileName parameter to prevent default logger from starting
        super().__init__()

    def run(self):
        # start custom logger
        CustomLogHandler(self)

        modelXbrl = self.modelManager.load("c:\\temp\\test.xbrl")

        self.modelManager.validateInferDecimals = True
        self.modelManager.validateCalcLB = True

        self.modelManager.validate()

        self.modelManager.close()

        self.close()

import logging
class CustomLogHandler(logging.Handler):
    def __init__(self, cntlr):
        logger = logging.getLogger("arelle")
        self.level = logging.DEBUG
        self.setFormatter(logging.Formatter("[%(messageCode)s] %(message)s - %(file)s %(sourceLine)s"))
        logger.addHandler(self)

    def emit(self, logRecord):
        # just print to standard output (e.g., terminal window)
        print(self.format(logRecord))

if __name__ == "__main__":
    CntlrCustomLoggingExample().run()
