"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject

class XbrlGroup(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The group object QName that identifies the group so it can be referenced by other objects.
    groupURI:Optional[AnyURI] # (optional) The group URI that uniquely identifies the group and id used for backward compatibility with roles.
    properties: OrderedSet[XbrlProperty] # (optional) an ordered set of property objects used to specify additional properties associated with the group using the property object. Only immutable properties as defined in the propertyType object can be added to a group.

class XbrlGroupContent(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    groupName: QName # (required) The QName of the group object.
    relatedNames: OrderedSet[QName] # (required) An ordered set of network object or cube object QNames that are included in the group object. The order of the set determines the order they appear in the group. The set cannot be empty. The set can only include the QNames of network and cube objects.
