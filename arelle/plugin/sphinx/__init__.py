'''
sphinx is an example of a package plug-in to both GUI menu and command line/web service
that compiles a Sphinx Rules file into an XBRL Formula Linkbase either to be saved or to
be directly executed by Arelle XBRL Formula processing.

This plug-in is a python package, and can be loaded by referencing the containing
directory (usually, "sphinx"), and selecting this "__init__.py" file within the sphinx
directory (such as in a file chooser).

See COPYRIGHT.md for copyright information.

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer
(c) Copyright 2012 CoreFiling, Oxford UK.
Sphinx copyright applies to the Sphinx language, not to this software.
Workiva, Inc. conveys neither rights nor license for the Sphinx language.
'''

import time, os, io, sys
from arelle.ModelValue import qname
from arelle import XmlUtil
from arelle.Version import authorLabel, copyrightLabel

logMessage = None

def sphinxFilesDialog(cntlr):
    # get multiple file names of the sphinx files
    sphinxFiles = cntlr.uiFileDialog("open",
            multiple=True,  # expect multiple sphinx files
            title=_("arelle - Open sphinx rules files"),
            initialdir=cntlr.config.setdefault("sphinxRulesFileDir","."),
            filetypes=[(_("Sphinx files .xsr"), "*.xsr"), (_("Sphinx archives .xrb"), "*.xrb")],
            defaultextension=".xsr")
    if not sphinxFiles:
        return None
    cntlr.config["sphinxRulesFileDir"] = os.path.dirname(sphinxFiles[0])
    cntlr.saveConfig()
    return sphinxFiles

def generatedFormulasDirDialog(cntlr):
    from tkinter.filedialog import askdirectory
    generatedFormulasDir = askdirectory(parent=cntlr.parent,
                                        initialdir=cntlr.config.setdefault("sphinxGeneratedFormulasDir","."),
                                        title='Please select a directory for formulas generated from sphinx')
    cntlr.config["sphinxGeneratedFormulasDir"] = generatedFormulasDir
    cntlr.saveConfig()
    return generatedFormulasDir

def sphinxFilesOpenMenuEntender(cntlr, menu, *args, **kwargs):

    def sphinxFileMenuCommand():
        from arelle import ModelDocument
        import os, sys, traceback
        if not cntlr.modelManager.modelXbrl or cntlr.modelManager.modelXbrl.modelDocument.type not in (
             ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE, ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
            import tkinter.messagebox
            tkinter.messagebox.showwarning(_("arelle - Warning"),
                            _("Import requires an opened DTS"), parent=cntlr.parent)
            return False
        modelXbrl = cntlr.modelManager.modelXbrl
        sphinxFiles = sphinxFilesDialog(cntlr)
        if not sphinxFiles:
            return False
        def backgroundParseSphinxFiles():
            try:
                from .SphinxParser import parse
                sphinxProgs = parse(cntlr, modelXbrl.log, sphinxFiles)
                try:
                    modelXbrl.sphinxContext.sphinxProgs.update(sphinxProgs) # add to previously loaded progs
                except AttributeError:
                    from .SphinxContext import SphinxContext
                    modelXbrl.sphinxContext = SphinxContext(sphinxProgs, modelXbrl)  # first sphinxProgs for DTS
            except Exception as ex:
                cntlr.addToLog(
                    _("[exception] Sphinx Compiling Exception: %(error)s \n%(traceback)s") %
                    {"error": ex,
                     "exc_info": True,
                     "traceback": traceback.format_tb(sys.exc_info()[2])})
        import threading
        thread = threading.Thread(target=backgroundParseSphinxFiles)
        thread.daemon = True
        thread.start()

    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Import Sphinx files...",
                     underline=0,
                     command=sphinxFileMenuCommand)

def sphinxToLBMenuEntender(cntlr, menu, *args, **kwargs):

    def sphinxToLBMenuCommand():
        import os, sys, traceback
        from .FormulaGenerator import generateFormulaLB

        sphinxFiles = sphinxFilesDialog(cntlr)
        if not sphinxFiles:
            return False
        generatedFormulasDir = generatedFormulasDirDialog(cntlr)
        if not generatedFormulasDir:
            return False

        def backgroundSphinxGenerateFormula():
            try:
                generateFormulaLB(cntlr, sphinxFiles, generatedFormulasDir)
            except Exception as ex:
                cntlr.addToLog(
                    _("[exception] Sphinx Compiling Exception: %(error)s \n%(traceback)s") %
                    {"error": ex,
                     "exc_info": True,
                     "traceback": traceback.format_tb(sys.exc_info()[2])})
        import threading
        thread = threading.Thread(target=backgroundSphinxGenerateFormula)
        thread.daemon = True
        thread.start()

    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Compile Sphinx to Formula",
                     underline=0,
                     command=sphinxToLBMenuCommand)

def sphinxToLBCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options to import sphinx files into DTS for validation
    parser.add_option("--import-sphinx",
                      action="store",
                      dest="sphinxFilesForValidation",
                      help=_("Import sphinx files to the DTS for validation.  "
                             "Multiple file names are separated by a '|' character. "))

    # extend command line options with a generate sphinx into formula linkbase option
    parser.add_option("--generate-sphinx-formula-linkbase",
                      action="store",
                      dest="sphinxFilesForFormulaLinkbase",
                      help=_("Generate an XBRL formula linkbase from sphinx files.  "
                             "Multiple file names are separated by a '|' character. "
                             "Files may be xrb archives, xsr source files, or directories of same.  "))
    parser.add_option("--generated-sphinx-formulas-directory",
                      action="store",
                      dest="generatedSphinxFormulasDirectory",
                      help=_("Generated XBRL formula linkbases directory.  "
                             "(If absent, formula linkbases save in sphinx files directory.) "))

def sphinxToLBCommandLineUtilityRun(cntlr, options, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "sphinxFilesForFormulaLinkbase", None):
        from .FormulaGenerator import generateFormulaLB
        generateFormulaLB(cntlr,
                          options.sphinxFilesForFormulaLinkbase.split("|"),
                          options.generatedSphinxFormulasDirectory)

def sphinxCommandLineLoader(cntlr, options, modelXbrl, *args, **kwargs):
    # DTS loaded, add in sphinx files if any
    if getattr(options, "sphinxFilesForValidation", None):
        from .SphinxParser import parse
        from .SphinxContext import SphinxContext
        sphinxProgs = parse(cntlr, modelXbrl.log, options.sphinxFilesForValidation.split('|'))
        modelXbrl.sphinxContext = SphinxContext(sphinxProgs, modelXbrl)

def sphinxValidater(val, *args, **kwargs):
    if hasattr(val.modelXbrl, "sphinxContext"):
        # sphinx is loaded, last step in validation
        from .SphinxValidator import validate
        validate(val.modelXbrl.log, val.modelXbrl.sphinxContext)

def sphinxTestcaseVariationReadMeFirstUris(modelTestcaseVariation, *args, **kwargs):
    xbrlElement = XmlUtil.descendant(modelTestcaseVariation, 'http://www.corefiling.com/sphinx-conformance-harness/2.0', "xbrl")
    if xbrlElement is not None:
        modelTestcaseVariation._readMeFirstUris.append(xbrlElement.textValue)
        return True # found it
    return False  # not a sphinx test case variation

def sphinxTestcaseVariationExpectedResult(modelTestcaseVariation, *args, **kwargs):
    issueElement = XmlUtil.descendant(modelTestcaseVariation, 'http://www.corefiling.com/sphinx-conformance-harness/2.0', "issue")
    if issueElement is not None:
        return issueElement.get("errorCode")
    return None # no issue or not a sphinx test case variation

def sphinxTestcasesStart(cntlr, options, testcasesModelXbrl, *args, **kwargs):
    if options and getattr(options, "sphinxFilesForValidation", None): # command line mode
        testcasesModelXbrl.sphinxFilesList = options.sphinxFilesForValidation.split('|')
    elif (cntlr.hasGui and
          testcasesModelXbrl.modelDocument.xmlRootElement.qname.namespaceURI == 'http://www.corefiling.com/sphinx-conformance-harness/2.0' and
          not hasattr(testcasesModelXbrl, "sphinxFilesList")):
        testcasesModelXbrl.sphinxFilesList = sphinxFilesDialog(cntlr)

def sphinxTestcaseVariationXbrlLoaded(testcasesModelXbrl, instanceModelXbrl, *args, **kwargs):
    # variation has been loaded, may need sphinx rules loaded if interactive
    try:
        sphinxFilesList = testcasesModelXbrl.sphinxFilesList
        # load sphinx
        from .SphinxParser import parse
        sphinxProgs = parse(testcasesModelXbrl.modelManager.cntlr, instanceModelXbrl.log, sphinxFilesList)
        from .SphinxContext import SphinxContext
        instanceModelXbrl.sphinxContext = SphinxContext(sphinxProgs, instanceModelXbrl)  # first sphinxProgs for DTS
    except AttributeError:
        pass # no sphinx


def sphinxTestcaseVariationExpectedSeverity(modelTestcaseVariation, *args, **kwargs):
    issueElement = XmlUtil.descendant(modelTestcaseVariation, 'http://www.corefiling.com/sphinx-conformance-harness/2.0', "issue")
    if issueElement is not None:
        return issueElement.get("severity")
    return None # no issue or not a sphinx test case variation

