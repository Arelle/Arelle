"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING

from arelle.PythonUtil import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyModuleType, SQNameKeyType
from .ModelValueMore import SQName
from .XbrlObject import XbrlReferencableTaxonomyObject

class XbrlEntity(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyModuleType
    name: SQNameKeyType # (required) The entity SQName that identifies the entity so it can be referenced by other objects.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.
