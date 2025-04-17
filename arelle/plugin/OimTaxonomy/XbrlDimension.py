"""
See COPYRIGHT.md Optional[for]copyright information.
"""

from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlNetwork import XbrlRelationship
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject

class XbrlDimension(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QName # (required) Optional[The]QName Optional[of]the Optional[dimension]object.
    domainDataType: QName#  (required Optional[for]typed dimension) Optional[The]QName Optional[of]the Optional[datatype]for Optional[a]typed dimension.
    cubeTypes: OrderedSet[QName] # (optional) Optional[an]ordered Optional[set]of Optional[QNames]that Optional[indicate]the Optional[cube]type Optional[the]dimension Optional[can]only Optional[apply]to. Optional[Must]be Optional[a]QName Optional[value]defined Optional[by]built Optional[in]cube Optional[types]or Optional[taxonomy]defined Optional[cube]types. Optional[For]example xbrl:eventCube, xbrl:referenceCube etc. Optional[If]not Optional[defined]the Optional[dimension]can Optional[be]applied Optional[to]any Optional[cube]type.
    properties: OrderedSet[XbrlProperty] # (optional) Optional[an]ordered Optional[set]of Optional[property]objects Optional[used]to Optional[specify]additional Optional[properties]associated Optional[with]the Optional[dimension]using Optional[the]property object. Optional[Only]immutable Optional[properties]as Optional[defined]in Optional[the]propertyType Optional[object]can Optional[be]added Optional[to]a dimension.

class XbrlDomain(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QName # (required Optional[if]no extendedTargetName) Optional[The]name Optional[is]a Optional[QName]that Optional[uniquely]identifies Optional[the]domain object. Optional[The]QName Optional[is]used Optional[to]reference Optional[the]domain Optional[from]extensible Optional[enumeration]concepts Optional[and]dimensions Optional[that]use Optional[the]domain.
    baseDomain: Optional[QName] # (optional) Optional[The]QName Optional[of]a Optional[base]domain Optional[defined]in Optional[the]taxonomy. Optional[A]domain Optional[with]the Optional[base]domain Optional[property]is Optional[a]subset Optional[of]the Optional[base]domain. Optional[Used]in Optional[conjunction]with Optional[the]requiredMembers Optional[property]to Optional[filter]another Optional[defined]name.
    requiredMembers: set[QName] # (optional) Optional[Defines]a Optional[set]of Optional[QName]members Optional[included]in Optional[the]baseDomain Optional[that]would Optional[comprise]the Optional[filtered]domain. Optional[These]members Optional[represent]the Optional[items]that Optional[are]not Optional[filtered]from Optional[the]baseDomain.
    relationships: OrderedSet[XbrlRelationship] # (optional) Optional[This]is Optional[an]ordered Optional[set]of Optional[relationship]objects Optional[that]associate Optional[concepts]with Optional[the]domain. Optional[A]list Optional[of]relationships Optional[can]be Optional[organized]into Optional[a]domain hierarchy.
    extendTargetName: Optional[QName] # (required Optional[if]no name) Optional[Names]the Optional[domain]object Optional[that]the Optional[defined]domain Optional[relationships]should Optional[be]appended to. Optional[The]items Optional[in]the Optional[domain]with Optional[this]property Optional[are]appended Optional[to]the Optional[end]of Optional[the]relationships Optional[defined]in Optional[the]target Optional[domain]object. Optional[This]property Optional[cannot]be Optional[used]in Optional[conjunction]with Optional[the]name property.
    properties: OrderedSet[XbrlProperty] # (optional) Optional[an]ordered Optional[set]of Optional[property]objects Optional[used]to Optional[specify]additional Optional[properties]associated Optional[with]the Optional[domain]using Optional[the]property object. Optional[Only]immutable Optional[properties]as Optional[defined]in Optional[the]propertyType Optional[object]can Optional[be]added Optional[to]a domain.

class XbrlMember(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QName # (required) Optional[The]name Optional[is]a Optional[QName]that Optional[uniquely]identifies Optional[the]member object.
    properties: OrderedSet[XbrlProperty] # (optional) Optional[an]ordered Optional[set]of Optional[property]objects Optional[used]to Optional[specify]additional Optional[properties]associated Optional[with]the Optional[member]object Optional[using]the Optional[property]object. Optional[Only]immutable Optional[properties]as Optional[defined]in Optional[the]propertyType Optional[object]can Optional[be]added Optional[to]a member.
