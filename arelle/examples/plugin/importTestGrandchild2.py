'''
pluginPackages test case

See COPYRIGHT.md for copyright information.
'''

def foo():
    print ("imported unpackaged plug-in grandchild 2")

__pluginInfo__ = {
    'name': 'Unpackaged Listed Import Grandchild 1.2',
    'version': '0.9',
    'description': "This is a packages-containing child plugin.",
    'license': 'Apache-2',
    'author': 'Workiva, Inc.',
    'copyright': '(c) Copyright 2011-present Workiva, Inc., All rights reserved.',
    # classes of mount points (required)
    'Import.Unpackaged.Entry5': foo,
    # imported plugins
}
