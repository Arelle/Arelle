"""
See COPYRIGHT.md for copyright information.
"""

from typing import Optional

from arelle.ModelValue import QName
from ordered_set import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlModuleType, QNameKeyType, NonemptySet
from .XbrlObject import XbrlReferencableModelObject

class XbrlHeading(XbrlReferencableModelObject):
    """ Heading Object
        Reference: oim-taxonomy.md#heading-object
    """
    module: XbrlModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the heading object.
    properties: Optional[NonemptySet[XbrlProperty]] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.
