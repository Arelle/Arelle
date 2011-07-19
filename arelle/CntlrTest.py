"""
Created on Oct 3, 2010

This module is Arelle's controller in command line non-interactive mode

(This module can be a pattern for custom integration of Arelle into an application.)

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
"""
import sys
import gettext, time, datetime
from optparse import OptionParser
from arelle import Cntlr, FileSource, XmlUtil, Version, traceit
from arelle.Locale import format_string
from arelle.ModelFormulaObject import FormulaOptions

import cProfile

def main():
    """Testing program for speed."""
    gettext.install("arelle")
    usage = "usage: %prog [options]"
    parser = OptionParser(usage, version="Arelle(TM) {0}".format(Version.version))
    parser.add_option("-f", "--file", dest="filename",
                      help=_("FILENAME is an entry point, which may be"
                             "an XBRL instance, schema, linkbase file, "
                             "inline XBRL instance, testcase file, "
                             "testcase index file.  FILENAME may be "
                             "a local file or a URI to a web located file."))
    parser.add_option("-p", "--profile", dest="profile_file",
                      help=_("PROFILE_FILE is a file to store profiling data in."))

    parser.add_option("-t", "--trace", dest="trace",
                      action="store_true", default = False,
                      help=_("Trace the execution for educational reasons."))

    (options, args) = parser.parse_args()
    if options.trace:
        sys.settrace(traceit)
        
    if len(args) != 0 or options.filename is None:
        parser.error(_("incorrect arguments, please try\n  python CntlrTest.pyw --help"))
    else:
        # parse and run the FILENAME
        CntlrTest().run(options)

class CntlrTest(Cntlr.Cntlr):
    """CntlrTest Class to shim together arelle classes for testing."""
    def __init__(self):
        super(CntlrTest, self).__init__()
        self.filename = None
        self.output_filename = None
        self.messages = []
    
    def run(self, options):
        """This actually does the loading and validation."""
        self.filename = options.filename
        filesource = FileSource.FileSource(self.filename, self)
        self.modelManager.validateDisclosureSystem = True
        self.modelManager.disclosureSystem.select("efm")
        self.modelManager.validateInferDecimals = False
        self.modelManager.validateCalcLB = True
        self.modelManager.validateUtr = True
        self.modelManager.formulaOptions = FormulaOptions()
        
        timeNow = XmlUtil.dateunionValue(datetime.datetime.now())
        startedAt = time.time()
        self.modelManager.load(filesource, _("views loading"))
        self.addToLog(format_string(self.modelManager.locale,
                                    _("[info] loaded in %.2f secs at %s"),
                                    (time.time() - startedAt, timeNow)))
        try:
            startedAt = time.time()
            if options.profile_file:
                cProfile.runctx('self.modelManager.validate()', globals(), locals(), options.profile_file)
            else:
                self.modelManager.validate()
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("[info] validated in %.2f secs"), 
                                        time.time() - startedAt))
        except (IOError, EnvironmentError) as err:
            self.addToLog(_("[IOError] Failed to save output:\n {0}").format(err))
        
        # self.filename = "test.log"
        if self.output_filename:
            try:
                with open(self.output_filename, "w", encoding="utf-8") as fh:
                    fh.writelines(self.messages)
            except (IOError, EnvironmentError) as err:
                print("Unable to save log to file: " + err)
        else:
            for msg in self.messages:
                print(msg.rstrip())
            
    def addToLog(self, message):
        if self.messages is not None:
            self.messages.append(message + '\n')
        else:
            print(message) # allows printing on standard out

    def showStatus(self, message, clearAfter=None):
        pass

if __name__ == "__main__":
    main()
