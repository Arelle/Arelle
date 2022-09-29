'''
pluginPackages test case

See COPYRIGHT.md for copyright information.
'''

def foo():
    print ("imported packaged plug-in child 1")

__pluginInfo__ = {
    'name': 'Package Listed Import Child 1',
    'version': '0.9',
    'description': "This is a packaged child plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2011-present Workiva, Inc., All rights reserved.',
    # classes of mount points (required)
    'Import.Packaged.Entry2': foo,
    # imported plugins
}
