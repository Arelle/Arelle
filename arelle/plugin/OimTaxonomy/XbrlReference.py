"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .ModelValueMore import SQName
from .XbrlTaxonomyObject import XbrlReferencableTaxonomyObject, XbrlTaxonomyTagObject

class XbrlReference(XbrlTaxonomyTagObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required if no extendTargetame) The name is a QName that uniquely identifies the reference object.
    extendTargetName: Optional[QName] # (required if no name) Names the reference object that the defined relatedNames property should be appended to. The relatedNames property in the reference with this property are appended to the end of the relatedName property defined in the target reference object. This property cannot be used in conjunction with the name property.
    relatedNames: OrderedSet[QName] # (optional) Defines a set of ordered QNames that the reference is associated with.
    referenceType: QName # (required) A QName representing the reference type of the reference. This can be a taxonomy defined reference or a standard XBRL reference included in the specification.
    language: Optional[str] # (optional) Defines the language of the reference using a valid BCP 47 [BCP47] language code.
    properties: OrderedSet[XbrlProperty] # (optional) an ordered set of property objects used to identify the properties of the reference.

    @property
    def _type(self):
        return self.referenceType

class XbrlReferenceType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the reference type object.
    uri: Optional[AnyURI] # (optional) A uri used to identify the reference type of reference objects for backward compatability with XBRL 2.1 taxonomies.
    allowedObjects: OrderedSet[QName] # (optional) Defines an ordered set of object types that can use the referenceType.
    orderedPropertiesproperties: OrderedSet[XbrlProperty] # (optional) Defines an ordered set of property QNames that can be used with the reference.
    requiredProperties: OrderedSet[QName] # (optional) Defines an ordered set of property QNames that must be included within a defined reference type.
