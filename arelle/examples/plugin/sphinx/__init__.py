'''
sphinx is an example of a package plug-in to both GUI menu and command line/web service
that compiles a Sphinx Rules file into an XBRL Formula Linkbase either to be saved or to
be directly executed by Arelle XBRL Formula processing.

This plug-in is a python package, and can be loaded by referencing the containing
directory (usually, "sphinx"), and selecting this "__init__.py" file within the sphinx
directory (such as in a file chooser).

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

import time, os, io, sys

logMessage = None

def sphinxFilesDialog(cntlr):
    # get multiple file names of the sphinx files
    sphinxFiles = cntlr.uiFileDialog("open",
            multiple=True,  # expect multiple sphinx files
            title=_("arelle - Open sphinx rules file"),
            initialdir=cntlr.config.setdefault("sphinxRulesFileDir","."),
            filetypes=[(_("Sphinx file .xsr"), "*.xsr")],
            defaultextension=".xsr")
    if not sphinxFiles:
        return None
    cntlr.config["sphinxRulesFileDir"] = os.path.dirname(sphinxFiles[0])
    cntlr.saveConfig()
    return sphinxFiles

def sphinxFilesOpenMenuEntender(cntlr, menu):
    
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
        try: 
            from .SphinxParser import parse
            sphinxProgs = parse(cntlr, modelXbrl.log, sphinxFiles)
            try:
                modelXbrl.sphinxContext.sphinxProgs.update(sphinxProgs) # add to previously loaded progs
            except AttributeError:
                from .SphinxContext import SphinxContext
                modelXbrl.sphinxContext = SphinxContext( sphinxProgs )  # first sphinxProgs for DTS
        except Exception as ex:
            cntlr.addToLog(
                _("[exception] Sphinx Compiling Exception: %(error)s \n%(traceback)s") % 
                {"error": ex,
                 "exc_info": True,
                 "traceback": traceback.format_tb(sys.exc_info()[2])})
            
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Import Sphinx files...", 
                     underline=0, 
                     command=sphinxFileMenuCommand)

def sphinxToLBMenuEntender(cntlr, menu):
    
    def sphinxToLBMenuCommand():
        import os, sys, traceback
        from .FormulaGenerator import generateFormulaLB
        
        sphinxFiles = sphinxFilesDialog(cntlr)
        if not sphinxFiles:
            return False    
        try: 
            generateFormulaLB(cntlr, sphinxFiles)
        except Exception as ex:
            cntlr.addToLog(
                _("[exception] Sphinx Compiling Exception: %(error)s \n%(traceback)s") % 
                {"error": ex,
                 "exc_info": True,
                 "traceback": traceback.format_tb(sys.exc_info()[2])})
            
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Compile Sphinx into Formula Linkbase", 
                     underline=0, 
                     command=sphinxToLBMenuCommand)

def sphinxToLBCommandLineOptionExtender(parser):
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
                             "Multiple file names are separated by a '|' character. "))
    parser.add_option("--generated-sphinx-formulas-directory", 
                      action="store", 
                      dest="generatedSphinxFormulasDirectory", 
                      help=_("Generated XBRL formula linkbases directory.  "
                             "(If absent, formula linkbases save in sphinx files directory.) "))

def sphinxToLBCommandLineUtilityRun(cntlr, options):
    # extend XBRL-loaded run processing for this option
    if options.sphinxFilesForFormulaLinkbase:
        from .FormulaGenerator import generateFormulaLB
        generateFormulaLB(cntlr, 
                          options.sphinxFilesForFormulaLinkbase.split("|"),
                          options.generatedSphinxFormulasDirectory)

def sphinxCommandLineLoader(cntlr, options, modelXbrl):
    # DTS loaded, add in sphinx files if any
    if options.sphinxFilesForValidation:
        from .SphinxParser import parse
        from .SphinxContext import SphinxContext
        sphinxProgs = parse(cntlr, logMessage, options.sphinxFilesForValidation.split('|'))
        modelXbrl.sphinxContext = SphinxContext( sphinxProgs )
        
def sphinxValidater(val):
    if hasattr(val.modelXbrl, "sphinxContext"):
        # sphinx is loaded, last step in validation
        from .SphinxValidator import validate
        validate(val.modelXbrl.log, val.modelXbrl.sphinxContext)

__pluginInfo__ = {
    'name': 'Compile Sphinx Formula Linkbase',
    'version': '0.9',
    'description': "This plug-in compiles a formula linkbase from a file containing sphinx rules.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.File.Open': sphinxFilesOpenMenuEntender,
    'CntlrWinMain.Menu.Tools': sphinxToLBMenuEntender,
    'CntlrCmdLine.Options': sphinxToLBCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': sphinxToLBCommandLineUtilityRun,
    'CntlrCmdLine.Xbrl.Loaded': sphinxCommandLineLoader,
    'Validate.Finally': sphinxValidater,
}