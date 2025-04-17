"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Set

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject

class XbrlAbstract(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QName # (required) The name is a QName that uniquely identifies the abstract object.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.
