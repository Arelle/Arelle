"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Any, Optional, Union

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlTaxonomyObject import XbrlReferencableTaxonomyObject
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType, DefaultFalse

class XbrlProperty:
    property: QName # (required) The name is a QName that uniquely identifies the property type object.
    value: Any # (required) The value of the property, that must be consistent with the datatype of the property.

    @property
    def propertyView(self):
        return ( str(getattr(self, "property", "")), str(getattr(self, "value", "")) )


class XbrlPropertyType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the property type object.
    dataType: QName # (required) Indicates the dataType of the property value. These are provided as a QName based on the datatypes specified in the XBRL 2.1 specification and any custom datatype defined in the taxonomy.
    enumerationDomain: Optional[QName] # (optional) Used to specify the QName of a domain object that is used to derive enumerated domain members QNames that can be used for the property.
    definitional: Union[bool, DefaultFalse] # (optional) Indicates if the property is definitional. If changes to the property change the meaning of the object it is definitional, if the property provides extra information about the object it is not definitional. If no value is provided the attribute defaults to false.
    allowedObjects: set[QName] # (optional) List of allowable objects that the property can be used with. For example the balance property can only be used with concept objects.
    allowedAsLinkProperty: Union[bool, DefaultFalse] # (optional) Indicates if the property can be used a a properton the link between two objects in a relationship. If no value is provided the attribute defaults to false.
