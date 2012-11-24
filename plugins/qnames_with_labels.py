#/usr/bin/python
# -*- coding: UTF-8 -*-

"""
This module is an Arelle plugin that shows QNames with their labels in the "Properties" pane
"""
from arelle import ModelInstanceObject

__author__ = 'R\u00e9gis D\u00e9camps'

def main():
    ModelInstanceObject.ModelDimensionValue.propertyView = propertyView

def propertyView(self):
    """

    :return: The Property view for a dimension vlue, with it'slabels
    """
    if self.isExplicit:
        return (str(self.dimensionQname),str(self.memberQname))
    else:
        return (str(self.dimensionQname), XmlUtil.xmlstring( XmlUtil.child(self), stripXmlns=True, prettyPrint=True ) )
__pluginInfo__ = {
    'name': 'dim_qnames',
    'version': '0.1',
    'description': '''Displays QNames as well as Labels for Dimensions values in the "Properties" Pane''',
    'localeURL': "locale",
    'localeDomain': 'dim_qnames',
    'license': 'Apache-2',
    'author': 'R\u00e9gis D\u00e9camps',
    'copyright': '(c) Copyright 2012 R\u00e9gis D\u00e9camps',
    # classes of mount points (required)
    'Cntlr.init': main
}