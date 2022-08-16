'''
pluginPackages test case

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

def foo():
	print ("imported packaged plug-in grandchild 1")

__pluginInfo__ = {
    'name': 'Package Listed Import Grandchild 1.1',
    'version': '0.9',
    'description': "This is a packaged grandchild plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Import.Packaged.Entry4': foo,
    # imported plugins
}
