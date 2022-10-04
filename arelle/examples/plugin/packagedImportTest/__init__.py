'''
pluginPackages test case

See COPYRIGHT.md for copyright information.
'''
from os import path
from arelle.PluginManager import pluginClassMethods
from arelle.Version import authorLabel, copyrightLabel
from . import importTestImported1
from .importTestImported1 import foo

def parentMenuEntender(cntlr, menu):
    menu.add_command(label="Packaged Parent exercise descendants", underline=0, command=lambda: parentMenuCommand(cntlr) )

def parentMenuCommand(cntl):
    for i in range(1,100):
        for pluginMethod in pluginClassMethods("Import.Packaged.Entry{}".format(i)):
            pluginMethod()

def parentCommandLineOptionExtender(parser):
    parser.add_option("--packagedParentImportExample",
                      action="store_true",
                      dest="packagedParentImportExample",
                      help=_('Test that imported plug-ins were actually loaded and activated"'))

def parentCommandLineUtilityRun(cntlr, options, **kwargs):
    if options.packagedParentImportExample:
        parentMenuCommand(cntlr)

def foo():
    print ("parent (__init__) of imported packaged plug-ins")

__pluginInfo__ = {
    'name': 'Import Test Package Parent',
    'version': '0.9',
    'description': "This is a imports-containing packaged (__init__) plugin.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': parentMenuEntender,
    'CntlrCmdLine.Options': parentCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': parentCommandLineUtilityRun,
    'Import.Packaged.Entry1': foo,
    # imported plugins
    'import': ('importTestChild1.py', 'importTestChild2.py', "module_import_subtree")
}
