'''
Profile Formula Validation is an example of a plug-in to GUI menu that will profile formula execution.

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
import os
from tkinter import simpledialog, messagebox

def profileFormulaMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the profile formula plugin
    menu.add_command(label="Profile formula validation", 
                     underline=0, 
                     command=lambda: profileFormulaMenuCommand(cntlr) )

def profileFormulaMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return

    # get file name into which to save log file while in foreground thread
    profileReportFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save Formula Profile Report"),
            initialdir=cntlr.config.setdefault("formulaProfileReportDir","."),
            filetypes=[(_("Profile report file .log"), "*.log")],
            defaultextension=".log")
    if not profileReportFile:
        return False
    errMsg = ""
    maxRunTime = 0
    while (1):
        timeout = simpledialog.askstring(_("arelle - Set formula run time limit"),
                _("{0}You may enter the maximum number of minutes to run formulas.\n"
                  "(Leave empty for no run time limitation.)".format(errMsg)),
                parent=cntlr.parent)
        if timeout:
            try:
                maxRunTime = float(timeout)
                break
            except ValueError as err:
                errMsg = str(err) + "\n\n"
                
    excludeCompileTime = messagebox.askyesno(_("arelle - Exclude formula compile statistics"),
                _("Should formula compiling be excluded from the statistics?\n"
                  "(Yes will make a separate compiling \"pass\" so that statistics include execution only.)".format(errMsg)),
                parent=cntlr.parent)
            
    cntlr.config["formulaProfileReportDir"] = os.path.dirname(profileReportFile)
    cntlr.saveConfig()

    # perform validation and profiling on background thread
    import threading    
    thread = threading.Thread(target=lambda c=cntlr, f=profileReportFile, t=maxRunTime, e=excludeCompileTime: backgroundProfileFormula(c,f,t,e))
    thread.daemon = True
    thread.start()

def backgroundProfileFormula(cntlr, profileReportFile, maxRunTime, excludeCompileTime):
    from arelle import Locale, XPathParser, ValidateXbrlDimensions, ValidateFormula

    # build grammar before profiling (if this is the first pass, so it doesn't count in profile statistics)
    XPathParser.initializeParser(cntlr.modelManager)
    
    # load dimension defaults
    ValidateXbrlDimensions.loadDimensionDefaults(cntlr.modelManager)
    
    import cProfile, pstats, sys, time
    
    # a minimal validation class for formula validator parameters that are needed
    class Validate:
        def __init__(self, modelXbrl, maxRunTime):
            self.modelXbrl = modelXbrl
            self.parameters = None
            self.validateSBRNL = False
            self.maxFormulaRunTime = maxRunTime
        def close(self):
            self.__dict__.clear()
            
    val = Validate(cntlr.modelManager.modelXbrl, maxRunTime)
    formulaOptions = val.modelXbrl.modelManager.formulaOptions
    if excludeCompileTime:
        startedAt = time.time()
        cntlr.addToLog(_("pre-compiling formulas before profiling"))
        val.validateFormulaCompileOnly = True
        ValidateFormula.validate(val)
        del val.validateFormulaCompileOnly
        cntlr.addToLog(Locale.format_string(cntlr.modelManager.locale, 
                                            _("formula pre-compiling completed in %.2f secs"), 
                                            time.time() - startedAt))
        cntlr.addToLog(_("executing formulas for profiling"))
    else:
        cntlr.addToLog(_("compiling and executing formulas for profiling"))
    startedAt = time.time()
            
    statsFile = profileReportFile + ".bin"
    cProfile.runctx("ValidateFormula.validate(val)", globals(), locals(), statsFile)
    cntlr.addToLog(Locale.format_string(cntlr.modelManager.locale, 
                                        _("formula profiling completed in %.2f secs"), 
                                        time.time() - startedAt))
    # dereference val
    val.close()
    
    # specify a file for log
    priorStdOut = sys.stdout
    sys.stdout = open(profileReportFile, "w")

    statObj = pstats.Stats(statsFile)
    statObj.strip_dirs()
    statObj.sort_stats("time")
    statObj.print_stats()
    statObj.print_callees()
    statObj.print_callers()
    sys.stdout.flush()
    sys.stdout.close()
    del statObj
    sys.stdout = priorStdOut
    os.remove(statsFile)

__pluginInfo__ = {
    'name': 'Profile Formula Validation',
    'version': '1.0',
    'description': "This plug-in adds a profiled formula validation. "
                    "Includes XPath compilation in the profile if it is the first validation of instance; "
                    "to exclude XPath compile statistics, validate first the normal way (e.g., toolbar button) "
                    "and then validate again using this profile formula validation plug-in.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Validation': profileFormulaMenuEntender,
}
