'''
pluginPackages test case

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

def foo():
	print ("imported plug-in child 1")

__pluginInfo__ = {
    'name': 'Import Test Child 1',
    'version': '0.9',
    'description': "This is a packages-containing child plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Import.Example.Entry2': foo,
    # imported plugins
}
