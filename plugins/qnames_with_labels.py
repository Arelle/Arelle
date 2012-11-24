#/usr/bin/python
# -*- coding: UTF-8 -*-

"""
This module is an Arelle plugin that shows QNames with their labels in the "Properties" pane
"""
from arelle import ModelInstanceObject, XmlUtil

__author__ = 'R\u00e9gis D\u00e9camps'

def main(controller):
    print("Monkey typing replaces ModelInstanceObject.ModelDimensionValue.propertyView")
    ModelInstanceObject.ModelDimensionValue.propertyView = property(propertyView)
    pass


def propertyView(self):
    """
    :param self: the ModelDimensionValue
    :return: The Property view for a dimension value, with it's label
    """

    if self.isExplicit:
        return qname_label(self.dimension, self.modelXbrl.modelManager.defaultLang), str(self.memberQname)
    else:
        return str(self.dimensionQname), XmlUtil.xmlstring(XmlUtil.child(self), stripXmlns=True, prettyPrint=True)

def qname_label(concept, lang):
    return "{prefix}:{lname} ({label})".format(prefix=concept.qname.prefix, lname=concept.qname.localName, label=concept.label(lang=lang))

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
    'Cntrl.init': main
}