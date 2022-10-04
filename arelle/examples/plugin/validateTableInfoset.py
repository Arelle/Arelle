'''
This is an example of a plug-in to both GUI menu and command line/web service
that will provide an option to replace behavior of table linkbase validation to
generate vs diff table linkbase infoset files.

See COPYRIGHT.md for copyright information.
'''
from arelle.Version import authorLabel, copyrightLabel

def validateTableInfosetMenuEntender(cntlr, validateMenu):
    # Extend menu with an item for the save infoset plugin
    cntlr.modelManager.generateTableInfoset = cntlr.config.setdefault("generateTableInfoset",False)
    from tkinter import BooleanVar
    generateTableInfoset = BooleanVar(value=cntlr.modelManager.generateTableInfoset)
    def setTableInfosetOption(*args):
        cntlr.config["generateTableInfoset"] = cntlr.modelManager.generateTableInfoset = generateTableInfoset.get()
    generateTableInfoset.trace("w", setTableInfosetOption)
    validateMenu.add_checkbutton(label=_("Generate table infosets (instead of diffing them)"),
                                 underline=0,
                                 variable=generateTableInfoset, onvalue=True, offvalue=False)

def validateTableInfosetCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--generate-table-infoset",
                      action="store_true",
                      dest="generateTableInfoset",
                      help=_("Generate table instance infosets (instead of diffing them)."))

def validateTableInfosetCommandLineXbrlLoaded(cntlr, options, modelXbrl, *args, **kwargs):
    cntlr.modelManager.generateTableInfoset = getattr(options, "generateTableInfoset", False)

def validateTableInfoset(modelXbrl, resultTableUri):
    diffToFile = not getattr(modelXbrl.modelManager, 'generateTableInfoset', False)
    from arelle import ViewFileRenderedGrid
    ViewFileRenderedGrid.viewRenderedGrid(modelXbrl,
                                          resultTableUri,
                                          diffToFile=diffToFile)  # false to save infoset files
    return True # blocks standard behavior in validate.py

__pluginInfo__ = {
    'name': 'Validate Table Infoset (Optional behavior)',
    'version': '0.9',
    'description': "This plug-in adds a feature modify batch validation of table linkbase to save, versus diff, infoset files.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Validation': validateTableInfosetMenuEntender,
    'CntlrCmdLine.Options': validateTableInfosetCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': validateTableInfosetCommandLineXbrlLoaded,
    'Validate.TableInfoset': validateTableInfoset,
}
