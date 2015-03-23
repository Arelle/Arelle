'''
pluginPackages test case

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
from arelle.PluginManager import pluginClassMethods

def parentMenuEntender(cntlr, menu):
    menu.add_command(label="Parent exercise descendants", underline=0, command=lambda: parentMenuCommand(cntlr) )

def parentMenuCommand(cntl):
    for i in range(1,6):
        for pluginMethod in pluginClassMethods("Import.Example.Entry{}".format(i)):
            pluginMethod()
	
def parentCommandLineOptionExtender(parser):
    parser.add_option("--parentImportExample", 
                      action="store_true", 
                      dest="parentImportExample", 
                      help=_('Test that imported plug-ins were actually loaded and activated"'))

def parentCommandLineUtilityRun(cntlr, options, **kwargs):
    parentMenuCommand(cntlr)
    
def foo():
	print ("parent of imported plug-ins")

__pluginInfo__ = {
    'name': 'Import Test Parent',
    'version': '0.9',
    'description': "This is a imports-containing parent plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': parentMenuEntender,
    'CntlrCmdLine.Options': parentCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': parentCommandLineUtilityRun,
    'Import.Example.Entry1': foo,
    # imported plugins
    'import': ('importTestChild1.py', 'importTestChild2.py')
}
