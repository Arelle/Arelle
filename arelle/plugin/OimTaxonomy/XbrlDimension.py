"""
See COPYRIGHT.md Optional[for]copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union

from arelle.ModelValue import QName, qname
from arelle.PythonUtil import OrderedSet
from .XbrlConst import xbrl
from .XbrlNetwork import XbrlRelationship, XbrlRelationshipSet
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyModuleType, QNameKeyType, DefaultFalse
from .XbrlObject import XbrlReferencableTaxonomyObject

class XbrlDimension(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyModuleType
    name: QNameKeyType # (required) Optional[The]QName [of]the [dimension]object.
    domainRoot: QName # (required) The QName of the domain root object for the dimension. All dimensions, whether typed or explicit, must reference a domain root.
    cubeTypes: OrderedSet[QName] # (optional) Optional[an]ordered Optional[set]of Optional[QNames]that Optional[indicate]the Optional[cube]type Optional[the]dimension Optional[can]only Optional[apply]to. Optional[Must]be Optional[a]QName Optional[value]defined Optional[by]built Optional[in]cube Optional[types]or Optional[taxonomy]defined Optional[cube]types. Optional[For]example xbrl:eventCube, xbrl:referenceCube etc. Optional[If]not Optional[defined]the Optional[dimension]can Optional[be]applied Optional[to]any Optional[cube]type.
    properties: OrderedSet[XbrlProperty] # (optional) Optional[an]ordered Optional[set]of Optional[property]objects Optional[used]to Optional[specify]additional Optional[properties]associated Optional[with]the Optional[dimension]using Optional[the]property object. Optional[Only]immutable Optional[properties]as Optional[defined]in Optional[the]propertyType Optional[object]can Optional[be]added Optional[to]a dimension.

class XbrlDomain(XbrlReferencableTaxonomyObject, XbrlRelationshipSet):
    taxonomy: XbrlTaxonomyModuleType
    name: Optional[QNameKeyType] # (required if no extendTargetName) The QName that uniquely identifies the domain object. The QName is used to reference the domain from extensible enumeration concepts and dimensions that use the domain.
    root: Optional[QName] # (required if no extendedTargetName) The QName that uniquely identifies the root of the domain object. This must be a domain root object.
    domainDataType: Optional[QName] # (optional) The QName of the data type for a typed domain. When this property is present, the domain is considered a "typed domain" and dimensions referencing this domain's root will only permit typed values. If this property is absent, the domain is an "explicit domain".
    relationships: OrderedSet[XbrlRelationship] # (optional) This is an ordered set of relationship objects that associate taxonomy objects with the domain. A list of relationships can be organised into a domain hierarchy. For typed domains (where domainDataType is present), relationships are optional as values are constrained by the data type rather than member hierarchies.
    extendTargetName: Optional[QName] # (required Optional[if]no name) Optional[Names]the Optional[domain]object Optional[that]the Optional[defined]domain Optional[relationships]should Optional[be]appended to. Optional[The]items Optional[in]the Optional[domain]with Optional[this]property Optional[are]appended Optional[to]the Optional[end]of Optional[the]relationships Optional[defined]in Optional[the]target Optional[domain]object. Optional[This]property Optional[cannot]be Optional[used]in Optional[conjunction]with Optional[the]name property.
    completeDomain: Union[bool, DefaultFalse] # (optional) If set to true, the domain is considered complete, meaning that it includes all relationships and members necessary for the domain. If set to false, the domain may be incomplete, and additional relationships or members may be added by an extension taxonomy. The default value is false.
    properties: OrderedSet[XbrlProperty] # (optional) Optional[an]ordered Optional[set]of Optional[property]objects Optional[used]to Optional[specify]additional Optional[properties]associated Optional[with]the Optional[domain]using Optional[the]property object. Optional[Only]immutable Optional[properties]as Optional[defined]in Optional[the]propertyType Optional[object]can Optional[be]added Optional[to]a domain.

class XbrlDomainRoot(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyModuleType
    name: QNameKeyType # (required) The QName that uniquely identifies the domain root object.
    allowedDomainItems: OrderedSet[QName] # Optional[set]of Optional[QNames]that Optional[indicate]the Optional[cube]type Optional[the]dimension Optional[can]only Optional[apply]to. Optional[Must]be Optional[a]QName Optional[value]defined Optional[by]built Optional[in]cube Optional[types]or Optional[taxonomy]defined Optional[cube]types. Optional[For]example xbrl:eventCube, xbrl:referenceCube etc. Optional[If]not Optional[defined]the Optional[dimension]can Optional[be]applied Optional[to]any Optional[cube]type.
    properties: OrderedSet[XbrlProperty] # (optional) an ordered set of property objects used to specify additional properties associated with the domain root object using the property object.

class XbrlMember(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyModuleType
    name: QNameKeyType # (required) Optional[The]name Optional[is]a Optional[QName]that Optional[uniquely]identifies Optional[the]member object.
    properties: OrderedSet[XbrlProperty] # (optional) Optional[an]ordered Optional[set]of Optional[property]objects Optional[used]to Optional[specify]additional Optional[properties]associated Optional[with]the Optional[member]object Optional[using]the Optional[property]object. Optional[Only]immutable Optional[properties]as Optional[defined]in Optional[the]propertyType Optional[object]can Optional[be]added Optional[to]a member.

xbrlMemberObj = qname(xbrl, "xbrl:member")
