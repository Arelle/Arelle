'''
See COPYRIGHT.md for copyright information.

This module is provided as a "loader" for all the validation modules, and can be specified
as a plugin to load all the validate subdirectory plugins.

'''
from arelle.Version import authorLabel, copyrightLabel

__pluginInfo__ = {
    'name': 'Import all validate modules',
    'version': '1.0',
    'description': "This is imports plugin modules in the validate subtree.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    # imported plugins
    'import': ("module_subtree",)
}
