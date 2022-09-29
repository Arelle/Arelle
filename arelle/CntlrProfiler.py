'''
See COPYRIGHT.md for copyright information.
'''
import Cntlr, ModelManager, FileSource, time
from optparse import OptionParser
import cProfile
import gettext
import locale

def main():
    CntlrProfiler().run()

class CntlrProfiler(Cntlr.Cntlr):

    def __init__(self):
        super(CntlrProfiler, self).__init__()

    def run(self):
        self.filename = r"C:\Users\Herm Fischer\Documents\mvsl\projects\SEC\Local.Conformance\conformance\Private\Formula\Extension-Conformance\root\efm-15-101007\conf\616-definition-syntax\616-03-dimension-domain-is-domain\e61603000gd-20081231.xml"
        filesource = FileSource.FileSource(self.filename)
        self.modelManager.validateEFM = True
        self.modelManager.load(filesource, _("views loading"))
        self.modelManager.validate()

    def addToLog(self, message):
        print(message)

    def showStatus(self, message, clearAfter=None):
        pass

if __name__ == "__main__":
    cProfile.run('main()')
