"""
See COPYRIGHT.md for copyright information.
"""

from typing import Optional

from ordered_set import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlModuleType, SQNameKeyType, NonemptySet
from .ModelValueMore import SQName
from .XbrlObject import XbrlReferencableModelObject

class XbrlEntity(XbrlReferencableModelObject):
    """XBRL entity definition.
        Reference: oim-taxonomy#entity-object
    """
    module: XbrlModuleType
    name: SQNameKeyType # (required) The entity SQName that identifies the entity so it can be referenced by other objects.
    properties: Optional[NonemptySet[XbrlProperty]] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.
