'''
pluginPackages test case

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
# this module would raise system error due to PEP 366 after python 3.4.3

def foo():
    print ("imported unpackaged plug-in imported relative 1.1")

__pluginInfo__ = {
    'name': 'Unpackaged Relative Import 1.1',
    'version': '0.9',
    'description': "This is a packages-containing unpackaged imported plugin.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Import.Unpackaged.Entry7': foo,
    # imported plugins
}
