'''
pluginPackages test case

See COPYRIGHT.md for copyright information.
'''

def foo():
    print ("imported unpackaged plug-in grandchild 1")

__pluginInfo__ = {
    'name': 'Unpackaged Listed Import Grandchild 1.1',
    'version': '0.9',
    'description': "This is a packages-containing unpackaged child plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2011-present Workiva, Inc., All rights reserved.',
    # classes of mount points (required)
    'Import.Unpackaged.Entry4': foo,
    # imported plugins
}
