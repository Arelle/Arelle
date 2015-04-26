'''
pluginPackages test case

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

def foo():
	print ("imported unpackaged plug-in grandchild 2")

__pluginInfo__ = {
    'name': 'Unpackaged Listed Import Grandchild 1.2',
    'version': '0.9',
    'description': "This is a packages-containing child plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Import.Unpackaged.Entry5': foo,
    # imported plugins
}
