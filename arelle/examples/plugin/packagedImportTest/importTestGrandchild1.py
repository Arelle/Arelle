'''
pluginPackages test case

See COPYRIGHT.md for copyright information.
'''
from arelle.Version import authorLabel, copyrightLabel

def foo():
    print ("imported packaged plug-in grandchild 1")

__pluginInfo__ = {
    'name': 'Package Listed Import Grandchild 1.1',
    'version': '0.9',
    'description': "This is a packaged grandchild plugin.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Import.Packaged.Entry4': foo,
    # imported plugins
}
