'''
pluginPackages test case

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
from arelle.PluginManager import pluginClassMethods
# . relative import only works inside a package now, see https://www.python.org/dev/peps/pep-0366/
# following two imports raise system error due to PEP 366 after python 3.4.3
# from . import importTestImported1
# from .importTestImported1 import foo

def parentMenuEntender(cntlr, menu):
    menu.add_command(label="Unpackaged Parent exercise descendants", underline=0, command=lambda: parentMenuCommand(cntlr) )

def parentMenuCommand(cntl):
    for i in range(1,100):
        for pluginMethod in pluginClassMethods("Import.Unpackaged.Entry{}".format(i)):
            pluginMethod()

def parentCommandLineOptionExtender(parser):
    parser.add_option("--unpackageParentImportExample",
                      action="store_true",
                      dest="unpackageParentImportExample",
                      help=_('Test that unpackaged imported plug-ins were actually loaded and activated"'))

def parentCommandLineUtilityRun(cntlr, options, **kwargs):
    if options.unpackageParentImportExample:
        parentMenuCommand(cntlr)

def foo():
    print ("parent of imported unpackaged plug-ins")

__pluginInfo__ = {
    'name': 'Import Test Unpackaged Parent',
    'version': '0.9',
    'description': "This is a imports-containing unpackaged parent plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': parentMenuEntender,
    'CntlrCmdLine.Options': parentCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': parentCommandLineUtilityRun,
    'Import.Unpackaged.Entry1': foo,
    # imported plugins
    'import': ('importTestChild1.py', 'importTestChild2.py', "module_import_subtree")
}
