"""
See COPYRIGHT.md for copyright information.
"""

from typing import Optional, Union

from arelle.ModelValue import QName, AnyURI
from ordered_set import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlModuleAlias, QNameKeyType, DefaultTrue, NonemptySet
from .ModelValueMore import SQName
from .XbrlObject import XbrlReferencableModelObject, XbrlTaxonomyTagObject

class XbrlReference(XbrlTaxonomyTagObject):
    """ Reference Object
        Reference: oim-taxonomy#reference-object
    """
    module: XbrlModuleAlias
    name: QNameKeyType # (required if no extendTargetame) The name is a QName that uniquely identifies the reference object.
    extends: Optional[QName] # (required if no name) Names the reference object that the defined forObjects property should be appended to. The forObjects property in the reference with this property are appended to the end of the forObjects property defined in the target reference object. This property cannot be used in conjunction with the name property.
    isExtensible: Union[bool, DefaultTrue] # (optional) If set to false, the reference is non-extensible and no importing taxonomy may augment it using extends. If set to true or omitted, the reference may be extended. The default value is true.
    forObjects: Optional[NonemptySet[QName]] # (optional) Defines a set of ordered QNames that the reference is associated with.
    referenceType: QName # (required) A QName representing the reference type of the reference. This can be a taxonomy defined reference or a standard XBRL reference included in the specification.
    language: Optional[str] # (optional) Defines the language of the reference using a valid BCP 47 [BCP47] language code.
    properties: Optional[NonemptySet[XbrlProperty]] # (optional) an ordered set of property objects used to identify the properties of the reference.

    @property
    def _type(self):
        return self.referenceType

class XbrlReferenceType(XbrlReferencableModelObject):
    """ Reference Type Object
        Reference: oim-taxonomy#referencetype-object
    """
    module: XbrlModuleAlias
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the reference type object.
    uri: Optional[AnyURI] # (optional) A uri used to identify the reference type of reference objects for backward compatability with XBRL 2.1 taxonomies.
    allowedObjects: Optional[NonemptySet[QName]] # (optional) Defines an ordered set of object types that can use the referenceType. MUST NOT be empty if provided.
    orderedProperties: Optional[NonemptySet[QName]] # (optional) Defines an ordered set of property QNames that can be used with the reference.
    requiredProperties: Optional[NonemptySet[QName]] # (optional) Defines an ordered set of property QNames that must be included within a defined reference type.
