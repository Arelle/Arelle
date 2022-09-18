'''
Save Instance Infoset is an example of a plug-in to both GUI menu and command line/web service
that will save facts decorated with ptv:periodType, ptv:balance, ptv:decimals and ptv:precision (inferred).

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

def savePickle(cntlr, modelXbrl, pickleFile):
    if modelXbrl.fileSource.isArchive:
        return
    import io, time, pickle
    from arelle import Locale
    startedAt = time.time()

    fh = io.open(pickleFile, "wb")
    try:
        pickle.dump(modelXbrl, fh)
    except Exception as ex:
        cntlr.addToLog("Exception " + str(ex))
    fh.close()
    
    cntlr.addToLog(Locale.format_string(cntlr.modelManager.locale, 
                                        _("profiled command processing completed in %.2f secs"), 
                                        time.time() - startedAt))

def savePickleMenuEntender(cntlr, menu):
    # Extend menu with an item for the save infoset plugin
    menu.add_command(label="Save pickled modelXbrl", 
                     underline=0, 
                     command=lambda: savePickleMenuCommand(cntlr) )

def savePickleMenuCommand(cntlr):
    # save Infoset menu item has been invoked
    from arelle.ModelDocument import Type
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or cntlr.modelManager.modelXbrl.modelDocument.type != Type.INSTANCE:
        cntlr.addToLog("No instance loaded.")
        return

        # get file name into which to save log file while in foreground thread
    pickleFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save pickle file"),
            initialdir=cntlr.config.setdefault("pickleDir","."),
            filetypes=[(_("Pickle .prl"), "*.prl")],
            defaultextension=".prl")
    if not pickleFile:
        return False
    import os
    cntlr.config["pickleDir"] = os.path.dirname(pickleFile)
    cntlr.saveConfig()

    try: 
        savePickle(cntlr, cntlr.modelManager.modelXbrl, pickleFile)
    except Exception as ex:
        modelXbrl = cntlr.modelManager.modelXbrl
        modelXbrl.error("exception",
                        _("Save pickle exception: %(error)s"), error=ex,
                        modelXbrl=modelXbrl,
                        exc_info=True)

def savePickleCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--save-pickle", 
                      action="store", 
                      dest="pickleFile", 
                      help=_("Save pickle of object model in specified file, or to send testcase infoset out files to out directory specify 'generateOutFiles'."))

def savePickleCommandLineXbrlLoaded(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    from arelle.ModelDocument import Type
    if getattr(options, "instanceInfosetFile", None) and options.infosetFile == "generateOutFiles" and modelXbrl.modelDocument.type in (Type.TESTCASESINDEX, Type.TESTCASE):
        cntlr.modelManager.generateInfosetOutFiles = True

def savePickleCommandLineXbrlRun(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "pickleFile", None):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        savePickle(cntlr, cntlr.modelManager.modelXbrl, options.pickleFile)
        
__pluginInfo__ = {
    'name': 'Save (Pickle) Object Model',
    'version': '0.9',
    'description': "This plug-in pickels the running object model.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': savePickleMenuEntender,
    'CntlrCmdLine.Options': savePickleCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': savePickleCommandLineXbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': savePickleCommandLineXbrlRun,
}
