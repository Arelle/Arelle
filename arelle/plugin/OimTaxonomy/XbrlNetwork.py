"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Any
from collections import defaultdict

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject

class XbrlRelationship(XbrlTaxonomyObject):
    source: QName # (required) This attribute identifies the source concept of the relationship type. The value of the attribute must be a QName.
    target: QName # (required) This attribute identifies the target concept of the relationship type. The value of the attribute must be a QName.
    order: Optional[int] # (optional) This is used to order the relationships if the order is different than the order that the relationship appears in the list of relationships. The order property can be used on any relationship type.
    weight: Optional[int] # (required on summation-item) Weight of a summation-item relationship type.
    preferredLabel: Optional[QName] # (optional on parent-child) The preferred label QName of a parent-child relationship type.
    usable: Optional[bool] # (optional on domain-member) Indicates if the member value is useable on a domain-member relationship.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.

    @property
    def propertyView(self):
        nestedProperties = [("source",str(self.source)), ("target",str(self.target))]
        if hasattr(self, "order"):
            nestedProperties.append( ("order", str(self.order)) )
        if hasattr(self, "weight"):
            nestedProperties.append( ("weight", str(self.weight)) )
        if hasattr(self, "preferredLabel"):
            nestedProperties.append( ("preferredLabel", str(self.preferredLabel)) )
        if hasattr(self, "useable"):
            nestedProperties.append( ("useable", str(self.useable)) )
        if getattr(self, "properties", None):
            for propObj in self.properties:
                nestedProperties.append( (str(propObj.propertyTypeName), str(propObj.propertyValue)) )
        return ("relationship", f"{str(self.source)}\u2192{self.target}", tuple(nestedProperties))

class XbrlRelationshipSet:
    _relationshipsFrom: Optional[dict[QName, list[XbrlRelationship]]]
    _relationshipsTo: Optional[dict[QName, list[XbrlRelationship]]]
    _roots: Optional[OrderedSet[QName]]

    def __init__(self):
        self._relationshipsFrom = self._relationshipsTo = self._roots = None
        if hasattr(self, "roots") and len(getattr(self, "roots")) > 1:
            self._roots = getattr(self, "roots")

    @property
    def relationshipsFrom(self):
        if not hasattr(self, "_relationshipsFrom"):
            self._relationshipsFrom = defaultdict(list)
            for relObj in self.relationships:
                if relObj.source is not None:
                    self._relationshipsFrom[relObj.source].append(relObj)
        return self._relationshipsFrom

    @property
    def relationshipsTo(self):
        if not hasattr(self, "_relationshipsTo"):
            self._relationshipsTo = defaultdict(list)
            for relObj in self.relationships:
                if relObj.target is not None:
                    self._relationshipsTo[relObj.target].append(relObj)
        return self._relationshipsTo

    @property
    def relationshipRoots(self):
        if not hasattr(self, "_roots"):
            if hasattr(self, "roots") and len(getattr(self, "roots")) > 1:
                self._roots = getattr(self, "roots")
            else:
                relsFrom = self.relationshipsFrom
                relsTo = self.relationshipsTo
                self._roots = [qnFrom
                               for qnFrom, relsFrom in relsFrom.items()
                               if qnFrom not in relsTo or
                               (len(relsFrom) == 1 and # root-level self-looping ar
                                len(relsTo[qnFrom]) == 1 and
                                relsFrom[0].source == relsFrom[0].target)]
        return self._roots

class XbrlNetwork(XbrlReferencableTaxonomyObject, XbrlRelationshipSet):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required if no extendedTargetName) The name is a QName that uniquely identifies the network object.
    relationshipTypeName: QName # (required if no extendedTargetName) The relationshipType object of the network expressed as a QName such as xbrl:parent-child
    roots: OrderedSet[QName] # (optional) A list of the root objects of the network object. This allows a single object to be associated with a network without the need for a relationship. The order of roots in the list indicates the order in which the roots should appear. If no root is specified for a list of relationships the roots property is inferred from the relationships defined.
    relationships: OrderedSet[XbrlRelationship] # (optional) A set of the relationship objects comprising the network.
    extendTargetName: Optional[QName] # (required if no name) Names the network object that the defined network relationships should be appended to. The items in the network with this property are appended to the end of the relationships or roots defined in the target network object. This property cannot be used in conjunction with the relationshipTypeName and name property.
    properties: OrderedSet[XbrlProperty] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.

class XbrlRelationshipType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the relationshipType object.
    uri: AnyURI # (optional) The URI identifies the uri of the relationship type for historical and backward compatibility purposes.
    cycles: QName # (required) The cycles attribute indicates if the relationship when used in a hierarchy can include cycles. Possible values are any, none, and undirected. Any means cycles are allowed in the relationships, undirected means cycles are allowed, but they must be undirected, and none means cycles are not allowed in the relationships.
    allowedLinkProperties: OrderedSet[QName] # (optional) Defines an ordered set of property QNames that can be included on the relationship type. Each property is represented as the QName defined in the propertyType object. Only properties defined in this list can be added to the specific relationship type.
    requiredLinkProperties: OrderedSet[QName] # (optional) Defines an ordered set of property QNames that MUST be included on the relationship type. Each property is represented as the QName defined in the propertyType object.
    sourceObjects: set[QName] # (optional) Defines a list of source object types that can be used as the source for the relationship. The only permitted values are referenceable taxonomy objects
    targetObjects: set[QName] # (optional) Defines a list of target object types that can be used as the source for the relationship. The only permitted values are referenceable taxonomy objects