def sphinxDialogRssWatchFileChoices(dialog, frame, row, options, cntlr, openFileImage, openDatabaseImage, *args, **kwargs):
    from tkinter import PhotoImage, N, S, E, W
    try:
        from tkinter.ttk import Button
    except ImportError:
        from ttk import Button
    from arelle.CntlrWinTooltip import ToolTip
    from arelle.UiUtil import gridCell, label
    # add sphinx formulas to RSS dialog
    def chooseSphinxFiles():
        sphinxFilesList = cntlr.uiFileDialog("open",
                multiple=True,  # expect multiple sphinx files
                title=_("arelle - Select sphinx rules file"),
                initialdir=cntlr.config.setdefault("rssWatchSphinxRulesFilesDir","."),
                filetypes=[(_("Sphinx files .xsr"), "*.xsr"), (_("Sphinx archives .xrb"), "*.xrb")],
                defaultextension=".xsr")
        if sphinxFilesList:
            dialog.options["rssWatchSphinxRulesFilesDir"] = os.path.dirname(sphinxFilesList[0])
            sphinxFilesPipeSeparated = '|'.join(sphinxFilesList)
            dialog.options["sphinxRulesFiles"] = sphinxFilesPipeSeparated
            dialog.cellSphinxFiles.setValue(sphinxFilesPipeSeparated)
        else:  # deleted
            dialog.options.pop("sphinxRulesFiles", "")  # remove entry
    label(frame, 1, row, "Sphinx rules:")
    dialog.cellSphinxFiles = gridCell(frame,2, row, options.get("sphinxRulesFiles",""))
    ToolTip(dialog.cellSphinxFiles, text=_("Select a sphinx rules (file(s) or archive(s)) to to evaluate each filing.  "
                                           "The results are recorded in the log file.  "), wraplength=240)
    chooseFormulaFileButton = Button(frame, image=openFileImage, width=12, command=chooseSphinxFiles)
    chooseFormulaFileButton.grid(row=row, column=3, sticky=W)

def sphinxDialogRssWatchValidateChoices(dialog, frame, row, *args, **kwargs):
    from arelle.UiUtil import checkbox
    dialog.checkboxes += (
       checkbox(frame, 2, row,
                "Sphinx rules",
                "validateSphinxRules"),
    )

def sphinxRssWatchHasWatchAction(rssWatchOptions, *args, **kwargs):
    return rssWatchOptions.get("sphinxRulesFiles") and rssWatchOptions.get("validateSphinxRules")

def sphinxRssDoWatchAction(modelXbrl, rssWatchOptions, rssItem, *args, **kwargs):
    sphinxFiles = rssWatchOptions.get("sphinxRulesFiles")
    if sphinxFiles:
        from .SphinxParser import parse
        sphinxProgs = parse(modelXbrl.modelManager.cntlr, modelXbrl.log, sphinxFiles.split('|'))
        from .SphinxContext import SphinxContext
        modelXbrl.sphinxContext = SphinxContext(sphinxProgs, modelXbrl)  # first sphinxProgs for DTS
        # sphinx is loaded, last step in validation
        from .SphinxValidator import validate
        validate(modelXbrl.log, modelXbrl.sphinxContext)

# plugin changes to model object factor classes
from arelle.ModelTestcaseObject import ModelTestcaseVariation
sphinxModelObjectElementSubstitutionClasses = (
     (qname("{http://www.corefiling.com/sphinx-conformance-harness/2.0}variation"), ModelTestcaseVariation),
    )

__pluginInfo__ = {
    'name': 'Sphinx 2.0 Processor',
    'version': '0.9',
    'description': "This plug-in provides a Sphinx 2.0 processor and a compiler (of a limited subset of Sphinx) into formula linkbase.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'ModelObjectFactory.ElementSubstitutionClasses': sphinxModelObjectElementSubstitutionClasses,
    'CntlrWinMain.Menu.File.Open': sphinxFilesOpenMenuEntender,
    'CntlrWinMain.Menu.Tools': sphinxToLBMenuEntender,
    'CntlrCmdLine.Options': sphinxToLBCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': sphinxToLBCommandLineUtilityRun,
    'CntlrCmdLine.Xbrl.Loaded': sphinxCommandLineLoader,
    'Validate.Finally': sphinxValidater,
    'Testcases.Start': sphinxTestcasesStart,
    'TestcaseVariation.Xbrl.Loaded': sphinxTestcaseVariationXbrlLoaded,
    'ModelTestcaseVariation.ReadMeFirstUris': sphinxTestcaseVariationReadMeFirstUris,
    'ModelTestcaseVariation.ExpectedResult': sphinxTestcaseVariationExpectedResult,
    'ModelTestcaseVariation.ExpectedSeverity': sphinxTestcaseVariationExpectedSeverity,
    'DialogRssWatch.FileChoices': sphinxDialogRssWatchFileChoices,
    'DialogRssWatch.ValidateChoices': sphinxDialogRssWatchValidateChoices,
    'RssWatch.HasWatchAction': sphinxRssWatchHasWatchAction,
    'RssWatch.DoWatchAction': sphinxRssDoWatchAction
}
