'''
Created on Nov. 14, 2015

@author: Mark V Systems Limited
(c) Copyright 2015 Mark V Systems Limited, All rights reserved.

This module is provided as a "loader" for all the validation modules, and can be specified
as a plugin to load all the validate subdirectory plugins.

'''
__pluginInfo__ = {
    'name': 'Import all validate modules',
    'version': '1.0',
    'description': "This is imports plugin modules in the validate subtree.",
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2015 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    # imported plugins
    'import': ("module_subtree",) 
}
