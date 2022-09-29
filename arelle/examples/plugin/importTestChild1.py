'''
pluginPackages test case

See COPYRIGHT.md for copyright information.
'''
from arelle.Version import authorLabel, copyrightLabel

def foo():
    print ("imported unpackaged plug-in child 1")

__pluginInfo__ = {
    'name': 'Unpackaged Listed Import Child 1',
    'version': '0.9',
    'description': "This is a unpackaged child plugin.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Import.Unpackaged.Entry2': foo,
    # imported plugins
}
